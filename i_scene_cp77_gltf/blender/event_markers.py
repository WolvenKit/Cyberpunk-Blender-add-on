from __future__ import annotations

import json

EVENT_MARKER_STATE_KEY = "_cp77_event_markers_json"


def _event_marker_state(action):
    payload = action.get(EVENT_MARKER_STATE_KEY)
    if not payload:
        return []
    try:
        values = json.loads(str(payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    result = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, list) and len(item) == 2:
                try:
                    result.append((str(item[0]), int(item[1])))
                except (TypeError, ValueError):
                    pass
    return result


def generated_event_marker_keys(action):
    return frozenset(_event_marker_state(action))


def sync_markers_from_events(action):
    if action is None:
        return
    previous = _event_marker_state(action)
    pending = list(previous)
    for marker in tuple(action.pose_markers):
        key = (str(marker.name), int(marker.frame))
        try:
            index = pending.index(key)
        except ValueError:
            continue
        action.pose_markers.remove(marker)
        pending.pop(index)

    current = []
    for event in getattr(action, "cp77_anim_events", ()):
        marker = action.pose_markers.new(event.event_name or event.event_type)
        marker.frame = event.start_frame
        current.append([str(marker.name), int(marker.frame)])
    action[EVENT_MARKER_STATE_KEY] = json.dumps(
        current, ensure_ascii=False, separators=(",", ":")
    )
