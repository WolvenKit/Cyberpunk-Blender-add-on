from __future__ import annotations

import math

from ...model.vehicle.gears import VehicleGear

PHYSX_MAX_FORWARD_GEARS = 30


def _finite(value, label):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def driven_wheel_radius(gearbox):
    front = max(float(gearbox.front_tire_radius), 1.0e-6)
    rear = max(float(gearbox.rear_tire_radius), 1.0e-6)
    wheels = gearbox.drive_wheels
    if gearbox.bike:
        front_drive, rear_drive = bool(wheels[0]), bool(wheels[1])
    else:
        front_drive = bool(wheels[0] or wheels[1])
        rear_drive = bool(wheels[2] or wheels[3])
    if front_drive and rear_drive:
        return 0.5 * (front + rear)
    if front_drive:
        return front
    if rear_drive:
        return rear
    return 0.5 * (front + rear)


def _ratio_for(max_speed, max_engine_rpm, driven_radius, index):
    speed = _finite(max_speed, f"gear {index} maxSpeed")
    rpm = _finite(max_engine_rpm, f"gear {index} maxEngineRPM")
    radius = _finite(driven_radius, "driven wheel radius")
    if speed <= 0.0 or rpm <= 0.0 or radius <= 0.0:
        raise ValueError(
            f"Gear {index} maxSpeed, maxEngineRPM, and driven wheel radius must be positive"
        )
    ratio = rpm * (2.0 * math.pi / 60.0) * radius / speed
    return -ratio if index == 0 else ratio


def speed_for_ratio(ratio, max_engine_rpm, driven_radius):
    ratio = abs(_finite(ratio, "gear ratio"))
    rpm = _finite(max_engine_rpm, "gear maximum RPM")
    radius = _finite(driven_radius, "driven wheel radius")
    if ratio <= 0.0 or rpm <= 0.0 or radius <= 0.0:
        raise ValueError(
            "Gear ratio, maximum RPM, and driven wheel radius must be positive"
        )
    return rpm * (2.0 * math.pi / 60.0) * radius / ratio


def effective_gear_ratio(gearbox, gear, index):
    if float(gear.max_speed) > 0.0:
        return _ratio_for(
            gear.max_speed, gear.max_engine_rpm, driven_wheel_radius(gearbox), index
        )
    ratio = _finite(gear.ratio, f"gear {index} ratio")
    if index == 0 and ratio >= 0.0:
        return -abs(ratio) if ratio else -1.0
    if index > 0 and ratio <= 0.0:
        return abs(ratio) if ratio else 1.0
    return ratio


def validate_gears(gears, *, max_forward_gears=PHYSX_MAX_FORWARD_GEARS, gearbox=None):
    gears = tuple(gears)
    if len(gears) < 2:
        raise ValueError("Gearbox must contain reverse and at least one forward gear")
    if len(gears) - 1 > int(max_forward_gears):
        raise ValueError(
            f"Gearbox contains {len(gears) - 1} forward gears; "
            f"the active vehicle backend supports at most {int(max_forward_gears)}"
        )
    for index, gear in enumerate(gears):
        multiplier = _finite(gear.torque_multiplier, f"gear {index} torqueMultiplier")
        minimum_rpm = _finite(gear.min_engine_rpm, f"gear {index} minEngineRPM")
        maximum_rpm = _finite(gear.max_engine_rpm, f"gear {index} maxEngineRPM")
        min_speed = _finite(gear.min_speed, f"gear {index} minSpeed")
        max_speed = _finite(gear.max_speed, f"gear {index} maxSpeed")
        ratio = (
            effective_gear_ratio(gearbox, gear, index)
            if gearbox is not None
            else _finite(gear.ratio, f"gear {index} ratio")
        )
        if index == 0 and ratio >= 0.0:
            raise ValueError("Reverse gear ratio must be negative")
        if index > 0 and ratio <= 0.0:
            raise ValueError(f"Forward gear {index} ratio must be positive")
        if min_speed < 0.0:
            raise ValueError(f"Gear {index} minSpeed cannot be negative")
        if max_speed <= 0.0:
            raise ValueError(f"Gear {index} maxSpeed must be positive")
        if min_speed >= max_speed:
            raise ValueError(f"Gear {index} minSpeed must be below maxSpeed")
        if multiplier < 0.0:
            raise ValueError(f"Gear {index} torqueMultiplier cannot be negative")
        if minimum_rpm < 0.0 or maximum_rpm <= 0.0:
            raise ValueError(
                f"Gear {index} RPM limits must be nonnegative with a positive maximum"
            )
        if minimum_rpm > maximum_rpm:
            raise ValueError(f"Gear {index} minEngineRPM cannot exceed maxEngineRPM")
    return gears


def gears_from_config(config, driven_radius=None):
    records = config.get("gears")
    if isinstance(records, list) and records:
        result = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"Resolved gear {index} must be a mapping")
            ratio = _finite(record.get("ratio"), f"gear {index} ratio")
            maximum_rpm = _finite(
                record.get("max_engine_rpm"), f"gear {index} maximum RPM"
            )
            max_speed = _finite(record.get("max_speed", 0.0), f"gear {index} maxSpeed")
            if max_speed <= 0.0 and driven_radius is not None:
                max_speed = speed_for_ratio(ratio, maximum_rpm, driven_radius)
            result.append(
                VehicleGear(
                    ratio=ratio,
                    min_speed=_finite(
                        record.get("min_speed", 0.0), f"gear {index} minSpeed"
                    ),
                    max_speed=max_speed,
                    torque_multiplier=_finite(
                        record.get("torque_multiplier", 1.0),
                        f"gear {index} torque multiplier",
                    ),
                    min_engine_rpm=_finite(
                        record.get("min_engine_rpm", 0.0), f"gear {index} minimum RPM"
                    ),
                    max_engine_rpm=maximum_rpm,
                    source_record=str(record.get("source_record", "") or ""),
                )
            )
        return validate_gears(result)

    ratios = config.get("gear_ratios")
    if not isinstance(ratios, list) or len(ratios) < 2:
        raise ValueError("Resolved vehicle data does not define a complete gearbox")
    multipliers = config.get("gear_torque_multipliers")
    if not isinstance(multipliers, list) or len(multipliers) != len(ratios):
        multipliers = [1.0] * len(ratios)
    engine_rpm = (
        _finite(config.get("engine_max_omega"), "engine maximum omega")
        * 60.0
        / (2.0 * math.pi)
    )
    up = config.get("autobox_up_ratios")
    down = config.get("autobox_down_ratios")
    forward_count = len(ratios) - 1
    if not isinstance(up, list) or len(up) != forward_count:
        up = [1.0] * forward_count
    if not isinstance(down, list) or len(down) != forward_count:
        down = [0.0] * forward_count
    result = []
    for index, ratio in enumerate(ratios):
        if index == 0:
            minimum_rpm = 0.0
            maximum_rpm = engine_rpm
        else:
            minimum_rpm = (
                _finite(down[index - 1], f"gear {index} down ratio") * engine_rpm
            )
            maximum_rpm = _finite(up[index - 1], f"gear {index} up ratio") * engine_rpm
        ratio_value = _finite(ratio, f"gear {index} ratio")
        max_speed = (
            speed_for_ratio(ratio_value, maximum_rpm, driven_radius)
            if driven_radius
            else 0.0
        )
        result.append(
            VehicleGear(
                ratio=ratio_value,
                min_speed=speed_for_ratio(ratio_value, minimum_rpm, driven_radius)
                if driven_radius and minimum_rpm > 0.0
                else 0.0,
                max_speed=max_speed,
                torque_multiplier=_finite(
                    multipliers[index], f"gear {index} torque multiplier"
                ),
                min_engine_rpm=minimum_rpm,
                max_engine_rpm=maximum_rpm,
            )
        )
    return validate_gears(result)


def default_gears(gearbox):
    max_rpm = float(gearbox.engine_max_omega) * 60.0 / (2.0 * math.pi)
    max_rpm = max(max_rpm, 1000.0)
    radius = driven_wheel_radius(gearbox)
    ratios = (-3.20, 3.20, 2.10, 1.52, 1.18, 0.96, 0.80)
    result = []
    for index, ratio in enumerate(ratios):
        if index == 0:
            minimum = 0.0
            maximum = max_rpm
        else:
            minimum = max_rpm * (0.22 if index == 1 else 0.34)
            maximum = max_rpm * (0.92 if index < len(ratios) - 1 else 1.0)
        result.append(
            VehicleGear(
                ratio=ratio,
                min_speed=speed_for_ratio(ratio, minimum, radius)
                if minimum > 0.0
                else 0.0,
                max_speed=speed_for_ratio(ratio, maximum, radius),
                torque_multiplier=1.0,
                min_engine_rpm=minimum,
                max_engine_rpm=maximum,
            )
        )
    return validate_gears(result)


def native_gear_payload(gearbox, *, max_forward_gears=PHYSX_MAX_FORWARD_GEARS):
    gears = validate_gears(
        gearbox.gears,
        max_forward_gears=max_forward_gears,
        gearbox=gearbox,
    )
    max_engine_rpm = float(gearbox.engine_max_omega) * 60.0 / (2.0 * math.pi)
    if not math.isfinite(max_engine_rpm) or max_engine_rpm <= 0.0:
        raise ValueError("Engine maximum omega must resolve to a positive RPM")
    final_scale = float(gearbox.final_gear_torque_decimation)
    if not math.isfinite(final_scale) or final_scale < 0.0:
        raise ValueError("Final gear torque scale must be finite and nonnegative")

    ratios = [
        effective_gear_ratio(gearbox, gear, index) for index, gear in enumerate(gears)
    ]
    multipliers = [float(gear.torque_multiplier) for gear in gears]
    multipliers[-1] *= final_scale
    up = []
    down = []
    for index, gear in enumerate(gears[1:], 1):
        up_ratio = min(max(gear.max_engine_rpm / max_engine_rpm, 0.01), 1.0)
        down_ratio = min(max(gear.min_engine_rpm / max_engine_rpm, 0.0), 0.99)
        if down_ratio >= up_ratio:
            raise ValueError(
                f"Forward gear {index} minEngineRPM must be below maxEngineRPM"
            )
        up.append(up_ratio)
        down.append(down_ratio)
    driven_indices = [
        index for index, drive in enumerate(gearbox.drive_wheels) if drive
    ]
    if not driven_indices:
        raise ValueError("At least one wheel must be configured as a drive wheel")

    return {
        "gear_ratios": ratios,
        "gear_torque_multipliers": multipliers,
        "gear_min_speeds": [float(gear.min_speed) for gear in gears],
        "gear_max_speeds": [float(gear.max_speed) for gear in gears],
        "gear_min_engine_rpms": [float(gear.min_engine_rpm) for gear in gears],
        "gear_max_engine_rpms": [float(gear.max_engine_rpm) for gear in gears],
        "driven_wheel_indices": driven_indices,
        "autobox_up_ratios": up,
        "autobox_down_ratios": down,
    }


def config_with_authored_gears(
    gearbox, config, *, max_forward_gears=PHYSX_MAX_FORWARD_GEARS
):
    result = dict(config)
    gears = validate_gears(
        gearbox.gears,
        max_forward_gears=max_forward_gears,
        gearbox=gearbox,
    )
    result["gears"] = [
        {
            "ratio": effective_gear_ratio(gearbox, gear, index),
            "min_speed": float(gear.min_speed),
            "max_speed": float(gear.max_speed),
            "torque_multiplier": float(gear.torque_multiplier),
            "min_engine_rpm": float(gear.min_engine_rpm),
            "max_engine_rpm": float(gear.max_engine_rpm),
            "source_record": gear.source_record,
        }
        for index, gear in enumerate(gears)
    ]
    result["final_gear_torque_decimation"] = float(gearbox.final_gear_torque_decimation)
    result.update(native_gear_payload(gearbox, max_forward_gears=max_forward_gears))
    return result


def gear_max_speed(gear, driven_radius):
    if float(gear.max_speed) > 0.0:
        return _finite(gear.max_speed, "gear maxSpeed")
    return speed_for_ratio(gear.ratio, gear.max_engine_rpm, driven_radius)
