from collections import defaultdict

import bpy
import numpy as np

from .compat import (
    bulk_set_keyframes,
    configure_float_idproperty,
    get_action_fcurves,
    get_action_groups,
    round_keyframes,
    )

_DEF_FPS = 30.0
_VERBOSE = False
_TRACK_PROPERTY_CACHE = {}


def _set_verbose(val: bool):
    global _VERBOSE
    _VERBOSE = bool(val)


def _vprint(msg: str):
    if _VERBOSE:
        print(msg)


def _iget(d, key, default=None):
    """Getter for IDPropertyGroup/dict/attrs."""
    try:
        return d.get(key, default)
    except AttributeError:
        try:
            return d[key]
        except Exception:
            return getattr(d, key, default)


#  Track-name resolution from armature skin extras

def _get_track_name_map(armature=None):
    candidates = [armature] if armature else [
        obj for obj in bpy.data.objects
        if obj.type == 'ARMATURE' and (
                obj.get("trackNames") is not None or obj.get("numTrackNames", 0) > 0
        )
        ]
    for arm in candidates:
        if arm is None:
            continue

        # read_rig stores canonical track names on armature data; native glTF
        # imports may store them on the object through skin extras.
        tn = arm.get("trackNames")
        if tn is None and getattr(arm, "data", None) is not None:
            tn = arm.data.get("trackNames")
        if tn is not None and hasattr(tn, 'keys'):
            return {int(k): str(v) for k, v in tn.items()}
        if tn is not None and not isinstance(tn, (str, bytes)):
            return {index: str(value) for index, value in enumerate(tn)}

        # Legacy format: numTrackNames + trackName_{i}
        num = arm.get("numTrackNames", 0)
        if num > 0:
            return {
                i: arm.get(f"trackName_{i}", f"T{i:02d}")
                for i in range(num)
                }
    return {}


def _track_prop_name(index, name_map):
    """Return the custom-property name for a track index.

    Uses the real track name from *name_map* when available, falling back
    to the legacy ``T00`` / ``T01`` format.
    """
    if name_map and index in name_map:
        return name_map[index]
    return f"T{index:02d}"


def _track_data_path(prop_name):
    """Return the FCurve data-path string for a track property name."""
    return f'["{prop_name}"]'


#  Bulk keyframe helpers  (foreach_set is ~10-50× faster than per-kf .co =)

def _bulk_set_keyframes(fc, frames, values, interpolation=None, *, update=False):
    return bulk_set_keyframes(
            fc, frames, values, interpolation=interpolation, update=update
            )


def _round_track_frames(frames):
    return round_keyframes(frames)


def _resolve_track_payload(action, extras=None):
    source = extras if isinstance(extras, dict) else action
    return source.get('trackKeys') or (), source.get('constTrackKeys') or ()


def _round_track_frames(frames):
    frames = np.asarray(frames, dtype=np.float64)
    lower = np.floor(frames)
    upper = np.ceil(frames)
    return np.where((upper - frames) < (frames - lower), upper, lower)


def _deduplicate_source_keys(frames, values):
    if len(frames) < 2:
        return frames, values
    _, reversed_indices = np.unique(frames[::-1], return_index=True)
    keep = np.sort(len(frames) - 1 - reversed_indices)
    return frames[keep], values[keep]


def _aligned_track_curve(raw_keys):
    count = len(raw_keys)
    frames = np.fromiter(
            (float(_iget(item, 'time', 0.0)) * _DEF_FPS for item in raw_keys),
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

    aligned_frames = np.unique(_round_track_frames(frames))
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


#  Export – synchronize track FCurves with individual Action properties

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


def export_anim_tracks(action, armature=None):
    """Rebuild Action trackKeys from live track FCurves without removing them."""
    obj = {
        "trackKeys": _plain_track_entries(action.get("trackKeys")),
        "constTrackKeys": _plain_track_entries(action.get("constTrackKeys")),
        }
    num_exported = 0
    fcurves = get_action_fcurves(action, armature)
    name_map = _get_track_name_map(armature)

    track_fc_info = []
    if fcurves is not None and name_map:
        path_to_index = {
            _track_data_path(prop_name): index
            for index, prop_name in name_map.items()
            }
        for curve in fcurves:
            index = path_to_index.get(curve.data_path)
            if index is not None:
                track_fc_info.append((index, curve))

    for track_index, curve in track_fc_info:
        obj['trackKeys'] = [
            entry for entry in obj['trackKeys']
            if int(_iget(entry, 'trackIndex', -1)) != track_index
            ]
        obj['constTrackKeys'] = [
            entry for entry in obj['constTrackKeys']
            if int(_iget(entry, 'trackIndex', -1)) != track_index
            ]
        key_count = len(curve.keyframe_points)
        if not key_count:
            continue

        coordinates = np.empty(key_count * 2, dtype=np.float64)
        curve.keyframe_points.foreach_get('co', coordinates)
        frames = coordinates[0::2]
        values = coordinates[1::2]
        order = np.argsort(frames, kind='stable')
        frames = frames[order]
        values = values[order]
        minimum = float(np.min(values))
        maximum = float(np.max(values))

        if abs(maximum - minimum) <= 1e-10:
            obj['constTrackKeys'].append({
                'trackIndex': int(track_index),
                'value': float(values[-1]),
                'time': 0.0,
                })
            num_exported += 1
        else:
            obj['trackKeys'].extend(
                {
                    'trackIndex': int(track_index),
                    'value': float(value),
                    'time': float(frame) / _DEF_FPS,
                    }
                for frame, value in zip(frames, values)
                )
            num_exported += key_count

    action['trackKeys'] = obj['trackKeys']
    action['constTrackKeys'] = obj['constTrackKeys']
    if 'optimizationHints' not in action:
        action['optimizationHints'] = {
            'preferSIMD': False,
            'maxRotationCompression': 0,
            }
    _vprint(f'{num_exported} Tracks Exported')


#  Custom properties on armatures for track channels

def _armature_cache_key(armature):
    try:
        return int(armature.as_pointer())
    except (AttributeError, TypeError, ValueError):
        return id(armature)


def add_track_properties(track_properties=None, armatures=None):
    """Create missing float track properties without replacing existing UI metadata."""
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
                created = configure_float_idproperty(
                        armature,
                        prop_name,
                        value,
                        default=0.0,
                        minimum=-3.40282e+38,
                        maximum=3.40282e+38,
                        soft_minimum=-3.40282e+38,
                        soft_maximum=3.40282e+38,
                        subtype='NONE',
                        overwrite_ui=False,
                        )
                if created:
                    try:
                        armature.property_overridable_library_set(f'["{prop_name}"]', True)
                    except Exception:
                        pass
                cached.add(prop_name)
            except Exception as error:
                print(
                        f"Error creating custom track property ({prop_name}) "
                        f"on Armature [{armature.name}]: {error}"
                        )


def prepare_anim_track_properties(animation_extras, armature):
    """Create the union of all track properties before action construction."""
    indices = set()
    for extras in animation_extras:
        for key_name in ("trackKeys", "constTrackKeys"):
            for entry in _iget(extras, key_name, ()) or ():
                index = _iget(entry, "trackIndex")
                if index is not None:
                    indices.add(int(index))
    if not indices:
        return 0
    name_map = _get_track_name_map(armature)
    properties = [_track_prop_name(index, name_map) for index in sorted(indices)]
    add_track_properties(properties, armatures=[armature])
    return len(properties)


#  Track action group helpers

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


#  Import – Create FCurves for anim tracks (with frame-alignment fix)

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
        name_map = _get_track_name_map(armature)
        add_track_properties(
                [_track_prop_name(index, name_map) for index in all_indices],
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
    name_map = _get_track_name_map(armature)
    existing = {curve.data_path: curve for curve in fcurves} if replace_existing else {}
    keypoint_count = 0

    for index, (frames, values, interpolation) in curves.items():
        data_path = _track_data_path(_track_prop_name(index, name_map))
        previous = existing.get(data_path)
        if previous is not None:
            fcurves.remove(previous)
        curve = fcurves.new(data_path=data_path)
        if action_group is not None:
            curve.group = action_group
        keypoint_count += _bulk_set_keyframes(
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


#  POSE BONES – Correct timing misalignment (sub-frame quantisation)

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
                _vprint(f'org {source_min} == {source_max} but {aligned_min} != {aligned_max} Re-Aligned')
            if aligned_min == aligned_max and source_min != source_max:
                _vprint(f'org {source_min} != {source_max} but {aligned_min} == {aligned_max} Re-Aligned')
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
