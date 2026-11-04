from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class MocapSkeletonError(ValueError):
    """A source skeleton whose body bones cannot be matched to the game rig"""

    def __init__(self, missing: tuple[str, ...], ambiguous: dict[str, tuple[str, ...]]):
        self.missing = tuple(missing)
        self.ambiguous = dict(ambiguous)
        clauses = []
        if self.missing:
            clauses.append("no source joint for " + ", ".join(self.missing))
        if self.ambiguous:
            clauses.append(
                "several candidates for "
                + ", ".join(
                    f"{bone} ({', '.join(candidates)})"
                    for bone, candidates in self.ambiguous.items()
                )
            )
        super().__init__("Unsupported skeleton: " + "; ".join(clauses) + ".")


class MocapTargetError(ValueError):
    """An armature the motion cannot be imported onto"""


@dataclass(frozen=True)
class TargetBody:
    """The game body the arms keep out of, skinned to the rig's bones"""

    points: np.ndarray
    normals: np.ndarray
    bones: tuple[int, ...]
    weights: np.ndarray
    arm_radii: tuple[float, float, float]


@dataclass(frozen=True)
class TargetRig:
    names: tuple[str, ...]
    parents: tuple[int, ...]
    rest_model: np.ndarray
    reference_model: np.ndarray
    body: TargetBody | None = None


@dataclass(frozen=True)
class RetargetResult:
    frame_count: int
    model_matrices: np.ndarray
    keyed: tuple[bool, ...]
    scale: float
