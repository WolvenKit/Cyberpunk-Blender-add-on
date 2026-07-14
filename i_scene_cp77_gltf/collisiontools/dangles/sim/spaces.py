from mathutils import Matrix, Vector


RIG_SPACE_CONTRACT_CURRENT = "CP77_RE_MODEL_BL_BONE_X_NEGZ_Y_Y_Z_X_V1"
RIG_SPACE_CONTRACT_DIRECT = "CP77_RE_MODEL_BL_BONE_DIRECT_V1"

# read_rig.apply_bone_from_matrix builds the Blender edit-bone basis as:
#   Blender X = -REDengine Z
#   Blender Y =  REDengine Y
#   Blender Z =  REDengine X
# This matrix converts REDengine bone-local coordinates into that Blender
# bone-local basis. Model/armature-space positions remain unchanged.
RE_TO_BLENDER_BONE_LOCAL_CURRENT = Matrix((
    (0.0, 0.0, -1.0, 0.0),
    (0.0, 1.0,  0.0, 0.0),
    (1.0, 0.0,  0.0, 0.0),
    (0.0, 0.0,  0.0, 1.0),
))
BLENDER_BONE_LOCAL_TO_RE_CURRENT = RE_TO_BLENDER_BONE_LOCAL_CURRENT.transposed()


def rig_space_contract(arm_obj):
    data = getattr(arm_obj, "data", None)
    if data is None:
        return RIG_SPACE_CONTRACT_CURRENT
    return data.get("cp77_rig_space_contract", RIG_SPACE_CONTRACT_CURRENT)


def re_to_blender_bone_local_matrix(arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return Matrix.Identity(4)
    return RE_TO_BLENDER_BONE_LOCAL_CURRENT


def blender_bone_local_to_re_matrix(arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return Matrix.Identity(4)
    return BLENDER_BONE_LOCAL_TO_RE_CURRENT


def re_axis_to_blender_bone(axis, arm_obj=None):
    return re_to_blender_bone_local_matrix(arm_obj).to_3x3() @ Vector(axis)


def blender_bone_axis_to_re(axis, arm_obj=None):
    return blender_bone_local_to_re_matrix(arm_obj).to_3x3() @ Vector(axis)


def re_local_transform_to_blender_bone(matrix, arm_obj=None):
    return re_to_blender_bone_local_matrix(arm_obj) @ matrix


def world_direction_to_model(arm_obj, direction):
    return arm_obj.matrix_world.to_quaternion().inverted() @ Vector(direction)


def previous_model_to_current_model(previous_matrix_world, current_matrix_world):
    # p_world = previous_world @ p_previous_model
    # p_current_model = inverse(current_world) @ p_world
    return current_matrix_world.inverted_safe() @ previous_matrix_world
