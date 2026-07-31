from __future__ import annotations

import numpy as np

from .contracts import (
    BLENDER_BONE_RIGHT_TO_GLTF,
    GLTF_TO_BLENDER_BONE_RIGHT,
    GLTF_TO_RED,
    RED_LOCAL_TO_BLENDER_BONE_CURRENT,
    RED_TO_GLTF,
    BLENDER_BONE_LOCAL_TO_RED_CURRENT,
)


def gltf_relative_to_blender(relative_gltf, is_root: bool):
    relative_gltf = np.asarray(relative_gltf, dtype=np.float64)
    if is_root:
        return np.matmul(np.matmul(GLTF_TO_RED, relative_gltf), GLTF_TO_BLENDER_BONE_RIGHT)
    return np.matmul(
        np.matmul(BLENDER_BONE_RIGHT_TO_GLTF, relative_gltf),
        GLTF_TO_BLENDER_BONE_RIGHT,
    )


def blender_relative_to_gltf(relative_blender, is_root: bool):
    relative_blender = np.asarray(relative_blender, dtype=np.float64)
    if is_root:
        return np.matmul(np.matmul(RED_TO_GLTF, relative_blender), BLENDER_BONE_RIGHT_TO_GLTF)
    return np.matmul(
        np.matmul(GLTF_TO_BLENDER_BONE_RIGHT, relative_blender),
        BLENDER_BONE_RIGHT_TO_GLTF,
    )


def gltf_matrix_to_red(matrix):
    value = np.asarray(matrix, dtype=np.float64)
    return GLTF_TO_RED @ value @ RED_TO_GLTF


def red_matrix_to_gltf(matrix):
    value = np.asarray(matrix, dtype=np.float64)
    return RED_TO_GLTF @ value @ GLTF_TO_RED


def red_local_transform_to_current_bone(matrix):
    return RED_LOCAL_TO_BLENDER_BONE_CURRENT @ np.asarray(matrix, dtype=np.float64)


def current_bone_local_transform_to_red(matrix):
    return BLENDER_BONE_LOCAL_TO_RED_CURRENT @ np.asarray(matrix, dtype=np.float64)

def red_additive_to_current_bone(translations, rotations_xyzw):
    translations = np.asarray(translations)
    rotations = np.asarray(rotations_xyzw)
    converted_translations = np.stack(
        (-translations[..., 2], translations[..., 1], translations[..., 0]),
        axis=-1,
    )
    converted_rotations = np.stack(
        (-rotations[..., 2], rotations[..., 1], rotations[..., 0], rotations[..., 3]),
        axis=-1,
    )
    return converted_translations, converted_rotations


def current_bone_to_red_additive(translations, rotations_xyzw):
    translations = np.asarray(translations)
    rotations = np.asarray(rotations_xyzw)
    converted_translations = np.stack(
        (translations[..., 2], translations[..., 1], -translations[..., 0]),
        axis=-1,
    )
    converted_rotations = np.stack(
        (rotations[..., 2], rotations[..., 1], -rotations[..., 0], rotations[..., 3]),
        axis=-1,
    )
    return converted_translations, converted_rotations
