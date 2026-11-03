from __future__ import annotations

import math
import re

from ....assetio.paths import (
    normalize_depot_path,
    split_source_tree_root,
    strip_json_suffix,
)
from ....assetio.transform_values import world_position_from_data
from ....assetio.values import cname_text, resource_path_text
from ....bartmoss.curve import simplify_piecewise_linear
from ....bartmoss.vehicle import cp77_spring_strength, cp77_tire_preview_friction
from ...model.vehicle.game_data import EntityVehicleData, VehicleGameData
from .camera import resolve_tpp_camera

_WHEEL_KEYS = ("LF", "RF", "LB", "RB")

# A generic tire friction profile for exports without wheel friction curvesets; exported curves replace it.
_BUILTIN_TIRE_TRACTION_CURVE = ((0.0, 0.0), (1.0, 1.0), (2.0, 1.0))
_BUILTIN_TIRE_CROSS_CURVE = ((0.0, 1.0), (2.0, 1.0))
_BUILTIN_TIRE_CURVE_SOURCE = "builtin:generic_preview"


def _builtin_tire_friction_config():
    traction = [list(point) for point in _BUILTIN_TIRE_TRACTION_CURVE]
    cross = [list(point) for point in _BUILTIN_TIRE_CROSS_CURVE]
    return {
        "tire_long_traction_front": [point[:] for point in traction],
        "tire_long_traction_rear": [point[:] for point in traction],
        "tire_lat_traction_front": [point[:] for point in traction],
        "tire_lat_traction_rear": [point[:] for point in traction],
        "tire_long_to_lat_front": [point[:] for point in cross],
        "tire_long_to_lat_rear": [point[:] for point in cross],
        "tire_lat_to_long_front": [point[:] for point in cross],
        "tire_lat_to_long_rear": [point[:] for point in cross],
        "traction_curve_source": "builtin",
        "source_friction_curve_set": _BUILTIN_TIRE_CURVE_SOURCE,
    }


def ensure_tire_friction_config(config):
    """Return config with a complete traction profile for preview"""
    result = dict(config) if isinstance(config, dict) else {}
    fallback = _builtin_tire_friction_config()
    result.setdefault("surface_friction_long_multiplier", 1.0)
    result.setdefault("surface_friction_lateral_multiplier", 1.0)

    primary = ("tire_long_traction_front", "tire_lat_traction_front")
    if not all(result.get(key) for key in primary):
        for key, value in fallback.items():
            if key.startswith("tire_") or key in (
                "traction_curve_source",
                "source_friction_curve_set",
            ):
                result[key] = (
                    [point[:] for point in value] if isinstance(value, list) else value
                )
        return result

    for rear_key, front_key in (
        ("tire_long_traction_rear", "tire_long_traction_front"),
        ("tire_lat_traction_rear", "tire_lat_traction_front"),
    ):
        if not result.get(rear_key):
            result[rear_key] = [list(point) for point in result[front_key]]

    for key in (
        "tire_long_to_lat_front",
        "tire_long_to_lat_rear",
        "tire_lat_to_long_front",
        "tire_lat_to_long_rear",
    ):
        if not result.get(key):
            result[key] = [list(point) for point in _BUILTIN_TIRE_CROSS_CURVE]
    result.setdefault("traction_curve_source", "exported")
    return result


def _entity_depot_path(value):
    """The depot path of an entity, given as one or as an exported file under a project's source tree"""
    path = strip_json_suffix(value)
    for tree in ("archive", "raw"):
        _root, relative = split_source_tree_root(path, tree)
        if relative:
            return normalize_depot_path(relative)
    return normalize_depot_path(path)


def _objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def entity_vehicle_data(document, entity_path=""):
    if not isinstance(document, dict):
        raise ValueError("Entity document must be a mapping")
    header = document.get("Header")
    archive_path = (
        str(header.get("ArchiveFileName", "") or "") if isinstance(header, dict) else ""
    )
    chassis = None
    vehicle_rig = None
    for value in _objects(document.get("Data", document)):
        value_type = value.get("$type")
        if value_type == "vehicleChassisComponent" and chassis is None:
            chassis = value
        elif (
            value_type == "entAnimatedComponent"
            and cname_text(value.get("name")).casefold() == "vehicle_rig"
            and vehicle_rig is None
        ):
            vehicle_rig = value
    if chassis is None:
        raise ValueError("Entity does not contain a vehicleChassisComponent")
    local_transform = chassis.get("localTransform")
    position = (
        world_position_from_data(local_transform.get("Position"))
        if isinstance(local_transform, dict)
        else (0.0, 0.0, 0.0)
    )
    vehicle_rig_transform = vehicle_rig.get("localTransform") if vehicle_rig else None
    return EntityVehicleData(
        entity_path=_entity_depot_path(entity_path or archive_path),
        chassis_collision_path=normalize_depot_path(
            resource_path_text(chassis.get("collisionResource"))
        ),
        chassis_local_position=position,
        chassis_local_transform=(
            dict(local_transform) if isinstance(local_transform, dict) else {}
        ),
        vehicle_rig_path=(
            normalize_depot_path(resource_path_text(vehicle_rig.get("rig")))
            if vehicle_rig
            else ""
        ),
        vehicle_rig_local_transform=(
            dict(vehicle_rig_transform)
            if isinstance(vehicle_rig_transform, dict)
            else {}
        ),
    )


def entity_appearance_names(document, appearance_name):
    """The entity's names for an imported appearance"""
    wanted = str(appearance_name or "").casefold()
    data = document.get("Data") if isinstance(document, dict) else None
    root = data.get("RootChunk") if isinstance(data, dict) else None
    if not wanted or not isinstance(root, dict):
        return ()
    names = []
    for entry in root.get("appearances") or ():
        if not isinstance(entry, dict):
            continue
        name = cname_text(entry.get("name"))
        if name and wanted in (
            name.casefold(),
            cname_text(entry.get("appearanceName")).casefold(),
        ):
            names.append(name)
    return tuple(dict.fromkeys(names))


def curve_entries(document):
    try:
        entries = document["Data"]["RootChunk"]["curves"]
    except (KeyError, TypeError) as error:
        raise ValueError("Curve document is missing Data.RootChunk.curves") from error
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name_value = entry.get("name")
        name = (
            str(name_value.get("$value", "") or "")
            if isinstance(name_value, dict)
            else str(name_value or "")
        )
        curve = entry.get("curve")
        if not name or not isinstance(curve, dict):
            continue
        points = []
        for element in curve.get("Elements", ()):
            if not isinstance(element, dict):
                continue
            try:
                point = float(element["Point"])
                value = float(element["Value"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(point) and math.isfinite(value):
                points.append((point, value))
        points.sort(key=lambda item: item[0])
        result[name] = {
            "interpolation": str(curve.get("InterpolationType", "Linear") or "Linear"),
            "points": tuple(points),
        }
    return result


def _number(mapping, key, *, positive=False, nonnegative=False):
    if not isinstance(mapping, dict) or key not in mapping:
        raise ValueError(f"Resolved vehicle data is missing {key}")
    try:
        value = float(mapping[key])
    except (TypeError, ValueError) as error:
        raise ValueError(f"Resolved vehicle field {key} is not numeric") from error
    if not math.isfinite(value):
        raise ValueError(f"Resolved vehicle field {key} must be finite")
    if positive and value <= 0.0:
        raise ValueError(f"Resolved vehicle field {key} must be positive")
    if nonnegative and value < 0.0:
        raise ValueError(f"Resolved vehicle field {key} must be nonnegative")
    return value


def _number_or(mapping, key, fallback, *, positive=False, nonnegative=False):
    if not isinstance(mapping, dict) or key not in mapping:
        value = float(fallback)
        if positive and value <= 0.0:
            raise ValueError(f"Fallback vehicle field {key} must be positive")
        if nonnegative and value < 0.0:
            raise ValueError(f"Fallback vehicle field {key} must be nonnegative")
        return value
    return _number(mapping, key, positive=positive, nonnegative=nonnegative)


def _vector(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if isinstance(value, dict):
        values = tuple(value.get(axis) for axis in ("x", "y", "z"))
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        values = tuple(value)
    else:
        raise ValueError(f"Resolved vehicle field {key} must contain XYZ values")
    result = tuple(float(component) for component in values)
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"Resolved vehicle field {key} must be finite")
    return result


def _number_list(mapping, key, count):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if value is None:
        raise ValueError(f"Resolved vehicle data is missing {key}")
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f"Resolved vehicle field {key} must contain {count} values")
    result = [float(item) for item in value]
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"Resolved vehicle field {key} must be finite")
    return result


def _link(database, value, current, label):
    try:
        return database.resolve_link(value, current)
    except (KeyError, TypeError) as error:
        raise ValueError(f"Could not resolve {label}: {error}") from error


def _record_reference(value):
    return str(value) if isinstance(value, str) and "." in value else ""


def _gear_records(database, engine, current):
    gears = engine.get("gears") if isinstance(engine, dict) else None
    if not isinstance(gears, list) or len(gears) < 2:
        raise ValueError("Resolved engine data must define reverse and forward gears")
    result = []
    for index, value in enumerate(gears):
        if isinstance(value, dict):
            result.append(value)
            continue
        result.append(_link(database, value, current, f"gear {index}"))
    return result


def _gearbox(engine, gear_records, max_rpm, driven_radius):
    """The gears' specs and ratios and the automatic box's up and down ratios"""
    gear_ratios = []
    gear_multipliers = []
    gear_specs = []
    auto_up = []
    auto_down = []
    gear_links = engine.get("gears") if isinstance(engine.get("gears"), list) else []
    for index, gear in enumerate(gear_records):
        min_speed = _number(gear, "minSpeed", nonnegative=True)
        max_speed = _number(gear, "maxSpeed", positive=True)
        gear_max_rpm = _number(gear, "maxEngineRPM", positive=True)
        gear_min_rpm = _number(gear, "minEngineRPM", nonnegative=True)
        ratio = gear_max_rpm * (2.0 * math.pi / 60.0) * driven_radius / max_speed
        signed_ratio = -ratio if index == 0 else ratio
        multiplier = _number_or(gear, "torqueMultiplier", 1.0, nonnegative=True)
        source_record = (
            _record_reference(gear_links[index]) if index < len(gear_links) else ""
        )
        gear_ratios.append(signed_ratio)
        gear_multipliers.append(multiplier)
        gear_specs.append(
            {
                "ratio": signed_ratio,
                "min_speed": min_speed,
                "max_speed": max_speed,
                "torque_multiplier": multiplier,
                "min_engine_rpm": gear_min_rpm,
                "max_engine_rpm": gear_max_rpm,
                "source_record": source_record,
            }
        )
        if index > 0:
            auto_up.append(min(max(gear_max_rpm / max_rpm, 0.01), 1.0))
            auto_down.append(min(max(gear_min_rpm / max_rpm, 0.0), 0.99))
    final_gear_torque_decimation = _number_or(
        engine, "finalGearTorqueDecimationScalor", 1.0, nonnegative=True
    )
    gear_multipliers[-1] *= final_gear_torque_decimation
    return (
        gear_specs,
        gear_ratios,
        gear_multipliers,
        auto_up,
        auto_down,
        final_gear_torque_decimation,
    )


def _torque_curve(engine, curve_loader):
    """The engine's gearCurvesPath and its torque curve's points"""
    path = str(engine.get("gearCurvesPath", "") or "")
    curve = _resolve_curve(curve_loader, path, "1")
    if not curve or not curve["points"]:
        return path, []
    return path, [
        list(point) for point in simplify_piecewise_linear(curve["points"], 8)
    ]


def _drive_layout(wheel_flags):
    flags = [bool(wheel_flags[key].get("isDrive", False)) for key in _WHEEL_KEYS]
    front = flags[0] or flags[1]
    rear = flags[2] or flags[3]
    if front and rear:
        return "AWD"
    if front:
        return "FWD"
    if rear:
        return "RWD"
    raise ValueError("Resolved wheel setup does not define driven wheels")


def _friction(preset):
    coefficient = _number(preset, "tireFrictionCoef", positive=True)
    longitudinal = _number(preset, "frictionMulLongitudinal", nonnegative=True)
    lateral = _number(preset, "frictionMulLateral", nonnegative=True)
    return cp77_tire_preview_friction(coefficient, longitudinal, lateral)


def _suspension_compression(preset):
    logical = _number_or(
        preset, "logicalSuspensionCompressionLength", 0.0, nonnegative=True
    )
    if logical > 0.0:
        return logical
    return _number_or(
        preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
    )


def _resolve_curve(curve_loader, path, name):
    if not path or curve_loader is None:
        return None
    document = curve_loader(path)
    if document is None:
        return None
    return curve_entries(document).get(name)


def _surface_friction_config(database, drive, current, curve_loader):
    result = {
        "surface_friction_long_multiplier": 1.0,
        "surface_friction_lateral_multiplier": 1.0,
        **_builtin_tire_friction_config(),
    }
    friction_map_ref = (
        drive.get("wheelsFrictionMap") if isinstance(drive, dict) else None
    )
    if not friction_map_ref:
        return result
    try:
        friction_map = _link(database, friction_map_ref, current, "wheels friction map")
        preset_ref = (
            friction_map.get("defaultFrictionPreset")
            if isinstance(friction_map, dict)
            else None
        )
        preset = _link(database, preset_ref, current, "default wheel friction preset")
    except ValueError:
        # The friction-map records are optional for authoring preview. Keep the
        # bundled generic profile rather than turning normal exports into an
        # additional TweakDB dependency.
        return result

    result["surface_friction_long_multiplier"] = _number_or(
        preset, "frictionLongMultiplier", 1.0, nonnegative=True
    )
    result["surface_friction_lateral_multiplier"] = _number_or(
        preset, "frictionLatMultiplier", 1.0, nonnegative=True
    )
    raw_curve_path = (
        preset.get("frictionCurveSet") if isinstance(preset, dict) else None
    )
    curve_path = normalize_depot_path(
        raw_curve_path
        if isinstance(raw_curve_path, str)
        else resource_path_text(raw_curve_path)
    )
    if not curve_path:
        return result

    curve_names = {
        "tire_long_traction_front": "long_speed_diff_to_traction",
        "tire_long_traction_rear": "long_speed_diff_to_traction_rear",
        "tire_lat_traction_front": "lat_speed_diff_to_traction",
        "tire_lat_traction_rear": "lat_speed_diff_to_traction_rear",
        "tire_long_to_lat_front": "long_to_lat_speed_coeff",
        "tire_long_to_lat_rear": "long_to_lat_speed_coeff_rear",
        "tire_lat_to_long_front": "lat_to_long_speed_coeff",
        "tire_lat_to_long_rear": "lat_to_long_speed_coeff_rear",
    }
    loaded = {
        key: _positive_input_curve(_resolve_curve(curve_loader, curve_path, name))
        for key, name in curve_names.items()
    }
    if not loaded["tire_long_traction_front"] or not loaded["tire_lat_traction_front"]:
        return result

    for rear_key, front_key in (
        ("tire_long_traction_rear", "tire_long_traction_front"),
        ("tire_lat_traction_rear", "tire_lat_traction_front"),
        ("tire_long_to_lat_rear", "tire_long_to_lat_front"),
        ("tire_lat_to_long_rear", "tire_lat_to_long_front"),
    ):
        if not loaded[rear_key]:
            loaded[rear_key] = [list(point) for point in loaded[front_key]]

    # Cross-influence curves are optional in vehicle records. A missing curve
    # is a multiplier of 1, so it needs no export.
    for key in (
        "tire_long_to_lat_front",
        "tire_long_to_lat_rear",
        "tire_lat_to_long_front",
        "tire_lat_to_long_rear",
    ):
        if not loaded[key]:
            loaded[key] = [list(point) for point in _BUILTIN_TIRE_CROSS_CURVE]

    result.update(loaded)
    result["source_friction_curve_set"] = curve_path
    result["traction_curve_source"] = "exported"
    return result


def _scaled_speed_curve(curve, top_speed, max_points=None, *, positive_only=False):
    if not curve or not curve["points"]:
        return []
    points = [
        (point * top_speed, value)
        for point, value in curve["points"]
        if (not positive_only or point >= 0.0) and math.isfinite(value)
    ]
    if not points:
        return []
    if positive_only and points[0][0] > 0.0:
        points.insert(0, (0.0, points[0][1]))
    if max_points is not None and len(points) > max_points:
        points = simplify_piecewise_linear(points, max_points)
    return [list(point) for point in points]


def _positive_input_curve(curve):
    if not curve or not curve["points"]:
        return []
    return [
        [point, value]
        for point, value in curve["points"]
        if point >= 0.0 and math.isfinite(value)
    ]


_WHEEL_PRESET_FIELDS = (
    "tireFrictionCoef",
    "extremeCompressionEventScalor",
    "frictionMulLateral",
    "frictionMulLongitudinal",
    "logicalSuspensionCompressionLength",
    "mass",
    "maxBrakingTorque",
    "springBoundDampingLowRate",
    "springDamping",
    "springDampingHighRateCompression",
    "springDampingLowRateCompression",
    "springReboundDamping",
    "springReboundDampingLowRate",
    "springStiffness",
    "swaybarStiffness",
    "swaybarLengthScalar",
    "swaybarDisplacementLimit",
    "tenderSpringLength",
    "tireLateralSlipEffectsMul",
    "tireLongitudinalSlipEffectsMul",
    "tireRollingResistanceCoef",
    "visualSuspensionCompressionLength",
    "visualSuspensionDroop",
    "wheelsVerticalOffset",
)


def _wheel_preset_snapshot(preset):
    if not isinstance(preset, dict):
        return {}
    result = {}
    for key in _WHEEL_PRESET_FIELDS:
        if key not in preset:
            continue
        try:
            value = float(preset[key])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            result[key] = value
    return result


def _resolve_car_game_data(
    database,
    record_id,
    *,
    curve_loader=None,
):
    record = database.resolve(record_id)
    vehicle = record.fields
    dimensions = _link(
        database, vehicle.get("vehWheelDimensionsSetup"), record_id, "wheel dimensions"
    )
    drive = _link(database, vehicle.get("vehDriveModelData"), record_id, "drive model")
    engine = _link(database, vehicle.get("vehEngineData"), record_id, "engine data")
    wheel_setup = _link(
        database, drive.get("wheelSetup"), record_id, "wheel driving setup"
    )
    front_dimensions = _link(
        database, dimensions.get("frontPreset"), record_id, "front wheel dimensions"
    )
    rear_dimensions = _link(
        database, dimensions.get("backPreset"), record_id, "rear wheel dimensions"
    )
    front_preset = _link(
        database, wheel_setup.get("frontPreset"), record_id, "front wheel preset"
    )
    rear_preset = _link(
        database, wheel_setup.get("backPreset"), record_id, "rear wheel preset"
    )

    wheel_flags = {
        key: database.link_fields(wheel_setup.get(key), record_id)
        for key in _WHEEL_KEYS
    }
    layout = _drive_layout(wheel_flags)
    front_radius = _number(front_dimensions, "tireRadius", positive=True)
    rear_radius = _number(rear_dimensions, "tireRadius", positive=True)
    front_rim_radius = _number(front_dimensions, "rimRadius", positive=True)
    rear_rim_radius = _number(rear_dimensions, "rimRadius", positive=True)
    front_width = _number(front_dimensions, "tireWidth", positive=True)
    rear_width = _number(rear_dimensions, "tireWidth", positive=True)
    front_mass = _number(front_preset, "mass", positive=True)
    rear_mass = _number(rear_preset, "mass", positive=True)
    wheel_radii = [front_radius, front_radius, rear_radius, rear_radius]
    wheel_rim_radii = [
        front_rim_radius,
        front_rim_radius,
        rear_rim_radius,
        rear_rim_radius,
    ]
    wheel_widths = [front_width, front_width, rear_width, rear_width]
    wheel_masses = [front_mass, front_mass, rear_mass, rear_mass]
    wheel_moi = [
        0.5 * mass * radius * radius for mass, radius in zip(wheel_masses, wheel_radii)
    ]

    handbrake = _number_or(drive, "handbrakeBrakingTorque", 2500.0, nonnegative=True)
    max_steer_degrees = _number_or(drive, "maxWheelTurnDeg", 30.0, positive=True)
    max_steer = math.radians(max_steer_degrees)
    wheel_turn_add = _number_or(drive, "wheelTurnMaxAddPerSecond", 90.0, positive=True)
    wheel_turn_sub = _number_or(drive, "wheelTurnMaxSubPerSecond", 90.0, positive=True)
    brake_torques = []
    handbrake_torques = []
    steer_angles = []
    for key in _WHEEL_KEYS:
        axle_preset = front_preset if key in {"LF", "RF"} else rear_preset
        flags = wheel_flags[key]
        brake_torques.append(
            _number(axle_preset, "maxBrakingTorque", nonnegative=True)
            if flags.get("isMainBrake", False)
            else 0.0
        )
        handbrake_torques.append(handbrake if flags.get("isHandBrake", False) else 0.0)
        steer_angles.append(max_steer if key in {"LF", "RF"} else 0.0)

    front_compression = _suspension_compression(front_preset)
    rear_compression = _suspension_compression(rear_preset)
    front_droop = _number_or(
        front_preset, "visualSuspensionDroop", 0.1, nonnegative=True
    )
    rear_droop = _number_or(rear_preset, "visualSuspensionDroop", 0.1, nonnegative=True)
    front_spring_rate = _number(front_preset, "springStiffness", positive=True)
    rear_spring_rate = _number(rear_preset, "springStiffness", positive=True)
    spring_rates = [
        front_spring_rate,
        front_spring_rate,
        rear_spring_rate,
        rear_spring_rate,
    ]
    spring_strengths = [
        cp77_spring_strength(front_spring_rate, front_compression + front_droop),
        cp77_spring_strength(front_spring_rate, front_compression + front_droop),
        cp77_spring_strength(rear_spring_rate, rear_compression + rear_droop),
        cp77_spring_strength(rear_spring_rate, rear_compression + rear_droop),
    ]
    front_damping = _number(front_preset, "springDamping", nonnegative=True)
    rear_damping = _number(rear_preset, "springDamping", nonnegative=True)
    front_rebound = _number_or(
        front_preset, "springReboundDamping", 0.0, nonnegative=True
    )
    rear_rebound = _number_or(
        rear_preset, "springReboundDamping", 0.0, nonnegative=True
    )
    damper_rates = [
        0.5 * (front_damping + front_rebound),
        0.5 * (front_damping + front_rebound),
        0.5 * (rear_damping + rear_rebound),
        0.5 * (rear_damping + rear_rebound),
    ]

    front_offset = _number_or(front_dimensions, "wheelOffset", 0.0)
    rear_offset = _number_or(rear_dimensions, "wheelOffset", 0.0)
    front_vertical = _number_or(front_preset, "wheelsVerticalOffset", 0.0)
    rear_vertical = _number_or(rear_preset, "wheelsVerticalOffset", 0.0)
    wheel_center_offsets = [
        [-front_offset, 0.0, front_vertical],
        [front_offset, 0.0, front_vertical],
        [-rear_offset, 0.0, rear_vertical],
        [rear_offset, 0.0, rear_vertical],
    ]
    wheel_vertical_offsets = [
        front_vertical,
        front_vertical,
        rear_vertical,
        rear_vertical,
    ]

    max_rpm = _number(engine, "maxRPM", positive=True)
    max_omega = max_rpm * (2.0 * math.pi / 60.0)
    engine_peak_torque = _number(engine, "engineMaxTorque", positive=True)
    gear_records = _gear_records(database, engine, record_id)
    driven_radius = (
        rear_radius
        if layout == "RWD"
        else front_radius
        if layout == "FWD"
        else 0.5 * (front_radius + rear_radius)
    )
    (
        gear_specs,
        gear_ratios,
        gear_multipliers,
        auto_up,
        auto_down,
        final_gear_torque_decimation,
    ) = _gearbox(engine, gear_records, max_rpm, driven_radius)

    warnings = [
        "Dynamic weight transfer, downforce, slope load, burnout modifiers and surface switching are not reproduced by the preview",
    ]
    inertia = None
    if "momentOfInertia" in drive:
        inertia = list(_vector(drive, "momentOfInertia"))
    else:
        warnings.append(
            "Drive data has no inertia tensor; PhysX will calculate it from the fitted chassis"
        )
    torque_curve_path, torque_points = _torque_curve(engine, curve_loader)
    if torque_curve_path and not torque_points:
        warnings.append(f"Engine torque curve was not found: {torque_curve_path}")

    vehicle_curve_path = str(vehicle.get("curvesPath", "") or "")
    steer_curve = _resolve_curve(
        curve_loader, vehicle_curve_path, "speed_to_wheel_max_turn"
    )
    top_speed = max(
        _number(gear, "maxSpeed", positive=True) for gear in gear_records[1:]
    )
    steer_points = _scaled_speed_curve(steer_curve, top_speed, 8, positive_only=True)
    if len(steer_points) < 2:
        steer_points = []
    if vehicle_curve_path and not steer_points:
        warnings.append(f"Vehicle steering curve was not found: {vehicle_curve_path}")

    config = {
        "vehicle_kind": "CAR",
        "source_dimensions_record": _record_reference(
            vehicle.get("vehWheelDimensionsSetup")
        ),
        "source_drive_record": _record_reference(vehicle.get("vehDriveModelData")),
        "source_engine_record": _record_reference(vehicle.get("vehEngineData")),
        "source_wheel_setup_record": _record_reference(drive.get("wheelSetup")),
        "source_front_dimensions_record": _record_reference(
            dimensions.get("frontPreset")
        ),
        "source_rear_dimensions_record": _record_reference(
            dimensions.get("backPreset")
        ),
        "source_front_wheel_record": _record_reference(wheel_setup.get("frontPreset")),
        "source_rear_wheel_record": _record_reference(wheel_setup.get("backPreset")),
        "cp77_front_wheel_preset": _wheel_preset_snapshot(front_preset),
        "cp77_rear_wheel_preset": _wheel_preset_snapshot(rear_preset),
        "wheel_flags": [dict(wheel_flags[key]) for key in _WHEEL_KEYS],
        "chassis_mass": _number(drive, "chassis_mass", positive=True),
        "total_mass": _number_or(
            drive,
            "total_mass",
            _number(drive, "chassis_mass", positive=True),
            positive=True,
        ),
        "chassis_cm_source": list(_vector(drive, "center_of_mass_offset")),
        "air_resistance_factor": _number_or(
            drive, "airResistanceFactor", 1.0, nonnegative=True
        ),
        "braking_friction_factor": _number_or(
            drive, "brakingFrictionFactor", 1.0, nonnegative=True
        ),
        "turning_roll_factor": _number_or(
            drive, "turningRollFactor", 1.0, nonnegative=True
        ),
        "anti_swaybar_damping_scalar": _number_or(
            drive, "antiSwaybarDampingScalor", 1.0, nonnegative=True
        ),
        "smooth_wheel_contact_increase_time": _number_or(
            drive, "smoothWheelContactIncreseTime", 0.1, nonnegative=True
        ),
        "smooth_wheel_contact_decrease_time": _number_or(
            drive, "smoothWheelContactDecreaseTime", 0.1, nonnegative=True
        ),
        "wheel_radii": wheel_radii,
        "wheel_rim_radii": wheel_rim_radii,
        "wheel_widths": wheel_widths,
        "wheel_masses": wheel_masses,
        "wheel_moi_values": wheel_moi,
        "wheel_center_offsets": wheel_center_offsets,
        "wheel_dimension_offsets": [front_offset, rear_offset],
        "wheel_vertical_offsets": wheel_vertical_offsets,
        "brake_torques": brake_torques,
        "handbrake_torques": handbrake_torques,
        "steer_angles": steer_angles,
        "suspension_compressions": [
            front_compression,
            front_compression,
            rear_compression,
            rear_compression,
        ],
        "suspension_visual_compressions": [
            _number_or(
                front_preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
            ),
            _number_or(
                front_preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
            ),
            _number_or(
                rear_preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
            ),
            _number_or(
                rear_preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
            ),
        ],
        "suspension_droops": [front_droop, front_droop, rear_droop, rear_droop],
        "suspension_spring_rates_kg_mm": spring_rates,
        "suspension_spring_strengths": spring_strengths,
        "suspension_damper_rates": damper_rates,
        "suspension_compression_damper_rates": [
            front_damping,
            front_damping,
            rear_damping,
            rear_damping,
        ],
        "suspension_rebound_damper_rates": [
            front_rebound,
            front_rebound,
            rear_rebound,
            rear_rebound,
        ],
        "tire_friction_coefficients": [
            _number(front_preset, "tireFrictionCoef", positive=True),
            _number(front_preset, "tireFrictionCoef", positive=True),
            _number(rear_preset, "tireFrictionCoef", positive=True),
            _number(rear_preset, "tireFrictionCoef", positive=True),
        ],
        "tire_friction_longitudinal_multipliers": [
            _number(front_preset, "frictionMulLongitudinal", nonnegative=True),
            _number(front_preset, "frictionMulLongitudinal", nonnegative=True),
            _number(rear_preset, "frictionMulLongitudinal", nonnegative=True),
            _number(rear_preset, "frictionMulLongitudinal", nonnegative=True),
        ],
        "tire_friction_lateral_multipliers": [
            _number(front_preset, "frictionMulLateral", nonnegative=True),
            _number(front_preset, "frictionMulLateral", nonnegative=True),
            _number(rear_preset, "frictionMulLateral", nonnegative=True),
            _number(rear_preset, "frictionMulLateral", nonnegative=True),
        ],
        "tire_frictions": [
            _friction(front_preset),
            _friction(front_preset),
            _friction(rear_preset),
            _friction(rear_preset),
        ],
        "differential_type": layout,
        "engine_peak_torque": engine_peak_torque,
        "engine_max_omega": max_omega,
        "engine_moi": _number(engine, "flyWheelMomentOfInertia", positive=True),
        "engine_damping_rate": _number(engine, "resistanceTorque", nonnegative=True)
        / max_omega,
        "engine_torque_curve": torque_points,
        "gears": gear_specs,
        "gear_ratios": gear_ratios,
        "gear_torque_multipliers": gear_multipliers,
        "final_gear_torque_decimation": final_gear_torque_decimation,
        "gear_switch_time": _number(engine, "gearChangeTime", nonnegative=True),
        "gear_change_cooldown": _number_or(
            engine, "gearChangeCooldown", 0.0, nonnegative=True
        ),
        "autobox_up_ratios": auto_up,
        "autobox_down_ratios": auto_down,
        "steer_vs_speed": steer_points,
        "steer_rise_rate": wheel_turn_add / max_steer_degrees,
        "steer_fall_rate": wheel_turn_sub / max_steer_degrees,
        "wheel_turn_add_rate": wheel_turn_add,
        "wheel_turn_sub_rate": wheel_turn_sub,
        "engine_curve_path": normalize_depot_path(torque_curve_path),
        "vehicle_curve_path": normalize_depot_path(vehicle_curve_path),
    }
    config.update(_surface_friction_config(database, drive, record_id, curve_loader))
    config["slip_ratio_min_speed_threshold"] = _number_or(
        drive, "slipRatioMinSpeedThreshold", -1.0
    )
    config["slip_ratio_curve_scale"] = _number_or(
        drive, "slipRatioCurveScale", 1.0, nonnegative=True
    )
    config["slip_angle_min_speed_threshold"] = _number_or(
        drive, "slipAngleMinSpeedThreshold", -1.0
    )
    config["slip_angle_curve_scale"] = _number_or(
        drive, "slipAngleCurveScale", 1.0, nonnegative=True
    )
    config["turning_roll_factor_weak_contact_mul"] = _number_or(
        drive, "turningRollFactorWeakContactMul", 1.0, nonnegative=True
    )
    config["turning_roll_factor_weak_contact_threshold_min"] = _number_or(
        drive, "turningRollFactorWeakContactThresholdMin", 0.9, nonnegative=True
    )
    config["turning_roll_factor_weak_contact_threshold_max"] = _number_or(
        drive, "turningRollFactorWeakContactThresholdMax", 0.6, nonnegative=True
    )
    config["rolling_resistance_factor"] = _number_or(
        drive, "rollingResistanceFactor", 0.0095, nonnegative=True
    )
    if inertia is not None:
        config["chassis_inertia"] = inertia
    config["tpp_camera"] = resolve_tpp_camera(database, vehicle, record_id)
    return VehicleGameData(
        record_id,
        config,
        record.sources,
        tuple(warnings),
    )


def _resolve_bike_game_data(database, record_id, *, curve_loader=None):
    record = database.resolve(record_id)
    vehicle = record.fields
    dimensions = _link(
        database, vehicle.get("vehWheelDimensionsSetup"), record_id, "wheel dimensions"
    )
    drive = _link(
        database, vehicle.get("bikeDriveModelData"), record_id, "bike drive model"
    )
    engine = _link(database, vehicle.get("vehEngineData"), record_id, "engine data")
    wheel_setup = _link(
        database, drive.get("wheelSetup"), record_id, "wheel driving setup"
    )
    front_dimensions = _link(
        database, dimensions.get("frontPreset"), record_id, "front wheel dimensions"
    )
    rear_dimensions = _link(
        database, dimensions.get("backPreset"), record_id, "rear wheel dimensions"
    )
    front_preset = _link(
        database, wheel_setup.get("frontPreset"), record_id, "front wheel preset"
    )
    rear_preset = _link(
        database, wheel_setup.get("backPreset"), record_id, "rear wheel preset"
    )

    radii = [
        _number(front_dimensions, "tireRadius", positive=True),
        _number(rear_dimensions, "tireRadius", positive=True),
    ]
    rim_radii = [
        _number(front_dimensions, "rimRadius", positive=True),
        _number(rear_dimensions, "rimRadius", positive=True),
    ]
    widths = [
        _number(front_dimensions, "tireWidth", positive=True),
        _number(rear_dimensions, "tireWidth", positive=True),
    ]
    masses = [
        _number(front_preset, "mass", positive=True),
        _number(rear_preset, "mass", positive=True),
    ]
    flags = [
        database.link_fields(wheel_setup.get("F"), record_id),
        database.link_fields(wheel_setup.get("B"), record_id),
    ]
    driven = [
        index for index, item in enumerate(flags) if bool(item.get("isDrive", False))
    ]
    if len(driven) != 1:
        raise ValueError(
            "Resolved bike wheel setup must define exactly one driven wheel"
        )

    handbrake = _number_or(drive, "handbrakeBrakingTorque", 2500.0, nonnegative=True)
    max_steer_degrees = _number_or(drive, "maxWheelTurnDeg", 30.0, positive=True)
    max_steer = math.radians(max_steer_degrees)
    wheel_turn_add = _number_or(drive, "wheelTurnMaxAddPerSecond", 90.0, positive=True)
    wheel_turn_sub = _number_or(drive, "wheelTurnMaxSubPerSecond", 90.0, positive=True)
    presets = (front_preset, rear_preset)
    brake_torques = [
        _number(preset, "maxBrakingTorque", nonnegative=True)
        if flag.get("isMainBrake", False)
        else 0.0
        for preset, flag in zip(presets, flags)
    ]
    handbrake_torques = [
        handbrake if flag.get("isHandBrake", False) else 0.0 for flag in flags
    ]

    max_rpm = _number(engine, "maxRPM", positive=True)
    max_omega = max_rpm * (2.0 * math.pi / 60.0)
    gear_records = _gear_records(database, engine, record_id)
    top_speed = max(
        _number(gear, "maxSpeed", positive=True) for gear in gear_records[1:]
    )
    (
        gear_specs,
        gear_ratios,
        gear_multipliers,
        auto_up,
        auto_down,
        final_gear_torque_decimation,
    ) = _gearbox(engine, gear_records, max_rpm, radii[driven[0]])

    torque_curve_path, torque_points = _torque_curve(engine, curve_loader)
    vehicle_curve_path = str(vehicle.get("curvesPath", "") or "")
    steer_curve = _resolve_curve(
        curve_loader, vehicle_curve_path, "speed_to_wheel_max_turn"
    )
    steer_points = _scaled_speed_curve(steer_curve, top_speed, 8, positive_only=True)
    if len(steer_points) < 2:
        steer_points = []
    bike_curve_path = str(drive.get("bikeCurvesPath", "") or "")
    speed_to_tilt = _scaled_speed_curve(
        _resolve_curve(curve_loader, bike_curve_path, "speed_to_tilt"),
        top_speed,
    )
    input_to_tilt = _positive_input_curve(
        _resolve_curve(curve_loader, bike_curve_path, "input_to_tilt")
    )
    speed_to_tilt_speed = _scaled_speed_curve(
        _resolve_curve(curve_loader, bike_curve_path, "speed_to_tilt_speed"),
        top_speed,
        positive_only=True,
    )

    front_damping = _number(front_preset, "springDamping", nonnegative=True)
    rear_damping = _number(rear_preset, "springDamping", nonnegative=True)
    front_rebound = _number_or(
        front_preset, "springReboundDamping", 0.0, nonnegative=True
    )
    rear_rebound = _number_or(
        rear_preset, "springReboundDamping", 0.0, nonnegative=True
    )
    tire_coefficients = [
        _number(front_preset, "tireFrictionCoef", positive=True),
        _number(rear_preset, "tireFrictionCoef", positive=True),
    ]
    tire_longitudinal = [
        _number(front_preset, "frictionMulLongitudinal", nonnegative=True),
        _number(rear_preset, "frictionMulLongitudinal", nonnegative=True),
    ]
    tire_lateral = [
        _number(front_preset, "frictionMulLateral", nonnegative=True),
        _number(rear_preset, "frictionMulLateral", nonnegative=True),
    ]
    warnings = [
        "Dynamic weight transfer, downforce, slope load, burnout modifiers and surface switching are not reproduced by the preview",
    ]
    for path, points, label in (
        (torque_curve_path, torque_points, "engine torque"),
        (vehicle_curve_path, steer_points, "vehicle steering"),
        (bike_curve_path, speed_to_tilt, "bike speed-to-tilt"),
        (bike_curve_path, input_to_tilt, "bike input-to-tilt"),
        (bike_curve_path, speed_to_tilt_speed, "bike tilt-speed"),
    ):
        if path and not points:
            warnings.append(f"The {label} curve was not found: {path}")

    config = {
        "vehicle_kind": "BIKE",
        "source_dimensions_record": _record_reference(
            vehicle.get("vehWheelDimensionsSetup")
        ),
        "source_drive_record": _record_reference(vehicle.get("bikeDriveModelData")),
        "source_engine_record": _record_reference(vehicle.get("vehEngineData")),
        "source_wheel_setup_record": _record_reference(drive.get("wheelSetup")),
        "source_front_dimensions_record": _record_reference(
            dimensions.get("frontPreset")
        ),
        "source_rear_dimensions_record": _record_reference(
            dimensions.get("backPreset")
        ),
        "source_front_wheel_record": _record_reference(wheel_setup.get("frontPreset")),
        "source_rear_wheel_record": _record_reference(wheel_setup.get("backPreset")),
        "cp77_front_wheel_preset": _wheel_preset_snapshot(front_preset),
        "cp77_rear_wheel_preset": _wheel_preset_snapshot(rear_preset),
        "wheel_flags": [dict(flags[0]), dict(flags[1])],
        "chassis_mass": _number(drive, "chassis_mass", positive=True),
        "total_mass": _number_or(
            drive,
            "total_mass",
            _number(drive, "chassis_mass", positive=True),
            positive=True,
        ),
        "chassis_cm_source": list(_vector(drive, "center_of_mass_offset")),
        "air_resistance_factor": _number_or(
            drive, "airResistanceFactor", 1.0, nonnegative=True
        ),
        "braking_friction_factor": _number_or(
            drive, "brakingFrictionFactor", 1.0, nonnegative=True
        ),
        "turning_roll_factor": _number_or(
            drive, "turningRollFactor", 1.0, nonnegative=True
        ),
        "anti_swaybar_damping_scalar": _number_or(
            drive, "antiSwaybarDampingScalor", 1.0, nonnegative=True
        ),
        "smooth_wheel_contact_increase_time": _number_or(
            drive, "smoothWheelContactIncreseTime", 0.1, nonnegative=True
        ),
        "smooth_wheel_contact_decrease_time": _number_or(
            drive, "smoothWheelContactDecreaseTime", 0.1, nonnegative=True
        ),
        "chassis_inertia": list(_vector(drive, "momentOfInertia")),
        "wheel_radii": radii,
        "wheel_rim_radii": rim_radii,
        "wheel_widths": widths,
        "wheel_masses": masses,
        "wheel_moi_values": [
            0.5 * mass * radius * radius for mass, radius in zip(masses, radii)
        ],
        "wheel_center_offsets": [
            [0.0, 0.0, _number_or(front_preset, "wheelsVerticalOffset", 0.0)],
            [0.0, 0.0, _number_or(rear_preset, "wheelsVerticalOffset", 0.0)],
        ],
        "wheel_dimension_offsets": [
            _number_or(front_dimensions, "wheelOffset", 0.0),
            _number_or(rear_dimensions, "wheelOffset", 0.0),
        ],
        "wheel_vertical_offsets": [
            _number_or(front_preset, "wheelsVerticalOffset", 0.0),
            _number_or(rear_preset, "wheelsVerticalOffset", 0.0),
        ],
        "brake_torques": brake_torques,
        "handbrake_torques": handbrake_torques,
        "steer_angles": [max_steer, 0.0],
        "suspension_compressions": [
            _suspension_compression(front_preset),
            _suspension_compression(rear_preset),
        ],
        "suspension_visual_compressions": [
            _number_or(
                front_preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
            ),
            _number_or(
                rear_preset, "visualSuspensionCompressionLength", 0.0, nonnegative=True
            ),
        ],
        "suspension_droops": [
            _number_or(front_preset, "visualSuspensionDroop", 0.1, nonnegative=True),
            _number_or(rear_preset, "visualSuspensionDroop", 0.1, nonnegative=True),
        ],
        "suspension_spring_rates_kg_mm": [
            _number(front_preset, "springStiffness", positive=True),
            _number(rear_preset, "springStiffness", positive=True),
        ],
        "suspension_spring_strengths": [
            cp77_spring_strength(
                _number(front_preset, "springStiffness", positive=True),
                _suspension_compression(front_preset)
                + _number_or(
                    front_preset, "visualSuspensionDroop", 0.1, nonnegative=True
                ),
            ),
            cp77_spring_strength(
                _number(rear_preset, "springStiffness", positive=True),
                _suspension_compression(rear_preset)
                + _number_or(
                    rear_preset, "visualSuspensionDroop", 0.1, nonnegative=True
                ),
            ),
        ],
        "suspension_damper_rates": [
            0.5 * (front_damping + front_rebound),
            0.5 * (rear_damping + rear_rebound),
        ],
        "suspension_compression_damper_rates": [front_damping, rear_damping],
        "suspension_rebound_damper_rates": [front_rebound, rear_rebound],
        "tire_friction_coefficients": tire_coefficients,
        "tire_friction_longitudinal_multipliers": tire_longitudinal,
        "tire_friction_lateral_multipliers": tire_lateral,
        "tire_frictions": [
            cp77_tire_preview_friction(coefficient, longitudinal, lateral)
            for coefficient, longitudinal, lateral in zip(
                tire_coefficients, tire_longitudinal, tire_lateral
            )
        ],
        "differential_type": "BIKE_FWD" if driven[0] == 0 else "BIKE_RWD",
        "engine_peak_torque": _number(engine, "engineMaxTorque", positive=True),
        "engine_max_omega": max_omega,
        "engine_moi": _number(engine, "flyWheelMomentOfInertia", positive=True),
        "engine_damping_rate": _number(engine, "resistanceTorque", nonnegative=True)
        / max_omega,
        "engine_torque_curve": torque_points,
        "gears": gear_specs,
        "gear_ratios": gear_ratios,
        "gear_torque_multipliers": gear_multipliers,
        "final_gear_torque_decimation": final_gear_torque_decimation,
        "gear_switch_time": _number(engine, "gearChangeTime", nonnegative=True),
        "gear_change_cooldown": _number_or(
            engine, "gearChangeCooldown", 0.0, nonnegative=True
        ),
        "autobox_up_ratios": auto_up,
        "autobox_down_ratios": auto_down,
        "steer_vs_speed": steer_points,
        "steer_rise_rate": wheel_turn_add / max_steer_degrees,
        "steer_fall_rate": wheel_turn_sub / max_steer_degrees,
        "wheel_turn_add_rate": wheel_turn_add,
        "wheel_turn_sub_rate": wheel_turn_sub,
        "engine_curve_path": normalize_depot_path(torque_curve_path),
        "vehicle_curve_path": normalize_depot_path(vehicle_curve_path),
        "bike_curve_path": normalize_depot_path(bike_curve_path),
        "bike_tilt_pid": _number_list(drive, "bikeTiltPID", 3),
        "bike_max_lean_angle": math.radians(
            _number(drive, "bikeMaxTilt", positive=True)
        ),
        "bike_tilt_speed": math.radians(_number(drive, "bikeTiltSpeed", positive=True)),
        "bike_tilt_return_speed": math.radians(
            _number(drive, "bikeTiltReturnSpeed", positive=True)
        ),
        "bike_tilt_custom_speed": math.radians(
            _number(drive, "bikeTiltCustomSpeed", positive=True)
        ),
        "bike_max_com_long_offset": _number_or(
            drive, "bikeMaxCOMLongOffset", 0.75, nonnegative=True
        ),
        "bike_min_com_long_offset": _number_or(
            drive, "bikeMinCOMLongOffset", 0.75, nonnegative=True
        ),
        "bike_com_offset_damp_factor": _number_or(
            drive, "bikeCOMOffsetDampFactor", 0.25, nonnegative=True
        ),
        "bike_speed_to_tilt": speed_to_tilt,
        "bike_input_to_tilt": input_to_tilt,
        "bike_speed_to_tilt_speed": speed_to_tilt_speed,
    }
    config.update(_surface_friction_config(database, drive, record_id, curve_loader))
    config["slip_ratio_min_speed_threshold"] = _number_or(
        drive, "slipRatioMinSpeedThreshold", -1.0
    )
    config["slip_ratio_curve_scale"] = _number_or(
        drive, "slipRatioCurveScale", 1.0, nonnegative=True
    )
    config["slip_angle_min_speed_threshold"] = _number_or(
        drive, "slipAngleMinSpeedThreshold", -1.0
    )
    config["slip_angle_curve_scale"] = _number_or(
        drive, "slipAngleCurveScale", 1.0, nonnegative=True
    )
    config["turning_roll_factor_weak_contact_mul"] = _number_or(
        drive, "turningRollFactorWeakContactMul", 1.0, nonnegative=True
    )
    config["turning_roll_factor_weak_contact_threshold_min"] = _number_or(
        drive, "turningRollFactorWeakContactThresholdMin", 0.9, nonnegative=True
    )
    config["turning_roll_factor_weak_contact_threshold_max"] = _number_or(
        drive, "turningRollFactorWeakContactThresholdMax", 0.6, nonnegative=True
    )
    config["rolling_resistance_factor"] = _number_or(
        drive, "rollingResistanceFactor", 0.0095, nonnegative=True
    )
    config["tpp_camera"] = resolve_tpp_camera(database, vehicle, record_id)
    return VehicleGameData(
        record_id,
        config,
        record.sources,
        tuple(warnings),
    )


PLAYER_VEHICLE_LIST = "Vehicle.vehicle_list"
_VEHICLE_CLASS_TOKEN = re.compile(r"(sport|standard|sportbike|utility|special)\d*")


def vehicle_record_kind(record):
    """'BIKE' for a resolved vehicle record that has a bike drive model, else 'CAR'"""
    return "BIKE" if "bikeDriveModelData" in record.fields else "CAR"


def vehicle_record_label(record_id):
    """A readable name for a vehicle record"""
    name = str(record_id or "").rsplit(".", 1)[-1]
    parts = [part for part in name.split("_") if part]
    if parts[:1] == ["v"]:
        parts = parts[1:]
    if parts and _VEHICLE_CLASS_TOKEN.fullmatch(parts[0]):
        parts = parts[1:]
    words = [
        part.upper() if len(part) <= 3 else part.capitalize()
        for part in parts
        if part != "player"
    ]
    return " ".join(words) or name


def player_vehicle_records(database, kind=""):
    """The records in Vehicle.vehicle_list.list, optionally only cars or bikes"""
    try:
        listed = database.resolve(PLAYER_VEHICLE_LIST).fields.get("list") or ()
    except KeyError:
        return ()
    result = []
    for record_id in listed:
        if not isinstance(record_id, str) or not database.has_record(record_id):
            continue
        if kind and vehicle_record_kind(database.resolve(record_id)) != kind:
            continue
        result.append(record_id)
    return tuple(dict.fromkeys(result))


def resolve_vehicle_game_data(database, record_id, *, curve_loader=None):
    record = database.resolve(record_id)
    if vehicle_record_kind(record) == "BIKE":
        return _resolve_bike_game_data(
            database,
            record_id,
            curve_loader=curve_loader,
        )
    return _resolve_car_game_data(
        database,
        record_id,
        curve_loader=curve_loader,
    )


def _inherited_depth(database, record_id, record_ids):
    """How many of record_ids record_id inherits from"""
    depth = 0
    seen = {record_id}
    base = database.base_record(record_id)
    while base and base not in seen:
        seen.add(base)
        if base in record_ids:
            depth += 1
        base = database.base_record(base)
    return depth


def entity_vehicle_records(database, entity_path, appearance_names=()):
    """The records whose entityTemplatePath is the entity, best guess first"""
    records = database.records_for_entity(_entity_depot_path(entity_path))
    record_ids = {record.record_id for record in records}
    names = {str(name).casefold() for name in appearance_names if name}

    def rank(record):
        named = str(record.fields.get("appearanceName", "") or "").casefold() in names
        return (
            not named,
            _inherited_depth(database, record.record_id, record_ids),
            record.record_id.casefold(),
        )

    return tuple(sorted(records, key=rank))


def vehicle_variants(database, record_id, appearance_names=()):
    """The records that share record_id's entity"""
    template = database.resolve(record_id).fields.get("entityTemplatePath")
    if not isinstance(template, str) or not template:
        return ()
    return entity_vehicle_records(database, template, appearance_names)
