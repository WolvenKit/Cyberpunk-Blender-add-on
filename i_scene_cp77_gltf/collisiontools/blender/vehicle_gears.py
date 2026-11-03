from __future__ import annotations

from ...physics.domain.vehicle.gears import (
    collection_gears,
    default_gears,
    driven_wheel_radius,
    gears_from_config,
    speed_for_ratio,
)
from ...physics.model.vehicle.gears import VehicleGear


def _write_collection(vehicle, gears):
    vehicle.gears.clear()
    for gear in gears:
        item = vehicle.gears.add()
        item.ratio = gear.ratio
        item.min_speed = gear.min_speed
        item.max_speed = gear.max_speed
        item.torque_multiplier = gear.torque_multiplier
        item.min_engine_rpm = gear.min_engine_rpm
        item.max_engine_rpm = gear.max_engine_rpm
        item.source_record = gear.source_record
    vehicle.gear_index = min(
        max(int(getattr(vehicle, "gear_index", 0)), 0), len(gears) - 1
    )
    return gears


def populate_default_gear_collection(vehicle):
    return _write_collection(vehicle, default_gears(vehicle))


def populate_gear_collection(vehicle, config):
    return _write_collection(
        vehicle, gears_from_config(config, driven_wheel_radius(vehicle))
    )


def ensure_gear_collection(vehicle, config=None):
    if len(vehicle.gears) >= 2:
        gears = collection_gears(vehicle)
        if any(gear.max_speed <= 0.0 for gear in gears):
            radius = driven_wheel_radius(vehicle)
            enriched = tuple(
                VehicleGear(
                    ratio=gear.ratio,
                    min_speed=gear.min_speed,
                    max_speed=gear.max_speed
                    if gear.max_speed > 0.0
                    else speed_for_ratio(gear.ratio, gear.max_engine_rpm, radius),
                    torque_multiplier=gear.torque_multiplier,
                    min_engine_rpm=gear.min_engine_rpm,
                    max_engine_rpm=gear.max_engine_rpm,
                    source_record=gear.source_record,
                )
                for gear in gears
            )
            return _write_collection(vehicle, enriched)
        return gears
    if isinstance(config, dict) and config:
        return populate_gear_collection(vehicle, config)
    return populate_default_gear_collection(vehicle)
