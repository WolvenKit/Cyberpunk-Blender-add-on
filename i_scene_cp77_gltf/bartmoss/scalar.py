from __future__ import annotations

import math

import numpy as np


def clamp_scalar(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def clamp01(value: float) -> float:
    return clamp_scalar(value, 0.0, 1.0)


def all_finite(values) -> bool:
    return all(math.isfinite(float(value)) for value in values)


REC709_LUMA_WEIGHTS = (0.2126, 0.7152, 0.0722)
REC601_LUMA_WEIGHTS = (0.299, 0.587, 0.114)
# The sRGB transfer function: the linear segment below its threshold, the power curve above it.
SRGB_DECODE_THRESHOLD = 0.04045
SRGB_ENCODE_THRESHOLD = 0.0031308
SRGB_LINEAR_SCALE = 12.92
SRGB_SCALE = 1.055
SRGB_OFFSET = 0.055
SRGB_GAMMA = 2.4


def luminance(rgb) -> float:
    """Rec. 709 relative luminance of linear RGB"""
    return sum(float(rgb[index]) * REC709_LUMA_WEIGHTS[index] for index in range(3))


def srgb_channel_to_linear(value):
    """An sRGB-encoded channel value in 0..1 as linear"""
    if np.isscalar(value):
        value = clamp01(value)
        if value <= SRGB_DECODE_THRESHOLD:
            return value / SRGB_LINEAR_SCALE
        return ((value + SRGB_OFFSET) / SRGB_SCALE) ** SRGB_GAMMA
    array = np.clip(np.asarray(value, dtype=np.float32), 0.0, 1.0)
    return np.where(
        array <= SRGB_DECODE_THRESHOLD,
        array / SRGB_LINEAR_SCALE,
        ((array + SRGB_OFFSET) / SRGB_SCALE) ** SRGB_GAMMA,
    ).astype(np.float32)


def linear_channel_to_srgb(value):
    """A linear channel value in 0..1 sRGB-encoded"""
    if np.isscalar(value):
        value = clamp01(value)
        if value <= SRGB_ENCODE_THRESHOLD:
            return value * SRGB_LINEAR_SCALE
        return SRGB_SCALE * value ** (1.0 / SRGB_GAMMA) - SRGB_OFFSET
    array = np.clip(np.asarray(value, dtype=np.float32), 0.0, 1.0)
    return np.where(
        array <= SRGB_ENCODE_THRESHOLD,
        array * SRGB_LINEAR_SCALE,
        SRGB_SCALE * array ** (1.0 / SRGB_GAMMA) - SRGB_OFFSET,
    ).astype(np.float32)


def lerp(start, end, weight):
    if np.isscalar(start) and np.isscalar(end):
        return start + weight * (end - start)
    start_array = np.asarray(start, dtype=np.float64)
    end_array = np.asarray(end, dtype=np.float64)
    return start_array + float(weight) * (end_array - start_array)


def lerp_three(values, bias):
    values = tuple(values)
    if len(values) != 3:
        raise ValueError("lerp_three requires exactly three values")
    weight = clamp_scalar(bias, 0.0, 2.0)
    if weight <= 1.0:
        return lerp(values[0], values[1], weight)
    return lerp(values[1], values[2], weight - 1.0)


def linear_step_scalar(edge0: float, edge1: float, value: float) -> float:
    """Position of value between the edges, clamped to [0, 1]"""
    if edge1 == edge0:
        return 1.0 if value >= edge1 else 0.0
    return clamp_scalar((value - edge0) / (edge1 - edge0), 0.0, 1.0)


def smoothstep_scalar(edge0: float, edge1: float, value: float) -> float:
    weight = linear_step_scalar(edge0, edge1, value)
    return weight * weight * (3.0 - 2.0 * weight)


def smoothstep(edge0, edge1, value):
    weight = np.clip((value - edge0) / (edge1 - edge0 + 1e-10), 0.0, 1.0)
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


def limit_weight_scalar(
    slider: float, minimum: float, midpoint: float, maximum: float
) -> float:
    if slider <= 1.0:
        value = minimum + slider * (midpoint - minimum)
        lower, upper = sorted((minimum, midpoint))
    else:
        value = midpoint + (slider - 1.0) * (maximum - midpoint)
        lower, upper = sorted((midpoint, maximum))
    return max(lower, min(upper, value))


def wrinkle_weight(track_weight):
    inverse = 1.0 - track_weight
    return np.clip(1.0 - inverse * inverse, 0.0, 1.0)


def sin_squared_ease(weight):
    return np.sin(0.5 * np.pi * np.clip(weight, 0.0, 1.0)) ** 2
