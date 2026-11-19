from __future__ import annotations

import math
from statistics import median

Vector3 = tuple[float, float, float]

# Recentring offsets snap to whole metres so game coordinates stay easy to read back by hand.
OFFSET_GRID = 1.0
# Content closer than this to the origin gains nothing from recentring.
RECENTRE_MIN_DISTANCE = 100.0


def add3(a, b) -> Vector3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub3(a, b) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale3(a, s: float) -> Vector3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot3(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a, b) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length3(a) -> float:
    return math.sqrt(dot3(a, a))


def normalized3(a, epsilon: float = 1e-12) -> Vector3:
    """Unit vector along a"""
    length = length3(a)
    return scale3(a, 1.0 / length) if length > epsilon else (0.0, 0.0, 0.0)


def normalize3_with_length(
    value, epsilon: float = 1e-12
) -> tuple[Vector3, float]:
    """(unit vector, length)"""
    x, y, z = value
    length = math.sqrt(x * x + y * y + z * z)
    if length <= epsilon:
        return (float(x), float(y), float(z)), length
    inv = 1.0 / length
    return (x * inv, y * inv, z * inv), length


def lerp3(a, b, weight: float) -> Vector3:
    return (
        a[0] + (b[0] - a[0]) * weight,
        a[1] + (b[1] - a[1]) * weight,
        a[2] + (b[2] - a[2]) * weight,
    )


def midpoint3(a, b) -> Vector3:
    return (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), 0.5 * (a[2] + b[2]))


def snapped_offset(points) -> Vector3 | None:
    """The whole-grid offset that brings the middle of points to the origin, or None when they are already close"""
    points = tuple(points)
    if not points:
        return None
    # The per-axis median, not the bounds centre: stray objects left at the origin (or far away)
    # must not drag the offset off the content people work on.
    centre = tuple(median(point[axis] for point in points) for axis in range(3))
    if length3(centre) < RECENTRE_MIN_DISTANCE:
        return None
    return tuple(-round(value / OFFSET_GRID) * OFFSET_GRID for value in centre)


def split_by_normal3(normal, vector) -> tuple[Vector3, Vector3]:
    """(in-plane part, along-normal part) of vector for a unit plane normal"""
    along = scale3(normal, dot3(vector, normal))
    return sub3(vector, along), along


def is_parallel3(a, b, tolerance: float = 0.001) -> bool:
    """True when unit vectors a and b are parallel or anti-parallel within tolerance"""
    return abs(abs(dot3(a, b)) - 1.0) <= tolerance
