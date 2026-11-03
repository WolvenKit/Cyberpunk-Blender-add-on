from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PhysicsFilterState:
    preset: str
    simulation_group: int
    simulation_target: int
    query_mask: int
