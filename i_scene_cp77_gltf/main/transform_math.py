from __future__ import annotations

import numpy as np


def quat_multiply_xyzw(left: np.ndarray, right: np.ndarray) -> np.ndarray:
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


def quat_multiply_wxyz(left: np.ndarray, right: np.ndarray) -> np.ndarray:
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


def quat_nlerp_xyzw(left: np.ndarray, right: np.ndarray, weight) -> np.ndarray:
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


def parse_wkit_trs(records, count: int | None = None, *, quaternion_order: str = "xyzw"):
    """Parse WolvenKit TRS dictionaries into normalized float32 arrays."""
    records = records or ()
    size = len(records) if count is None else int(count)
    quaternions = np.zeros((size, 4), dtype=np.float32)
    translations = np.zeros((size, 3), dtype=np.float32)
    scales = np.ones((size, 3), dtype=np.float32)
    if quaternion_order == "xyzw":
        identity_index = 3
        component_keys = ("i", "j", "k", "r")
    elif quaternion_order == "wxyz":
        identity_index = 0
        component_keys = ("r", "i", "j", "k")
    else:
        raise ValueError(f"Unsupported quaternion order: {quaternion_order}")
    quaternions[:, identity_index] = 1.0
    for index, transform in enumerate(records[:size]):
        if not transform:
            continue
        rotation = transform.get("Rotation", {})
        quaternions[index] = tuple(float(rotation.get(key, 1.0 if key == "r" else 0.0)) for key in component_keys)
        translation = transform.get("Translation", {})
        translations[index] = (
            float(translation.get("X", 0.0)),
            float(translation.get("Y", 0.0)),
            float(translation.get("Z", 0.0)),
        )
        scale = transform.get("Scale", {})
        scales[index] = (
            float(scale.get("X", 1.0)),
            float(scale.get("Y", 1.0)),
            float(scale.get("Z", 1.0)),
        )
    norms = np.linalg.norm(quaternions, axis=1, keepdims=True)
    np.divide(quaternions, np.where(norms > 0.0, norms, 1.0), out=quaternions)
    return quaternions, translations, scales
