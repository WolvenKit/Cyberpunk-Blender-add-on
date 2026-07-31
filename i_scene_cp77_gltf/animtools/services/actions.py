from __future__ import annotations

import bpy

from ...animation.keyframes import assign_action_with_slot
from ...animation.metadata import ensure_action_defaults
from ...blender.animation_context import active_armature
from ..model import OperationResult


_ANIMATION_AREA_TYPES = {
    "VIEW_3D",
    "TIMELINE",
    "DOPESHEET_EDITOR",
    "GRAPH_EDITOR",
    "NLA_EDITOR",
}


def iter_local_actions():
    for action in bpy.data.actions:
        if action.library is None:
            yield action


def assign_action(animation_data, action):
    owner = getattr(animation_data, "id_data", None)
    if owner is None:
        animation_data.action = action
        return animation_data
    return assign_action_with_slot(owner, action)


def delete_action(name: str) -> OperationResult:
    action = bpy.data.actions.get(name)
    if action is None:
        return OperationResult(False, f"Action '{name}' not found", "WARNING")
    try:
        bpy.data.actions.remove(action)
    except (RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Failed to delete '{name}': {exc}", "ERROR")
    return OperationResult(True, f"Deleted '{name}'")


def toggle_simd(name: str) -> OperationResult:
    action = bpy.data.actions.get(name)
    if action is None:
        return OperationResult(False, f"Action '{name}' not found", "WARNING")
    ensure_action_defaults(action)
    hints = action["optimizationHints"]
    get_value = hints.get if hasattr(hints, "get") else lambda key, default=None: hints[key]
    prefer_simd = not bool(get_value("preferSIMD", False))
    action["optimizationHints"] = {
        "preferSIMD": prefer_simd,
        "maxRotationCompression": get_value("maxRotationCompression", 0),
        "simdQuantizationBits": get_value("simdQuantizationBits", 0),
    }
    label = "SIMD" if prefer_simd else "Compressed"
    return OperationResult(True, f"'{name}' encoding set to {label}")


def reset_armature(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis.identity()
    armature.update_tag(refresh={"DATA"})
    return OperationResult(True, "Armature pose reset")


def play_action(context, action_name: str) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    action = bpy.data.actions.get(action_name)
    if action is None:
        return OperationResult(False, f"Action '{action_name}' not found.", "ERROR")
    if armature.animation_data is None:
        armature.animation_data_create()
    assign_action(armature.animation_data, action)
    context.view_layer.objects.active = armature

    scene = context.scene
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    if end <= start:
        end = start + 1
    scene.frame_start = start
    scene.frame_end = end
    if not start <= scene.frame_current <= end:
        scene.frame_current = start

    screen = context.screen
    if screen and screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)

    override = _animation_override(context)
    if override is None:
        bpy.ops.screen.animation_play()
    else:
        with context.temp_override(**override):
            bpy.ops.screen.animation_play()
    return OperationResult(True, f"Playing '{action.name}'")


def _animation_override(context):
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return None
    for window in window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type not in _ANIMATION_AREA_TYPES:
                continue
            region = next((item for item in area.regions if item.type == "WINDOW"), None)
            if region is None:
                continue
            return {
                "window": window,
                "screen": screen,
                "area": area,
                "region": region,
                "scene": context.scene,
                "view_layer": context.view_layer,
            }
    return None


def set_action(context, name: str, *, new_name: str = "", play: bool = False) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    if armature.animation_data is None:
        armature.animation_data_create()
    if not name:
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

    reset = reset_armature(context)
    if not reset.ok:
        return reset
    if play:
        return play_action(context, action.name)
    assign_action(armature.animation_data, action)
    return OperationResult(True, f"Action '{action.name}' assigned")


def new_action(context, name: str) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    if not armature.animation_data:
        armature.animation_data_create()
    action = bpy.data.actions.new(name or "New action")
    action.use_fake_user = True
    reset = reset_armature(context)
    if not reset.ok:
        bpy.data.actions.remove(action)
        return reset
    assign_action(armature.animation_data, action)
    return OperationResult(True, f"Created '{action.name}'", details={"action": action})


def normalize_action_names() -> OperationResult:
    count = 0
    for action in iter_local_actions():
        normalized = action.name.replace(" ", "_").lower()
        if normalized != action.name:
            action.name = normalized
            count += 1
    return OperationResult(True, f"Normalized {count} action name(s)", details={"count": count})
