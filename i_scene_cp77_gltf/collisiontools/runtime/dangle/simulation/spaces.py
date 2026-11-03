from mathutils import Matrix, Quaternion, Vector

from .....blender.armature_bones import (
    is_read_rig_armature,
    resolve_pose_bone,
    rig_space_contract,
)
from .....redSpace.contracts import (
    RIG_SPACE_CONTRACT_DIRECT,
    SUPPORTED_RIG_SPACE_CONTRACTS,
)
from .....redSpace.transforms import (
    current_bone_additive_matrix_to_red,
    current_bone_model_transform_to_red,
    red_additive_matrix_to_current_bone,
    red_axis_to_current_bone,
    red_local_transform_to_current_bone,
    red_model_transform_to_current_bone,
)
from ..preview_plan import executable_node_indices, preview_input_errors
from . import state_validation
from .state_validation import missing_dangle_bindings


def parent_red_rotation(parent_transform, arm_obj=None):
    """Engine model-space rotation of a bone given its Blender armature-space matrix"""
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        rotation = parent_transform.to_quaternion()
    else:
        rotation = Matrix(
            current_bone_model_transform_to_red(parent_transform)
        ).to_quaternion()
    rotation.normalize()
    return rotation


def re_axis_to_blender_bone(axis, arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return Vector(axis)
    return Vector(red_axis_to_current_bone(axis))


def re_local_transform_to_blender_bone(matrix, arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return matrix.copy()
    return Matrix(red_local_transform_to_current_bone(matrix))


def re_local_matrix(rotation, offset, arm_obj=None):
    """Blender bone-local matrix of an authored engine local transform (w, x, y, z rotation and offset)"""
    matrix = Quaternion(rotation).to_matrix().to_4x4()
    matrix.translation = Vector(offset)
    return re_local_transform_to_blender_bone(matrix, arm_obj)


def red_additive_transform_to_blender_bone(matrix, arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return matrix.copy()
    return Matrix(red_additive_matrix_to_current_bone(matrix))


def blender_bone_additive_transform_to_red(matrix, arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return matrix.copy()
    return Matrix(current_bone_additive_matrix_to_red(matrix))


def red_model_transform_to_blender_bone(matrix, arm_obj):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return matrix.copy()
    return Matrix(red_model_transform_to_current_bone(matrix))


def state_configuration_errors(state):
    try:
        active_dangles, _active_drags = executable_node_indices(state)
    except ValueError as error:
        return [str(error)]
    return preview_input_errors(
        state, active_dangles
    ) + state_validation.state_configuration_errors(
        state, active_dangles=active_dangles
    )


def dangle_node_missing_bones(arm_obj, state, node_index):
    return missing_dangle_bindings(
        state, node_index, lambda name: resolve_pose_bone(arm_obj, name)
    )


def armature_space_errors(arm_obj, tolerance=1e-5):
    if arm_obj is None or getattr(arm_obj, "type", None) != "ARMATURE":
        return ["The Dangle target must be an armature"]
    data = getattr(arm_obj, "data", None)
    stored_contract = data.get("cp77_rig_space_contract") if data is not None else None
    if (
        stored_contract is not None
        and stored_contract not in SUPPORTED_RIG_SPACE_CONTRACTS
    ):
        return [f"Unsupported CP77 rig-space contract: {stored_contract}"]
    if stored_contract is None and not is_read_rig_armature(arm_obj):
        return [
            "The Dangle target must be a read_rig armature/MetaRig or expose "
            "an explicit CP77 rig-space contract"
        ]
    matrix = arm_obj.matrix_world
    determinant = matrix.determinant()
    if abs(determinant) <= 1e-12:
        return ["The armature world transform is singular"]
    if determinant < 0.0:
        return [
            "The armature world transform is mirrored; apply transforms before "
            "running Dangle physics"
        ]
    scale = matrix.to_scale()
    if min(abs(value) for value in scale) <= 1e-8:
        return ["The armature has a zero world-scale axis"]
    if any(abs(abs(value) - 1.0) > tolerance for value in scale):
        return [
            "The armature object scale must be applied before running Dangle "
            "physics; world forces are converted by orientation only"
        ]
    return []


def world_position_to_model(arm_obj, position):
    return arm_obj.matrix_world.inverted_safe() @ Vector(position)


def world_vector_to_model(arm_obj, vector, *, direction=False):
    """A world-space position in the armature's space, or with direction a direction, turned but not moved"""
    matrix = arm_obj.matrix_world.inverted_safe()
    return (matrix.to_3x3() if direction else matrix) @ Vector(vector)


def previous_model_to_current_model(previous_matrix_world, current_matrix_world):
    return current_matrix_world.inverted_safe() @ previous_matrix_world
