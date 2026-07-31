from __future__ import annotations

import numpy as np


def closest_point_on_segment(points, start, end, epsilon: float = 1e-6):
    segment = end - start
    relative = points - start
    length_squared = np.sum(segment * segment, axis=-1)
    safe = np.where(length_squared < epsilon, 1.0, length_squared)
    factor = np.clip(np.sum(relative * segment, axis=-1) / safe, 0.0, 1.0)
    return start + factor[..., None] * segment


def closest_point_on_segment_single(point, start, end, epsilon: float = 1e-6):
    segment = end - start
    length_squared = np.dot(segment, segment)
    if length_squared < epsilon:
        return start.copy()
    factor = max(0.0, min(1.0, np.dot(point - start, segment) / length_squared))
    return start + segment * factor


def orthogonal_vector(vector):
    value = np.asarray(vector)
    x, y, z = value
    if 0.81 * np.dot(value, value) - x * x < 0.0:
        return np.asarray((-z, 0.0, x), dtype=value.dtype)
    return np.asarray((0.0, z, -y), dtype=value.dtype)
