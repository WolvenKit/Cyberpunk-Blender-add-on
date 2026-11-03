from __future__ import annotations

import json

import bpy
import numpy as np

from .custom_normals import set_custom_normals_from_corners
from .mesh import _mesh_signature

_SOURCE_MORPH_SHADING = "cp77_source_morph_shading"


def _key_signature(key):
    points = np.empty(len(key.data) * 3, dtype=np.float32)
    key.data.foreach_get("co", points)
    return _mesh_signature(b"CP77Morph", points)


def store_source_morph_shading(
    obj, normal_deltas, tangent_deltas, *, position_deltas=()
):
    """Retain authored morph channels with fingerprints of their Blender key coordinates"""
    if obj.data.shape_keys is None:
        return
    position_map = dict(position_deltas)
    normal_map, tangent_map = dict(normal_deltas), dict(tangent_deltas)
    basis_signature = _key_signature(obj.data.shape_keys.key_blocks[0])
    records = {}
    for index, key in enumerate(tuple(obj.data.shape_keys.key_blocks)[1:]):
        record = {"signature": _key_signature(key), "basisSignature": basis_signature}
        for semantic, values in (
            ("position", position_map.get(key.name)),
            ("normal", normal_map.get(key.name)),
            ("tangent", tangent_map.get(key.name)),
        ):
            if values is None:
                continue
            name = f".cp77_morph_{semantic}_{index}"
            attribute = obj.data.attributes.new(
                name=name, type="FLOAT_VECTOR", domain="POINT"
            )
            attribute.data.foreach_set(
                "vector", np.asarray(values, dtype=np.float32).reshape(-1)
            )
            record[semantic] = attribute.name
        records[key.name] = record
    obj.data[_SOURCE_MORPH_SHADING] = json.dumps(records, separators=(",", ":"))


def source_morph_positions(obj):
    """Recover exact source offsets only while both Basis and the target remain untouched"""
    keys = obj.data.shape_keys
    if keys is None:
        return {}
    records = json.loads(str(obj.data.get(_SOURCE_MORPH_SHADING, "{}")))
    basis_signature = _key_signature(keys.key_blocks[0])
    result = {}
    for key in tuple(keys.key_blocks)[1:]:
        record = records.get(key.name)
        if (
            record is None
            or record.get("basisSignature") != basis_signature
            or record.get("signature") != _key_signature(key)
        ):
            continue
        attribute = obj.data.attributes.get(record.get("position", ""))
        if (
            attribute is None
            or attribute.domain != "POINT"
            or attribute.data_type != "FLOAT_VECTOR"
            or len(attribute.data) != len(key.data)
        ):
            continue
        values = np.empty((len(attribute.data), 3), dtype=np.float32)
        attribute.data.foreach_get("vector", values.reshape(-1))
        result[key.name] = values
    return result


def source_position_only_morphs(obj):
    """Names of the shape keys imported from source targets that carried positions but no shading deltas"""
    records = json.loads(str(obj.data.get(_SOURCE_MORPH_SHADING, "{}")))
    return {
        name
        for name, record in records.items()
        if "position" in record and "normal" not in record and "tangent" not in record
    }


def source_morph_shading(obj, loop_vertices):
    """Recover untouched source deltas using the current key coordinates as evidence"""
    records = json.loads(str(obj.data.get(_SOURCE_MORPH_SHADING, "{}")))
    keys = obj.data.shape_keys
    result = {}
    if keys is None:
        return result
    for key in tuple(keys.key_blocks)[1:]:
        record = records.get(key.name)
        if record is None or record.get("signature") != _key_signature(key):
            continue
        channels = {}
        for semantic in ("normal", "tangent"):
            attribute = obj.data.attributes.get(record.get(semantic, ""))
            if (
                attribute is None
                or attribute.domain != "POINT"
                or attribute.data_type != "FLOAT_VECTOR"
                or len(attribute.data) != len(obj.data.vertices)
            ):
                continue
            values = np.empty(len(attribute.data) * 3, dtype=np.float32)
            attribute.data.foreach_get("vector", values)
            channels[semantic] = np.ascontiguousarray(
                values.reshape(-1, 3)[loop_vertices]
            )
        result[key.name] = channels
    return result


def mesh_corner_frame(mesh, uv_name):
    """Read the actual split normal and tangent frame used by Blender for a mesh"""
    if not uv_name or mesh.uv_layers.get(uv_name) is None:
        raise ValueError(
            "Morph shading export requires a UV0 layer for tangent calculation."
        )
    mesh.free_tangents()
    mesh.calc_tangents(uvmap=uv_name)
    count = len(mesh.loops)
    normals = np.empty(count * 3, dtype=np.float32)
    tangents = np.empty_like(normals)
    signs = np.empty(count, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", normals)
    mesh.loops.foreach_get("tangent", tangents)
    mesh.loops.foreach_get("bitangent_sign", signs)
    return normals.reshape(-1, 3), tangents.reshape(-1, 3), signs


def morph_shading_from_mesh(mesh, morph_targets, uv_name, *, preserved=None):
    """Evaluate edited shape shading on an isolated mesh while retaining source deltas"""
    preserved = preserved or {}
    normal_deltas, tangent_deltas = [], []
    sample = None
    base_positions = base_normals = base_tangents = base_signs = basis_key_normals = (
        None
    )
    try:
        for name, position_delta in morph_targets:
            channels = preserved.get(name, {})
            normal, tangent = channels.get("normal"), channels.get("tangent")
            if normal is None or tangent is None:
                if not np.any(position_delta):
                    derived_normal = derived_tangent = np.zeros(
                        (len(mesh.loops), 3), dtype=np.float32
                    )
                else:
                    if sample is None:
                        sample = mesh.copy()
                        base_positions = np.empty(
                            len(mesh.vertices) * 3, dtype=np.float32
                        )
                        mesh.vertices.foreach_get("co", base_positions)
                        base_positions = base_positions.reshape(-1, 3)
                        base_normals, base_tangents, base_signs = mesh_corner_frame(
                            sample, uv_name
                        )
                        if mesh.shape_keys is not None:
                            basis_key_normals = np.asarray(
                                mesh.shape_keys.key_blocks[0].normals_split_get(),
                                dtype=np.float32,
                            ).reshape(-1, 3)
                    sample.vertices.foreach_set(
                        "co", (base_positions + position_delta).reshape(-1)
                    )
                    sample.update()
                    key = (
                        mesh.shape_keys.key_blocks.get(name)
                        if mesh.shape_keys is not None
                        else None
                    )
                    if key is not None and basis_key_normals is not None:
                        key_normals = np.asarray(
                            key.normals_split_get(), dtype=np.float32
                        ).reshape(-1, 3)
                        desired_normals = base_normals + key_normals - basis_key_normals
                        desired_normals /= np.maximum(
                            np.linalg.norm(desired_normals, axis=1, keepdims=True),
                            1e-12,
                        )
                        set_custom_normals_from_corners(
                            sample, desired_normals, label=f"Morph {name}"
                        )
                        sample.update()
                    target_normals, target_tangents, target_signs = mesh_corner_frame(
                        sample, uv_name
                    )
                    if not np.array_equal(base_signs, target_signs):
                        raise ValueError(
                            f"Morph {name!r} changes tangent handedness, which glTF morph targets cannot encode."
                        )
                    derived_normal = target_normals - base_normals
                    derived_tangent = target_tangents - base_tangents
                normal = derived_normal if normal is None else normal
                tangent = derived_tangent if tangent is None else tangent
            normal_deltas.append((name, np.ascontiguousarray(normal)))
            tangent_deltas.append((name, np.ascontiguousarray(tangent)))
    finally:
        if sample is not None:
            bpy.data.meshes.remove(sample)
    return normal_deltas, tangent_deltas


def evaluated_morph_frame(obj, depsgraph, uv_name):
    """Read one shape through its modifier stack without retaining evaluated datablocks"""
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        loops = np.empty(len(mesh.loops), dtype=np.int32)
        totals = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.vertices.foreach_get("co", positions)
        mesh.loops.foreach_get("vertex_index", loops)
        mesh.polygons.foreach_get("loop_total", totals)
        normals, tangents, signs = mesh_corner_frame(mesh, uv_name)
        return positions.reshape(-1, 3), loops, totals, normals, tangents, signs
    finally:
        evaluated.to_mesh_clear()
