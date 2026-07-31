from __future__ import annotations

import time

import bpy

from ....animation.bake import frame_sequence, sample_pose_bones, write_pose_bone_samples
from ....animation.keyframes import assign_action_with_slot, get_action_fcurves
from ....assetio.resolver import resolve_asset_path
from ....blender.animation_context import active_armature
from ...model import FacialBakeRequest, OperationResult
from . import preview, runtime, session


def load(context, rig_path_value: str, setup_path_value: str) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature first", "ERROR")
    if not rig_path_value:
        return OperationResult(False, "Please select a rig JSON file", "ERROR")
    if not setup_path_value:
        return OperationResult(False, "Please select a facial setup JSON file", "ERROR")
    try:
        setup_path = _resolve_json_path(setup_path_value, ".facialsetup.json")
        rig_path = _resolve_json_path(rig_path_value, ".rig.json")
        started = time.perf_counter()
        existing = session.get_session(armature)
        if existing is not None and existing.has_preview:
            preview.clear_preview(existing, context)
        bound, missing = session.bind_session(armature, setup_path, rig_path)
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Load failed: {exc}", "ERROR")
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    warning = f" ({len(missing)} bones missing)" if missing else ""
    message = (
        f"Loaded: {bound.rig.num_bones} bones, {bound.setup.face.num_main_poses} main poses, "
        f"{bound.setup.face.num_correctives} correctives{warning} [{elapsed_ms:.0f}ms]"
    )
    return OperationResult(True, message, warnings=tuple(missing), details={"session": bound})


def unbind(context, *, keep_properties: bool) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature first", "ERROR")
    current = session.get_session(armature)
    if current is not None and current.has_preview:
        preview.clear_preview(current, context)
    session.remove_session(armature, keep_properties=keep_properties)
    return OperationResult(True, f"Unbound facial setup from '{armature.name}'")


def rebuild(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature first", "ERROR")
    current = session.get_session(armature)
    if current is not None and current.has_preview:
        preview.clear_preview(current, context)
    restored = session.restore_session(armature)
    if restored is None:
        return OperationResult(False, "Session rebuild failed", "ERROR")
    session.refresh_session(restored, check_sources=True)
    return OperationResult(True, f"Facial session rebuilt for '{armature.name}'")


def reset_neutral(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an Armature object.", "ERROR")
    if armature.mode != "POSE":
        try:
            bpy.ops.object.mode_set(mode="POSE")
        except RuntimeError as exc:
            return OperationResult(False, f"Failed to enter pose mode: {exc}", "ERROR")
    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis.identity()
    armature.update_tag(refresh={"DATA"})
    context.view_layer.update()
    return OperationResult(True, "Facial pose reset to rest")


def reset_tracks(context) -> OperationResult:
    armature = active_armature(context)
    current = session.get_session(armature)
    if current is None:
        return OperationResult(False, "No rig loaded. Bind facial setup first.", "ERROR")
    count = 0
    for name in current.track_names:
        text = str(name)
        if text in armature:
            armature[text] = 0.0
            count += 1
    return OperationResult(True, f"Reset {count} tracks to zero", details={"count": count})


def apply_main_pose(context, part: str, pose_index: int) -> OperationResult:
    current = session.ensure_context_session(context)
    if current is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    ok, message = preview.apply_pose(current, part, pose_index, context)
    return OperationResult(ok, message, "INFO" if ok else "ERROR")


def browse_pose(context, part: str, current_index: int, direction: int) -> OperationResult:
    current = session.ensure_context_session(context)
    if current is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    part_data = getattr(current.setup, part, None)
    if part_data is None or part_data.num_main_poses <= 0:
        return OperationResult(False, f"No poses available for '{part}'", "WARNING")
    pose_index = (int(current_index) + int(direction)) % part_data.num_main_poses
    ok, message = preview.apply_pose(current, part, pose_index, context)
    return OperationResult(
        ok,
        message,
        "INFO" if ok else "ERROR",
        details={"pose_index": pose_index},
    )


def clear_preview(context) -> OperationResult:
    armature = active_armature(context)
    current = session.get_session(armature)
    if current is None:
        return OperationResult(False, "No facial session for this armature.", "ERROR")
    ok, message = preview.clear_preview(current, context)
    return OperationResult(ok, message, "INFO" if ok else "ERROR")


def bake(context, request: FacialBakeRequest) -> OperationResult:
    armature = active_armature(context)
    current = session.ensure_context_session(context)
    if current is None or armature is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    if request.frame_end < request.frame_start:
        return OperationResult(False, "End frame must be >= start frame.", "ERROR")
    if armature.mode != "POSE":
        try:
            bpy.ops.object.mode_set(mode="POSE")
        except RuntimeError as exc:
            return OperationResult(False, f"Failed to enter pose mode: {exc}", "ERROR")
    if not armature.animation_data:
        armature.animation_data_create()
    action = armature.animation_data.action
    if action is None:
        action = bpy.data.actions.new(name="FacialAnimation")
        assign_action_with_slot(armature, action)
    frames = frame_sequence(request.frame_start, request.frame_end, request.keyframe_step)
    bone_names = [bone.name for bone in current.used_pose_bones if bone is not None]
    try:
        samples = sample_pose_bones(
            context.scene,
            armature,
            bone_names,
            frames,
            before_sample=lambda _frame: runtime.solve_session(current, lod=0),
            rotation_path_override="rotation_quaternion",
        )
        write_pose_bone_samples(
            action,
            armature,
            frames,
            samples,
            interpolation="BEZIER",
            replace_frames=True,
        )
    except (KeyError, RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Facial bake failed: {exc}", "ERROR")
    armature.update_tag(refresh={"DATA"})
    context.view_layer.update()
    return OperationResult(
        True,
        f"Baked {len(frames)} frames ({request.frame_start}-{request.frame_end}).",
        details={"frames": len(frames)},
    )


def clear_animation(context) -> OperationResult:
    armature = active_armature(context)
    action = getattr(getattr(armature, "animation_data", None), "action", None)
    if action is None:
        return OperationResult(False, "No action found.", "INFO")
    fcurves = get_action_fcurves(action)
    if fcurves is None:
        return OperationResult(False, "No F-curves found.", "INFO")
    curves = list(fcurves)
    for fcurve in curves:
        fcurves.remove(fcurve)
    return OperationResult(True, f"Cleared {len(curves)} F-curves.", details={"count": len(curves)})


def _resolve_json_path(path_value: str, extension: str) -> str:
    resolved = resolve_asset_path(
        bpy.path.abspath(path_value),
        extensions=(extension,),
        warn=False,
    )
    if not resolved:
        raise FileNotFoundError(path_value)
    return resolved
