from __future__ import annotations

import bisect

from ...assetio.values import coerce_float
from ...bartmoss.celestial import DAY_HOURS, wrap_hour
from ...bartmoss.scalar import clamp_scalar


def is_curve(value) -> bool:
    return isinstance(value, dict) and "p" in value


def _lerp_value(low_value, high_value, blend):
    if isinstance(low_value, tuple) and isinstance(high_value, tuple):
        size = min(len(low_value), len(high_value))
        return tuple(
            low_value[index] + (high_value[index] - low_value[index]) * blend
            for index in range(size)
        )
    if isinstance(low_value, (int, float)) and isinstance(high_value, (int, float)):
        return low_value + (high_value - low_value) * blend
    return low_value


def evaluate_curve(curve, hour):
    """Curve value at a clock hour, wrapping across midnight"""
    if not (isinstance(curve, dict) and "p" in curve):
        return None
    return _evaluate_points(curve, hour)


def _evaluate_points(curve, hour):
    points = curve["p"]
    if not points:
        return None
    if len(points) == 1:
        return points[0][1]

    hour = wrap_hour(hour)
    times = getattr(curve, "times", None)
    if times is None:
        times = tuple(point for point, _ in points)
    index = bisect.bisect_right(times, hour)

    if index == 0 or index == len(times):
        low_time, low_value = points[-1]
        high_time, high_value = points[0]
        span = (high_time + DAY_HOURS) - low_time
        offset = (hour - low_time) % DAY_HOURS
    else:
        low_time, low_value = points[index - 1]
        high_time, high_value = points[index]
        span = high_time - low_time
        offset = hour - low_time

    if span <= 1e-9:
        return low_value

    interpolation = curve.get("i", "Linear")
    if interpolation == "Constant":
        return low_value

    blend = clamp_scalar(offset / span, 0.0, 1.0)
    if interpolation == "BezierCubic":
        # Exported BezierCubic elements carry no tangents: a smoothstep between neighbouring points.
        blend = blend * blend * (3.0 - 2.0 * blend)
    return _lerp_value(low_value, high_value, blend)


def curve_value(table, key, hour, fallback=None):
    """A table entry at a clock hour"""
    value = table.get(key)
    if isinstance(value, dict) and "p" in value:
        sampled = _evaluate_points(value, hour)
        return fallback if sampled is None else sampled
    return fallback if value is None else value


# The game's value of each environment curve the solver reads when the curve is missing, keyed by curve name.
CURVE_DEFAULTS = {
    "sunSize": 0.02,
    "moonSize": 0.017,
    "turbidity": 4.0,
    "lutTurbidity": 1.0,
    "sunMinZ": 0.0,
    "horizonMinZ": 0.05,
    "horizonFalloff": 0.05,
    "sunFalloff": 0.01,
    "moonFalloff": 0.01,
    "rayTracedSunShadowRange": 2000.0,
    "moonGlowIntensity": 0.05,
    "moonGlowFalloff": 10.0,
    "galaxyIntensity": 0.3,
    "starMapIntensity": 5.0,
    "starMapBrightScale": 10.5,
    "starMapDimScale": 25.0,
    "starMapConstelationsScale": 10.0,
    "starCornerLuminanceFix": 0.25,
    "artisticDarkeningStartPoint": 0.0,
    "artisticDarkeningEndPoint": 1.0,
    "artisticDarkeningExponent": 1.0,
}


def curve_scalar(table, key, hour, fallback=None):
    """A scalar entry"""
    if fallback is None:
        fallback = CURVE_DEFAULTS.get(key, 0.0)
    value = curve_value(table, key, hour, fallback)
    if isinstance(value, tuple):
        return float(value[3]) if len(value) > 3 else float(fallback)
    if isinstance(value, (int, float)):
        return float(value)
    return float(fallback)


def curve_number(table, key, hour, fallback=0.0):
    """Like curve_scalar but also accepts numeric text"""
    value = curve_value(table, key, hour, fallback)
    if isinstance(value, tuple):
        if len(value) >= 4:
            return float(value[3])
        return float(fallback)
    return coerce_float(value, fallback, unwrap=False, finite=False)


def curve_color(table, key, hour, fallback=(1.0, 1.0, 1.0, 0.0)):
    """An RGBA entry"""
    value = curve_value(table, key, hour, fallback)
    if isinstance(value, tuple):
        if len(value) >= 4:
            return tuple(float(value[index]) for index in range(4))
        if len(value) == 3:
            return tuple(float(value[index]) for index in range(3)) + (1.0,)
    if isinstance(value, (int, float)):
        scalar = float(value)
        return (1.0, 1.0, 1.0, scalar)
    return tuple(float(v) for v in fallback)


def curve_rgba(table, key, hour, fallback=(1.0, 1.0, 1.0, 0.0)):
    """A strict RGBA entry"""
    value = curve_value(table, key, hour, fallback)
    if isinstance(value, tuple) and len(value) >= 4:
        return tuple(float(value[index]) for index in range(4))
    return tuple(float(v) for v in fallback)


def curve_vector(table, key, hour, fallback=()):
    value = curve_value(table, key, hour, fallback)
    if isinstance(value, (tuple, list)):
        return tuple(float(v) for v in value)
    return tuple(float(v) for v in fallback)


def curve_bool(table, key, hour, fallback=False):
    return bool(curve_value(table, key, hour, fallback))


def curve_text(table, key, hour, fallback=""):
    value = curve_value(table, key, hour, fallback)
    return str(value or fallback)


def resource_text(table, key, fallback=""):
    """A resource-path entry"""
    value = table.get(key, fallback)
    if value in (None, 0, "0"):
        return ""
    return str(value)


def optional_curve_scalar(table, key, hour, fallback=None):
    """A scalar entry that may be absent"""
    value = table.get(key)
    if is_curve(value):
        sampled = evaluate_curve(value, hour)
        return fallback if sampled is None else float(sampled)
    if isinstance(value, (int, float)):
        return float(value)
    return fallback


def first_curve_value(value, fallback):
    """The first point's value of a curve (used for per-area constants stored as curves)"""
    if isinstance(value, dict) and value.get("p"):
        value = value["p"][0][1]
    return value or fallback
