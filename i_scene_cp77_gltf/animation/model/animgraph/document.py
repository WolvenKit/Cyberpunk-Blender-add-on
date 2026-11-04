from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnimGraphDocument:
    """A WolvenKit AnimGraph export"""

    path: str
    payload: dict
    source_text: str
