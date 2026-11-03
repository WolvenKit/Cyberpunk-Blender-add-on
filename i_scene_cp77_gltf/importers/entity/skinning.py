from __future__ import annotations

import numpy as np
from mathutils import Matrix

from ...assetio.values import cname_value
from .transforms import (
    _rig_json_bone_matrix_array,
    _rig_json_model_space_matrices,
    cache_armature_bones,
    is_live_armature_object,
    rig_bone_index_for,
)
from ..common.collections import _preserve_world_parent
from ...animation.rig_binding import merged_bone_name

_UNSET = object()
_RED_MATRIX_CACHE = {}
_RED_MATRIX_ARRAY_CACHE = {}
_SKIN_ATTACHMENT_CACHE = {}


def clear_skinning_caches():
    """Clear import-scoped RED matrix and skin attachment caches."""
    _RED_MATRIX_CACHE.clear()
    _RED_MATRIX_ARRAY_CACHE.clear()
    _SKIN_ATTACHMENT_CACHE.clear()

def _red_matrix_to_blender(value):
    """Convert a serialized RED Matrix to mathutils column-vector form."""
    if not isinstance(value, dict):
        return None
    cache_key = id(value)
    cached = _RED_MATRIX_CACHE.get(cache_key)
    if cached is not None and cached[0] is value:
        return cached[1]
    x = value.get('X')
    y = value.get('Y')
    z = value.get('Z')
    w = value.get('W')
    matrix = None
    if all(isinstance(column, dict) for column in (x, y, z, w)):
        try:
            matrix = Matrix(
                    (
                        (float(x['X']), float(y['X']), float(z['X']), float(w['X'])),
                        (float(x['Y']), float(y['Y']), float(z['Y']), float(w['Y'])),
                        (float(x['Z']), float(y['Z']), float(z['Z']), float(w['Z'])),
                        (float(x['W']), float(y['W']), float(z['W']), float(w['W'])),
                        )
                    )
        except (KeyError, TypeError, ValueError):
            matrix = None
    _RED_MATRIX_CACHE[cache_key] = (value, matrix)
    return matrix

def _red_matrix_to_array(value):
    if not isinstance(value, dict):
        return None
    cache_key = id(value)
    cached = _RED_MATRIX_ARRAY_CACHE.get(cache_key)
    if cached is not None and cached[0] is value:
        return cached[1]
    matrix = _red_matrix_to_blender(value)
    array = None if matrix is None else np.asarray(matrix, dtype=np.float64)
    _RED_MATRIX_ARRAY_CACHE[cache_key] = (value, array)
    return array

def _mesh_skin_anchor(mesh_j, rig_j):
    """Return the first mapped bone in authored mesh order."""
    if not isinstance(mesh_j, dict) or not isinstance(rig_j, dict):
        return None, 'missing_json'
    raw_names = mesh_j.get('boneNames')
    raw_matrices = mesh_j.get('boneRigMatrices')
    if not isinstance(raw_names, list) or not isinstance(raw_matrices, list):
        return None, 'missing_skin_data'

    rig_index = rig_bone_index_for(rig_j)
    saw_named_bone = False
    for mesh_index, raw_name in enumerate(raw_names):
        source_name = cname_value(raw_name)
        if not source_name:
            continue
        saw_named_bone = True
        if mesh_index >= len(raw_matrices):
            continue
        target_name = merged_bone_name(source_name)
        target_index = rig_index.get(target_name)
        if target_index is not None:
            return (mesh_index, source_name, target_name, target_index), 'ok'

    return None, 'missing_mapped_bone' if saw_named_bone else 'missing_bones'

def _matrices_near(a, b, epsilon=1e-4):
    for row in range(4):
        a_row = a[row]
        b_row = b[row]
        for column in range(4):
            if abs(a_row[column] - b_row[column]) > epsilon:
                return False
    return True

def component_skin_attachment_matrix(mesh_j, rig_j):
    """Return the RED attachment transform for the first mapped bone."""
    cache_key = (id(mesh_j), id(rig_j))
    cached = _SKIN_ATTACHMENT_CACHE.get(cache_key)
    if cached is not None and cached[0] is mesh_j and cached[1] is rig_j:
        return cached[2]

    root, status = _mesh_skin_anchor(mesh_j, rig_j)
    if root is None:
        result = (None, '', status)
        _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
        return result

    mesh_index, source_name, target_name, target_index = root
    raw_matrices = mesh_j.get('boneRigMatrices') or ()
    if mesh_index >= len(raw_matrices):
        result = (None, source_name, 'missing_anchor_bind_matrix')
        _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
        return result

    skin_to_rig = _red_matrix_to_blender(raw_matrices[mesh_index])
    if skin_to_rig is None:
        result = (None, source_name, 'invalid_anchor_bind_matrix')
        _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
        return result

    rig_matrices = _rig_json_model_space_matrices(rig_j)
    rig_model_space = rig_matrices[target_index] if target_index < len(rig_matrices) else Matrix.Identity(4)
    placement = rig_model_space @ skin_to_rig

    # Descendant products diagnose deformation, not root attachment.
    rig_index = rig_bone_index_for(rig_j)
    non_uniform_children = []
    missing_children = []
    child_names = []
    child_target_indices = []
    child_bind_matrices = []
    raw_names = mesh_j.get('boneNames') or ()
    for child_index, raw_name in enumerate(raw_names):
        if child_index == mesh_index or child_index >= len(raw_matrices):
            continue
        child_source_name = cname_value(raw_name)
        if not child_source_name:
            continue
        child_target_index = rig_index.get(merged_bone_name(child_source_name))
        child_skin_to_rig = _red_matrix_to_array(raw_matrices[child_index])
        if child_target_index is None or child_skin_to_rig is None:
            missing_children.append(child_source_name)
            continue
        child_names.append(child_source_name)
        child_target_indices.append(child_target_index)
        child_bind_matrices.append(child_skin_to_rig)

    if child_names:
        rig_matrix_array = _rig_json_bone_matrix_array(rig_j)
        target_array = rig_matrix_array[np.asarray(child_target_indices, dtype=np.intp)]
        bind_array = np.stack(child_bind_matrices)
        products = np.matmul(target_array, bind_array)
        placement_array = np.asarray(placement, dtype=np.float64)
        differences = np.max(np.abs(products - placement_array), axis=(1, 2))
        non_uniform_children = [
            name for name, difference in zip(child_names, differences)
            if difference > 1e-4
            ]

    if missing_children:
        status = 'anchor_ok_missing_mappings:' + ','.join(missing_children)
    elif non_uniform_children:
        status = 'anchor_ok_deforming_bones:' + ','.join(non_uniform_children)
    else:
        status = 'ok'
    result = (placement, source_name, status)
    _SKIN_ATTACHMENT_CACHE[cache_key] = (mesh_j, rig_j, result)
    return result

def _rename_vertex_groups_to_meta(obj, rig):
    rig_bones = cache_armature_bones(rig)
    for group in getattr(obj, 'vertex_groups', ()):
        source_name = group.name
        target_name = merged_bone_name(source_name)
        if target_name != source_name and target_name in rig_bones and source_name not in rig_bones:
            group.name = target_name


def bind_skinned_objects_to_rig(objects, rig):
    """Retarget copied skinned meshes to the completed MetaRig."""
    if rig is None:
        return 0, 0

    live_sources = {}
    skinned_meshes = 0
    redirected_modifiers = 0
    reparented_meshes = 0
    for obj in objects:
        if getattr(obj, 'type', None) != 'MESH':
            continue

        mesh_redirected = False
        source_armatures = set()
        for modifier in getattr(obj, 'modifiers', ()):
            if modifier.type != 'ARMATURE':
                continue
            source_armature = modifier.object
            if source_armature is rig:
                mesh_redirected = True
                continue
            if source_armature is None:
                continue
            source_key = id(source_armature)
            source_is_live = live_sources.get(source_key, _UNSET)
            if source_is_live is _UNSET:
                source_is_live = is_live_armature_object(source_armature)
                live_sources[source_key] = source_is_live
            if not source_is_live:
                continue

            source_armatures.add(source_armature)
            _rename_vertex_groups_to_meta(obj, rig)
            modifier.object = rig
            redirected_modifiers += 1
            mesh_redirected = True

        parent = getattr(obj, 'parent', None)
        parent_is_source_armature = (
            parent is not None
            and parent is not rig
            and getattr(parent, 'type', None) == 'ARMATURE'
            and (
                parent in source_armatures
                or is_live_armature_object(parent)
            )
        )
        if parent_is_source_armature:
            _preserve_world_parent(obj, rig)
            reparented_meshes += 1
            mesh_redirected = True
        elif mesh_redirected and parent is None:
            _preserve_world_parent(obj, rig)
            reparented_meshes += 1

        if mesh_redirected:
            obj['cp77_source_armature_retained'] = False
            obj['cp77_retargeted_to_metarig'] = rig.name
            skinned_meshes += 1

    try:
        rig['cp77_retargeted_mesh_count'] = int(
            rig.get('cp77_retargeted_mesh_count', 0)
        ) + skinned_meshes
        rig['cp77_retargeted_parent_count'] = int(
            rig.get('cp77_retargeted_parent_count', 0)
        ) + reparented_meshes
    except (AttributeError, ReferenceError, TypeError, ValueError):
        pass
    return skinned_meshes, redirected_modifiers
