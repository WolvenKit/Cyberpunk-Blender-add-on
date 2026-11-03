from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from math import isfinite

import bpy
import numpy as np

from ...animation.domain.rig.naming import merged_bone_name
from ...bartmoss.arrays import float32_bit_keys, stable_unique_integer_rows
from ...bartmoss.geometry import transform_normalized_direction_deltas
from ...bartmoss.hierarchy import local_matrices_to_model
from ...bartmoss.matrix import as_matrix_4x4, matrix_is_identity
from ...bartmoss.weights import normalization_divisors
from ...blender.custom_normals import set_custom_normals_from_corners
from ...blender.mesh import (
    MESH_SOURCE_REST_SNAPSHOT_KEY,
    SOURCE_GEOMETRY_SIGNATURE_KEY,
    SOURCE_NORMAL_ATTRIBUTE,
    SOURCE_SHADING_SIGNATURE_KEY,
    SOURCE_SKIN_BINDING_KEY,
    SOURCE_SKIN_EXTRAS_KEY,
    SOURCE_TANGENT_ATTRIBUTE,
    SOURCE_TANGENT_FRAME_SIGNATURE_KEY,
    SOURCE_TANGENT_SIGN_ATTRIBUTE,
    export_material_names,
    geometry_and_tangent_frame_signatures,
    is_preview_only_modifier,
    shading_signature,
    source_vertex_indices,
)
from ...blender.mesh_validation import VERT_LIMIT, _loop_vertex_indices
from ...blender.morphs import (
    evaluated_morph_frame,
    mesh_corner_frame,
    morph_shading_from_mesh,
    source_morph_positions,
    source_morph_shading,
    source_position_only_morphs,
)
from ...core.log import get_logger, log_once
from ...gltf.builder import GLBBuilder
from ...gltf.channels import assign_attribute_channels, named_channel
from ...gltf.extras import skin_extras_for_export
from ...gltf.garment_support import (
    GARMENT_CAP_ATTRIBUTE,
    GARMENT_SUPPORT_MORPH,
    GARMENT_WEIGHT_ATTRIBUTE,
    canonical_garment_attribute,
    is_garment_attribute,
)
from ...gltf.mesh_contract import (
    COLOR_ATTRIBUTES,
    JOINT_ATTRIBUTES,
    MAX_SKIN_INFLUENCES,
    SKIN_WEIGHT_EPSILON,
    UV_ATTRIBUTES,
    WEIGHT_ATTRIBUTES,
    WOLVENKIT_UV_SETS,
)
from ...gltf.nodes import node_transforms
from ...gltf.provenance import DIRECT_MESH_GENERATOR
from ...gltf.submesh import ordered_submesh_objects, submesh_index_for_object
from ...redSpace.contracts import SOURCE_REST_SPACE_CONTRACT
from ...redSpace.tangent import convert_wolvenkit_tangent_sign
from ...redSpace.transforms import (
    blender_relative_to_gltf,
    red_matrix_to_gltf,
    red_vectors_to_gltf,
)
from ...redSpace.uv import convert_wolvenkit_uv_channel
from .errors import DirectMeshExportError

_LOG = get_logger(__name__)


_IDENTITY_TOLERANCE = 1.0e-9

_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963


@dataclass(slots=True)
class ExportSubmesh:
    name: str
    positions: np.ndarray
    triangles: np.ndarray
    normals: np.ndarray | None
    tangents: np.ndarray | None
    node_matrix_gltf: np.ndarray
    uv_layers: list[tuple[int, np.ndarray]] = field(default_factory=list)
    color_layers: list[tuple[int, np.ndarray]] = field(default_factory=list)
    custom_colors: list[tuple[str, np.ndarray]] = field(default_factory=list)
    joint_indices: np.ndarray | None = None
    joint_weights: np.ndarray | None = None
    morph_targets: list[tuple[str, np.ndarray]] = field(default_factory=list)
    morph_normals: list[tuple[str, np.ndarray]] = field(default_factory=list)
    morph_tangents: list[tuple[str, np.ndarray]] = field(default_factory=list)
    material_names: list[str] = field(default_factory=list)
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


def _rotate_to_gltf(values) -> np.ndarray:
    """Rotate an Nx3 REDengine/Blender vector block back into glTF space"""
    source = np.asarray(values, dtype=np.float32)
    if source.ndim != 2 or source.shape[1] < 3:
        raise DirectMeshExportError(
            f"Expected an Nx3 vector block, got {source.shape}."
        )
    return np.ascontiguousarray(red_vectors_to_gltf(source))


def _triangle_loops(mesh) -> np.ndarray:
    mesh.calc_loop_triangles()
    triangle_count = len(mesh.loop_triangles)
    if not triangle_count:
        raise DirectMeshExportError(f"Mesh {mesh.name!r} produced no triangles.")
    loops = np.empty(triangle_count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", loops)
    return loops.reshape(-1, 3)


def _mesh_normals(mesh):
    """Read point normals when shared by all corners, else corner normals"""
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
    """Return mikktspace loop tangents and bitangent signs, or None when unavailable"""
    if not uv_name or not hasattr(mesh, "calc_tangents"):
        return None, None
    try:
        mesh.calc_tangents(uvmap=uv_name)
    except (RuntimeError, TypeError) as error:
        _LOG.warning(
            "Tangents unavailable for %r; exporting without authored tangents: %s",
            mesh.name,
            error,
            exc_info=True,
        )
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


def _uv_loop_layers(mesh) -> list[tuple[int, str, np.ndarray]]:
    layers = []
    assignments = assign_attribute_channels(
        (uv_layer.name for uv_layer in mesh.uv_layers),
        base_name="UVMap",
        semantic="TEXCOORD",
        max_channels=WOLVENKIT_UV_SETS,
    )
    for layer_index, channel_index in assignments:
        uv_layer = mesh.uv_layers[layer_index]
        if named_channel(uv_layer.name, "UVMap", "TEXCOORD") is None:
            _LOG.warning(
                "%s: assigning UV layer %r to TEXCOORD_%d; use canonical UVMap names to retain explicit channel identity",
                mesh.name,
                uv_layer.name,
                channel_index,
            )
        values = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        uv_layer.uv.foreach_get("vector", values)
        layers.append((channel_index, uv_layer.name, values.reshape(-1, 2)))
    return layers


def _color_loop_values(attribute, loop_vertices) -> np.ndarray:
    """Read a colour attribute onto the loop domain as linear-or-raw float RGBA"""
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
    """Resolve explicit standard colour channels and canonical custom semantics"""
    standard = []
    custom = []
    custom_semantics = {}
    for attribute in mesh.color_attributes:
        if attribute.name.startswith("_"):
            if not is_garment_attribute(attribute.name):
                continue
            semantic = canonical_garment_attribute(attribute.name)
            previous = custom_semantics.get(semantic)
            if previous is not None:
                raise DirectMeshExportError(
                    f"{object_name!r} has custom colour attributes {previous!r} and "
                    f"{attribute.name!r} that both export as {semantic!r}."
                )
            custom_semantics[semantic] = attribute.name
            custom.append(attribute)
        else:
            standard.append(attribute)
    assignments = assign_attribute_channels(
        (attribute.name for attribute in standard),
        base_name="Color",
        semantic="COLOR",
        max_channels=len(COLOR_ATTRIBUTES),
    )
    resolved = []
    for index, channel in assignments:
        attribute = standard[index]
        if named_channel(attribute.name, "Color", "COLOR") is None:
            _LOG.warning(
                "%s: assigning colour layer %r to COLOR_%d; use canonical Color names to retain explicit channel identity",
                object_name,
                attribute.name,
                channel,
            )
        resolved.append((channel, attribute))
    return resolved, custom


def _export_shape_keys(obj, *, export_garment_morph):
    """Select exportable shape keys while retaining their Blender block indices"""
    shape_keys = getattr(obj.data, "shape_keys", None)
    if shape_keys is None:
        return []
    return [
        (index, block)
        for index, block in enumerate(shape_keys.key_blocks)
        if index
        and (
            export_garment_morph
            or block.name.casefold() != GARMENT_SUPPORT_MORPH.casefold()
        )
    ]


def _validate_shape_key_contract(obj, apply_modifiers, *, export_garment_morph):
    blocks = _export_shape_keys(obj, export_garment_morph=export_garment_morph)
    if not blocks:
        return
    keys = obj.data.shape_keys
    if not keys.use_relative:
        raise DirectMeshExportError(
            f"{obj.name!r}: absolute shape keys require conversion before export."
        )
    basis = keys.key_blocks[0]
    for _, block in blocks:
        if block.relative_key != basis or block.vertex_group:
            raise DirectMeshExportError(
                f"{obj.name!r}: shape key {block.name!r} must be relative to Basis "
                "without a vertex-group mask for direct export."
            )
    if not apply_modifiers:
        return
    stable_types = {
        "ARMATURE",
        "CAST",
        "CORRECTIVE_SMOOTH",
        "CURVE",
        "DISPLACE",
        "HOOK",
        "LAPLACIANDEFORM",
        "LAPLACIANSMOOTH",
        "LATTICE",
        "MESH_DEFORM",
        "NORMAL_EDIT",
        "SHRINKWRAP",
        "SIMPLE_DEFORM",
        "SMOOTH",
        "SUBSURF",
        "SURFACE_DEFORM",
        "TRIANGULATE",
        "UV_PROJECT",
        "UV_WARP",
        "WARP",
        "WAVE",
        "WEIGHTED_NORMAL",
        "VERTEX_WEIGHT_EDIT",
        "VERTEX_WEIGHT_MIX",
        "VERTEX_WEIGHT_PROXIMITY",
    }
    unsupported = [
        m.name
        for m in obj.modifiers
        if m.show_viewport and _exported_modifier(m) and m.type not in stable_types
    ]
    if unsupported:
        raise DirectMeshExportError(
            f"{obj.name!r}: stable morph vertex correspondence is not established for "
            + ", ".join(unsupported)
            + "; apply these modifiers with a verified shape-key workflow before export."
        )


def _exported_modifier(modifier) -> bool:
    """Armature deformation and preview-only modifiers never reach the exported geometry"""
    return modifier.type != "ARMATURE" and not is_preview_only_modifier(modifier)


def _has_applicable_modifiers(obj) -> bool:
    return any(
        modifier.show_viewport and _exported_modifier(modifier)
        for modifier in obj.modifiers
    )


def _position_only_morphs(obj) -> set[str]:
    """GarmentSupport keys imported without shading deltas"""
    return {
        name
        for name in source_position_only_morphs(obj)
        if name == GARMENT_SUPPORT_MORPH
    }


def _morph_deltas_from_shape_keys(
    obj, vertex_count, *, export_garment_morph
) -> list[tuple[str, np.ndarray]]:
    blocks = _export_shape_keys(obj, export_garment_morph=export_garment_morph)
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

    preserved = source_morph_positions(obj)
    targets = []
    for _, block in blocks:
        if block.name in preserved:
            targets.append((block.name, preserved[block.name]))
            continue
        values = np.empty(len(block.data) * 3, dtype=np.float32)
        block.data.foreach_get("co", values)
        targets.append((block.name, values.reshape(-1, 3) - base))
    return targets


def _morph_deltas_through_modifiers(
    obj, depsgraph, base_positions, base_mesh, uv_name, *, export_garment_morph
):
    """Evaluate position and shading deltas through the same isolated modifier stack"""
    blocks = _export_shape_keys(obj, export_garment_morph=export_garment_morph)
    if not blocks:
        return [], [], []
    base_loops = _loop_vertex_indices(base_mesh)
    base_totals = np.empty(len(base_mesh.polygons), dtype=np.int32)
    base_mesh.polygons.foreach_get("loop_total", base_totals)
    base_normals, base_tangents, base_signs = mesh_corner_frame(base_mesh, uv_name)
    key_blocks = obj.data.shape_keys.key_blocks
    basis = np.empty(len(key_blocks[0].data) * 3, dtype=np.float32)
    key_blocks[0].data.foreach_get("co", basis)
    scratch = np.empty_like(basis)
    raw_base_normals = np.empty(len(obj.data.loops) * 3, dtype=np.float32)
    obj.data.corner_normals.foreach_get("vector", raw_base_normals)
    raw_base_normals = raw_base_normals.reshape(-1, 3)
    basis_key_normals = np.asarray(
        key_blocks[0].normals_split_get(), dtype=np.float32
    ).reshape(-1, 3)
    raw_loops = _loop_vertex_indices(obj.data)
    raw_geometry_signature, raw_frame_signature = geometry_and_tangent_frame_signatures(
        obj.data, uv_name=uv_name
    )
    source_frame_valid = (
        str(obj.data.get(SOURCE_GEOMETRY_SIGNATURE_KEY, "")) == raw_geometry_signature
        and str(obj.data.get(SOURCE_TANGENT_FRAME_SIGNATURE_KEY, ""))
        == raw_frame_signature
        and str(obj.data.get(SOURCE_SHADING_SIGNATURE_KEY, ""))
        == shading_signature(obj.data)
    )
    preserved = source_morph_shading(obj, raw_loops) if source_frame_valid else {}
    position_only = _position_only_morphs(obj)
    native_normals, native_tangents = {}, {}
    basis_unchanged = False
    if preserved:
        raw_targets = [
            target
            for target in _morph_deltas_from_shape_keys(
                obj, len(obj.data.vertices), export_garment_morph=export_garment_morph
            )
            if target[0] not in position_only
        ]
        raw_normal_deltas, raw_tangent_deltas = morph_shading_from_mesh(
            obj.data, raw_targets, uv_name
        )
        native_normals, native_tangents = (
            dict(raw_normal_deltas),
            dict(raw_tangent_deltas),
        )
        raw_normals, raw_tangents, raw_signs = mesh_corner_frame(obj.data, uv_name)
        raw_totals = np.empty(len(obj.data.polygons), dtype=np.int32)
        obj.data.polygons.foreach_get("loop_total", raw_totals)
        basis_unchanged = (
            base_positions.shape == (len(obj.data.vertices), 3)
            and np.array_equal(base_loops, raw_loops)
            and np.array_equal(base_totals, raw_totals)
            and np.allclose(base_positions, basis.reshape(-1, 3), rtol=0, atol=2e-6)
            and np.allclose(base_normals, raw_normals, rtol=0, atol=2e-6)
            and np.allclose(base_tangents, raw_tangents, rtol=0, atol=2e-6)
            and np.array_equal(base_signs, raw_signs)
        )
    previous_only, previous_active = obj.show_only_shape_key, obj.active_shape_key_index
    positions, normals, tangents = [], [], []
    try:
        obj.show_only_shape_key = True
        for index, block in blocks:
            block.data.foreach_get("co", scratch)
            channels = preserved.get(block.name, {})
            independent_shading = any(
                not np.allclose(values, native[block.name], rtol=0, atol=2e-6)
                for semantic, native in (
                    ("normal", native_normals),
                    ("tangent", native_tangents),
                )
                if (values := channels.get(semantic)) is not None
            )
            if independent_shading and not basis_unchanged:
                raise DirectMeshExportError(
                    f"Shape key {block.name!r} on {obj.name!r} has authored morph shading that cannot be preserved through this modifier stack. Export without modifiers or rebuild the shape's shading explicitly."
                )
            if np.array_equal(scratch, basis):
                position_delta = np.zeros_like(base_positions)
                normal_delta, tangent_delta = (
                    np.zeros_like(base_normals),
                    np.zeros_like(base_tangents),
                )
                unchanged = basis_unchanged
            else:
                obj.active_shape_key_index = index
                shaded = block.name not in position_only
                if shaded:
                    desired_normals = (
                        raw_base_normals
                        + np.asarray(
                            block.normals_split_get(), dtype=np.float32
                        ).reshape(-1, 3)
                        - basis_key_normals
                    )
                    desired_normals /= np.maximum(
                        np.linalg.norm(desired_normals, axis=1, keepdims=True), 1e-12
                    )
                    set_custom_normals_from_corners(
                        obj.data, desired_normals, label=f"Morph {block.name}"
                    )
                    obj.data.update()
                depsgraph.update()
                (
                    target_positions,
                    target_loops,
                    target_totals,
                    target_normals,
                    target_tangents,
                    target_signs,
                ) = evaluated_morph_frame(obj, depsgraph, uv_name)
                if (
                    target_positions.shape != base_positions.shape
                    or not np.array_equal(base_loops, target_loops)
                    or not np.array_equal(base_totals, target_totals)
                ):
                    raise DirectMeshExportError(
                        f"Modifier stack on {obj.name!r} changes topology for shape key {block.name!r}."
                    )
                if shaded and not np.array_equal(base_signs, target_signs):
                    raise DirectMeshExportError(
                        f"Shape key {block.name!r} changes tangent handedness, which glTF morphs cannot encode."
                    )
                position_delta = target_positions - base_positions
                normal_delta, tangent_delta = (
                    target_normals - base_normals,
                    target_tangents - base_tangents,
                )
                unchanged = (
                    shaded
                    and basis_unchanged
                    and (
                        np.allclose(
                            target_positions, scratch.reshape(-1, 3), rtol=0, atol=2e-6
                        )
                        and np.allclose(
                            normal_delta, native_normals[block.name], rtol=0, atol=2e-6
                        )
                        and np.allclose(
                            tangent_delta,
                            native_tangents[block.name],
                            rtol=0,
                            atol=2e-6,
                        )
                    )
                )
            if independent_shading and not unchanged:
                raise DirectMeshExportError(
                    f"Shape key {block.name!r} on {obj.name!r} has authored morph shading changed by its modifier stack. Export without modifiers or rebuild the shape's shading explicitly."
                )
            if unchanged and channels:
                normal_delta = channels.get("normal", normal_delta)
                tangent_delta = channels.get("tangent", tangent_delta)
            positions.append((block.name, position_delta))
            if block.name not in position_only:
                normals.append((block.name, normal_delta))
                tangents.append((block.name, tangent_delta))
    finally:
        obj.show_only_shape_key, obj.active_shape_key_index = (
            previous_only,
            previous_active,
        )
        depsgraph.update()
    return positions, normals, tangents


class _EvaluationTarget:
    """Temporary duplicate of an export object with armature deformation disabled"""

    def __init__(self, obj, apply_modifiers: bool):
        self.source = obj
        self.apply_modifiers = apply_modifiers and _has_applicable_modifiers(obj)
        self.object = None
        self.mesh = None
        self._owns_mesh = False
        self._collection = None
        self._copied_mesh = None

    def __enter__(self):
        source = self.source
        if not self.apply_modifiers:
            self.object = source
            self.mesh = source.data
            return self

        try:
            self.object = source.copy()
            self._copied_mesh = source.data.copy()
            self.object.data = self._copied_mesh
            self.object.animation_data_clear()
            keys = self.object.data.shape_keys
            if keys is not None:
                if keys == source.data.shape_keys:
                    raise DirectMeshExportError(
                        "Temporary evaluation did not isolate shape-key data."
                    )
                keys.animation_data_clear()
                for key in keys.key_blocks:
                    key.value = 0.0
                    key.mute = False
                self.object.show_only_shape_key = True
                self.object.active_shape_key_index = 0
            for modifier in tuple(self.object.modifiers):
                if not _exported_modifier(modifier):
                    self.object.modifiers.remove(modifier)
            self._collection = bpy.context.scene.collection
            self._collection.objects.link(self.object)

            depsgraph = bpy.context.evaluated_depsgraph_get()
            depsgraph.update()
            evaluated = self.object.evaluated_get(depsgraph)
            try:
                evaluated_mesh = evaluated.to_mesh(
                    preserve_all_data_layers=True, depsgraph=depsgraph
                )
                self.mesh = evaluated_mesh.copy()
                self._owns_mesh = True
            finally:
                evaluated.to_mesh_clear()
            self.depsgraph = depsgraph
            return self
        except BaseException:
            self._cleanup()
            raise

    def _cleanup(self):
        try:
            if self._owns_mesh and self.mesh is not None:
                bpy.data.meshes.remove(self.mesh)
        finally:
            self.mesh = None
            self._owns_mesh = False
            try:
                if self.object is not None and self.object is not self.source:
                    bpy.data.objects.remove(self.object, do_unlink=True)
            finally:
                self.object = None
                if self._copied_mesh is not None and self._copied_mesh.users == 0:
                    bpy.data.meshes.remove(self._copied_mesh)
                self._copied_mesh = None

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()
        return False


def _pack_influences(vertex_ids, joint_ids, weights, vertex_count, object_name=""):
    """Sort and normalize per-vertex influences into VEC4 JOINTS/WEIGHTS blocks"""
    if not len(vertex_ids):
        return None, None, 0

    vertex_ids = np.asarray(vertex_ids, dtype=np.int64)
    joint_ids = np.asarray(joint_ids, dtype=np.int64)
    weights = np.asarray(weights, dtype=np.float64)
    if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
        raise DirectMeshExportError("Skin weights must be finite and non-negative.")

    keep = weights > SKIN_WEIGHT_EPSILON
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
    if influence_width > MAX_SKIN_INFLUENCES:
        crowded = int(np.count_nonzero(run_lengths > MAX_SKIN_INFLUENCES))
        raise DirectMeshExportError(
            f"{object_name!r} has {crowded} vertices with more than {MAX_SKIN_INFLUENCES} bone influences "
            f"(the most is {influence_width}); direct export supports at most {MAX_SKIN_INFLUENCES}. Limit the "
            "weights, or enable Try Fix > Limit Bone Influences."
        )
    blocks = max(1, (influence_width + 3) // 4)
    width = blocks * 4

    packed_joints = np.zeros((vertex_count, width), dtype=np.int32)
    packed_weights = np.zeros((vertex_count, width), dtype=np.float64)
    packed_joints[vertex_ids, ranks] = joint_ids
    packed_weights[vertex_ids, ranks] = weights

    totals = packed_weights.sum(axis=1)
    scalable = totals > SKIN_WEIGHT_EPSILON
    packed_weights[scalable] /= normalization_divisors(totals[scalable])[:, np.newaxis]
    return packed_joints, packed_weights.astype(np.float32), blocks


def _vertex_group_influences(
    mesh, group_to_joint, dropped_groups, vertex_count, object_name
):
    """Collect deform weights from the mesh vertices for the mapped vertex groups"""
    if not group_to_joint and not dropped_groups:
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
            if not isfinite(weight) or weight < 0.0:
                raise DirectMeshExportError(
                    f"{object_name!r} contains an invalid weight at vertex {vertex_index}."
                )
            if weight <= SKIN_WEIGHT_EPSILON:
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
    return _pack_influences(vertex_ids, joint_ids, weights, vertex_count, object_name)


def _object_group_to_joint(obj, binding: SkeletonWriteBinding):
    """Map this object's vertex group indices onto skin joint indices by bone name"""
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
    """Depth-first ordering of deform bones, parents ahead of children"""
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
    """Read the source joint order the direct mesh importer stored on the armature"""
    raw = armature.get(MESH_SOURCE_REST_SNAPSHOT_KEY)
    if not raw:
        return ()
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError):
        _LOG.warning(
            "%s: source rest snapshot is unreadable; falling back to the deform bone hierarchy.",
            armature.name,
            exc_info=True,
        )
        return ()
    names = payload.get("boneNames") or ()
    return tuple(str(name) for name in names)


def _resolve_target_bone_name(armature, source_name):
    """Resolve a source joint name onto a bone in this armature"""
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
    """Build the joint list in source order, keyed to this armature's bones"""
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
        else _json_property(armature, MESH_SOURCE_REST_SNAPSHOT_KEY, None)
    )
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("version") != 2:
        raise DirectMeshExportError(
            "This mesh has an unsupported source-rest snapshot. Re-import it before export."
        )
    if snapshot.get("space") != SOURCE_REST_SPACE_CONTRACT:
        return None
    snapshot_names = tuple(str(name) for name in snapshot.get("boneNames", ()))
    if snapshot_names != tuple(source_names):
        return None

    count = len(source_names)
    try:
        relative = np.asarray(snapshot.get("matrices"), dtype=np.float64).reshape(
            count, 4, 4
        )
    except (TypeError, ValueError):
        return None
    if not np.all(np.isfinite(relative)):
        return None

    source_globals = local_matrices_to_model(relative, parent_indices, range(count))

    current_globals = np.asarray(
        [as_matrix_4x4(bone.matrix_local) for bone in bones],
        dtype=np.float64,
    )
    try:
        imported_targets = np.asarray(
            snapshot["targetMatrices"], dtype=np.float64
        ).reshape(count, 4, 4)
    except (KeyError, TypeError, ValueError) as error:
        raise DirectMeshExportError(
            "The mesh source-rest snapshot has no valid imported rest fingerprint. Re-import it before export."
        ) from error
    if not np.all(np.isfinite(imported_targets)):
        raise DirectMeshExportError(
            "The mesh source-rest fingerprint contains non-finite matrices. Re-import it before export."
        )
    if not np.allclose(current_globals, imported_targets, rtol=0.0, atol=1.0e-7):
        return None
    return source_globals


def build_mesh_skeleton_binding(
    armature,
    source_skin_extras=None,
    source_skin_binding=None,
    source_rest_snapshot=None,
) -> SkeletonWriteBinding:
    """Rebuild the glTF skin from an armature's rest pose"""
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
            [as_matrix_4x4(bone.matrix_local) for bone in bones],
            dtype=np.float64,
        )
    )
    globals_gltf = blender_relative_to_gltf(globals_blender, is_root=True)

    try:
        inverse_bind = np.linalg.inv(globals_gltf)
    except np.linalg.LinAlgError as error:
        raise DirectMeshExportError(
            f"Armature {armature.name!r} has a singular bone rest matrix."
        ) from error

    node_local = globals_gltf.copy()
    parents = np.asarray(parent_indices, dtype=np.intp)
    children = np.flatnonzero(parents >= 0)
    node_local[children] = inverse_bind[parents[children]] @ globals_gltf[children]

    return SkeletonWriteBinding(
        bone_names=bone_names,
        parent_indices=parent_indices,
        node_local_gltf=node_local,
        inverse_bind_gltf=inverse_bind,
        group_to_joint=dict(group_to_joint),
        rig_path=str(armature.get("rigPath", "") or ""),
        skin_extras=copy.deepcopy(source_skin_extras),
    )


def _source_property_owner(idblock, key):
    if idblock is None:
        return None
    try:
        if key in idblock:
            return idblock
        for collection in getattr(idblock, "users_collection", ()):
            if key in collection:
                return collection
        source_name = str(idblock.get("cp77_master_source_object", "") or "")
        collection_name = str(idblock.get("cp77_master_source_collection", "") or "")
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_source_property_owner 1", type(error).__name__),
            "source property owner: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    if not source_name:
        return None
    source = None
    if collection_name:
        collection = bpy.data.collections.get(collection_name)
        if collection is not None:
            source = collection.objects.get(source_name)
    if source is None:
        source = bpy.data.objects.get(source_name)
    if source is None or source is idblock:
        return None
    try:
        return source if key in source else None
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_source_property_owner 2", type(error).__name__),
            "source property owner: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def _source_property(idblock, key, default=None):
    owner = _source_property_owner(idblock, key)
    if owner is None:
        return default
    try:
        return owner[key]
    except (KeyError, ReferenceError, RuntimeError, TypeError):
        return default


def _json_property(idblock, key, default=None):
    value = _source_property(idblock, key, None)
    if value is None:
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _point_vector_attribute(mesh, name):
    attribute = mesh.attributes.get(name)
    if (
        attribute is None
        or attribute.domain != "POINT"
        or attribute.data_type != "FLOAT_VECTOR"
    ):
        return None
    values = np.empty((len(attribute.data), 3), dtype=np.float32)
    attribute.data.foreach_get("vector", values.reshape(-1))
    return values


def _point_float_attribute(mesh, name):
    attribute = mesh.attributes.get(name)
    if (
        attribute is None
        or attribute.domain != "POINT"
        or attribute.data_type != "FLOAT"
    ):
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
    encode_wolvenkit_uvs: bool = True,
    bake_transform: bool = True,
    export_garment_morph: bool = True,
    export_garment_attributes: bool = True,
    ensure_garment_attributes: bool = False,
) -> ExportSubmesh:
    """Expand one Blender mesh object into per-vertex glTF attribute blocks"""
    if obj.type != "MESH":
        raise DirectMeshExportError(f"{obj.name!r} is not a mesh object.")

    _validate_shape_key_contract(
        obj, apply_modifiers, export_garment_morph=export_garment_morph
    )
    with _EvaluationTarget(obj, apply_modifiers) as target:
        mesh = target.mesh
        if not len(mesh.polygons):
            raise DirectMeshExportError(f"Mesh {obj.name!r} contains no faces.")
        material_indices = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", material_indices)
        if np.any(material_indices != material_indices[0]):
            raise DirectMeshExportError(
                f"{obj.name!r} uses multiple material regions; separate them into individual submesh objects before exporting."
            )

        loop_vertices = _loop_vertex_indices(mesh)
        triangles_loops = _triangle_loops(mesh)
        uv_layers = _uv_loop_layers(mesh)
        tangent_uv_name = next(
            (name for channel_index, name, _ in uv_layers if channel_index == 0),
            None,
        )
        standard_colors, custom_colors = _split_color_attributes(mesh, obj.name)

        source_geometry_signature = str(mesh.get(SOURCE_GEOMETRY_SIGNATURE_KEY, ""))
        source_frame_signature = str(mesh.get(SOURCE_TANGENT_FRAME_SIGNATURE_KEY, ""))
        current_geometry_signature, current_frame_signature = (
            geometry_and_tangent_frame_signatures(mesh, uv_name=tangent_uv_name or "")
        )
        source_shading = str(mesh.get(SOURCE_SHADING_SIGNATURE_KEY, ""))
        shading_valid = bool(
            source_shading and source_shading == shading_signature(mesh)
        )
        source_geometry_valid = bool(
            shading_valid
            and source_geometry_signature
            and current_geometry_signature == source_geometry_signature
        )
        source_normals = (
            _point_vector_attribute(mesh, SOURCE_NORMAL_ATTRIBUTE)
            if source_geometry_valid
            else None
        )
        if (
            source_geometry_valid
            and source_normals is not None
            and len(source_normals) == len(mesh.vertices)
        ):
            normals = source_normals
            normals_per_vertex = True
        else:
            normals, normals_per_vertex = _mesh_normals(mesh)

        source_frame_valid = bool(
            source_geometry_valid
            and source_frame_signature
            and current_frame_signature == source_frame_signature
        )
        _LOG.debug(
            "Mesh export frame %s: source_normals=%s source_tangents=%s shading_snapshot=%s",
            obj.name,
            source_geometry_valid,
            source_frame_valid,
            bool(source_shading),
        )
        source_tangents = (
            _point_vector_attribute(mesh, SOURCE_TANGENT_ATTRIBUTE)
            if source_frame_valid
            else None
        )
        source_tangent_signs = (
            _point_float_attribute(mesh, SOURCE_TANGENT_SIGN_ATTRIBUTE)
            if source_frame_valid
            else None
        )
        if (
            source_frame_valid
            and source_tangents is not None
            and source_tangent_signs is not None
            and len(source_tangents) == len(mesh.vertices)
            and len(source_tangent_signs) == len(mesh.vertices)
        ):
            tangents = np.ascontiguousarray(source_tangents[loop_vertices])
            tangent_signs = np.ascontiguousarray(source_tangent_signs[loop_vertices])
        else:
            tangents, tangent_signs = _corner_tangents(mesh, tangent_uv_name)

        color_loops = [
            (channel, _color_loop_values(attribute, loop_vertices))
            for channel, attribute in standard_colors
        ]
        custom_color_loops = [
            (
                canonical_garment_attribute(attribute.name),
                _color_loop_values(attribute, loop_vertices),
            )
            for attribute in custom_colors
            if export_garment_attributes or not is_garment_attribute(attribute.name)
        ]

        if ensure_garment_attributes and export_garment_attributes:
            present = {name for name, _ in custom_color_loops}
            # A set red channel marks a cap vertex, so missing data means no caps and no weight.
            for name, default in (
                (GARMENT_CAP_ATTRIBUTE, (0.0, 0.0, 0.0, 1.0)),
                (GARMENT_WEIGHT_ATTRIBUTE, (0.0, 0.0, 0.0, 1.0)),
            ):
                if name not in present:
                    values = np.empty((len(mesh.loops), 4), dtype=np.float32)
                    values[:] = default
                    custom_color_loops.append((name, values))

        vertex_positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", vertex_positions)
        vertex_positions = vertex_positions.reshape(-1, 3)

        if target.apply_modifiers:
            morph_targets, morph_normals, morph_tangents = (
                _morph_deltas_through_modifiers(
                    target.object,
                    target.depsgraph,
                    vertex_positions,
                    mesh,
                    tangent_uv_name,
                    export_garment_morph=export_garment_morph,
                )
            )
        else:
            morph_targets = _morph_deltas_from_shape_keys(
                obj,
                vertex_positions.shape[0],
                export_garment_morph=export_garment_morph,
            )
            preserved = (
                source_morph_shading(obj, loop_vertices)
                if morph_targets and source_frame_valid
                else {}
            )
            morph_normals, morph_tangents = [], []
            if morph_targets:
                position_only = _position_only_morphs(obj)
                try:
                    morph_normals, morph_tangents = morph_shading_from_mesh(
                        mesh,
                        [
                            target
                            for target in morph_targets
                            if target[0] not in position_only
                        ],
                        tangent_uv_name,
                        preserved=preserved,
                    )
                except ValueError as error:
                    raise DirectMeshExportError(str(error)) from error
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
        identities = source_vertex_indices(mesh, current_geometry_signature)
        corner_vertices = loop_vertices[flat_loops]
        key_columns = [
            corner_vertices if identities is None else identities[corner_vertices]
        ]
        if identities is not None:
            key_columns.append(float32_bit_keys(vertex_positions[corner_vertices]))
            if normals is not None and normals_per_vertex:
                key_columns.append(float32_bit_keys(normals[corner_vertices]))
            if joint_blocks is not None:
                key_columns.append(joint_blocks[corner_vertices])
                key_columns.append(float32_bit_keys(weight_blocks[corner_vertices]))
            for _, values in morph_targets:
                key_columns.append(float32_bit_keys(values[corner_vertices]))
        if normals is not None and not normals_per_vertex:
            key_columns.append(float32_bit_keys(normals[flat_loops]))
        if tangents is not None:
            key_columns.append(float32_bit_keys(tangents[flat_loops]))
            key_columns.append(float32_bit_keys(tangent_signs[flat_loops]))
        for _, _, uv in uv_layers:
            key_columns.append(float32_bit_keys(uv[flat_loops]))
        for _, color in color_loops:
            key_columns.append(float32_bit_keys(color[flat_loops]))
        for _, color in custom_color_loops:
            key_columns.append(float32_bit_keys(color[flat_loops]))

        for _, values in (*morph_normals, *morph_tangents):
            key_columns.append(float32_bit_keys(values[flat_loops]))
        representative, inverse = stable_unique_integer_rows(key_columns)
        # Vertices go out in source vertex order (the splits of one vertex together, in first-use order): files
        # beside the mesh, such as its .morphtarget, address its vertices by index.
        order = np.lexsort((representative, key_columns[0][representative]))
        rank = np.empty_like(order)
        rank[order] = np.arange(order.shape[0])
        representative, inverse = representative[order], rank[inverse]
        if representative.shape[0] > VERT_LIMIT:
            raise DirectMeshExportError(
                f"{obj.name!r} expands to {representative.shape[0]} vertices after "
                f"attribute splitting, above the {VERT_LIMIT} submesh limit. "
                "Split the submesh or reduce UV, normal, tangent or colour seams."
            )
        source_loops = flat_loops[representative]
        source_vertices = loop_vertices[source_loops]
        triangles = inverse.reshape(-1, 3).astype(np.int32)

        positions = np.ascontiguousarray(vertex_positions[source_vertices])
        if normals is None:
            split_normals = None
        else:
            split_normals = np.ascontiguousarray(
                normals[source_vertices]
                if normals_per_vertex
                else normals[source_loops]
            )
        split_tangents = None
        if tangents is not None:
            split_tangents = np.empty((source_loops.shape[0], 4), dtype=np.float32)
            split_tangents[:, :3] = tangents[source_loops]
            split_tangents[:, 3] = tangent_signs[source_loops]

        split_uvs = []
        for channel_index, _, uv in uv_layers:
            values = np.array(uv[source_loops], dtype=np.float32, order="C", copy=True)
            if encode_wolvenkit_uvs:
                values = convert_wolvenkit_uv_channel(values, channel_index, copy=False)
            split_uvs.append((channel_index, values))
        split_colors = [
            (channel, np.ascontiguousarray(color[source_loops]))
            for channel, color in color_loops
        ]
        split_custom_colors = [
            (name, np.ascontiguousarray(color[source_loops]))
            for name, color in custom_color_loops
        ]
        split_morph_normals = [
            (name, np.ascontiguousarray(delta[source_loops]))
            for name, delta in morph_normals
        ]
        split_morph_tangents = [
            (name, np.ascontiguousarray(delta[source_loops]))
            for name, delta in morph_tangents
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
            relative = as_matrix_4x4(
                armature.matrix_world.inverted() @ obj.matrix_world
            )
        node_matrix_gltf = np.eye(4, dtype=np.float64)
    else:
        relative = as_matrix_4x4(obj.matrix_world)
        node_matrix_gltf = (
            np.eye(4, dtype=np.float64)
            if bake_transform
            else red_matrix_to_gltf(relative)
        )

    if (skinned or bake_transform) and not matrix_is_identity(
        relative, tolerance=_IDENTITY_TOLERANCE
    ):
        if np.linalg.det(relative[:3, :3]) < 0.0:
            triangles = np.ascontiguousarray(triangles[:, (0, 2, 1)])
        if split_morphs:
            try:
                split_morph_normals = transform_normalized_direction_deltas(
                    split_normals,
                    split_morph_normals,
                    np.linalg.inv(relative[:3, :3]).T,
                )
                split_morph_tangents = transform_normalized_direction_deltas(
                    split_tangents[:, :3],
                    split_morph_tangents,
                    relative[:3, :3],
                )
            except (ValueError, np.linalg.LinAlgError) as error:
                raise DirectMeshExportError(
                    f"Cannot transform morph shading: {error}"
                ) from error
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
        tangents=_rotate_tangents(
            split_tangents,
            encode_wolvenkit_space=encode_wolvenkit_uvs,
        ),
        node_matrix_gltf=node_matrix_gltf,
        uv_layers=split_uvs,
        color_layers=split_colors,
        custom_colors=split_custom_colors,
        joint_indices=split_joints,
        joint_weights=split_weights,
        morph_targets=[(name, _rotate_to_gltf(delta)) for name, delta in split_morphs],
        morph_normals=[
            (name, _rotate_to_gltf(delta)) for name, delta in split_morph_normals
        ],
        morph_tangents=[
            (name, _rotate_to_gltf(delta)) for name, delta in split_morph_tangents
        ],
        material_names=export_material_names(obj),
        skinned=skinned,
    )


def _rotate_tangents(tangents, *, encode_wolvenkit_space: bool):
    if tangents is None:
        return None
    result = np.empty_like(tangents)
    result[:, :3] = red_vectors_to_gltf(np.asarray(tangents[:, :3], dtype=np.float32))
    result[:, 3] = (
        convert_wolvenkit_tangent_sign(tangents[:, 3])
        if encode_wolvenkit_space
        else tangents[:, 3]
    )
    return np.ascontiguousarray(result)


def _bake_transform(matrix, positions, normals, tangents, morphs):
    """Fold a residual object transform into geometry for identity-node skinned meshes"""
    linear = matrix[:3, :3]
    translation = matrix[:3, 3]
    if not np.all(np.isfinite(matrix)):
        raise DirectMeshExportError("Cannot bake a non-finite object transform.")
    try:
        normal_matrix = np.linalg.inv(linear).T
    except np.linalg.LinAlgError as error:
        raise DirectMeshExportError(
            "Cannot bake a singular object transform."
        ) from error
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


def _write_primitive(builder: GLBBuilder, submesh: ExportSubmesh) -> dict:
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
    for channel_index, uv in submesh.uv_layers[: len(UV_ATTRIBUTES)]:
        attributes[UV_ATTRIBUTES[channel_index]] = builder.add_float_accessor(
            uv,
            "VEC2",
            name=f"{submesh.name}/{UV_ATTRIBUTES[channel_index]}",
            target=_ARRAY_BUFFER,
            include_bounds=False,
        )
    for index, color in submesh.color_layers:
        attributes[COLOR_ATTRIBUTES[index]] = builder.add_float_accessor(
            color,
            "VEC4",
            name=f"{submesh.name}/{COLOR_ATTRIBUTES[index]}",
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
            attributes[JOINT_ATTRIBUTES[block]] = builder.add_integer_accessor(
                submesh.joint_indices[:, span],
                "VEC4",
                5123,
                name=f"{submesh.name}/{JOINT_ATTRIBUTES[block]}",
                target=_ARRAY_BUFFER,
                include_bounds=True,
            )
            attributes[WEIGHT_ATTRIBUTES[block]] = builder.add_float_accessor(
                submesh.joint_weights[:, span],
                "VEC4",
                name=f"{submesh.name}/{WEIGHT_ATTRIBUTES[block]}",
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
    if submesh.morph_targets:
        normal_map, tangent_map = (
            dict(submesh.morph_normals),
            dict(submesh.morph_tangents),
        )
        targets = []
        for name, delta in submesh.morph_targets:
            # A GarmentSupport imported as positions only goes back the same way; every other morph carries shading.
            positions_only = (
                name == GARMENT_SUPPORT_MORPH
                and name not in normal_map
                and name not in tangent_map
            )
            if not positions_only and (
                name not in normal_map or name not in tangent_map
            ):
                raise DirectMeshExportError(
                    f"Morph {name!r} is missing normal or tangent deltas."
                )
            channels = (
                (("POSITION", delta),)
                if positions_only
                else (
                    ("POSITION", delta),
                    ("NORMAL", normal_map[name]),
                    ("TANGENT", tangent_map[name]),
                )
            )
            targets.append(
                {
                    semantic: builder.add_float_accessor(
                        values,
                        "VEC3",
                        name=f"{submesh.name}/{name}/{semantic}",
                        target=_ARRAY_BUFFER,
                        include_bounds=semantic == "POSITION",
                    )
                    for semantic, values in channels
                }
            )
        primitive["targets"] = targets
    return primitive


def _shared_json_property(objects, key, default=None):
    resolved = []
    for obj in objects:
        if _source_property_owner(obj, key) is None:
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
    encode_wolvenkit_uvs: bool = True,
    bake_transforms: bool = True,
    export_garment_morph: bool = True,
    export_garment_attributes: bool = True,
    ensure_garment_attributes: bool = False,
):
    """Assemble the glTF document and BIN payload for a set of submesh objects"""
    mesh_objects = ordered_submesh_objects(obj for obj in objects if obj.type == "MESH")
    if not mesh_objects:
        raise DirectMeshExportError("No mesh objects were supplied for export.")

    seen_submesh_indices = {}
    for obj in mesh_objects:
        submesh_index = submesh_index_for_object(obj, None)
        if submesh_index is None:
            continue
        previous = seen_submesh_indices.get(submesh_index)
        if previous is not None and previous.data == obj.data:
            raise DirectMeshExportError(
                f"{previous.name!r} and {obj.name!r} share submesh {submesh_index}. Export one appearance at a time or export its collections separately."
            )
        if previous is not None:
            _LOG.warning(
                "Submesh index %d is shared by %r and %r; "
                "preserving their stable relative order.",
                submesh_index,
                previous.name,
                obj.name,
            )
        else:
            seen_submesh_indices[submesh_index] = obj

    armatures = {
        found.name: found
        for found in (_armature_of(obj) for obj in mesh_objects)
        if found is not None and is_skinned
    }
    if armature is not None:
        armatures.setdefault(armature.name, armature)
    if len(armatures) > 1:
        raise DirectMeshExportError(
            "Direct mesh export requires a single armature; found "
            + ", ".join(sorted(armatures))
        )
    resolved_armature = armature or (
        next(iter(armatures.values())) if armatures else None
    )
    if not is_skinned:
        resolved_armature = None
    source_skin_extras = (
        _shared_json_property(
            mesh_objects,
            SOURCE_SKIN_EXTRAS_KEY,
            None,
        )
        if resolved_armature is not None
        else None
    )
    source_skin_binding = (
        _shared_json_property(
            mesh_objects,
            SOURCE_SKIN_BINDING_KEY,
            None,
        )
        if resolved_armature is not None
        else None
    )
    source_rest_snapshot = (
        _shared_json_property(
            mesh_objects,
            MESH_SOURCE_REST_SNAPSHOT_KEY,
            None,
        )
        if resolved_armature is not None
        else None
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
            encode_wolvenkit_uvs=encode_wolvenkit_uvs,
            bake_transform=bake_transforms,
            export_garment_morph=export_garment_morph,
            export_garment_attributes=export_garment_attributes,
            ensure_garment_attributes=ensure_garment_attributes,
        )
        for obj in mesh_objects
    ]
    if binding is not None:
        for submesh in submeshes:
            if not submesh.skinned:
                _LOG.warning(
                    "%r has no vertex weights; exported as a static submesh without a skin.",
                    submesh.name,
                )
    return assemble_mesh_document(submeshes, binding)


def assemble_mesh_document(
    submeshes,
    binding: SkeletonWriteBinding | None,
):
    """Serialize expanded submeshes and an optional skin into a glTF document"""
    builder = GLBBuilder(error_type=DirectMeshExportError)
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

        nodes.append(
            {"name": "Armature", "children": [index + 1 for index in root_indices]}
        )
        joint_offset = 1
        transforms = node_transforms(binding.node_local_gltf)
        for index, bone_name in enumerate(binding.bone_names):
            node = {"name": bone_name}
            node.update(transforms[index])
            if child_lists[index]:
                node["children"] = [
                    child + joint_offset for child in child_lists[index]
                ]
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
        skin_extras = skin_extras_for_export(skin_extras)
        skin = {
            "name": "Armature",
            "inverseBindMatrices": inverse_bind_accessor,
            "joints": [
                index + joint_offset for index in range(len(binding.bone_names))
            ],
            "extras": skin_extras,
        }

    meshes = []
    expected_morph_names = None
    for submesh in submeshes:
        names = tuple(
            name for name, _ in submesh.morph_targets if name != GARMENT_SUPPORT_MORPH
        )
        if expected_morph_names is None:
            expected_morph_names = names
        elif names != expected_morph_names:
            raise DirectMeshExportError(
                "All submeshes must have the same morph target names and order, excluding GarmentSupport; add zero-valued keys where a target does not move a submesh."
            )
    scene_nodes = [0] if binding is not None else []
    transforms = node_transforms(
        np.asarray([submesh.node_matrix_gltf for submesh in submeshes])
    )
    for submesh, transform in zip(submeshes, transforms):
        mesh_extras = {}
        if submesh.material_names:
            mesh_extras["materialNames"] = list(submesh.material_names)
        if submesh.morph_targets:
            mesh_extras["targetNames"] = [name for name, _ in submesh.morph_targets]

        mesh_document = {
            "name": submesh.name,
            "primitives": [_write_primitive(builder, submesh)],
        }
        if mesh_extras:
            mesh_document["extras"] = mesh_extras
        if submesh.morph_targets:
            mesh_document["weights"] = [0.0] * len(submesh.morph_targets)

        node = {"name": submesh.name, "mesh": len(meshes)}
        node.update(transform)
        if submesh.skinned and skin is not None:
            node["skin"] = 0
        meshes.append(mesh_document)
        scene_nodes.append(len(nodes))
        nodes.append(node)

    scene = {"nodes": scene_nodes}
    document = {
        "asset": {
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
