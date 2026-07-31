from __future__ import annotations

import os

import bpy

from ...animation.bones import ANIMATION_BONE_SET
from ...animation.rig import RigRepository
from ...assetio.documents import DocumentSession
from ...blender.animation_context import active_armature
from ...blender.armature import apply_bone_from_matrix, build_apose_matrices, model_space_matrices_cached
from ...blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ..model import OperationResult


def insert_pose_keyframes(context, *, frame_all: bool, step: int = 1) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    original_mode = context.mode
    if original_mode != "POSE":
        try:
            bpy.ops.object.mode_set(mode="POSE")
        except (RuntimeError, TypeError, ValueError) as exc:
            return OperationResult(False, f"Failed to switch to pose mode: {exc}", "ERROR")
    try:
        if not frame_all:
            bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
            return OperationResult(True, "Keyframe inserted at current frame.")
        if not armature.animation_data or not armature.animation_data.action:
            return OperationResult(False, "Armature has no animation data or action.", "ERROR")
        action = armature.animation_data.action
        start, end = map(int, action.frame_range)
        original_frame = context.scene.frame_current
        count = 0
        try:
            for frame in range(start, end + 1, max(1, int(step))):
                context.scene.frame_set(frame)
                bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
                count += 1
        finally:
            context.scene.frame_set(original_frame)
        return OperationResult(True, f"Inserted keyframes at {count} frames.", details={"count": count})
    except (RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Keyframe insertion failed: {exc}", "ERROR")
    finally:
        if context.mode != original_mode:
            safe_mode_switch(original_mode)


def load_bind_pose(armature, *, use_tpose: bool) -> OperationResult:
    armature_data = armature.data
    filepath = armature_data.get("source_rig_file", "")
    if not filepath or ";" in filepath or not os.path.isfile(filepath):
        return OperationResult(False, f"Invalid single-rig JSON source: {filepath}", "ERROR")
    with DocumentSession() as documents:
        rig = RigRepository(documents).load(filepath, required=True)
    matrices = (
        list(model_space_matrices_cached(rig.bone_transforms, rig.parent_indices))
        if use_tpose
        else build_apose_matrices(rig.apose_ms, rig.apose_ls, rig.bone_names, rig.parent_indices)
    )
    pose_name = "T-Pose" if use_tpose else "A-Pose"
    if not matrices:
        return OperationResult(False, f"No complete {pose_name} found in {rig.rig_name}", "ERROR")

    store_current_context()
    try:
        safe_mode_switch("EDIT")
        edit_bones = armature_data.edit_bones
        bone_map = {index: edit_bones.get(name) for index, name in enumerate(rig.bone_names)}
        missing = [rig.bone_names[index] for index, bone in bone_map.items() if bone is None]
        if missing:
            return OperationResult(
                False,
                f"Armature is missing {len(missing)} rig bones",
                "ERROR",
                details={"missing_bones": tuple(missing)},
            )
        for index, matrix in enumerate(matrices):
            apply_bone_from_matrix(index, matrix, bone_map, rig.parent_indices, matrices)
        armature_data["T-Pose"] = use_tpose
    finally:
        restore_previous_context()

    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis.identity()
    return OperationResult(True, f"{pose_name} loaded")


def set_extra_bones_hidden(context, hidden: bool) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature object.", "ERROR")
    affected = 0
    for pose_bone in armature.pose.bones:
        should_change = not hidden or pose_bone.name not in ANIMATION_BONE_SET
        if should_change:
            pose_bone.hide = hidden
            affected += 1
    armature.update_tag()
    if hidden:
        armature["deformBonesHidden"] = True
        return OperationResult(True, f"Hidden {affected} extra bones", details={"count": affected})
    if "deformBonesHidden" in armature:
        del armature["deformBonesHidden"]
    return OperationResult(True, f"Unhidden {affected} bones", details={"count": affected})
