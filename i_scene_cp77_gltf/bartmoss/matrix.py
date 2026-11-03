from __future__ import annotations

import numpy as np

# How far a matrix may stray from unit scale and orthonormal axes and still count as rigid.
RIGID_TOLERANCE = 2e-5


def transfer_matrix_delta(current, previous_reference, next_reference):
    """Preserve a model-space edit while changing its reference transform"""
    return (
        as_matrix_4x4(current)
        @ np.linalg.inv(as_matrix_4x4(previous_reference))
        @ as_matrix_4x4(next_reference)
    )


def as_matrix_4x4(matrix, *, dtype=np.float64) -> np.ndarray:
    value = matrix.to_4x4() if hasattr(matrix, "to_4x4") else matrix
    if isinstance(value, np.ndarray):
        return np.asarray(value, dtype=dtype).reshape(4, 4)
    rows = tuple(tuple(row) if hasattr(row, "__iter__") else row for row in value)
    return np.asarray(rows, dtype=dtype).reshape(4, 4)


def rigid_matrices(matrices) -> np.ndarray:
    """4x4 matrices with each 3x3 basis replaced by its nearest orthogonal basis (polar decomposition)"""
    result = np.array(matrices, dtype=np.float64)
    left, _scales, right = np.linalg.svd(result[..., :3, :3])
    result[..., :3, :3] = left @ right
    return result


def flatten_matrix(
    matrix, *, column_major: bool = False, dtype=np.float64
) -> np.ndarray:
    value = as_matrix_4x4(matrix, dtype=dtype)
    if column_major:
        value = value.T
    return np.ascontiguousarray(value.reshape(16))


def matrix_is_identity(matrix, tolerance: float = 1e-8) -> bool:
    try:
        value = as_matrix_4x4(matrix, dtype=np.float64)
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        np.allclose(value, np.eye(4, dtype=np.float64), atol=float(tolerance), rtol=0.0)
    )


# Not placements_near: an absolute tolerance on plain rows, without numpy, for the dangle solver's per-bone checks.
def matrices_near(left, right, epsilon: float = 1e-5) -> bool:
    """Whether two matrices agree element-wise within epsilon"""
    if right is None:
        return False
    for left_row, right_row in zip(left, right):
        for a, b in zip(left_row, right_row):
            if abs(a - b) > epsilon:
                return False
    return True


def placements_near(left, right, epsilon: float = 1e-5, relative: float = 4e-7) -> bool:
    """Whether two placements agree element-wise within epsilon, or relative for larger values"""
    a, b = as_matrix_4x4(left), as_matrix_4x4(right)
    return bool(
        np.all(
            np.abs(a - b)
            <= np.maximum(epsilon, relative * np.maximum(np.abs(a), np.abs(b)))
        )
    )


def scale_in_frame(rotation, scale) -> np.ndarray:
    """What scaling by scale does to something the 3x3 rotation turned, in its own turned frame"""
    turned = np.array([tuple(row)[:3] for row in rotation][:3], dtype=np.float64)
    return turned.T @ np.diag(np.asarray(scale, dtype=np.float64)) @ turned


def scale_shears(rotation, scale, epsilon: float = 1e-5) -> bool:
    """Whether scaling by scale what the 3x3 rotation turned shears it"""
    stretched = scale_in_frame(rotation, scale)
    off_diagonal = stretched - np.diag(np.diag(stretched))
    return bool(
        np.abs(off_diagonal).max() > epsilon * max(float(np.abs(scale).max()), 1.0)
    )


def box_around(matrix) -> tuple[np.ndarray, np.ndarray]:
    """(centre, half extents) of the axis-aligned box around the cube matrix moves"""
    value = as_matrix_4x4(matrix)
    return value[:3, 3].copy(), np.abs(value[:3, :3]).sum(axis=1)


def axis_angle_matrices(axes, angles) -> np.ndarray:
    """3x3 rotations by angles (radians) about the axes, batched"""
    axes = np.asarray(axes, dtype=np.float64)
    axes = axes / np.maximum(np.linalg.norm(axes, axis=-1, keepdims=True), 1e-15)
    angles = np.asarray(angles, dtype=np.float64)[..., None, None]
    cross = np.zeros(axes.shape[:-1] + (3, 3))
    cross[..., 0, 1], cross[..., 0, 2] = -axes[..., 2], axes[..., 1]
    cross[..., 1, 0], cross[..., 1, 2] = axes[..., 2], -axes[..., 0]
    cross[..., 2, 0], cross[..., 2, 1] = -axes[..., 1], axes[..., 0]
    return np.eye(3) + np.sin(angles) * cross + (1.0 - np.cos(angles)) * (cross @ cross)


def swing_matrices(source, target) -> np.ndarray:
    """The shortest 3x3 rotations that turn the source directions onto the target directions, batched"""
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    source = source / np.maximum(np.linalg.norm(source, axis=-1, keepdims=True), 1e-15)
    target = target / np.maximum(np.linalg.norm(target, axis=-1, keepdims=True), 1e-15)
    axes = np.cross(source, target)
    sines = np.linalg.norm(axes, axis=-1)
    cosines = np.clip(np.sum(source * target, axis=-1), -1.0, 1.0)
    # Opposite directions turn half a turn about any axis square to the source.
    opposite = (sines <= 1e-9) & (cosines < 0.0)
    if np.any(opposite):
        spare = np.where(
            np.abs(source[..., :1]) < 0.9, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        )
        axes = np.where(opposite[..., None], np.cross(source, spare), axes)
    return axis_angle_matrices(axes, np.arctan2(sines, cosines))


def rotation_vectors(rotations) -> np.ndarray:
    """Axis times angle (radians) of 3x3 rotations, batched, as axis_angle_matrices takes them"""
    rotations = np.asarray(rotations, dtype=np.float64)
    cosines = np.clip((np.trace(rotations, axis1=-2, axis2=-1) - 1.0) / 2.0, -1.0, 1.0)
    angles = np.arccos(cosines)
    skew = np.stack(
        (
            rotations[..., 2, 1] - rotations[..., 1, 2],
            rotations[..., 0, 2] - rotations[..., 2, 0],
            rotations[..., 1, 0] - rotations[..., 0, 1],
        ),
        axis=-1,
    )
    sines = np.linalg.norm(skew, axis=-1) / 2.0
    return (
        skew
        * np.where(sines > 1e-9, angles / np.maximum(2.0 * sines, 1e-12), 0.5)[
            ..., None
        ]
    )
