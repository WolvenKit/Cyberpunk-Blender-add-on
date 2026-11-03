from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SolveResults:
    ran: frozenset[str] = frozenset()
    states: Mapping[str, int] = field(default_factory=dict)
    # State machine handle -> (source state, target state, progress 0-1) while a transition runs.
    transitions: Mapping[str, tuple[int, int, float]] = field(default_factory=dict)
    switches: Mapping[str, int] = field(default_factory=dict)
    # Blend or switch handle -> how much each input contributes, by the input's field: ``inputNode``, ``inputNodes[1]``.
    blend_weights: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
