from collections import defaultdict

import numpy as np

from ....bartmoss.curve import ordered_key_samples
from ....core.log import get_logger, log_once
from ...model.clip.metadata import FPS

_LOG = get_logger(__name__)

TRACK_ACTION_GROUP_NAME = "Track Keys"


def entry_value(d, key, default=None):
    """d[key] for mappings and keyed sequences, falling back to an attribute of that name"""
    try:
        return d.get(key, default)
    except AttributeError as error:
        log_once(
            _LOG,
            "DEBUG",
            ("entry_value", type(error).__name__),
            "entry value: fell back after %s",
            error,
            exc_info=True,
        )
        try:
            return d[key]
        except (IndexError, KeyError, TypeError):
            return getattr(d, key, default)


def track_property_name(index, name_map):
    if name_map and index in name_map:
        return name_map[index]
    return f"T{index:02d}"


def aligned_track_curve(raw_keys):
    count = len(raw_keys)
    frames = np.fromiter(
        (float(entry_value(item, "time", 0.0)) * FPS for item in raw_keys),
        dtype=np.float64,
        count=count,
    )
    values = np.fromiter(
        (float(entry_value(item, "value", 0.0)) for item in raw_keys),
        dtype=np.float64,
        count=count,
    )
    return ordered_key_samples(frames, values, collapse_constant=True)


def _compressed_track_dt(a: float, b: float) -> float:
    return abs(float(b) - float(a)) ** 0.5


def compressed_track_segment_tangents(p0, p1, p2, p3):
    threshold = 1e-4
    dt0 = _compressed_track_dt(p0, p1)
    dt1 = _compressed_track_dt(p1, p2)
    dt2 = _compressed_track_dt(p2, p3)
    if dt1 < threshold:
        dt1 = 1.0
    if dt0 < threshold:
        dt0 = dt1
    if dt2 < threshold:
        dt2 = dt1

    t1 = (p1 - p0) / dt0 - (p2 - p0) / (dt0 + dt1) + (p2 - p1) / dt1
    t2 = (p2 - p1) / dt1 - (p3 - p1) / (dt1 + dt2) + (p3 - p2) / dt2
    return t1 * dt1, t2 * dt1


def prepare_track_curves(
    track_keys,
    const_track_keys,
    *,
    prefer_simd=False,
):
    animated = defaultdict(list)
    constants = defaultdict(list)
    all_indices = set()

    for entry in track_keys:
        index = entry_value(entry, "trackIndex")
        if index is None:
            continue
        index = int(index)
        animated[index].append(entry)
        all_indices.add(index)

    for entry in const_track_keys:
        index = entry_value(entry, "trackIndex")
        if index is None:
            continue
        index = int(index)
        constants[index].append(float(entry_value(entry, "value", 0.0)))
        all_indices.add(index)

    curves = {}
    omitted_zero = []
    for index in sorted(all_indices):
        raw_keys = animated.get(index)
        if raw_keys:
            frames, values = aligned_track_curve(raw_keys)
            curves[index] = (
                frames,
                values,
                "LINEAR" if prefer_simd else "BEZIER",
            )
            continue

        values = constants.get(index, ())
        if not values:
            continue
        minimum = min(values)
        maximum = max(values)
        value = minimum if minimum == maximum else values[-1]
        curves[index] = (
            np.asarray((0.0,), dtype=np.float64),
            np.asarray((value,), dtype=np.float64),
            "CONSTANT",
        )

    return curves, tuple(omitted_zero), tuple(sorted(all_indices))


def track_curve_matches_source(frames, values, source_dynamic, source_const):
    expected = aligned_track_curve(source_dynamic) if source_dynamic else None
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
        and np.array_equal(
            np.asarray(frames, dtype=np.float32),
            np.asarray(expected_frames, dtype=np.float32),
        )
        and np.array_equal(
            np.asarray(values, dtype=np.float32),
            np.asarray(expected_values, dtype=np.float32),
        )
    )


def track_payload_fits_simd_grid(track_keys, duration_seconds):
    """Check that raw keys fill each native frame exactly once per scalar track"""
    if not track_keys:
        return True
    duration = float(np.float32(duration_seconds))
    frame_count = max(2, int(np.ceil(duration * FPS))) if duration > 0 else 1
    indices = np.fromiter(
        (int(key["trackIndex"]) for key in track_keys),
        dtype=np.int64,
        count=len(track_keys),
    )
    _, counts = np.unique(indices, return_counts=True)
    if np.any(counts != frame_count):
        return False
    times = np.fromiter(
        (float(key["time"]) for key in track_keys),
        dtype=np.float64,
        count=len(track_keys),
    )
    if duration <= 0:
        return bool(np.all(times == 0))
    frames = np.rint(times * ((frame_count - 1) / duration)).astype(np.int64)
    if np.any(frames < 0) or np.any(frames >= frame_count):
        return False
    expected_times = frames * (duration / (frame_count - 1))
    precision = 2.0 * np.finfo(np.float32).eps * duration
    return bool(
        np.all(np.abs(times - expected_times) <= precision)
        and len(np.unique(indices * frame_count + frames)) == len(track_keys)
    )


FACIAL_RANGE_2 = frozenset({1, 2, 7, 8})
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


def facial_track_description(index, name, segments):
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


def sparse_track_indices(values, threshold: float = 0.005) -> np.ndarray:
    """Frames to key so LINEAR interpolation stays within 2 * threshold of every value"""
    track_values = np.asarray(values, dtype=np.float64)
    frame_count = len(track_values)
    if frame_count == 0:
        return np.empty(0, dtype=np.intp)
    threshold = float(threshold)
    first = float(track_values[0])
    if not np.any(np.abs(track_values - first) > threshold):
        return np.asarray(
            [0] if frame_count == 1 else [0, frame_count - 1], dtype=np.intp
        )
    selected = [0]
    previous_value = first
    last = frame_count - 1
    for frame_index, current in enumerate(track_values.tolist()[1:], start=1):
        if frame_index == last or abs(current - previous_value) > threshold:
            if frame_index - selected[-1] > 1:
                selected.append(frame_index - 1)
            selected.append(frame_index)
            previous_value = current
    return np.asarray(selected, dtype=np.intp)
