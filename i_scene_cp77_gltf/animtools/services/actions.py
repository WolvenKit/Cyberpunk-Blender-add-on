from __future__ import annotations

import bpy

from ...animation.domain.clip.additive import next_editable_additive_type
from ...animation.model.clip.metadata import prefers_simd, with_simd_preference
from ...blender.action_metadata import (
    action_is_additive,
    action_playback_frame_bounds,
    ensure_action_defaults,
)
from ...blender.animation_context import (
    active_armature,
    local_actions,
    track_animation_data,
    track_pose,
    track_scene_frames,
)
from ...blender.keyframes import assign_action_with_slot
from ...blender.operator_results import OperationResult
from ...blender.pose import reset_pose_bones
from ...blender.transactions import transactional
from ...core.log import get_logger
from ..blender import playback
from ..model.additive import ActionListSlot
from ..runtime import additive_preview as additive_runtime
from . import additive as additive_service

_LOG = get_logger(__name__)


def action_counts() -> tuple[int, int]:
    """Number of normal and additive actions in the file"""
    additive_count = sum(1 for action in bpy.data.actions if action_is_additive(action))
    return len(bpy.data.actions) - additive_count, additive_count


def _select_in_list(settings, slot: ActionListSlot, action) -> None:
    if settings is None:
        return
    for index, candidate in enumerate(bpy.data.actions):
        if candidate == action:
            if int(getattr(settings, slot.selector, -1)) != index:
                setattr(settings, slot.selector, index)
            return


def delete_action(context, name: str) -> OperationResult:
    action = bpy.data.actions.get(name)
    if action is None:
        return OperationResult(False, f"Action '{name}' not found", "WARNING")
    if additive_runtime.references_action(name):
        stopped = additive_service.stop(context)
        if not stopped.ok:
            return stopped
    try:
        bpy.data.actions.remove(action)
    except (RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        _LOG.error("Action delete failed: action=%s error=%s", name, exc, exc_info=True)
        return OperationResult(False, f"Failed to delete '{name}': {exc}", "ERROR")
    return OperationResult(True, f"Deleted '{name}'")


def toggle_simd(name: str) -> OperationResult:
    action = bpy.data.actions.get(name)
    if action is None:
        return OperationResult(False, f"Action '{name}' not found", "WARNING")
    ensure_action_defaults(action)
    hints = action["optimizationHints"]
    prefer = not prefers_simd(hints)
    action["optimizationHints"] = with_simd_preference(hints, prefer)
    label = "SIMD" if prefer else "Compressed"
    return OperationResult(True, f"'{name}' encoding set to {label}")


def cycle_additive_type(context, name: str) -> OperationResult:
    action = bpy.data.actions.get(name)
    if action is None:
        return OperationResult(False, f"Action '{name}' not found", "WARNING")
    animation_type = next_editable_additive_type(
        action.get("animationType", "AdditiveFromRefPose")
    )
    action["animationType"] = animation_type
    if additive_runtime.is_active(active_armature(context)):
        additive_service.reconfigure(context)
    return OperationResult(True, f"Type: {animation_type}")


def reset_armature(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    if additive_runtime.is_active(armature):
        stopped = additive_service.stop(context)
        if not stopped.ok:
            return stopped
    reset_pose_bones(armature)
    armature.update_tag(refresh={"DATA"})
    return OperationResult(True, "Armature pose reset")


@transactional("Action playback")
def play_action(context, action_name: str) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    action = bpy.data.actions.get(action_name)
    if action is None:
        return OperationResult(False, f"Action '{action_name}' not found.", "ERROR")

    if additive_runtime.is_active(armature):
        stopped = additive_service.stop(context)
    else:
        stopped = playback.stop(context)
    if not stopped.ok:
        return stopped

    track_pose(armature, label="action playback pose")
    track_animation_data(armature, label="action playback Action")
    track_scene_frames(context.scene, label="action playback frame range")
    reset = reset_armature(context)
    if not reset.ok:
        return reset

    if armature.animation_data is None:
        armature.animation_data_create()
    assign_action_with_slot(armature, action)
    context.view_layer.objects.active = armature

    scene = context.scene
    start, end = action_playback_frame_bounds(action)
    scene.frame_start = start
    scene.frame_end = end
    if not start <= scene.frame_current <= end:
        scene.frame_current = start

    started = playback.start(context, label=f"'{action.name}'")
    if not started.ok:
        return started
    return OperationResult(True, f"Playing '{action.name}'")


def _primary_action_for_secondary(settings):
    primary_index = (
        int(getattr(settings, ActionListSlot.PRIMARY.selector, -1))
        if settings is not None
        else -1
    )
    if 0 <= primary_index < len(bpy.data.actions):
        candidate = bpy.data.actions[primary_index]
        if action_is_additive(candidate):
            return candidate
    return None


def _set_additive_action(
    context, armature, action, settings, slot: ActionListSlot, play: bool
) -> OperationResult:
    selector = (
        ActionListSlot.SECONDARY
        if slot is ActionListSlot.SECONDARY
        else ActionListSlot.PRIMARY
    )
    _select_in_list(settings, selector, action)
    mixer_enabled = (
        bool(getattr(settings, "mixer_enabled", False))
        if settings is not None
        else False
    )
    if slot is ActionListSlot.SECONDARY and settings is not None:
        settings.secondary_action = action.name
    if mixer_enabled:
        if slot is ActionListSlot.SECONDARY:
            if additive_runtime.is_active(armature):
                primary_name = additive_runtime.active_action_name(armature)
                return additive_service.start(context, primary_name, play=play)
            primary = _primary_action_for_secondary(settings)
            if primary is None:
                return OperationResult(True, f"Second additive set to '{action.name}'")
            return additive_service.start(context, primary.name, play=play)
        return additive_service.start(context, action.name, play=play)
    if slot is ActionListSlot.SECONDARY and not play:
        return OperationResult(True, f"Second additive set to '{action.name}'")
    return additive_service.start(
        context,
        action.name,
        play=play,
        force_reference_base=True,
        include_secondary=False,
        standalone=True,
    )


def set_action(
    context,
    name: str,
    *,
    new_name: str = "",
    play: bool = False,
    slot: ActionListSlot = ActionListSlot.NORMAL,
) -> OperationResult:
    """Assign, detach, rename or preview the clicked list action, depending on the list it came from"""
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    if armature.animation_data is None:
        armature.animation_data_create()
    if not name:
        if additive_runtime.is_active(armature):
            stopped = additive_service.stop(context)
            if not stopped.ok:
                return stopped
        armature.animation_data.action = None
        return OperationResult(True, "Action cleared")

    action = bpy.data.actions.get(name)
    if action is None:
        return OperationResult(False, f"Action '{name}' not found", "ERROR")
    action.use_fake_user = True
    if new_name:
        action.name = new_name
        return OperationResult(True, f"Action renamed to '{new_name}'")
    if not play and armature.animation_data.action == action:
        armature.animation_data.action = None
        return OperationResult(True, f"Action '{name}' detached")

    settings = additive_service.preview_settings(context)
    if action_is_additive(action):
        return _set_additive_action(context, armature, action, settings, slot, play)
    _select_in_list(settings, ActionListSlot.NORMAL, action)

    if additive_runtime.is_active(armature):
        if (
            bool(getattr(settings, "mixer_enabled", False))
            if settings is not None
            else False
        ):
            result = additive_service.reconfigure(context)
            if not result.ok:
                return result
            if play:
                return playback.start(context, label=f"mixer '{action.name}'")
            return OperationResult(True, f"Mixer base set to '{action.name}'")
        stopped = additive_service.stop(context, stop_playback=False)
        if not stopped.ok:
            return stopped

    if play:
        return play_action(context, action.name)

    reset = reset_armature(context)
    if not reset.ok:
        return reset
    assign_action_with_slot(armature, action)
    return OperationResult(True, f"Action '{action.name}' assigned")


@transactional("New action")
def new_action(context, name: str, *, additive: bool = False) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    track_animation_data(armature, label="new Action")
    track_pose(armature, label="new Action pose")
    if not armature.animation_data:
        armature.animation_data_create()
    action = bpy.data.actions.new(name or "New action")
    action.use_fake_user = True
    action["animationType"] = "AdditiveFromRefPose" if additive else "Normal"
    reset = reset_armature(context)
    if not reset.ok:
        return reset
    assign_action_with_slot(armature, action)
    return OperationResult(True, f"Created '{action.name}'", details={"action": action})


def normalize_action_names() -> OperationResult:
    count = 0
    for action in local_actions():
        normalized = action.name.replace(" ", "_").lower()
        if normalized != action.name:
            action.name = normalized
            count += 1
    return OperationResult(
        True, f"Normalized {count} action name(s)", details={"count": count}
    )
