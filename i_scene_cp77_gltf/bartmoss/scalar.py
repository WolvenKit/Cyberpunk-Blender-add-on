from __future__ import annotations

import numpy as np


def clamp(value, minimum, maximum):
    return np.clip(value, minimum, maximum)


def clamp_scalar(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def lerp(start, end, weight):
    return start + weight * (end - start)


def smoothstep(edge0, edge1, value):
    weight = clamp((value - edge0) / (edge1 - edge0 + 1e-10), 0.0, 1.0)
    return weight * weight * (3.0 - 2.0 * weight)


def limit_weight(slider, minimum, midpoint, maximum):
    slider = np.asarray(slider)
    minimum = np.asarray(minimum)
    midpoint = np.asarray(midpoint)
    maximum = np.asarray(maximum)
    below = minimum + slider * (midpoint - minimum)
    below = np.clip(below, np.minimum(minimum, midpoint), np.maximum(minimum, midpoint))
    above = midpoint + (slider - 1.0) * (maximum - midpoint)
    above = np.clip(above, np.minimum(midpoint, maximum), np.maximum(midpoint, maximum))
    return np.where(slider < 1.0, below, np.where(slider > 1.0, above, midpoint))


def limit_weight_scalar(slider: float, minimum: float, midpoint: float, maximum: float) -> float:
    if slider <= 1.0:
        value = minimum + slider * (midpoint - minimum)
        lower, upper = sorted((minimum, midpoint))
    else:
        value = midpoint + (slider - 1.0) * (maximum - midpoint)
        lower, upper = sorted((midpoint, maximum))
    return max(lower, min(upper, value))


def wrinkle_weight(track_weight):
    inverse = 1.0 - track_weight
    return clamp(1.0 - inverse * inverse, 0.0, 1.0)


def sin_squared_ease(weight):
    return np.sin(0.5 * np.pi * clamp(weight, 0.0, 1.0)) ** 2
