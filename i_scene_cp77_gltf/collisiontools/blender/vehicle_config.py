from __future__ import annotations

import json

import bpy
from mathutils import Vector

from ...bartmoss.vehicle import vehicle_axle_geometry
from ...blender.physics.vehicle_geometry import (
    WHEEL_FIELDS,
    bone_is_descendant_of,
    pose_from_matrix,
    rig_bone_world_matrix,
    vehicle_actor_world,
    vehicle_chassis_shape_definitions,
    vehicle_frame_world,
    vehicle_local_position,
    vehicle_root,
    wheel_objects,
)
from .vehicle_validation import (
    resolved_game_config,
    validate_authoring_state,
    validate_powertrain,
)


def _rig_wheel_center(vehicle, field, frame_inverse=None, shape_offset=None):
    rig = vehicle.rig
    bone_name = getattr(vehicle, f"{field}_bone", "")
    matrix = rig_bone_world_matrix(rig, bone_name)
    if matrix is None:
        return None
    if frame_inverse is None:
        frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    if shape_offset is None:
        shape_offset = Vector(vehicle.chassis_shape_offset)
    return frame_inverse @ matrix.translation - shape_offset


def wheel_centers(vehicle, frame_inverse=None, shape_offset=None):
    if vehicle.source_mode == "RIG":
        return [
            _rig_wheel_center(vehicle, field, frame_inverse, shape_offset)
            for field, _label in WHEEL_FIELDS
        ]
    return [
        vehicle_local_position(vehicle, wheel, frame_inverse, shape_offset)
        for wheel in wheel_objects(vehicle)
    ]


def validate_vehicle(vehicle):
    if getattr(vehicle, "vehicle_kind", "CAR") == "BIKE":
        from .vehicle_authoring_state import validate_bike

        return validate_bike(vehicle)
    errors, warnings, game_config = validate_authoring_state(vehicle)
    if vehicle.source_mode == "RIG":
        rig = vehicle.rig
        if rig is None:
            errors.append("Assign the imported vehicle MetaRig")
        elif rig.type != "ARMATURE":
            errors.append("The vehicle source must be an armature")
        else:
            for field, label in WHEEL_FIELDS:
                bone_name = getattr(vehicle, f"{field}_bone", "")
                suspension_name = getattr(vehicle, f"{field}_suspension_bone", "")
                bone = rig.data.bones.get(bone_name) if bone_name else None
                suspension = (
                    rig.data.bones.get(suspension_name) if suspension_name else None
                )
                if bone is None:
                    errors.append(
                        f"The rig does not define the {label.lower()} wheel bone"
                    )
                    continue
                if suspension is None:
                    warnings.append(
                        f"The rig does not define the {label.lower()} suspension bone"
                    )
                elif not bone_is_descendant_of(bone, suspension):
                    warnings.append(
                        f"The {label.lower()} wheel is not parented below its suspension bone"
                    )
            try:
                resolved_names = json.loads(vehicle.resolved_object_names or "[]")
            except (TypeError, ValueError):
                resolved_names = ()
            if not resolved_names:
                warnings.append(
                    "No imported appearance meshes were resolved from the rig"
                )
    else:
        if vehicle.chassis is None:
            errors.append("Assign a chassis object")
        elif vehicle.chassis.type != "MESH":
            errors.append("The chassis must be a mesh object")

        seen = set()
        for field, label in WHEEL_FIELDS:
            wheel = getattr(vehicle, field, None)
            if wheel is None:
                errors.append(f"Assign the {label.lower()} wheel")
                continue
            if wheel.type != "MESH":
                errors.append(f"{label} must be a mesh object")
            pointer = wheel.as_pointer()
            if pointer in seen:
                errors.append("Each wheel slot must reference a different object")
            seen.add(pointer)

    if errors or vehicle_root(vehicle) is None:
        return errors, warnings

    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    shape_offset = Vector(vehicle.chassis_shape_offset)
    centers = wheel_centers(vehicle, frame_inverse, shape_offset)
    if any(center is None for center in centers):
        errors.append("The four wheel centers could not be resolved")
        return errors, warnings
    fl, fr, rl, rr = centers
    try:
        vehicle_axle_geometry(centers)
    except ValueError as error:
        errors.append(str(error))
    if abs(fl.y - fr.y) > max(0.05, vehicle.axle_alignment_tolerance):
        warnings.append("Front wheel centers are not aligned on one axle")
    if abs(rl.y - rr.y) > max(0.05, vehicle.axle_alignment_tolerance):
        warnings.append("Rear wheel centers are not aligned on one axle")
    if abs(fl.z - fr.z) > max(0.05, vehicle.axle_alignment_tolerance):
        warnings.append("Front wheel heights differ")
    if abs(rl.z - rr.z) > max(0.05, vehicle.axle_alignment_tolerance):
        warnings.append("Rear wheel heights differ")
    from .vehicle_authoring_state import ensure_axle_authoring

    ensure_axle_authoring(vehicle, game_config)
    errors.extend(validate_powertrain(vehicle, total_mass_label="vehDriveModelData"))
    return errors, warnings


def vehicle_config(vehicle, *, include_powertrain=True, include_chassis_shapes=True):
    from .vehicle_authoring_state import apply_authored_vehicle_values

    frame = vehicle_actor_world(vehicle)
    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    shape_offset = Vector(vehicle.chassis_shape_offset)
    centers = [
        list(center) for center in wheel_centers(vehicle, frame_inverse, shape_offset)
    ]
    target_centers = [list(center) for center in centers]
    game_config = resolved_game_config(vehicle)
    config = apply_authored_vehicle_values(
        vehicle, game_config, include_powertrain=include_powertrain
    )
    center_offsets = config.get("wheel_center_offsets", ())
    if isinstance(center_offsets, list) and len(center_offsets) == 4:
        for center, target_center, offset in zip(
            centers, target_centers, center_offsets
        ):
            if isinstance(offset, list) and len(offset) == 3:
                for axis in range(3):
                    center[axis] += float(offset[axis])
                target_center[0] += float(offset[0])
                target_center[1] += float(offset[1])
    geometry = vehicle_axle_geometry(centers)
    config.update(
        {
            "pose": pose_from_matrix(frame),
            "chassis_dims": list(vehicle.chassis_dims),
            "chassis_mass": float(vehicle.chassis_mass),
            "chassis_cm_offset": [
                float(vehicle.chassis_cm_offset[index]) - float(shape_offset[index])
                for index in range(3)
            ],
            "wheel_centers": centers,
            "wheel_target_centers": target_centers,
            "wheelbase": geometry.wheelbase,
            "front_track": geometry.front_track,
            "rear_track": geometry.rear_track,
            "clutch_strength": float(vehicle.clutch_strength),
            "ackermann_accuracy": float(vehicle.ackermann_accuracy),
            "auto_gears": bool(vehicle.auto_gears),
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
            "ackermann_accuracy",
            "auto_gears",
            "gear_ratios",
            "gear_torque_multipliers",
            "autobox_up_ratios",
            "autobox_down_ratios",
            "final_gear_torque_decimation",
        ):
            config.pop(key, None)
    return config


def vehicle_live_dynamics_config(vehicle):
    """The values the built vehicle takes in place"""
    if getattr(vehicle, "vehicle_kind", "CAR") == "BIKE":
        from .vehicle_authoring_state import bike_vehicle_config

        config = bike_vehicle_config(vehicle, include_chassis_shapes=False)
    else:
        config = vehicle_config(vehicle, include_chassis_shapes=False)
    keys = (
        "chassis_mass",
        "chassis_inertia",
        "engine_peak_torque",
        "engine_max_omega",
        "engine_moi",
        "engine_damping_rate",
        "engine_torque_curve",
        "gear_switch_time",
        "gear_change_cooldown",
        "clutch_strength",
        "auto_gears",
        "ackermann_accuracy",
        "differential_type",
        "gear_ratios",
        "gear_torque_multipliers",
        "autobox_up_ratios",
        "autobox_down_ratios",
        "gear_min_speeds",
        "gear_max_speeds",
        "gear_min_engine_rpms",
        "gear_max_engine_rpms",
        "driven_wheel_indices",
        "vehicle_kind",
        "chassis_cm_offset",
        "wheel_centers",
        "wheel_target_centers",
        "wheel_radii",
        "wheel_widths",
        "wheel_masses",
        "wheel_moi_values",
        "wheel_damping_rates",
        "brake_torques",
        "handbrake_torques",
        "steer_angles",
        "wheel_vertical_offsets",
        "suspension_directions",
        "suspension_visual_lengths",
        "suspension_visual_droops",
        "suspension_compressions",
        "suspension_droops",
        "suspension_spring_strengths",
        "suspension_damper_rates",
        "suspension_compression_damper_rates",
        "suspension_rebound_damper_rates",
        "suspension_bound_damping_low_rates",
        "suspension_rebound_damping_low_rates",
        "suspension_damping_low_rate_compressions",
        "suspension_damping_high_rate_compressions",
        "suspension_extreme_compression_scalars",
        "tire_frictions",
        "tire_friction_coefficients",
        "tire_friction_longitudinal_multipliers",
        "tire_friction_lateral_multipliers",
        "tire_rolling_resistance_coefficients",
        "tire_longitudinal_stiffnesses",
        "tire_lateral_stiffness_x",
        "tire_lateral_stiffness_y",
        "anti_roll_stiffnesses",
        "anti_roll_displacement_limits",
        "anti_roll_length_scalars",
        "anti_swaybar_damping_scalar",
        "smooth_wheel_contact_increase_time",
        "smooth_wheel_contact_decrease_time",
        "turning_roll_factor",
        "steer_rise_rate",
        "steer_fall_rate",
        "bike_max_lean_angle",
        "bike_tilt_pid",
        "bike_tilt_speed",
        "bike_tilt_return_speed",
    )
    result = {key: config[key] for key in keys if key in config}
    wheel_count = 2 if result.get("vehicle_kind") == "BIKE" else 4
    per_wheel_fields = (
        "wheel_radii",
        "wheel_widths",
        "wheel_masses",
        "wheel_moi_values",
        "wheel_damping_rates",
        "brake_torques",
        "handbrake_torques",
        "steer_angles",
        "wheel_vertical_offsets",
        "suspension_visual_lengths",
        "suspension_visual_droops",
        "suspension_compressions",
        "suspension_droops",
        "suspension_spring_strengths",
        "suspension_damper_rates",
        "suspension_compression_damper_rates",
        "suspension_rebound_damper_rates",
        "suspension_bound_damping_low_rates",
        "suspension_rebound_damping_low_rates",
        "suspension_damping_low_rate_compressions",
        "suspension_damping_high_rate_compressions",
        "suspension_extreme_compression_scalars",
        "tire_frictions",
        "tire_friction_coefficients",
        "tire_friction_longitudinal_multipliers",
        "tire_friction_lateral_multipliers",
        "tire_rolling_resistance_coefficients",
        "tire_longitudinal_stiffnesses",
        "tire_lateral_stiffness_x",
        "tire_lateral_stiffness_y",
    )
    for field in per_wheel_fields:
        values = result.get(field)
        if not isinstance(values, (list, tuple)) or len(values) != wheel_count:
            raise ValueError(
                f"Internal live vehicle payload {field} must contain exactly {wheel_count} values"
            )
    directions = result.get("suspension_directions")
    if not isinstance(directions, (list, tuple)) or len(directions) != wheel_count:
        raise ValueError(
            f"Internal live vehicle payload suspension_directions must contain exactly {wheel_count} vectors"
        )
    for direction in directions:
        if not isinstance(direction, (list, tuple)) or len(direction) != 3:
            raise ValueError("Internal live suspension direction must be an XYZ vector")
    centers = result.get("wheel_centers")
    if not isinstance(centers, (list, tuple)) or len(centers) != wheel_count:
        raise ValueError(
            f"Internal live vehicle payload wheel_centers must contain exactly {wheel_count} vectors"
        )
    target_centers = result.get("wheel_target_centers")
    if (
        not isinstance(target_centers, (list, tuple))
        or len(target_centers) != wheel_count
    ):
        raise ValueError(
            f"Internal live vehicle payload wheel_target_centers must contain exactly {wheel_count} vectors"
        )
    if result.get("vehicle_kind") != "BIKE":
        for field in (
            "anti_roll_stiffnesses",
            "anti_roll_displacement_limits",
            "anti_roll_length_scalars",
        ):
            values = result.get(field)
            if not isinstance(values, (list, tuple)) or len(values) != 2:
                raise ValueError(
                    f"Internal live vehicle payload {field} must contain exactly two axle values"
                )
    return result


def vehicle_objects(scene):
    vehicle = getattr(scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.enabled:
        return set()
    result = set()
    if vehicle.source_mode == "RIG":
        try:
            names = json.loads(vehicle.resolved_object_names or "[]")
        except (TypeError, ValueError):
            names = ()
        for name in names:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                result.add(obj)
        return result
    if vehicle.chassis is not None:
        result.add(vehicle.chassis)
    if getattr(vehicle, "vehicle_kind", "CAR") == "BIKE":
        for wheel in (
            getattr(vehicle, "bike_front", None),
            getattr(vehicle, "bike_rear", None),
        ):
            if wheel is not None:
                result.add(wheel)
        return result
    for field, _label in WHEEL_FIELDS:
        wheel = getattr(vehicle, field, None)
        if wheel is not None:
            result.add(wheel)
    return result


def vehicle_simulation_excluded_objects(scene):
    result = set(vehicle_objects(scene))
    vehicle = getattr(scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.enabled:
        return result
    from ...blender.physics.vehicle_chassis import vehicle_chassis_phys_objects

    result.update(vehicle_chassis_phys_objects(scene, getattr(vehicle, "rig", None)))
    return result
