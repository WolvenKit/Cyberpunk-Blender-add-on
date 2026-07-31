from __future__ import annotations

import numpy as np

from .quaternion import matrix_from_xyzw, slerp_xyzw, xyzw_from_matrices
from .scalar import lerp


def compose_matrix(translation, rotation_xyzw, scale) -> np.ndarray:
    matrix = matrix_from_xyzw(rotation_xyzw)
    matrix[:3, :3] *= np.asarray(scale, dtype=np.float64)[np.newaxis, :]
    matrix[:3, 3] = np.asarray(translation, dtype=np.float64)
    return matrix


def compose_matrices(translations, rotations_xyzw, scales, *, normalize_rotations_in_place=False) -> np.ndarray:
    translations = np.asarray(translations, dtype=np.float64)
    rotations = np.asarray(rotations_xyzw, dtype=np.float64)
    if not normalize_rotations_in_place or not rotations.flags.writeable:
        rotations = rotations.copy()
    scales = np.asarray(scales, dtype=np.float64)
    lengths = np.linalg.norm(rotations, axis=-1)
    invalid = lengths <= 1e-15
    rotations[invalid] = (0.0, 0.0, 0.0, 1.0)
    lengths = np.linalg.norm(rotations, axis=-1)
    rotations /= lengths[..., None]
    x, y, z, w = np.moveaxis(rotations, -1, 0)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    shape = translations.shape[:-1] + (4, 4)
    matrices = np.zeros(shape, dtype=np.float64)
    matrices[..., 0, 0] = 1.0 - 2.0 * (yy + zz)
    matrices[..., 0, 1] = 2.0 * (xy - wz)
    matrices[..., 0, 2] = 2.0 * (xz + wy)
    matrices[..., 1, 0] = 2.0 * (xy + wz)
    matrices[..., 1, 1] = 1.0 - 2.0 * (xx + zz)
    matrices[..., 1, 2] = 2.0 * (yz - wx)
    matrices[..., 2, 0] = 2.0 * (xz - wy)
    matrices[..., 2, 1] = 2.0 * (yz + wx)
    matrices[..., 2, 2] = 1.0 - 2.0 * (xx + yy)
    matrices[..., :3, :3] *= scales[..., None, :]
    matrices[..., :3, 3] = translations
    matrices[..., 3, 3] = 1.0
    return matrices


def decompose_matrices(matrices):
    matrices = np.asarray(matrices, dtype=np.float64)
    translations = matrices[..., :3, 3].copy()
    axes = matrices[..., :3, :3]
    scales = np.linalg.norm(axes, axis=-2)
    rotations = axes / np.maximum(scales[..., None, :], 1e-15)
    flat_rotations = rotations.reshape(-1, 3, 3)
    flat_scales = scales.reshape(-1, 3)
    mirrored = np.linalg.det(flat_rotations) < 0.0
    if np.any(mirrored):
        flat_scales[mirrored, 0] *= -1.0
        flat_rotations[mirrored, :, 0] *= -1.0
    quaternions = xyzw_from_matrices(flat_rotations).reshape(matrices.shape[:-2] + (4,))
    return translations, quaternions, scales


def interpolate_matrices(previous, current, weight) -> np.ndarray:
    previous_translation, previous_rotation, previous_scale = decompose_matrices(previous)
    current_translation, current_rotation, current_scale = decompose_matrices(current)
    translation = lerp(previous_translation, current_translation, weight)
    rotation = slerp_xyzw(previous_rotation, current_rotation, weight)
    scale = lerp(previous_scale, current_scale, weight)
    return compose_matrices(translation, rotation, scale)
