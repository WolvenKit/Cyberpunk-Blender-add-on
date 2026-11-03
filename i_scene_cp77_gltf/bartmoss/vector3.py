from __future__ import annotations

import math

Vector3 = tuple[float, float, float]


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


def normalize3_with_length(value, epsilon: float = 1e-12) -> tuple[Vector3, float]:
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


def split_by_normal3(normal, vector) -> tuple[Vector3, Vector3]:
    """(in-plane part, along-normal part) of vector for a unit plane normal"""
    along = scale3(normal, dot3(vector, normal))
    return sub3(vector, along), along


def is_parallel3(a, b, tolerance: float = 0.001) -> bool:
    """True when unit vectors a and b are parallel or anti-parallel within tolerance"""
    return abs(abs(dot3(a, b)) - 1.0) <= tolerance
