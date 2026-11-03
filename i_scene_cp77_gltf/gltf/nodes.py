from __future__ import annotations

import numpy as np

from ..bartmoss.matrix import RIGID_TOLERANCE
from ..bartmoss.trs import compose_matrices, compose_matrix, decompose_matrices


def node_reference(value, count, label):
    """Validate an integer glTF table reference without numeric coercion"""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < count:
        raise ValueError(
            f"{label} must be an integer index in the range 0..{count - 1}."
        )
    return value


def node_trs(node):
    """Read a glTF node transform without accepting non-finite, ambiguous or sheared data"""
    if "matrix" in node:
        if any(name in node for name in ("translation", "rotation", "scale")):
            raise ValueError(
                "A glTF node cannot contain both matrix and TRS properties."
            )
        values = np.asarray(node["matrix"], dtype=np.float64)
        if values.shape != (16,) or not np.all(np.isfinite(values)):
            raise ValueError("glTF node matrix must contain 16 finite values.")
        matrix = values.reshape(4, 4).T
        if not np.allclose(matrix[3], (0, 0, 0, 1), rtol=0, atol=1e-8):
            raise ValueError("glTF node matrix must be affine.")
        translation, rotation, scale = decompose_matrices(matrix)
        if not np.allclose(
            compose_matrix(translation, rotation, scale),
            matrix,
            rtol=0,
            atol=RIGID_TOLERANCE,
        ):
            raise ValueError(
                "glTF node matrix contains shear that cannot be represented by TRS."
            )
        return translation, rotation, scale
    translation = np.asarray(node.get("translation", (0, 0, 0)), dtype=np.float64)
    rotation = np.asarray(node.get("rotation", (0, 0, 0, 1)), dtype=np.float64)
    scale = np.asarray(node.get("scale", (1, 1, 1)), dtype=np.float64)
    if translation.shape != (3,) or rotation.shape != (4,) or scale.shape != (3,):
        raise ValueError("Invalid glTF node TRS dimensions.")
    if not all(
        np.all(np.isfinite(values)) for values in (translation, rotation, scale)
    ):
        raise ValueError("glTF node TRS contains non-finite values.")
    length = np.linalg.norm(rotation)
    if not np.isclose(length, 1.0, rtol=0, atol=1e-3):
        raise ValueError("glTF node rotation must be a unit quaternion.")
    return translation, rotation / length, scale


def node_matrix(node):
    translation, rotation, scale = node_trs(node)
    if "matrix" in node:
        return np.asarray(node["matrix"], dtype=np.float64).reshape(4, 4).T.copy()
    return compose_matrix(translation, rotation, scale)


def node_transforms(matrices, *, matrix_fallback=True):
    """Serialize independent node transforms in one batch without quaternion sign coupling"""
    values = np.asarray(matrices, dtype=np.float64)
    if values.ndim != 3 or values.shape[1:] != (4, 4):
        raise ValueError("Node transforms require an array of 4x4 matrices.")
    if not np.all(np.isfinite(values)) or not np.allclose(
        values[:, 3], (0, 0, 0, 1), rtol=0, atol=1e-8
    ):
        raise ValueError("Node transforms must be finite affine matrices.")
    result = [{} for _ in values]
    identities = np.all(np.isclose(values, np.eye(4), rtol=0, atol=1e-9), axis=(1, 2))
    indices = np.flatnonzero(~identities)
    if not len(indices):
        return result
    selected = values[indices]
    translations, rotations, scales = decompose_matrices(
        selected, continuous_rotation=False
    )
    reconstructed = compose_matrices(translations, rotations, scales)
    representable = np.all(
        np.isclose(reconstructed, selected, rtol=0, atol=1e-6), axis=(1, 2)
    )
    representable &= np.all(np.abs(scales) > 1e-12, axis=1)
    if matrix_fallback:
        representable &= np.linalg.det(selected[:, :3, :3]) > 0
    elif not np.all(representable):
        raise ValueError(
            "Animated node rest transforms must be representable by non-singular TRS."
        )
    translated = ~np.all(np.isclose(translations, 0, atol=1e-8), axis=1)
    rotated = ~np.all(np.isclose(rotations, (0, 0, 0, 1), atol=1e-8), axis=1)
    scaled = ~np.all(np.isclose(scales, 1, atol=1e-8), axis=1)
    for row, index in enumerate(indices):
        node = result[index]
        if not representable[row]:
            node["matrix"] = selected[row].T.reshape(-1).tolist()
            continue
        if translated[row]:
            node["translation"] = translations[row].tolist()
        if rotated[row]:
            node["rotation"] = rotations[row].tolist()
        if scaled[row]:
            node["scale"] = scales[row].tolist()
    return result
