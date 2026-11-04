from __future__ import annotations

from ...blender.animation_context import active_action
from ...blender.event_markers import (
    generated_event_marker_keys,
    sync_markers_from_events,
)
from ...blender.operator_results import OperationResult


def _selected_event(action):
    if action is None:
        return None
    index = int(getattr(action, "cp77_anim_events_index", -1))
    events = getattr(action, "cp77_anim_events", ())
    return events[index] if 0 <= index < len(events) else None


def _append(owner, items_name: str, index_name: str, **values):
    items = getattr(owner, items_name)
    item = items.add()
    for key, value in values.items():
        setattr(item, key, value)
    setattr(owner, index_name, len(items) - 1)
    return item


def _remove_active(owner, items_name: str, index_name: str) -> bool:
    items = getattr(owner, items_name)
    index = int(getattr(owner, index_name))
    if not 0 <= index < len(items):
        return False
    items.remove(index)
    setattr(owner, index_name, min(index, len(items) - 1))
    return True


def event_changed(context) -> None:
    """Keep the active action's generated pose markers in step with an edited event"""
    action = active_action(context)
    if action is not None:
        sync_markers_from_events(action)


def add_event(action, frame: int) -> OperationResult:
    if action is None:
        return OperationResult.cancelled("No active action", "WARNING")
    _append(
        action,
        "cp77_anim_events",
        "cp77_anim_events_index",
        event_type="Simple",
        start_frame=int(frame),
    )
    sync_markers_from_events(action)
    return OperationResult.finished()


def remove_event(action) -> OperationResult:
    if action is None:
        return OperationResult.cancelled("No active action", "WARNING")
    if _remove_active(action, "cp77_anim_events", "cp77_anim_events_index"):
        sync_markers_from_events(action)
    return OperationResult.finished()


def goto_event(action, scene) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    scene.frame_set(event.start_frame)
    return OperationResult.finished()


def move_event(action, direction: str) -> OperationResult:
    if action is None:
        return OperationResult.cancelled()
    index = int(action.cp77_anim_events_index)
    count = len(action.cp77_anim_events)
    if direction == "UP" and index > 0:
        action.cp77_anim_events.move(index, index - 1)
        action.cp77_anim_events_index = index - 1
    elif direction == "DOWN" and index < count - 1:
        action.cp77_anim_events.move(index, index + 1)
        action.cp77_anim_events_index = index + 1
    sync_markers_from_events(action)
    return OperationResult.finished()


def sync_markers(action) -> OperationResult:
    if action is None:
        return OperationResult.cancelled()
    sync_markers_from_events(action)
    return OperationResult.finished(f"Synced {len(action.cp77_anim_events)} markers")


def add_events_from_markers(action) -> OperationResult:
    if action is None:
        return OperationResult.cancelled()
    count = 0
    generated = generated_event_marker_keys(action)
    for marker in action.pose_markers:
        if (str(marker.name), int(marker.frame)) in generated:
            continue
        event = action.cp77_anim_events.add()
        event.event_type = "Simple"
        event.event_name = marker.name
        event.start_frame = marker.frame
        count += 1
    if count:
        action.cp77_anim_events_index = len(action.cp77_anim_events) - 1
    return OperationResult.finished(f"Created {count} events from markers")


def add_switch(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    _append(event, "switches", "switches_index")
    return OperationResult.finished()


def remove_switch(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    _remove_active(event, "switches", "switches_index")
    return OperationResult.finished()


def add_param(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    _append(
        event,
        "params",
        "params_index",
        enter_curve_type="Linear",
        enter_curve_time=1.0,
        exit_curve_type="Linear",
        exit_curve_time=1.0,
    )
    return OperationResult.finished()


def remove_param(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    _remove_active(event, "params", "params_index")
    return OperationResult.finished()


def add_workspot_action(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    _append(
        event,
        "workspot_actions",
        "workspot_actions_index",
        action_type="EquipItemToSlot",
    )
    return OperationResult.finished()


def remove_workspot_action(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    _remove_active(event, "workspot_actions", "workspot_actions_index")
    return OperationResult.finished()
