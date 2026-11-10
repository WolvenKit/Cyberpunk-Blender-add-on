from __future__ import annotations

import bpy

from ...blender.operator_results import OperationResult

_ANIMATION_AREA_TYPES = {
    "VIEW_3D",
    "TIMELINE",
    "DOPESHEET_EDITOR",
    "GRAPH_EDITOR",
    "NLA_EDITOR",
}


def start(context, *, label: str = "animation") -> OperationResult:
    override = _animation_override(context)
    screen = (
        override.get("screen")
        if override is not None
        else getattr(context, "screen", None)
    )
    if screen is not None and screen.is_animation_playing:
        return OperationResult(True)
    try:
        if override is None:
            result = bpy.ops.screen.animation_play()
        else:
            with context.temp_override(**override):
                result = bpy.ops.screen.animation_play()
    except (RuntimeError, TypeError, ValueError) as exc:
        return OperationResult(
            False,
            f"Could not start playback for {label}: {exc}",
            "ERROR",
            error=exc,
        )

    if "FINISHED" not in result and not (
        screen is not None and screen.is_animation_playing
    ):
        return OperationResult(False, f"Could not start playback for {label}.", "ERROR")
    return OperationResult(True)


def stop(context) -> OperationResult:
    for window in tuple(_iter_playing_windows(context)):
        screen = window.screen
        if not screen.is_animation_playing:
            continue
        override = _animation_override(context, window=window)
        try:
            if override is None:
                result = bpy.ops.screen.animation_cancel(restore_frame=False)
            else:
                with context.temp_override(**override):
                    result = bpy.ops.screen.animation_cancel(restore_frame=False)
        except (RuntimeError, TypeError, ValueError) as exc:
            if not screen.is_animation_playing:
                continue
            return OperationResult(
                False,
                f"Could not stop the current animation playback: {exc}",
                "ERROR",
                error=exc,
            )

        if "FINISHED" not in result and screen.is_animation_playing:
            return OperationResult(
                False, "Could not stop the current animation playback.", "ERROR"
            )
    return OperationResult(True)


def _iter_playing_windows(context):
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return
    for window in tuple(window_manager.windows):
        screen = getattr(window, "screen", None)
        if screen is not None and screen.is_animation_playing:
            yield window


def _animation_override(context, *, window=None):
    windows = []
    if window is not None:
        windows.append(window)
    else:
        context_window = getattr(context, "window", None)
        if context_window is not None:
            windows.append(context_window)
        window_manager = getattr(context, "window_manager", None)
        if window_manager is not None:
            windows.extend(
                item for item in window_manager.windows if item not in windows
            )

    fallback = None
    for candidate in windows:
        screen = getattr(candidate, "screen", None)
        if screen is None:
            continue
        if fallback is None:
            fallback = {
                "window": candidate,
                "screen": screen,
                "scene": context.scene,
                "view_layer": context.view_layer,
            }
        for area in screen.areas:
            if area.type not in _ANIMATION_AREA_TYPES:
                continue
            region = next(
                (item for item in area.regions if item.type == "WINDOW"), None
            )
            if region is None:
                continue
            return {
                "window": candidate,
                "screen": screen,
                "area": area,
                "region": region,
                "scene": context.scene,
                "view_layer": context.view_layer,
            }
    return fallback
