from __future__ import annotations

import json
import math

import bpy
from mathutils import Vector

from ...bartmoss.vector3 import length3
from ...bartmoss.vehicle import (
    STANDARD_GRAVITY,
    cp77_logical_suspension_droop,
    cp77_spring_rate_kg_mm,
    cp77_spring_strength,
    cp77_tire_preview_friction,
    spring_rate_kg_mm_to_strength,
)
from ...blender.physics.vehicle_geometry import (
    WHEEL_FIELDS,
    aggregate_bounds,
    bone_is_descendant_of,
    pose_from_matrix,
    projected_dimensions,
    rig_bone_world_matrix,
    vehicle_actor_world,
    vehicle_chassis_shape_definitions,
    vehicle_frame_world,
    vehicle_local_position,
    wheel_objects,
)
from ...physics.domain.vehicle.game_data import ensure_tire_friction_config
from ...physics.domain.vehicle.gears import config_with_authored_gears
from .vehicle_validation import (
    resolved_game_config,
    validate_authoring_state,
    validate_powertrain,
)


def geometry_wheel_dimensions(vehicle):
    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    if vehicle.vehicle_kind == "BIKE":
        fields = ("front", "rear")
        wheels = (vehicle.bike_front, vehicle.bike_rear)
    else:
        fields = ("front_left", "front_right", "rear_left", "rear_right")
        wheels = wheel_objects(vehicle)
    try:
        group_names = json.loads(vehicle.resolved_wheel_groups or "{}")
    except (TypeError, ValueError):
        group_names = {}
    radii = []
    widths = []
    for field, wheel in zip(fields, wheels):
        size = None
        if vehicle.source_mode == "RIG":
            group = [
                obj
                for name in group_names.get(field, ())
                if (obj := bpy.data.objects.get(name)) is not None
            ]
            bounds = aggregate_bounds(group, frame_inverse)
            if bounds:
                size = bounds[1] - bounds[0]
        if size is None and wheel is None:
            radii.append(float(vehicle.wheel_radius))
            widths.append(float(vehicle.wheel_width))
            continue
        if size is None:
            size = projected_dimensions(wheel, frame_inverse)
        radii.append(max(size.y, size.z) * 0.5)
        widths.append(size.x)
    return radii, widths


def _axle_snapshot(axle):
    return {
        "tireFrictionCoef": float(axle.tire_friction_coef),
        "extremeCompressionEventScalor": float(axle.extreme_compression_event_scalor),
        "frictionMulLateral": float(axle.friction_mul_lateral),
        "frictionMulLongitudinal": float(axle.friction_mul_longitudinal),
        "logicalSuspensionCompressionLength": float(
            axle.logical_suspension_compression_length
        ),
        "mass": float(axle.mass),
        "maxBrakingTorque": float(axle.max_braking_torque),
        "springBoundDampingLowRate": float(axle.spring_bound_damping_low_rate),
        "springDamping": float(axle.spring_damping),
        "springDampingHighRateCompression": float(
            axle.spring_damping_high_rate_compression
        ),
        "springDampingLowRateCompression": float(
            axle.spring_damping_low_rate_compression
        ),
        "springReboundDamping": float(axle.spring_rebound_damping),
        "springReboundDampingLowRate": float(axle.spring_rebound_damping_low_rate),
        "springStiffness": float(axle.spring_stiffness),
        "swaybarStiffness": float(axle.swaybar_stiffness),
        "swaybarLengthScalar": float(axle.swaybar_length_scalar),
        "swaybarDisplacementLimit": float(axle.swaybar_displacement_limit),
        "tenderSpringLength": float(axle.tender_spring_length),
        "tireLateralSlipEffectsMul": float(axle.tire_lateral_slip_effects_mul),
        "tireLongitudinalSlipEffectsMul": float(
            axle.tire_longitudinal_slip_effects_mul
        ),
        "tireRollingResistanceCoef": float(axle.tire_rolling_resistance_coef),
        "visualSuspensionCompressionLength": float(
            axle.visual_suspension_compression_length
        ),
        "visualSuspensionDroop": float(axle.visual_suspension_droop),
        "wheelsVerticalOffset": float(axle.wheels_vertical_offset),
    }


def _set_axle_from_config(axle, preset, radius, rim_radius, width, wheel_offset):
    preset = preset if isinstance(preset, dict) else {}
    axle.tire_radius = float(radius)
    axle.rim_radius = float(rim_radius)
    axle.tire_width = float(width)
    axle.wheel_offset = float(wheel_offset)
    mapping = {
        "mass": "mass",
        "max_braking_torque": "maxBrakingTorque",
        "logical_suspension_compression_length": "logicalSuspensionCompressionLength",
        "visual_suspension_compression_length": "visualSuspensionCompressionLength",
        "visual_suspension_droop": "visualSuspensionDroop",
        "spring_stiffness": "springStiffness",
        "spring_damping": "springDamping",
        "spring_rebound_damping": "springReboundDamping",
        "tire_friction_coef": "tireFrictionCoef",
        "friction_mul_longitudinal": "frictionMulLongitudinal",
        "friction_mul_lateral": "frictionMulLateral",
        "wheels_vertical_offset": "wheelsVerticalOffset",
        "extreme_compression_event_scalor": "extremeCompressionEventScalor",
        "spring_bound_damping_low_rate": "springBoundDampingLowRate",
        "spring_damping_high_rate_compression": "springDampingHighRateCompression",
        "spring_damping_low_rate_compression": "springDampingLowRateCompression",
        "spring_rebound_damping_low_rate": "springReboundDampingLowRate",
        "swaybar_stiffness": "swaybarStiffness",
        "swaybar_length_scalar": "swaybarLengthScalar",
        "swaybar_displacement_limit": "swaybarDisplacementLimit",
        "tender_spring_length": "tenderSpringLength",
        "tire_lateral_slip_effects_mul": "tireLateralSlipEffectsMul",
        "tire_longitudinal_slip_effects_mul": "tireLongitudinalSlipEffectsMul",
        "tire_rolling_resistance_coef": "tireRollingResistanceCoef",
    }
    for attr, key in mapping.items():
        if key in preset:
            setattr(axle, attr, float(preset[key]))
    # A preset without a logical compression length leaves it at 0, which means the suspension-to-wheel bone
    # distance, rather than the property's default.
    axle.logical_suspension_compression_length = max(
        float(preset.get("logicalSuspensionCompressionLength", 0.0)), 0.0
    )


def _wheel_roles(vehicle):
    return (
        vehicle.wheel_role_lf,
        vehicle.wheel_role_rf,
        vehicle.wheel_role_lb,
        vehicle.wheel_role_rb,
    )


def _bike_wheel_roles(vehicle):
    return (vehicle.wheel_role_front, vehicle.wheel_role_back)


def _apply_role_flags(vehicle, source_flags=None):
    if vehicle.vehicle_kind == "BIKE":
        roles = _bike_wheel_roles(vehicle)
        if isinstance(source_flags, list) and len(source_flags) >= 2:
            for role, source in zip(roles, source_flags[:2]):
                source = source if isinstance(source, dict) else {}
                role.is_drive = bool(source.get("isDrive", False))
                role.is_main_brake = bool(source.get("isMainBrake", False))
                role.is_hand_brake = bool(source.get("isHandBrake", False))
            return
        roles[0].is_drive = False
        roles[0].is_main_brake = True
        roles[0].is_hand_brake = False
        roles[1].is_drive = True
        roles[1].is_main_brake = True
        roles[1].is_hand_brake = True
        return
    roles = _wheel_roles(vehicle)
    if isinstance(source_flags, list) and len(source_flags) >= 4:
        for role, source in zip(roles, source_flags[:4]):
            source = source if isinstance(source, dict) else {}
            role.is_drive = bool(source.get("isDrive", False))
            role.is_main_brake = bool(source.get("isMainBrake", False))
            role.is_hand_brake = bool(source.get("isHandBrake", False))
        return
    for index, role in enumerate(roles):
        role.is_drive = True
        role.is_main_brake = True
        role.is_hand_brake = index >= 2


def ensure_axle_authoring(vehicle, source=None):
    if getattr(vehicle, "axle_authoring_initialized", False):
        return
    source = source if isinstance(source, dict) else {}
    count = 2 if vehicle.vehicle_kind == "BIKE" else 4
    geometry_radii, geometry_widths = geometry_wheel_dimensions(vehicle)
    radii = (
        source.get("wheel_radii")
        if isinstance(source.get("wheel_radii"), list)
        else geometry_radii
    )
    widths = (
        source.get("wheel_widths")
        if isinstance(source.get("wheel_widths"), list)
        else geometry_widths
    )
    rims = (
        source.get("wheel_rim_radii")
        if isinstance(source.get("wheel_rim_radii"), list)
        else radii
    )
    offsets = (
        source.get("wheel_dimension_offsets")
        if isinstance(source.get("wheel_dimension_offsets"), list)
        else [0.0, 0.0]
    )
    if len(radii) != count:
        radii = [float(vehicle.wheel_radius)] * count
    if len(widths) != count:
        widths = [float(vehicle.wheel_width)] * count
    if len(rims) != count:
        rims = list(radii)
    front_indices = (0,) if count == 2 else (0, 1)
    rear_indices = (1,) if count == 2 else (2, 3)
    mean = lambda values, indices: sum(float(values[i]) for i in indices) / len(indices)
    front_preset = source.get("cp77_front_wheel_preset", {})
    rear_preset = source.get("cp77_rear_wheel_preset", {})
    if not front_preset:
        front_preset = {
            "mass": vehicle.wheel_mass,
            "maxBrakingTorque": vehicle.max_brake_torque,
            "logicalSuspensionCompressionLength": vehicle.suspension_max_compression,
            "visualSuspensionCompressionLength": vehicle.suspension_max_compression,
            "visualSuspensionDroop": vehicle.suspension_max_droop,
            "springStiffness": cp77_spring_rate_kg_mm(
                vehicle.suspension_spring_strength,
                max(
                    float(vehicle.suspension_max_compression)
                    + float(vehicle.suspension_max_droop),
                    1.0e-6,
                ),
                _vehicle_gravity_magnitude(vehicle),
            ),
            "springDamping": vehicle.suspension_damper_rate,
            "springReboundDamping": vehicle.suspension_damper_rate,
            "tireFrictionCoef": vehicle.tire_friction,
            "frictionMulLongitudinal": 1.0,
            "frictionMulLateral": 1.0,
        }
    if not rear_preset:
        rear_preset = dict(front_preset)
    _set_axle_from_config(
        vehicle.front_axle,
        front_preset,
        mean(radii, front_indices),
        mean(rims, front_indices),
        mean(widths, front_indices),
        float(offsets[0]) if len(offsets) > 0 else 0.0,
    )
    _set_axle_from_config(
        vehicle.rear_axle,
        rear_preset,
        mean(radii, rear_indices),
        mean(rims, rear_indices),
        mean(widths, rear_indices),
        float(offsets[1]) if len(offsets) > 1 else 0.0,
    )
    _apply_role_flags(vehicle, source.get("wheel_flags"))
    vehicle.axle_authoring_initialized = True


def authored_wheel_dimensions(vehicle):
    source = (
        resolved_game_config(vehicle)
        if getattr(vehicle, "game_data_enabled", False)
        else {}
    )
    ensure_axle_authoring(vehicle, source)
    if vehicle.vehicle_kind == "BIKE":
        return (
            [
                float(vehicle.front_axle.tire_radius),
                float(vehicle.rear_axle.tire_radius),
            ],
            [float(vehicle.front_axle.tire_width), float(vehicle.rear_axle.tire_width)],
        )
    return (
        [float(vehicle.front_axle.tire_radius)] * 2
        + [float(vehicle.rear_axle.tire_radius)] * 2,
        [float(vehicle.front_axle.tire_width)] * 2
        + [float(vehicle.rear_axle.tire_width)] * 2,
    )


def scene_gravity_magnitude(scene, fallback=STANDARD_GRAVITY):
    """The length of the scene's PhysX gravity in m/s², or fallback when the scene has none"""
    gravity = getattr(getattr(scene, "physx", None), "gravity", None)
    if gravity is None:
        return float(fallback)
    try:
        return length3(tuple(float(value) for value in gravity[:3]))
    except (TypeError, ValueError, IndexError):
        return float(fallback)


def _vehicle_gravity_magnitude(vehicle):
    magnitude = scene_gravity_magnitude(getattr(vehicle, "id_data", None))
    if not math.isfinite(magnitude) or magnitude <= 1.0e-6:
        raise ValueError(
            "Vehicle spring conversion requires a nonzero finite scene gravity"
        )
    return magnitude


def _suspension_bone_pairs(vehicle):
    if vehicle.vehicle_kind == "BIKE":
        return (
            (vehicle.bike_front_bone, vehicle.bike_front_suspension_bone),
            (vehicle.bike_rear_bone, vehicle.bike_rear_suspension_bone),
        )
    return tuple(
        (
            getattr(vehicle, f"{field}_bone", ""),
            getattr(vehicle, f"{field}_suspension_bone", ""),
        )
        for field, _label in WHEEL_FIELDS
    )


def source_suspension_geometry(vehicle, axles):
    directions = [[0.0, 0.0, -1.0] for _axle in axles]
    visual_lengths = [None for _axle in axles]
    if vehicle.source_mode == "RIG" and vehicle.rig is not None:
        frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
        for index, (wheel_name, suspension_name) in enumerate(
            _suspension_bone_pairs(vehicle)
        ):
            wheel_matrix = rig_bone_world_matrix(vehicle.rig, wheel_name)
            suspension_matrix = rig_bone_world_matrix(vehicle.rig, suspension_name)
            if wheel_matrix is None or suspension_matrix is None:
                continue
            wheel_position = frame_inverse @ wheel_matrix.translation
            suspension_position = frame_inverse @ suspension_matrix.translation
            delta = wheel_position - suspension_position
            length = float(delta.length)
            if length <= 1.0e-6:
                continue
            direction = delta / length
            if float(direction.z) >= 0.0:
                raise ValueError(
                    "Vehicle suspension bones must point from suspension origin down toward the wheel"
                )
            directions[index] = [
                float(direction.x),
                float(direction.y),
                float(direction.z),
            ]
            visual_lengths[index] = length

    compressions = []
    droops = []
    spring_lengths = []
    spring_strengths = []
    gravity = _vehicle_gravity_magnitude(vehicle)
    for index, axle in enumerate(axles):
        direction_z = float(directions[index][2])
        authored_compression = float(axle.logical_suspension_compression_length)
        visual_length = visual_lengths[index]
        if authored_compression > 0.0:
            compression = authored_compression
        elif visual_length is not None and visual_length > 0.0:
            compression = visual_length
        else:
            compression = max(float(axle.visual_suspension_compression_length), 1.0e-6)
        droop = cp77_logical_suspension_droop(
            float(axle.visual_suspension_droop), direction_z
        )
        spring_length = compression + droop
        compressions.append(compression)
        droops.append(droop)
        spring_lengths.append(spring_length)
        spring_strengths.append(
            cp77_spring_strength(float(axle.spring_stiffness), spring_length, gravity)
        )
    return {
        "directions": directions,
        "visual_lengths": [
            float(length) if length is not None and length > 0.0 else float(compression)
            for length, compression in zip(visual_lengths, compressions)
        ],
        "compressions": compressions,
        "droops": droops,
        "spring_lengths": spring_lengths,
        "spring_strengths": spring_strengths,
        "gravity": gravity,
    }


def apply_authored_vehicle_values(vehicle, source, *, include_powertrain=True):
    config = ensure_tire_friction_config(source)
    ensure_axle_authoring(vehicle, config)
    count = 2 if vehicle.vehicle_kind == "BIKE" else 4
    front = vehicle.front_axle
    rear = vehicle.rear_axle
    axles = [front, rear] if count == 2 else [front, front, rear, rear]
    config["wheel_radii"] = [float(axle.tire_radius) for axle in axles]
    config["wheel_rim_radii"] = [float(axle.rim_radius) for axle in axles]
    config["wheel_widths"] = [float(axle.tire_width) for axle in axles]
    config["wheel_masses"] = [float(axle.mass) for axle in axles]
    config["wheel_damping_rates"] = [float(vehicle.wheel_damping_rate)] * count
    config["wheel_dimension_offsets"] = [
        float(front.wheel_offset),
        float(rear.wheel_offset),
    ]
    config["wheel_vertical_offsets"] = [
        float(axle.wheels_vertical_offset) for axle in axles
    ]
    if count == 4:
        offsets = (
            -front.wheel_offset,
            front.wheel_offset,
            -rear.wheel_offset,
            rear.wheel_offset,
        )
        config["wheel_center_offsets"] = [
            [float(x), 0.0, float(axle.wheels_vertical_offset)]
            for x, axle in zip(offsets, axles)
        ]
        roles = _wheel_roles(vehicle)
        flags = [
            {
                "isDrive": bool(role.is_drive),
                "isMainBrake": bool(role.is_main_brake),
                "isHandBrake": bool(role.is_hand_brake),
            }
            for role in roles
        ]
        config["wheel_flags"] = flags
        front_drive = flags[0]["isDrive"] or flags[1]["isDrive"]
        rear_drive = flags[2]["isDrive"] or flags[3]["isDrive"]
        config["differential_type"] = (
            "AWD" if front_drive and rear_drive else "FWD" if front_drive else "RWD"
        )
        config["brake_torques"] = [
            float(axle.max_braking_torque) if flag["isMainBrake"] else 0.0
            for axle, flag in zip(axles, flags)
        ]
        config["handbrake_torques"] = [
            float(vehicle.rear_handbrake_torque) if flag["isHandBrake"] else 0.0
            for flag in flags
        ]
        config["steer_angles"] = [
            float(vehicle.front_steer_angle),
            float(vehicle.front_steer_angle),
            0.0,
            0.0,
        ]
    else:
        roles = _bike_wheel_roles(vehicle)
        source_flags = [
            {
                "isDrive": bool(role.is_drive),
                "isMainBrake": bool(role.is_main_brake),
                "isHandBrake": bool(role.is_hand_brake),
            }
            for role in roles
        ]
        config["wheel_flags"] = source_flags
        config["wheel_center_offsets"] = [
            [0.0, 0.0, float(front.wheels_vertical_offset)],
            [0.0, 0.0, float(rear.wheels_vertical_offset)],
        ]
        config["brake_torques"] = [
            float(axle.max_braking_torque) if flag["isMainBrake"] else 0.0
            for axle, flag in zip(axles, source_flags)
        ]
        config["handbrake_torques"] = [
            float(vehicle.rear_handbrake_torque) if flag["isHandBrake"] else 0.0
            for flag in source_flags
        ]
        config["steer_angles"] = [float(vehicle.front_steer_angle), 0.0]
        driven = [i for i, flag in enumerate(source_flags) if flag["isDrive"]]
        if driven not in ([0], [1]):
            raise ValueError("Bike wheelSetup must define exactly one driven wheel")
        config["differential_type"] = "BIKE_FWD" if driven == [0] else "BIKE_RWD"
    suspension = source_suspension_geometry(vehicle, axles)
    config["suspension_directions"] = suspension["directions"]
    config["suspension_visual_lengths"] = suspension["visual_lengths"]
    config["suspension_compressions"] = suspension["compressions"]
    config["suspension_visual_compressions"] = [
        float(axle.visual_suspension_compression_length) for axle in axles
    ]
    config["suspension_visual_droops"] = [
        float(axle.visual_suspension_droop) for axle in axles
    ]
    config["suspension_droops"] = suspension["droops"]
    config["suspension_spring_lengths"] = suspension["spring_lengths"]
    config["suspension_spring_rates_kg_mm"] = [
        float(axle.spring_stiffness) for axle in axles
    ]
    config["suspension_spring_strengths"] = suspension["spring_strengths"]
    config["suspension_compression_damper_rates"] = [
        float(axle.spring_damping) for axle in axles
    ]
    config["suspension_rebound_damper_rates"] = [
        float(axle.spring_rebound_damping) for axle in axles
    ]
    config["suspension_bound_damping_low_rates"] = [
        float(axle.spring_bound_damping_low_rate) for axle in axles
    ]
    config["suspension_rebound_damping_low_rates"] = [
        float(axle.spring_rebound_damping_low_rate) for axle in axles
    ]
    config["suspension_damping_low_rate_compressions"] = [
        float(axle.spring_damping_low_rate_compression) for axle in axles
    ]
    config["suspension_damping_high_rate_compressions"] = [
        float(axle.spring_damping_high_rate_compression) for axle in axles
    ]
    config["suspension_extreme_compression_scalars"] = [
        float(axle.extreme_compression_event_scalor) for axle in axles
    ]
    config["suspension_damper_rates"] = [
        0.5 * (float(axle.spring_damping) + float(axle.spring_rebound_damping))
        for axle in axles
    ]
    config["tire_friction_coefficients"] = [
        float(axle.tire_friction_coef) for axle in axles
    ]
    config["tire_friction_longitudinal_multipliers"] = [
        float(axle.friction_mul_longitudinal) for axle in axles
    ]
    config["tire_friction_lateral_multipliers"] = [
        float(axle.friction_mul_lateral) for axle in axles
    ]
    config["tire_rolling_resistance_coefficients"] = [
        float(axle.tire_rolling_resistance_coef) for axle in axles
    ]
    config["tire_frictions"] = [
        cp77_tire_preview_friction(
            float(axle.tire_friction_coef),
            float(axle.friction_mul_longitudinal),
            float(axle.friction_mul_lateral),
        )
        for axle in axles
    ]
    config["tire_longitudinal_stiffnesses"] = [
        1000.0 * float(axle.friction_mul_longitudinal) for axle in axles
    ]
    config["tire_lateral_stiffness_x"] = [2.0 for _axle in axles]
    config["tire_lateral_stiffness_y"] = [
        (0.3125 * 180.0 / math.pi) * float(axle.friction_mul_lateral) for axle in axles
    ]
    if count == 4:
        gravity = _vehicle_gravity_magnitude(vehicle)
        front_spring_length = 0.5 * (
            suspension["spring_lengths"][0] + suspension["spring_lengths"][1]
        )
        rear_spring_length = 0.5 * (
            suspension["spring_lengths"][2] + suspension["spring_lengths"][3]
        )
        config["anti_roll_stiffnesses"] = [
            spring_rate_kg_mm_to_strength(
                float(front.swaybar_stiffness), front_spring_length, gravity
            ),
            spring_rate_kg_mm_to_strength(
                float(rear.swaybar_stiffness), rear_spring_length, gravity
            ),
        ]
        config["anti_roll_displacement_limits"] = [
            float(front.swaybar_displacement_limit),
            float(rear.swaybar_displacement_limit),
        ]
        config["anti_roll_length_scalars"] = [
            float(front.swaybar_length_scalar),
            float(rear.swaybar_length_scalar),
        ]
    config["cp77_front_wheel_preset"] = _axle_snapshot(front)
    config["cp77_rear_wheel_preset"] = _axle_snapshot(rear)
    config["chassis_mass"] = float(vehicle.chassis_mass)
    config["total_mass"] = float(vehicle.total_mass)
    config["chassis_cm_source"] = list(vehicle.chassis_cm_offset)
    if vehicle.use_chassis_inertia:
        config["chassis_inertia"] = [float(value) for value in vehicle.chassis_inertia]
    else:
        config.pop("chassis_inertia", None)
    config["air_resistance_factor"] = float(vehicle.air_resistance_factor)
    config["braking_friction_factor"] = float(vehicle.braking_friction_factor)
    config["turning_roll_factor"] = float(vehicle.turning_roll_factor)
    config["wheel_turn_add_rate"] = float(vehicle.wheel_turn_max_add_per_second)
    config["wheel_turn_sub_rate"] = float(vehicle.wheel_turn_max_sub_per_second)
    max_steer_degrees = max(math.degrees(float(vehicle.front_steer_angle)), 0.001)
    config["steer_rise_rate"] = (
        float(vehicle.wheel_turn_max_add_per_second) / max_steer_degrees
    )
    config["steer_fall_rate"] = (
        float(vehicle.wheel_turn_max_sub_per_second) / max_steer_degrees
    )
    if vehicle.auto_wheel_moi:
        config["wheel_moi_values"] = [
            0.5 * mass * radius * radius
            for mass, radius in zip(config["wheel_masses"], config["wheel_radii"])
        ]
    else:
        config["wheel_moi_values"] = [float(vehicle.wheel_moi)] * count
    if include_powertrain:
        config["engine_peak_torque"] = float(vehicle.engine_peak_torque)
        config["engine_max_omega"] = float(vehicle.engine_max_omega)
        config["gear_switch_time"] = float(vehicle.gear_switch_time)
        config["engine_moi"] = float(vehicle.engine_moi)
        config["engine_damping_rate"] = float(vehicle.engine_resistance_torque) / max(
            float(vehicle.engine_max_omega), 1.0e-6
        )
        config = config_with_authored_gears(vehicle, config)
    if vehicle.vehicle_kind == "BIKE":
        config["bike_max_lean_angle"] = float(vehicle.bike_max_lean_angle)
        config["bike_tilt_pid"] = list(vehicle.bike_tilt_pid)
        config["bike_tilt_speed"] = float(vehicle.bike_tilt_speed)
        config["bike_tilt_return_speed"] = float(vehicle.bike_tilt_return_speed)
        config["bike_tilt_custom_speed"] = float(vehicle.bike_tilt_custom_speed)
        config["bike_max_com_long_offset"] = float(vehicle.bike_max_com_long_offset)
        config["bike_min_com_long_offset"] = float(vehicle.bike_min_com_long_offset)
        config["bike_com_offset_damp_factor"] = float(
            vehicle.bike_com_offset_damp_factor
        )
    # A curve whose resource was not found is left out, so the preview uses its default curve.
    for key in ("engine_torque_curve", "steer_vs_speed"):
        if not config.get(key):
            config.pop(key, None)
    return config


def validate_bike(vehicle):
    errors, warnings, game_config = validate_authoring_state(vehicle)
    if vehicle.source_mode == "RIG":
        if vehicle.rig is None or vehicle.rig.type != "ARMATURE":
            errors.append("Assign the imported bike MetaRig")
        for label, name, suspension_name in (
            ("front", vehicle.bike_front_bone, vehicle.bike_front_suspension_bone),
            ("rear", vehicle.bike_rear_bone, vehicle.bike_rear_suspension_bone),
        ):
            if vehicle.rig is None or vehicle.rig.type != "ARMATURE":
                continue
            bone = vehicle.rig.data.bones.get(name) if name else None
            suspension = (
                vehicle.rig.data.bones.get(suspension_name) if suspension_name else None
            )
            if bone is None:
                errors.append(f"The rig does not define the {label} bike wheel bone")
                continue
            if suspension is None:
                warnings.append(
                    f"The rig does not define the {label} bike suspension bone"
                )
            elif not bone_is_descendant_of(bone, suspension):
                warnings.append(
                    f"The {label} bike wheel is not parented below its suspension bone"
                )
    else:
        if vehicle.chassis is None:
            errors.append("Assign a chassis object")
        elif vehicle.chassis.type != "MESH":
            errors.append("The chassis must be a mesh object")
        if vehicle.bike_front is None or vehicle.bike_rear is None:
            errors.append("Assign the front and rear bike wheels")
        elif vehicle.bike_front == vehicle.bike_rear:
            errors.append("Bike wheel slots must reference different objects")
        else:
            if vehicle.bike_front.type != "MESH":
                errors.append("The front bike wheel must be a mesh object")
            if vehicle.bike_rear.type != "MESH":
                errors.append("The rear bike wheel must be a mesh object")
    if not errors:
        frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
        if vehicle.source_mode == "RIG":
            centers = []
            for bone_name in (vehicle.bike_front_bone, vehicle.bike_rear_bone):
                matrix = rig_bone_world_matrix(vehicle.rig, bone_name)
                if matrix is None:
                    centers = []
                    break
                centers.append(frame_inverse @ matrix.translation)
        else:
            centers = [
                frame_inverse @ wheel.matrix_world.translation
                for wheel in (vehicle.bike_front, vehicle.bike_rear)
            ]
        if len(centers) != 2:
            errors.append("Bike wheel centers could not be resolved")
        else:
            front, rear = centers
            if front.y <= rear.y:
                errors.append("The front bike wheel must be ahead of the rear wheel")
            if abs(front.x - rear.x) > 0.05:
                warnings.append("Bike wheel centers are not laterally aligned")
    ensure_axle_authoring(vehicle, game_config)
    numeric_fields = (
        "chassis_mass",
        "bike_max_lean_angle",
        "bike_tilt_speed",
        "bike_tilt_return_speed",
    )
    if any(
        not math.isfinite(float(getattr(vehicle, field))) for field in numeric_fields
    ):
        errors.append("Bike dimensions, mass, and lean settings must be finite")
    if (
        vehicle.bike_max_lean_angle <= 0.0
        or vehicle.bike_max_lean_angle >= math.pi * 0.5
        or vehicle.bike_tilt_speed <= 0.0
        or vehicle.bike_tilt_return_speed <= 0.0
    ):
        errors.append("Bike lean angle and rates must be positive and physically valid")
    if any(
        not math.isfinite(float(value)) or value < 0.0
        for value in vehicle.bike_tilt_pid
    ):
        errors.append("Bike lean PID values must be finite and nonnegative")
    errors.extend(
        validate_powertrain(
            vehicle, total_mass_label="bikeDriveModelData", axles_first=False
        )
    )
    driven = [role.is_drive for role in _bike_wheel_roles(vehicle)]
    if sum(bool(value) for value in driven) != 1:
        errors.append("Bike wheelSetup must define exactly one driven wheel")
    return errors, warnings


def bike_vehicle_config(
    vehicle, *, include_powertrain=True, include_chassis_shapes=True
):
    frame = vehicle_actor_world(vehicle)
    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    shape_offset = Vector(vehicle.chassis_shape_offset)
    if vehicle.source_mode == "RIG":
        centers = []
        for bone_name in (vehicle.bike_front_bone, vehicle.bike_rear_bone):
            matrix = rig_bone_world_matrix(vehicle.rig, bone_name)
            if matrix is None:
                raise ValueError("Bike wheel bone transforms could not be resolved")
            centers.append(list(frame_inverse @ matrix.translation - shape_offset))
    else:
        centers = [
            list(vehicle_local_position(vehicle, wheel, frame_inverse, shape_offset))
            for wheel in (vehicle.bike_front, vehicle.bike_rear)
        ]
    target_centers = [list(center) for center in centers]
    wheelbase = float(centers[0][1] - centers[1][1])
    if wheelbase <= 0.0:
        raise ValueError("The front bike wheel must be ahead of the rear wheel")
    game_config = resolved_game_config(vehicle)
    config = apply_authored_vehicle_values(
        vehicle, game_config, include_powertrain=include_powertrain
    )
    center_offsets = config.get("wheel_center_offsets")
    if isinstance(center_offsets, list) and len(center_offsets) == 2:
        for center, target_center, offset in zip(
            centers, target_centers, center_offsets
        ):
            if isinstance(offset, list) and len(offset) == 3:
                for axis in range(3):
                    center[axis] += float(offset[axis])
                target_center[0] += float(offset[0])
                target_center[1] += float(offset[1])
    config.update(
        {
            "vehicle_kind": "BIKE",
            "pose": pose_from_matrix(frame),
            "chassis_dims": list(vehicle.chassis_dims),
            "chassis_mass": float(vehicle.chassis_mass),
            "chassis_cm_offset": [
                float(vehicle.chassis_cm_offset[index]) - float(shape_offset[index])
                for index in range(3)
            ],
            "wheel_centers": centers,
            "wheel_target_centers": target_centers,
            "wheelbase": wheelbase,
            "clutch_strength": float(vehicle.clutch_strength),
            "auto_gears": bool(vehicle.auto_gears),
            "bike_max_lean_angle": float(vehicle.bike_max_lean_angle),
            "bike_tilt_pid": list(vehicle.bike_tilt_pid),
            "bike_tilt_speed": float(vehicle.bike_tilt_speed),
            "bike_tilt_return_speed": float(vehicle.bike_tilt_return_speed),
            "bike_tilt_custom_speed": float(vehicle.bike_tilt_custom_speed),
            "bike_max_com_long_offset": float(vehicle.bike_max_com_long_offset),
            "bike_min_com_long_offset": float(vehicle.bike_min_com_long_offset),
            "bike_com_offset_damp_factor": float(vehicle.bike_com_offset_damp_factor),
        }
    )
    if include_chassis_shapes:
        scene = getattr(vehicle, "id_data", None)
        if scene is None:
            raise ValueError("Vehicle configuration is not attached to a Blender scene")
        chassis_shapes, _actors = vehicle_chassis_shape_definitions(
            scene, vehicle, frame
        )
        if chassis_shapes:
            config["chassis_shapes"] = chassis_shapes
    if not config.get("bike_speed_to_tilt"):
        config["bike_speed_to_tilt"] = [
            [0.0, 0.0],
            [5.0, 0.65],
            [25.0, 1.0],
            [80.0, 1.0],
        ]
    if not config.get("bike_input_to_tilt"):
        config["bike_input_to_tilt"] = [
            [0.0, 0.0],
            [0.25, 0.3],
            [0.6, 0.75],
            [1.0, 1.0],
        ]
    if not config.get("bike_speed_to_tilt_speed"):
        config["bike_speed_to_tilt_speed"] = [
            [0.0, 0.6],
            [5.0, 0.85],
            [25.0, 1.0],
            [80.0, 1.0],
        ]
    config.pop("chassis_cm_source", None)
    config.pop("wheel_center_offsets", None)
    config.pop("engine_curve_path", None)
    config.pop("vehicle_curve_path", None)
    config.pop("bike_curve_path", None)
    config.pop("wheel_flags", None)
    config.pop("geometry_authoritative", None)
    config.pop("cp77_front_wheel_preset", None)
    config.pop("cp77_rear_wheel_preset", None)
    for key in tuple(config):
        if key.startswith("source_"):
            config.pop(key, None)
    if not include_powertrain:
        for key in (
            "engine_peak_torque",
            "engine_max_omega",
            "gear_switch_time",
            "clutch_strength",
            "auto_gears",
            "gear_ratios",
            "gear_torque_multipliers",
            "autobox_up_ratios",
            "autobox_down_ratios",
            "final_gear_torque_decimation",
        ):
            config.pop(key, None)
    return config
