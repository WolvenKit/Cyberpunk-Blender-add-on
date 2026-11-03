from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ....assetio.values import cname_or_empty
from .topology import PreviewBoundary, has_link, resolve

SYNC_METHOD_BY_PROGRESS = "animSyncMethodByProgress"
SYNC_METHOD_BY_FOOT_PHASE = "animSyncMethodByFootPhase"
SUPPORTED_SYNC_METHODS = frozenset({SYNC_METHOD_BY_PROGRESS, SYNC_METHOD_BY_FOOT_PHASE})

# Single-precision machine epsilon: the tolerance below which a non-looped clip
# counts as having already reached its end when synced.
FLOAT_EPSILON = 1.1920928955078125e-07


def selected_input_index(weight: float, num_inputs: int) -> int:
    count = int(num_inputs)
    if count <= 0:
        return -1
    if count == 1:
        return 0
    maximum = count - 1
    value = float(weight)
    if value < 0.0:
        return 0
    if value > maximum:
        return maximum
    return min(maximum, int(value + 0.5))


@dataclass(frozen=True)
class SyncEntry:
    """One gathered clip"""

    duration: float
    current_time: float
    weight: float
    animation: str = ""


def _entry_progress(entry: SyncEntry) -> float:
    duration = float(entry.duration)
    if duration == 0.0:
        return 0.0
    return float(entry.current_time) / duration * float(entry.weight)


def progress_from_sync_entries(entries: Sequence[SyncEntry]) -> float:
    """Average normalised progress of the gathered clips"""
    if not entries:
        return 0.0
    if len(entries) == 1:
        return _entry_progress(entries[0])
    x = 0.0
    y = 0.0
    for entry in entries:
        radius = float(entry.weight)
        angle = _entry_progress(entry) * math.tau
        x += radius * math.cos(angle)
        y += radius * math.sin(angle)
    angle = math.atan2(y, x)
    if angle < 0.0:
        angle += math.tau
    return angle / math.tau


def synced_clip_time(
    progress: float,
    duration: float,
    current_time: float,
    *,
    clip_end: float,
    looped: bool,
) -> float | None:
    """Clip time after synchronisation, or None when the clip keeps its time"""
    target = float(progress) * float(duration)
    if looped:
        return target
    anim_end = max(float(duration) - float(clip_end), 0.0)
    if abs(float(current_time) - anim_end) <= FLOAT_EPSILON:
        return None
    return target


def switch_input_weights(
    selected: int | None,
    source: int | None,
    alpha: float,
    active: frozenset[int],
) -> tuple[tuple[int, float], ...]:
    """Active inputs and their gather weights when a switch gathers sync data"""
    result = []
    if source is not None and source != selected and source in active and alpha < 1.0:
        result.append((source, 1.0 - alpha))
    if selected is not None and selected in active and alpha > 0.0:
        result.append((selected, alpha))
    return tuple(result)


BLEND_MULTIPLE_THRESHOLD = 0.001


def blend_multiple_selection(
    values, weight: float, minimum: float, maximum: float, radial: bool
):
    """(first, second, alpha) selected from the sorted input values"""
    values = [float(v) for v in values]
    if not values:
        return -1, -1, 0.0
    if len(values) == 1:
        return 0, -1, 0.0
    low = max(values[0], float(minimum))
    high = min(values[-1], float(maximum))
    weight = float(weight)
    if radial:
        if high - low == 0.0:
            weight = low
        else:
            remainder = math.fmod(weight - low, high - low)
            if remainder < 0.0:
                remainder += high
            weight = remainder + low
    else:
        weight = min(max(weight, low), high)
    second = 0
    while second + 1 < len(values) and values[second] <= weight:
        second += 1
    first = second - 1
    span = values[second] - values[first]
    normalized = (weight - values[first]) / span if span > 0.0 else 1.0
    if normalized < BLEND_MULTIPLE_THRESHOLD:
        alpha = 0.0
    elif normalized > 1.0 - BLEND_MULTIPLE_THRESHOLD:
        alpha = 1.0
    else:
        alpha = min(
            1.0,
            max(
                0.0,
                (normalized - BLEND_MULTIPLE_THRESHOLD)
                / (1.0 - 2.0 * BLEND_MULTIPLE_THRESHOLD),
            ),
        )
    return first, second, alpha


def switch_state_weights(
    blend_time: float, selected, blend, active
) -> tuple[tuple[int, float], ...]:
    """Active inputs and gather weights of a switch whose blend toward selected has blend remaining"""
    duration = float(blend_time)
    source, remaining = blend if blend is not None else (selected, 0.0)
    alpha = 1.0 - remaining / duration if duration > 0.0 else 1.0
    return switch_input_weights(selected, source, alpha, frozenset(active))


def sync_source(entries, sync_method):
    """Gathered clips as a sync source"""
    if sync_method == SYNC_METHOD_BY_FOOT_PHASE:
        return ("foot_phase", entries[0] if entries else None)
    return progress_from_sync_entries(entries)


def sync_method_type(node, index, label: str) -> str:
    """The node's synchronisation method type, or '' without one"""
    if node.get("syncMethod") is None:
        return ""
    method = resolve(node["syncMethod"], index)
    sync_method = (
        str(method.get("$type", "") or "") if isinstance(method, Mapping) else ""
    )
    if sync_method not in SUPPORTED_SYNC_METHODS:
        raise PreviewBoundary(
            f"{label} synchronization method {sync_method or '<unresolved>'} is not implemented by Graph preview"
        )
    return sync_method


def switch_data(node, index):
    """A Switch's data and its declared input links"""
    try:
        num_inputs = int(node.get("numInputs", len(node.get("inputNodes") or ())) or 0)
    except (TypeError, ValueError) as error:
        raise PreviewBoundary("Switch numInputs is not an integer") from error
    inputs = list(node.get("inputNodes") or ())
    if num_inputs < 0 or num_inputs > len(inputs):
        raise PreviewBoundary(
            f"Switch declares {num_inputs} inputs but only {len(inputs)} are serialized"
        )
    blend_time = float(node.get("blendTime", 0.0) or 0.0)
    sync_method = sync_method_type(node, index, "Switch")
    # A motion provider only feeds the graph's motion table for gameplay planning; the pose is unaffected.
    active_inputs = inputs[:num_inputs]
    if any(not isinstance(item, Mapping) for item in active_inputs):
        raise PreviewBoundary("Switch contains a malformed declared input")
    return {
        "numInputs": num_inputs,
        "blendTime": max(0.0, blend_time),
        "hasWeightNode": has_link(node, "weightNode"),
        "syncMethod": sync_method,
        "timeWarping": bool(node.get("timeWarpingEnabled", False)),
        "canRequestInertialization": bool(node.get("canRequestInertialization", False)),
        "pushDataByTag": cname_or_empty(node.get("pushDataByTag")),
    }, active_inputs


def selector_switch_data(node_type: str, node, index):
    """An EnumSwitch's or InputSwitch's data and its input links"""
    sync_method = sync_method_type(node, index, node_type)
    inputs = list(node.get("inputNodes") or ())
    select_source = (
        "int"
        if has_link(node, "selectIntNode")
        else ("float" if has_link(node, "selectFloatNode") else "none")
    )
    return {
        "numInputs": len(inputs),
        "blendTime": max(0.0, float(node.get("blendTime", 0.0) or 0.0)),
        "hasWeightNode": False,
        "syncMethod": sync_method,
        "timeWarping": bool(node.get("timeWarpingEnabled", False)),
        "canRequestInertialization": bool(node.get("canRequestInertialization", False)),
        "selectSource": select_source,
    }, inputs
