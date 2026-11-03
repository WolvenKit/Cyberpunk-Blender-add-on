from __future__ import annotations

import math

import numpy as np


def translation_matrix_2d(x, y):
    return np.array(
        ((1.0, 0.0, float(x)), (0.0, 1.0, float(y)), (0.0, 0.0, 1.0)),
        dtype=np.float64,
    )


def scale_matrix_2d(x, y):
    return np.array(
        ((float(x), 0.0, 0.0), (0.0, float(y), 0.0), (0.0, 0.0, 1.0)),
        dtype=np.float64,
    )


def rotation_matrix_2d(degrees):
    angle = math.radians(float(degrees))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        ((cosine, -sine, 0.0), (sine, cosine, 0.0), (0.0, 0.0, 1.0)),
        dtype=np.float64,
    )


def shear_matrix_2d(x, y):
    return np.array(
        ((1.0, float(x), 0.0), (float(y), 1.0, 0.0), (0.0, 0.0, 1.0)),
        dtype=np.float64,
    )
