from __future__ import annotations

import math
import re

from .gears import gear_max_speed, gears_from_config

_RECORD_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


def _record_id(value, label):
    value = str(value or "").strip()
    if not _RECORD_ID.fullmatch(value):
        raise ValueError(f"{label} must be a dotted TweakDB record ID")
    return value


def _number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("TweakXL numeric values must be finite")
    text = f"{result:.9g}"
    return text if "." in text or "e" in text.casefold() else text + ".0"


def _vector(values):
    x, y, z = (float(value) for value in values)
    return f"{{ x: {_number(x)}, y: {_number(y)}, z: {_number(z)} }}"


def _line(lines, level, key, value=None):
    suffix = ":" if value is None else f": {value}"
    lines.append("  " * level + str(key) + suffix)


PLAYER_VEHICLE_LIST_FIELD = "Vehicle.vehicle_list.list"


def build_tweakxl_yaml(
    record_id, base_record, kind, config, *, add_to_vehicle_list=False
):
    """The TweakXL YAML of an authored vehicle"""
    record_id = _record_id(record_id, "Record ID")
    base_record = _record_id(base_record, "Base Record")
    if record_id.casefold() == base_record.casefold():
        raise ValueError("Record ID must differ from the base vehicle record")
    kind = str(kind or "CAR").upper()
    if kind not in {"CAR", "BIKE"}:
        raise ValueError("Vehicle kind must be CAR or BIKE")
    expected = 2 if kind == "BIKE" else 4

    def values(key, fallback=None):
        result = config.get(key, fallback)
        if not isinstance(result, (list, tuple)) or len(result) != expected:
            raise ValueError(
                f"{key} must contain {expected} values for a {kind.lower()}"
            )
        return list(result)

    radii = list(config.get("wheel_radii", ()))
    widths = list(config.get("wheel_widths", ()))
    if len(radii) != expected or len(widths) != expected:
        raise ValueError(
            f"{kind.title()} geometry must contain {expected} wheel dimensions"
        )
    front_indices = (0,) if kind == "BIKE" else (0, 1)
    rear_indices = (1,) if kind == "BIKE" else (2, 3)
    front_radius = sum(radii[index] for index in front_indices) / len(front_indices)
    rear_radius = sum(radii[index] for index in rear_indices) / len(rear_indices)
    front_width = sum(widths[index] for index in front_indices) / len(front_indices)
    rear_width = sum(widths[index] for index in rear_indices) / len(rear_indices)
    rim_radii = list(config.get("wheel_rim_radii", radii))
    if len(rim_radii) != expected:
        raise ValueError(
            f"{kind.title()} geometry must contain {expected} rim dimensions"
        )
    front_rim_radius = sum(rim_radii[index] for index in front_indices) / len(
        front_indices
    )
    rear_rim_radius = sum(rim_radii[index] for index in rear_indices) / len(
        rear_indices
    )
    gears = gears_from_config(config)
    differential = str(config.get("differential_type", "") or "").upper()
    if kind == "BIKE":
        driven_radius = front_radius if differential == "BIKE_FWD" else rear_radius
    elif differential == "FWD":
        driven_radius = front_radius
    elif differential == "RWD":
        driven_radius = rear_radius
    else:
        driven_radius = 0.5 * (front_radius + rear_radius)
    gear_record_ids = [
        f"{record_id}_gear_reverse" if index == 0 else f"{record_id}_gear_{index}"
        for index in range(len(gears))
    ]
    fallback_gear_base = next(
        (gear.source_record for gear in gears if gear.source_record), ""
    )
    dimension_offsets = list(config.get("wheel_dimension_offsets", (0.0, 0.0)))
    if len(dimension_offsets) != 2:
        raise ValueError("Wheel dimension offsets must contain front and rear values")
    wheel_masses = values("wheel_masses")
    brake_torques = values("brake_torques")
    handbrake_torques = values("handbrake_torques")
    steer_angles = values("steer_angles")
    spring_rates = values("suspension_spring_rates_kg_mm")
    compression_lengths = values("suspension_compressions")
    droop_lengths = values("suspension_droops")
    damper_rates = values("suspension_damper_rates")
    compression_damping = values("suspension_compression_damper_rates", damper_rates)
    rebound_damping = values("suspension_rebound_damper_rates", damper_rates)
    visual_compression = values("suspension_visual_compressions", compression_lengths)
    vertical_offsets = values("wheel_vertical_offsets", [0.0] * expected)
    tire_frictions = values("tire_frictions")
    coefficients = values("tire_friction_coefficients", tire_frictions)
    longitudinal = values("tire_friction_longitudinal_multipliers", [1.0] * expected)
    lateral = values("tire_friction_lateral_multipliers", [1.0] * expected)

    lines = []
    _line(lines, 0, record_id)
    _line(lines, 1, "$base", base_record)
    _line(lines, 1, "vehWheelDimensionsSetup")
    dimensions_base = config.get("source_dimensions_record")
    if dimensions_base:
        _line(lines, 2, "$base", _record_id(dimensions_base, "Wheel dimensions base"))
    _line(lines, 2, "frontPreset")
    if config.get("source_front_dimensions_record"):
        _line(
            lines,
            3,
            "$base",
            _record_id(
                config["source_front_dimensions_record"], "Front dimensions base"
            ),
        )
    _line(lines, 3, "tireRadius", _number(front_radius))
    _line(lines, 3, "rimRadius", _number(front_rim_radius))
    _line(lines, 3, "tireWidth", _number(front_width))
    _line(lines, 3, "wheelOffset", _number(dimension_offsets[0]))
    _line(lines, 2, "backPreset")
    if config.get("source_rear_dimensions_record"):
        _line(
            lines,
            3,
            "$base",
            _record_id(config["source_rear_dimensions_record"], "Rear dimensions base"),
        )
    _line(lines, 3, "tireRadius", _number(rear_radius))
    _line(lines, 3, "rimRadius", _number(rear_rim_radius))
    _line(lines, 3, "tireWidth", _number(rear_width))
    _line(lines, 3, "wheelOffset", _number(dimension_offsets[1]))

    drive_key = "bikeDriveModelData" if kind == "BIKE" else "vehDriveModelData"
    _line(lines, 1, drive_key)
    drive_base = config.get("source_drive_record")
    if drive_base:
        _line(lines, 2, "$base", _record_id(drive_base, "Drive model base"))
    _line(lines, 2, "chassis_mass", _number(config["chassis_mass"]))
    _line(
        lines,
        2,
        "total_mass",
        _number(config.get("total_mass", config["chassis_mass"])),
    )
    _line(lines, 2, "center_of_mass_offset", _vector(config["chassis_cm_source"]))
    _line(
        lines,
        2,
        "airResistanceFactor",
        _number(config.get("air_resistance_factor", 1.0)),
    )
    _line(
        lines,
        2,
        "brakingFrictionFactor",
        _number(config.get("braking_friction_factor", 1.0)),
    )
    _line(
        lines, 2, "turningRollFactor", _number(config.get("turning_roll_factor", 1.0))
    )
    if config.get("chassis_inertia"):
        _line(lines, 2, "momentOfInertia", _vector(config["chassis_inertia"]))
    _line(lines, 2, "maxWheelTurnDeg", _number(math.degrees(max(steer_angles))))
    _line(lines, 2, "wheelTurnMaxAddPerSecond", _number(config["wheel_turn_add_rate"]))
    _line(lines, 2, "wheelTurnMaxSubPerSecond", _number(config["wheel_turn_sub_rate"]))
    _line(lines, 2, "handbrakeBrakingTorque", _number(max(handbrake_torques)))
    if kind == "BIKE":
        tilt_pid = list(config.get("bike_tilt_pid", (2.5, 0.2, 0.0)))
        if len(tilt_pid) != 3:
            raise ValueError("Bike lean PID must contain three values")
        _line(
            lines,
            2,
            "bikeTiltPID",
            "[ " + ", ".join(_number(value) for value in tilt_pid) + " ]",
        )
        _line(
            lines,
            2,
            "bikeMaxTilt",
            _number(math.degrees(config["bike_max_lean_angle"])),
        )
        _line(
            lines, 2, "bikeTiltSpeed", _number(math.degrees(config["bike_tilt_speed"]))
        )
        _line(
            lines,
            2,
            "bikeTiltReturnSpeed",
            _number(math.degrees(config["bike_tilt_return_speed"])),
        )
        _line(
            lines,
            2,
            "bikeTiltCustomSpeed",
            _number(math.degrees(config["bike_tilt_custom_speed"])),
        )
        _line(
            lines,
            2,
            "bikeMaxCOMLongOffset",
            _number(config["bike_max_com_long_offset"]),
        )
        _line(
            lines,
            2,
            "bikeMinCOMLongOffset",
            _number(config["bike_min_com_long_offset"]),
        )
        _line(
            lines,
            2,
            "bikeCOMOffsetDampFactor",
            _number(config["bike_com_offset_damp_factor"]),
        )
    _line(lines, 2, "wheelSetup")
    if config.get("source_wheel_setup_record"):
        _line(
            lines,
            3,
            "$base",
            _record_id(config["source_wheel_setup_record"], "Wheel setup base"),
        )
    for axle_name, indices, source_key in (
        ("frontPreset", front_indices, "source_front_wheel_record"),
        ("backPreset", rear_indices, "source_rear_wheel_record"),
    ):
        _line(lines, 3, axle_name)
        if config.get(source_key):
            _line(
                lines, 4, "$base", _record_id(config[source_key], f"{axle_name} base")
            )
        _line(
            lines,
            4,
            "mass",
            _number(sum(wheel_masses[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "maxBrakingTorque",
            _number(max(brake_torques[index] for index in indices)),
        )
        _line(
            lines,
            4,
            "springStiffness",
            _number(sum(spring_rates[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "springDamping",
            _number(
                sum(compression_damping[index] for index in indices) / len(indices)
            ),
        )
        _line(
            lines,
            4,
            "springReboundDamping",
            _number(sum(rebound_damping[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "visualSuspensionDroop",
            _number(sum(droop_lengths[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "logicalSuspensionCompressionLength",
            _number(
                sum(compression_lengths[index] for index in indices) / len(indices)
            ),
        )
        _line(
            lines,
            4,
            "visualSuspensionCompressionLength",
            _number(sum(visual_compression[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "wheelsVerticalOffset",
            _number(sum(vertical_offsets[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "tireFrictionCoef",
            _number(sum(coefficients[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "frictionMulLongitudinal",
            _number(sum(longitudinal[index] for index in indices) / len(indices)),
        )
        _line(
            lines,
            4,
            "frictionMulLateral",
            _number(sum(lateral[index] for index in indices) / len(indices)),
        )
        preset_key = (
            "cp77_front_wheel_preset"
            if axle_name == "frontPreset"
            else "cp77_rear_wheel_preset"
        )
        preset = (
            config.get(preset_key) if isinstance(config.get(preset_key), dict) else {}
        )
        for field in (
            "extremeCompressionEventScalor",
            "springBoundDampingLowRate",
            "springDampingHighRateCompression",
            "springDampingLowRateCompression",
            "springReboundDampingLowRate",
            "swaybarStiffness",
            "swaybarLengthScalar",
            "swaybarDisplacementLimit",
            "tenderSpringLength",
            "tireLateralSlipEffectsMul",
            "tireLongitudinalSlipEffectsMul",
            "tireRollingResistanceCoef",
        ):
            if field in preset:
                _line(lines, 4, field, _number(preset[field]))
    flag_names = ("F", "B") if kind == "BIKE" else ("LF", "RF", "LB", "RB")
    source_flags = list(config.get("wheel_flags", ()))
    for index, flag_name in enumerate(flag_names):
        flag = (
            source_flags[index]
            if index < len(source_flags) and isinstance(source_flags[index], dict)
            else {}
        )
        _line(lines, 3, flag_name)
        _line(lines, 4, "isDrive", "true" if flag.get("isDrive", False) else "false")
        _line(
            lines,
            4,
            "isMainBrake",
            "true" if flag.get("isMainBrake", False) else "false",
        )
        _line(
            lines,
            4,
            "isHandBrake",
            "true" if flag.get("isHandBrake", False) else "false",
        )

    _line(lines, 1, "vehEngineData")
    engine_base = config.get("source_engine_record")
    if engine_base:
        _line(lines, 2, "$base", _record_id(engine_base, "Engine base"))
    _line(lines, 2, "engineMaxTorque", _number(config["engine_peak_torque"]))
    max_omega = float(config["engine_max_omega"])
    _line(lines, 2, "maxRPM", _number(max_omega * 60.0 / (2.0 * math.pi)))
    _line(
        lines,
        2,
        "resistanceTorque",
        _number(float(config["engine_damping_rate"]) * max_omega),
    )
    _line(lines, 2, "flyWheelMomentOfInertia", _number(config["engine_moi"]))
    _line(lines, 2, "gearChangeTime", _number(config["gear_switch_time"]))
    _line(
        lines,
        2,
        "finalGearTorqueDecimationScalor",
        _number(config.get("final_gear_torque_decimation", 1.0)),
    )
    _line(lines, 2, "gears")
    for gear_record_id in gear_record_ids:
        lines.append("  " * 3 + f"- {gear_record_id}")

    for index, (gear, gear_record_id) in enumerate(zip(gears, gear_record_ids)):
        lines.append("")
        _line(lines, 0, gear_record_id)
        gear_base = gear.source_record or fallback_gear_base
        if gear_base:
            _line(lines, 1, "$base", _record_id(gear_base, f"Gear {index} base"))
        _line(lines, 1, "minSpeed", _number(gear.min_speed))
        _line(lines, 1, "minEngineRPM", _number(gear.min_engine_rpm))
        _line(lines, 1, "maxEngineRPM", _number(gear.max_engine_rpm))
        _line(lines, 1, "maxSpeed", _number(gear_max_speed(gear, driven_radius)))
        _line(lines, 1, "torqueMultiplier", _number(gear.torque_multiplier))
    if add_to_vehicle_list:
        lines.append("")
        _line(lines, 0, PLAYER_VEHICLE_LIST_FIELD)
        lines.append(f"  - !append-once {record_id}")
    return "\n".join(lines) + "\n"
