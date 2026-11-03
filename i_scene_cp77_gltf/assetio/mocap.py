from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class MocapFormatError(ValueError):
    """A motion file the importer cannot read"""


@dataclass(frozen=True)
class MocapSkeleton:
    names: tuple[str, ...]
    parents: tuple[int, ...]
    rest_translations: np.ndarray
    rest_rotations: np.ndarray
    end_offsets: tuple[tuple[float, float, float] | None, ...]
    hik_slots: tuple[int, ...] = ()


@dataclass(frozen=True)
class MocapTrack:
    times: np.ndarray
    rotations: np.ndarray
    translations: np.ndarray | None


@dataclass(frozen=True)
class MocapClip:
    name: str
    space: str
    skeleton: MocapSkeleton
    tracks: tuple[MocapTrack | None, ...]
    duration: float
