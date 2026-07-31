from __future__ import annotations

import numpy as np

from .bake import PoseBoneSamples
from ..bartmoss.quaternion import normalize_sequence_xyzw


def action_frame_range(action) -> tuple[int, int]:
    frame_range = action.frame_range
    return int(frame_range.x), int(frame_range.y)


def continuous_wxyz(values):
    values = np.asarray(values, dtype=np.float64)
    xyzw = normalize_sequence_xyzw(values[:, (1, 2, 3, 0)])
    return xyzw[:, (3, 0, 1, 2)]


def pose_samples(bone_name, locations, rotations, scales):
    return PoseBoneSamples(
        bone_name,
        np.asarray(locations, dtype=np.float64),
        continuous_wxyz(rotations),
        np.asarray(scales, dtype=np.float64),
        "rotation_quaternion",
    )


def identity_samples(bone_name, count: int):
    locations = np.zeros((count, 3), dtype=np.float64)
    rotations = np.zeros((count, 4), dtype=np.float64)
    rotations[:, 0] = 1.0
    scales = np.ones((count, 3), dtype=np.float64)
    return PoseBoneSamples(
        bone_name,
        locations,
        rotations,
        scales,
        "rotation_quaternion",
    )
