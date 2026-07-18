from __future__ import annotations

import math

import numpy as np

RIG_SPACE_CONTRACT = "CP77_RE_MODEL_BL_BONE_X_NEGZ_Y_Y_Z_X_V1"
FPS = 30.0
ANIMATION_EXTRAS_SNAPSHOT_KEY = "cp77_animation_extras_json"
SKIN_EXTRAS_SNAPSHOT_KEY = "cp77_skin_extras_json"
SOURCE_REST_SNAPSHOT_KEY = "cp77_animation_source_rest_json"
SOURCE_REST_SPACE_CONTRACT = "CP77_GLTF_SOURCE_RELATIVE_BLENDER_V1"

GLTF_TO_RED = np.array(
    (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ),
    dtype=np.float64,
)
RED_TO_GLTF = np.linalg.inv(GLTF_TO_RED)
RED_TO_BLENDER_BONE = np.array(
    (
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ),
    dtype=np.float64,
)
GLTF_TO_BLENDER_BONE_RIGHT = RED_TO_GLTF @ RED_TO_BLENDER_BONE
BLENDER_BONE_RIGHT_TO_GLTF = np.linalg.inv(GLTF_TO_BLENDER_BONE_RIGHT)


def quaternion_matrix_xyzw(value) -> np.ndarray:
    x, y, z, w = (float(component) for component in value)
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-15:
        x = y = z = 0.0
        w = 1.0
    else:
        x /= length
        y /= length
        z /= length
        w /= length
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array(
        (
            (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), 0.0),
            (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), 0.0),
            (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )


def compose_trs(translation, rotation_xyzw, scale) -> np.ndarray:
    matrix = quaternion_matrix_xyzw(rotation_xyzw)
    matrix[:3, :3] *= np.asarray(scale, dtype=np.float64)[np.newaxis, :]
    matrix[:3, 3] = np.asarray(translation, dtype=np.float64)
    return matrix


def compose_trs_batch(
    translations, rotations_xyzw, scales, *, normalize_rotations_in_place=False
) -> np.ndarray:
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


def quaternions_wxyz_from_matrices(matrices) -> np.ndarray:
    matrices = np.asarray(matrices, dtype=np.float64)
    original_shape = matrices.shape[:-2]
    values = matrices.reshape(-1, 3, 3)
    result = np.empty((len(values), 4), dtype=np.float64)
    trace = values[:, 0, 0] + values[:, 1, 1] + values[:, 2, 2]

    mask = trace > 0.0
    if np.any(mask):
        root = np.sqrt(np.maximum(trace[mask] + 1.0, 0.0)) * 2.0
        root = np.maximum(root, 1e-15)
        result[mask, 0] = 0.25 * root
        result[mask, 1] = (values[mask, 2, 1] - values[mask, 1, 2]) / root
        result[mask, 2] = (values[mask, 0, 2] - values[mask, 2, 0]) / root
        result[mask, 3] = (values[mask, 1, 0] - values[mask, 0, 1]) / root

    remaining = ~mask
    diagonal = np.stack(
        (values[:, 0, 0], values[:, 1, 1], values[:, 2, 2]), axis=1
    )
    dominant = np.argmax(diagonal, axis=1)
    for axis in range(3):
        axis_mask = remaining & (dominant == axis)
        if not np.any(axis_mask):
            continue
        matrix = values[axis_mask]
        if axis == 0:
            root = np.sqrt(
                np.maximum(1.0 + matrix[:, 0, 0] - matrix[:, 1, 1] - matrix[:, 2, 2], 0.0)
            ) * 2.0
            root = np.maximum(root, 1e-15)
            result[axis_mask, 0] = (matrix[:, 2, 1] - matrix[:, 1, 2]) / root
            result[axis_mask, 1] = 0.25 * root
            result[axis_mask, 2] = (matrix[:, 0, 1] + matrix[:, 1, 0]) / root
            result[axis_mask, 3] = (matrix[:, 0, 2] + matrix[:, 2, 0]) / root
        elif axis == 1:
            root = np.sqrt(
                np.maximum(1.0 + matrix[:, 1, 1] - matrix[:, 0, 0] - matrix[:, 2, 2], 0.0)
            ) * 2.0
            root = np.maximum(root, 1e-15)
            result[axis_mask, 0] = (matrix[:, 0, 2] - matrix[:, 2, 0]) / root
            result[axis_mask, 1] = (matrix[:, 0, 1] + matrix[:, 1, 0]) / root
            result[axis_mask, 2] = 0.25 * root
            result[axis_mask, 3] = (matrix[:, 1, 2] + matrix[:, 2, 1]) / root
        else:
            root = np.sqrt(
                np.maximum(1.0 + matrix[:, 2, 2] - matrix[:, 0, 0] - matrix[:, 1, 1], 0.0)
            ) * 2.0
            root = np.maximum(root, 1e-15)
            result[axis_mask, 0] = (matrix[:, 1, 0] - matrix[:, 0, 1]) / root
            result[axis_mask, 1] = (matrix[:, 0, 2] + matrix[:, 2, 0]) / root
            result[axis_mask, 2] = (matrix[:, 1, 2] + matrix[:, 2, 1]) / root
            result[axis_mask, 3] = 0.25 * root

    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    return result.reshape(original_shape + (4,))


def normalize_quaternions_xyzw(values) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64).copy()
    lengths = np.linalg.norm(result, axis=-1)
    invalid = lengths <= 1e-15
    if np.any(invalid):
        result[invalid] = (0.0, 0.0, 0.0, 1.0)
        lengths = np.linalg.norm(result, axis=-1)
    result /= lengths[..., None]
    if len(result) > 1:
        dots = np.sum(result[:-1] * result[1:], axis=1)
        flips = np.cumprod(np.where(dots < 0.0, -1.0, 1.0))
        result[1:] *= flips[:, None]
    return result


def quaternions_xyzw_from_matrices(matrices) -> np.ndarray:
    wxyz = quaternions_wxyz_from_matrices(matrices)
    xyzw = wxyz[..., (1, 2, 3, 0)]
    flat = xyzw.reshape(-1, 4)
    normalized = normalize_quaternions_xyzw(flat)
    return normalized.reshape(xyzw.shape)


def decompose_trs_batch(matrices):
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
    quaternions = quaternions_xyzw_from_matrices(flat_rotations).reshape(
        matrices.shape[:-2] + (4,)
    )
    return translations, quaternions, scales


def gltf_relative_to_blender(relative_gltf, is_root: bool):
    relative_gltf = np.asarray(relative_gltf, dtype=np.float64)
    if is_root:
        return np.matmul(
            np.matmul(GLTF_TO_RED, relative_gltf),
            GLTF_TO_BLENDER_BONE_RIGHT,
        )
    return np.matmul(
        np.matmul(BLENDER_BONE_RIGHT_TO_GLTF, relative_gltf),
        GLTF_TO_BLENDER_BONE_RIGHT,
    )


def blender_relative_to_gltf(relative_blender, is_root: bool):
    relative_blender = np.asarray(relative_blender, dtype=np.float64)
    if is_root:
        return np.matmul(
            np.matmul(RED_TO_GLTF, relative_blender),
            BLENDER_BONE_RIGHT_TO_GLTF,
        )
    return np.matmul(
        np.matmul(GLTF_TO_BLENDER_BONE_RIGHT, relative_blender),
        BLENDER_BONE_RIGHT_TO_GLTF,
    )
