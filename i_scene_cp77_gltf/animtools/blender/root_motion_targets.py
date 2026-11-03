from __future__ import annotations

from ...animation.domain.rig.naming import merged_bone_name
from ...blender.action_metadata import action_skin_extras


def target_bone_name(armature, source_name):
    return (
        source_name
        if armature.pose.bones.get(source_name)
        else merged_bone_name(source_name)
    )


def motion_targets(armature, root: str, source: str) -> tuple[str, str]:
    """The export root and motion source bones"""
    action = armature.animation_data.action
    names = action_skin_extras(action, armature).get("boneNames") or ()
    root_name = str(root)
    if not root_name:
        root_name = target_bone_name(armature, str(names[0])) if names else ""
        if root_name not in armature.pose.bones:
            root_name = next(
                (bone.name for bone in armature.pose.bones if bone.parent is None), ""
            )
    source_name = str(source)
    if not source_name:
        trajectory = next(
            (str(name) for name in names if str(name) == "Trajectory"),
            "Trajectory" if not names else "",
        )
        candidate = target_bone_name(armature, trajectory) if trajectory else ""
        source_name = (
            candidate
            if candidate != root_name and candidate in armature.pose.bones
            else ""
        )
    return root_name, source_name
