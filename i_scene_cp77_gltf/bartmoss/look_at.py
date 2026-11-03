from __future__ import annotations

import math

from .quaternion import rotate_vector_scalar_xyzw


def direction_angles(vector):
    x, y, z = vector
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(
        math.atan2(-x, y)
    )


def direction_delta(source, target):
    ap, ay = direction_angles(source)
    bp, by = direction_angles(target)
    ay = 180.0 if ay <= -180.0 else ay
    by = 180.0 if by <= -180.0 else by
    return bp - ap, by - ay


def rotate_direction(vector, pitch, yaw):
    p, y = math.radians(pitch) * 0.5, math.radians(yaw) * 0.5
    x, qy, z, w = (
        math.cos(y) * math.sin(p),
        math.sin(y) * math.sin(p),
        math.sin(y) * math.cos(p),
        math.cos(y) * math.cos(p),
    )
    heading = math.radians(direction_angles(vector)[1])
    c, s = math.cos(heading), math.sin(heading)
    return rotate_vector_scalar_xyzw((c * x - s * qy, s * x + c * qy, z, w), vector)


def interpolate_direction(source, target, weight):
    if weight == 0.0:
        return source
    if weight == 1.0:
        return target
    pitch, yaw = direction_delta(source, target)
    return rotate_direction(source, pitch * weight, yaw * weight)


def unit_direction(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return (
        tuple(value / length for value in vector) if length > 1e-12 else (0.0, 1.0, 0.0)
    )
