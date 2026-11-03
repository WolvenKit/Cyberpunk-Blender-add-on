from __future__ import annotations

import numpy as np

WOLVENKIT_V_FLIPPED_TEXCOORDS = frozenset({0})


def convert_wolvenkit_uv_channel(
    values, channel_index: int, *, copy: bool = True
) -> np.ndarray:
    """Convert a WolvenKit mesh TEXCOORD channel to or from RED numeric UV space"""
    uv = np.array(values, dtype=np.float32, order="C", copy=copy)
    if uv.ndim != 2 or uv.shape[1] < 2:
        raise ValueError(f"UV data must be an Nx2-or-wider array, got {uv.shape!r}.")
    if int(channel_index) in WOLVENKIT_V_FLIPPED_TEXCOORDS:
        uv[:, 1] = 1.0 - uv[:, 1]
    return uv
