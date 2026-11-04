from __future__ import annotations

import numpy as np

from ....bartmoss.geometry import unit_vectors

# The clavicle elevation and forward lean (degrees, in the chest's axes) the game's own clips hold for an upper arm's
# elevation and forward lean: least squares over the woman_average and man_average unarmed clips.
_ELEVATION = (0.275, 0.025, 21.1)
_FORWARD = (0.091, 0.156, -15.4)
# A performer's clavicle may stray this far (degrees) from their own rhythm with the arm and still be kept.
_MOST_DEVIATION = 25.0
_LEAST_FRAMES = 8


def chest_axes(up, side) -> np.ndarray:
    """Side, forward and up chest axes as matrix columns"""
    up = unit_vectors(up)
    side = unit_vectors(side - np.sum(side * up, axis=-1, keepdims=True) * up)
    return np.stack((side, np.cross(side, up), up), axis=-1)


def axis_angles(directions, axes) -> np.ndarray:
    """Elevation and forward lean in degrees of directions in chest axes"""
    local = np.einsum("...ji,...j->...i", axes, unit_vectors(directions))
    return np.degrees(np.arcsin(np.clip(local[..., (2, 1)], -1.0, 1.0)))


def rhythm(arm) -> np.ndarray:
    """The clavicle elevation and forward lean the game gives upper arm angles"""
    arm = np.asarray(arm, dtype=np.float64)
    return np.stack(
        [
            coefficients[0] * arm[..., 0]
            + coefficients[1] * arm[..., 1]
            + coefficients[2]
            for coefficients in (_ELEVATION, _FORWARD)
        ],
        axis=-1,
    )


def deviations(clavicle, arm) -> np.ndarray:
    """How far a performer's clavicle angles stray from their own rhythm with the upper arm"""
    clavicle = np.asarray(clavicle, dtype=np.float64)
    if len(clavicle) < _LEAST_FRAMES:
        return np.zeros_like(clavicle)
    design = np.column_stack((arm, np.ones(len(arm))))
    coefficients, *_ = np.linalg.lstsq(design, clavicle, rcond=None)
    return np.clip(clavicle - design @ coefficients, -_MOST_DEVIATION, _MOST_DEVIATION)


def clavicle_directions(angles, axes, outward: float) -> np.ndarray:
    """Unit directions with the given elevation and forward lean in chest axes"""
    sines = np.sin(np.radians(angles))
    lateral = np.sqrt(np.clip(1.0 - np.sum(sines * sines, axis=-1), 0.0, 1.0))
    local = np.stack((outward * lateral, sines[..., 1], sines[..., 0]), axis=-1)
    return np.einsum("...ij,...j->...i", axes, local)
