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


@dataclass(frozen=True, slots=True)
class VehicleGearbox:
    gears: tuple[VehicleGear, ...]
    front_tire_radius: float
    rear_tire_radius: float
    drive_wheels: tuple[bool, ...]
    engine_max_omega: float
    final_gear_torque_decimation: float = 1.0
    bike: bool = False
