from __future__ import annotations

import numpy as np

from ....redSpace.contracts import SOURCE_REST_SPACE_CONTRACT


def source_rest_relative(snapshot, source_names: tuple[str, ...]) -> np.ndarray | None:
    """A stored source rest as parent-relative Blender matrices, or None if it does not fit"""
    if not snapshot or snapshot.get("space") != SOURCE_REST_SPACE_CONTRACT:
        return None
    names = tuple(str(name) for name in snapshot.get("boneNames", ()))
    if names != source_names:
        return None
    matrices = snapshot.get("matrices")
    try:
        values = np.asarray(matrices, dtype=np.float64).reshape(len(source_names), 4, 4)
    except (TypeError, ValueError):
        return None
    if not np.all(np.isfinite(values)):
        return None
    determinants = np.linalg.det(values[:, :3, :3])
    if np.any(np.abs(determinants) <= 1e-10):
        return None
    return values
