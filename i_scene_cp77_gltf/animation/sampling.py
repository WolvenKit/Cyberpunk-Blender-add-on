import math

import numpy as np


def curve_key_frames(curve) -> np.ndarray:
    points = curve.keyframe_points
    if not len(points):
        return np.empty(0, dtype=np.float64)
    coordinates = np.empty(len(points) * 2, dtype=np.float64)
    points.foreach_get("co", coordinates)
    return coordinates[0::2]


def curve_interpolations(curve) -> set[str]:
    return {str(point.interpolation) for point in curve.keyframe_points}


def property_sampling(curves, action, *, force_dense=False):
    if not curves:
        return None
    interpolations = set()
    frame_arrays = []
    for curve in curves:
        interpolations.update(curve_interpolations(curve))
        frames = curve_key_frames(curve)
        if len(frames):
            frame_arrays.append(frames)
    if not frame_arrays:
        return None
    exact_mode = interpolations.issubset({"CONSTANT"}) or interpolations.issubset({"LINEAR"})
    if force_dense or not exact_mode:
        start, end = (float(value) for value in action.frame_range)
        first = int(math.floor(start + 1e-7))
        last = int(math.ceil(end - 1e-7))
        frames = np.arange(first, max(first, last) + 1, dtype=np.float64)
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
        if curve is None:
            continue
        curves.append(curve)
        result[:, component] = np.fromiter(
            (float(curve.evaluate(float(frame))) for frame in frames),
            dtype=np.float64,
            count=len(frames),
        )
    return result, curves
