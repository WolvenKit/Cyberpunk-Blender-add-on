from __future__ import annotations

import time

import bpy

from ...animation.domain.clip.bake import frame_sequence
from ...assetio.resolver import resolve_asset_path
from ...blender.animation_context import (
    active_armature,
    track_action_curves,
    track_animation_data,
    track_id_properties,
    track_pose,
    track_scene_frames,
)
from ...blender.bake import sample_pose_bones, write_pose_bone_samples
from ...blender.context import safe_mode_switch, tag_view3d_redraw
from ...blender.facial import session as facial_session
from ...blender.facial.resources import load_resource
from ...blender.facial.solver import solve_session
from ...blender.keyframes import assign_action_with_slot, remove_fcurves
from ...blender.operator_results import OperationResult
from ...blender.pose import reset_pose_bones
from ...blender.transactions import new_tracked_datablock, transactional
from ...core.log import get_logger
from ..blender import facial_preview
from ..model.requests import FacialBakeRequest
from ..runtime import additive_preview
from ..runtime import facial as facial_runtime

_LOG = get_logger(__name__)
_BAKED_CHANNELS = (
    "location",
    "rotation_quaternion",
    "rotation_euler",
    "rotation_axis_angle",
    "scale",
)


def context_session(context):
    """The facial session of the active armature, binding the setup chosen in the panel when needed"""
    obj = active_armature(context)
    if obj is None:
        return None
    session = facial_session.ensure_session(obj)
    if session is not None:
        return session
    props = getattr(getattr(context, "scene", None), "cp77_facial", None)
    if props is None or not props.facial_json:
        return None
    try:
        resource = load_resource(obj, props.facial_json)
        return facial_session.bind_session(
            obj,
            resource.setup_path,
            resource.rig_path,
            rig=resource.rig,
            setup=resource.setup,
        )[0]
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        _LOG.warning(
            "Facial setup '%s' could not be bound to '%s': %s",
            props.facial_json,
            obj.name,
            error,
            exc_info=True,
        )
        return None


def _resolve_json_path(path_value: str, extension: str) -> str:
    resolved = resolve_asset_path(
        bpy.path.abspath(path_value),
        extensions=(extension,),
        warn=False,
    )
    if not resolved:
        raise FileNotFoundError(path_value)
    return resolved


def _clear_existing_preview(context, armature) -> None:
    existing = facial_session.get_session(armature)
    if existing is not None and existing.has_preview:
        facial_preview.clear_preview(existing)
        tag_view3d_redraw(context)


def _facial_pose_paths(armature, session) -> set[str]:
    """The transform channels a facial bake keys"""
    return {
        armature.pose.bones[bone.name].path_from_id(channel)
        for bone in session.used_pose_bones
        if bone is not None
        for channel in _BAKED_CHANNELS
    }


def _enter_pose_mode(armature) -> OperationResult | None:
    if armature.mode == "POSE":
        return None
    try:
        safe_mode_switch("POSE")
    except RuntimeError as exc:
        return OperationResult(False, f"Failed to enter pose mode: {exc}", "ERROR")
    return None


@transactional("Facial setup load")
def load(context, setup_path_value: str) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature first", "ERROR")
    if not setup_path_value:
        setup_path_value = facial_session.stored_paths(armature)[0]
    if not setup_path_value:
        return OperationResult(False, "Please select a facial setup JSON file", "ERROR")
    try:
        setup_path = _resolve_json_path(setup_path_value, ".facialsetup.json")
        resource = load_resource(armature, setup_path)
        started = time.perf_counter()
        _clear_existing_preview(context, armature)
        bound, missing = facial_session.bind_session(
            armature,
            resource.setup_path,
            resource.rig_path,
            rig=resource.rig,
            setup=resource.setup,
        )
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        _LOG.error(
            "Facial setup load failed: armature=%s setup=%s error=%s",
            armature.name,
            setup_path_value,
            exc,
            exc_info=True,
        )
        return OperationResult(False, f"Load failed: {exc}", "ERROR")
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    warning = f" ({len(missing)} bones missing)" if missing else ""
    message = (
        f"Loaded: {bound.rig.num_bones} bones, {bound.setup.face.num_main_poses} main poses, "
        f"{bound.setup.face.num_correctives} correctives{warning} [{elapsed_ms:.0f}ms]"
    )
    return OperationResult(
        True, message, warnings=tuple(missing), details={"session": bound}
    )


@transactional("Facial setup unbind")
def unbind(context, *, keep_properties: bool) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature first", "ERROR")
    _clear_existing_preview(context, armature)
    track_id_properties(armature, label="facial session properties")
    facial_session.remove_session(armature, keep_properties=keep_properties)
    return OperationResult(True, f"Unbound facial setup from '{armature.name}'")


def rebuild(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature first", "ERROR")
    _clear_existing_preview(context, armature)
    restored = facial_session.restore_session(armature)
    if restored is None:
        return OperationResult(False, "Session rebuild failed", "ERROR")
    facial_session.refresh_session(restored, check_sources=True)
    return OperationResult(True, f"Facial session rebuilt for '{armature.name}'")


def reset_neutral(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an Armature object.", "ERROR")
    failure = _enter_pose_mode(armature)
    if failure is not None:
        return failure
    reset_pose_bones(armature)
    armature.update_tag(refresh={"DATA"})
    context.view_layer.update()
    return OperationResult(True, "Facial pose reset to rest")


def reset_tracks(context) -> OperationResult:
    armature = active_armature(context)
    current = facial_session.get_session(armature)
    if current is None:
        return OperationResult(
            False, "No rig loaded. Bind facial setup first.", "ERROR"
        )
    count = 0
    for name in current.track_names:
        text = str(name)
        if text in armature:
            armature[text] = 0.0
            count += 1
    return OperationResult(
        True, f"Reset {count} tracks to zero", details={"count": count}
    )


def apply_main_pose(context, part: str, pose_index: int) -> OperationResult:
    current = context_session(context)
    if current is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    ok, message = facial_preview.apply_main_pose(current, part, pose_index)
    if ok:
        tag_view3d_redraw(context)
    return OperationResult(ok, message, "INFO" if ok else "ERROR")


def browse_pose(
    context, part: str, current_index: int, direction: int
) -> OperationResult:
    current = context_session(context)
    if current is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    part_data = getattr(current.setup, part, None)
    if part_data is None or part_data.num_main_poses <= 0:
        return OperationResult(False, f"No poses available for '{part}'", "WARNING")
    pose_index = (int(current_index) + int(direction)) % part_data.num_main_poses
    ok, message = facial_preview.apply_main_pose(current, part, pose_index)
    if ok:
        tag_view3d_redraw(context)
    return OperationResult(
        ok, message, "INFO" if ok else "ERROR", details={"pose_index": pose_index}
    )


def clear_preview(context) -> OperationResult:
    armature = active_armature(context)
    current = facial_session.get_session(armature)
    if current is None:
        return OperationResult(False, "No facial session for this armature.", "ERROR")
    ok, message = facial_preview.clear_preview(current)
    tag_view3d_redraw(context)
    return OperationResult(ok, message, "INFO" if ok else "ERROR")


@transactional("Facial bake")
def bake(context, request: FacialBakeRequest) -> OperationResult:
    armature = active_armature(context)
    current = context_session(context)
    if current is None or armature is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    if request.frame_end < request.frame_start:
        return OperationResult(False, "End frame must be >= start frame.", "ERROR")
    failure = _enter_pose_mode(armature)
    if failure is not None:
        return failure
    # Registered first so it is restored last: returning to the frame re-evaluates the restored Action.
    track_scene_frames(context.scene, label="facial bake frame")
    track_id_properties(armature, label="facial bake solver tracks")
    track_animation_data(armature, label="facial bake Action")
    track_pose(armature, label="facial bake pose")
    if not armature.animation_data:
        armature.animation_data_create()
    action = armature.animation_data.action
    if action is None:
        action = new_tracked_datablock("actions", name="FacialAnimation")
        assign_action_with_slot(armature, action)
    frames = frame_sequence(
        request.frame_start, request.frame_end, request.keyframe_step
    )
    bone_names = [bone.name for bone in current.used_pose_bones if bone is not None]
    track_action_curves(
        action,
        armature,
        _facial_pose_paths(armature, current),
        label="facial bake curves",
    )
    additive_composed = additive_preview.is_active(armature)
    try:
        # Each frame is solved once by before_sample; the frame-change handler would
        # otherwise solve it a second time during frame_set.
        with facial_runtime.frame_solver_suspended():
            samples = sample_pose_bones(
                context.scene,
                armature,
                bone_names,
                frames,
                before_sample=lambda _frame: solve_session(
                    current, lod=0, additive_composed=additive_composed
                ),
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
        _LOG.error(
            "Facial bake failed: armature=%s action=%s error=%s",
            armature.name,
            action.name,
            exc,
            exc_info=True,
        )
        return OperationResult(False, f"Facial bake failed: {exc}", "ERROR")
    armature.update_tag(refresh={"DATA"})
    context.view_layer.update()
    return OperationResult(
        True,
        f"Baked {len(frames)} frames ({request.frame_start}-{request.frame_end}).",
        details={"frames": len(frames)},
    )


def clear_animation(context) -> OperationResult:
    """Remove what a facial bake keys from the rig's own slot of its Action"""
    armature = active_armature(context)
    action = getattr(getattr(armature, "animation_data", None), "action", None)
    if action is None:
        return OperationResult(False, "No action found.", "INFO")
    current = context_session(context)
    if current is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    paths = _facial_pose_paths(armature, current)
    count = remove_fcurves(action, armature, lambda curve: curve.data_path in paths)
    return OperationResult(True, f"Cleared {count} F-curves.", details={"count": count})


def solve_now(scene) -> OperationResult:
    facial_runtime.solve_frame(
        scene, additive_armature=additive_preview.active_armature()
    )
    timing = facial_runtime.last_solve_timing()
    if timing:
        message = ", ".join(
            f"'{name}': {value:.1f} ms" for name, value in timing.items()
        )
        return OperationResult(True, "Solved — " + message)
    return OperationResult(True, "Solve complete")


def pose_preview_label(session, part: str, pose_index: int) -> tuple[int, str]:
    """Pose count of the part and the track name of the clamped pose index, for display"""
    count = facial_session.pose_count(session, part)
    clamped = max(0, min(int(pose_index), max(0, count - 1)))
    return count, facial_session.pose_track_name(session, part, clamped)
