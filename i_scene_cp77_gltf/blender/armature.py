import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..redSpace.qs_transform import parse_wkit_trs
from .context import safe_mode_switch

_MODEL_SPACE_MATRIX_CACHE = {}
_PARENT_CHILDREN_CACHE = {}
_CACHE_LIMIT = 64


def _bounded_cache_store(cache, key, value):
    cache[key] = value
    if len(cache) > _CACHE_LIMIT:
        cache.pop(next(iter(cache)))


def trs_dicts_to_arrays(trs_list):
    return parse_wkit_trs(trs_list, quaternion_order="wxyz")


def trs_to_matrices_np(q_wxyz, translation, scale):
    w, x, y, z = (
        q_wxyz[:, 0],
        q_wxyz[:, 1],
        q_wxyz[:, 2],
        q_wxyz[:, 3],
    )
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    r00 = (1 - 2 * (yy + zz)) * scale[:, 0]
    r01 = (2 * (xy - wz)) * scale[:, 1]
    r02 = (2 * (xz + wy)) * scale[:, 2]
    r10 = (2 * (xy + wz)) * scale[:, 0]
    r11 = (1 - 2 * (xx + zz)) * scale[:, 1]
    r12 = (2 * (yz - wx)) * scale[:, 2]
    r20 = (2 * (xz - wy)) * scale[:, 0]
    r21 = (2 * (yz + wx)) * scale[:, 1]
    r22 = (1 - 2 * (xx + yy)) * scale[:, 2]

    matrices = np.zeros((q_wxyz.shape[0], 4, 4), dtype=np.float32)
    matrices[:, 0, 0] = r00
    matrices[:, 0, 1] = r01
    matrices[:, 0, 2] = r02
    matrices[:, 0, 3] = translation[:, 0]
    matrices[:, 1, 0] = r10
    matrices[:, 1, 1] = r11
    matrices[:, 1, 2] = r12
    matrices[:, 1, 3] = translation[:, 1]
    matrices[:, 2, 0] = r20
    matrices[:, 2, 1] = r21
    matrices[:, 2, 2] = r22
    matrices[:, 2, 3] = translation[:, 2]
    matrices[:, 3, 3] = 1.0
    return matrices


def scale_matrix(scale):
    matrix = Matrix.Identity(4)
    matrix[0][0], matrix[1][1], matrix[2][2] = scale
    return matrix


def _global_transform(index, transforms, parents, cache):
    cached = cache.get(index)
    if cached is not None:
        return cached

    transform = transforms[index]
    translation = transform["Translation"]
    rotation = transform["Rotation"]
    scale = transform.get("Scale", {"X": 1.0, "Y": 1.0, "Z": 1.0})
    translation_vector = Vector((translation["X"], translation["Y"], translation["Z"]))
    rotation_quaternion = Quaternion(
        (rotation["r"], rotation["i"], rotation["j"], rotation["k"])
    )
    scale_vector = Vector((scale["X"], scale["Y"], scale["Z"]))
    local_matrix = (
        Matrix.Translation(translation_vector)
        @ rotation_quaternion.to_matrix().to_4x4()
        @ scale_matrix(scale_vector)
    )
    parent_index = int(parents[index]) if index < len(parents) else -1
    matrix = (
        local_matrix
        if parent_index == -1
        else _global_transform(parent_index, transforms, parents, cache) @ local_matrix
    )
    cache[index] = matrix
    return matrix


def model_space_matrices_cached(transforms, parent_indices):
    cache_key = (id(transforms), id(parent_indices), len(transforms), len(parent_indices))
    cached = _MODEL_SPACE_MATRIX_CACHE.get(cache_key)
    if cached is not None and cached[0] is transforms and cached[1] is parent_indices:
        return cached[2]
    resolved = {}
    matrices = tuple(
        _global_transform(index, transforms, parent_indices, resolved)
        for index in range(len(transforms))
    )
    _bounded_cache_store(
        _MODEL_SPACE_MATRIX_CACHE,
        cache_key,
        (transforms, parent_indices, matrices),
    )
    return matrices


def build_apose_matrices(apose_ms, apose_ls, bone_names, parent_indices):
    bone_count = len(bone_names)
    if not isinstance(apose_ls, list) or len(apose_ls) != bone_count:
        return None
    if isinstance(apose_ms, list) and len(apose_ms) == bone_count:
        q_wxyz, translation, scale = trs_dicts_to_arrays(apose_ms)
        return [Matrix(matrix) for matrix in trs_to_matrices_np(q_wxyz, translation, scale)]
    return list(model_space_matrices_cached(apose_ls, parent_indices))


def children_by_parent(parent_indices):
    cache_key = id(parent_indices)
    cached = _PARENT_CHILDREN_CACHE.get(cache_key)
    if cached is not None and cached[0] is parent_indices and cached[1] == len(parent_indices):
        return cached[2]
    children = [[] for _ in range(len(parent_indices))]
    for child_index, parent_index in enumerate(parent_indices):
        parent_index = int(parent_index)
        if 0 <= parent_index < len(children):
            children[parent_index].append(child_index)
    _PARENT_CHILDREN_CACHE[cache_key] = (parent_indices, len(parent_indices), children)
    return children


def clear_parent_cache(parent_indices):
    _PARENT_CHILDREN_CACHE.pop(id(parent_indices), None)


def apply_bone_from_matrix(
    bone_index,
    matrix,
    edit_bones,
    parent_indices,
    global_transforms,
    default_length=0.01,
):
    active_object = bpy.context.object
    if active_object is None or getattr(active_object, "mode", None) != "EDIT":
        safe_mode_switch("EDIT")
    head = matrix.to_translation()

    distances = []
    for child_index in children_by_parent(parent_indices)[bone_index]:
        child_matrix = (
            global_transforms.get(child_index)
            if hasattr(global_transforms, "get")
            else global_transforms[child_index]
            if child_index < len(global_transforms)
            else None
        )
        if child_matrix is None:
            continue
        distance = (child_matrix.to_translation() - head).length
        if distance > 1e-6:
            distances.append(distance)
    length = max(
        sum(distances) / len(distances) if distances else default_length,
        default_length,
    )

    rotation = matrix.to_quaternion()
    if sum(component * component for component in rotation) < 1e-12:
        rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
    else:
        rotation.normalize()
    basis = rotation.to_matrix()
    y_axis = basis @ Vector((0.0, 1.0, 0.0))
    x_axis = basis @ Vector((1.0, 0.0, 0.0))
    if y_axis.length_squared < 1e-12:
        y_axis = Vector((0.0, 1.0, 0.0))
    else:
        y_axis.normalize()

    edit_bone = edit_bones[bone_index]
    edit_bone.head = head
    edit_bone.tail = head + y_axis * length
    edit_bone.align_roll(x_axis)
