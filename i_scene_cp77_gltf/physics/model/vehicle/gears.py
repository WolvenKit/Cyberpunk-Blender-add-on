from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VehicleGear:
    ratio: float
    min_speed: float
    max_speed: float
    torque_multiplier: float = 1.0
    min_engine_rpm: float = 0.0
    max_engine_rpm: float = 0.0
    source_record: str = ""
