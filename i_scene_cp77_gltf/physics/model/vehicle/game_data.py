from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityVehicleData:
    entity_path: str
    chassis_collision_path: str
    chassis_local_position: tuple[float, float, float]
    chassis_local_transform: dict
    vehicle_rig_path: str
    vehicle_rig_local_transform: dict


@dataclass(frozen=True, slots=True)
class VehicleGameData:
    record_id: str
    config: dict
    source_files: tuple[str, ...]
    warnings: tuple[str, ...]
