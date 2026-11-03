from __future__ import annotations

import hashlib
import struct
from functools import cache

import bpy
import numpy as np
from bpy_extras import anim_utils

from ..assetio.values import coerce_int
from ..bartmoss.curve import sample_frame_grid
from ..core.log import get_logger, log_once

_LOG = get_logger(__name__)


@cache
def keyframe_interpolation_value(name):
    """Resolve Blender's interpolation enum once for bulk curve operations"""
    return bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items[name].value


def get_action_slot(action, id_data=None, *, create: bool = False):
    if action is None:
        return None
    slots = action.slots
    animation_data = (
        getattr(id_data, "animation_data", None) if id_data is not None else None
    )
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
    slot = slots.new(id_type=id_type, name=name)
    if animation_data is not None and animation_data.action is action:
        animation_data.action_slot = slot
    return slot


def action_slot_identity(animation_data):
    slot = (
        getattr(animation_data, "action_slot", None)
        if animation_data is not None
        else None
    )
    if slot is None:
        return "", -1
    identifier = str(getattr(slot, "identifier", "") or "")
    handle = coerce_int(getattr(slot, "handle", -1), -1, unwrap=False)
    return identifier, handle


def _find_action_slot(action, *, identifier: str = "", handle: int = -1):
    if action is None:
        return None
    for slot in action.slots:
        if identifier and str(getattr(slot, "identifier", "") or "") == identifier:
            return slot
        if handle >= 0:
            try:
                if int(getattr(slot, "handle", -1)) == handle:
                    return slot
            except (TypeError, ValueError):
                continue
    return None


def assign_action_with_slot(
    id_data, action, *, slot_identifier: str = "", slot_handle: int = -1
):
    animation_data = id_data.animation_data_create()
    animation_data.action = action
    slot = _find_action_slot(action, identifier=slot_identifier, handle=slot_handle)
    if slot is None:
        slot = get_action_slot(action, id_data, create=True)
    if slot is not None:
        animation_data.action_slot = slot
    return animation_data


def get_action_channelbag(action, id_data=None, *, create: bool = False):
    if action is None:
        return None
    slot = get_action_slot(action, id_data, create=create)
    if slot is None:
        return None
    if create:
        return anim_utils.action_ensure_channelbag_for_slot(action, slot)

    return anim_utils.action_get_channelbag_for_slot(action, slot)


def get_action_fcurves(action, id_data=None, *, create: bool = False):
    channelbag = get_action_channelbag(action, id_data, create=create)
    return channelbag.fcurves if channelbag is not None else None


def get_action_groups(action, id_data=None, *, create: bool = False):
    channelbag = get_action_channelbag(action, id_data, create=create)
    return channelbag.groups if channelbag is not None else None


# The channels that place an object, as opposed to its pose, shape keys or other properties.
_OBJECT_TRANSFORM_PATHS = frozenset(
    {
        "location",
        "rotation_euler",
        "rotation_quaternion",
        "rotation_axis_angle",
        "scale",
        "delta_location",
        "delta_rotation_euler",
        "delta_rotation_quaternion",
        "delta_scale",
    }
)


def object_transform_animated(obj) -> bool:
    """Whether the object's own placement is keyed, by its action or one in its NLA tracks"""
    animation_data = getattr(obj, "animation_data", None)
    if animation_data is None:
        return False
    assigned = [(animation_data.action, animation_data.action_slot)]
    assigned.extend(
        (strip.action, strip.action_slot)
        for track in animation_data.nla_tracks
        for strip in track.strips
    )
    for action, slot in assigned:
        if action is None or slot is None:
            continue
        channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
        if channelbag is not None and any(
            curve.data_path in _OBJECT_TRANSFORM_PATHS for curve in channelbag.fcurves
        ):
            return True
    return False


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
        enum_value = keyframe_interpolation_value(blender_interpolation)
        points.foreach_set(
            "interpolation",
            np.full(count, enum_value, dtype=np.int32),
        )
    if update:
        fcurve.update()
    return count


def write_pose_curves(
    fcurves, pose_bones, frames, locations, rotations_wxyz, scales
) -> tuple[int, int]:
    """Key each pose bone's location, quaternion and scale"""
    frames = np.asarray(frames, dtype=np.float64)
    curve_count = keypoint_count = 0
    for index, pose_bone in enumerate(pose_bones):
        channels = [
            ("location", locations, 3),
            ("rotation_quaternion", rotations_wxyz, 4),
        ]
        if not np.allclose(scales[:, index], 1.0, atol=1e-7):
            channels.append(("scale", scales, 3))
        for property_name, values, width in channels:
            data_path = pose_bone.path_from_id(property_name)
            for component in range(width):
                curve = fcurves.ensure(
                    data_path, index=component, group_name=pose_bone.name
                )
                keypoint_count += bulk_set_keyframes(
                    curve,
                    frames,
                    values[:, index, component],
                    interpolation="LINEAR",
                    collapse_constant=True,
                )
                curve_count += 1
    return curve_count, keypoint_count


def clear_fcurve_points(fcurve) -> None:
    fcurve.keyframe_points.clear()


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


def capture_keyframe_point_state(point):
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
        except (AttributeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("capture_keyframe_point_state 1", type(error).__name__),
                "capture keyframe point state: fell back after %s",
                error,
                exc_info=True,
            )
    for name in ("handle_left", "handle_right"):
        try:
            value = getattr(point, name)
            state[name] = (float(value[0]), float(value[1]))
        except (AttributeError, TypeError, IndexError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("capture_keyframe_point_state 2", type(error).__name__),
                "capture keyframe point state: fell back after %s",
                error,
                exc_info=True,
            )
    return state


def apply_keyframe_point_state(point, state, *, handles: bool) -> None:
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
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("apply_keyframe_point_state 1", type(error).__name__),
                "apply keyframe point state: fell back after %s",
                error,
                exc_info=True,
            )
    if not handles:
        return
    for name in ("handle_left", "handle_right"):
        if name not in state:
            continue
        try:
            setattr(point, name, state[name])
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("apply_keyframe_point_state 2", type(error).__name__),
                "apply keyframe point state: fell back after %s",
                error,
                exc_info=True,
            )


def _writable_curve_properties(value):
    captured = {}
    for prop in getattr(getattr(value, "bl_rna", None), "properties", ()):
        name = getattr(prop, "identifier", "")
        if (
            not name
            or name in {"rna_type", "type"}
            or getattr(prop, "is_readonly", False)
        ):
            continue
        if getattr(prop, "type", "") in {"POINTER", "COLLECTION"}:
            continue
        try:
            current = getattr(value, name)
            captured[name] = (
                tuple(current) if getattr(prop, "is_array", False) else current
            )
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_writable_curve_properties", type(error).__name__),
                "writable curve properties: fell back after %s",
                error,
                exc_info=True,
            )
    return captured


_POINT_ENUMS = (
    "interpolation",
    "easing",
    "handle_left_type",
    "handle_right_type",
    "type",
)
_POINT_FLOATS = ("amplitude", "back", "period")
_POINT_PAIRS = ("co", "handle_left", "handle_right")
_POINT_FLAGS = ("select_control_point", "select_left_handle", "select_right_handle")


def _capture_points(points) -> dict:
    count = len(points)
    state = {"count": count}
    for name in _POINT_PAIRS:
        values = np.empty(count * 2, dtype=np.float64)
        points.foreach_get(name, values)
        state[name] = values
    for name in _POINT_FLOATS:
        values = np.empty(count, dtype=np.float64)
        points.foreach_get(name, values)
        state[name] = values
    for name in _POINT_FLAGS:
        values = np.empty(count, dtype=bool)
        points.foreach_get(name, values)
        state[name] = values
    state["enums"] = tuple(
        tuple(getattr(point, name) for name in _POINT_ENUMS) for point in points
    )
    return state


def _restore_points(points, state) -> None:
    """Rewrite keyframes exactly as captured, without sorting, merging or recomputing handles"""
    points.clear()
    if not state["count"]:
        return
    points.add(state["count"])
    for point, enums in zip(points, state["enums"]):
        for name, value in zip(_POINT_ENUMS, enums):
            setattr(point, name, value)
    # Bulk writes go last: they bypass RNA updates, so handle types set above cannot recompute them.
    for name in (*_POINT_FLOATS, *_POINT_FLAGS, *_POINT_PAIRS):
        points.foreach_set(name, state[name])


def _find_fcurve(fcurves, data_path: str, index: int):
    try:
        return fcurves.find(data_path, index=index)
    except (AttributeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_find_fcurve", type(error).__name__),
            "find fcurve: fell back after %s",
            error,
            exc_info=True,
        )
        return next(
            (
                curve
                for curve in fcurves
                if curve.data_path == data_path and curve.array_index == index
            ),
            None,
        )


def capture_fcurves(action, id_data, predicate) -> tuple[dict, ...]:
    """Snapshot keys, curve settings and modifiers of the action's curves matching predicate"""
    fcurves = get_action_fcurves(action, id_data)
    if fcurves is None:
        return ()
    return tuple(
        {
            "data_path": curve.data_path,
            "array_index": int(curve.array_index),
            "group_name": curve.group.name if curve.group is not None else "",
            "properties": _writable_curve_properties(curve),
            "points": _capture_points(curve.keyframe_points),
            "modifiers": tuple(
                {
                    "type": modifier.type,
                    "properties": _writable_curve_properties(modifier),
                }
                for modifier in curve.modifiers
            ),
        }
        for curve in tuple(fcurves)
        if predicate(curve)
    )


def restore_fcurves(action, id_data, predicate, snapshots) -> None:
    """Return the curves matching predicate to the state capture_fcurves captured"""
    fcurves = get_action_fcurves(action, id_data, create=True)
    if fcurves is None:
        raise RuntimeError(f"Unable to resolve FCurves for action {action.name!r}")
    captured = {
        (snapshot["data_path"], snapshot["array_index"]) for snapshot in snapshots
    }
    for curve in tuple(fcurves):
        if (
            predicate(curve)
            and (curve.data_path, int(curve.array_index)) not in captured
        ):
            fcurves.remove(curve)
    for snapshot in snapshots:
        curve = _find_fcurve(fcurves, snapshot["data_path"], snapshot["array_index"])
        if curve is None:
            curve = ensure_fcurve(
                action,
                id_data,
                snapshot["data_path"],
                snapshot["array_index"],
                snapshot["group_name"],
            )
        for name, value in snapshot["properties"].items():
            try:
                setattr(curve, name, value)
            except (AttributeError, TypeError, ValueError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("restore_fcurves 1", type(error).__name__),
                    "restore fcurves: fell back after %s",
                    error,
                    exc_info=True,
                )
        for modifier in reversed(tuple(curve.modifiers)):
            curve.modifiers.remove(modifier)
        for modifier_state in snapshot["modifiers"]:
            modifier = curve.modifiers.new(type=modifier_state["type"])
            for name, value in modifier_state["properties"].items():
                try:
                    setattr(modifier, name, value)
                except (AttributeError, TypeError, ValueError) as error:
                    log_once(
                        _LOG,
                        "DEBUG",
                        ("restore_fcurves 2", type(error).__name__),
                        "restore fcurves: fell back after %s",
                        error,
                        exc_info=True,
                    )
        _restore_points(curve.keyframe_points, snapshot["points"])


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
    if (
        collapse_constant
        and len(frames) > 1
        and np.all(np.abs(values - values[0]) <= 1e-10)
    ):
        frames = frames[:1]
        values = values[:1]

    retained = []
    replaced = {}
    epsilon = 1e-7
    existing = [capture_keyframe_point_state(point) for point in fcurve.keyframe_points]
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
            new_states.append(
                {
                    "frame": float(frame),
                    "value": float(value),
                    "interpolation": blender_interpolation,
                }
            )
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
        apply_keyframe_point_state(point, state, handles=False)
    fcurve.update()
    for point, state in zip(points, states):
        apply_keyframe_point_state(point, state, handles=True)
    return len(new_states)


def action_curve_map(action, armature=None, *, error_type=ValueError):
    """Index one Action's curves while rejecting ambiguous duplicate channels"""
    curves = get_action_fcurves(action, armature) or ()
    result = {}
    for curve in curves:
        key = (str(curve.data_path), int(curve.array_index))
        if key in result:
            raise error_type(f"Action {action.name!r} has duplicate FCurves for {key}.")
        result[key] = curve
    return result


def curve_coordinates(curve, *, sort=False):
    """Read keyed or sampled coordinates in bulk, with optional stable time ordering"""
    points = (
        curve.keyframe_points if len(curve.keyframe_points) else curve.sampled_points
    )
    if not len(points):
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
    coordinates = np.empty(len(points) * 2, dtype=np.float64)
    points.foreach_get("co", coordinates)
    frames, values = coordinates[0::2], coordinates[1::2]
    if sort and np.any(np.diff(frames) < 0):
        order = np.argsort(frames, kind="stable")
        return frames[order], values[order]
    return frames, values


def property_curve_fingerprint(curve_map, data_path: str, width: int) -> str:
    digest = hashlib.sha256()
    digest.update(data_path.encode("utf-8"))
    digest.update(struct.pack("<I", int(width)))
    for component in range(width):
        curve = curve_map.get((data_path, component))
        digest.update(struct.pack("<I", component))
        if curve is None:
            digest.update(b"missing")
            continue
        digest.update(str(getattr(curve, "extrapolation", "CONSTANT")).encode("utf-8"))
        digest.update(b"\x01" if bool(getattr(curve, "mute", False)) else b"\x00")
        modifiers = tuple(getattr(curve, "modifiers", ()))
        digest.update(struct.pack("<I", len(modifiers)))
        for modifier in modifiers:
            digest.update(str(getattr(modifier, "type", "")).encode("utf-8"))

        sampled = not len(curve.keyframe_points) and bool(len(curve.sampled_points))
        points = curve.sampled_points if sampled else curve.keyframe_points
        digest.update(struct.pack("<I", len(points)))
        if not len(points):
            continue
        coordinates = np.empty(len(points) * 2, dtype=np.float32)
        points.foreach_get("co", coordinates)
        digest.update(coordinates.tobytes())
        if sampled:
            digest.update(b"SAMPLED")
        else:
            interpolations = np.empty(len(points), dtype=np.int32)
            points.foreach_get("interpolation", interpolations)
            digest.update(interpolations.tobytes())
            if len(points) < 2 or not np.any(
                interpolations == keyframe_interpolation_value("BEZIER")
            ):
                continue
            for name in ("handle_left_type", "handle_right_type"):
                values = np.empty(len(points), dtype=np.int32)
                points.foreach_get(name, values)
                digest.update(values.tobytes())
            for name in ("handle_left", "handle_right"):
                values = np.empty(len(points) * 2, dtype=np.float32)
                points.foreach_get(name, values)
                digest.update(values.tobytes())
    return digest.hexdigest()


def transform_curve_fingerprint(curve_map, paths) -> str:
    """Track all transform dependencies when rest-pivot conversion couples channels"""
    digest = hashlib.sha256()
    for name, width in (("location", 3), ("rotation_quaternion", 4), ("scale", 3)):
        digest.update(
            property_curve_fingerprint(curve_map, paths[name], width).encode("ascii")
        )
    return digest.hexdigest()


def curve_key_frames(curve) -> np.ndarray:
    return curve_coordinates(curve)[0]


def curve_interpolations(curve) -> set[str]:
    if not len(curve.keyframe_points) and len(curve.sampled_points):
        return {"LINEAR"}
    return {str(point.interpolation) for point in curve.keyframe_points}


def property_sampling(
    curves, action, *, force_dense=False, frame_start=None, frame_end=None
):
    if not curves:
        return None
    interpolations = set()
    frame_arrays = []
    has_modifiers = False
    for curve in curves:
        if getattr(curve, "mute", False):
            continue
        has_modifiers |= any(
            not getattr(item, "mute", False) for item in getattr(curve, "modifiers", ())
        )
        interpolations.update(curve_interpolations(curve))
        frames = curve_key_frames(curve)
        if len(frames):
            frame_arrays.append(frames)
    if not frame_arrays:
        return None
    exact_mode = interpolations.issubset({"CONSTANT"}) or interpolations.issubset(
        {"LINEAR"}
    )
    if force_dense or has_modifiers or not exact_mode:
        action_start, action_end = (float(value) for value in action.frame_range)
        start = action_start if frame_start is None else float(frame_start)
        end = action_end if frame_end is None else float(frame_end)
        frames = sample_frame_grid(start, end, np.concatenate(frame_arrays))
        interpolation = "LINEAR"
    else:
        frames = np.unique(np.concatenate(frame_arrays))
        interpolation = "STEP" if interpolations == {"CONSTANT"} else "LINEAR"
    return frames, interpolation


def evaluate_property(curve_map, data_path, width, frames, defaults):
    result = np.broadcast_to(
        np.asarray(defaults, dtype=np.float64),
        (len(frames), width),
    ).copy()
    curves = []
    for component in range(width):
        curve = curve_map.get((data_path, component))
        if curve is None or getattr(curve, "mute", False):
            continue
        curves.append(curve)
        result[:, component] = np.fromiter(
            (float(curve.evaluate(float(frame))) for frame in frames),
            dtype=np.float64,
            count=len(frames),
        )
    return result, curves


def scalar_curve_fingerprints(curve):
    """Capture scalar key data and interpolation state without per-key Python access"""
    sampled = not len(curve.keyframe_points) and bool(len(curve.sampled_points))
    points = curve.sampled_points if sampled else curve.keyframe_points
    coordinates = np.empty(len(points) * 2, dtype=np.float32)
    points.foreach_get("co", coordinates)
    coordinate_hash = hashlib.sha256(coordinates.tobytes()).hexdigest()
    digest = hashlib.sha256()
    digest.update(str(curve.data_path).encode("utf-8"))
    digest.update(coordinates.tobytes())
    if sampled:
        digest.update(b"SAMPLED")
    else:
        for name in ("handle_left", "handle_right"):
            values = np.empty(len(points) * 2, dtype=np.float32)
            points.foreach_get(name, values)
            digest.update(values.tobytes())
        for name in ("interpolation", "handle_left_type", "handle_right_type"):
            values = np.empty(len(points), dtype=np.int32)
            points.foreach_get(name, values)
            digest.update(values.tobytes())
    digest.update(str(curve.extrapolation).encode("ascii"))
    return {"coordinates": coordinate_hash, "curve": digest.hexdigest()}
