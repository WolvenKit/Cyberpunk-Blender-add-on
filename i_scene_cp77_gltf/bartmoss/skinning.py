from __future__ import annotations

import numpy as np

# The least total weight that deforms a vertex, as Blender's armature deform has it.
MIN_DEFORM_WEIGHT = 1e-4


def blended_vertex_matrices(
    vertex_count, vertices, bones, weights, bone_matrices
) -> np.ndarray:
    """Each vertex's 4x4 deform by linear blend skinning"""
    vertices = np.asarray(vertices, dtype=np.int64)
    bones = np.asarray(bones, dtype=np.int64)
    weights = np.asarray(weights, dtype=np.float64)
    keep = weights > 0.0
    vertices, bones, weights = vertices[keep], bones[keep], weights[keep]
    blended = np.zeros((vertex_count, 4, 4))
    np.add.at(
        blended,
        vertices,
        weights[:, None, None] * np.asarray(bone_matrices, dtype=np.float64)[bones],
    )
    totals = np.bincount(vertices, weights=weights, minlength=vertex_count)
    weighted = totals >= MIN_DEFORM_WEIGHT
    blended[weighted] /= totals[weighted, None, None]
    blended[~weighted] = np.eye(4)
    return blended


def transform_points(points, matrices) -> np.ndarray:
    """Each point through its own affine 4x4 matrix"""
    matrices = np.asarray(matrices, dtype=np.float64)
    return (
        np.einsum(
            "nij,nj->ni", matrices[:, :3, :3], np.asarray(points, dtype=np.float64)
        )
        + matrices[:, :3, 3]
    )


def transform_normals(normals, matrices) -> np.ndarray:
    """Each unit normal through the inverse transpose of its matrix's linear part"""
    turned = np.einsum(
        "nji,nj->ni",
        np.linalg.inv(np.asarray(matrices, dtype=np.float64)[:, :3, :3]),
        np.asarray(normals, dtype=np.float64),
    )
    return turned / np.linalg.norm(turned, axis=1)[:, None]


def skinned_points(
    points, normals, weights, bone_matrices
) -> tuple[np.ndarray, np.ndarray]:
    """Points and unit normals skinned by weights for each frame of bone matrices"""
    weights = np.asarray(weights, dtype=np.float64)
    blended = np.einsum(
        "nk,fkij->fnij", weights, np.asarray(bone_matrices, dtype=np.float64)
    )
    posed = (
        np.einsum(
            "fnij,nj->fni", blended[..., :3, :3], np.asarray(points, dtype=np.float64)
        )
        + blended[..., :3, 3]
    )
    turned = np.einsum(
        "fnij,nj->fni", blended[..., :3, :3], np.asarray(normals, dtype=np.float64)
    )
    return posed, turned / np.maximum(
        np.linalg.norm(turned, axis=-1, keepdims=True), 1e-15
    )
