from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ...blender.animgraph import node_lod, sm_links, sm_overlay
from ...blender.tracks import clear_track_property_cache
from ...core.log import get_logger
from . import additive_preview, facial, overlay, read_models

_LOG = get_logger(__name__)


def _call(label: str, function, *args, **kwargs) -> None:
    """Run one runtime step so that a failure is logged without skipping the steps after it"""
    try:
        function(*args, **kwargs)
    except Exception:
        _LOG.exception("Animation Tools %s failed", label)


@persistent
def on_frame_change_post(scene, _depsgraph=None) -> None:
    # The facial solver reads tracks the additive preview has just composed, so it runs second.
    _call("additive preview frame", additive_preview.evaluate_frame, scene)
    _call(
        "facial solve",
        facial.solve_frame,
        scene,
        additive_armature=additive_preview.active_armature(),
    )
    # Last, so the lines are rebuilt from the poses written above.
    _call("bone overlay frame invalidation", overlay.invalidate_frame)


@persistent
def on_depsgraph_update_post(_scene, depsgraph=None) -> None:
    _call("bone overlay invalidation", overlay.invalidate, depsgraph)


@persistent
def on_load_pre(*_args) -> None:
    _call("additive preview reset", additive_preview.clear, restore=False)
    _call("facial session reset", facial.clear_sessions)
    _call("facial resource reset", facial.clear_resources)
    _call("bone overlay reset", overlay.stop)
    _call("read model reset", read_models.clear)
    _call("track property cache reset", clear_track_property_cache)
    _call("AnimGraph pending link reset", sm_links.reset_before_load)
    _call("AnimGraph node detail reset", node_lod.reset)


@persistent
def on_load_post(*_args) -> None:
    _call(
        "facial solver reset",
        facial.reset_after_load,
        getattr(bpy.context, "scene", None),
    )
    _call("AnimGraph overlay reset", sm_overlay.on_file_loaded)
    _call("AnimGraph dragged link cleanup", sm_links.discard_dragged_links)


@persistent
def on_history_pre(*_args) -> None:
    _call("facial session reset", facial.clear_sessions)


@persistent
def on_history_post(*_args) -> None:
    _call("facial session restore", facial.restore_sessions)
    _call("AnimGraph overlay refresh", sm_overlay.on_undo_redo)
    _call("AnimGraph node detail reset", node_lod.reset)
    _call("AnimGraph dragged link cleanup", sm_links.discard_dragged_links)


HANDLERS = (
    ("frame_change_post", on_frame_change_post),
    ("depsgraph_update_post", on_depsgraph_update_post),
    ("load_pre", on_load_pre),
    ("load_post", on_load_post),
    ("undo_pre", on_history_pre),
    ("redo_pre", on_history_pre),
    ("undo_post", on_history_post),
    ("redo_post", on_history_post),
)


def shutdown() -> None:
    """Release every runtime owned by Animation Tools"""
    _call("additive preview shutdown", additive_preview.clear, restore=True)
    _call("bone overlay shutdown", overlay.stop)
    _call("facial session shutdown", facial.clear_sessions)
    _call("facial resource shutdown", facial.clear_resources)
    _call("read model shutdown", read_models.clear)
    _call("track property cache shutdown", clear_track_property_cache)
    _call("AnimGraph pending link shutdown", sm_links.clear_pending)
    _call("AnimGraph node detail shutdown", node_lod.reset)
