from __future__ import annotations

import numpy as np


def convert_wolvenkit_tangent_sign(values, *, copy: bool = True) -> np.ndarray:
    """Convert WolvenKit glTF tangent handedness to or from RED runtime sign"""
    signs = np.array(values, dtype=np.float32, order="C", copy=copy)
    signs *= -1.0
    return signs
