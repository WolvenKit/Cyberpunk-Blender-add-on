from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import math

import bpy
from mathutils import Matrix, Vector

from ....animation.blender_pose import interpolate_matrix_trs_components

from ..context import DeformationDataError
from ....assetio.values import axis_value


DEFORMATION_CONTRACT = "FRAME_MATRIX_VERTEX_BAKE"


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
    normalized_homogeneous_frames: int
    dominant_axis_index: int
    dominant_axis_span: float
    contract_axis_span: float
    contract_axis_min: float
    contract_axis_max: float
    minimum_frame_step: float
    maximum_frame_step: float
    monotonic_contract_axis: bool


@dataclass(slots=True, frozen=True)
class DeformationAnalysis:
    node_type: str
    contract: DeformationAxisContract
    records: tuple
    frames: tuple
    metrics: DeformationFrameMetrics
    source_axis_min: float
    source_axis_max: float
    source_vertex_count: int
    can_deform: bool


@dataclass(slots=True, frozen=True)
class DeformationPlacement:
    collection: object
    placement_root: object
    path_object: object | None
    rendered_fallback_curve: bool


class DeformationService:
    def __init__(self):
        self._bounds_cache = {}

    @staticmethod
    def records(data):
        records = (
            data.get("deformationData", [])
            if isinstance(data, dict)
            else []
        )
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
                raise ValueError(
                    f"deformation frame has no {column_name} column"
                )
            columns.append(column)

        x_axis, y_axis, z_axis, translation = columns
        return Matrix((
            (
                float(axis_value(x_axis, "X", 1.0)),
                float(axis_value(y_axis, "X")),
                float(axis_value(z_axis, "X")),
                float(axis_value(translation, "X")),
            ),
            (
                float(axis_value(x_axis, "Y")),
                float(axis_value(y_axis, "Y", 1.0)),
                float(axis_value(z_axis, "Y")),
                float(axis_value(translation, "Y")),
            ),
            (
                float(axis_value(x_axis, "Z")),
                float(axis_value(y_axis, "Z")),
                float(axis_value(z_axis, "Z", 1.0)),
                float(axis_value(translation, "Z")),
            ),
            (0.0, 0.0, 0.0, 1.0),
        ))

    @staticmethod
    def frame_metrics(records, frames, axis_index):
        normalized_homogeneous_frames = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            source = (
                record.get("Properties")
                if isinstance(record.get("Properties"), dict)
                else record
            )
            columns = [
                source.get(name, source.get(name.lower(), {}))
                for name in ("X", "Y", "Z", "W")
            ]
            if not all(isinstance(column, dict) for column in columns):
                continue
            x_axis, y_axis, z_axis, translation = columns
            if (
                abs(float(axis_value(x_axis, "W"))) > 1e-8
                or abs(float(axis_value(y_axis, "W"))) > 1e-8
                or abs(float(axis_value(z_axis, "W"))) > 1e-8
                or abs(
                    float(axis_value(translation, "W", 1.0)) - 1.0
                ) > 1e-8
            ):
                normalized_homogeneous_frames += 1

        translations = [frame.to_translation() for frame in frames]
        spans = [0.0, 0.0, 0.0]
        if translations:
            for component in range(3):
                values = [
                    float(location[component])
                    for location in translations
                ]
                spans[component] = max(values) - min(values)

        dominant_axis = (
            max(range(3), key=lambda component: spans[component])
            if translations
            else axis_index
        )
        axis_values = [
            float(location[axis_index])
            for location in translations
        ]
        steps = [
            axis_values[index + 1] - axis_values[index]
            for index in range(len(axis_values) - 1)
        ]
        monotonic = (
            all(step >= -1e-6 for step in steps)
            or all(step <= 1e-6 for step in steps)
        )
        return DeformationFrameMetrics(
            normalized_homogeneous_frames=(
                normalized_homogeneous_frames
            ),
            dominant_axis_index=dominant_axis,
            dominant_axis_span=(
                float(spans[dominant_axis]) if spans else 0.0
            ),
            contract_axis_span=(
                float(spans[axis_index]) if spans else 0.0
            ),
            contract_axis_min=min(axis_values) if axis_values else 0.0,
            contract_axis_max=max(axis_values) if axis_values else 0.0,
            minimum_frame_step=min(
                (abs(step) for step in steps),
                default=0.0,
            ),
            maximum_frame_step=max(
                (abs(step) for step in steps),
                default=0.0,
            ),
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
                    f"{frame_index} is invalid: {error}"
                )
        if len(frames) < 2:
            warning(
                f"{sector_name}: node {node_index} contains "
                f"{len(frames)} usable deformation frames; at least two "
                "are required"
            )
        return records, tuple(frames)

    @staticmethod
    def _collection_identity(collection):
        as_pointer = getattr(collection, "as_pointer", None)
        if callable(as_pointer):
            try:
                return int(as_pointer())
            except Exception:
                pass
        return id(collection)

    def collection_axis_bounds(self, collection, axis_index):
        key = (self._collection_identity(collection), int(axis_index))
        cached = self._bounds_cache.get(key)
        if cached is not None:
            return cached

        lower = float("inf")
        upper = float("-inf")
        vertex_count = 0
        for obj in collection.all_objects:
            if obj.type != "MESH" or obj.data is None:
                continue
            source_matrix = obj.matrix_world
            for vertex in obj.data.vertices:
                coordinate = float(
                    (source_matrix @ vertex.co)[axis_index]
                )
                lower = min(lower, coordinate)
                upper = max(upper, coordinate)
                vertex_count += 1

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

        records, frames = self.frames(
            data,
            sector_name=sector_name,
            node_index=node_index,
            warning=warning,
        )
        metrics = self.frame_metrics(
            records,
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
        if (
            len(frames) >= 2
            and not metrics.monotonic_contract_axis
        ):
            warning(
                f"{sector_name}: node {node_index} deformation frames are "
                f"not monotonic along {contract.axis_name}"
            )

        axis_min = 0.0
        axis_max = 0.0
        vertex_count = 0
        if group is not None:
            axis_min, axis_max, vertex_count = (
                self.collection_axis_bounds(
                    group,
                    contract.axis_index,
                )
            )
            if (
                vertex_count == 0
                or abs(axis_max - axis_min) <= 1e-8
            ):
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
            records=records,
            frames=frames,
            metrics=metrics,
            source_axis_min=float(axis_min),
            source_axis_max=float(axis_max),
            source_vertex_count=int(vertex_count),
            can_deform=bool(can_deform),
        )

    @staticmethod
    def interpolate_frame(frames, factor):
        if len(frames) == 1:
            return frames[0].decompose()
        position = (
            max(0.0, min(1.0, float(factor)))
            * (len(frames) - 1)
        )
        frame_index = min(
            int(math.floor(position)),
            len(frames) - 2,
        )
        blend = position - frame_index
        return interpolate_matrix_trs_components(
            frames[frame_index],
            frames[frame_index + 1],
            blend,
        )

    def deform_content_point(self, point, analysis):
        axis_index = analysis.contract.axis_index
        axis_min = analysis.source_axis_min
        axis_max = analysis.source_axis_max
        span = axis_max - axis_min
        if abs(span) <= 1e-8:
            return point.copy()

        coordinate = float(point[axis_index])
        factor = (
            (coordinate - axis_min) / span
            if analysis.contract.axis_sign > 0.0
            else (axis_max - coordinate) / span
        )
        location, rotation, scale = self.interpolate_frame(
            analysis.frames,
            factor,
        )
        cross_section = point.copy()
        cross_section[axis_index] = 0.0
        scaled_cross_section = Vector((
            cross_section.x * scale.x,
            cross_section.y * scale.y,
            cross_section.z * scale.z,
        ))
        return location + rotation @ scaled_cross_section

    def deform_mesh_copy(self, old_obj, new_obj, analysis):
        source_matrix = old_obj.matrix_world.copy()
        inverse_source = source_matrix.inverted_safe()

        def deform_coordinate(coordinate):
            content_point = source_matrix @ coordinate
            deformed_point = self.deform_content_point(
                content_point,
                analysis,
            )
            return inverse_source @ deformed_point

        shape_keys = getattr(new_obj.data, "shape_keys", None)
        if shape_keys is not None and shape_keys.key_blocks:
            for key_block in shape_keys.key_blocks:
                for point in key_block.data:
                    point.co = deform_coordinate(point.co)
            basis = shape_keys.key_blocks[0]
            for vertex_index, vertex in enumerate(
                new_obj.data.vertices
            ):
                vertex.co = basis.data[vertex_index].co
        else:
            for vertex in new_obj.data.vertices:
                vertex.co = deform_coordinate(vertex.co)
        new_obj.data.update()

    @staticmethod
    def create_path(
        name,
        frames,
        target_collection,
        placement_root,
        *,
        trim_name,
        cable_radius=0.0,
        render_geometry=False,
    ):
        curve = track_created_datablock("curves", bpy.data.curves.new(
            trim_name(f"{name}_Path"),
            "CURVE",
        ))
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

        path_object = track_created_datablock("objects", bpy.data.objects.new(curve.name, curve))
        target_collection.objects.link(path_object)
        path_object.parent = placement_root
        path_object.matrix_parent_inverse = Matrix.Identity(4)
        path_object.matrix_basis = Matrix.Identity(4)
        path_object.display_type = "WIRE"
        path_object.hide_render = not render_geometry
        path_object.show_in_front = True
        path_object["deformationFrameCount"] = len(frames)
        return path_object

    def copy_deformed_collection(
        self,
        source_collection,
        name,
        node_matrix,
        analysis,
        operations,
        *,
        color=None,
        hide_armatures=True,
    ):
        destination_root = operations.new_collection(
            operations.trim_name(name)
        )
        copy_map = {}

        def copy_into(source, destination):
            for child in source.children:
                child_destination = operations.new_collection(child.name)
                destination.children.link(child_destination)
                copy_into(child, child_destination)
            for old_object in source.objects:
                new_object = operations.copy_object(
                    old_object,
                    color=color,
                    hide_armature=hide_armatures,
                )
                if (
                    new_object.type == "MESH"
                    and new_object.data is not None
                ):
                    new_object.data = track_created_datablock("meshes", old_object.data.copy())
                copy_map[old_object] = new_object
                destination.objects.link(new_object)

        copy_into(source_collection, destination_root)
        operations.remap_copied_object_references(
            tuple(copy_map.values()),
            copy_map,
        )

        placement_root = operations.new_empty(
            f"{name}_Placement",
            destination_root,
        )
        placement_root.matrix_world = node_matrix
        content_root = operations.new_empty(
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
            if (
                new_object.type == "MESH"
                and new_object.data is not None
            ):
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
        operations,
        *,
        cable_radius=0.0,
    ):
        if analysis.can_deform:
            collection, placement_root = (
                self.copy_deformed_collection(
                    group,
                    instance_name,
                    node_matrix,
                    analysis,
                    operations,
                    color=(0.0380098, 0.595213, 0.600022, 1),
                    hide_armatures=True,
                )
            )
        else:
            collection = operations.new_collection(instance_name)
            placement_root = operations.new_empty(
                f"{instance_name}_Placement",
                collection,
            )
            placement_root.matrix_world = node_matrix

        render_fallback = (
            analysis.node_type == "worldCableMeshNode"
            and not analysis.can_deform
        )
        path_object = None
        if analysis.frames:
            path_object = self.create_path(
                instance_name,
                analysis.frames,
                collection,
                placement_root,
                trim_name=operations.trim_name,
                cable_radius=cable_radius,
                render_geometry=render_fallback,
            )

        return DeformationPlacement(
            collection=collection,
            placement_root=placement_root,
            path_object=path_object,
            rendered_fallback_curve=render_fallback,
        )
