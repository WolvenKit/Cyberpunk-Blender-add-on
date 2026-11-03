from __future__ import annotations

import numpy as np

<<<<<<< Updated upstream
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
=======
from ..bartmoss.quaternion import multiply_scalar_xyzw, xyzw_from_matrices
from .contracts import (
    BLENDER_BONE_LOCAL_TO_RED_CURRENT,
    BLENDER_BONE_RIGHT_TO_GLTF,
    BVH_TO_RED,
    GLTF_TO_BLENDER_BONE_RIGHT,
    GLTF_TO_RED,
    ICLONE_TO_RED,
    MOCAP_SPACE_BVH,
    MOCAP_SPACE_ICLONE,
    RED_LIGHT_TO_BLENDER_LIGHT,
    RED_LOCAL_TO_BLENDER_BONE_CURRENT,
    RED_TO_BLENDER_BONE_RIGHT,
    RED_TO_GLTF,
    RIG_SPACE_CONTRACT_CURRENT,
    RIG_SPACE_CONTRACT_DIRECT,
)


def gltf_relative_to_blender_factors(is_root: bool):
    """(left, right) with gltf_relative_to_blender(m, is_root) == left @ m @ right"""
    return (
        GLTF_TO_RED if is_root else BLENDER_BONE_RIGHT_TO_GLTF
    ), GLTF_TO_BLENDER_BONE_RIGHT


def gltf_relative_to_blender(relative_gltf, is_root: bool):
    left, right = gltf_relative_to_blender_factors(is_root)
    return np.matmul(
        np.matmul(left, np.asarray(relative_gltf, dtype=np.float64)), right
>>>>>>> Stashed changes
    )


def blender_relative_to_gltf(relative_blender, is_root: bool):
    relative_blender = np.asarray(relative_blender, dtype=np.float64)
    if is_root:
<<<<<<< Updated upstream
        return np.matmul(np.matmul(RED_TO_GLTF, relative_blender), BLENDER_BONE_RIGHT_TO_GLTF)
=======
        return np.matmul(
            np.matmul(RED_TO_GLTF, relative_blender), BLENDER_BONE_RIGHT_TO_GLTF
        )
>>>>>>> Stashed changes
    return np.matmul(
        np.matmul(GLTF_TO_BLENDER_BONE_RIGHT, relative_blender),
        BLENDER_BONE_RIGHT_TO_GLTF,
    )


<<<<<<< Updated upstream
=======
def skeleton_relative_to_gltf(relative_blender, parent_indices) -> np.ndarray:
    """Parent-relative Blender bone matrices of a skeleton as glTF node matrices"""
    relative_blender = np.asarray(relative_blender, dtype=np.float64)
    roots = np.asarray(parent_indices) < 0
    result = np.empty_like(relative_blender)
    result[..., roots, :, :] = blender_relative_to_gltf(
        relative_blender[..., roots, :, :], True
    )
    result[..., ~roots, :, :] = blender_relative_to_gltf(
        relative_blender[..., ~roots, :, :], False
    )
    return result


# Row-vector forms of the glTF/REDengine axis change, held in float32 so per-vertex
# blocks stay in the accessor component type.
_GLTF_TO_RED_VECTOR_ROWS = np.ascontiguousarray(
    GLTF_TO_RED[:3, :3].astype(np.float32).T
)
_RED_TO_GLTF_VECTOR_ROWS = np.ascontiguousarray(
    RED_TO_GLTF[:3, :3].T.astype(np.float32)
)


def gltf_vectors_to_red(vectors):
    """Rows of glTF vectors (their first three columns) in REDengine space"""
    return vectors[:, :3] @ _GLTF_TO_RED_VECTOR_ROWS


def red_vectors_to_gltf(vectors):
    """Rows of REDengine vectors (their first three columns) in glTF space"""
    return vectors[:, :3] @ _RED_TO_GLTF_VECTOR_ROWS


>>>>>>> Stashed changes
def gltf_matrix_to_red(matrix):
    value = np.asarray(matrix, dtype=np.float64)
    return GLTF_TO_RED @ value @ RED_TO_GLTF


def red_matrix_to_gltf(matrix):
    value = np.asarray(matrix, dtype=np.float64)
    return RED_TO_GLTF @ value @ GLTF_TO_RED


def red_local_transform_to_current_bone(matrix):
    return RED_LOCAL_TO_BLENDER_BONE_CURRENT @ np.asarray(matrix, dtype=np.float64)


<<<<<<< Updated upstream
def current_bone_local_transform_to_red(matrix):
    return BLENDER_BONE_LOCAL_TO_RED_CURRENT @ np.asarray(matrix, dtype=np.float64)
=======
def red_axis_to_current_bone(axis):
    """A REDengine joint-local direction in the imported rig's bone-local frame"""
    return RED_LOCAL_TO_BLENDER_BONE_CURRENT[:3, :3] @ np.asarray(
        axis, dtype=np.float64
    )


def red_light_local_to_blender_light():
    """The local rotation that turns a REDengine light's +Y direction into a Blender light's -Z direction"""
    return RED_LIGHT_TO_BLENDER_LIGHT.copy()


def red_model_transform_to_current_bone(matrix):
    return np.asarray(matrix, dtype=np.float64) @ RED_TO_BLENDER_BONE_RIGHT


def current_bone_model_transform_to_red(matrix):
    return np.asarray(matrix, dtype=np.float64) @ RED_TO_BLENDER_BONE_RIGHT.T


def red_additive_matrix_to_current_bone(matrix):
    value = np.asarray(matrix, dtype=np.float64)
    return RED_LOCAL_TO_BLENDER_BONE_CURRENT @ value @ BLENDER_BONE_LOCAL_TO_RED_CURRENT


def current_bone_additive_matrix_to_red(matrix):
    value = np.asarray(matrix, dtype=np.float64)
    return BLENDER_BONE_LOCAL_TO_RED_CURRENT @ value @ RED_LOCAL_TO_BLENDER_BONE_CURRENT

>>>>>>> Stashed changes

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


<<<<<<< Updated upstream
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
=======
def red_additive_to_rig_contract(translations, rotations_xyzw, contract: str):
    """Engine local deltas in the bone space declared by a rig's space contract"""
    if contract == RIG_SPACE_CONTRACT_CURRENT:
        return red_additive_to_current_bone(translations, rotations_xyzw)
    if contract == RIG_SPACE_CONTRACT_DIRECT:
        return np.asarray(translations), np.asarray(rotations_xyzw)
    raise RuntimeError(f"Unsupported rig-space contract: {contract!r}")


def gltf_rest_relative_to_blender(
    local_matrices, joint_prefixes, joint_nodes, parent_indices
):
    """Convert parent-relative joint rests through intermediate glTF nodes"""
    relative = np.matmul(joint_prefixes, np.asarray(local_matrices)[list(joint_nodes)])
    return np.stack(
        [
            gltf_relative_to_blender(matrix, parent < 0)
            for matrix, parent in zip(relative, parent_indices)
        ]
    )


# Current-contract conversions on (translation, xyzw rotation, scale) components.
# The bone basis is a signed axis permutation, so translation and scale permute,
# the rotation is conjugated, and no matrix decomposition is needed.
_BONE_BASIS = np.asarray(RED_TO_BLENDER_BONE_RIGHT, dtype=np.float64)[:3, :3]
_BONE_BASIS_ROTATION = tuple(
    float(v) for v in xyzw_from_matrices(_BONE_BASIS[np.newaxis])[0]
)
_BONE_BASIS_ROTATION_INVERSE = (
    -_BONE_BASIS_ROTATION[0],
    -_BONE_BASIS_ROTATION[1],
    -_BONE_BASIS_ROTATION[2],
    _BONE_BASIS_ROTATION[3],
)
_BONE_BASIS_SQUARED = _BONE_BASIS * _BONE_BASIS


def _apply3(matrix, vector):
    return tuple(float(v) for v in matrix @ np.asarray(vector, dtype=np.float64))


def red_trs_to_current_bone(
    translation, rotation_xyzw, scale, *, relative_to_parent: bool
):
    """Engine transform components in the imported rig's bone space (see the matrix forms above)"""
    scale = _apply3(_BONE_BASIS_SQUARED.T, scale)
    if relative_to_parent:
        return (
            _apply3(_BONE_BASIS.T, translation),
            multiply_scalar_xyzw(
                multiply_scalar_xyzw(_BONE_BASIS_ROTATION_INVERSE, rotation_xyzw),
                _BONE_BASIS_ROTATION,
            ),
            scale,
        )
    return (
        tuple(translation),
        multiply_scalar_xyzw(rotation_xyzw, _BONE_BASIS_ROTATION),
        scale,
    )


def current_bone_trs_to_red(
    translation, rotation_xyzw, scale, *, relative_to_parent: bool
):
    """Imported-rig bone-space transform components as engine components"""
    scale = _apply3(_BONE_BASIS_SQUARED, scale)
    if relative_to_parent:
        return (
            _apply3(_BONE_BASIS, translation),
            multiply_scalar_xyzw(
                multiply_scalar_xyzw(_BONE_BASIS_ROTATION, rotation_xyzw),
                _BONE_BASIS_ROTATION_INVERSE,
            ),
            scale,
        )
    return (
        tuple(translation),
        multiply_scalar_xyzw(rotation_xyzw, _BONE_BASIS_ROTATION_INVERSE),
        scale,
    )


_MOCAP_TO_RED = {MOCAP_SPACE_BVH: BVH_TO_RED, MOCAP_SPACE_ICLONE: ICLONE_TO_RED}


def mocap_model_to_red(matrices, space: str) -> np.ndarray:
    """Model-space matrices of a mocap source space in the game's model axes"""
    basis = _MOCAP_TO_RED.get(space)
    if basis is None:
        raise ValueError(f"Unknown mocap space: {space!r}")
    return basis @ np.asarray(matrices, dtype=np.float64) @ basis.T
>>>>>>> Stashed changes
