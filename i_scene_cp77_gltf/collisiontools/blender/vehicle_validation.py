from __future__ import annotations

import json

from ...physics.domain.vehicle.gears import collection_gears, validate_gears
from .vehicle_gears import ensure_gear_collection


def resolved_game_config(vehicle):
    if not getattr(vehicle, "game_data_enabled", False):
        return {}
    try:
        value = json.loads(vehicle.game_data_config or "{}")
    except (TypeError, ValueError) as error:
        raise ValueError(f"Resolved vehicle game data is invalid: {error}") from error
    if not isinstance(value, dict) or not value:
        raise ValueError("Resolved vehicle game data is empty")
    return value


def validate_authoring_state(vehicle):
    errors = []
    warnings = []
    if not vehicle.enabled:
        errors.append("Vehicle authoring is disabled")
    game_config = {}
    if getattr(vehicle, "game_data_enabled", False):
        try:
            game_config = resolved_game_config(vehicle)
        except ValueError as error:
            errors.append(str(error))
    try:
        ensure_gear_collection(vehicle, game_config)
        validate_gears(collection_gears(vehicle), vehicle=vehicle)
    except ValueError as error:
        errors.append(str(error))
    return errors, warnings, game_config


def validate_powertrain(vehicle, *, total_mass_label, axles_first=True):
    axle_errors = []
    for label, axle in (("Front", vehicle.front_axle), ("Rear", vehicle.rear_axle)):
        if axle.tire_radius <= 0.0 or axle.tire_width <= 0.0 or axle.mass <= 0.0:
            axle_errors.append(
                f"{label} tireRadius, tireWidth, and mass must be positive"
            )
        if axle.spring_stiffness <= 0.0:
            axle_errors.append(f"{label} springStiffness must be positive")

    powertrain_errors = []
    if min(vehicle.chassis_dims) <= 0.0 or vehicle.chassis_mass <= 0.0:
        powertrain_errors.append("Chassis dimensions and mass must be positive")
    if vehicle.total_mass <= 0.0:
        powertrain_errors.append(f"{total_mass_label}.total_mass must be positive")
    if vehicle.use_chassis_inertia and any(
        value <= 0.0 for value in vehicle.chassis_inertia
    ):
        powertrain_errors.append(
            f"{total_mass_label}.momentOfInertia components must be positive"
        )
    if vehicle.engine_peak_torque <= 0.0 or vehicle.engine_max_omega <= 0.0:
        powertrain_errors.append(
            "vehEngineData.engineMaxTorque and maxRPM must be positive"
        )
    if vehicle.engine_moi <= 0.0 or vehicle.engine_resistance_torque < 0.0:
        powertrain_errors.append(
            "vehEngineData.flyWheelMomentOfInertia must be positive and resistanceTorque nonnegative"
        )
    if axles_first:
        return axle_errors + powertrain_errors
    return powertrain_errors + axle_errors
