from __future__ import annotations

import math

import numpy as np


def identity_xyzw(count: int, dtype=np.float32) -> np.ndarray:
    result = np.zeros((int(count), 4), dtype=dtype)
    result[:, 3] = 1.0
    return result


def identity_wxyz(count: int, dtype=np.float32) -> np.ndarray:
    result = np.zeros((int(count), 4), dtype=dtype)
    result[:, 0] = 1.0
    return result


def multiply_xyzw(left, right) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    lx, ly, lz, lw = np.moveaxis(left, -1, 0)
    rx, ry, rz, rw = np.moveaxis(right, -1, 0)
    return np.stack((
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    ), axis=-1)


def multiply_wxyz(left, right) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    lw, lx, ly, lz = np.moveaxis(left, -1, 0)
    rw, rx, ry, rz = np.moveaxis(right, -1, 0)
    return np.stack((
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ), axis=-1)


def normalize_xyzw(values, epsilon: float = 1e-15) -> np.ndarray:
    result = np.asarray(values).copy()
    norms = np.linalg.norm(result, axis=-1, keepdims=True)
    invalid = norms <= epsilon
    np.divide(result, np.where(invalid, 1.0, norms), out=result)
    if np.any(invalid):
        result = np.where(
            invalid,
            np.asarray((0.0, 0.0, 0.0, 1.0), dtype=result.dtype),
            result,
        )
    return result


def normalize_wxyz(values, epsilon: float = 1e-15) -> np.ndarray:
    result = np.asarray(values).copy()
    norms = np.linalg.norm(result, axis=-1, keepdims=True)
    invalid = norms <= epsilon
    np.divide(result, np.where(invalid, 1.0, norms), out=result)
    if np.any(invalid):
        result = np.where(
            invalid,
            np.asarray((1.0, 0.0, 0.0, 0.0), dtype=result.dtype),
            result,
        )
    return result


def normalize_sequence_xyzw(values) -> np.ndarray:
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


def nlerp_xyzw(left, right, weight) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    dot = np.sum(left * right, axis=-1, keepdims=True)
    aligned = np.where(dot < 0.0, -right, right)
    weight = np.asarray(weight, dtype=left.dtype)
    while weight.ndim < left.ndim:
        weight = weight[..., None]
    blended = left + weight * (aligned - left)
    norms = np.linalg.norm(blended, axis=-1, keepdims=True)
    safe = np.where(norms < 1e-8, 1.0, norms)
    normalized = blended / safe
    return np.where(norms < 1e-8, left, normalized)


def slerp_xyzw(left, right, weight) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    weight = np.asarray(weight, dtype=np.result_type(left.dtype, right.dtype, np.float32))
    while weight.ndim < left.ndim:
        weight = weight[..., None]
    dot = np.sum(left * right, axis=-1, keepdims=True)
    aligned = np.where(dot < 0.0, -right, right)
    dot = np.abs(dot)
    theta = np.arccos(np.clip(dot, -1.0, 1.0))
    sin_theta = np.sin(theta)
    close = dot > 0.9995
    safe_sin = np.where(sin_theta < 1e-10, 1.0, sin_theta)
    first = np.sin((1.0 - weight) * theta) / safe_sin
    second = np.sin(weight * theta) / safe_sin
    spherical = first * left + second * aligned
    linear = (1.0 - weight) * left + weight * aligned
    linear /= np.linalg.norm(linear, axis=-1, keepdims=True) + 1e-10
    return np.where(close, linear, spherical)


def matrix_from_xyzw(value) -> np.ndarray:
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
    return np.array((
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), 0.0),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), 0.0),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ), dtype=np.float64)


def wxyz_from_matrices(matrices) -> np.ndarray:
    matrices = np.asarray(matrices, dtype=np.float64)
    original_shape = matrices.shape[:-2]
    values = matrices.reshape(-1, 3, 3)
    result = np.empty((len(values), 4), dtype=np.float64)
    trace = values[:, 0, 0] + values[:, 1, 1] + values[:, 2, 2]
    positive = trace > 0.0
    if np.any(positive):
        root = np.sqrt(np.maximum(trace[positive] + 1.0, 0.0)) * 2.0
        root = np.maximum(root, 1e-15)
        result[positive, 0] = 0.25 * root
        result[positive, 1] = (values[positive, 2, 1] - values[positive, 1, 2]) / root
        result[positive, 2] = (values[positive, 0, 2] - values[positive, 2, 0]) / root
        result[positive, 3] = (values[positive, 1, 0] - values[positive, 0, 1]) / root
    remaining = ~positive
    diagonal = np.stack((values[:, 0, 0], values[:, 1, 1], values[:, 2, 2]), axis=1)
    dominant = np.argmax(diagonal, axis=1)
    for axis in range(3):
        mask = remaining & (dominant == axis)
        if not np.any(mask):
            continue
        matrix = values[mask]
        if axis == 0:
            root = np.sqrt(np.maximum(1.0 + matrix[:, 0, 0] - matrix[:, 1, 1] - matrix[:, 2, 2], 0.0)) * 2.0
            root = np.maximum(root, 1e-15)
            result[mask, 0] = (matrix[:, 2, 1] - matrix[:, 1, 2]) / root
            result[mask, 1] = 0.25 * root
            result[mask, 2] = (matrix[:, 0, 1] + matrix[:, 1, 0]) / root
            result[mask, 3] = (matrix[:, 0, 2] + matrix[:, 2, 0]) / root
        elif axis == 1:
            root = np.sqrt(np.maximum(1.0 + matrix[:, 1, 1] - matrix[:, 0, 0] - matrix[:, 2, 2], 0.0)) * 2.0
            root = np.maximum(root, 1e-15)
            result[mask, 0] = (matrix[:, 0, 2] - matrix[:, 2, 0]) / root
            result[mask, 1] = (matrix[:, 0, 1] + matrix[:, 1, 0]) / root
            result[mask, 2] = 0.25 * root
            result[mask, 3] = (matrix[:, 1, 2] + matrix[:, 2, 1]) / root
        else:
            root = np.sqrt(np.maximum(1.0 + matrix[:, 2, 2] - matrix[:, 0, 0] - matrix[:, 1, 1], 0.0)) * 2.0
            root = np.maximum(root, 1e-15)
            result[mask, 0] = (matrix[:, 1, 0] - matrix[:, 0, 1]) / root
            result[mask, 1] = (matrix[:, 0, 2] + matrix[:, 2, 0]) / root
            result[mask, 2] = (matrix[:, 1, 2] + matrix[:, 2, 1]) / root
            result[mask, 3] = 0.25 * root
    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    return result.reshape(original_shape + (4,))


def xyzw_from_matrices(matrices) -> np.ndarray:
    wxyz = wxyz_from_matrices(matrices)
    xyzw = wxyz[..., (1, 2, 3, 0)]
    normalized = normalize_sequence_xyzw(xyzw.reshape(-1, 4))
    return normalized.reshape(xyzw.shape)
