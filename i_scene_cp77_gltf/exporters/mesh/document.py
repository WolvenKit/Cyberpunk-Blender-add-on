from __future__ import annotations

import copy
import json
import os
import struct
from dataclasses import dataclass, field

import numpy as np

from ...animation.metadata import SOURCE_REST_SNAPSHOT_KEY
from ...animation.rig_binding import merged_bone_name
from ...redSpace.contracts import (
    GLTF_TO_BLENDER_BONE_RIGHT,
    GLTF_TO_RED,
    RED_TO_GLTF,
    SOURCE_REST_SPACE_CONTRACT,
)
from ...redSpace.transforms import red_matrix_to_gltf
from ...gltf.provenance import DIRECT_MESH_GENERATOR
from ..common.glb import GLBBuilder, encode_glb
from ...blender.mesh_validation import VERT_LIMIT, _loop_vertex_indices, _quantize

try:
    import bpy
except ImportError:
    bpy = None


_GLTF_TO_RED_4 = np.asarray(GLTF_TO_RED, dtype=np.float64)
_RED_TO_GLTF_4 = np.asarray(RED_TO_GLTF, dtype=np.float64)
_GLTF_TO_BONE_RIGHT_4 = np.asarray(GLTF_TO_BLENDER_BONE_RIGHT, dtype=np.float64)
_BONE_RIGHT_TO_GLTF_4 = np.linalg.inv(_GLTF_TO_BONE_RIGHT_4)

# Row-vector rotation from REDengine/Blender space back into glTF space. The import path
# applies GLTF_TO_RED[:3, :3].T; this is its exact inverse, held in float32 so the
# per-vertex transforms stay in the accessor component type.
_ROTATION_RED_TO_GLTF_T = np.ascontiguousarray(
    _RED_TO_GLTF_4[:3, :3].T.astype(np.float32)
)

GARMENT_CAP_ATTRIBUTE = "_GarmentSupportCap"
GARMENT_WEIGHT_ATTRIBUTE = "_GarmentSupportWeight"
GARMENT_SUPPORT_MORPH = "GarmentSupport"

_UV_ATTRIBUTES = ("TEXCOORD_0", "TEXCOORD_1", "TEXCOORD_2", "TEXCOORD_3")
_COLOR_ATTRIBUTES = ("COLOR_0", "COLOR_1")
_JOINT_ATTRIBUTES = ("JOINTS_0", "JOINTS_1", "JOINTS_2", "JOINTS_3")
_WEIGHT_ATTRIBUTES = ("WEIGHTS_0", "WEIGHTS_1", "WEIGHTS_2", "WEIGHTS_3")

_MAX_INFLUENCE_BLOCKS = len(_JOINT_ATTRIBUTES)
_WEIGHT_EPSILON = 1.0e-8
_IDENTITY_TOLERANCE = 1.0e-9
_SOURCE_NORMAL_ATTRIBUTE = ".cp77_source_normal"
_SOURCE_TANGENT_ATTRIBUTE = ".cp77_source_tangent"
_SOURCE_TANGENT_SIGN_ATTRIBUTE = ".cp77_source_tangent_sign"
_SOURCE_MESH_EXTRAS_KEY = "cp77_direct_mesh_extras"
_SOURCE_NODE_EXTRAS_KEY = "cp77_direct_node_extras"
_SOURCE_DOCUMENT_METADATA_KEY = "cp77_direct_document_metadata"
_SOURCE_SCENE_METADATA_KEY = "cp77_direct_scene_metadata"
_SOURCE_SKIN_EXTRAS_KEY = "cp77_direct_skin_extras"
_SOURCE_SKIN_BINDING_KEY = "cp77_direct_mesh_skin_binding"
_MESH_SOURCE_REST_SNAPSHOT_KEY = "cp77_direct_mesh_source_rest_json"
_SOURCE_MATERIAL_INDEX_KEY = "cp77_direct_material_index"

# Object custom properties written by the import path; they carry no meaning for
# WolvenKit and are stripped from the exported node extras.
_INTERNAL_OBJECT_KEYS = frozenset(
    {
        "cp77_lod",
        "cp77_material_name",
        "cp77_skin_invalid_influences",
        "cp77_skin_unmapped_influences",
        "cp77_skin_duplicate_influences",
        "cp77_skin_zero_weight_vertices",
        _SOURCE_MESH_EXTRAS_KEY,
        _SOURCE_NODE_EXTRAS_KEY,
        _SOURCE_DOCUMENT_METADATA_KEY,
        _SOURCE_SCENE_METADATA_KEY,
        _SOURCE_SKIN_EXTRAS_KEY,
        _SOURCE_SKIN_BINDING_KEY,
        _MESH_SOURCE_REST_SNAPSHOT_KEY,
        _SOURCE_MATERIAL_INDEX_KEY,
    }
)

_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963


class DirectMeshExportError(RuntimeError):
    pass


class MeshGLBBuilder(GLBBuilder):
    """GLBBuilder extended with the integer and normalized accessors meshes need."""

    def _finish(self, accessor: dict, target: int | None) -> int:
        if target is not None:
            self.buffer_views[accessor["bufferView"]]["target"] = target
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index

    def _write_block(self, array: np.ndarray, target: int | None):
        self._align(4)
        byte_offset = len(self.binary)
        payload = np.ascontiguousarray(array).tobytes(order="C")
        self.binary.extend(payload)
        view_index = len(self.buffer_views)
        view = {"buffer": 0, "byteOffset": byte_offset, "byteLength": len(payload)}
        if target is not None:
            view["target"] = target
        self.buffer_views.append(view)
        return view_index

    def add_float_accessor(self, values, accessor_type, *, target=None, **kwargs):
        accessor_index = super().add_float_accessor(values, accessor_type, **kwargs)
        if target is not None:
            view_index = self.accessors[accessor_index]["bufferView"]
            self.buffer_views[view_index]["target"] = target
        return accessor_index

    def add_integer_accessor(
        self,
        values,
        accessor_type: str,
        component_type: int,
        *,
        name: str | None = None,
        target: int | None = None,
        include_bounds: bool = False,
    ) -> int:
        dtypes = {5121: np.dtype("<u1"), 5123: np.dtype("<u2"), 5125: np.dtype("<u4")}
        dtype = dtypes.get(component_type)
        if dtype is None:
            raise DirectMeshExportError(
                f"Unsupported integer component type {component_type}."
            )
        widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
        width = widths.get(accessor_type)
        if width is None:
            raise DirectMeshExportError(f"Unsupported accessor type {accessor_type!r}.")

        array = np.asarray(values)
        if np.any(array < 0):
            raise DirectMeshExportError(f"Accessor {name or accessor_type} holds negative values.")
        if int(array.max(initial=0)) > int(np.iinfo(dtype).max):
            raise DirectMeshExportError(
                f"Accessor {name or accessor_type} exceeds component type {component_type}."
            )
        array = array.reshape(-1) if width == 1 else array.reshape(-1, width)
        array = np.ascontiguousarray(array, dtype=dtype)
        count = int(array.shape[0])

        view_index = self._write_block(array, target)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": accessor_type,
        }
        if name:
            accessor["name"] = name
        if include_bounds and count:
            bounds = array.reshape(count, width)
            accessor["min"] = [int(value) for value in bounds.min(axis=0)]
            accessor["max"] = [int(value) for value in bounds.max(axis=0)]
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index

    def add_normalized_accessor(
        self,
        values,
        accessor_type: str,
        component_type: int,
        *,
        name: str | None = None,
        target: int | None = None,
    ) -> int:
        dtypes = {5121: np.dtype("<u1"), 5123: np.dtype("<u2")}
        dtype = dtypes.get(component_type)
        if dtype is None:
            raise DirectMeshExportError(
                f"Unsupported normalized component type {component_type}."
            )
        widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
        width = widths.get(accessor_type)
        if width is None:
            raise DirectMeshExportError(f"Unsupported accessor type {accessor_type!r}.")

        maximum = float(np.iinfo(dtype).max)
        scaled = np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0) * maximum
        array = np.ascontiguousarray(np.rint(scaled).astype(dtype).reshape(-1, width))
        count = int(array.shape[0])

        view_index = self._write_block(array, target)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": accessor_type,
            "normalized": True,
        }
        if name:
            accessor["name"] = name
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index


@dataclass(slots=True)
class ExportSubmesh:
    name: str
    positions: np.ndarray
    triangles: np.ndarray
    normals: np.ndarray | None
    tangents: np.ndarray | None
    node_matrix_gltf: np.ndarray
    uv_layers: list[np.ndarray] = field(default_factory=list)
    color_layers: list[np.ndarray] = field(default_factory=list)
    custom_colors: list[tuple[str, np.ndarray]] = field(default_factory=list)
    joint_indices: np.ndarray | None = None
    joint_weights: np.ndarray | None = None
    morph_targets: list[tuple[str, np.ndarray]] = field(default_factory=list)
    material_names: list[str] = field(default_factory=list)
    material_index: int | None = None
    mesh_extras: dict = field(default_factory=dict)
    node_extras: dict = field(default_factory=dict)
    skinned: bool = False

    @property
    def vertex_count(self) -> int:
        return int(self.positions.shape[0])


@dataclass(slots=True)
class SkeletonWriteBinding:
    bone_names: tuple[str, ...]
    parent_indices: tuple[int, ...]
    node_local_gltf: np.ndarray
    inverse_bind_gltf: np.ndarray
    group_to_joint: dict[str, int]
    rig_path: str = ""
    skin_extras: dict | None = None


def _require_bpy():
    if bpy is None:
        raise RuntimeError("Blender is required for direct mesh export.")


def _rotate_to_gltf(values) -> np.ndarray:
    """Rotate an Nx3 REDengine/Blender vector block back into glTF space."""
    source = np.asarray(values, dtype=np.float32)
    if source.ndim != 2 or source.shape[1] < 3:
        raise DirectMeshExportError(f"Expected an Nx3 vector block, got {source.shape}.")
    return np.ascontiguousarray(source[:, :3] @ _ROTATION_RED_TO_GLTF_T)


def _matrix_to_numpy(matrix) -> np.ndarray:
    return np.asarray([[float(value) for value in row] for row in matrix], dtype=np.float64)


def _red_matrix_to_gltf(matrix: np.ndarray) -> np.ndarray:
    return red_matrix_to_gltf(matrix)


def _bone_matrix_to_gltf(matrix_local: np.ndarray) -> np.ndarray:
    """Undo the import-side bind transform: matrix_local = GLTF_TO_RED @ J @ BONE_RIGHT."""
    return _RED_TO_GLTF_4 @ np.asarray(matrix_local, dtype=np.float64) @ _BONE_RIGHT_TO_GLTF_4


def _is_identity(matrix: np.ndarray) -> bool:
    return bool(np.allclose(matrix, np.eye(4), atol=_IDENTITY_TOLERANCE, rtol=0.0))


def _decompose_node(matrix: np.ndarray) -> dict:
    """Emit a glTF node transform, preferring TRS and falling back to a raw matrix."""
    matrix = np.asarray(matrix, dtype=np.float64)
    if _is_identity(matrix):
        return {}
    basis = matrix[:3, :3]
    scale = np.linalg.norm(basis, axis=0)
    if np.any(scale <= 1.0e-12) or np.linalg.det(basis) <= 0.0:
        return {"matrix": [float(value) for value in matrix.T.reshape(-1)]}
    rotation_basis = basis / scale[np.newaxis, :]
    if not np.allclose(rotation_basis.T @ rotation_basis, np.eye(3), atol=1.0e-6, rtol=0.0):
        return {"matrix": [float(value) for value in matrix.T.reshape(-1)]}

    trace = float(np.trace(rotation_basis))
    if trace > 0.0:
        root = np.sqrt(trace + 1.0) * 2.0
        w = 0.25 * root
        x = (rotation_basis[2, 1] - rotation_basis[1, 2]) / root
        y = (rotation_basis[0, 2] - rotation_basis[2, 0]) / root
        z = (rotation_basis[1, 0] - rotation_basis[0, 1]) / root
    else:
        axis = int(np.argmax(np.diagonal(rotation_basis)))
        if axis == 0:
            root = np.sqrt(1.0 + rotation_basis[0, 0] - rotation_basis[1, 1] - rotation_basis[2, 2]) * 2.0
            w = (rotation_basis[2, 1] - rotation_basis[1, 2]) / root
            x = 0.25 * root
            y = (rotation_basis[0, 1] + rotation_basis[1, 0]) / root
            z = (rotation_basis[0, 2] + rotation_basis[2, 0]) / root
        elif axis == 1:
            root = np.sqrt(1.0 + rotation_basis[1, 1] - rotation_basis[0, 0] - rotation_basis[2, 2]) * 2.0
            w = (rotation_basis[0, 2] - rotation_basis[2, 0]) / root
            x = (rotation_basis[0, 1] + rotation_basis[1, 0]) / root
            y = 0.25 * root
            z = (rotation_basis[1, 2] + rotation_basis[2, 1]) / root
        else:
            root = np.sqrt(1.0 + rotation_basis[2, 2] - rotation_basis[0, 0] - rotation_basis[1, 1]) * 2.0
            w = (rotation_basis[1, 0] - rotation_basis[0, 1]) / root
            x = (rotation_basis[0, 2] + rotation_basis[2, 0]) / root
            y = (rotation_basis[1, 2] + rotation_basis[2, 1]) / root
            z = 0.25 * root

    node = {}
    translation = matrix[:3, 3]
    if not np.allclose(translation, 0.0, atol=1.0e-8):
        node["translation"] = [float(value) for value in translation]
    rotation = np.asarray((x, y, z, w), dtype=np.float64)
    rotation = rotation / np.linalg.norm(rotation)
    if not np.allclose(rotation, (0.0, 0.0, 0.0, 1.0), atol=1.0e-8):
        node["rotation"] = [float(value) for value in rotation]
    if not np.allclose(scale, 1.0, atol=1.0e-8):
        node["scale"] = [float(value) for value in scale]
    return node


def _unique_rows(columns):
    """Row-wise unique over stacked integer key columns, in first-appearance order.

    Columns are copied into one preallocated matrix rather than concatenating per-column
    byte views, and the matrix uses the narrowest integer width that holds every column.
    Quantized normals, UVs and colours fit int32 on any realistic mesh, which halves both
    the key width and the sort cost of the np.unique against a uniform int64 key.
    """
    blocks = []
    for array in columns:
        block = np.ascontiguousarray(array)
        if block.dtype.kind not in "iu":
            raise DirectMeshExportError(
                f"Split key columns must be integral; got {block.dtype}. "
                "Float attributes are quantized through _split_key_column so the split "
                "matches predicted_export_vertex_count."
            )
        if block.ndim == 1:
            block = block[:, np.newaxis]
        blocks.append(block)
    if not blocks:
        raise DirectMeshExportError("The split key requires at least one column.")

    rows = blocks[0].shape[0]
    width = sum(block.shape[1] for block in blocks)
    info = np.iinfo(np.int32)
    fits_int32 = all(
        int(block.max(initial=0)) <= info.max and int(block.min(initial=0)) >= info.min
        for block in blocks
    )

    packed = np.empty((rows, width), dtype=np.int32 if fits_int32 else np.int64)
    offset = 0
    for block in blocks:
        span = block.shape[1]
        packed[:, offset:offset + span] = block
        offset += span

    view = packed.view(np.dtype((np.void, packed.dtype.itemsize * width))).reshape(-1)
    _, unique_index, inverse = np.unique(view, return_index=True, return_inverse=True)

    order = np.argsort(unique_index, kind="stable")
    relabel = np.empty(order.shape[0], dtype=np.int64)
    relabel[order] = np.arange(order.shape[0], dtype=np.int64)
    return unique_index[order], relabel[inverse.reshape(-1)]


def _split_key_column(values) -> np.ndarray:
    """Quantize a loop attribute for the split key.

    The scale is mesh_validation._quantize so the vertex count this writer emits agrees
    with predicted_export_vertex_count, which gates each submesh against VERT_LIMIT.
    Quantization applies to the grouping key only; emitted attribute values are taken
    unquantized from the representative loop of each group.
    """
    source = np.asarray(values, dtype=np.float32)
    source = np.nan_to_num(source, nan=0.0, posinf=0.0, neginf=0.0)
    quantized = _quantize(source)
    # _quantize widens to int64; normals, UVs and colours quantize well inside int32 on
    # any realistic mesh, so narrow here rather than carrying doubled key columns into
    # the pack in _unique_rows. Out-of-range values keep int64 and are handled there.
    info = np.iinfo(np.int32)
    if quantized.size and (
        int(quantized.max()) > info.max or int(quantized.min()) < info.min
    ):
        return np.ascontiguousarray(quantized)
    return np.ascontiguousarray(quantized, dtype=np.int32)


def _triangle_loops(mesh) -> np.ndarray:
    mesh.calc_loop_triangles()
    triangle_count = len(mesh.loop_triangles)
    if not triangle_count:
        raise DirectMeshExportError(f"Mesh {mesh.name!r} produced no triangles.")
    loops = np.empty(triangle_count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", loops)
    return loops.reshape(-1, 3)


def _mesh_normals(mesh):
    """Read normals at the domain Blender reports for this mesh.

    ``normals_domain`` is POINT only when every face is smooth with no custom normals
    and no sharp edges, which is exactly the condition under which corner normals cannot
    diverge at a shared vertex. Reading the point domain there avoids a 3N corner fetch
    and lets the caller drop normals from the split key, which keeps the split aligned
    with predicted_export_vertex_count: that predictor adds normal columns only when
    has_custom_normals or a flat face is present.

    Returns the array plus whether it is indexed by vertex rather than by loop.
    """
    if getattr(mesh, "normals_domain", "CORNER") == "POINT":
        values = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertex_normals.foreach_get("vector", values)
        return values.reshape(-1, 3), True

    corner_normals = getattr(mesh, "corner_normals", None)
    # Mesh.corner_normals is documented as possibly empty; foreach_get against an empty
    # collection would leave the buffer uninitialised rather than fail.
    if corner_normals is None or len(corner_normals) != len(mesh.loops):
        return None, False
    values = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    corner_normals.foreach_get("vector", values)
    return values.reshape(-1, 3), False


def _corner_tangents(mesh, uv_name: str | None):
    """Return mikktspace loop tangents and bitangent signs, or None when unavailable.

    calc_tangents allocates a tangent CustomData layer on the mesh. When modifiers are
    not applied the export operates on the user's own mesh datablock, so the layer is
    released once the values have been copied out; leaving it behind would silently grow
    the .blend on every export.
    """
    if not uv_name or not hasattr(mesh, "calc_tangents"):
        return None, None
    try:
        mesh.calc_tangents(uvmap=uv_name)
    except (RuntimeError, TypeError) as error:
        print(f"[CP77 Direct Mesh Export] Tangents unavailable for {mesh.name!r}: {error}")
        return None, None
    try:
        loop_count = len(mesh.loops)
        tangents = np.empty(loop_count * 3, dtype=np.float32)
        signs = np.empty(loop_count, dtype=np.float32)
        mesh.loops.foreach_get("tangent", tangents)
        mesh.loops.foreach_get("bitangent_sign", signs)
        return tangents.reshape(-1, 3), signs
    finally:
        free_tangents = getattr(mesh, "free_tangents", None)
        if free_tangents is not None:
            free_tangents()


def _uv_loop_layers(mesh) -> list[tuple[str, np.ndarray]]:
    layers = []
    for uv_layer in mesh.uv_layers[: len(_UV_ATTRIBUTES)]:
        values = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        uv_layer.uv.foreach_get("vector", values)
        layers.append((uv_layer.name, values.reshape(-1, 2)))
    return layers


def _color_loop_values(mesh, attribute, loop_vertices) -> np.ndarray:
    """Read a colour attribute onto the loop domain as linear-or-raw float RGBA."""
    is_byte = attribute.data_type == "BYTE_COLOR"
    # BYTE_COLOR stores sRGB-encoded bytes; reading color_srgb keeps the stored byte
    # values intact so the normalized u8 accessor round-trips them exactly.
    field_name = "color_srgb" if is_byte else "color"
    count = len(attribute.data)
    values = np.empty(count * 4, dtype=np.float32)
    attribute.data.foreach_get(field_name, values)
    values = values.reshape(-1, 4)
    if attribute.domain == "POINT":
        return np.ascontiguousarray(values[loop_vertices])
    if attribute.domain != "CORNER":
        raise DirectMeshExportError(
            f"Colour attribute {attribute.name!r} uses unsupported domain {attribute.domain!r}."
        )
    return np.ascontiguousarray(values)


def _split_color_attributes(mesh, object_name):
    """Partition colour attributes into COLOR_n slots and underscore-prefixed customs."""
    standard = []
    custom = []
    overflow = []
    for attribute in mesh.color_attributes:
        if attribute.name.startswith("_"):
            custom.append(attribute)
        elif len(standard) < len(_COLOR_ATTRIBUTES):
            standard.append(attribute)
        else:
            overflow.append(attribute.name)
    if overflow:
        print(
            f"[CP77 Direct Mesh Export] {object_name}: glTF defines "
            f"{len(_COLOR_ATTRIBUTES)} COLOR_n slots; not exporting "
            + ", ".join(overflow)
        )
    return standard, custom


def _shape_key_blocks(obj):
    shape_keys = getattr(obj.data, "shape_keys", None)
    if shape_keys is None:
        return []
    blocks = list(shape_keys.key_blocks)
    return blocks[1:] if len(blocks) > 1 else []


def _has_applicable_modifiers(obj) -> bool:
    return any(
        modifier.show_viewport and modifier.type != "ARMATURE"
        for modifier in obj.modifiers
    )


def _evaluated_positions(obj, depsgraph) -> np.ndarray:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", positions)
        return positions.reshape(-1, 3)
    finally:
        evaluated.to_mesh_clear()


def _morph_deltas_from_shape_keys(obj, vertex_count) -> list[tuple[str, np.ndarray]]:
    blocks = _shape_key_blocks(obj)
    if not blocks:
        return []
    basis = obj.data.shape_keys.key_blocks[0]
    base = np.empty(len(basis.data) * 3, dtype=np.float32)
    basis.data.foreach_get("co", base)
    base = base.reshape(-1, 3)
    if base.shape[0] != vertex_count:
        raise DirectMeshExportError(
            f"Shape key basis on {obj.name!r} has {base.shape[0]} points "
            f"against {vertex_count} vertices."
        )

    targets = []
    for block in blocks:
        values = np.empty(len(block.data) * 3, dtype=np.float32)
        block.data.foreach_get("co", values)
        targets.append((block.name, values.reshape(-1, 3) - base))
    return targets


def _morph_deltas_through_modifiers(obj, depsgraph, base_positions) -> list[tuple[str, np.ndarray]]:
    """Evaluate each shape key through the modifier stack and difference the results.

    ``show_only_shape_key`` drives the active key to full strength regardless of the
    stored blend values, so each evaluation isolates one target. This is valid for any
    stack whose output topology depends on connectivity rather than vertex positions;
    a vertex count change between evaluations is rejected rather than silently mismapped.
    """
    blocks = _shape_key_blocks(obj)
    if not blocks:
        return []

    # A key identical to the basis evaluates to the base result through any deterministic
    # stack, so its delta is zero by construction. Character meshes commonly carry dozens
    # of unused morphs; skipping them avoids a full stack evaluation each.
    key_blocks = obj.data.shape_keys.key_blocks
    basis = np.empty(len(key_blocks[0].data) * 3, dtype=np.float32)
    key_blocks[0].data.foreach_get("co", basis)
    scratch = np.empty_like(basis)

    previous_only = obj.show_only_shape_key
    previous_active = obj.active_shape_key_index
    zero_delta = np.zeros_like(base_positions)
    targets = []
    try:
        obj.show_only_shape_key = True
        for index, block in enumerate(blocks, start=1):
            block.data.foreach_get("co", scratch)
            if np.array_equal(scratch, basis):
                targets.append((block.name, zero_delta))
                continue

            obj.active_shape_key_index = index
            depsgraph.update()
            positions = _evaluated_positions(obj, depsgraph)
            if positions.shape != base_positions.shape:
                raise DirectMeshExportError(
                    f"Modifier stack on {obj.name!r} changes topology for shape key "
                    f"{block.name!r} ({positions.shape[0]} against "
                    f"{base_positions.shape[0]} vertices); morph targets cannot be "
                    "resolved through it."
                )
            targets.append((block.name, positions - base_positions))
    finally:
        obj.show_only_shape_key = previous_only
        obj.active_shape_key_index = previous_active
        depsgraph.update()
    return targets


class _EvaluationTarget:
    """Temporary duplicate of an export object with the armature deformation disabled.

    Modifiers are evaluated on the copy so the source object, its modifier flags and its
    active shape key are never mutated. Armature modifiers are suppressed because the
    GLB carries rest-pose geometry plus skinning data, not posed geometry.
    """

    def __init__(self, obj, apply_modifiers: bool):
        self.source = obj
        self.apply_modifiers = apply_modifiers and _has_applicable_modifiers(obj)
        self.object = None
        self.mesh = None
        self._owns_mesh = False
        self._collection = None

    def __enter__(self):
        source = self.source
        if not self.apply_modifiers:
            self.object = source
            self.mesh = source.data
            return self

        self.object = source.copy()
        self.object.data = source.data.copy()
        self.object.animation_data_clear()
        for modifier in tuple(self.object.modifiers):
            if modifier.type == "ARMATURE":
                self.object.modifiers.remove(modifier)
        self._collection = bpy.context.scene.collection
        self._collection.objects.link(self.object)

        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        evaluated = self.object.evaluated_get(depsgraph)
        self.mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        self.mesh = self.mesh.copy()
        self._owns_mesh = True
        evaluated.to_mesh_clear()
        self.depsgraph = depsgraph
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._owns_mesh and self.mesh is not None:
            bpy.data.meshes.remove(self.mesh)
        if self.object is not None and self.object is not self.source:
            mesh_data = self.object.data
            if self._collection is not None:
                self._collection.objects.unlink(self.object)
            bpy.data.objects.remove(self.object, do_unlink=True)
            if mesh_data is not None and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)
        return False


def _pack_influences(vertex_ids, joint_ids, weights, vertex_count):
    """Sort, cap and normalize per-vertex influences into VEC4 JOINTS/WEIGHTS blocks."""
    if not len(vertex_ids):
        return None, None, 0

    vertex_ids = np.asarray(vertex_ids, dtype=np.int64)
    joint_ids = np.asarray(joint_ids, dtype=np.int64)
    weights = np.asarray(weights, dtype=np.float64)

    keep = np.isfinite(weights) & (weights > _WEIGHT_EPSILON)
    vertex_ids = vertex_ids[keep]
    joint_ids = joint_ids[keep]
    weights = weights[keep]
    if not len(vertex_ids):
        return None, None, 0

    order = np.lexsort((-weights, vertex_ids))
    vertex_ids = vertex_ids[order]
    joint_ids = joint_ids[order]
    weights = weights[order]

    # vertex_ids is sorted by the lexsort above, so run boundaries give per-vertex rank
    # in one linear pass instead of a searchsorted over the whole array.
    total = vertex_ids.shape[0]
    boundaries = np.flatnonzero(
        np.concatenate(((True,), vertex_ids[1:] != vertex_ids[:-1]))
    )
    run_lengths = np.diff(np.concatenate((boundaries, (total,))))
    starts = np.repeat(boundaries, run_lengths)
    ranks = np.arange(total, dtype=np.int64) - starts

    influence_width = int(run_lengths.max(initial=0))
    blocks = min(
        max(1, (influence_width + 3) // 4),
        _MAX_INFLUENCE_BLOCKS,
    )
    width = blocks * 4

    retained = ranks < width
    vertex_ids = vertex_ids[retained]
    joint_ids = joint_ids[retained]
    weights = weights[retained]
    ranks = ranks[retained]

    packed_joints = np.zeros((vertex_count, width), dtype=np.int32)
    packed_weights = np.zeros((vertex_count, width), dtype=np.float64)
    packed_joints[vertex_ids, ranks] = joint_ids
    packed_weights[vertex_ids, ranks] = weights

    totals = packed_weights.sum(axis=1)
    scalable = totals > _WEIGHT_EPSILON
    packed_weights[scalable] /= totals[scalable, np.newaxis]
    return packed_joints, packed_weights.astype(np.float32), blocks


def _vertex_group_influences(mesh, group_to_joint, dropped_groups, vertex_count, object_name):
    """Collect deform weights from the mesh vertices for the mapped vertex groups.

    Weight carried by a group with no corresponding skin joint is a correctness failure
    rather than a warning: the influence is discarded and the surviving weights on that
    vertex renormalize, which silently changes the deformation relative to the scene.
    ``mesh_validation`` cannot catch this because it matches groups against every bone
    while the skin only binds ``use_deform`` bones.
    """
    if not group_to_joint:
        return None, None, 0

    vertex_ids = []
    joint_ids = []
    weights = []
    append_vertex = vertex_ids.append
    append_joint = joint_ids.append
    append_weight = weights.append
    lookup = group_to_joint.get
    dropped_lookup = dropped_groups.get if dropped_groups else None
    weighted_drops = set()

    for vertex_index, vertex in enumerate(mesh.vertices):
        for element in vertex.groups:
            weight = element.weight
            if weight <= _WEIGHT_EPSILON:
                continue
            joint = lookup(element.group)
            if joint is None:
                if dropped_lookup is not None:
                    name = dropped_lookup(element.group)
                    if name is not None:
                        weighted_drops.add(name)
                continue
            append_vertex(vertex_index)
            append_joint(joint)
            append_weight(weight)

    if weighted_drops:
        names = ", ".join(sorted(weighted_drops)[:16])
        raise DirectMeshExportError(
            f"{object_name!r} carries weight on {len(weighted_drops)} vertex group(s) "
            f"that bind to no deform bone: {names}. Enable Deform on the matching bones "
            "or remove the weights; exporting would renormalize the remaining "
            "influences and change the deformation."
        )
    return _pack_influences(vertex_ids, joint_ids, weights, vertex_count)


def _object_group_to_joint(obj, binding: SkeletonWriteBinding):
    """Map this object's vertex group indices onto skin joint indices by bone name.

    Returns the index mapping plus the groups that resolved to nothing, keyed by group
    index so the weight scan can report only those that actually carry weight.
    """
    mapping = {}
    dropped = {}
    for group in obj.vertex_groups:
        joint = binding.group_to_joint.get(group.name)
        if joint is None:
            dropped[group.index] = group.name
            continue
        mapping[group.index] = joint
    return mapping, dropped


def _armature_of(obj):
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object is not None:
            return modifier.object
    parent = obj.parent
    if parent is not None and parent.type == "ARMATURE":
        return parent
    return None


def _deform_bone_order(armature):
    """Depth-first ordering of deform bones, parents ahead of children."""
    ordered = []
    parents = []
    index_of = {}

    def visit(bone, parent_index):
        current = parent_index
        if bone.use_deform:
            current = len(ordered)
            index_of[bone.name] = current
            ordered.append(bone)
            parents.append(parent_index)
        for child in bone.children:
            visit(child, current)

    for bone in armature.data.bones:
        if bone.parent is None:
            visit(bone, -1)
    return ordered, parents, index_of


def _snapshot_source_bone_names(armature) -> tuple[str, ...]:
    """Read the source joint order the direct mesh importer stored on the armature.

    ``merged_bone_name`` maps authored plug names onto merged slot names and is not
    invertible, so a Blender rig cannot reproduce the source joint names on its own. The
    importer records them under the mesh-specific source-rest key; this is the only way
    to emit a GLB whose joint identities match the asset the mesh was imported from.
    """
    raw = armature.get(_MESH_SOURCE_REST_SNAPSHOT_KEY)
    if not raw:
        # Backward compatibility for files imported before mesh and animation source
        # rests were separated.
        raw = armature.get(SOURCE_REST_SNAPSHOT_KEY)
    if not raw:
        return ()
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError):
        print(
            f"[CP77 Direct Mesh Export] {armature.name}: source rest snapshot is "
            "unreadable; falling back to the deform bone hierarchy."
        )
        return ()
    names = payload.get("boneNames") or ()
    return tuple(str(name) for name in names)


def _resolve_target_bone_name(armature, source_name):
    """Resolve a source joint name onto a bone in this armature.

    Mirrors the forward resolution the importer and the animation exporter use, rather
    than attempting to invert merged_bone_name.
    """
    bones = armature.data.bones
    if bones.get(source_name) is not None:
        return source_name
    mapped = merged_bone_name(source_name)
    return mapped if bones.get(mapped) is not None else None


def _binding_from_source_names(
    armature,
    source_names,
    source_parent_indices=None,
):
    """Build the joint list in source order, keyed to this armature's bones."""
    target_names = []
    bones = []
    used = {}
    for source_name in source_names:
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            raise DirectMeshExportError(
                f"Armature {armature.name!r} is missing source joint {source_name!r} "
                f"(also tried {merged_bone_name(source_name)!r})."
            )
        if target_name in used:
            raise DirectMeshExportError(
                f"Source joints {used[target_name]!r} and {source_name!r} both resolve "
                f"to bone {target_name!r}."
            )
        used[target_name] = source_name
        target_names.append(target_name)
        bones.append(armature.data.bones[target_name])

    index_of_target = {name: index for index, name in enumerate(target_names)}
    if source_parent_indices is not None:
        try:
            parent_indices = [int(value) for value in source_parent_indices]
        except (TypeError, ValueError) as error:
            raise DirectMeshExportError(
                "The imported mesh skin binding contains invalid parent indices."
            ) from error
        if len(parent_indices) != len(source_names):
            raise DirectMeshExportError(
                "The imported mesh skin binding parent count does not match its joints."
            )
    else:
        parent_indices = []
        for bone in bones:
            parent = bone.parent
            while parent is not None and parent.name not in index_of_target:
                parent = parent.parent
            parent_indices.append(
                -1 if parent is None else index_of_target[parent.name]
            )

    for index, parent_index in enumerate(parent_indices):
        if parent_index < -1 or parent_index >= index:
            raise DirectMeshExportError(
                f"Invalid source parent index {parent_index} for joint "
                f"{source_names[index]!r}."
            )
    return tuple(source_names), tuple(parent_indices), bones, index_of_target


def _source_rest_globals_if_untouched(
    armature,
    source_names,
    parent_indices,
    bones,
    source_rest_snapshot=None,
):
    snapshot = (
        source_rest_snapshot
        if isinstance(source_rest_snapshot, dict)
        else _json_property(armature, _MESH_SOURCE_REST_SNAPSHOT_KEY, None)
    )
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("space") != SOURCE_REST_SPACE_CONTRACT:
        return None
    snapshot_names = tuple(str(name) for name in snapshot.get("boneNames", ()))
    if snapshot_names != tuple(source_names):
        return None

    count = len(source_names)
    try:
        relative = np.asarray(
            snapshot.get("matrices"), dtype=np.float64
        ).reshape(count, 4, 4)
    except (TypeError, ValueError):
        return None
    if not np.all(np.isfinite(relative)):
        return None

    source_globals = np.empty_like(relative)
    for index, parent_index in enumerate(parent_indices):
        source_globals[index] = (
            relative[index]
            if parent_index < 0
            else source_globals[parent_index] @ relative[index]
        )

    current_globals = np.asarray(
        [_matrix_to_numpy(bone.matrix_local) for bone in bones],
        dtype=np.float64,
    )
    target_payload = snapshot.get("targetMatrices")
    if target_payload is not None:
        try:
            imported_targets = np.asarray(
                target_payload, dtype=np.float64
            ).reshape(count, 4, 4)
        except (TypeError, ValueError):
            return None
        # The importer records the Blender rest actually present after its bind-pose
        # correction. Reuse the exact WolvenKit matrices only while that rest remains
        # unchanged; any deliberate edit switches export back to the live armature.
        if not np.allclose(
            current_globals, imported_targets, rtol=0.0, atol=1.0e-7
        ):
            return None
    elif not np.allclose(
        current_globals, source_globals, rtol=0.0, atol=5.0e-5
    ):
        # Compatibility with version-1 snapshots, which did not store the
        # post-import Blender rest fingerprint.
        return None
    return source_globals


def build_mesh_skeleton_binding(
    armature,
    source_skin_extras=None,
    source_skin_binding=None,
    source_rest_snapshot=None,
) -> SkeletonWriteBinding:
    """Rebuild the glTF skin from an armature's rest pose.

    Joint names, ordering and parent indices come from the imported source binding.
    For an untouched import, the exact WolvenKit bind matrices are reused so Blender's
    edit-bone head/tail/roll quantization cannot leak into the GLB. The importer also
    records the post-import Blender rest as a fingerprint; once that rest is edited,
    export intentionally derives matrices from the live armature instead.
    """
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise DirectMeshExportError("Skinned mesh export requires an armature object.")

    source_skin_binding = (
        source_skin_binding if isinstance(source_skin_binding, dict) else {}
    )
    source_names = tuple(
        str(name) for name in (source_skin_binding.get("boneNames") or ())
    )
    source_parent_indices = source_skin_binding.get("boneParentIndexes")
    if not source_names:
        source_names = _snapshot_source_bone_names(armature)
        source_parent_indices = None
    if source_names:
        bone_names, parent_indices, bones, group_to_joint = _binding_from_source_names(
            armature,
            source_names,
            source_parent_indices=source_parent_indices,
        )
    else:
        bones, parent_list, index_of = _deform_bone_order(armature)
        if not bones:
            raise DirectMeshExportError(
                f"Armature {armature.name!r} exposes no deform bones to bind against."
            )
        bone_names = tuple(bone.name for bone in bones)
        parent_indices = tuple(int(value) for value in parent_list)
        group_to_joint = index_of

    source_globals_blender = _source_rest_globals_if_untouched(
        armature,
        bone_names,
        parent_indices,
        bones,
        source_rest_snapshot=source_rest_snapshot,
    )
    globals_blender = (
        source_globals_blender
        if source_globals_blender is not None
        else np.asarray(
            [_matrix_to_numpy(bone.matrix_local) for bone in bones],
            dtype=np.float64,
        )
    )
    globals_gltf = np.asarray(
        [_bone_matrix_to_gltf(matrix) for matrix in globals_blender],
        dtype=np.float64,
    )

    node_local = np.empty_like(globals_gltf)
    for index, parent_index in enumerate(parent_indices):
        node_local[index] = (
            globals_gltf[index]
            if parent_index < 0
            else np.linalg.inv(globals_gltf[parent_index]) @ globals_gltf[index]
        )

    try:
        inverse_bind = np.linalg.inv(globals_gltf)
    except np.linalg.LinAlgError as error:
        raise DirectMeshExportError(
            f"Armature {armature.name!r} has a singular bone rest matrix."
        ) from error

    return SkeletonWriteBinding(
        bone_names=bone_names,
        parent_indices=parent_indices,
        node_local_gltf=node_local,
        inverse_bind_gltf=inverse_bind,
        group_to_joint=dict(group_to_joint),
        rig_path=str(armature.get("rigPath", "") or ""),
        skin_extras=copy.deepcopy(source_skin_extras),
    )


def _json_property(idblock, key, default=None):
    if idblock is None or key not in idblock:
        return default
    try:
        return json.loads(str(idblock[key]))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _node_extras(obj) -> dict:
    extras = copy.deepcopy(_json_property(obj, _SOURCE_NODE_EXTRAS_KEY, {}))
    for key in obj.keys():
        if key.startswith("_") or key in _INTERNAL_OBJECT_KEYS:
            continue
        value = obj[key]
        if isinstance(value, (str, bool, int, float)):
            extras[key] = value
    return extras


def _material_names(obj) -> list[str]:
    mesh_extras = _json_property(obj, _SOURCE_MESH_EXTRAS_KEY, {})
    source_names = mesh_extras.get("materialNames") if isinstance(mesh_extras, dict) else None
    if isinstance(source_names, list):
        return [str(value) for value in source_names]
    explicit = obj.get("cp77_material_name")
    if isinstance(explicit, str) and explicit:
        return [explicit]
    return [slot.material.name for slot in obj.material_slots if slot.material is not None]


def _point_vector_attribute(mesh, name):
    attribute = mesh.attributes.get(name)
    if attribute is None or attribute.domain != "POINT" or attribute.data_type != "FLOAT_VECTOR":
        return None
    values = np.empty((len(attribute.data), 3), dtype=np.float32)
    attribute.data.foreach_get("vector", values.reshape(-1))
    return values


def _point_float_attribute(mesh, name):
    attribute = mesh.attributes.get(name)
    if attribute is None or attribute.domain != "POINT" or attribute.data_type != "FLOAT":
        return None
    values = np.empty(len(attribute.data), dtype=np.float32)
    attribute.data.foreach_get("value", values)
    return values


def build_export_submesh(
    obj,
    binding: SkeletonWriteBinding | None,
    *,
    armature=None,
    apply_modifiers: bool = True,
    flip_v: bool = True,
    bake_transform: bool = True,
    export_garment_morph: bool = True,
    export_garment_attributes: bool = True,
) -> ExportSubmesh:
    """Expand one Blender mesh object into per-vertex glTF attribute blocks."""
    _require_bpy()
    if obj.type != "MESH":
        raise DirectMeshExportError(f"{obj.name!r} is not a mesh object.")

    with _EvaluationTarget(obj, apply_modifiers) as target:
        mesh = target.mesh
        if not len(mesh.polygons):
            raise DirectMeshExportError(f"Mesh {obj.name!r} contains no faces.")

        loop_vertices = _loop_vertex_indices(mesh)
        triangles_loops = _triangle_loops(mesh)
        uv_layers = _uv_loop_layers(mesh)
        standard_colors, custom_colors = _split_color_attributes(mesh, obj.name)

        source_normals = _point_vector_attribute(mesh, _SOURCE_NORMAL_ATTRIBUTE)
        if source_normals is not None and len(source_normals) == len(mesh.vertices):
            normals = source_normals
            normals_per_vertex = True
        else:
            normals, normals_per_vertex = _mesh_normals(mesh)

        source_tangents = _point_vector_attribute(mesh, _SOURCE_TANGENT_ATTRIBUTE)
        source_tangent_signs = _point_float_attribute(
            mesh,
            _SOURCE_TANGENT_SIGN_ATTRIBUTE,
        )
        if (
            source_tangents is not None
            and source_tangent_signs is not None
            and len(source_tangents) == len(mesh.vertices)
            and len(source_tangent_signs) == len(mesh.vertices)
        ):
            tangents = np.ascontiguousarray(source_tangents[loop_vertices])
            tangent_signs = np.ascontiguousarray(source_tangent_signs[loop_vertices])
        else:
            tangents, tangent_signs = _corner_tangents(
                mesh,
                uv_layers[0][0] if uv_layers else None,
            )

        color_loops = [
            _color_loop_values(mesh, attribute, loop_vertices)
            for attribute in standard_colors
        ]
        custom_color_loops = [
            (attribute.name, _color_loop_values(mesh, attribute, loop_vertices))
            for attribute in custom_colors
            if export_garment_attributes
            or attribute.name not in (GARMENT_CAP_ATTRIBUTE, GARMENT_WEIGHT_ATTRIBUTE)
        ]

        vertex_positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", vertex_positions)
        vertex_positions = vertex_positions.reshape(-1, 3)

        if target.apply_modifiers:
            morph_targets = _morph_deltas_through_modifiers(
                target.object,
                target.depsgraph,
                vertex_positions,
            )
        else:
            morph_targets = _morph_deltas_from_shape_keys(obj, vertex_positions.shape[0])
        if not export_garment_morph:
            morph_targets = [
                item for item in morph_targets
                if item[0].casefold() != GARMENT_SUPPORT_MORPH.casefold()
            ]

        group_to_joint = {}
        dropped_groups = {}
        if binding is not None:
            group_to_joint, dropped_groups = _object_group_to_joint(obj, binding)
        joint_blocks, weight_blocks, _ = _vertex_group_influences(
            mesh,
            group_to_joint,
            dropped_groups,
            vertex_positions.shape[0],
            obj.name,
        )

        # Split key: any loop-domain divergence forces a new glTF vertex, since every
        # exported attribute lives on the vertex domain.
        flat_loops = triangles_loops.reshape(-1)
        key_columns = [loop_vertices[flat_loops]]
        if normals is not None and not normals_per_vertex:
            key_columns.append(_split_key_column(normals[flat_loops]))
        if tangents is not None:
            key_columns.append(_split_key_column(tangents[flat_loops]))
            key_columns.append(_split_key_column(tangent_signs[flat_loops]))
        for _, uv in uv_layers:
            key_columns.append(_split_key_column(uv[flat_loops]))
        for color in color_loops:
            key_columns.append(_split_key_column(color[flat_loops]))
        for _, color in custom_color_loops:
            key_columns.append(_split_key_column(color[flat_loops]))

        representative, inverse = _unique_rows(key_columns)
        if representative.shape[0] > VERT_LIMIT:
            raise DirectMeshExportError(
                f"{obj.name!r} expands to {representative.shape[0]} vertices after "
                f"attribute splitting, above the {VERT_LIMIT} submesh limit. "
                "predicted_export_vertex_count does not model tangent or colour-alpha "
                "divergence, so it can under-report; split the submesh or reduce UV "
                "and normal seams."
            )
        source_loops = flat_loops[representative]
        source_vertices = loop_vertices[source_loops]
        triangles = inverse.reshape(-1, 3).astype(np.int32)

        positions = np.ascontiguousarray(vertex_positions[source_vertices])
        if normals is None:
            split_normals = None
        else:
            split_normals = np.ascontiguousarray(
                normals[source_vertices] if normals_per_vertex else normals[source_loops]
            )
        split_tangents = None
        if tangents is not None:
            split_tangents = np.empty((source_loops.shape[0], 4), dtype=np.float32)
            split_tangents[:, :3] = tangents[source_loops]
            split_tangents[:, 3] = tangent_signs[source_loops]

        split_uvs = []
        for _, uv in uv_layers:
            values = np.array(uv[source_loops], dtype=np.float32, order="C", copy=True)
            if flip_v:
                values[:, 1] = 1.0 - values[:, 1]
            split_uvs.append(values)
        split_colors = [
            np.ascontiguousarray(color[source_loops]) for color in color_loops
        ]
        split_custom_colors = [
            (name, np.ascontiguousarray(color[source_loops]))
            for name, color in custom_color_loops
        ]
        split_morphs = [
            (name, np.ascontiguousarray(delta[source_vertices]))
            for name, delta in morph_targets
        ]
        split_joints = (
            np.ascontiguousarray(joint_blocks[source_vertices])
            if joint_blocks is not None
            else None
        )
        split_weights = (
            np.ascontiguousarray(weight_blocks[source_vertices])
            if weight_blocks is not None
            else None
        )

    skinned = split_joints is not None
    if skinned:
        # The importer derives bind data as mesh_node_global @ inv(inverseBindMatrix)
        # and compares it against the joint node globals, so a skinned mesh node has to
        # be identity; any residual object transform is baked into the geometry instead.
        relative = np.eye(4, dtype=np.float64)
        if armature is not None:
            relative = _matrix_to_numpy(
                armature.matrix_world.inverted() @ obj.matrix_world
            )
        node_matrix_gltf = np.eye(4, dtype=np.float64)
    else:
        relative = _matrix_to_numpy(obj.matrix_world)
        node_matrix_gltf = (
            np.eye(4, dtype=np.float64)
            if bake_transform
            else _red_matrix_to_gltf(relative)
        )

    if (skinned or bake_transform) and not _is_identity(relative):
        positions, split_normals, split_tangents, split_morphs = _bake_transform(
            relative,
            positions,
            split_normals,
            split_tangents,
            split_morphs,
        )

    return ExportSubmesh(
        name=obj.name,
        positions=_rotate_to_gltf(positions),
        triangles=triangles,
        normals=_rotate_to_gltf(split_normals) if split_normals is not None else None,
        tangents=_rotate_tangents(split_tangents),
        node_matrix_gltf=node_matrix_gltf,
        uv_layers=split_uvs,
        color_layers=split_colors,
        custom_colors=split_custom_colors,
        joint_indices=split_joints,
        joint_weights=split_weights,
        morph_targets=[
            (name, _rotate_to_gltf(delta)) for name, delta in split_morphs
        ],
        material_names=_material_names(obj),
        material_index=(
            int(obj[_SOURCE_MATERIAL_INDEX_KEY])
            if _SOURCE_MATERIAL_INDEX_KEY in obj
            else None
        ),
        mesh_extras=copy.deepcopy(
            _json_property(obj, _SOURCE_MESH_EXTRAS_KEY, {})
        ),
        node_extras=_node_extras(obj),
        skinned=skinned,
    )


def _rotate_tangents(tangents):
    if tangents is None:
        return None
    result = np.empty_like(tangents)
    result[:, :3] = np.asarray(tangents[:, :3], dtype=np.float32) @ _ROTATION_RED_TO_GLTF_T
    result[:, 3] = tangents[:, 3]
    return np.ascontiguousarray(result)


def _bake_transform(matrix, positions, normals, tangents, morphs):
    """Fold a residual object transform into geometry for identity-node skinned meshes."""
    linear = matrix[:3, :3]
    translation = matrix[:3, 3]
    normal_matrix = np.linalg.inv(linear).T
    # A mirroring transform reverses the basis handedness, so the stored bitangent sign
    # no longer describes cross(normal, tangent) * w in the baked frame.
    handedness = -1.0 if np.linalg.det(linear) < 0.0 else 1.0

    baked_positions = np.ascontiguousarray(
        (positions @ linear.T + translation).astype(np.float32)
    )
    baked_normals = None
    if normals is not None:
        rotated = normals @ normal_matrix.T
        lengths = np.linalg.norm(rotated, axis=1, keepdims=True)
        np.maximum(lengths, 1.0e-12, out=lengths)
        baked_normals = np.ascontiguousarray((rotated / lengths).astype(np.float32))
    baked_tangents = None
    if tangents is not None:
        baked_tangents = np.empty_like(tangents)
        rotated = tangents[:, :3] @ linear.T
        lengths = np.linalg.norm(rotated, axis=1, keepdims=True)
        np.maximum(lengths, 1.0e-12, out=lengths)
        baked_tangents[:, :3] = rotated / lengths
        baked_tangents[:, 3] = tangents[:, 3] * handedness
        baked_tangents = np.ascontiguousarray(baked_tangents)
    baked_morphs = [
        (name, np.ascontiguousarray((delta @ linear.T).astype(np.float32)))
        for name, delta in morphs
    ]
    return baked_positions, baked_normals, baked_tangents, baked_morphs


def _write_primitive(builder: MeshGLBBuilder, submesh: ExportSubmesh) -> dict:
    vertex_count = submesh.vertex_count
    attributes = {
        "POSITION": builder.add_float_accessor(
            submesh.positions,
            "VEC3",
            name=f"{submesh.name}/POSITION",
            target=_ARRAY_BUFFER,
        )
    }
    if submesh.normals is not None:
        attributes["NORMAL"] = builder.add_float_accessor(
            submesh.normals,
            "VEC3",
            name=f"{submesh.name}/NORMAL",
            target=_ARRAY_BUFFER,
            include_bounds=False,
        )
    if submesh.tangents is not None:
        attributes["TANGENT"] = builder.add_float_accessor(
            submesh.tangents,
            "VEC4",
            name=f"{submesh.name}/TANGENT",
            target=_ARRAY_BUFFER,
            include_bounds=False,
        )
    for index, uv in enumerate(submesh.uv_layers[: len(_UV_ATTRIBUTES)]):
        attributes[_UV_ATTRIBUTES[index]] = builder.add_float_accessor(
            uv,
            "VEC2",
            name=f"{submesh.name}/{_UV_ATTRIBUTES[index]}",
            target=_ARRAY_BUFFER,
            include_bounds=False,
        )
    for index, color in enumerate(submesh.color_layers[: len(_COLOR_ATTRIBUTES)]):
        attributes[_COLOR_ATTRIBUTES[index]] = builder.add_float_accessor(
            color,
            "VEC4",
            name=f"{submesh.name}/{_COLOR_ATTRIBUTES[index]}",
            target=_ARRAY_BUFFER,
            include_bounds=False,
        )
    for name, color in submesh.custom_colors:
        attributes[name.upper()] = builder.add_normalized_accessor(
            color,
            "VEC4",
            5121,
            name=f"{submesh.name}/{name.upper()}",
            target=_ARRAY_BUFFER,
        )
    if submesh.joint_indices is not None and submesh.joint_weights is not None:
        blocks = submesh.joint_indices.shape[1] // 4
        for block in range(blocks):
            span = slice(block * 4, block * 4 + 4)
            attributes[_JOINT_ATTRIBUTES[block]] = builder.add_integer_accessor(
                submesh.joint_indices[:, span],
                "VEC4",
                5123,
                name=f"{submesh.name}/{_JOINT_ATTRIBUTES[block]}",
                target=_ARRAY_BUFFER,
                include_bounds=True,
            )
            attributes[_WEIGHT_ATTRIBUTES[block]] = builder.add_float_accessor(
                submesh.joint_weights[:, span],
                "VEC4",
                name=f"{submesh.name}/{_WEIGHT_ATTRIBUTES[block]}",
                target=_ARRAY_BUFFER,
                include_bounds=False,
            )

    component_type = 5125 if vertex_count > VERT_LIMIT else 5123
    primitive = {
        "attributes": attributes,
        "indices": builder.add_integer_accessor(
            submesh.triangles,
            "SCALAR",
            component_type,
            name=f"{submesh.name}/indices",
            target=_ELEMENT_ARRAY_BUFFER,
        ),
        "mode": 4,
    }
    if submesh.material_index is not None:
        primitive["material"] = int(submesh.material_index)
    if submesh.morph_targets:
        primitive["targets"] = [
            {
                "POSITION": builder.add_float_accessor(
                    delta,
                    "VEC3",
                    name=f"{submesh.name}/{name}",
                    target=_ARRAY_BUFFER,
                )
            }
            for name, delta in submesh.morph_targets
        ]
    return primitive


def _shared_json_property(objects, key, default=None):
    resolved = []
    for obj in objects:
        if key not in obj:
            continue
        value = _json_property(obj, key, default)
        if not resolved:
            resolved.append(value)
        elif value != resolved[0]:
            raise DirectMeshExportError(
                f"Selected objects do not share the same {key!r} source metadata."
            )
    return resolved[0] if resolved else default


def build_direct_mesh_glb(
    objects,
    *,
    armature=None,
    is_skinned: bool = True,
    apply_modifiers: bool = True,
    flip_v: bool = True,
    bake_transforms: bool = True,
    export_garment_morph: bool = True,
    export_garment_attributes: bool = True,
):
    """Assemble the glTF document and BIN payload for a set of submesh objects."""
    _require_bpy()
    mesh_objects = [obj for obj in objects if obj.type == "MESH"]
    if not mesh_objects:
        raise DirectMeshExportError("No mesh objects were supplied for export.")

    armatures = {
        found.name: found
        for found in (_armature_of(obj) for obj in mesh_objects)
        if found is not None
    }
    if armature is not None:
        armatures.setdefault(armature.name, armature)
    if len(armatures) > 1:
        raise DirectMeshExportError(
            "Direct mesh export requires a single armature; found "
            + ", ".join(sorted(armatures))
        )
    resolved_armature = armature or (next(iter(armatures.values())) if armatures else None)
    if not is_skinned:
        resolved_armature = None
    source_skin_extras = _shared_json_property(
        mesh_objects,
        _SOURCE_SKIN_EXTRAS_KEY,
        None,
    )
    source_skin_binding = _shared_json_property(
        mesh_objects,
        _SOURCE_SKIN_BINDING_KEY,
        None,
    )
    source_rest_snapshot = _shared_json_property(
        mesh_objects,
        _MESH_SOURCE_REST_SNAPSHOT_KEY,
        None,
    )
    binding = (
        build_mesh_skeleton_binding(
            resolved_armature,
            source_skin_extras=source_skin_extras,
            source_skin_binding=source_skin_binding,
            source_rest_snapshot=source_rest_snapshot,
        )
        if resolved_armature is not None
        else None
    )

    submeshes = [
        build_export_submesh(
            obj,
            binding,
            armature=resolved_armature,
            apply_modifiers=apply_modifiers,
            flip_v=flip_v,
            bake_transform=bake_transforms,
            export_garment_morph=export_garment_morph,
            export_garment_attributes=export_garment_attributes,
        )
        for obj in mesh_objects
    ]
    return assemble_mesh_document(
        submeshes,
        binding,
        document_metadata=_shared_json_property(
            mesh_objects,
            _SOURCE_DOCUMENT_METADATA_KEY,
            {},
        ),
        scene_metadata=_shared_json_property(
            mesh_objects,
            _SOURCE_SCENE_METADATA_KEY,
            {},
        ),
    )


def assemble_mesh_document(
    submeshes,
    binding: SkeletonWriteBinding | None,
    *,
    document_metadata=None,
    scene_metadata=None,
):
    """Serialize expanded submeshes and an optional skin into a glTF document."""
    builder = MeshGLBBuilder()
    nodes = []
    skin = None
    joint_offset = 0

    if binding is not None:
        inverse_bind_accessor = builder.add_float_accessor(
            binding.inverse_bind_gltf,
            "MAT4",
            name="Bind Matrices",
            matrix_column_major=True,
            include_bounds=False,
        )
        child_lists = [[] for _ in binding.bone_names]
        root_indices = []
        for index, parent_index in enumerate(binding.parent_indices):
            if parent_index < 0:
                root_indices.append(index)
            else:
                child_lists[parent_index].append(index)

        nodes.append({"name": "Armature", "children": [index + 1 for index in root_indices]})
        joint_offset = 1
        for index, bone_name in enumerate(binding.bone_names):
            node = {"name": bone_name}
            node.update(_decompose_node(binding.node_local_gltf[index]))
            if child_lists[index]:
                node["children"] = [child + joint_offset for child in child_lists[index]]
            nodes.append(node)

        skin_extras = (
            copy.deepcopy(binding.skin_extras)
            if binding.skin_extras is not None
            else {
                "rigPath": binding.rig_path,
                "boneNames": list(binding.bone_names),
                "boneParentIndexes": list(binding.parent_indices),
            }
        )
        skin = {
            "name": "Armature",
            "inverseBindMatrices": inverse_bind_accessor,
            "joints": [index + joint_offset for index in range(len(binding.bone_names))],
            "extras": skin_extras,
        }

    meshes = []
    scene_nodes = [0] if binding is not None else []
    for submesh in submeshes:
        mesh_extras = copy.deepcopy(submesh.mesh_extras)
        if submesh.material_names:
            mesh_extras["materialNames"] = list(submesh.material_names)
        else:
            mesh_extras.pop("materialNames", None)
        if submesh.morph_targets:
            mesh_extras["targetNames"] = [name for name, _ in submesh.morph_targets]
        else:
            mesh_extras.pop("targetNames", None)

        mesh_document = {
            "name": submesh.name,
            "primitives": [_write_primitive(builder, submesh)],
        }
        if mesh_extras:
            mesh_document["extras"] = mesh_extras
        if submesh.morph_targets:
            mesh_document["weights"] = [0.0] * len(submesh.morph_targets)

        node = {"name": submesh.name, "mesh": len(meshes)}
        node.update(_decompose_node(submesh.node_matrix_gltf))
        if submesh.skinned and skin is not None:
            node["skin"] = 0
        if submesh.node_extras:
            node["extras"] = submesh.node_extras
        meshes.append(mesh_document)
        scene_nodes.append(len(nodes))
        nodes.append(node)

    scene = copy.deepcopy(scene_metadata or {})
    scene["nodes"] = scene_nodes
    document = {
        "asset": {
            "copyright": "",
            "generator": DIRECT_MESH_GENERATOR,
            "version": "2.0",
        },
        "accessors": builder.accessors,
        "bufferViews": builder.buffer_views,
        "buffers": [{"byteLength": len(builder.binary)}],
        "meshes": meshes,
        "nodes": nodes,
        "scene": 0,
        "scenes": [scene],
    }
    for key, value in (document_metadata or {}).items():
        if key not in document:
            document[key] = copy.deepcopy(value)
    if skin is not None:
        document["skins"] = [skin]

    summary = {
        "submesh_count": len(submeshes),
        "vertex_count": sum(submesh.vertex_count for submesh in submeshes),
        "triangle_count": sum(int(submesh.triangles.shape[0]) for submesh in submeshes),
        "joint_count": len(binding.bone_names) if binding is not None else 0,
        "morph_count": sum(len(submesh.morph_targets) for submesh in submeshes),
        "accessor_count": len(builder.accessors),
        "binary_bytes": len(builder.binary),
        "skinned": binding is not None,
    }
    return document, bytes(builder.binary), summary


def validate_direct_mesh_document(document: dict, binary: bytes) -> dict:
    """Check the emitted document against the constraints direct_mesh_import enforces."""
    accessors = document.get("accessors") or []
    views = document.get("bufferViews") or []
    nodes = document.get("nodes") or []
    meshes = document.get("meshes") or []
    if not meshes:
        raise DirectMeshExportError("The document contains no meshes.")

    declared = int(document.get("buffers", [{}])[0].get("byteLength", -1))
    if declared != len(binary):
        raise DirectMeshExportError("buffers[0].byteLength disagrees with the BIN payload.")
    for index, view in enumerate(views):
        if int(view.get("buffer", 0)) != 0:
            raise DirectMeshExportError(f"bufferViews[{index}] targets a non-embedded buffer.")
        end = int(view.get("byteOffset", 0)) + int(view.get("byteLength", 0))
        if end > len(binary):
            raise DirectMeshExportError(f"bufferViews[{index}] overruns the BIN payload.")

    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    for index, accessor in enumerate(accessors):
        width = widths.get(accessor.get("type"))
        size = sizes.get(int(accessor.get("componentType", 0)))
        if width is None or size is None:
            raise DirectMeshExportError(f"accessors[{index}] has an unsupported layout.")
        view_index = int(accessor.get("bufferView", -1))
        if not 0 <= view_index < len(views):
            raise DirectMeshExportError(f"accessors[{index}] references an invalid bufferView.")
        required = int(accessor.get("count", 0)) * width * size
        available = int(views[view_index].get("byteLength", 0)) - int(
            accessor.get("byteOffset", 0)
        )
        if required > available:
            raise DirectMeshExportError(f"accessors[{index}] overruns its bufferView.")

    skins = document.get("skins") or []
    joint_count = 0
    if skins:
        if len(skins) != 1:
            raise DirectMeshExportError("Direct mesh export writes exactly one skin.")
        skin = skins[0]
        joints = [int(value) for value in (skin.get("joints") or ())]
        if not joints or len(set(joints)) != len(joints):
            raise DirectMeshExportError("The skin joint list is empty or contains duplicates.")
        extras = skin.get("extras") or {}
        bone_names = [str(value) for value in (extras.get("boneNames") or ())]
        node_names = [str(nodes[joint].get("name", "")) for joint in joints]
        if bone_names:
            if bone_names != node_names:
                raise DirectMeshExportError(
                    "skin.extras.boneNames disagree with the joint node names."
                )
            if len(set(bone_names)) != len(bone_names) or not all(bone_names):
                raise DirectMeshExportError("skin.extras.boneNames are not unique.")

        parents = [int(value) for value in (extras.get("boneParentIndexes") or ())]
        if parents:
            if len(parents) != len(joints):
                raise DirectMeshExportError(
                    "boneParentIndexes length disagrees with the joint count."
                )
            for index, parent in enumerate(parents):
                if parent >= index or parent < -1:
                    raise DirectMeshExportError(
                        f"boneParentIndexes[{index}] is not topologically ordered."
                    )
                if parent >= 0 and joints[index] not in nodes[joints[parent]].get(
                    "children", ()
                ):
                    raise DirectMeshExportError(
                        f"Joint {index} disagrees with the node hierarchy."
                    )

        inverse_bind = int(skin.get("inverseBindMatrices", -1))
        if not 0 <= inverse_bind < len(accessors):
            raise DirectMeshExportError("The skin has no valid inverseBindMatrices accessor.")
        if accessors[inverse_bind].get("type") != "MAT4" or int(
            accessors[inverse_bind].get("count", -1)
        ) != len(joints):
            raise DirectMeshExportError("inverseBindMatrices must hold one MAT4 per joint.")
        joint_count = len(joints)

    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives") or ()
        if len(primitives) != 1:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] must contain exactly one primitive."
            )
        primitive = primitives[0]
        if int(primitive.get("mode", 4)) != 4:
            raise DirectMeshExportError(f"meshes[{mesh_index}] is not a triangle list.")
        attributes = primitive.get("attributes") or {}
        position = attributes.get("POSITION")
        if position is None:
            raise DirectMeshExportError(f"meshes[{mesh_index}] has no POSITION accessor.")
        vertex_count = int(accessors[int(position)].get("count", 0))
        for name, accessor_index in attributes.items():
            if int(accessors[int(accessor_index)].get("count", -1)) != vertex_count:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] attribute {name} disagrees with the vertex count."
                )

        joint_blocks = tuple(
            index for index, name in enumerate(_JOINT_ATTRIBUTES) if name in attributes
        )
        weight_blocks = tuple(
            index for index, name in enumerate(_WEIGHT_ATTRIBUTES) if name in attributes
        )
        if joint_blocks != weight_blocks:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] JOINTS/WEIGHTS blocks are not paired."
            )
        if joint_blocks and joint_blocks != tuple(range(len(joint_blocks))):
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] skinning blocks are not contiguous from zero."
            )
        if joint_blocks and not joint_count:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] carries skinning data without a skin."
            )
        for block in joint_blocks:
            accessor = accessors[int(attributes[_JOINT_ATTRIBUTES[block]])]
            bounds = accessor.get("max")
            if bounds is None:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] {_JOINT_ATTRIBUTES[block]} has no bounds to verify."
                )
            if int(max(bounds)) >= joint_count:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] {_JOINT_ATTRIBUTES[block]} references joint "
                    f"{int(max(bounds))} outside the {joint_count}-joint skin."
                )

        indices = primitive.get("indices")
        if indices is None:
            raise DirectMeshExportError(f"meshes[{mesh_index}] is not indexed.")
        index_count = int(accessors[int(indices)].get("count", 0))
        if index_count % 3:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] index count is not divisible by three."
            )

        targets = primitive.get("targets") or ()
        names = (mesh.get("extras") or {}).get("targetNames") or ()
        if targets and len(names) != len(targets):
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] targetNames disagree with its morph target count."
            )
        for target_index, target in enumerate(targets):
            target_accessor = target.get("POSITION")
            if target_accessor is None:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] target {target_index} has no POSITION delta."
                )
            if int(accessors[int(target_accessor)].get("count", -1)) != vertex_count:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] target {target_index} vertex count disagrees."
                )

    mesh_nodes = [node for node in nodes if "mesh" in node]
    for node in mesh_nodes:
        if "skin" in node and (
            "matrix" in node or "translation" in node or "rotation" in node or "scale" in node
        ):
            raise DirectMeshExportError(
                f"Skinned mesh node {node.get('name')!r} must carry an identity transform."
            )

    json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return {
        "valid": True,
        "mesh_count": len(meshes),
        "joint_count": joint_count,
        "accessor_count": len(accessors),
        "vertex_count": sum(
            int(accessors[int(mesh["primitives"][0]["attributes"]["POSITION"])]["count"])
            for mesh in meshes
        ),
    }


def validate_direct_mesh_glb_file(filepath: str) -> dict:
    """Re-parse a written GLB and validate its container plus mesh contract."""
    with open(filepath, "rb") as stream:
        payload = stream.read()
    if len(payload) < 20:
        raise DirectMeshExportError("GLB payload is truncated.")
    magic, version, total_length = struct.unpack_from("<4sII", payload, 0)
    if magic != b"glTF" or version != 2 or total_length != len(payload):
        raise DirectMeshExportError("GLB header is invalid.")

    offset = 12
    document = None
    binary = b""
    first_chunk = None
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise DirectMeshExportError("GLB chunk header is truncated.")
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        offset += 8
        end = offset + chunk_length
        if chunk_length % 4 or end > len(payload):
            raise DirectMeshExportError("GLB chunk length or alignment is invalid.")
        chunk = payload[offset:end]
        offset = end
        if first_chunk is None:
            first_chunk = chunk_type
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
        elif chunk_type == 0x004E4942:
            binary = chunk
    if first_chunk != 0x4E4F534A or document is None:
        raise DirectMeshExportError("The first GLB chunk must be JSON.")

    declared = int(document.get("buffers", [{}])[0].get("byteLength", -1))
    if declared < 0 or len(binary) - declared not in {0, 1, 2, 3}:
        raise DirectMeshExportError("The BIN chunk padding disagrees with buffers[0].byteLength.")
    validation = validate_direct_mesh_document(document, binary[:declared])
    validation["file_bytes"] = len(payload)
    validation["binary_chunk_bytes"] = len(binary)
    return validation


def export_mesh_glb_direct(
    filepath: str,
    objects,
    *,
    armature=None,
    is_skinned: bool = True,
    apply_modifiers: bool = True,
    flip_v: bool = True,
    bake_transforms: bool = True,
    export_garment_morph: bool = True,
    export_garment_attributes: bool = True,
) -> dict:
    """Write a WolvenKit-compatible mesh GLB and validate the result on disk."""
    document, binary, summary = build_direct_mesh_glb(
        objects,
        armature=armature,
        is_skinned=is_skinned,
        apply_modifiers=apply_modifiers,
        flip_v=flip_v,
        bake_transforms=bake_transforms,
        export_garment_morph=export_garment_morph,
        export_garment_attributes=export_garment_attributes,
    )
    summary["document_validation"] = validate_direct_mesh_document(document, binary)

    filepath = os.path.abspath(filepath)
    if not filepath.lower().endswith(".glb"):
        filepath += ".glb"
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temporary = filepath + ".tmp"
    payload = encode_glb(document, binary)
    try:
        with open(temporary, "wb") as stream:
            stream.write(payload)
        summary["file_validation"] = validate_direct_mesh_glb_file(temporary)
        atomic_replace_staged({filepath: temporary})
        temporary = ""
    except Exception:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        finally:
            raise
    summary["filepath"] = filepath
    summary["file_bytes"] = len(payload)
    return summary
