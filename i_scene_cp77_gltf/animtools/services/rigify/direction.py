from __future__ import annotations

from typing import Tuple

from ....animation.rigify.mapping import (
    CP77_TO_METARIG,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    REVERSE_CONSTRAINT,
    reverse_target_for,
)
from ....blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ....blender.selection import select_objects
from .pairing import get_constraint_direction
from .sync import clear_forward_constraints, disable_forward_sync, enable_forward_sync

def _make_copy_transforms(pose_bone, name: str, target, subtarget: str):
    existing = pose_bone.constraints.get(name)
    if existing is not None:
        pose_bone.constraints.remove(existing)
    constraint = pose_bone.constraints.new("COPY_TRANSFORMS")
    constraint.name = name
    constraint.target = target
    constraint.subtarget = subtarget
    constraint.target_space = "WORLD"
    constraint.owner_space = "WORLD"
    if hasattr(constraint, "use_offset"):
        constraint.use_offset = False
    if hasattr(constraint, "mix_mode"):
        constraint.mix_mode = "REPLACE"
    return constraint

def _set_constraint_mute(armature, constraint_name: str, mute: bool) -> int:
    count = 0
    for pose_bone in armature.pose.bones:
        constraint = pose_bone.constraints.get(constraint_name)
        if constraint is not None:
            constraint.mute = mute
            count += 1
    return count

def build_reverse_constraints(source, rig) -> int:
    rig_names = set(rig.data.bones.keys())
    select_objects(rig)
    safe_mode_switch("POSE")
    count = 0
    for source_bone in source.pose.bones:
        metarig_name = CP77_TO_METARIG.get(source_bone.name)
        target_name = reverse_target_for(source_bone.name, metarig_name, rig_names)
        if not target_name:
            continue
        target_pose_bone = rig.pose.bones.get(target_name)
        if target_pose_bone is None:
            continue
        _make_copy_transforms(target_pose_bone, REVERSE_CONSTRAINT, source, source_bone.name)
        count += 1
    return count

def set_constraint_direction(source, rig, direction: str) -> Tuple[bool, str]:
    if direction not in (DIRECTION_FORWARD, DIRECTION_REVERSE):
        return False, f"Unknown direction '{direction}'"
    if source is None or rig is None:
        return False, "Missing source or rigify rig"
    store_current_context()
    try:
        if direction == DIRECTION_FORWARD:
            _set_constraint_mute(rig, REVERSE_CONSTRAINT, True)
            synced = enable_forward_sync(source, rig)
            message = f"Forward: rigify drives source ({synced} synced bones)"
        else:
            disable_forward_sync(source)
            built = 0
            has_reverse = any(
                pose_bone.constraints.get(REVERSE_CONSTRAINT) is not None
                for pose_bone in rig.pose.bones
            )
            if not has_reverse:
                built = build_reverse_constraints(source, rig)
            clear_forward_constraints(source)
            unmuted = _set_constraint_mute(rig, REVERSE_CONSTRAINT, False)
            suffix = f", built {built}" if built else ""
            message = f"Reverse: source drives rigify ({unmuted} bones{suffix})"
        source.data["cp77_constraint_direction"] = direction
    finally:
        restore_previous_context()
    return True, message
