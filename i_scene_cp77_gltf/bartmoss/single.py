from __future__ import annotations

import math
import struct

_PACK1 = struct.Struct("f")
_PACK3 = struct.Struct("3f")
_PACK4 = struct.Struct("4f")
_PACK6 = struct.Struct("6f")
_PACK12 = struct.Struct("12f")
_FLOAT32_MAX = 3.4028234663852886e38


def _overflow(value: float) -> float:
    if value != value or abs(value) <= _FLOAT32_MAX:
        return value
    return math.copysign(math.inf, value)


def f32(value: float) -> float:
    """Round to the nearest float32 (as Python float)"""
    try:
        return _PACK1.unpack(_PACK1.pack(value))[0]
    except OverflowError:
        return _overflow(value)


def _rounded(packer, *values):
    """Each value rounded to float32, in one pack (rounding is per value, so batching is exact)"""
    try:
        return packer.unpack(packer.pack(*values))
    except OverflowError:
        return tuple(f32(value) for value in values)


def vec3(x: float, y: float, z: float):
    """A float32 vector from three values (as mathutils.Vector stores them)"""
    return _rounded(_PACK3, x, y, z)


def quat(w: float, x: float, y: float, z: float):
    return _rounded(_PACK4, w, x, y, z)


def add(a, b):
    return vec3(a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return vec3(a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, factor: float):
    """Vector times scalar, with the scalar first stored as float32"""
    factor = f32(factor)
    return vec3(a[0] * factor, a[1] * factor, a[2] * factor)


def negate(a):
    return (-a[0], -a[1], -a[2])


def dot(a, b) -> float:
    """Vector.dot"""
    z, y, x = _rounded(_PACK3, a[2] * b[2], a[1] * b[1], a[0] * b[0])
    return ((0.0 + z) + y) + x


def length_squared(a) -> float:
    """Vector.length_squared (same accumulation as dot)"""
    return dot(a, a)


def length(a) -> float:
    """Vector.length"""
    return math.sqrt(dot(a, a))


def normalized(a):
    """Vector.normalized()"""
    total = 0.0
    total += a[2] * a[2]
    total += a[1] * a[1]
    total += a[0] * a[0]
    if total > 1.0e-35:
        inverse = f32(1.0 / f32(math.sqrt(total)))
        return vec3(a[0] * inverse, a[1] * inverse, a[2] * inverse)
    return (0.0, 0.0, 0.0)


def cross(a, b):
    """Vector.cross (float32 throughout)"""
    p = _rounded(
        _PACK6,
        a[1] * b[2],
        a[2] * b[1],
        a[2] * b[0],
        a[0] * b[2],
        a[0] * b[1],
        a[1] * b[0],
    )
    return vec3(p[0] - p[1], p[2] - p[3], p[4] - p[5])


def _dot3_float32(a, b) -> float:
    x, y, z = _rounded(_PACK3, a[0] * b[0], a[1] * b[1], a[2] * b[2])
    return f32(f32(x + y) + z)


def normalized_float32(a):
    """Fixed-size float32 normalization"""
    d = _dot3_float32(a, a)
    if d > 1.0e-35:
        inverse = f32(1.0 / f32(math.sqrt(d)))
        return vec3(a[0] * inverse, a[1] * inverse, a[2] * inverse)
    return None


def axis_angle_quat(axis, half_sine: float, half_cosine: float):
    """Quaternion(axis, angle) given the float32 sin/cos of the half angle (identity for a zero axis)"""
    unit = normalized_float32(axis)
    if unit is None:
        return (1.0, 0.0, 0.0, 0.0)
    return (
        half_cosine,
        f32(unit[0] * half_sine),
        f32(unit[1] * half_sine),
        f32(unit[2] * half_sine),
    )


def rotate(q, v):
    """Quaternion @ Vector in float32, in Blender's operation order"""
    w, x, y, z = q
    r0, r1, r2 = v
    a = _rounded(
        _PACK12,
        -x * r0,
        y * r1,
        z * r2,
        w * r0,
        y * r2,
        z * r1,
        w * r1,
        z * r0,
        x * r2,
        w * r2,
        x * r1,
        y * r0,
    )
    b = _rounded(_PACK4, a[0] - a[1], a[3] + a[4], a[6] + a[7], a[9] + a[10])
    t0, r0, r1, r2 = _rounded(
        _PACK4, b[0] - a[2], b[1] - a[5], b[2] - a[8], b[3] - a[11]
    )
    c = _rounded(
        _PACK12,
        t0 * -x,
        r0 * w,
        r1 * z,
        r2 * y,
        t0 * -y,
        r1 * w,
        r2 * x,
        r0 * z,
        t0 * -z,
        r2 * w,
        r0 * y,
        r1 * x,
    )
    d = _rounded(_PACK3, c[0] + c[1], c[4] + c[5], c[8] + c[9])
    e = _rounded(_PACK3, d[0] - c[2], d[1] - c[6], d[2] - c[10])
    return _rounded(_PACK3, e[0] + c[3], e[1] + c[7], e[2] + c[11])


def conjugate(q):
    return (q[0], -q[1], -q[2], -q[3])
