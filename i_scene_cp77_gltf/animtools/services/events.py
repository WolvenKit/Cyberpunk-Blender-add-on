from __future__ import annotations

from ...animation.events import sync_markers_from_events
from ..model import OperationResult


def _selected_event(action):
    if action is None:
        return None
    index = int(getattr(action, "cp77_anim_events_index", -1))
    events = getattr(action, "cp77_anim_events", ())
    return events[index] if 0 <= index < len(events) else None


def add_event(action, frame: int) -> OperationResult:
    if action is None:
        return OperationResult.cancelled("No active action", "WARNING")
    event = action.cp77_anim_events.add()
    event.event_type = "Simple"
    event.start_frame = int(frame)
    action.cp77_anim_events_index = len(action.cp77_anim_events) - 1
    sync_markers_from_events(action)
    return OperationResult.finished()


def remove_event(action) -> OperationResult:
    if action is None:
        return OperationResult.cancelled("No active action", "WARNING")
    index = int(action.cp77_anim_events_index)
    if 0 <= index < len(action.cp77_anim_events):
        action.cp77_anim_events.remove(index)
        action.cp77_anim_events_index = min(index, len(action.cp77_anim_events) - 1)
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
    for marker in action.pose_markers:
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
    event.switches.add()
    event.switches_index = len(event.switches) - 1
    return OperationResult.finished()


def remove_switch(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    index = int(event.switches_index)
    if 0 <= index < len(event.switches):
        event.switches.remove(index)
        event.switches_index = min(index, len(event.switches) - 1)
    return OperationResult.finished()


def add_param(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    param = event.params.add()
    param.enter_curve_type = "Linear"
    param.enter_curve_time = 1.0
    param.exit_curve_type = "Linear"
    param.exit_curve_time = 1.0
    event.params_index = len(event.params) - 1
    return OperationResult.finished()


def remove_param(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    index = int(event.params_index)
    if 0 <= index < len(event.params):
        event.params.remove(index)
        event.params_index = min(index, len(event.params) - 1)
    return OperationResult.finished()


def add_workspot_action(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    item = event.workspot_actions.add()
    item.action_type = "EquipItemToSlot"
    event.workspot_actions_index = len(event.workspot_actions) - 1
    return OperationResult.finished()


def remove_workspot_action(action) -> OperationResult:
    event = _selected_event(action)
    if event is None:
        return OperationResult.cancelled()
    index = int(event.workspot_actions_index)
    if 0 <= index < len(event.workspot_actions):
        event.workspot_actions.remove(index)
        event.workspot_actions_index = min(index, len(event.workspot_actions) - 1)
    return OperationResult.finished()
