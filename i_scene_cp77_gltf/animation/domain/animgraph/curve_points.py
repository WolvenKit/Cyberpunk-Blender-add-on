from __future__ import annotations

from collections.abc import Mapping, Sequence

from ....bartmoss.scalar import smoothstep


def inserted_curve_point(
    points: Sequence[tuple[float, float]], active_index: int
) -> tuple[float, float]:
    """The point added after the active one"""
    count = len(points)
    if count == 0:
        return 0.0, 0.0
    index = max(0, min(active_index, count - 1))
    if index < count - 1:
        (ax, ay), (bx, by) = points[index], points[index + 1]
        return (ax + bx) * 0.5, (ay + by) * 0.5
    ax, ay = points[index]
    step = 0.1
    if count >= 2:
        previous_x = points[index - 1][0]
        step = max(0.01, min(1.0, abs(ax - previous_x)))
    return ax + step, ay


def _cubic_bezier_component(
    p0: float, p1: float, p2: float, p3: float, u: float
) -> float:
    inv = 1.0 - float(u)
    return (
        inv * inv * inv * float(p0)
        + 3.0 * inv * inv * float(u) * float(p1)
        + 3.0 * inv * float(u) * float(u) * float(p2)
        + float(u) * float(u) * float(u) * float(p3)
    )


def _sample_cubic_bezier(
    points: Sequence[tuple[float, float]], t: float
) -> float | None:
    if len(points) < 4 or (len(points) - 1) % 3 != 0:
        return None
    for start in range(0, len(points) - 1, 3):
        segment = points[start : start + 4]
        if len(segment) != 4:
            continue
        if t > segment[3][0] and start + 4 < len(points):
            continue
        x0, y0 = segment[0]
        x1, y1 = segment[1]
        x2, y2 = segment[2]
        x3, y3 = segment[3]
        if x3 <= x0:
            return y0
        low = 0.0
        high = 1.0
        for _ in range(32):
            u = (low + high) * 0.5
            if _cubic_bezier_component(x0, x1, x2, x3, u) < t:
                low = u
            else:
                high = u
        u = (low + high) * 0.5
        return _cubic_bezier_component(y0, y1, y2, y3, u)
    return points[-1][1]


def sample_curve(
    curve: Mapping | None, time_seconds: float, reference_value: float = 0.0
) -> float:
    if not isinstance(curve, Mapping):
        return float(reference_value)
    elements = curve.get("Elements") or curve.get("elements") or ()
    points = []
    for item in elements:
        if not isinstance(item, Mapping):
            continue
        try:
            points.append(
                (
                    float(item.get("Point", item.get("point", 0.0)) or 0.0),
                    float(item.get("Value", item.get("value", 0.0)) or 0.0),
                )
            )
        except (TypeError, ValueError):
            continue
    if not points:
        return float(reference_value)
    points.sort(key=lambda pair: pair[0])
    t = float(time_seconds)
    if t <= points[0][0]:
        return points[0][1]
    if t >= points[-1][0]:
        return points[-1][1]
    interpolation = str(
        curve.get("InterpolationType", curve.get("interpolationType", "Linear"))
        or "Linear"
    ).lower()
    if interpolation == "beziercubic":
        sampled = _sample_cubic_bezier(points, t)
        if sampled is not None:
            return float(sampled)
    for index in range(1, len(points)):
        right_t, right_v = points[index]
        if t > right_t:
            continue
        left_t, left_v = points[index - 1]
        if interpolation == "constant" or right_t <= left_t:
            return left_v
        alpha = (t - left_t) / (right_t - left_t)
        if interpolation == "beziercubic":
            alpha = float(smoothstep(0.0, 1.0, alpha))
        return left_v + (right_v - left_v) * alpha
    return points[-1][1]
