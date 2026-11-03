from __future__ import annotations

import bpy

from ...core.log import get_logger
from .updates import suspended

_LOG = get_logger(__name__)
_PENDING = {"scheduled": False}


def choices_key(entity: str, appearance: str, component_index: int) -> str:
    return f"{entity}|{appearance}|{component_index}"


def _refresh():
    _PENDING["scheduled"] = False
    context = bpy.context
    try:
        from ..blender.state import ensure_appearance_state
        from ..services.selection import current_collection, refresh_choices

        collection = current_collection(context)
        if collection is not None:
            ensure_appearance_state(collection)
        refresh_choices(context)
        tools = context.scene.cp77_entity_tools
        with suspended():
            tools.choices_key = choices_key(
                tools.entity, tools.appearance, tools.component_index
            )
        for area in getattr(context.screen, "areas", ()):
            if area.type == "VIEW_3D":
                area.tag_redraw()
    except Exception as error:
        _LOG.error("Entity panel refresh failed: %s", error, exc_info=True)


def schedule_refresh() -> None:
    if _PENDING["scheduled"]:
        return
    _PENDING["scheduled"] = True
    bpy.app.timers.register(_refresh, first_interval=0.0)


def cancel_refresh() -> None:
    if bpy.app.timers.is_registered(_refresh):
        bpy.app.timers.unregister(_refresh)
    _PENDING["scheduled"] = False
