import bpy

try:
    from ...core.log import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(f"i_scene_cp77_gltf.user_scripts.{name}")


_LOG = get_logger(__name__)


def hide_extra_bones(context):

    animBones = [
        "Hips",
        "Spine",
        "Spine1",
        "Spine2",
        "Spine3",
        "LeftShoulder",
        "LeftArm",
        "LeftForeArm",
        "LeftHand",
        "WeaponLeft",
        "LeftInHandThumb",
        "LeftHandThumb1",
        "LeftHandThumb2",
        "LeftInHandIndex",
        "LeftHandIndex1",
        "LeftHandIndex2",
        "LeftHandIndex3",
        "LeftInHandMiddle",
        "LeftHandMiddle1",
        "LeftHandMiddle2",
        "LeftHandMiddle3",
        "LeftInHandRing",
        "LeftHandRing1",
        "LeftHandRing2",
        "LeftHandRing3",
        "LeftInHandPinky",
        "LeftHandPinky1",
        "LeftHandPinky2",
        "LeftHandPinky3",
        "RightShoulder",
        "RightArm",
        "RightForeArm",
        "RightHand",
        "WeaponRight",
        "RightInHandThumb",
        "RightHandThumb1",
        "RightHandThumb2",
        "RightInHandIndex",
        "RightHandIndex1",
        "RightHandIndex2",
        "RightHandIndex3",
        "RightInHandMiddle",
        "RightHandMiddle1",
        "RightHandMiddle2",
        "RightHandMiddle3",
        "RightInHandRing",
        "RightHandRing1",
        "RightHandRing2",
        "RightHandRing3",
        "RightInHandPinky",
        "RightHandPinky1",
        "RightHandPinky2",
        "RightHandPinky3",
        "Neck",
        "Neck1",
        "Head",
        "LeftEye",
        "RightEye",
        "LeftUpLeg",
        "LeftLeg",
        "LeftFoot",
        "LeftHeel",
        "LeftToeBase",
        "RightUpLeg",
        "RightLeg",
        "RightFoot",
        "RightHeel",
        "RightToeBase",
    ]

    selected_object = context.active_object

    if selected_object is not None and selected_object.type == "ARMATURE":
        armature = selected_object
    else:
        _LOG.warning("Select an armature object.")
        armature = None

    if armature:
        for pose_bone in armature.pose.bones:
            if pose_bone.name not in animBones:
                pose_bone.hide = True


hide_extra_bones(bpy.context)
