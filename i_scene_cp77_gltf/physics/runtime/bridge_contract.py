VEHICLE_STATE_CONTRACT = 21
VEHICLE_REQUIRED_FEATURES = (
    "vehicle_live_dynamics",
    "vehicle_live_powertrain",
    "vehicle_state_transfer",
    "vehicle_chassis_shapes",
    "vehicle_cp77_wheel_mapping",
    "vehicle_live_anti_roll",
    "vehicle_live_tire_stiffness",
    "vehicle_suspension_directions",
    "vehicle_cp77_affine_gears",
    "vehicle_shape_inertia",
    "vehicle_cp77_wheel_solver",
    "vehicle_wheel_telemetry",
    "vehicle_smoothed_tire_load",
    "vehicle_isolated_cp77_forces",
    "vehicle_cp77_impulse_timing",
    "vehicle_low_speed_friction_clamp",
    "vehicle_two_phase_tire_forces",
    "vehicle_cp77_traction_curves",
    "vehicle_cp77_traction_required",
    "vehicle_game_gearbox",
)


def validate_vehicle_build_info(build_info, *, bridge_label="pxbridge.pyd") -> None:
    if not isinstance(build_info, dict):
        raise RuntimeError(
            f"{bridge_label} returned invalid build metadata. "
            "Rebuild this Blender/Python ABI slot from the current native source."
        )
    if int(build_info.get("vehicle_state", 0)) < VEHICLE_STATE_CONTRACT:
        raise RuntimeError(
            f"{bridge_label} does not implement vehicle state contract {VEHICLE_STATE_CONTRACT}. "
            "Rebuild this Blender/Python ABI slot from the current native source."
        )
    missing = tuple(
        name
        for name in VEHICLE_REQUIRED_FEATURES
        if not bool(build_info.get(name, False))
    )
    if missing:
        raise RuntimeError(
            f"{bridge_label} is missing required vehicle contract-{VEHICLE_STATE_CONTRACT} feature(s): "
            + ", ".join(missing)
        )


VEHICLE_REQUIRED_CALLABLES = (
    "build_vehicle",
    "update_inputs",
    "update_vehicle_dynamics",
    "get_vehicle_dynamic_state",
    "get_stats",
    "get_build_info",
)


def validate_vehicle_bridge_contract(module, *, bridge_label="PxBridge") -> dict:
    missing = tuple(
        name
        for name in VEHICLE_REQUIRED_CALLABLES
        if not callable(getattr(module, name, None))
    )
    if missing:
        raise RuntimeError(
            f"{bridge_label} is missing vehicle functions: " + ", ".join(missing)
        )
    build_info = module.get_build_info()
    validate_vehicle_build_info(build_info, bridge_label=bridge_label)
    return build_info


CURRENT_BRIDGE_REQUIRED_CALLABLES = (
    "init",
    "shutdown",
    "reset",
    "is_initialized",
    "set_gravity",
    "build_vehicle",
    "update_inputs",
    "update_vehicle_dynamics",
    "get_vehicle_dynamic_state",
    "get_stats",
    "get_build_info",
    "nvcloth_init",
    "nvcloth_shutdown",
    "nvcloth_reset",
    "nvcloth_is_initialized",
    "nvcloth_is_step_in_flight",
    "nvcloth_get_cloth_count",
    "nvcloth_get_fabric_count",
    "nvcloth_get_fabric_info",
    "nvcloth_cook_fabric",
    "nvcloth_load_fabric",
    "nvcloth_release_fabric",
    "nvcloth_create_cloth",
    "nvcloth_remove_cloth",
    "nvcloth_begin_step",
    "nvcloth_end_step",
    "nvcloth_get_particles",
    "nvcloth_get_velocities",
    "nvcloth_set_particles",
    "nvcloth_set_inv_masses",
    "nvcloth_set_motion_constraints",
    "nvcloth_clear_motion_constraints",
    "nvcloth_set_motion_constraint_scale_bias",
    "nvcloth_set_motion_constraint_stiffness",
    "nvcloth_set_separation_constraints",
    "nvcloth_clear_separation_constraints",
    "nvcloth_set_solver_frequency",
    "nvcloth_set_gravity",
    "nvcloth_set_damping",
    "nvcloth_set_linear_drag",
    "nvcloth_set_stiffness_frequency",
    "nvcloth_set_tether_constraint_scale",
    "nvcloth_set_tether_constraint_stiffness",
    "nvcloth_set_self_collision_distance",
    "nvcloth_set_self_collision_stiffness",
    "nvcloth_set_friction",
    "nvcloth_enable_continuous_collision",
    "nvcloth_set_collision_mass_scale",
    "nvcloth_set_phase_config",
    "nvcloth_set_drag_coefficient",
    "nvcloth_set_translation",
    "nvcloth_set_rotation",
    "nvcloth_teleport",
    "nvcloth_clear_inertia",
    "nvcloth_set_spheres",
    "nvcloth_set_capsules",
    "nvcloth_set_triangles",
    "nvcloth_get_collider_counts",
    "nvcloth_set_stabilization_enabled",
    "nvcloth_get_stabilization_enabled",
    "nvcloth_get_recovered_particle_count",
)


def missing_current_bridge_callables(module) -> tuple[str, ...]:
    return tuple(
        name
        for name in CURRENT_BRIDGE_REQUIRED_CALLABLES
        if not callable(getattr(module, name, None))
    )


# Behaviour a current bridge reports in its build metadata.
BRIDGE_REQUIRED_FEATURES = (
    # Cooked shapes from game and project files are checked before the SDK reads them.
    "cooked_shape_validation",
)


def validate_current_bridge_contract(module) -> None:
    missing = missing_current_bridge_callables(module)
    if missing:
        raise RuntimeError(
            "pxbridge.pyd does not match the current native bridge contract. "
            "Rebuild this Blender/Python ABI slot from the current native source. "
            f"Missing callable(s): {', '.join(missing)}"
        )
    build_info = module.get_build_info()
    validate_vehicle_build_info(build_info)
    missing = tuple(
        name for name in BRIDGE_REQUIRED_FEATURES if build_info.get(name) is not True
    )
    if missing:
        raise RuntimeError(
            "pxbridge.pyd does not match the current native bridge contract. "
            "Rebuild this Blender/Python ABI slot from the current native source. "
            f"Missing feature(s): {', '.join(missing)}"
        )
