from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ....bartmoss.quaternion import continuous_wxyz


@dataclass(slots=True)
class PoseBoneSamples:
    bone_name: str
    locations: np.ndarray
    rotations: np.ndarray
    scales: np.ndarray
    rotation_path: str


def frame_sequence(start: int, end: int, step: int = 1) -> np.ndarray:
    start = int(start)
    end = int(end)
    step = max(1, int(step))
    if end < start:
        raise ValueError("end must be greater than or equal to start")
    frames = np.arange(start, end + 1, step, dtype=np.float64)
    if not len(frames) or frames[-1] != end:
        frames = np.append(frames, float(end))
    return frames


def rotation_width(data_path: str) -> int:
    return 3 if data_path == "rotation_euler" else 4


def stabilize_rotations(values: np.ndarray, data_path: str) -> np.ndarray:
    if data_path == "rotation_quaternion":
        return continuous_wxyz(values)
    if data_path != "rotation_euler" or len(values) < 2:
        return values
    result = values.copy()
    for index in range(1, len(result)):
        for axis in range(3):
            delta = result[index, axis] - result[index - 1, axis]
            result[index, axis] -= np.floor((delta + np.pi) / (2.0 * np.pi)) * (
                2.0 * np.pi
            )
    return result
