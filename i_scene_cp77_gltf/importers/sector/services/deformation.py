from __future__ import annotations

from dataclasses import dataclass

import bpy
import numpy as np
from mathutils import Matrix

from ....blender.identity import rna_identity
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ...common.collections import remap_copied_object_references
from ..context import DeformationDataError
from ..objects import copy_object, new_collection, new_empty
from .buffers import column_matrix


@dataclass(slots=True, frozen=True)
class DeformationAxisContract:
    axis_index: int
    axis_sign: float
    axis_name: str


DEFORMATION_AXIS_CONTRACTS = {
    "worldBendedMeshNode": DeformationAxisContract(1, 1.0, "POS_Y"),
    "worldCableMeshNode": DeformationAxisContract(0, -1.0, "NEG_X"),
}


@dataclass(slots=True, frozen=True)
class DeformationFrameMetrics:
    dominant_axis_index: int
    dominant_axis_span: float
    monotonic_contract_axis: bool


@dataclass(slots=True, frozen=True)
class DeformationAnalysis:
    node_type: str
    contract: DeformationAxisContract
    frames: tuple
    source_axis_min: float
    source_axis_max: float
    can_deform: bool


@dataclass(slots=True, frozen=True)
class DeformationPlacement:
    collection: object
    placement_root: object
    path_object: object | None


def _coordinates(points) -> np.ndarray:
    values = np.empty(len(points) * 3, dtype=np.float32)
    points.foreach_get("co", values)
    return values.reshape(-1, 3).astype(np.float64)


def _transformed(points: np.ndarray, matrix) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float64)
    return points @ matrix[:3, :3].T + matrix[:3, 3]


def _lerp(start: np.ndarray, end: np.ndarray, factor: np.ndarray) -> np.ndarray:
    return start * (1.0 - factor)[:, None] + end * factor[:, None]


def _slerp(start: np.ndarray, end: np.ndarray, factor: np.ndarray) -> np.ndarray:
    cosine = np.sum(start * end, axis=1)
    start = np.where((cosine < 0.0)[:, None], -start, start)
    cosine = np.abs(cosine)
    linear = 1.0 - cosine <= 0.0001
    omega = np.arccos(np.clip(cosine, -1.0, 1.0))
    sine = np.where(linear, 1.0, np.sin(omega))
    start_weight = np.where(linear, 1.0 - factor, np.sin((1.0 - factor) * omega) / sine)
    end_weight = np.where(linear, factor, np.sin(factor * omega) / sine)
    return start * start_weight[:, None] + end * end_weight[:, None]


def _rotated(quaternions: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    w, axis = quaternions[:, :1], quaternions[:, 1:]
    return (
        vectors * (w * w - np.sum(axis * axis, axis=1, keepdims=True))
        + 2.0 * axis * np.sum(axis * vectors, axis=1, keepdims=True)
        + 2.0 * w * np.cross(axis, vectors)
    )


class DeformationService:
    def __init__(self):
        self._bounds_cache = {}

    @staticmethod
    def records(data):
        records = data.get("deformationData", []) if isinstance(data, dict) else []
        if isinstance(records, dict):
            for key in ("Data", "Matrices", "Elements", "entries"):
                candidate = records.get(key)
                if isinstance(candidate, list):
                    records = candidate
                    break
        return tuple(records) if isinstance(records, list) else ()

    @staticmethod
    def frame_matrix(record):
        if not isinstance(record, dict):
            raise TypeError("deformation frame must be a dictionary")
        source = (
            record.get("Properties")
            if isinstance(record.get("Properties"), dict)
            else record
        )
        columns = []
        for column_name in ("X", "Y", "Z", "W"):
            column = source.get(column_name)
            if not isinstance(column, dict):
                column = source.get(column_name.lower())
            if not isinstance(column, dict):
                raise ValueError(f"deformation frame has no {column_name} column")
            columns.append(column)

        return column_matrix(*columns)

    @staticmethod
    def frame_metrics(frames, axis_index):
        translations = [frame.to_translation() for frame in frames]
        spans = [0.0, 0.0, 0.0]
        if translations:
            for component in range(3):
                values = [float(location[component]) for location in translations]
                spans[component] = max(values) - min(values)

        dominant_axis = (
            max(range(3), key=lambda component: spans[component])
            if translations
            else axis_index
        )
        axis_values = [float(location[axis_index]) for location in translations]
        steps = [
            axis_values[index + 1] - axis_values[index]
            for index in range(len(axis_values) - 1)
        ]
        monotonic = all(step >= -1e-6 for step in steps) or all(
            step <= 1e-6 for step in steps
        )
        return DeformationFrameMetrics(
            dominant_axis_index=dominant_axis,
            dominant_axis_span=(float(spans[dominant_axis]) if spans else 0.0),
            monotonic_contract_axis=monotonic,
        )

    def frames(self, data, *, sector_name, node_index, warning):
        records = self.records(data)
        frames = []
        for frame_index, record in enumerate(records):
            try:
                frames.append(self.frame_matrix(record))
            except (TypeError, ValueError, KeyError) as error:
                warning(
                    f"{sector_name}: node {node_index} deformation frame "
                    f"{frame_index} is invalid: {error}",
                    exc_info=True,
                )
        if len(frames) < 2:
            warning(
                f"{sector_name}: node {node_index} contains "
                f"{len(frames)} usable deformation frames; at least two "
                "are required"
            )
        return tuple(frames)

    def collection_axis_bounds(self, collection, axis_index):
        key = (rna_identity(collection), int(axis_index))
        cached = self._bounds_cache.get(key)
        if cached is not None:
            return cached

        lower = float("inf")
        upper = float("-inf")
        vertex_count = 0
        for obj in collection.all_objects:
            if obj.type != "MESH" or obj.data is None or not obj.data.vertices:
                continue
            values = _transformed(_coordinates(obj.data.vertices), obj.matrix_world)[
                :, axis_index
            ]
            lower = min(lower, float(values.min()))
            upper = max(upper, float(values.max()))
            vertex_count += len(values)

        result = (lower, upper, vertex_count)
        self._bounds_cache[key] = result
        return result

    def analyze(
        self,
        node_type,
        data,
        group,
        *,
        sector_name,
        node_index,
        handle_id,
        meshname,
        warning,
    ):
        contract = DEFORMATION_AXIS_CONTRACTS.get(node_type)
        if contract is None:
            raise DeformationDataError(
                f"Unsupported deformation node type: {node_type}"
            )

        frames = self.frames(
            data,
            sector_name=sector_name,
            node_index=node_index,
            warning=warning,
        )
        metrics = self.frame_metrics(
            frames,
            contract.axis_index,
        )

        if (
            len(frames) >= 2
            and metrics.dominant_axis_span > 1e-6
            and metrics.dominant_axis_index != contract.axis_index
        ):
            warning(
                f"{sector_name}: node {node_index} deformation frames move "
                f"primarily along "
                f"{'XYZ'[metrics.dominant_axis_index]} but {node_type} "
                f"expects {contract.axis_name}"
            )
        if len(frames) >= 2 and not metrics.monotonic_contract_axis:
            warning(
                f"{sector_name}: node {node_index} deformation frames are "
                f"not monotonic along {contract.axis_name}"
            )

        axis_min = 0.0
        axis_max = 0.0
        vertex_count = 0
        if group is not None:
            axis_min, axis_max, vertex_count = self.collection_axis_bounds(
                group,
                contract.axis_index,
            )
            if vertex_count == 0 or abs(axis_max - axis_min) <= 1e-8:
                warning(
                    f"{sector_name}: node {node_index} source mesh has no "
                    f"usable {contract.axis_name} longitudinal span"
                )
        else:
            warning(
                f"{sector_name}: deformation mesh not found in masters: "
                f"{meshname} - node {node_index} - {handle_id}"
            )

        can_deform = (
            group is not None
            and len(frames) >= 2
            and vertex_count > 0
            and abs(axis_max - axis_min) > 1e-8
        )
        return DeformationAnalysis(
            node_type=node_type,
            contract=contract,
            frames=frames,
            source_axis_min=float(axis_min),
            source_axis_max=float(axis_max),
            can_deform=bool(can_deform),
        )

    @staticmethod
    def deform_content_points(points: np.ndarray, analysis) -> np.ndarray:
        axis_index = analysis.contract.axis_index
        axis_min = analysis.source_axis_min
        axis_max = analysis.source_axis_max
        span = axis_max - axis_min
        if abs(span) <= 1e-8:
            return points.copy()

        coordinates = points[:, axis_index]
        factors = (
            (coordinates - axis_min) / span
            if analysis.contract.axis_sign > 0.0
            else (axis_max - coordinates) / span
        )
        parts = [frame.decompose() for frame in analysis.frames]
        locations = np.array([tuple(part[0]) for part in parts], dtype=np.float64)
        rotations = np.array([tuple(part[1]) for part in parts], dtype=np.float64)
        scales = np.array([tuple(part[2]) for part in parts], dtype=np.float64)
        if len(parts) == 1:
            count = len(points)
            location = np.repeat(locations, count, axis=0)
            rotation = np.repeat(rotations, count, axis=0)
            scale = np.repeat(scales, count, axis=0)
        else:
            positions = np.clip(factors, 0.0, 1.0) * (len(parts) - 1)
            index = np.minimum(np.floor(positions).astype(np.int64), len(parts) - 2)
            blend = positions - index
            location = _lerp(locations[index], locations[index + 1], blend)
            rotation = _slerp(rotations[index], rotations[index + 1], blend)
            scale = _lerp(scales[index], scales[index + 1], blend)
        cross_section = points.copy()
        cross_section[:, axis_index] = 0.0
        return location + _rotated(rotation, cross_section * scale)

    def deform_mesh_copy(self, old_obj, new_obj, analysis):
        source_matrix = old_obj.matrix_world.copy()
        inverse_source = source_matrix.inverted_safe()

        def deformed(points):
            content = _transformed(_coordinates(points), source_matrix)
            result = _transformed(
                self.deform_content_points(content, analysis), inverse_source
            )
            return result.astype(np.float32).reshape(-1)

        mesh = new_obj.data
        shape_keys = getattr(mesh, "shape_keys", None)
        if shape_keys is not None and shape_keys.key_blocks:
            for key_block in shape_keys.key_blocks:
                key_block.data.foreach_set("co", deformed(key_block.data))
            basis = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            shape_keys.key_blocks[0].data.foreach_get("co", basis)
            mesh.vertices.foreach_set("co", basis)
        elif mesh.vertices:
            mesh.vertices.foreach_set("co", deformed(mesh.vertices))
        mesh.update()

    @staticmethod
    def create_path(
        name,
        frames,
        target_collection,
        placement_root,
        *,
        cable_radius=0.0,
        render_geometry=False,
    ):
        curve = track_created_datablock(
            "curves",
            bpy.data.curves.new(
                fit_id_name(f"{name}_Path"),
                "CURVE",
            ),
        )
        curve.dimensions = "3D"
        curve.twist_mode = "MINIMUM"
        curve.resolution_u = 1
        spline = curve.splines.new("POLY")
        spline.points.add(len(frames) - 1)
        for frame_index, frame in enumerate(frames):
            location = frame.to_translation()
            spline.points[frame_index].co = (*location, 1.0)

        if render_geometry and cable_radius > 0.0:
            curve.bevel_depth = float(cable_radius)
            curve.bevel_resolution = 2
            curve.resolution_u = 2
            curve.fill_mode = "FULL"

        path_object = track_created_datablock(
            "objects", bpy.data.objects.new(curve.name, curve)
        )
        target_collection.objects.link(path_object)
        path_object.parent = placement_root
        path_object.matrix_parent_inverse = Matrix.Identity(4)
        path_object.matrix_basis = Matrix.Identity(4)
        path_object.display_type = "WIRE"
        path_object.hide_render = not render_geometry
        path_object.show_in_front = True
        return path_object

    def copy_deformed_collection(
        self,
        source_collection,
        name,
        node_matrix,
        analysis,
        *,
        color=None,
        hide_armatures=True,
    ):
        destination_root = new_collection(fit_id_name(name))
        copy_map = {}

        def copy_into(source, destination):
            for child in source.children:
                child_destination = new_collection(child.name)
                destination.children.link(child_destination)
                copy_into(child, child_destination)
            for old_object in source.objects:
                new_object = copy_object(
                    old_object,
                    color=color,
                    hide_armature=hide_armatures,
                )
                if new_object.type == "MESH" and new_object.data is not None:
                    new_object.data = track_created_datablock(
                        "meshes", old_object.data.copy()
                    )
                copy_map[old_object] = new_object
                destination.objects.link(new_object)

        copy_into(source_collection, destination_root)
        remap_copied_object_references(
            tuple(copy_map.values()),
            copy_map,
        )

        placement_root = new_empty(
            f"{name}_Placement",
            destination_root,
        )
        placement_root.matrix_world = node_matrix
        content_root = new_empty(
            f"{name}_Content",
            destination_root,
        )
        content_root.parent = placement_root
        content_root.matrix_parent_inverse = Matrix.Identity(4)
        content_root.matrix_basis = Matrix.Identity(4)

        for old_object, new_object in copy_map.items():
            if old_object.parent in copy_map:
                continue
            new_object.parent = content_root
            new_object.matrix_parent_inverse = Matrix.Identity(4)
            new_object.matrix_basis = old_object.matrix_world.copy()

        for old_object, new_object in copy_map.items():
            if new_object.type == "MESH" and new_object.data is not None:
                self.deform_mesh_copy(
                    old_object,
                    new_object,
                    analysis,
                )
        return destination_root, placement_root

    def instantiate(
        self,
        group,
        instance_name,
        node_matrix,
        analysis,
        *,
        cable_radius=0.0,
    ):
        if analysis.can_deform:
            collection, placement_root = self.copy_deformed_collection(
                group,
                instance_name,
                node_matrix,
                analysis,
                color=(0.0380098, 0.595213, 0.600022, 1),
                hide_armatures=True,
            )
        else:
            collection = new_collection(instance_name)
            placement_root = new_empty(
                f"{instance_name}_Placement",
                collection,
            )
            placement_root.matrix_world = node_matrix

        render_fallback = (
            analysis.node_type == "worldCableMeshNode" and not analysis.can_deform
        )
        path_object = None
        if analysis.frames:
            path_object = self.create_path(
                instance_name,
                analysis.frames,
                collection,
                placement_root,
                cable_radius=cable_radius,
                render_geometry=render_fallback,
            )

        return DeformationPlacement(
            collection=collection,
            placement_root=placement_root,
            path_object=path_object,
        )
