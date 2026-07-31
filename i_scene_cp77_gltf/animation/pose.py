from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..bartmoss.hierarchy import local_matrices_to_model, model_matrices_to_local
from ..bartmoss.quaternion import identity_xyzw, multiply_xyzw, nlerp_xyzw


@dataclass
class PoseBuffer:
    translations: np.ndarray
    rotations_xyzw: np.ndarray
    scales: np.ndarray

    def copy(self):
        return PoseBuffer(
            self.translations.copy(),
            self.rotations_xyzw.copy(),
            self.scales.copy(),
        )


def identity_pose(count: int, dtype=np.float32) -> PoseBuffer:
    return PoseBuffer(
        np.zeros((int(count), 3), dtype=dtype),
        identity_xyzw(count, dtype=dtype),
        np.ones((int(count), 3), dtype=dtype),
    )


def apply_additive_pose(base: PoseBuffer, additive: PoseBuffer, weight=1.0) -> PoseBuffer:
    weight_array = np.asarray(weight, dtype=base.translations.dtype)
    while weight_array.ndim < base.translations.ndim:
        weight_array = weight_array[..., None]
    translations = base.translations + additive.translations * weight_array
    combined = multiply_xyzw(base.rotations_xyzw, additive.rotations_xyzw)
    rotations = nlerp_xyzw(base.rotations_xyzw, combined, np.squeeze(weight_array, axis=-1))
    scales = base.scales + (additive.scales - 1.0) * weight_array
    return PoseBuffer(translations, rotations, scales)


def local_to_model_matrices(local_matrices, parent_indices, order=None):
    return local_matrices_to_model(local_matrices, parent_indices, order)


def model_to_local_matrices(model_matrices, parent_indices, order=None):
    return model_matrices_to_local(model_matrices, parent_indices, order)
