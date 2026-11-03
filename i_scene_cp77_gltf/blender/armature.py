import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..animation.domain.rig.model_space import rig_model_matrices
from ..assetio.cache import store_bounded
from ..assetio.transform_values import parse_wkit_trs
from ..bartmoss.geometry import float32_direction_length
from ..bartmoss.hierarchy import children_by_parent
from ..bartmoss.matrix import as_matrix_4x4, matrix_is_identity, rigid_matrices
from ..bartmoss.trs import compose_matrices_wxyz
from .context import safe_mode_switch

_MODEL_SPACE_MATRIX_CACHE = {}
_CACHE_LIMIT = 64


def model_space_matrices_cached(transforms, parent_indices):
    cache_key = (
        id(transforms),
        id(parent_indices),
        len(transforms),
        len(parent_indices),
    )
    cached = _MODEL_SPACE_MATRIX_CACHE.get(cache_key)
    if cached is not None and cached[0] is transforms and cached[1] is parent_indices:
        return cached[2]
    matrices = tuple(
        Matrix(matrix) for matrix in rig_model_matrices(transforms, parent_indices)
    )
    store_bounded(
        _MODEL_SPACE_MATRIX_CACHE,
        cache_key,
        (transforms, parent_indices, matrices),
        limit=_CACHE_LIMIT,
    )
    return matrices


def build_apose_matrices(apose_ms, apose_ls, bone_names, parent_indices):
    bone_count = len(bone_names)
    if not isinstance(apose_ls, list) or len(apose_ls) != bone_count:
        return None
    if isinstance(apose_ms, list) and len(apose_ms) == bone_count:
        q_wxyz, translation, scale = parse_wkit_trs(
            apose_ms,
            quaternion_order="wxyz",
        )
        return [
            Matrix(matrix)
            for matrix in compose_matrices_wxyz(translation, q_wxyz, scale)
        ]
    return list(model_space_matrices_cached(apose_ls, parent_indices))


def rest_model_matrices(bones) -> np.ndarray:
    """The bones' rest matrices (matrix_local) without their float32 scale and shear noise"""
    return rigid_matrices([as_matrix_4x4(bone.matrix_local) for bone in bones])


def inheritance_issue(bone) -> str:
    """How bone departs from inheriting its parent's full transform with local location, or ''"""
    if bone.inherit_scale != "FULL":
        return f"uses unsupported inherit_scale={bone.inherit_scale!r}"
    if not bone.use_inherit_rotation:
        return "disables inherited rotation"
    if not bone.use_local_location:
        return "disables local location"
    return ""


# The orientation error a bone's float32 head and tail may carry.
BIND_PRECISION_TARGET = 1.0e-5


def precision_safe_bone_length(
    head, requested, target: float = BIND_PRECISION_TARGET
) -> float:
    """Raise a bone length until float32 head/tail can carry its orientation"""
    return max(float(requested), float32_direction_length(head, target))


def child_mean_bone_length(head, child_heads, default_length=0.01):
    """The mean distance from head to the child heads that do not coincide with it, at least default_length"""
    distances = []
    for child_head in child_heads:
        distance = (child_head - head).length
        if distance > 1e-6:
            distances.append(distance)
    return max(
        sum(distances) / len(distances) if distances else default_length,
        default_length,
    )


def set_edit_bone_model_matrices(
    edit_bones_by_index, model_matrices, parent_indices, *, default_length=0.01
):
    """Assign model-space matrices to edit bones by rig index"""
    children = children_by_parent(parent_indices)
    heads = tuple(matrix.to_translation() for matrix in model_matrices)
    for bone_index, matrix in enumerate(model_matrices):
        length = child_mean_bone_length(
            heads[bone_index],
            (
                heads[child_index]
                for child_index in children[bone_index]
                if child_index < len(heads)
            ),
            default_length,
        )
        edit_bone = edit_bones_by_index[bone_index]
        edit_bone.matrix = matrix
        edit_bone.length = precision_safe_bone_length(heads[bone_index], length)


def _place_edit_bone(edit_bone, matrix, length):
    """Point the bone's Y axis and roll its X axis along the matrix rotation's"""
    head = matrix.to_translation()
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

    edit_bone.head = head
    edit_bone.tail = head + y_axis * length
    edit_bone.align_roll(x_axis)


def apply_bind_matrices(edit_bones, matrices, parent_indices, *, skip_identity=False):
    """Place edit bones at model-space bind matrices by rig index"""
    children = children_by_parent(parent_indices)
    for index, matrix in enumerate(matrices):
        if skip_identity and (
            matrix is None or matrix_is_identity(matrix, tolerance=1e-6)
        ):
            continue
        active_object = bpy.context.object
        if active_object is None or getattr(active_object, "mode", None) != "EDIT":
            safe_mode_switch("EDIT")
        head = matrix.to_translation()
        length = child_mean_bone_length(
            head,
            (
                matrices[child_index].to_translation()
                for child_index in children[index]
                if child_index < len(matrices) and matrices[child_index] is not None
            ),
        )
        _place_edit_bone(edit_bones[index], matrix, length)
