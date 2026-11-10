from __future__ import annotations

from contextlib import contextmanager

import bpy
from bpy.app.handlers import persistent

from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)
_STATE = {"syncing": 0, "last_active": None}
_PENDING = {"scheduled": False, "separate": False, "follow": False}


@contextmanager
def syncing():
    """Selection changes made by the tool itself"""
    _STATE["syncing"] += 1
    try:
        yield
    finally:
        _STATE["syncing"] -= 1


def _active_pointer(context):
    obj = getattr(getattr(context, "view_layer", None), "objects", None)
    active = getattr(obj, "active", None) if obj is not None else None
    return active.as_pointer() if active is not None else None


def _collections_changed(depsgraph) -> bool:
    return depsgraph is not None and any(
        isinstance(update.id, bpy.types.Collection) for update in depsgraph.updates
    )


def _run_pending():
    """Separate renamed meshes and follow the active object after the update that asked for it"""
    _PENDING["scheduled"] = False
    separate, follow = _PENDING["separate"], _PENDING["follow"]
    _PENDING["separate"] = _PENDING["follow"] = False
    context = bpy.context
    if separate:
        try:
            from ..services.components import separate_renamed_meshes

            with syncing():
                separate_renamed_meshes()
        except Exception:
            _LOG.warning(
                "Renamed mesh separation failed; later edits may change a mesh other objects share",
                exc_info=True,
            )
    if follow and getattr(context.scene, "cp77_entity_tools", None) is not None:
        try:
            from ..services.selection import follow_active_object

            follow_active_object(context)
        except Exception:
            debug_exception(_LOG, "Entity selection sync skipped")


@persistent
def on_depsgraph_update(scene, depsgraph=None):
    context = bpy.context
    if _collections_changed(depsgraph) and not _STATE["syncing"]:
        _PENDING["separate"] = True
    pointer = _active_pointer(context)
    if pointer != _STATE["last_active"]:
        _STATE["last_active"] = pointer
        if (
            not _STATE["syncing"]
            and getattr(context.scene, "cp77_entity_tools", None) is not None
        ):
            _PENDING["follow"] = True
    if (_PENDING["separate"] or _PENDING["follow"]) and not _PENDING["scheduled"]:
        _PENDING["scheduled"] = True
        bpy.app.timers.register(_run_pending, first_interval=0.0)


@persistent
def reset_selection_sync(_unused=None):
    if bpy.app.timers.is_registered(_run_pending):
        bpy.app.timers.unregister(_run_pending)
    _PENDING.update(scheduled=False, separate=False, follow=False)
    _STATE["syncing"] = 0
    _STATE["last_active"] = None
