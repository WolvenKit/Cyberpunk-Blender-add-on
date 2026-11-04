from __future__ import annotations

import math

import numpy as np

from .quaternion import normalize_sequence_xyzw


def simplify_piecewise_linear(points, limit):
    values = tuple((float(x), float(y)) for x, y in points)
    if limit < 2:
        raise ValueError("Curve point limit must be at least two")
    if len(values) <= limit:
        return values
    if any(values[index][0] <= values[index - 1][0] for index in range(1, len(values))):
        raise ValueError("Curve points must be strictly increasing")

    selected = {0, len(values) - 1}
    while len(selected) < limit:
        ordered = sorted(selected)
        best_index = None
        best_error = -1.0
        for left, right in zip(ordered, ordered[1:]):
            x0, y0 = values[left]
            x1, y1 = values[right]
            span = x1 - x0
            for index in range(left + 1, right):
                x, y = values[index]
                expected = y0 + (y1 - y0) * ((x - x0) / span)
                error = abs(y - expected)
                if error > best_error:
                    best_error = error
                    best_index = index
        if best_index is None:
            break
        selected.add(best_index)
    return tuple(values[index] for index in sorted(selected))


def piecewise_linear_value(points, x):
    """Value of the piecewise-linear curve through (x, y) points sorted by x, held constant past either end"""
    x = float(x)
    if x <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            span = x1 - x0
            return float(y1) if span <= 0.0 else y0 + (y1 - y0) * ((x - x0) / span)
    return float(points[-1][1])


def centered_convolve(values, kernel):
    """Return centered convolution with exactly the input sample count"""
    values = np.asarray(values)
    kernel = np.asarray(kernel)
    if not len(values):
        return values.copy()
    full = np.convolve(values, kernel, mode="full")
    start = (len(kernel) - 1) // 2
    return full[start : start + len(values)]


def sample_frame_grid(start, end, key_frames=()) -> np.ndarray:
    start, end = float(start), float(end)
    if not math.isfinite(start) or not math.isfinite(end) or end < start:
        raise ValueError("Animation sampling requires finite, ordered frame bounds.")
    keys = np.asarray(key_frames, dtype=np.float64).reshape(-1)
    if not np.all(np.isfinite(keys)):
        raise ValueError("Animation keyframes must be finite.")
    interior = np.arange(math.floor(start) + 1, math.ceil(end), dtype=np.float64)
    keys = keys[(keys > start) & (keys < end)]
    anchors = np.unique(np.concatenate(([start, end], keys)))
    right = np.searchsorted(anchors, interior)
    distance = np.minimum(
        np.abs(interior - anchors[np.clip(right, 0, len(anchors) - 1)]),
        np.abs(interior - anchors[np.clip(right - 1, 0, len(anchors) - 1)]),
    )
    interior = interior[distance > 1e-5]
    return np.unique(np.concatenate((anchors, interior)))


def ordered_key_samples(times, values, *, collapse_constant=False):
    """Order scalar samples and retain the final authored value at duplicate times"""
    times = np.asarray(times, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if times.ndim != 1 or values.shape != times.shape:
        raise ValueError(
            "Scalar samples require matching one-dimensional times and values."
        )
    if len(times) > 1:
        differences = np.diff(times)
        if np.any(differences < 0):
            order = np.argsort(times, kind="stable")
            times, values = times[order], values[order]
            differences = np.diff(times)
        if np.any(differences == 0):
            keep = np.concatenate((differences != 0, [True]))
            times, values = times[keep], values[keep]
        if collapse_constant and np.all(values == values[0]):
            times, values = times[:1], values[:1]
    return times, values


def sample_linear(times, values, sample_times):
    if len(times) == 0:
        raise ValueError("Animation sampler has no input keys.")
    if len(times) != len(values):
        raise ValueError("Animation sampler input/output counts differ.")
    if len(times) == 1:
        return np.repeat(values[:1], len(sample_times), axis=0)
    right = np.searchsorted(times, sample_times, side="right")
    right = np.clip(right, 1, len(times) - 1)
    left = right - 1
    denominator = times[right] - times[left]
    factor = np.divide(
        sample_times - times[left],
        denominator,
        out=np.zeros_like(sample_times),
        where=np.abs(denominator) > 1e-15,
    )
    factor = np.clip(factor, 0.0, 1.0)
    before = sample_times <= times[0]
    after = sample_times >= times[-1]
    result = values[left] + (values[right] - values[left]) * factor[:, None]
    result[before] = values[0]
    result[after] = values[-1]
    return result


def sample_step(times, values, sample_times):
    if len(times) == 0 or len(times) != len(values):
        raise ValueError("Invalid STEP animation sampler.")
    indices = np.searchsorted(times, sample_times, side="right") - 1
    indices = np.clip(indices, 0, len(times) - 1)
    return values[indices]


def sample_quaternions_xyzw(times, values, sample_times, interpolation="LINEAR"):
    values = normalize_sequence_xyzw(values)
    if interpolation == "STEP" or len(times) == 1:
        return sample_step(times, values, sample_times)

    right = np.searchsorted(times, sample_times, side="right")
    right = np.clip(right, 1, len(times) - 1)
    left = right - 1
    denominator = times[right] - times[left]
    factor = np.divide(
        sample_times - times[left],
        denominator,
        out=np.zeros_like(sample_times),
        where=np.abs(denominator) > 1e-15,
    )
    factor = np.clip(factor, 0.0, 1.0)
    q0 = values[left]
    q1 = values[right]
    dot = np.sum(q0 * q1, axis=1)
    q1 = np.where((dot < 0.0)[:, None], -q1, q1)
    dot = np.clip(np.abs(dot), 0.0, 1.0)
    theta = np.arccos(dot)
    sin_theta = np.sin(theta)
    linear = sin_theta < 1e-7
    w0 = np.empty_like(factor)
    w1 = np.empty_like(factor)
    w0[linear] = 1.0 - factor[linear]
    w1[linear] = factor[linear]
    nonlinear = ~linear
    w0[nonlinear] = (
        np.sin((1.0 - factor[nonlinear]) * theta[nonlinear]) / sin_theta[nonlinear]
    )
    w1[nonlinear] = np.sin(factor[nonlinear] * theta[nonlinear]) / sin_theta[nonlinear]
    result = q0 * w0[:, None] + q1 * w1[:, None]
    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    result[sample_times <= times[0]] = values[0]
    result[sample_times >= times[-1]] = values[-1]
    return result
