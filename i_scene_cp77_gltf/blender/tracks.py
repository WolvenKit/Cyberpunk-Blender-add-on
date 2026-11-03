from collections import defaultdict

import bpy
import numpy as np

from ..animation.domain.clip.tracks import (
    FACIAL_RANGE_2,
    TRACK_ACTION_GROUP_NAME,
    compressed_track_segment_tangents,
    entry_value,
    facial_track_description,
    prepare_track_curves,
    sparse_track_indices,
    track_curve_matches_source,
    track_payload_fits_simd_grid,
    track_property_name,
)
from ..animation.model.clip.binding import track_property_path
from ..animation.model.clip.metadata import (
    ANIMATION_EXTRAS_SNAPSHOT_KEY,
    FPS,
    TRACK_CURVES_SNAPSHOT_KEY,
    TRACKS_IMPORTED_KEY,
    indexed_strings,
    track_payload_duration,
)
from ..assetio.values import coerce_float
from ..bartmoss.curve import ordered_key_samples
from ..core.log import get_logger, log_once
from .action_metadata import (
    action_export_name,
    armature_skin_extras,
    ensure_action_defaults,
    load_json_snapshot,
    resolve_track_binding,
    store_action_source,
    store_json_snapshot,
)
from .identity import rna_identity
from .keyframes import (
    assign_action_with_slot,
    bulk_set_keyframes,
    curve_coordinates,
    get_action_fcurves,
    get_action_groups,
    replace_fcurve_keyframes,
    scalar_curve_fingerprints,
)
from .transactions import new_tracked_datablock

_LOG = get_logger(__name__)

_TRACK_PROPERTY_CACHE = {}


def clear_track_property_cache():
    _TRACK_PROPERTY_CACHE.clear()


def reference_track_values(armature, names) -> dict[str, float]:
    track_names = ()
    reference_values = ()
    arm_data = getattr(armature, "data", None)
    if arm_data is not None:
        track_names = indexed_strings(arm_data.get("trackNames"))
        reference_values = arm_data.get("referenceTracks", ()) or ()
    reference_by_name = {
        str(name): float(reference_values[index])
        for index, name in enumerate(track_names)
        if index < len(reference_values)
    }

    result = {}
    for name in names:
        default = reference_by_name.get(name)
        if default is None:
            try:
                default = armature.id_properties_ui(name).as_dict().get("default")
            except (
                AttributeError,
                KeyError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("reference_track_values", type(error).__name__),
                    "reference track values: fell back after %s",
                    error,
                    exc_info=True,
                )
                default = None
        if default is None:
            default = 0.0
        result[str(name)] = float(default or 0.0)
    return result


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


def _set_compressed_track_handles(curve, frames, values):
    frames = np.asarray(frames, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    points = curve.keyframe_points
    count = len(points)
    if count < 2:
        if count == 1:
            points[0].interpolation = "BEZIER"
        curve.update()
        return

    for point in points:
        point.interpolation = "BEZIER"
        point.handle_left_type = "FREE"
        point.handle_right_type = "FREE"

    for index in range(count - 1):
        p1 = float(values[index])
        p2 = float(values[index + 1])
        p0 = float(values[index - 1]) if index > 0 else p1
        p3 = float(values[index + 2]) if index + 2 < count else p2
        tangent1, tangent2 = compressed_track_segment_tangents(p0, p1, p2, p3)
        left_frame = float(frames[index])
        right_frame = float(frames[index + 1])
        span = right_frame - left_frame
        points[index].handle_right = (
            left_frame + span / 3.0,
            p1 + tangent1 / 3.0,
        )
        points[index + 1].handle_left = (
            right_frame - span / 3.0,
            p2 - tangent2 / 3.0,
        )

    first_span = float(frames[1] - frames[0])
    last_span = float(frames[-1] - frames[-2])
    points[0].handle_left = (
        float(frames[0]) - first_span / 3.0,
        float(values[0]),
    )
    points[-1].handle_right = (
        float(frames[-1]) + last_span / 3.0,
        float(values[-1]),
    )
    curve.update()


def track_payload_from_fcurves(
    action,
    armature=None,
    *,
    source_track_keys=None,
    source_const_track_keys=None,
    skin_extras=None,
    track_binding=None,
    prefer_simd=False,
    duration_seconds=None,
    error_type=ValueError,
):
    """Preserve untouched raw scalar payloads and serialize live track values by rig index"""
    binding = track_binding or resolve_track_binding(action, armature, skin_extras)
    if len(binding.index_by_name) != len(binding.names):
        raise error_type("The animation skin extras contain duplicate trackNames.")
    indexed_curves = {}
    for curve in get_action_fcurves(action, armature) or ():
        index = binding.index_by_path.get(str(curve.data_path))
        if index is None:
            continue
        if int(curve.array_index) != 0 or index in indexed_curves:
            raise error_type(
                f"Action {action.name!r} track {binding.name(index)!r} must have one scalar F-Curve."
            )
        if curve.mute or any(not modifier.mute for modifier in curve.modifiers):
            raise error_type(
                f"Action {action.name!r} track {binding.name(index)!r} has a muted curve or live modifiers. Bake the track before export."
            )
        indexed_curves[index] = curve
    source_dynamic = defaultdict(list)
    source_constants = defaultdict(list)
    for entry in source_track_keys or ():
        source_dynamic[int(entry["trackIndex"])].append(dict(entry))
    for entry in source_const_track_keys or ():
        source_constants[int(entry["trackIndex"])].append(dict(entry))
    snapshot = load_json_snapshot(action, TRACK_CURVES_SNAPSHOT_KEY)
    imported_curves = snapshot.get("curves", {})
    preserve_unkeyed = not bool(action.get(TRACKS_IMPORTED_KEY, False))
    action_start = float(action.frame_range[0])
    states = {}
    unchanged = set()
    for index, curve in indexed_curves.items():
        states[index] = scalar_curve_fingerprints(curve)
        original = imported_curves.get(str(index))
        if original and original["curve"] == states[index]["curve"]:
            unchanged.add(index)
        elif original is None:
            frames, values = curve_coordinates(curve, sort=True)
            if track_curve_matches_source(
                frames - action_start,
                values,
                source_dynamic.get(index),
                next(iter(source_constants.get(index, ())), None),
            ):
                unchanged.add(index)
        elif (
            original["coordinates"] == states[index]["coordinates"]
            and not prefer_simd
            and not len(curve.sampled_points)
        ):
            raise error_type(
                f"Action {action.name!r} track {binding.name(index)!r} has edited interpolation. Raw compressed track keys store values and times; bake the curve or use SIMD storage."
            )
    source_indices = set(source_dynamic) | set(source_constants)
    codec_unchanged = not snapshot or bool(snapshot.get("preferSIMD")) == bool(
        prefer_simd
    )
    if duration_seconds is None:
        duration_seconds = max(
            float(action.get("cp77_direct_anim_duration_seconds", 0.0)),
            max(0.0, float(action.frame_range[1]) - action_start) / FPS,
            max(
                (
                    float(entry["time"])
                    for entries in source_dynamic.values()
                    for entry in entries
                ),
                default=0.0,
            ),
            max(
                (
                    float(entry["time"])
                    for entries in source_constants.values()
                    for entry in entries
                ),
                default=0.0,
            ),
        )
    native_duration = float(np.float32(duration_seconds))
    if not np.isfinite(native_duration) or native_duration < 0:
        raise error_type(f"Action {action.name!r} has an invalid track duration.")
    needs_resampling = bool(source_dynamic) and track_payload_needs_resampling(
        action,
        source_track_keys=source_track_keys,
        prefer_simd=prefer_simd,
        duration_seconds=native_duration,
    )
    if needs_resampling and preserve_unkeyed and source_indices - set(indexed_curves):
        raise error_type(
            f"Action {action.name!r} needs a new SIMD float-track grid. Import its float tracks before changing the duration or storage encoding."
        )
    if (
        codec_unchanged
        and not needs_resampling
        and not (set(indexed_curves) - source_indices)
        and set(indexed_curves).issubset(unchanged)
        and (preserve_unkeyed or source_indices == set(indexed_curves))
    ):
        return [dict(entry) for entry in source_track_keys or ()], [
            dict(entry) for entry in source_const_track_keys or ()
        ]
    simd_times = None
    if prefer_simd:
        count = max(2, int(np.ceil(native_duration * FPS)))
        simd_times = (
            np.linspace(0.0, native_duration, count)
            .astype(np.float32)
            .astype(np.float64)
            if native_duration > 0
            else np.asarray([0.0])
        )
    track_keys, const_track_keys = [], []
    for index in sorted(source_indices | set(indexed_curves)):
        curve = indexed_curves.get(index)
        if curve is None:
            if preserve_unkeyed:
                track_keys.extend(source_dynamic.get(index, ()))
                const_track_keys.extend(source_constants.get(index, ()))
            continue
        if not prefer_simd and index in unchanged:
            track_keys.extend(source_dynamic.get(index, ()))
            const_track_keys.extend(source_constants.get(index, ()))
            continue
        if prefer_simd and index in unchanged and bool(snapshot.get("preferSIMD")):
            times = simd_times
            source = source_dynamic.get(index)
            if source:
                source_times = np.asarray(
                    [entry["time"] for entry in source], dtype=np.float32
                ).astype(np.float64)
                source_values = np.asarray(
                    [entry["value"] for entry in source], dtype=np.float32
                ).astype(np.float64)
                source_times, source_values = ordered_key_samples(
                    source_times, source_values
                )
                values = np.interp(times, source_times, source_values)
            else:
                values = np.full(
                    len(times), float(source_constants[index][-1]["value"])
                )
        else:
            frames, values = curve_coordinates(curve, sort=True)
            if not len(frames):
                continue
            relative_frames = frames - action_start
            if (
                not np.all(np.isfinite(frames))
                or not np.all(np.isfinite(values))
                or np.any(relative_frames < -1e-7)
            ):
                raise error_type(
                    f"Action {action.name!r} track {binding.name(index)!r} has invalid key coordinates."
                )
            if prefer_simd:
                times = simd_times
                values = np.fromiter(
                    (
                        curve.evaluate(float(action_start + time * FPS))
                        for time in times
                    ),
                    dtype=np.float64,
                    count=len(times),
                )
            else:
                source_times = {
                    float(np.float32(entry["time"] * FPS)): float(entry["time"])
                    for entry in source_dynamic.get(index, ())
                }
                times = np.asarray(
                    [
                        source_times.get(
                            float(np.float32(frame)), max(0.0, float(frame)) / FPS
                        )
                        for frame in relative_frames
                    ]
                )
        if prefer_simd:
            values = np.asarray(values, dtype=np.float32).astype(np.float64)
        if not np.all(np.isfinite(values)):
            raise error_type(
                f"Action {action.name!r} track {binding.name(index)!r} evaluates to non-finite values."
            )
        if np.all(values == values[0]):
            previous = next(iter(source_constants.get(index, ())), {})
            const_track_keys.append(
                {
                    "trackIndex": index,
                    "time": float(previous.get("time", 0.0)),
                    "value": float(values[0]),
                }
            )
        else:
            track_keys.extend(
                {"trackIndex": index, "time": float(time), "value": float(value)}
                for time, value in zip(times, values)
            )
    return track_keys, const_track_keys


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
            owner.property_overridable_library_set(track_property_path(name), True)
        except (AttributeError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("ensure_track_property", type(error).__name__),
                "ensure track property: fell back after %s",
                error,
                exc_info=True,
            )
    return created


def ensure_track_properties(track_properties=None, armatures=None):
    track_properties = track_properties or []
    armature_list = (
        [obj for obj in armatures if obj is not None and obj.type == "ARMATURE"]
        if armatures is not None
        else [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    )
    for armature in armature_list:
        cache_key = rna_identity(armature)
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
                value = coerce_float(current, 0.0, unwrap=False)
                ensure_track_property(armature, prop_name, value)
                cached.add(prop_name)
            except Exception as error:
                _LOG.warning(
                    "Unable to create custom track property (%s) on Armature [%s]: %s",
                    prop_name,
                    armature.name,
                    error,
                    exc_info=True,
                )


def ensure_rig_track_properties(owner, rig, segments=None, *, apply_defaults=False):
    if owner is None or getattr(owner, "type", None) != "ARMATURE":
        return 0
    defaults = getattr(rig, "reference_tracks", ())
    count = 0
    for index, raw_name in enumerate(getattr(rig, "track_names", ())):
        name = (
            raw_name.get("$value", "") if isinstance(raw_name, dict) else str(raw_name)
        )
        if not name:
            continue
        default = float(defaults[index]) if index < len(defaults) else 0.0
        current = owner.get(name)
        value = default if apply_defaults or current is None else float(current)
        maximum = 2.0 if index in FACIAL_RANGE_2 else 1.0
        ensure_track_property(
            owner,
            name,
            value,
            default=default,
            minimum=0.0,
            maximum=maximum,
            soft_minimum=0.0,
            soft_maximum=maximum,
            description=facial_track_description(index, name, segments),
            subtype="FACTOR",
            overwrite_ui=True,
        )
        count += 1
    return count


def prepare_anim_track_properties(animation_extras, armature):
    indices = set()
    for extras in animation_extras:
        for key_name in ("trackKeys", "constTrackKeys"):
            for entry in entry_value(extras, key_name, ()) or ():
                index = entry_value(entry, "trackIndex")
                if index is not None:
                    indices.add(int(index))
    if not indices:
        return 0
    name_map = track_name_map(armature)
    properties = [track_property_name(index, name_map) for index in sorted(indices)]
    ensure_track_properties(properties, armatures=[armature])
    return len(properties)


def add_track_action_group(action, armature=None):
    groups = get_action_groups(action, armature, create=True)
    if groups is None:
        return None
    try:
        group_name = TRACK_ACTION_GROUP_NAME
        group_id = groups.find(group_name)
        if group_id < 0:
            return groups.new(group_name)
        else:
            return groups[group_id]
    except Exception as e:
        _LOG.error("Unable to add custom track action group: %s", e, exc_info=True)
        return None


def import_anim_tracks(
    action,
    armature=None,
    ensure_properties=True,
    *,
    extras=None,
    replace_existing=True,
):
    track_keys, const_track_keys = resolve_track_payload(action, extras)
    action[TRACKS_IMPORTED_KEY] = True
    hints = (
        entry_value(
            extras if isinstance(extras, dict) else action, "optimizationHints", {}
        )
        or {}
    )
    prefer_simd = bool(entry_value(hints, "preferSIMD", False))
    curves, omitted_zero, all_indices = prepare_track_curves(
        track_keys, const_track_keys, prefer_simd=prefer_simd
    )

    if ensure_properties and all_indices:
        name_map = track_name_map(armature, action)
        ensure_track_properties(
            [track_property_name(index, name_map) for index in all_indices],
            armatures=[armature] if armature is not None else None,
        )

    if not curves:
        return {
            "curve_count": 0,
            "keypoint_count": 0,
            "omitted_zero_count": len(omitted_zero),
        }

    fcurves = get_action_fcurves(action, armature, create=True)
    if fcurves is None:
        _LOG.debug("import_anim_tracks: no fcurves collection available")
        return {
            "curve_count": 0,
            "keypoint_count": 0,
            "omitted_zero_count": len(omitted_zero),
        }

    action_group = add_track_action_group(action, armature)
    name_map = track_name_map(armature, action)
    existing = {curve.data_path: curve for curve in fcurves} if replace_existing else {}
    keypoint_count = 0

    fingerprints = {}
    for index, (frames, values, interpolation) in curves.items():
        data_path = track_property_path(track_property_name(index, name_map))
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
            interpolation="BEZIER" if interpolation == "BEZIER" else interpolation,
        )
        if interpolation == "BEZIER":
            _set_compressed_track_handles(curve, frames, values)
        fingerprints[str(index)] = scalar_curve_fingerprints(curve)
    store_json_snapshot(
        action,
        TRACK_CURVES_SNAPSHOT_KEY,
        {"version": 1, "preferSIMD": prefer_simd, "curves": fingerprints},
    )

    _LOG.debug(
        "%d Track Keys Imported into %d curves; %d zero curves omitted",
        keypoint_count,
        len(curves),
        len(omitted_zero),
    )
    return {
        "curve_count": len(curves),
        "keypoint_count": keypoint_count,
        "omitted_zero_count": len(omitted_zero),
    }


def write_track_matrix(
    armature,
    track_names,
    values,
    *,
    action_name: str = "Track Animation",
    start_frame: float = 1.0,
    threshold: float = 0.005,
    columns=None,
    new_action: bool = False,
    keep_keys_outside_range: bool = False,
) -> int:
    """Key a frame-by-track matrix as the curves of columns"""
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError("Track values must be a frame-by-track matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Track values must be finite")
    names = tuple(str(name) for name in track_names)
    if matrix.shape[1] != len(names):
        raise ValueError("Track matrix width does not match the track-name count")
    animation_data = armature.animation_data_create()
    action = animation_data.action
    created = False
    if action is None or new_action:
        if action is not None:
            action.use_fake_user = True
        action = new_tracked_datablock("actions", name=action_name)
        action.use_fake_user = True
        assign_action_with_slot(armature, action)
        created = True
    skin = armature_skin_extras(armature)
    if created or not skin.get("trackNames"):
        skin["trackNames"] = list(names)
    ensure_action_defaults(action)
    if created:
        store_action_source(action, source_name=action_export_name(action), skin=skin)
    fcurves = get_action_fcurves(action, armature, create=True)
    if fcurves is None:
        raise RuntimeError(f"Unable to access FCurves for action {action.name!r}")
    group = add_track_action_group(action, armature)
    frame_count = matrix.shape[0]
    all_frames = np.arange(frame_count, dtype=np.float64) + float(start_frame)
    frame_range = (float(all_frames[0]), float(all_frames[-1])) if frame_count else None
    existing = {curve.data_path: curve for curve in fcurves}
    keyed = 0
    for index in (
        range(len(names)) if columns is None else sorted({int(c) for c in columns})
    ):
        name = names[index]
        if not name:
            continue
        track_values = matrix[:, index]
        if not len(track_values):
            continue
        ensure_track_property(armature, name)
        data_path = track_property_path(name)
        selected = sparse_track_indices(track_values, threshold)
        previous = existing.get(data_path)
        if (
            previous is not None
            and keep_keys_outside_range
            and len(previous.keyframe_points)
        ):
            replace_fcurve_keyframes(
                previous,
                all_frames[selected],
                track_values[selected],
                interpolation="LINEAR",
                replace_range=frame_range,
            )
            keyed += 1
            continue
        if previous is not None:
            fcurves.remove(previous)
        curve = fcurves.new(data_path=data_path)
        if group is not None:
            curve.group = group
        bulk_set_keyframes(
            curve,
            all_frames[selected],
            track_values[selected],
            interpolation="LINEAR",
        )
        keyed += 1
    action[TRACKS_IMPORTED_KEY] = True
    return keyed


def _ensure_float_idproperty(owner, name: str, value: float) -> bool:
    value = float(value)
    current = owner.get(name)
    if isinstance(current, float):
        owner[name] = value
        return False
    if current is not None:
        try:
            del owner[name]
        except (KeyError, TypeError):
            pass
    owner[name] = value
    return True


def configure_float_idproperty(
    owner,
    name: str,
    value: float,
    *,
    default: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    soft_minimum: float | None = None,
    soft_maximum: float | None = None,
    description: str | None = None,
    subtype: str | None = None,
    overwrite_ui: bool = True,
) -> bool:
    created = _ensure_float_idproperty(owner, name, value)
    if not overwrite_ui and not created:
        return created
    kwargs = {}
    if default is not None:
        kwargs["default"] = float(default)
    if minimum is not None:
        kwargs["min"] = float(minimum)
    if maximum is not None:
        kwargs["max"] = float(maximum)
    if soft_minimum is not None:
        kwargs["soft_min"] = float(soft_minimum)
    if soft_maximum is not None:
        kwargs["soft_max"] = float(soft_maximum)
    if description is not None:
        kwargs["description"] = description
    if subtype is not None:
        kwargs["subtype"] = subtype
    if kwargs:
        owner.id_properties_ui(name).update(**kwargs)
    return created


def resolve_track_payload(action, extras=None):
    source = extras if isinstance(extras, dict) else action
    return source.get("trackKeys") or (), source.get("constTrackKeys") or ()


def track_payload_needs_resampling(
    action, *, source_track_keys, prefer_simd, duration_seconds, source_extras=None
):
    """Identify changes to the native SIMD time grid before preserving raw keys"""
    if not prefer_simd or not source_track_keys:
        return False
    snapshot = load_json_snapshot(action, TRACK_CURVES_SNAPSHOT_KEY)
    source_prefer_simd = snapshot.get("preferSIMD")
    source_duration = action.get("cp77_direct_anim_duration_seconds")
    if source_prefer_simd is None or source_duration is None:
        source = (
            source_extras
            if source_extras is not None
            else load_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY)
        )
        if source_prefer_simd is None:
            source_prefer_simd = bool(
                (source.get("optimizationHints") or {}).get("preferSIMD", False)
            )
        if source_duration is None:
            source_duration = track_payload_duration(source)
    return (
        not source_prefer_simd
        or np.float32(source_duration) != np.float32(duration_seconds)
        or not track_payload_fits_simd_grid(source_track_keys, duration_seconds)
    )
