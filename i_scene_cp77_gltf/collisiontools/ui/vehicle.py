import math

from ...physics.domain.vehicle.game_data import vehicle_record_label

_CAR_WHEELS = (
    ("front_left", "Front Left"),
    ("front_right", "Front Right"),
    ("rear_left", "Rear Left"),
    ("rear_right", "Rear Right"),
)
_BIKE_WHEELS = (("bike_front", "Front"), ("bike_rear", "Rear"))
# The axle fields Advanced shows, with their labels; the game names are the fields' names, in their tooltips.
_ADVANCED_AXLE = (
    ("extreme_compression_event_scalor", "Full Compression Force"),
    ("spring_bound_damping_low_rate", "Slow Bump Damping"),
    ("spring_damping_high_rate_compression", "Fast Damping Depth"),
    ("spring_damping_low_rate_compression", "Slow Damping Depth"),
    ("spring_rebound_damping_low_rate", "Slow Rebound Damping"),
    ("swaybar_length_scalar", "Anti-Roll Lever Scale"),
    ("swaybar_displacement_limit", "Anti-Roll Travel Limit"),
    ("tender_spring_length", "Tender Spring Length"),
    ("tire_lateral_slip_effects_mul", "Side Slip Effects"),
    ("tire_longitudinal_slip_effects_mul", "Forward Slip Effects"),
    ("tire_rolling_resistance_coef", "Rolling Resistance"),
)


def _gear_label(value):
    value = int(value)
    if value == 0:
        return "R"
    if value == 1:
        return "N"
    return str(value - 1)


def _fields(layout):
    column = layout.column(align=True)
    column.use_property_split = True
    column.use_property_decorate = False
    return column


def _alert(layout, text):
    row = layout.row()
    row.alert = True
    row.label(text=text, icon="ERROR")


def _header(layout, vehicle):
    row = layout.row(align=True)
    row.prop(vehicle, "enabled", text="Vehicle", toggle=True)
    if not vehicle.enabled:
        return
    row.prop(vehicle, "vehicle_kind", text="")
    row.prop(vehicle, "ui_show_advanced", text="", toggle=True, icon="PREFERENCES")
    layout.row(align=True).prop(vehicle, "authoring_page", expand=True)


def _onboarding(layout, vehicle):
    box = layout.box()
    box.row().prop(vehicle, "vehicle_kind", expand=True)
    box.row().prop(vehicle, "source_mode", expand=True)
    row = box.row()
    row.scale_y = 1.3
    if vehicle.source_mode == "RIG":
        row.operator(
            "physx.vehicle_setup_selection",
            text="Use Selected Rig",
            icon="ARMATURE_DATA",
        )
    else:
        row.operator(
            "physx.vehicle_setup_manual", text="Use Selected Meshes", icon="EYEDROPPER"
        )


def _source(layout, vehicle):
    box = layout.box()
    box.row().prop(vehicle, "source_mode", expand=True)
    wheels = _BIKE_WHEELS if vehicle.vehicle_kind == "BIKE" else _CAR_WHEELS
    if vehicle.source_mode == "RIG":
        row = box.row(align=True)
        row.prop(vehicle, "rig", text="")
        row.operator("physx.vehicle_setup_selection", text="", icon="EYEDROPPER")
        row.operator("physx.vehicle_autofit", text="", icon="FILE_REFRESH")
        if vehicle.ui_show_advanced:
            column = _fields(box)
            for field, label in wheels:
                column.prop(vehicle, f"{field}_bone", text=label)
            box.prop(vehicle, "refresh_rig_on_build")
    else:
        column = _fields(box)
        column.prop(vehicle, "chassis")
        for field, label in wheels:
            column.prop(vehicle, field, text=label)
        row = box.row(align=True)
        row.operator(
            "physx.vehicle_setup_manual", text="Use Selection", icon="EYEDROPPER"
        )
        row.operator("physx.vehicle_autofit", text="Fit", icon="FILE_REFRESH")
    if vehicle.ui_show_advanced:
        column = _fields(box)
        column.prop(vehicle, "forward_axis")
        column.prop(vehicle, "axle_alignment_tolerance")


def _game_data(layout, vehicle):
    box = layout.box()
    box.label(text="Game Data")
    row = box.row(align=True)
    if vehicle.source_mode == "RIG":
        row.operator("physx.vehicle_load_game_data", icon="IMPORT")
    row.operator("physx.vehicle_apply_archetype", text="Apply Base Vehicle")
    if vehicle.game_data_enabled:
        row = box.row(align=True)
        row.label(text=vehicle_record_label(vehicle.game_data_record) or "Game vehicle")
        row.operator("physx.vehicle_clear_data", text="", icon="X")
    if vehicle.ui_show_advanced:
        column = _fields(box)
        column.prop(vehicle, "vehicle_tweak_root")
        column.prop(vehicle, "vehicle_resource_root")
        column.prop(vehicle, "game_data_record_override")


def _setup_page(layout, vehicle):
    _source(layout, vehicle)
    _game_data(layout, vehicle)


def _chassis(layout, vehicle):
    box = layout.box()
    box.label(text="Chassis")
    column = _fields(box)
    column.prop(vehicle, "chassis_mass", text="Mass")
    column.prop(vehicle, "chassis_cm_offset", text="Center of Mass")
    column.prop(vehicle, "front_steer_angle", text="Max Steering Angle")
    column.prop(vehicle, "wheel_turn_max_add_per_second", text="Steering Speed")
    column.prop(vehicle, "wheel_turn_max_sub_per_second", text="Return Speed")
    column.prop(vehicle, "rear_handbrake_torque", text="Handbrake Torque")
    column.prop(vehicle, "use_chassis_inertia", text="Custom Inertia")
    if vehicle.use_chassis_inertia:
        column.prop(vehicle, "chassis_inertia", text="Inertia")
    if vehicle.ui_show_advanced:
        column.separator()
        column.prop(vehicle, "chassis_dims", text="Collider Size")
        column.prop(vehicle, "chassis_shape_offset", text="Collider Center")
        column.prop(vehicle, "ackermann_accuracy", text="Ackermann")
        column.prop(vehicle, "total_mass", text="Total Mass")
        column.prop(vehicle, "air_resistance_factor", text="Air Resistance")
        column.prop(vehicle, "braking_friction_factor", text="Braking Friction")
        column.prop(vehicle, "turning_roll_factor", text="Turning Roll")


def _axle(layout, vehicle, axle):
    box = layout.box()
    box.row().prop(vehicle, "axle_authoring_view", expand=True)
    column = _fields(box)
    column.prop(axle, "tire_radius", text="Tire Radius")
    column.prop(axle, "tire_width", text="Tire Width")
    column.prop(axle, "wheel_offset", text="Wheel Offset")
    column.prop(axle, "mass", text="Wheel Mass")
    column.prop(axle, "max_braking_torque", text="Brake Torque")
    column.separator()
    column.prop(axle, "logical_suspension_compression_length", text="Suspension Travel")
    column.prop(axle, "visual_suspension_droop", text="Droop")
    column.prop(axle, "spring_stiffness", text="Spring Stiffness")
    column.prop(axle, "spring_damping", text="Bump Damping")
    column.prop(axle, "spring_rebound_damping", text="Rebound Damping")
    column.prop(axle, "swaybar_stiffness", text="Anti-Roll")
    column.prop(axle, "wheels_vertical_offset", text="Ride Height Offset")
    column.separator()
    column.prop(axle, "tire_friction_coef", text="Tire Grip")
    column.prop(axle, "friction_mul_longitudinal", text="Forward Grip")
    column.prop(axle, "friction_mul_lateral", text="Side Grip")
    if vehicle.ui_show_advanced:
        column.separator()
        column.prop(axle, "rim_radius", text="Rim Radius")
        column.prop(axle, "visual_suspension_compression_length", text="Visual Travel")
        for prop, label in _ADVANCED_AXLE:
            column.prop(axle, prop, text=label)


def _wheel_roles(layout, vehicle):
    box = layout.box()
    if vehicle.vehicle_kind == "BIKE":
        entries = (
            ("Front", vehicle.wheel_role_front),
            ("Rear", vehicle.wheel_role_back),
        )
    else:
        entries = (
            ("Front Left", vehicle.wheel_role_lf),
            ("Front Right", vehicle.wheel_role_rf),
            ("Rear Left", vehicle.wheel_role_lb),
            ("Rear Right", vehicle.wheel_role_rb),
        )
    grid = box.grid_flow(row_major=True, columns=4, even_columns=False, align=True)
    for text in ("", "Drive", "Brake", "Handbrake"):
        grid.label(text=text)
    for label, role in entries:
        grid.label(text=label)
        grid.prop(role, "is_drive", text="")
        grid.prop(role, "is_main_brake", text="")
        grid.prop(role, "is_hand_brake", text="")


def _bike(layout, vehicle):
    box = layout.box()
    box.label(text="Lean")
    column = _fields(box)
    column.prop(vehicle, "bike_max_lean_angle", text="Max Lean")
    column.prop(vehicle, "bike_tilt_speed", text="Lean Speed")
    column.prop(vehicle, "bike_tilt_return_speed", text="Return Speed")
    if vehicle.ui_show_advanced:
        column.prop(vehicle, "bike_tilt_pid", text="Lean PID")


def _wheels_page(layout, vehicle):
    if vehicle.live_update_error:
        _alert(layout, vehicle.live_update_error)
    layout.prop(vehicle, "show_authoring_guides", toggle=True, icon="OVERLAY")
    _chassis(layout, vehicle)
    axle = (
        vehicle.front_axle
        if vehicle.axle_authoring_view == "FRONT"
        else vehicle.rear_axle
    )
    _axle(layout, vehicle, axle)
    _wheel_roles(layout, vehicle)
    if vehicle.vehicle_kind == "BIKE":
        _bike(layout, vehicle)


def _gearbox(layout, vehicle):
    box = layout.box()
    row = box.row(align=True)
    row.label(text="Gears")
    row.operator("physx.vehicle_gear_reset", text="", icon="FILE_REFRESH")
    if not vehicle.gears:
        box.operator("physx.vehicle_gear_reset", text="Create Gearbox", icon="ADD")
        return
    row = box.row()
    row.template_list(
        "PHYSX_UL_vehicle_gear_list",
        "",
        vehicle,
        "gears",
        vehicle,
        "gear_index",
        rows=max(4, min(len(vehicle.gears), 10)),
    )
    controls = row.column(align=True)
    controls.operator("physx.vehicle_gear_add", text="", icon="ADD")
    controls.operator("physx.vehicle_gear_remove", text="", icon="REMOVE")
    controls.separator()
    controls.operator(
        "physx.vehicle_gear_move", text="", icon="TRIA_UP"
    ).direction = "UP"
    controls.operator(
        "physx.vehicle_gear_move", text="", icon="TRIA_DOWN"
    ).direction = "DOWN"
    index = min(max(int(vehicle.gear_index), 0), len(vehicle.gears) - 1)
    item = vehicle.gears[index]
    column = _fields(box)
    column.prop(item, "min_speed", text="Min Speed")
    column.prop(item, "max_speed", text="Max Speed")
    column.prop(item, "min_engine_rpm", text="Min RPM")
    column.prop(item, "max_engine_rpm", text="Max RPM")
    column.prop(item, "torque_multiplier", text="Torque Scale")


def _engine_page(layout, vehicle):
    if vehicle.live_update_error:
        _alert(layout, vehicle.live_update_error)
    box = layout.box()
    box.label(text="Engine")
    column = _fields(box)
    column.prop(vehicle, "engine_peak_torque", text="Torque")
    column.prop(vehicle, "engine_max_rpm", text="Max RPM")
    column.prop(vehicle, "engine_moi", text="Flywheel Inertia")
    column.prop(vehicle, "engine_resistance_torque", text="Engine Braking")
    column.prop(vehicle, "gear_switch_time", text="Shift Time")
    column.prop(vehicle, "final_gear_torque_decimation", text="Top Gear Torque")
    column.prop(vehicle, "auto_gears", text="Automatic")
    if vehicle.ui_show_advanced:
        column.prop(vehicle, "clutch_strength", text="Clutch Strength")
    _gearbox(layout, vehicle)


def _drive_page(layout, vehicle):
    box = layout.box()
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator(
        "physx.vehicle_build",
        text="Rebuild" if vehicle.preview_built else "Build",
        icon="PLAY",
    )
    row.operator("physx.vehicle_reset", text="Reset", icon="LOOP_BACK")
    if vehicle.preview_built and vehicle.preview_dirty:
        _alert(box, "Rebuild to apply the geometry change")
    row = box.row(align=True)
    row.prop(vehicle, "preview_auto_ground", text="Ground Plane", toggle=True)
    row.prop(vehicle, "show_authoring_guides", toggle=True, icon="OVERLAY")
    row = box.row(align=True)
    row.prop(vehicle, "game_camera", toggle=True, icon="VIEW_CAMERA")
    sub = row.row(align=True)
    sub.active = vehicle.game_camera
    sub.prop(vehicle, "game_camera_height", text="")
    sub.prop(vehicle, "game_camera_distance", text="")

    inputs = layout.box()
    column = inputs.column(align=True)
    column.enabled = bool(vehicle.preview_built and not vehicle.preview_dirty)
    column.prop(vehicle, "throttle", slider=True)
    column.prop(vehicle, "brake", slider=True)
    column.prop(vehicle, "steer", slider=True)
    column.prop(vehicle, "handbrake", slider=True)
    inputs.label(text="W/S drive · A/D steer · Space handbrake")

    if not vehicle.preview_built:
        return
    telemetry = layout.box()
    row = telemetry.row()
    row.label(text=f"{vehicle.forward_speed * 3.6:.0f} km/h")
    row.label(text=f"Gear {_gear_label(vehicle.current_gear)}")
    row.label(text=f"{vehicle.engine_omega * 60.0 / (2.0 * math.pi):.0f} RPM")
    if vehicle.vehicle_in_air:
        telemetry.label(text="Airborne")
    if vehicle.vehicle_kind == "BIKE":
        telemetry.label(text=f"Lean {math.degrees(vehicle.bike_lean):+.0f}°")
    labels = (
        ("Front", "Rear")
        if vehicle.vehicle_kind == "BIKE"
        else ("Front Left", "Front Right", "Rear Left", "Rear Right")
    )
    grid = telemetry.grid_flow(
        row_major=True, columns=3, even_columns=False, align=True
    )
    for text in ("", "Compression", "Load"):
        grid.label(text=text)
    for index, label in enumerate(labels):
        grid.label(text=label)
        grid.label(text=f"{vehicle.wheel_compression[index] * 100.0:.1f} cm")
        grid.label(text=f"{vehicle.wheel_normal_load[index] / 1000.0:.2f} kN")
    if vehicle.ui_show_advanced:
        grid = telemetry.grid_flow(
            row_major=True, columns=3, even_columns=False, align=True
        )
        for text in ("", "Slip", "Tire Force"):
            grid.label(text=text)
        for index, label in enumerate(labels):
            grid.label(text=label)
            grid.label(
                text=f"{vehicle.wheel_longitudinal_slip[index]:+.2f} / {vehicle.wheel_lateral_slip[index]:+.2f}"
            )
            grid.label(
                text=f"{vehicle.wheel_longitudinal_force[index] / 1000.0:+.2f} / {vehicle.wheel_lateral_force[index] / 1000.0:+.2f} kN"
            )


def _export_page(layout, vehicle):
    box = layout.box()
    column = _fields(box)
    column.prop(vehicle, "tweakxl_record_id", text="Record")
    column.prop(vehicle, "tweakxl_base_record", text="Based On")
    column.prop(vehicle, "tweakxl_add_to_vehicle_list")
    row = box.row()
    row.scale_y = 1.3
    row.operator("physx.vehicle_export_tweakxl", text="Export TweakXL", icon="EXPORT")
    box.operator("physx.vehicle_validate", text="Check Vehicle")
    for message in vehicle.validation_errors.splitlines():
        _alert(box, message)
    for message in vehicle.validation_warnings.splitlines():
        box.label(text=message)


def draw_vehicle(layout, context):
    vehicle = context.scene.physx_vehicle
    _header(layout, vehicle)
    if not vehicle.enabled:
        _onboarding(layout, vehicle)
        return
    page = vehicle.authoring_page
    if page == "SETUP":
        _setup_page(layout, vehicle)
    elif page == "DYNAMICS":
        _wheels_page(layout, vehicle)
    elif page == "POWERTRAIN":
        _engine_page(layout, vehicle)
    elif page == "PREVIEW":
        _drive_page(layout, vehicle)
    else:
        _export_page(layout, vehicle)
