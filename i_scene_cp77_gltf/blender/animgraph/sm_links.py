from __future__ import annotations

from functools import partial

import bpy

from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...core.log import debug_exception, get_logger, log_once
from . import sm_edit, sm_records, sm_sockets

_LOG = get_logger(__name__)

UNDO_MESSAGE = "Edit Transition"

# Names of trees with a consume pass registered but not yet run.
_PENDING: set = set()
# Tree name -> the timer callback registered for it (so a file load can cancel it).
_CALLBACKS: dict = {}


def _is_row_link(link) -> bool:
    """True for a link dragged from a transition row / T+ socket"""
    try:
        return link.from_socket.bl_idname == sm_sockets.ROW_SOCKET_ID
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_is_row_link", type(error).__name__),
            "is row link: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _dropped_state(tree, link):
    """The State node the link was dropped on, or None if it is not a valid target"""
    try:
        to_node, to_socket = link.to_node, link.to_socket
        if to_socket.bl_idname != sm_sockets.IN_SOCKET_ID or to_node.id_data != tree:
            return None
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_dropped_state", type(error).__name__),
            "dropped state: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    return to_node if sm_edit.is_state(to_node) else None


def _resolve(tree, link):
    """(owner, row, target) for link, or None when it is not a valid drop"""
    try:
        owner, row = link.from_node, int(link.from_socket.red_row_index)
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_resolve", type(error).__name__),
            "resolve: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    target = _dropped_state(tree, link)
    if target is None or getattr(owner, "red_transitions", None) is None:
        return None
    if not sm_edit.is_transition_owner(owner):
        return None
    return owner, row, target


def _apply(owner, row, target) -> None:
    """Add a transition or retarget row row"""
    records = owner.red_transitions
    try:
        if row < 0:
            sm_edit.add_transition(owner, target)
        elif row < len(records):
            sm_edit.set_target(records[row], target)
    except ValueError:
        pass


def _key(link):
    try:
        return link.as_pointer()
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_key", type(error).__name__),
            "key: fell back after %s",
            error,
            exc_info=True,
        )
        return id(link)


def _row_links(tree) -> list:
    return [link for link in list(tree.links) if _is_row_link(link)]


def consume_transition_links(tree) -> int:
    """Edit records for every link dragged from a transition socket and remove those links"""
    if tree is None or sm_records.sm_container_for(tree) is None:
        return 0
    count = 0
    handled: set = set()
    for _ in range(len(_row_links(tree))):
        # Re-read every pass: editing a row re-syncs sockets.
        link = next(
            (other for other in _row_links(tree) if _key(other) not in handled), None
        )
        if link is None:
            break
        key = _key(link)
        handled.add(key)
        resolved = _resolve(tree, link)
        try:
            tree.links.remove(link)
        except (ReferenceError, RuntimeError):
            continue
        if any(_key(other) == key for other in _row_links(tree)):
            continue
        count += 1
        if resolved is not None:
            _apply(*resolved)
    return count


def _is_background() -> bool:
    return bool(bpy.app.background)


def _undo_push() -> None:
    if _is_background():
        return
    try:
        bpy.ops.ed.undo_push(message=UNDO_MESSAGE)
    except (
        AttributeError,
        RuntimeError,
    ) as error:  # a missing context must never raise out of a timer
        log_once(
            _LOG,
            "DEBUG",
            ("_undo_push", type(error).__name__),
            "undo push: fell back after %s",
            error,
            exc_info=True,
        )


def _fire(name: str):
    """Consume the links of the tree called name"""
    _PENDING.discard(name)
    _CALLBACKS.pop(name, None)
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        return
    try:
        consumed = consume_transition_links(tree)
    except (ReferenceError, RuntimeError):
        return
    if consumed:
        _undo_push()
    return


def schedule_consume(tree) -> None:
    """Register a one-shot timer that consumes tree's transition links"""
    try:
        name = tree.name
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("schedule_consume", type(error).__name__),
            "schedule consume: fell back after %s",
            error,
            exc_info=True,
        )
        return
    if name in _PENDING:
        return
    _PENDING.add(name)
    callback = partial(_fire, name)
    try:
        bpy.app.timers.register(callback, first_interval=0)
    except (TypeError, ValueError):
        _PENDING.discard(name)
        return
    _CALLBACKS[name] = callback


def clear_pending() -> None:
    """Forget and unregister every scheduled consumption"""
    callbacks = list(_CALLBACKS.values())
    _CALLBACKS.clear()
    _PENDING.clear()
    timers = getattr(bpy.app, "timers", None)
    for callback in callbacks:
        try:
            if timers is not None and timers.is_registered(callback):
                timers.unregister(callback)
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("clear_pending", type(error).__name__),
                "clear pending: fell back after %s",
                error,
                exc_info=True,
            )


def discard_row_links(tree) -> int:
    """Remove every link dragged from a transition socket of tree without applying it"""
    removed = 0
    try:
        links = _row_links(tree)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("discard_row_links 1", type(error).__name__),
            "discard row links: fell back after %s",
            error,
            exc_info=True,
        )
        return 0
    for link in links:
        try:
            tree.links.remove(link)
            removed += 1
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("discard_row_links 2", type(error).__name__),
                "discard row links: fell back after %s",
                error,
                exc_info=True,
            )
            continue
    return removed


@bpy.app.handlers.persistent
def discard_dragged_links(*_args) -> None:
    """Drop raw transition links after undo, redo or load"""
    try:
        for tree in list(bpy.data.node_groups):
            if getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID:
                discard_row_links(tree)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("discard_dragged_links", type(error).__name__),
            "discard dragged links: fell back after %s",
            error,
            exc_info=True,
        )


@bpy.app.handlers.persistent
def reset_before_load(*_args) -> None:
    """Drop scheduled consumption before a file loads"""
    try:
        clear_pending()
    except Exception:
        debug_exception(_LOG, "AnimGraph pending link cleanup details")
