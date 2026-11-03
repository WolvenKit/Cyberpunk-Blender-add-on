from __future__ import annotations

import numpy as np


def read_npz_arrays(path) -> dict[str, np.ndarray] | None:
    """Every array of an .npz file, or None when it is missing or unreadable. Pickled objects are refused"""
    try:
        with np.load(path, allow_pickle=False) as data:
            return {key: data[key] for key in data.files}
    except (OSError, ValueError):
        return None
