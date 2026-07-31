from __future__ import annotations

import numpy as np

try:
    import bpy
    from bpy_extras import anim_utils
except ImportError:
    bpy = None
    anim_utils = None


def get_action_slot(action, id_data=None, *, create: bool = False):
    if action is None:
        return None
    slots = action.slots
    animation_data = getattr(id_data, "animation_data", None) if id_data is not None else None
    if animation_data is not None and animation_data.action is action:
        assigned = animation_data.action_slot
        if assigned is not None:
            return assigned
        suitable = animation_data.action_suitable_slots
        if suitable:
            animation_data.action_slot = suitable[0]
            return suitable[0]
    if len(slots):
        return slots[0]
    if not create:
        return None
    id_type = getattr(id_data, "id_type", "OBJECT") if id_data is not None else "OBJECT"
    name = getattr(id_data, "name", action.name)
    try:
        slot = slots.new(id_type=id_type, name=name)
    except TypeError:
        slot = slots.new(id_type=id_type)
    if animation_data is not None and animation_data.action is action:
        animation_data.action_slot = slot
    return slot


def assign_action_with_slot(id_data, action):
    animation_data = id_data.animation_data_create()
    animation_data.action = action
    slot = get_action_slot(action, id_data, create=True)
    if slot is not None:
        animation_data.action_slot = slot
    return animation_data


def get_action_channelbag(action, id_data=None, *, create: bool = False):
    if action is None or anim_utils is None:
        return None
    slot = get_action_slot(action, id_data, create=create)
    if slot is None:
        return None
    if create:
        return anim_utils.action_ensure_channelbag_for_slot(action, slot)
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                if channelbag.slot is slot:
                    return channelbag
    return None


def get_action_fcurves(action, id_data=None, *, create: bool = False):
    channelbag = get_action_channelbag(action, id_data, create=create)
    return channelbag.fcurves if channelbag is not None else None


def get_action_groups(action, id_data=None, *, create: bool = False):
    channelbag = get_action_channelbag(action, id_data, create=create)
    return channelbag.groups if channelbag is not None else None


def ensure_fcurve(action, id_data, data_path: str, index: int, group_name: str = ""):
    fcurves = get_action_fcurves(action, id_data, create=True)
    if fcurves is None:
        raise RuntimeError(f"Unable to resolve FCurves for action {action.name!r}")
    return fcurves.ensure(data_path, index=index, group_name=group_name)


def bulk_set_keyframes(
    fcurve,
    frames,
    values,
    interpolation: str | None = None,
    *,
    collapse_constant: bool = False,
    update: bool = False,
) -> int:
    frames = np.asarray(frames, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    count = len(frames)
    if count == 0:
        return 0
    if collapse_constant and count > 1 and np.all(np.abs(values - values[0]) <= 1e-10):
        frames = frames[:1]
        values = values[:1]
        count = 1
    points = fcurve.keyframe_points
    points.add(count)
    coordinates = np.empty(count * 2, dtype=np.float64)
    coordinates[0::2] = frames
    coordinates[1::2] = values
    points.foreach_set("co", coordinates)
    if interpolation:
        blender_interpolation = "CONSTANT" if interpolation == "STEP" else interpolation
        try:
            enum_value = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items[
                blender_interpolation
            ].value
            points.foreach_set(
                "interpolation",
                np.full(count, enum_value, dtype=np.int32),
            )
        except (AttributeError, KeyError, TypeError, RuntimeError):
            for point in points:
                point.interpolation = blender_interpolation
    if update:
        fcurve.update()
    return count


def round_keyframes(frames):
    frames = np.asarray(frames, dtype=np.float64)
    lower = np.floor(frames)
    upper = np.ceil(frames)
    return np.where((upper - frames) < (frames - lower), upper, lower)


def clear_fcurve_points(fcurve) -> None:
    points = fcurve.keyframe_points
    clear = getattr(points, "clear", None)
    if clear is not None:
        clear()
        return
    for point in reversed(tuple(points)):
        points.remove(point, fast=True)


def remove_fcurves(action, id_data, predicate) -> int:
    fcurves = get_action_fcurves(action, id_data)
    if fcurves is None:
        return 0
    removed = 0
    for curve in tuple(fcurves):
        if predicate(curve):
            fcurves.remove(curve)
            removed += 1
    return removed


def remove_property_fcurves(action, id_data, data_path: str) -> int:
    return remove_fcurves(
        action,
        id_data,
        lambda curve: curve.data_path == data_path,
    )


def remove_bone_fcurves(action, id_data, bone_name: str) -> int:
    prefix = f'pose.bones["{bone_name}"]'
    return remove_fcurves(
        action,
        id_data,
        lambda curve: curve.data_path.startswith(prefix),
    )


def _point_state(point):
    state = {
        "frame": float(point.co[0]),
        "value": float(point.co[1]),
    }
    for name in (
        "interpolation",
        "easing",
        "handle_left_type",
        "handle_right_type",
        "type",
        "amplitude",
        "back",
        "period",
    ):
        try:
            state[name] = getattr(point, name)
        except (AttributeError, TypeError):
            pass
    for name in ("handle_left", "handle_right"):
        try:
            value = getattr(point, name)
            state[name] = (float(value[0]), float(value[1]))
        except (AttributeError, TypeError, IndexError):
            pass
    return state


def _set_point_state(point, state, *, handles: bool) -> None:
    names = (
        "interpolation",
        "easing",
        "handle_left_type",
        "handle_right_type",
        "type",
        "amplitude",
        "back",
        "period",
    )
    for name in names:
        if name not in state:
            continue
        try:
            setattr(point, name, state[name])
        except (AttributeError, TypeError, ValueError):
            pass
    if not handles:
        return
    for name in ("handle_left", "handle_right"):
        if name not in state:
            continue
        try:
            setattr(point, name, state[name])
        except (AttributeError, TypeError, ValueError):
            pass


def replace_fcurve_keyframes(
    fcurve,
    frames,
    values,
    interpolation: str = "BEZIER",
    *,
    replace_range=None,
    replace_frames: bool = False,
    collapse_constant: bool = False,
) -> int:
    frames = np.asarray(frames, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if len(frames) != len(values):
        raise ValueError("frames and values must have the same length")
    if len(frames) == 0:
        return 0
    if collapse_constant and len(frames) > 1 and np.all(np.abs(values - values[0]) <= 1e-10):
        frames = frames[:1]
        values = values[:1]

    retained = []
    replaced = {}
    epsilon = 1e-7
    existing = [_point_state(point) for point in fcurve.keyframe_points]
    if replace_range is not None:
        start, end = (float(value) for value in replace_range)
        for state in existing:
            frame = state["frame"]
            if frame < start - epsilon or frame > end + epsilon:
                retained.append(state)
                continue
            matches = np.flatnonzero(np.abs(frames - frame) <= epsilon)
            if len(matches):
                replaced[int(matches[0])] = state
    elif replace_frames:
        for state in existing:
            frame = state["frame"]
            matches = np.flatnonzero(np.abs(frames - frame) <= epsilon)
            if len(matches):
                replaced[int(matches[0])] = state
            else:
                retained.append(state)

    blender_interpolation = "CONSTANT" if interpolation == "STEP" else interpolation
    new_states = []
    for index, (frame, value) in enumerate(zip(frames, values)):
        previous = replaced.get(index)
        if previous is None:
            new_states.append({
                "frame": float(frame),
                "value": float(value),
                "interpolation": blender_interpolation,
            })
            continue
        state = previous.copy()
        delta = float(value) - state["value"]
        state["frame"] = float(frame)
        state["value"] = float(value)
        for handle_name in ("handle_left", "handle_right"):
            if handle_name in state:
                handle = state[handle_name]
                state[handle_name] = (handle[0], handle[1] + delta)
        new_states.append(state)
    states = sorted(retained + new_states, key=lambda state: state["frame"])
    clear_fcurve_points(fcurve)
    points = fcurve.keyframe_points
    points.add(len(states))
    coordinates = np.empty(len(states) * 2, dtype=np.float64)
    coordinates[0::2] = [state["frame"] for state in states]
    coordinates[1::2] = [state["value"] for state in states]
    points.foreach_set("co", coordinates)
    for point, state in zip(points, states):
        _set_point_state(point, state, handles=False)
    fcurve.update()
    for point, state in zip(points, states):
        _set_point_state(point, state, handles=True)
    return len(new_states)
