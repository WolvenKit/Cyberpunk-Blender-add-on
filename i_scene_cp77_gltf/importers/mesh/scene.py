from __future__ import annotations

import json
import os
from contextlib import nullcontext

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

from ...animation.domain.rig.naming import merged_bone_name
from ...assetio.paths import absolute_local_path_key
from ...assetio.values import json_text
from ...bartmoss.geometry import float32_direction_length
from ...bartmoss.hierarchy import model_matrices_to_local
from ...bartmoss.weights import normalization_divisors
from ...blender.custom_normals import set_custom_normals_from_vertices
from ...blender.mesh import (
    MESH_SOURCE_REST_SNAPSHOT_KEY,
    SOURCE_FRAME_VALID_ATTRIBUTE,
    SOURCE_GEOMETRY_SIGNATURE_KEY,
    SOURCE_MESH_EXTRAS_KEY,
    SOURCE_NORMAL_ATTRIBUTE,
    SOURCE_SHADING_SIGNATURE_KEY,
    SOURCE_SKIN_BINDING_KEY,
    SOURCE_SKIN_EXTRAS_KEY,
    SOURCE_TANGENT_ATTRIBUTE,
    SOURCE_TANGENT_FRAME_SIGNATURE_KEY,
    SOURCE_TANGENT_SIGN_ATTRIBUTE,
    TANGENT_SIGN_ATTRIBUTE,
    TANGENT_SIGN_VALID_ATTRIBUTE,
    geometry_and_tangent_frame_signatures,
    shading_signature,
    store_source_vertex_indices,
)
from ...blender.mesh_validation import _loop_vertex_indices
from ...blender.morphs import store_source_morph_shading
from ...blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    raise_if_rollback_incomplete,
    restore_id_properties,
    snapshot_id_properties,
    track_created_datablock,
)
from ...core.log import get_logger, is_enabled, log_once
from ...gltf.provenance import ORIGIN_PLUGIN, mark_origin
from ...gltf.submesh import submesh_index_from_name
from ...redSpace.contracts import SOURCE_REST_SPACE_CONTRACT
from ...redSpace.transforms import gltf_relative_to_blender
from ..rig.gltf import build_rest_armature_from_binding
from .document import (
    BIND_MATRIX_TOLERANCE,
    DirectMeshData,
    DirectMeshImportError,
    SkinningAudit,
    Submesh,
    decode_mesh_glb,
)

_LOG = get_logger(__name__)

# Residuals up to this bound with no short or non-rigid joint are float32 roll
# quantization of otherwise exact edit bones and are reported at debug level.
_BIND_ROLL_QUANTIZATION_LIMIT = 2.0 * BIND_MATRIX_TOLERANCE
_BIND_MATRIX_HARD_LIMIT = 1.0e-2
_WEIGHT_EPSILON = 1.0e-8
_SOURCE_FRAME_VERSION_KEY = "cp77_source_frame_version"
_SOURCE_FRAME_VERSION = 3
_SOURCE_NODE_EXTRAS_KEY = "cp77_direct_node_extras"
_SOURCE_DOCUMENT_METADATA_KEY = "cp77_direct_document_metadata"
_SOURCE_SCENE_METADATA_KEY = "cp77_direct_scene_metadata"
_METALBASE_VERTEX_RM_ATTRIBUTE = "cp77_metalbase_vertex_rm"


def _build_mesh_geometry(
    submesh: Submesh,
    *,
    validate_geometry: bool = True,
    calculate_edges: bool = True,
):
    mesh = track_created_datablock("meshes", bpy.data.meshes.new(submesh.name))
    positions = np.ascontiguousarray(submesh.positions, dtype=np.float32)
    triangles = np.ascontiguousarray(submesh.triangles, dtype=np.int32)
    vertex_count = positions.shape[0]
    triangle_count = triangles.shape[0]
    loop_count = triangle_count * 3

    mesh.vertices.add(vertex_count)
    mesh.vertices.foreach_set("co", positions.reshape(-1))
    mesh.loops.add(loop_count)
    mesh.loops.foreach_set("vertex_index", triangles.reshape(-1))
    mesh.polygons.add(triangle_count)
    mesh.polygons.foreach_set(
        "loop_start",
        np.arange(0, loop_count, 3, dtype=np.int32),
    )
    mesh.polygons.foreach_set(
        "loop_total",
        np.full(triangle_count, 3, dtype=np.int32),
    )

    mesh.update(calc_edges=calculate_edges)
    geometry_changed = False
    if validate_geometry:
        geometry_changed = bool(mesh.validate(verbose=False))
        if geometry_changed:
            mesh.update(calc_edges=calculate_edges)
        if len(mesh.vertices) != vertex_count:
            bpy.data.meshes.remove(mesh)
            raise DirectMeshImportError(
                f"Mesh {submesh.name!r} validation changed its vertex count; "
                "decoded vertex attributes can no longer be mapped safely."
            )

    loop_vertices = (
        _loop_vertex_indices(mesh)
        if geometry_changed or len(mesh.loops) != loop_count
        else triangles.reshape(-1)
    )
    return mesh, loop_vertices


def _apply_uv_layers(mesh, submesh, loop_vertices):
    if not submesh.uv_layers:
        return
    loop_uv = np.empty((len(loop_vertices), 2), dtype=np.float32)
    for channel_index, uv in submesh.uv_layers:
        np.take(uv, loop_vertices, axis=0, out=loop_uv)
        layer = mesh.uv_layers.new(
            name=f"UVMap_{channel_index}" if channel_index else "UVMap"
        )
        layer.uv.foreach_set("vector", loop_uv.reshape(-1))


def _apply_color_layers(mesh, submesh):
    for layer_index, color in submesh.color_layers:
        color = np.ascontiguousarray(color, dtype=np.float32)
        attribute = mesh.color_attributes.new(
            name="Color" if layer_index == 0 else f"Color_{layer_index}",
            type="FLOAT_COLOR",
            domain="POINT",
        )
        attribute.data.foreach_set("color", color.reshape(-1))
    for name, color in submesh.custom_colors:
        color = np.ascontiguousarray(color, dtype=np.float32)
        attribute = mesh.color_attributes.get(name)
        if attribute is None:
            attribute = mesh.color_attributes.new(
                name=name,
                type="FLOAT_COLOR",
                domain="POINT",
            )
        if attribute.domain != "POINT" or len(attribute.data) != len(color):
            raise DirectMeshImportError(
                f"Custom color attribute {name!r} does not match the imported vertex domain."
            )
        attribute.data.foreach_set("color", color.reshape(-1))


def ensure_metalbase_vertex_rm_attribute(mesh):
    source = mesh.color_attributes.get("Color")
    if (
        source is None
        or source.domain != "POINT"
        or len(source.data) != len(mesh.vertices)
    ):
        return False

    existing = mesh.attributes.get(_METALBASE_VERTEX_RM_ATTRIBUTE)
    if (
        existing is not None
        and existing.domain == "POINT"
        and existing.data_type == "FLOAT_VECTOR"
        and len(existing.data) == len(mesh.vertices)
    ):
        return True
    if existing is not None:
        mesh.attributes.remove(existing)

    values = np.empty(len(source.data) * 4, dtype=np.float32)
    field = "color_srgb" if source.data_type == "BYTE_COLOR" else "color"
    source.data.foreach_get(field, values)
    alpha = values.reshape(-1, 4)[:, 3]
    packed = np.clip(np.trunc(alpha * np.float32(255.0)), 0.0, 255.0).astype(np.uint32)
    decoded = np.empty((len(alpha), 3), dtype=np.float32)
    decoded[:, 0] = (packed & np.uint32(15)).astype(np.float32) / np.float32(15.0)
    decoded[:, 1] = (np.uint32(15) - (packed >> np.uint32(4))).astype(
        np.float32
    ) / np.float32(15.0)
    decoded[:, 2] = 1.0

    attribute = mesh.attributes.new(
        name=_METALBASE_VERTEX_RM_ATTRIBUTE,
        type="FLOAT_VECTOR",
        domain="POINT",
    )
    attribute.data.foreach_set("vector", decoded.reshape(-1))
    return True


def _apply_custom_normals(mesh, submesh):
    if submesh.normals is None:
        return
    polygon_count = len(mesh.polygons)
    if polygon_count:
        mesh.polygons.foreach_set(
            "use_smooth",
            np.ones(polygon_count, dtype=np.bool_),
        )
    set_custom_normals_from_vertices(
        mesh,
        submesh.normals,
        label=f"direct mesh {submesh.name!r}",
    )


def _source_frame_attribute(mesh, name, data_type):
    attribute = mesh.attributes.get(name)
    if attribute is not None and (
        getattr(attribute, "domain", None) != "POINT"
        or getattr(attribute, "data_type", None) != data_type
    ):
        mesh.attributes.remove(attribute)
        attribute = None
    if attribute is None:
        attribute = mesh.attributes.new(
            name=name,
            type=data_type,
            domain="POINT",
        )
    return attribute


def _source_frame_attribute_available(mesh, name, data_type):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        return False
    attribute = attributes.get(name)
    return (
        attribute is not None
        and getattr(attribute, "domain", None) == "POINT"
        and getattr(attribute, "data_type", None) == data_type
        and len(attribute.data) == len(mesh.vertices)
    )


def source_frame_attributes_available(mesh):
    if int(mesh.get(_SOURCE_FRAME_VERSION_KEY, 0) or 0) != _SOURCE_FRAME_VERSION:
        return False
    return all(
        (
            _source_frame_attribute_available(
                mesh, SOURCE_NORMAL_ATTRIBUTE, "FLOAT_VECTOR"
            ),
            _source_frame_attribute_available(
                mesh, SOURCE_TANGENT_ATTRIBUTE, "FLOAT_VECTOR"
            ),
            _source_frame_attribute_available(
                mesh, SOURCE_TANGENT_SIGN_ATTRIBUTE, "FLOAT"
            ),
            _source_frame_attribute_available(
                mesh, SOURCE_FRAME_VALID_ATTRIBUTE, "FLOAT"
            ),
        )
    )


def ensure_source_frame_attributes(mesh, submesh):
    mesh[SOURCE_SHADING_SIGNATURE_KEY] = shading_signature(mesh)
    normals = submesh.normals
    tangents = submesh.tangents
    normal_ready = normals is not None and len(normals) == len(mesh.vertices)
    tangent_ready = tangents is not None and len(tangents) == len(mesh.vertices)
    frame_ready = normal_ready and tangent_ready

    attributes = getattr(mesh, "attributes", None)
    if attributes is not None:
        frame_valid = attributes.get(SOURCE_FRAME_VALID_ATTRIBUTE)
        if frame_valid is not None:
            attributes.remove(frame_valid)

    if not normal_ready and SOURCE_GEOMETRY_SIGNATURE_KEY in mesh:
        del mesh[SOURCE_GEOMETRY_SIGNATURE_KEY]
    if not tangent_ready and SOURCE_TANGENT_FRAME_SIGNATURE_KEY in mesh:
        del mesh[SOURCE_TANGENT_FRAME_SIGNATURE_KEY]

    geometry_signature = ""
    tangent_signature = ""
    if normal_ready or tangent_ready:
        geometry_signature, tangent_signature = geometry_and_tangent_frame_signatures(
            mesh
        )

    if normal_ready:
        normal = _source_frame_attribute(
            mesh,
            SOURCE_NORMAL_ATTRIBUTE,
            "FLOAT_VECTOR",
        )
        normal.data.foreach_set(
            "vector",
            np.ascontiguousarray(normals, dtype=np.float32).reshape(-1),
        )
        if geometry_signature:
            mesh[SOURCE_GEOMETRY_SIGNATURE_KEY] = geometry_signature

    if tangent_ready:
        tangent = _source_frame_attribute(
            mesh,
            SOURCE_TANGENT_ATTRIBUTE,
            "FLOAT_VECTOR",
        )
        tangent.data.foreach_set(
            "vector",
            np.ascontiguousarray(tangents[:, :3], dtype=np.float32).reshape(-1),
        )
        source_sign = np.ascontiguousarray(tangents[:, 3], dtype=np.float32)
        shading_sign_values = source_sign
        sign = _source_frame_attribute(
            mesh,
            SOURCE_TANGENT_SIGN_ATTRIBUTE,
            "FLOAT",
        )
        sign.data.foreach_set("value", source_sign)
        shading_sign = _source_frame_attribute(
            mesh,
            TANGENT_SIGN_ATTRIBUTE,
            "FLOAT",
        )
        shading_sign.data.foreach_set("value", shading_sign_values)
        shading_valid = _source_frame_attribute(
            mesh,
            TANGENT_SIGN_VALID_ATTRIBUTE,
            "FLOAT",
        )
        shading_valid.data.foreach_set(
            "value",
            np.ones(len(tangents), dtype=np.float32),
        )
        if tangent_signature:
            mesh[SOURCE_TANGENT_FRAME_SIGNATURE_KEY] = tangent_signature

    if frame_ready:
        mesh[_SOURCE_FRAME_VERSION_KEY] = _SOURCE_FRAME_VERSION
        frame_valid = _source_frame_attribute(
            mesh,
            SOURCE_FRAME_VALID_ATTRIBUTE,
            "FLOAT",
        )
        frame_valid.data.foreach_set(
            "value",
            np.ones(len(mesh.vertices), dtype=np.float32),
        )

    if not frame_ready and _SOURCE_FRAME_VERSION_KEY in mesh:
        del mesh[_SOURCE_FRAME_VERSION_KEY]

    return frame_ready


def _resolve_target_bone_name(armature, source_name):
    if armature is None:
        return None
    pose_bones = armature.pose.bones
    if pose_bones.get(source_name) is not None:
        return source_name
    mapped = merged_bone_name(source_name)
    return mapped if pose_bones.get(mapped) is not None else None


def _aggregate_deform_weights(joints, weights, source_to_group):
    joints = np.asarray(joints, dtype=np.int32)
    weights = np.asarray(weights, dtype=np.float32)
    source_to_group = np.asarray(source_to_group, dtype=np.int32)
    if joints.shape != weights.shape:
        raise DirectMeshImportError(
            f"Joint and weight arrays have different shapes: {joints.shape} != {weights.shape}."
        )

    finite = np.isfinite(weights)
    positive = finite & (weights > _WEIGHT_EPSILON)
    invalid_weight_count = int(
        np.count_nonzero((~finite) | (weights < -_WEIGHT_EPSILON))
    )
    in_range = (joints >= 0) & (joints < len(source_to_group))
    valid_source = positive & in_range
    invalid_influence_count = invalid_weight_count + int(
        np.count_nonzero(positive & ~in_range)
    )

    mapped = np.full(joints.shape, -1, dtype=np.int32)
    mapped[valid_source] = source_to_group[joints[valid_source]]
    unmapped = valid_source & (mapped < 0)
    usable = valid_source & (mapped >= 0)
    if not np.any(usable):
        audit = SkinningAudit(
            invalid_influence_count=invalid_influence_count,
            unmapped_influence_count=int(np.count_nonzero(unmapped)),
            zero_weight_vertex_count=int(joints.shape[0]),
        )
        empty_i = np.empty(0, dtype=np.int32)
        empty_w = np.empty(0, dtype=np.float32)
        return empty_i, empty_i, empty_w, audit

    vertex_grid = np.broadcast_to(
        np.arange(joints.shape[0], dtype=np.int64)[:, np.newaxis],
        joints.shape,
    )
    vertex_indices = vertex_grid[usable]
    group_indices = mapped[usable].astype(np.int64, copy=False)
    usable_weights = weights[usable].astype(np.float64, copy=False)

    stride = int(np.max(group_indices)) + 1
    keys = vertex_indices * stride + group_indices
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    sorted_weights = usable_weights[order]
    reduce_starts = np.flatnonzero(
        np.concatenate(((True,), sorted_keys[1:] != sorted_keys[:-1]))
    )
    unique_keys = sorted_keys[reduce_starts]
    summed_weights = np.add.reduceat(sorted_weights, reduce_starts)

    aggregate_vertices = (unique_keys // stride).astype(np.int32)
    aggregate_groups = (unique_keys % stride).astype(np.int32)
    duplicate_count = int(len(keys) - len(unique_keys))

    positive_sums = summed_weights > _WEIGHT_EPSILON
    aggregate_vertices = aggregate_vertices[positive_sums]
    aggregate_groups = aggregate_groups[positive_sums]
    summed_weights = summed_weights[positive_sums]

    totals = np.bincount(
        aggregate_vertices,
        weights=summed_weights,
        minlength=joints.shape[0],
    )
    surviving = totals[aggregate_vertices] > _WEIGHT_EPSILON
    aggregate_vertices = aggregate_vertices[surviving]
    aggregate_groups = aggregate_groups[surviving]
    summed_weights = summed_weights[surviving]
    normalized_weights = (
        summed_weights / normalization_divisors(totals)[aggregate_vertices]
    ).astype(np.float32)

    zero_weight_vertices = int(np.count_nonzero(totals <= _WEIGHT_EPSILON))
    audit = SkinningAudit(
        invalid_influence_count=invalid_influence_count,
        unmapped_influence_count=int(np.count_nonzero(unmapped)),
        duplicate_influence_count=duplicate_count,
        zero_weight_vertex_count=zero_weight_vertices,
        valid_influence_count=len(normalized_weights),
    )
    return aggregate_vertices, aggregate_groups, normalized_weights, audit


def _prepare_vertex_groups(obj, submesh, skin, armature):
    joints = submesh.joint_indices
    weights = submesh.joint_weights
    if joints is None or weights is None:
        return None

    positive = np.isfinite(weights) & (weights > _WEIGHT_EPSILON)
    in_range = (joints >= 0) & (joints < len(skin.bone_names))
    invalid_positive_count = int(np.count_nonzero(positive & ~in_range))
    if invalid_positive_count:
        raise DirectMeshImportError(
            f"Skinned mesh {submesh.name!r} contains "
            f"{invalid_positive_count} positive influences with invalid joint indices."
        )
    used_source_indices = np.unique(joints[positive & in_range])

    source_to_group = np.full(len(skin.bone_names), -1, dtype=np.int32)
    unmapped_bones = []
    resolved_groups = []
    for source_index_value in used_source_indices:
        source_index = int(source_index_value)
        source_name = skin.bone_names[source_index]
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            unmapped_bones.append(source_name)
            continue
        resolved_groups.append((source_index, target_name))

    if unmapped_bones:
        raise DirectMeshImportError(
            f"Skinned mesh {submesh.name!r} references weighted bones that "
            "do not exist on the destination armature: "
            + ", ".join(unmapped_bones[:16])
        )

    for source_index, target_name in resolved_groups:
        group = obj.vertex_groups.get(target_name) or obj.vertex_groups.new(
            name=target_name
        )
        source_to_group[source_index] = group.index

    vertices, groups, normalized, audit = _aggregate_deform_weights(
        joints,
        weights,
        source_to_group,
    )
    audit.unmapped_bones = tuple(unmapped_bones)
    return vertices, groups, normalized, audit


def _write_deform_weights(obj, vertices, groups, weights):
    if not len(weights):
        return False

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        deform_layer = bm.verts.layers.deform.verify()
        current_vertex = -1
        deform = None
        for vertex_index, group_index, weight in zip(vertices, groups, weights):
            vertex_index = int(vertex_index)
            if vertex_index != current_vertex:
                current_vertex = vertex_index
                deform = bm.verts[vertex_index][deform_layer]
            deform[int(group_index)] = float(weight)
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    return True


def _apply_vertex_groups(obj, submesh, skin, armature):
    prepared = _prepare_vertex_groups(obj, submesh, skin, armature)
    if prepared is None:
        return False, SkinningAudit()
    vertices, groups, weights, audit = prepared
    topology_rebuilt = _write_deform_weights(obj, vertices, groups, weights)
    return topology_rebuilt, audit


def _apply_shape_keys(obj, submesh):
    if not submesh.morph_targets:
        return
    basis = obj.shape_key_add(name="Basis", from_mix=False)
    track_created_datablock("shape_keys", obj.data.shape_keys)
    basis.value = 0.0
    work = np.empty_like(submesh.positions, dtype=np.float32)
    for name, delta in submesh.morph_targets:
        np.add(submesh.positions, delta, out=work)
        key = obj.shape_key_add(name=name, from_mix=False)
        key.data.foreach_set("co", work.reshape(-1))
        key.value = 0.0


def _finish_submesh_object(
    obj,
    submesh,
    loop_vertices,
    *,
    preserve_source_frame: bool = True,
):
    mesh = obj.data
    _apply_uv_layers(mesh, submesh, loop_vertices)
    _apply_color_layers(mesh, submesh)
    _apply_shape_keys(obj, submesh)
    _apply_custom_normals(mesh, submesh)
    mesh.update()
    if preserve_source_frame:
        ensure_source_frame_attributes(mesh, submesh)
    store_source_morph_shading(
        obj,
        submesh.morph_normals,
        submesh.morph_tangents,
        position_deltas=submesh.morph_targets,
    )
    if submesh.source_vertex_indices is not None:
        store_source_vertex_indices(mesh, submesh.source_vertex_indices)


def _new_submesh_object(
    submesh: Submesh,
    *,
    validate_geometry: bool = True,
    calculate_edges: bool = True,
):
    mesh, loop_vertices = _build_mesh_geometry(
        submesh,
        validate_geometry=validate_geometry,
        calculate_edges=calculate_edges,
    )
    return (
        track_created_datablock("objects", bpy.data.objects.new(submesh.name, mesh)),
        loop_vertices,
    )


def _expected_bind_bone_matrices(mesh_data: DirectMeshData):
    joint_bind = mesh_data.authoritative_joint_bind_gltf
    skin_index = mesh_data.authoritative_skin_index
    if joint_bind is None or skin_index is None:
        return None, None
    skin = mesh_data.skins[skin_index]
    matrices = gltf_relative_to_blender(joint_bind, is_root=True)
    return skin, matrices


def _armature_bind_error(armature, skin, expected_matrices):
    maximum = 0.0
    missing = []
    for source_name, expected in zip(skin.bone_names, expected_matrices):
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            missing.append(source_name)
            continue
        actual = np.asarray(
            armature.data.bones[target_name].matrix_local,
            dtype=np.float64,
        )
        maximum = max(maximum, float(np.max(np.abs(actual - expected))))
    return maximum, tuple(missing)


def _bind_failure_analysis(armature, skin, expected_matrices):
    """Explain why an inverse-bind rest pose could not be satisfied"""
    basis = expected_matrices[:, :3, :3]
    u, singular, vt = np.linalg.svd(basis)
    residual = np.max(np.abs(basis - np.matmul(u, vt)), axis=(1, 2))
    scale_deviation = np.max(np.abs(singular - 1.0), axis=1)

    lines = []
    short = []
    for index, source_name in enumerate(skin.bone_names):
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            continue
        bone = armature.data.bones[target_name]
        length = float(bone.length)
        error = float(
            np.max(
                np.abs(
                    np.asarray(bone.matrix_local, dtype=np.float64)
                    - expected_matrices[index]
                )
            )
        )
        if error <= BIND_MATRIX_TOLERANCE:
            continue
        required_length = float32_direction_length(
            expected_matrices[index, :3, 3], BIND_MATRIX_TOLERANCE
        )
        lines.append(
            (
                error,
                source_name,
                length,
                required_length,
                float(residual[index]),
                float(scale_deviation[index]),
            )
        )
        if length < required_length:
            short.append(source_name)

    lines.sort(reverse=True)
    non_rigid = [name for _, name, _, _, res, _ in lines if res > BIND_MATRIX_TOLERANCE]
    return short, non_rigid, lines


def _bind_failure_detail(armature, skin, expected_matrices, analysis=None):
    short, non_rigid, lines = analysis or _bind_failure_analysis(
        armature,
        skin,
        expected_matrices,
    )
    report = []
    if short:
        report.append(
            f"{len(short)} joint(s) are shorter than float32 head/tail can carry at "
            "this tolerance; lengthen them using "
            "blender.armature.precision_safe_bone_length."
        )
    if non_rigid:
        report.append(
            f"{len(non_rigid)} joint(s) have non-rigid bind matrices (scale or shear) "
            f"that an edit bone cannot represent."
        )
    if not report:
        report.append(
            "No joint is short or non-rigid; the residual is likely roll quantization."
        )
    for error, name, length, needed, _, scale in lines[:8]:
        report.append(
            f"  {name}: error {error:.6g}, length {length:.6g} "
            f"(needs {needed:.6g}), scale dev {scale:.6g}"
        )
    return "\n".join(report)


def _set_created_armature_bind_pose(armature, skin, expected_matrices):
    maximum, missing = _armature_bind_error(armature, skin, expected_matrices)
    if missing:
        raise DirectMeshImportError(
            "Created armature is missing skin joints: " + ", ".join(missing[:8])
        )
    if maximum <= BIND_MATRIX_TOLERANCE:
        return maximum, False

    from ..rig.reader import set_armature_model_space_matrices

    target_names = []
    for source_name in skin.bone_names:
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            raise DirectMeshImportError(
                f"Created armature is missing edit bone for {source_name!r}."
            )
        target_names.append(target_name)

    set_armature_model_space_matrices(
        armature,
        target_names,
        expected_matrices,
    )

    corrected_error, missing = _armature_bind_error(
        armature,
        skin,
        expected_matrices,
    )
    if missing:
        raise DirectMeshImportError(
            "Created armature is missing skin joints after correction: "
            + ", ".join(missing[:8])
        )
    if corrected_error > _BIND_MATRIX_HARD_LIMIT:
        detail = _bind_failure_detail(armature, skin, expected_matrices)
        raise DirectMeshImportError(
            f"Authoritative inverse-bind rest pose is unusable "
            f"(max error {corrected_error:.6g}, limit {_BIND_MATRIX_HARD_LIMIT:.6g}).\n"
            + detail
        )
    if corrected_error > BIND_MATRIX_TOLERANCE:
        analysis = _bind_failure_analysis(armature, skin, expected_matrices)
        short, non_rigid, _lines = analysis
        detail = _bind_failure_detail(armature, skin, expected_matrices, analysis)
        if (
            not short
            and not non_rigid
            and corrected_error <= _BIND_ROLL_QUANTIZATION_LIMIT
        ):
            _LOG.debug(
                "Rest pose applied within %.6g (clean tolerance %.6g); continuing.\n%s",
                corrected_error,
                BIND_MATRIX_TOLERANCE,
                detail,
            )
        else:
            _LOG.warning(
                "Rest pose applied within %.6g (clean tolerance %.6g); %s",
                corrected_error,
                BIND_MATRIX_TOLERANCE,
                detail.splitlines()[0],
            )
            _LOG.debug("%s", detail)
    return corrected_error, True


def _authoritative_source_rest_snapshot(armature, skin, global_matrices):
    relative = model_matrices_to_local(
        global_matrices, skin.parent_indices, skin.topological_joint_indices
    )

    snapshot = {
        "version": 2,
        "space": SOURCE_REST_SPACE_CONTRACT,
        "boneNames": list(skin.bone_names),
        "matrices": relative.reshape(len(relative), 16).tolist(),
    }
    target_matrices = []
    for source_name in skin.bone_names:
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            target_matrices = []
            break
        target_matrices.append(
            np.asarray(
                armature.data.bones[target_name].matrix_local,
                dtype=np.float64,
            )
        )
    if target_matrices:
        snapshot["targetMatrices"] = (
            np.asarray(target_matrices, dtype=np.float64)
            .reshape(len(target_matrices), 16)
            .tolist()
        )
    return snapshot


def _store_authoritative_source_rest(armature, skin, global_matrices):
    snapshot = _authoritative_source_rest_snapshot(armature, skin, global_matrices)
    armature[MESH_SOURCE_REST_SNAPSHOT_KEY] = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return snapshot


def _configure_armature_bind_pose(mesh_data, armature, created_armature):
    skin, expected = _expected_bind_bone_matrices(mesh_data)
    if skin is None:
        return 0.0, False, ()

    if created_armature:
        error, corrected = _set_created_armature_bind_pose(
            armature,
            skin,
            expected,
        )
        _store_authoritative_source_rest(
            armature,
            skin,
            expected,
        )
        missing = ()
    else:
        error, missing = _armature_bind_error(armature, skin, expected)
        corrected = False

    return error, corrected, missing


def _set_object_bind_transform(obj, submesh, armature):
    matrix = Matrix(
        tuple(tuple(float(value) for value in row) for row in submesh.node_matrix_red)
    )
    if armature is None:
        obj.matrix_world = matrix
        return
    obj.parent = armature
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = matrix


def _resolve_armature(mesh_data: DirectMeshData, armature, collection=None):
    if armature is not None:
        return armature
    if not mesh_data.is_skinned:
        return None
    if mesh_data.binding is None or mesh_data.sampling_context is None:
        raise DirectMeshImportError(
            "A skinned mesh requires a decoded skeleton binding."
        )
    skin, expected_matrices = _expected_bind_bone_matrices(mesh_data)
    if skin is None or expected_matrices is None:
        raise DirectMeshImportError(
            "A skinned mesh has no authoritative inverse-bind rest pose."
        )
    return build_rest_armature_from_binding(
        mesh_data.binding,
        mesh_data.sampling_context,
        source_label=mesh_data.source_path,
        assign_shapes=False,
        model_space_matrices=expected_matrices,
        collection=collection,
    )


def _collection_name_from_filepath(filepath: str) -> str:
    name = os.path.splitext(os.path.basename(filepath))[0]
    return name or "CP77_Mesh"


def _new_import_collection(
    filepath: str,
    *,
    parent_collection=None,
    collection_name: str = "",
):
    collection = track_created_datablock(
        "collections",
        bpy.data.collections.new(
            collection_name or _collection_name_from_filepath(filepath)
        ),
    )
    (parent_collection or bpy.context.scene.collection).children.link(collection)
    return collection


def _set_object_hidden(obj, hidden):
    hidden = bool(hidden)
    try:
        obj.hide_viewport = hidden
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_object_hidden 1", type(error).__name__),
            "set object hidden: fell back after %s",
            error,
            exc_info=True,
        )
    try:
        view_layer = bpy.context.view_layer
        if view_layer is not None and view_layer.objects.get(obj.name) is obj:
            obj.hide_set(hidden, view_layer=view_layer)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_object_hidden 2", type(error).__name__),
            "set object hidden: fell back after %s",
            error,
            exc_info=True,
        )


def _move_object_to_collection(obj, collection):
    if collection.objects.get(obj.name) is None:
        collection.objects.link(obj)
    for current in tuple(obj.users_collection):
        if current is not collection:
            current.objects.unlink(obj)


def _select_imported_objects(objects, active=None):
    for selected in tuple(bpy.context.selected_objects):
        selected.select_set(False)
    for obj in objects:
        obj.select_set(True)
    if active is not None:
        bpy.context.view_layer.objects.active = active


def _store_json_property(idblock, key, value):
    idblock[key] = json_text(value)


def _source_skin_binding_snapshot(skin):
    return {
        "version": 1,
        "boneNames": list(skin.bone_names),
        "boneParentIndexes": [int(value) for value in skin.parent_indices],
    }


def _finalize_import_collection(
    collection,
    filepath,
    audits,
    mesh_data,
    *,
    document_metadata_json: str,
    scene_metadata_json: str,
):
    mark_origin(
        collection,
        ORIGIN_PLUGIN,
        source_path=filepath,
    )
    invalid = unmapped = duplicate = zero_weight = 0
    for audit in audits:
        invalid += audit.invalid_influence_count
        unmapped += audit.unmapped_influence_count
        duplicate += audit.duplicate_influence_count
        zero_weight += audit.zero_weight_vertex_count
    collection[_SOURCE_DOCUMENT_METADATA_KEY] = document_metadata_json
    collection[_SOURCE_SCENE_METADATA_KEY] = scene_metadata_json
    if mesh_data.authoritative_skin_index is not None:
        _store_json_property(
            collection,
            SOURCE_SKIN_BINDING_KEY,
            _source_skin_binding_snapshot(
                mesh_data.skins[mesh_data.authoritative_skin_index]
            ),
        )


def _import_mesh_glb_impl(
    filepath: str,
    armature=None,
    *,
    appearance_index: int = 0,
    restore_red_uvs: bool = True,
    collection=None,
    parent_collection=None,
    collection_name: str = "",
    import_garment_support: bool = True,
    hide_armature: bool = False,
    select_objects: bool = True,
    decoded_mesh_data: DirectMeshData | None = None,
    bulk_master: bool = False,
):
    """Import a WolvenKit mesh GLB with authoritative glTF skin binding"""

    mesh_data = decoded_mesh_data or decode_mesh_glb(
        filepath,
        restore_red_uvs=restore_red_uvs,
        build_binding=armature is None,
        import_garment_support=import_garment_support,
    )
    requested_source = absolute_local_path_key(filepath)
    decoded_source = absolute_local_path_key(mesh_data.source_path)
    if decoded_source != requested_source:
        raise DirectMeshImportError(
            "Predecoded mesh data does not belong to the requested GLB."
        )
    target_collection = collection or _new_import_collection(
        filepath,
        parent_collection=parent_collection,
        collection_name=collection_name,
    )
    resolved_armature = _resolve_armature(mesh_data, armature, target_collection)
    created_armature = armature is None and resolved_armature is not None

    bind_error = 0.0
    bind_corrected = False
    missing_bind_bones = ()
    source_rest_snapshot = None
    if resolved_armature is not None:
        bind_error, bind_corrected, missing_bind_bones = _configure_armature_bind_pose(
            mesh_data,
            resolved_armature,
            created_armature,
        )
        source_skin, source_bind_matrices = _expected_bind_bone_matrices(mesh_data)
        if source_skin is not None and source_bind_matrices is not None:
            source_rest_snapshot = _authoritative_source_rest_snapshot(
                resolved_armature,
                source_skin,
                source_bind_matrices,
            )

    if created_armature:
        mark_origin(
            resolved_armature,
            ORIGIN_PLUGIN,
            source_path=filepath,
        )
        resolved_armature.name = f"Armature__{target_collection.name}"
        _move_object_to_collection(resolved_armature, target_collection)
        _set_object_hidden(resolved_armature, hide_armature)

    document_metadata_json = json_text(mesh_data.document_metadata)
    scene_metadata_json = json_text(mesh_data.scene_metadata)
    source_rest_snapshot_json = (
        json_text(source_rest_snapshot) if source_rest_snapshot is not None else ""
    )
    skin_binding_json = {
        skin_index: json_text(_source_skin_binding_snapshot(skin))
        for skin_index, skin in mesh_data.skins.items()
    }
    skin_extras_json = {
        skin_index: json_text(skin.extras)
        for skin_index, skin in mesh_data.skins.items()
    }
    if source_rest_snapshot_json:
        target_collection[MESH_SOURCE_REST_SNAPSHOT_KEY] = source_rest_snapshot_json

    created = []
    audits = []
    for fallback_index, submesh in enumerate(mesh_data.submeshes):
        obj, loop_vertices = _new_submesh_object(
            submesh,
            validate_geometry=not bulk_master,
            calculate_edges=True,
        )
        _set_object_bind_transform(obj, submesh, resolved_armature)

        audit = SkinningAudit()
        if submesh.joint_indices is not None:
            if resolved_armature is None or submesh.skin_index is None:
                bpy.data.objects.remove(obj, do_unlink=True)
                raise DirectMeshImportError(
                    f"Skinned mesh {submesh.name!r} has no destination armature."
                )
            skin = mesh_data.skins[submesh.skin_index]
            topology_rebuilt, audit = _apply_vertex_groups(
                obj,
                submesh,
                skin,
                resolved_armature,
            )
            if topology_rebuilt:
                loop_vertices = _loop_vertex_indices(obj.data)
            modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
            modifier.object = resolved_armature

        _finish_submesh_object(
            obj,
            submesh,
            loop_vertices,
            preserve_source_frame=not bulk_master,
        )
        mark_origin(
            obj,
            ORIGIN_PLUGIN,
            source_path=filepath,
        )
        _store_json_property(obj, SOURCE_MESH_EXTRAS_KEY, submesh.mesh_extras)
        _store_json_property(obj, _SOURCE_NODE_EXTRAS_KEY, submesh.node_extras)
        if not bulk_master:
            obj[_SOURCE_DOCUMENT_METADATA_KEY] = document_metadata_json
            obj[_SOURCE_SCENE_METADATA_KEY] = scene_metadata_json
        if submesh.skin_index is not None:
            obj[SOURCE_SKIN_EXTRAS_KEY] = skin_extras_json[submesh.skin_index]
            obj[SOURCE_SKIN_BINDING_KEY] = skin_binding_json[submesh.skin_index]
            if source_rest_snapshot_json:
                obj[MESH_SOURCE_REST_SNAPSHOT_KEY] = source_rest_snapshot_json
        if 0 <= appearance_index < len(submesh.material_names):
            obj["cp77_material_name"] = submesh.material_names[appearance_index]
        obj["cp77_imported_mesh"] = True
        obj["cp77_single_material_submesh"] = True
        obj["cp77_submesh_index"] = int(
            submesh_index_from_name(submesh.name, fallback_index)
        )
        if submesh.skinning_warning:
            _LOG.warning("%s", submesh.skinning_warning)
        target_collection.objects.link(obj)
        created.append(obj)
        audits.append(audit)

        if is_enabled("DEBUG", _LOG) and (
            audit.invalid_influence_count
            or audit.unmapped_influence_count
            or audit.duplicate_influence_count
            or audit.zero_weight_vertex_count
        ):
            details = []
            if audit.invalid_influence_count:
                details.append(f"{audit.invalid_influence_count} invalid")
            if audit.unmapped_influence_count:
                details.append(f"{audit.unmapped_influence_count} unmapped")
            if audit.duplicate_influence_count:
                details.append(
                    f"{audit.duplicate_influence_count} duplicates consolidated"
                )
            if audit.zero_weight_vertex_count:
                details.append(f"{audit.zero_weight_vertex_count} zero-weight vertices")
            _LOG.debug("%s: %s", obj.name, ", ".join(details))
            if audit.unmapped_bones:
                _LOG.debug("Unmapped bones: %s", ", ".join(audit.unmapped_bones[:16]))

    _finalize_import_collection(
        target_collection,
        filepath,
        audits,
        mesh_data,
        document_metadata_json=document_metadata_json,
        scene_metadata_json=scene_metadata_json,
    )

    if mesh_data.max_inverse_bind_error > BIND_MATRIX_TOLERANCE:
        _LOG.warning(
            "Inverse-bind/node-rest disagreement: %.6g; %s",
            mesh_data.max_inverse_bind_error,
            "created armature rest corrected."
            if bind_corrected
            else "target armature retained.",
        )
    if missing_bind_bones:
        _LOG.warning(
            "Target armature is missing bind bones: %s",
            ", ".join(missing_bind_bones[:16]),
        )

    all_objects = ([resolved_armature] if created_armature else []) + created
    if select_objects:
        selectable = [obj for obj in all_objects if not obj.hide_get()]
        active = (
            resolved_armature
            if created_armature and not resolved_armature.hide_get()
            else (created[0] if created else None)
        )
        _select_imported_objects(selectable, active=active)

    return {
        "objects": created,
        "all_objects": all_objects,
        "armature": resolved_armature,
        "collection": target_collection,
        "mesh_data": mesh_data,
        "skin_audits": audits,
        "target_bind_error": bind_error,
        "bind_pose_corrected": bind_corrected,
        "missing_bind_bones": missing_bind_bones,
    }


def import_mesh_glb(
    filepath: str,
    armature=None,
    *,
    appearance_index: int = 0,
    restore_red_uvs: bool = True,
    collection=None,
    parent_collection=None,
    collection_name: str = "",
    import_garment_support: bool = True,
    hide_armature: bool = False,
    select_objects: bool = True,
    transaction=None,
    decoded_mesh_data: DirectMeshData | None = None,
    bulk_master: bool = False,
):
    active = current_import_transaction()
    if transaction is not None and active not in (None, transaction):
        raise RuntimeError("Mesh import transaction conflicts with active transaction")
    owner = transaction or active
    owns_transaction = owner is None
    if owner is None:
        owner = DatablockImportTransaction()
    armature_properties = snapshot_id_properties(armature)
    collection_properties = snapshot_id_properties(collection)
    scope = owner.scope() if active is not owner else None
    try:
        with scope if scope is not None else nullcontext():
            result = _import_mesh_glb_impl(
                filepath,
                armature,
                appearance_index=appearance_index,
                restore_red_uvs=restore_red_uvs,
                collection=collection,
                parent_collection=parent_collection,
                collection_name=collection_name,
                import_garment_support=import_garment_support,
                hide_armature=hide_armature,
                select_objects=select_objects,
                decoded_mesh_data=decoded_mesh_data,
                bulk_master=bulk_master,
            )
    except Exception as error:
        report = owner.rollback() if owns_transaction else None
        restore_id_properties(armature, armature_properties)
        restore_id_properties(collection, collection_properties)
        raise_if_rollback_incomplete(report, error)
        raise
    if owns_transaction:
        owner.commit()
    return result
