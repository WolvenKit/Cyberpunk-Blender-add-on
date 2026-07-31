from __future__ import annotations

import bpy

from ....animation.bake import frame_sequence, sample_pose_bones, write_pose_bone_samples
from ....animation.bones import ANIMATION_BONE_SET
from ....animation.keyframes import assign_action_with_slot
from ....animation.rigify.mapping import DIRECTION_FORWARD
from ....blender.context import restore_previous_context, store_current_context
from ...model import OperationResult, RigifyBakeRequest
from .runtime import get_runtime
from .pairing import get_constraint_direction
from .sync import register_runtime, sync_runtime


def bake_to_source(context, source, rig, request: RigifyBakeRequest) -> OperationResult:
    if source is None or rig is None:
        return OperationResult(False, "No Rigify pair found for active object", "ERROR")
    if not rig.animation_data or rig.animation_data.action is None:
        return OperationResult(False, "Rigify rig has no action to bake", "ERROR")
    if request.frame_end < request.frame_start:
        return OperationResult(
            False,
            f"Invalid frame range: {request.frame_start} → {request.frame_end}",
            "ERROR",
        )

    action_name = request.action_name.strip() or f"{rig.animation_data.action.name}_baked"
    existing = bpy.data.actions.get(action_name)
    if existing is not None and not request.overwrite:
        return OperationResult(
            False,
            f"Action '{action_name}' already exists — enable Overwrite to replace",
            "ERROR",
        )
    if existing is not None:
        bpy.data.actions.remove(existing)

    target_action = bpy.data.actions.new(action_name)
    target_action.use_fake_user = True
    present_bones = []
    store_current_context()
    try:
        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError:
                pass
        for obj in tuple(context.selected_objects):
            obj.select_set(False)
        if source.hide_get():
            source.hide_set(False)
        source.select_set(True)
        context.view_layer.objects.active = source
        bpy.ops.object.mode_set(mode="POSE")

        if not source.animation_data:
            source.animation_data_create()
        assign_action_with_slot(source, target_action)
        present_bones = [
            pose_bone.name
            for pose_bone in source.pose.bones
            if pose_bone.name in ANIMATION_BONE_SET
        ]
        if not present_bones:
            bpy.data.actions.remove(target_action)
            return OperationResult(False, "No animation bones present on source rig", "ERROR")

        frames = frame_sequence(request.frame_start, request.frame_end, request.step)
        runtime = get_runtime(source)
        if runtime is None and get_constraint_direction(source) == DIRECTION_FORWARD:
            runtime = register_runtime(source, rig)
        before_sample = (lambda _frame: sync_runtime(runtime)) if runtime is not None else None
        if runtime is not None:
            runtime.manual_sync = True
        try:
            samples = sample_pose_bones(
                context.scene,
                source,
                present_bones,
                frames,
                before_sample=before_sample,
            )
        finally:
            if runtime is not None:
                runtime.manual_sync = False
        write_pose_bone_samples(
            target_action,
            source,
            frames,
            samples,
            interpolation="BEZIER",
        )
    except (KeyError, RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        if bpy.data.actions.get(target_action.name) is target_action:
            bpy.data.actions.remove(target_action)
        return OperationResult(False, f"Bake failed: {exc}", "ERROR")
    finally:
        restore_previous_context()

    return OperationResult(
        True,
        f"Baked '{target_action.name}' ({request.frame_start}→{request.frame_end}, "
        f"step {request.step}, {len(present_bones)} bones). Mute source constraints to play it standalone.",
        details={"action": target_action, "bone_count": len(present_bones)},
    )
