from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PoseOpEvaluation:
    transforms_written: tuple[str, ...]
    tracks_written: tuple[str, ...] = ()
    applied: bool = True
    reason: str = ""
