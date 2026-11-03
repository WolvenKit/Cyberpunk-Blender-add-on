from __future__ import annotations

import bpy
import numpy as np

from ..bartmoss.matrix import as_matrix_4x4
from ..bartmoss.skinning import (
    blended_vertex_matrices,
    transform_normals,
    transform_points,
)
from .custom_normals import CUSTOM_NORMAL_ATTRIBUTE
from .identity import rna_is_live
from .mesh import deform_weights
from .transactions import track_mutation


def _vectors(collection, attribute):
    values = np.empty(len(collection) * 3, dtype=np.float32)
    collection.foreach_get(attribute, values)
    return values.reshape(-1, 3)


def _free_normals(mesh):
    """The mesh's free custom normals, which keep their direction when the surface under them moves"""
    attribute = mesh.attributes.get(CUSTOM_NORMAL_ATTRIBUTE)
    if (
        attribute is None
        or attribute.data_type != "FLOAT_VECTOR"
        or attribute.domain not in {"POINT", "CORNER"}
    ):
        return None
    return attribute


def _skinned_meshes(armature):
    """The mesh objects armature deforms through vertex groups, one per mesh"""
    found = {}
    for obj in bpy.data.objects:
        if (
            obj.type != "MESH"
            or not obj.vertex_groups
            or obj.data.as_pointer() in found
        ):
            continue
        if any(
            modifier.type == "ARMATURE"
            and modifier.object == armature
            and modifier.use_vertex_groups
            for modifier in obj.modifiers
        ):
            found[obj.data.as_pointer()] = obj
    return tuple(found.values())


def _vertex_deforms(obj, armature, bind_rest, rest):
    """Each vertex's deform from bind_rest to rest in the mesh's own space"""
    to_armature = np.linalg.inv(as_matrix_4x4(armature.matrix_world)) @ as_matrix_4x4(
        obj.matrix_world
    )
    to_mesh = np.linalg.inv(to_armature)
    bones = armature.data.bones
    groups = np.tile(np.eye(4), (len(obj.vertex_groups), 1, 1))
    deforming = np.zeros(len(obj.vertex_groups), dtype=bool)
    for group in obj.vertex_groups:
        bone = bones.get(group.name)
        if (
            bone is not None
            and bone.use_deform
            and group.name in bind_rest
            and group.name in rest
        ):
            groups[group.index] = (
                to_mesh
                @ as_matrix_4x4(rest[group.name])
                @ np.linalg.inv(as_matrix_4x4(bind_rest[group.name]))
                @ to_armature
            )
            deforming[group.index] = True
    pairs, weights = deform_weights(obj.data, True)
    keep = deforming[pairs[:, 1]]
    return blended_vertex_matrices(
        len(obj.data.vertices), pairs[keep, 0], pairs[keep, 1], weights[keep], groups
    )


def _capture(mesh):
    normals = _free_normals(mesh)
    return (
        _vectors(mesh.vertices, "co"),
        {key.name: _vectors(key.data, "co") for key in mesh.shape_keys.key_blocks}
        if mesh.shape_keys
        else {},
        _vectors(normals.data, "vector") if normals is not None else None,
    )


def _write(mesh, positions, keys, normals):
    mesh.vertices.foreach_set("co", np.asarray(positions, dtype=np.float32).ravel())
    for name, values in keys.items():
        mesh.shape_keys.key_blocks[name].data.foreach_set(
            "co", np.asarray(values, dtype=np.float32).ravel()
        )
    if normals is not None:
        _free_normals(mesh).data.foreach_set(
            "vector", np.asarray(normals, dtype=np.float32).ravel()
        )
    mesh.update()


def _track(mesh, state):
    def restore():
        if rna_is_live(mesh):
            _write(mesh, *state)

    track_mutation(
        ("skinned_rest_shape", mesh.as_pointer()),
        restore,
        label=f"rest shape of {mesh.name}",
    )


def move_skinned_rest_shapes(armature, bind_rest, rest, *, inverse=False):
    """Move the rest shape of every mesh armature deforms from bind_rest to rest"""
    moves = []
    for obj in _skinned_meshes(armature):
        deforms = _vertex_deforms(obj, armature, bind_rest, rest)
        moves.append((obj.data, np.linalg.inv(deforms) if inverse else deforms))
    for mesh, deforms in moves:
        positions, keys, normals = state = _capture(mesh)
        _track(mesh, state)
        if normals is not None and _free_normals(mesh).domain == "CORNER":
            corners = np.empty(len(mesh.loops), dtype=np.int64)
            mesh.loops.foreach_get("vertex_index", corners)
            normals = transform_normals(normals, deforms[corners])
        elif normals is not None:
            normals = transform_normals(normals, deforms)
        _write(
            mesh,
            transform_points(positions, deforms),
            {name: transform_points(values, deforms) for name, values in keys.items()},
            normals,
        )
    return len(moves)
