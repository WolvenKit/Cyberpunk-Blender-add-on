from __future__ import annotations

from ...physics.domain.vehicle.gears import (
    PHYSX_MAX_FORWARD_GEARS,
    default_gears,
    driven_wheel_radius,
    gears_from_config,
    speed_for_ratio,
    validate_gears,
)
from ...physics.model.vehicle.gears import VehicleGear, VehicleGearbox


def vehicle_gearbox(vehicle):
    bike = getattr(vehicle, "vehicle_kind", "CAR") == "BIKE"
    if bike:
        roles = (vehicle.wheel_role_front, vehicle.wheel_role_back)
    else:
        roles = (
            vehicle.wheel_role_lf,
            vehicle.wheel_role_rf,
            vehicle.wheel_role_lb,
            vehicle.wheel_role_rb,
        )
    return VehicleGearbox(
        gears=tuple(
            VehicleGear(
                ratio=float(item.ratio),
                min_speed=float(getattr(item, "min_speed", 0.0)),
                max_speed=float(getattr(item, "max_speed", 0.0)),
                torque_multiplier=float(item.torque_multiplier),
                min_engine_rpm=float(item.min_engine_rpm),
                max_engine_rpm=float(item.max_engine_rpm),
                source_record=str(item.source_record or ""),
            )
            for item in vehicle.gears
        ),
        front_tire_radius=float(vehicle.front_axle.tire_radius),
        rear_tire_radius=float(vehicle.rear_axle.tire_radius),
        drive_wheels=tuple(bool(role.is_drive) for role in roles),
        engine_max_omega=float(vehicle.engine_max_omega),
        final_gear_torque_decimation=float(vehicle.final_gear_torque_decimation),
        bike=bike,
    )


def validated_gears(vehicle, *, max_forward_gears=PHYSX_MAX_FORWARD_GEARS):
    gearbox = vehicle_gearbox(vehicle)
    return validate_gears(
        gearbox.gears, max_forward_gears=max_forward_gears, gearbox=gearbox
    )


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
    return _write_collection(vehicle, default_gears(vehicle_gearbox(vehicle)))


def populate_gear_collection(vehicle, config):
    return _write_collection(
        vehicle,
        gears_from_config(config, driven_wheel_radius(vehicle_gearbox(vehicle))),
    )


def ensure_gear_collection(vehicle, config=None):
    if len(vehicle.gears) >= 2:
        gearbox = vehicle_gearbox(vehicle)
        gears = gearbox.gears
        if any(gear.max_speed <= 0.0 for gear in gears):
            radius = driven_wheel_radius(gearbox)
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
