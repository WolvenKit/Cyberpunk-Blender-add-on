import copy
from collections import defaultdict

import bpy
import numpy as np

from .binding import resolve_track_binding
from .keyframes import (
    assign_action_with_slot,
    bulk_set_keyframes,
    get_action_fcurves,
    get_action_groups,
    round_keyframes,
)
from .metadata import ACTION_DEFAULTS, FPS, armature_skin_extras, store_action_source
from .rig_binding import configure_float_idproperty

_VERBOSE = False
_TRACK_PROPERTY_CACHE = {}


def _set_verbose(val: bool):
    global _VERBOSE
    _VERBOSE = bool(val)


def _vprint(msg: str):
    if _VERBOSE:
        print(msg)


def _iget(d, key, default=None):
    try:
        return d.get(key, default)
    except AttributeError:
        try:
            return d[key]
        except Exception:
            return getattr(d, key, default)


def track_name_map(armature=None, action=None, skin=None):
    binding = resolve_track_binding(action, armature, skin)
    if not binding.names and armature is None:
        for candidate in bpy.data.objects:
            if getattr(candidate, "type", None) != "ARMATURE":
                continue
            binding = resolve_track_binding(action, candidate, skin)
            if binding.names:
                break
    return {index: name for index, name in enumerate(binding.names)}

def track_property_name(index, name_map):
    if name_map and index in name_map:
        return name_map[index]
    return f"T{index:02d}"


def _resolve_track_payload(action, extras=None):
    source = extras if isinstance(extras, dict) else action
    return source.get('trackKeys') or (), source.get('constTrackKeys') or ()


def _deduplicate_source_keys(frames, values):
    if len(frames) < 2:
        return frames, values
    _, reversed_indices = np.unique(frames[::-1], return_index=True)
    keep = np.sort(len(frames) - 1 - reversed_indices)
    return frames[keep], values[keep]


def _aligned_track_curve(raw_keys):
    count = len(raw_keys)
    frames = np.fromiter(
            (float(_iget(item, 'time', 0.0)) * FPS for item in raw_keys),
            dtype=np.float64,
            count=count,
            )
    values = np.fromiter(
            (float(_iget(item, 'value', 0.0)) for item in raw_keys),
            dtype=np.float64,
            count=count,
            )
    order = np.argsort(frames, kind='stable')
    frames = frames[order]
    values = values[order]
    frames, values = _deduplicate_source_keys(frames, values)

    aligned_frames = np.unique(round_keyframes(frames))
    aligned_values = np.interp(aligned_frames, frames, values)
    if len(aligned_values) > 1 and np.all(
            np.abs(aligned_values - aligned_values[0]) <= 1e-10
            ):
        aligned_frames = aligned_frames[:1]
        aligned_values = aligned_values[:1]
    return aligned_frames, aligned_values


def _prepare_track_curves(track_keys, const_track_keys, zero_epsilon=1e-12):
    animated = defaultdict(list)
    constants = defaultdict(list)
    all_indices = set()

    for entry in track_keys:
        index = _iget(entry, 'trackIndex')
        if index is None:
            continue
        index = int(index)
        animated[index].append(entry)
        all_indices.add(index)

    for entry in const_track_keys:
        index = _iget(entry, 'trackIndex')
        if index is None:
            continue
        index = int(index)
        constants[index].append(float(_iget(entry, 'value', 0.0)))
        all_indices.add(index)

    curves = {}
    omitted_zero = []
    for index in sorted(all_indices):
        raw_keys = animated.get(index)
        if raw_keys:
            raw_values = [float(_iget(item, 'value', 0.0)) for item in raw_keys]
            if not raw_values or max(abs(value) for value in raw_values) <= zero_epsilon:
                omitted_zero.append(index)
                continue
            frames, values = _aligned_track_curve(raw_keys)
            if len(values) == 1 and abs(float(values[0])) <= zero_epsilon:
                omitted_zero.append(index)
                continue
            curves[index] = (frames, values, 'BEZIER')
            continue

        values = constants.get(index, ())
        if not values:
            continue
        minimum = min(values)
        maximum = max(values)
        value = minimum if minimum == maximum else values[-1]
        if abs(value) <= zero_epsilon:
            omitted_zero.append(index)
            continue
        curves[index] = (
            np.asarray((0.0,), dtype=np.float64),
            np.asarray((value,), dtype=np.float64),
            'CONSTANT',
            )

    return curves, tuple(omitted_zero), tuple(sorted(all_indices))


def _plain_track_entries(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if hasattr(value, 'keys'):
        keys = list(value.keys())
        try:
            keys.sort(key=lambda key: int(key))
        except (TypeError, ValueError):
            keys.sort(key=str)
        return [value[key] for key in keys]
    try:
        return list(value)
    except TypeError:
        return []


def _source_track_curve(entries):
    if not entries:
        return None
    frames = np.asarray(
        [float(entry.get("time", 0.0)) * FPS for entry in entries],
        dtype=np.float64,
    )
    values = np.asarray(
        [float(entry.get("value", 0.0)) for entry in entries],
        dtype=np.float64,
    )
    order = np.argsort(frames, kind="stable")
    frames = frames[order]
    values = values[order]
    frames, values = _deduplicate_source_keys(frames, values)
    aligned_frames = np.unique(round_keyframes(frames))
    aligned_values = np.interp(aligned_frames, frames, values)
    if len(aligned_values) > 1 and np.all(
        np.abs(aligned_values - aligned_values[0]) <= 1e-10
    ):
        aligned_frames = aligned_frames[:1]
        aligned_values = aligned_values[:1]
    return aligned_frames, aligned_values


def _track_curve_matches_source(frames, values, source_dynamic, source_const):
    expected = _source_track_curve(source_dynamic)
    if expected is None and source_const is not None:
        expected = (
            np.asarray((0.0,), dtype=np.float64),
            np.asarray((float(source_const.get("value", 0.0)),), dtype=np.float64),
        )
    if expected is None:
        return False
    expected_frames, expected_values = expected
    return (
        frames.shape == expected_frames.shape
        and values.shape == expected_values.shape
        and np.allclose(frames, expected_frames, rtol=0.0, atol=1e-5)
        and np.allclose(values, expected_values, rtol=0.0, atol=1e-6)
    )


def track_payload_from_fcurves(
    action,
    armature=None,
    *,
    source_track_keys=None,
    source_const_track_keys=None,
    skin_extras=None,
    track_binding=None,
    error_type=ValueError,
):
    binding = track_binding or resolve_track_binding(action, armature, skin_extras)
    track_names = binding.names
    if len(binding.index_by_name) != len(track_names):
        raise error_type("The animation skin extras contain duplicate trackNames.")
    track_index_by_path = binding.index_by_path
    indexed_curves = []
    seen_indices = set()
    for curve in get_action_fcurves(action, armature) or ():
        index = track_index_by_path.get(str(curve.data_path))
        if index is None:
            continue
        if index in seen_indices:
            raise error_type(
                f"Action {action.name!r} has multiple FCurves for track "
                f"{track_names[index]!r}."
            )
        seen_indices.add(index)
        indexed_curves.append((index, curve))
    indexed_curves.sort(key=lambda item: item[0])

    action_start = float(action.frame_range[0])
    source_track_keys = [
        copy.deepcopy(entry)
        for entry in (source_track_keys or ())
        if isinstance(entry, dict)
    ]
    source_const_track_keys = [
        copy.deepcopy(entry)
        for entry in (source_const_track_keys or ())
        if isinstance(entry, dict)
    ]
    source_dynamic_by_index = {}
    for entry in source_track_keys:
        source_dynamic_by_index.setdefault(int(entry.get("trackIndex", -1)), []).append(entry)
    source_const_by_index = {
        int(entry.get("trackIndex", -1)): entry for entry in source_const_track_keys
    }

    track_keys = []
    const_track_keys = []
    emitted_indices = set()
    for track_index, curve in indexed_curves:
        points = curve.keyframe_points
        if not len(points):
            continue
        coordinates = np.empty(len(points) * 2, dtype=np.float64)
        points.foreach_get("co", coordinates)
        frames = coordinates[0::2]
        values = coordinates[1::2]
        order = np.argsort(frames, kind="stable")
        frames = frames[order]
        values = values[order]
        relative_frames = frames - action_start
        source_entries = source_dynamic_by_index.get(track_index, ())
        source_const = source_const_by_index.get(track_index)
        if _track_curve_matches_source(
            relative_frames, values, source_entries, source_const
        ):
            if source_entries:
                track_keys.extend(copy.deepcopy(source_entries))
            elif source_const is not None:
                const_track_keys.append(copy.deepcopy(source_const))
            emitted_indices.add(track_index)
            continue
        if np.all(np.abs(values - values[0]) <= 1e-9):
            const_track_keys.append({
                "trackIndex": int(track_index),
                "time": float(source_const.get("time", 0.0))
                if source_const is not None else 0.0,
                "value": float(values[0]),
            })
            emitted_indices.add(track_index)
            continue
        for key_index, (frame, value) in enumerate(zip(frames, values)):
            relative_frame = float(frame) - action_start
            if relative_frame < -1e-7:
                raise error_type(
                    f"Action {action.name!r} track {track_names[track_index]!r} "
                    "contains a key before its frame range start."
                )
            time_value = max(0.0, relative_frame) / FPS
            if key_index < len(source_entries):
                source_time = float(source_entries[key_index].get("time", time_value))
                if abs(source_time * FPS - relative_frame) <= 1e-3:
                    time_value = source_time
            track_keys.append({
                "trackIndex": int(track_index),
                "time": time_value,
                "value": float(value),
            })
        emitted_indices.add(track_index)
    for entry in source_const_track_keys:
        if int(entry.get("trackIndex", -1)) not in emitted_indices:
            const_track_keys.append(entry)
    for entry in source_track_keys:
        if int(entry.get("trackIndex", -1)) not in emitted_indices:
            track_keys.append(entry)
    return track_keys, const_track_keys


def export_anim_tracks(action, armature=None):
    track_keys, const_track_keys = track_payload_from_fcurves(
        action,
        armature,
        source_track_keys=_plain_track_entries(action.get("trackKeys")),
        source_const_track_keys=_plain_track_entries(action.get("constTrackKeys")),
    )
    action["trackKeys"] = track_keys
    action["constTrackKeys"] = const_track_keys
    if "optimizationHints" not in action:
        action["optimizationHints"] = copy.deepcopy(ACTION_DEFAULTS["optimizationHints"])
    return len(track_keys) + len(const_track_keys)

def _armature_cache_key(armature):
    try:
        return int(armature.as_pointer())
    except (AttributeError, TypeError, ValueError):
        return id(armature)


def ensure_track_property(
    owner,
    name,
    value=0.0,
    *,
    default=0.0,
    minimum=-3.40282e38,
    maximum=3.40282e38,
    soft_minimum=None,
    soft_maximum=None,
    description=None,
    subtype="NONE",
    overwrite_ui=False,
):
    created = configure_float_idproperty(
        owner,
        name,
        value,
        default=default,
        minimum=minimum,
        maximum=maximum,
        soft_minimum=minimum if soft_minimum is None else soft_minimum,
        soft_maximum=maximum if soft_maximum is None else soft_maximum,
        description=description,
        subtype=subtype,
        overwrite_ui=overwrite_ui,
    )
    if created:
        try:
            owner.property_overridable_library_set(f'["{name}"]', True)
        except (AttributeError, RuntimeError, TypeError):
            pass
    return created


def ensure_track_properties(track_properties=None, armatures=None):
    track_properties = track_properties or []
    armature_list = (
        [obj for obj in armatures if obj is not None and obj.type == 'ARMATURE']
        if armatures is not None
        else [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    )
    for armature in armature_list:
        cache_key = _armature_cache_key(armature)
        cache_entry = _TRACK_PROPERTY_CACHE.get(cache_key)
        if cache_entry is not None and cache_entry[0] is armature:
            cached = cache_entry[1]
        else:
            cached = set()
            _TRACK_PROPERTY_CACHE[cache_key] = (armature, cached)
        for prop_name in track_properties:
            if prop_name in cached and isinstance(armature.get(prop_name), float):
                continue
            try:
                current = armature.get(prop_name, 0.0)
                try:
                    value = float(current)
                except (TypeError, ValueError):
                    value = 0.0
                ensure_track_property(armature, prop_name, value)
                cached.add(prop_name)
            except Exception as error:
                print(
                        f"Error creating custom track property ({prop_name}) "
                        f"on Armature [{armature.name}]: {error}"
                        )


_FACIAL_RANGE_2 = frozenset({1, 2, 7, 8})
_FACIAL_ENVELOPE_DESCRIPTIONS = {
    0: "Face envelope — master facial weight",
    1: "Upper face envelope (0–2)",
    2: "Lower face envelope (0–2)",
    3: "Anti-stretch envelope",
    4: "Lipsync envelope — master lipsync weight",
    5: "Lipsync left-side envelope",
    6: "Lipsync right-side envelope",
    7: "JALI jaw slider (0–2)",
    8: "JALI lips slider (0–2)",
    9: "Muzzle lips",
    10: "Muzzle eyes",
    11: "Muzzle brows",
    12: "Muzzle eye directions",
}


def _facial_track_description(index, name, segments):
    if index in _FACIAL_ENVELOPE_DESCRIPTIONS:
        return _FACIAL_ENVELOPE_DESCRIPTIONS[index]
    if segments is None:
        return f"Facial track {index}: {name}"
    if segments.main_start <= index < segments.main_end:
        return f"Main pose weight — {name}"
    if segments.lipsync_ovr_start <= index < segments.lipsync_ovr_end:
        return f"Lipsync override weight — {name}"
    if segments.lipsync_out_start <= index < segments.lipsync_out_end:
        return f"[OUTPUT] Lipsync pose output — {name}"
    if segments.wrinkle_start <= index < segments.wrinkle_end:
        return f"[OUTPUT] Wrinkle weight — {name}"
    return name


def ensure_rig_track_properties(owner, rig, segments=None, *, apply_defaults=False):
    if owner is None or getattr(owner, "type", None) != "ARMATURE":
        return 0
    defaults = getattr(rig, "reference_tracks", ())
    count = 0
    for index, raw_name in enumerate(getattr(rig, "track_names", ())):
        name = raw_name.get("$value", "") if isinstance(raw_name, dict) else str(raw_name)
        if not name:
            continue
        default = float(defaults[index]) if index < len(defaults) else 0.0
        current = owner.get(name)
        value = default if apply_defaults or current is None else float(current)
        maximum = 2.0 if index in _FACIAL_RANGE_2 else 1.0
        ensure_track_property(
            owner,
            name,
            value,
            default=default,
            minimum=0.0,
            maximum=maximum,
            soft_minimum=0.0,
            soft_maximum=maximum,
            description=_facial_track_description(index, name, segments),
            subtype="FACTOR",
            overwrite_ui=True,
        )
        count += 1
    return count


def prepare_anim_track_properties(animation_extras, armature):
    indices = set()
    for extras in animation_extras:
        for key_name in ("trackKeys", "constTrackKeys"):
            for entry in _iget(extras, key_name, ()) or ():
                index = _iget(entry, "trackIndex")
                if index is not None:
                    indices.add(int(index))
    if not indices:
        return 0
    name_map = track_name_map(armature)
    properties = [track_property_name(index, name_map) for index in sorted(indices)]
    ensure_track_properties(properties, armatures=[armature])
    return len(properties)


def _get_action_groups(action, armature=None, *, create=False):
    return get_action_groups(action, armature, create=create)


def get_track_action_group_name():
    return "Track Keys"


def remove_track_action_group(action, armature=None):
    groups = _get_action_groups(action, armature)
    if groups is None:
        return
    try:
        group_name = get_track_action_group_name()
        group_id = groups.find(group_name)
        if group_id >= 0:
            groups.remove(groups[group_id])
    except Exception as e:
        print(f"Error removing custom track action group: {e}")


def add_track_action_group(action, armature=None):
    groups = _get_action_groups(action, armature, create=True)
    if groups is None:
        return None
    try:
        group_name = get_track_action_group_name()
        group_id = groups.find(group_name)
        if group_id < 0:
            return groups.new(group_name)
        else:
            return groups[group_id]
    except Exception as e:
        print(f"Error adding custom track action group: {e}")
        return None


def import_anim_tracks(
        action,
        armature=None,
        ensure_properties=True,
        *,
        extras=None,
        replace_existing=True,
        ):
    track_keys, const_track_keys = _resolve_track_payload(action, extras)
    curves, omitted_zero, all_indices = _prepare_track_curves(
            track_keys, const_track_keys
            )

    if ensure_properties and all_indices:
        name_map = track_name_map(armature, action)
        ensure_track_properties(
                [track_property_name(index, name_map) for index in all_indices],
                armatures=[armature] if armature is not None else None,
                )

    if not curves:
        return {
            'curve_count': 0,
            'keypoint_count': 0,
            'omitted_zero_count': len(omitted_zero),
            }

    fcurves = get_action_fcurves(action, armature, create=True)
    if fcurves is None:
        _vprint('import_anim_tracks: no fcurves collection available')
        return {
            'curve_count': 0,
            'keypoint_count': 0,
            'omitted_zero_count': len(omitted_zero),
            }

    action_group = add_track_action_group(action, armature)
    name_map = track_name_map(armature, action)
    existing = {curve.data_path: curve for curve in fcurves} if replace_existing else {}
    keypoint_count = 0

    for index, (frames, values, interpolation) in curves.items():
        data_path = f'["{track_property_name(index, name_map)}"]'
        previous = existing.get(data_path)
        if previous is not None:
            fcurves.remove(previous)
        curve = fcurves.new(data_path=data_path)
        if action_group is not None:
            curve.group = action_group
        keypoint_count += bulk_set_keyframes(
                curve,
                frames,
                values,
                interpolation=None if interpolation == 'BEZIER' else interpolation,
                update=(interpolation == 'BEZIER'),
                )

    _vprint(
            f'{keypoint_count} Track Keys Imported into {len(curves)} curves; '
            f'{len(omitted_zero)} zero curves omitted'
            )
    return {
        'curve_count': len(curves),
        'keypoint_count': keypoint_count,
        'omitted_zero_count': len(omitted_zero),
        }


def fix_anim_frame_alignment(action, armature=None):
    fcurves = get_action_fcurves(action, armature)
    if fcurves is None:
        return

    curves_by_path = defaultdict(list)
    for curve in fcurves:
        if curve.data_path.startswith('pose.bones['):
            curves_by_path[curve.data_path].append(curve)

    for data_path, curves in curves_by_path.items():
        num_fixed = 0
        for curve in curves:
            points = curve.keyframe_points
            key_count = len(points)
            if key_count == 0:
                continue
            coordinates = np.empty(key_count * 2, dtype=np.float64)
            points.foreach_get('co', coordinates)
            source_frames = coordinates[0::2]
            source_values = coordinates[1::2]
            aligned_frames = round_keyframes(source_frames)
            num_fixed += int(np.count_nonzero(aligned_frames != source_frames))
            unique_frames = np.unique(aligned_frames)
            if num_fixed == 0 and len(unique_frames) == key_count:
                continue
            aligned_values = np.asarray(
                    [curve.evaluate(float(frame)) for frame in unique_frames],
                    dtype=np.float64,
                    )
            source_min = float(np.min(source_values))
            source_max = float(np.max(source_values))
            aligned_min = float(np.min(aligned_values))
            aligned_max = float(np.max(aligned_values))
            if source_min == source_max and aligned_min != aligned_max:
                _vprint(
                    f'org {source_min} == {source_max} but '
                    f'{aligned_min} != {aligned_max} Re-Aligned'
                )
            if aligned_min == aligned_max and source_min != source_max:
                _vprint(
                    f'org {source_min} != {source_max} but '
                    f'{aligned_min} == {aligned_max} Re-Aligned'
                )
            interpolation = points[0].interpolation
            points.clear()
            bulk_set_keyframes(
                    curve,
                    unique_frames,
                    aligned_values,
                    interpolation=interpolation,
                    )
        if num_fixed:
            _vprint(f'{data_path} Re-Aligned Timing for {num_fixed} Frames')


def sparse_track_indices(values, threshold: float = 0.005) -> np.ndarray:
    track_values = np.asarray(values)
    frame_count = len(track_values)
    selected = []
    previous_value = None
    for frame_index, value in enumerate(track_values):
        current = float(value)
        if (
            frame_index == 0
            or frame_index == frame_count - 1
            or previous_value is None
            or abs(current - previous_value) > float(threshold)
        ):
            selected.append(frame_index)
            previous_value = current
    return np.asarray(selected, dtype=np.intp)


def write_track_matrix(
    armature,
    track_names,
    values,
    *,
    action_name: str = "Track Animation",
    start_frame: float = 1.0,
    threshold: float = 0.005,
) -> int:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError("Track values must be a frame-by-track matrix")
    names = tuple(str(name) for name in track_names)
    if matrix.shape[1] != len(names):
        raise ValueError("Track matrix width does not match the track-name count")
    animation_data = armature.animation_data_create()
    action = animation_data.action
    if action is None:
        from ..blender.transactions import new_tracked_datablock

        action = new_tracked_datablock("actions", name=action_name)
        action.use_fake_user = True
        assign_action_with_slot(armature, action)
    skin = armature_skin_extras(armature)
    skin["trackNames"] = list(names)
    store_action_source(action, skin=skin)
    fcurves = get_action_fcurves(action, armature, create=True)
    if fcurves is None:
        raise RuntimeError(f"Unable to access FCurves for action {action.name!r}")
    group = add_track_action_group(action, armature)
    frame_count = matrix.shape[0]
    all_frames = np.arange(frame_count, dtype=np.float64) + float(start_frame)
    keyed = 0
    for index, name in enumerate(names):
        if not name:
            continue
        track_values = matrix[:, index]
        if not len(track_values) or float(np.max(np.abs(track_values))) < 0.001:
            continue
        data_path = f'["{name}"]'
        previous = fcurves.find(data_path=data_path)
        if previous is not None:
            fcurves.remove(previous)
        curve = fcurves.new(data_path=data_path)
        if group is not None:
            curve.group = group
        selected = sparse_track_indices(track_values, threshold)
        bulk_set_keyframes(
            curve,
            all_frames[selected],
            track_values[selected],
            interpolation="LINEAR",
        )
        keyed += 1
    return keyed
