from __future__ import annotations

from rna_prop_ui import rna_idprop_ui_prop_update

from ....animation.domain.rigify.controls import (
    LIMBS,
    TORSO_SELECTION,
    limb_descriptor,
    limb_selection,
)

IK_FK = "IK_FK"
_LIMB_SWITCHES = (IK_FK, "IK_Stretch", "FK_limb_follow", "pole_vector")
_TORSO_SWITCHES = (
    ("torso", "torso_parent"),
    ("head", "neck_follow"),
    ("head", "head_follow"),
)


def limb_switch_bones(rig) -> list:
    """The pose bones that hold each limb's IK-FK switch"""
    pose = getattr(rig, "pose", None)
    if pose is None:
        return []
    bones = (
        pose.bones.get(limb_descriptor(side, is_leg=is_leg)["prop_bone"])
        for _label, _kind, side, is_leg in LIMBS
    )
    return [bone for bone in bones if bone is not None and IK_FK in bone]


def all_limbs_ik_fk(rig) -> float:
    """The limbs' IK-FK switches averaged, 0 for IK and 1 for FK"""
    bones = limb_switch_bones(rig)
    return sum(float(bone[IK_FK]) for bone in bones) / len(bones) if bones else 0.0


def set_all_limbs_ik_fk(rig, value: float) -> None:
    """Move every limb's IK-FK switch to value, each still editable on its own afterwards"""
    for bone in limb_switch_bones(rig):
        bone[IK_FK] = value
        # Drivers read the switch, so they need the same update the limb's own slider sends.
        rna_idprop_ui_prop_update(bone, IK_FK)


def selected_switch_channels(rig, selected_names) -> tuple:
    """(rig, data path, index, group) for the switches of each limb, and of the torso and head, a selected control moves"""
    selected = set(selected_names)
    owners = []
    for _label, _kind, side, is_leg in LIMBS:
        if selected & limb_selection(side, is_leg=is_leg):
            prop_bone = limb_descriptor(side, is_leg=is_leg)["prop_bone"]
            owners.extend((prop_bone, name) for name in _LIMB_SWITCHES)
    if selected & TORSO_SELECTION:
        owners.extend(_TORSO_SWITCHES)
    channels = []
    for bone_name, prop in owners:
        bone = rig.pose.bones.get(bone_name)
        if bone is not None and prop in bone:
            channels.append((rig, bone.path_from_id(f'["{prop}"]'), -1, bone_name))
    return tuple(channels)
