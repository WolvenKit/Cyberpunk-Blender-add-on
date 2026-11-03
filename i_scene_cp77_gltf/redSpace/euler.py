from __future__ import annotations

import math

import numpy as np

# Index into the (pitch, roll, yaw) tuple for each animTransformChannel rotation entry.
CHANNEL_INDEX = {"RotX": 0, "RotY": 1, "RotZ": 2}

_GIMBAL_EPSILON = 0.001


def euler_from_xyzw(rotation) -> tuple[float, float, float]:
    """(pitch, roll, yaw) in degrees"""
    x, y, z, w = (float(v) for v in rotation)
    unit = w * w + x * x + y * y + z * z
    if unit <= 1e-30:
        return 0.0, 0.0, 0.0
    test = w * x + y * z
    if test > (0.5 - _GIMBAL_EPSILON) * unit:
        return 90.0, 0.0, math.degrees(2.0 * math.atan2(y, w))
    if test < (-0.5 + _GIMBAL_EPSILON) * unit:
        return -90.0, 0.0, math.degrees(-2.0 * math.atan2(y, w))
    pitch = math.degrees(math.asin(2.0 * test / unit))
    roll = math.degrees(math.atan2(2.0 * (w * y - x * z), unit - 2.0 * (y * y + x * x)))
    yaw = math.degrees(math.atan2(2.0 * (w * z - x * y), unit - 2.0 * (z * z + x * x)))
    return pitch, roll, yaw


def xyzw_from_euler(pitch: float, roll: float, yaw: float) -> np.ndarray:
    """Quaternion (x, y, z, w) of Yaw(Z) * Pitch(X) * Roll(Y), angles in degrees"""
    hp, hr, hy = (math.radians(float(v)) * 0.5 for v in (pitch, roll, yaw))
    sp, cp = math.sin(hp), math.cos(hp)
    sr, cr = math.sin(hr), math.cos(hr)
    sy, cy = math.sin(hy), math.cos(hy)
    return np.array(
        (
            cy * sp * cr - sy * cp * sr,
            cy * cp * sr + sy * sp * cr,
            sy * cp * cr + cy * sp * sr,
            cy * cp * cr - sy * sp * sr,
        ),
        dtype=np.float64,
    )
