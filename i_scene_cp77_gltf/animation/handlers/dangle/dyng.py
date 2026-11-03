import numpy as np

from ....bartmoss.dynamics import clamp_damping_vectors
from ...domain.dangle import collision, constraints

DAMPING_ACCEL_LIMIT = 50.0
MIN_TIME_DILATION = 0.05
MAX_TIME_DILATION = 1.0
MAX_PHYSICS_STEPS = 3.0
LP_FILTER_RC = 1.0


def _interpolate_tracked_positions(system, frame_progress, workspace):
    indices = workspace["tracked_indices"]
    if indices.size:
        interpolated = workspace["tracked_interpolated_positions"]
        np.subtract(
            workspace["tracked_current_positions"],
            workspace["tracked_previous_positions"],
            out=interpolated,
        )
        interpolated *= frame_progress
        interpolated += workspace["tracked_previous_positions"]
        system.interp_bone_ms[indices] = interpolated
    extra_indices = workspace["tracked_extra_indices"]
    if extra_indices.size:
        system.pos_ms[extra_indices] = interpolated[workspace["tracked_extra_local"]]


def _compute_accelerations(system, workspace, grav_ms, ext_ms):
    node_slice = workspace["slice"]
    acceleration = workspace["acceleration"]
    external = workspace["external_acceleration"]
    damping = workspace["damping_acceleration"]
    pull = workspace["pull_acceleration"]

    acceleration[:] = grav_ms
    clamp_damping_vectors(
        system.vel_ms[node_slice],
        workspace["damping_factor"],
        DAMPING_ACCEL_LIMIT,
        out=damping,
        norm_buffer=workspace["damping_norm"],
        safe_buffer=workspace["damping_safe_norm"],
        clamped_buffer=workspace["clamped_damping"],
        mask_buffer=workspace["damping_limit_mask"],
    )
    acceleration += damping
    np.multiply(
        workspace["inverse_mass"][:, None],
        ext_ms,
        out=external,
    )
    acceleration += external
    np.subtract(
        system.interp_bone_ms[node_slice],
        system.pos_ms[node_slice],
        out=pull,
    )
    pull *= workspace["pull_factor"][:, None]
    acceleration += pull
    fixed_local = workspace["fixed_local"]
    if fixed_local.size:
        acceleration[fixed_local] = 0.0
    return acceleration


def _initialize_node_state(
    system, node_index, workspace, node_shapes, reset_positions, frames
):
    node_slice = workspace["slice"]
    if reset_positions:
        system.pos_ms[node_slice] = system.cur_bone_ms[node_slice]
        system.prev_pos_ms[node_slice] = system.cur_bone_ms[node_slice]

    system.vel_ms[node_slice] = 0.0
    system.prev_bone_ms[node_slice] = system.cur_bone_ms[node_slice]
    frames.reset_dyng_interpolation(node_index)

    system.node_prev_ext_force_ms[node_index] = system.node_cur_ext_force_ms[node_index]
    system.node_prev_grav_ms[node_index] = system.node_cur_grav_ms[node_index]
    frames.initialize_shapes(node_shapes)


def step_dyng_node(
    system, node_index, raw_dt, time_dilation, skip_physics, params, frames
):
    start, end = system.node_ranges[node_index]
    if start >= end:
        return
    workspace = system.node_workspaces[node_index]
    node_slice = workspace["slice"]
    substep_time = max(0.001, float(params.substep_time))
    needs_initialization = bool(system.node_simulation_needs_initialization[node_index])
    skip_node_physics = bool(skip_physics or needs_initialization)
    node_shapes = system.node_col_shapes[node_index]

    if skip_node_physics:
        _initialize_node_state(system, node_index, workspace, node_shapes, True, frames)
        system.node_simulation_needs_initialization[node_index] = False

    system.node_time_remainder[node_index] += raw_dt
    raw_steps = int(system.node_time_remainder[node_index] / substep_time)
    system.node_time_remainder[node_index] -= raw_steps * substep_time
    lp_alpha = raw_dt / (LP_FILTER_RC + raw_dt)
    system.node_damped_physics_steps[node_index] += lp_alpha * (
        raw_steps - system.node_damped_physics_steps[node_index]
    )
    physics_steps = int(round(system.node_damped_physics_steps[node_index]))
    physics_steps = max(1, min(physics_steps, int(MAX_PHYSICS_STEPS)))
    dt = min(MAX_TIME_DILATION, time_dilation) * substep_time

    # Consume the accumulator and update the filtered step count
    # before deciding whether time dilation permits the actual physics loop.
    if time_dilation <= MIN_TIME_DILATION:
        if skip_node_physics:
            _initialize_node_state(
                system, node_index, workspace, node_shapes, False, frames
            )
        return

    frames.begin_shapes(node_shapes)
    iterations = max(1, int(params.solver_iterations))
    position = system.pos_ms[node_slice]
    previous_position = system.prev_pos_ms[node_slice]
    velocity = system.vel_ms[node_slice]
    interpolated_bone = system.interp_bone_ms[node_slice]
    free_local = workspace["free_local"]
    fixed_local = workspace["fixed_local"]

    for step_index in range(physics_steps):
        frame_progress = (step_index + 1.0) / physics_steps
        _interpolate_tracked_positions(system, frame_progress, workspace)
        frame = frames.dyng_frame(node_index, frame_progress)
        frames.pose_shapes(node_shapes, frame_progress)
        interpolated_external = workspace["interpolated_external"]
        np.subtract(
            system.node_cur_ext_force_ms[node_index],
            system.node_prev_ext_force_ms[node_index],
            out=interpolated_external,
        )
        interpolated_external *= frame_progress
        interpolated_external += system.node_prev_ext_force_ms[node_index]
        interpolated_gravity = workspace["interpolated_gravity"]
        np.subtract(
            system.node_cur_grav_ms[node_index],
            system.node_prev_grav_ms[node_index],
            out=interpolated_gravity,
        )
        interpolated_gravity *= frame_progress
        interpolated_gravity += system.node_prev_grav_ms[node_index]
        previous_position[:] = position

        if skip_node_physics:
            if fixed_local.size:
                position[fixed_local] = interpolated_bone[fixed_local]
        else:
            acceleration = _compute_accelerations(
                system, workspace, interpolated_gravity, interpolated_external
            )
            half_velocity = workspace["half_velocity"]
            predicted_position = workspace["predicted_position"]
            np.multiply(acceleration, dt * 0.5, out=half_velocity)
            half_velocity += velocity
            np.multiply(half_velocity, dt, out=predicted_position)
            predicted_position += position
            if workspace["all_free"]:
                position[:] = predicted_position
            else:
                if free_local.size:
                    position[free_local] = predicted_position[free_local]
                if fixed_local.size:
                    position[fixed_local] = interpolated_bone[fixed_local]

        for _iteration in range(iterations):
            constraints.satisfy_in_authored_order(system, node_index, frame)
            collision.respond_to_collisions(
                system, node_shapes, workspace, frame.directed_axes
            )
            constraints.respond_cone_collisions_in_authored_order(
                system, node_index, node_shapes, frame
            )

        if not skip_node_physics and dt > 0.0:
            acceleration = _compute_accelerations(
                system, workspace, interpolated_gravity, interpolated_external
            )
            corrected_velocity = workspace["corrected_velocity"]
            np.subtract(position, previous_position, out=corrected_velocity)
            corrected_velocity *= 1.0 / dt
            half_velocity = workspace["half_velocity"]
            np.multiply(acceleration, dt * 0.5, out=half_velocity)
            corrected_velocity += half_velocity
            if workspace["all_free"]:
                velocity[:] = corrected_velocity
            else:
                velocity.fill(0.0)
                if free_local.size:
                    velocity[free_local] = corrected_velocity[free_local]

    if skip_node_physics:
        _initialize_node_state(
            system, node_index, workspace, node_shapes, False, frames
        )


def step_position_projection_node(system, node_index, params, frames):
    if not system.single_particle_node_is_valid(
        system.position_projection_nodes, node_index
    ):
        return

    runtime = system.position_projection_nodes[node_index]
    particle_index = runtime["particle_index"]
    node_shapes = system.node_col_shapes[node_index]

    frames.begin_shapes(node_shapes)
    frames.pose_shapes(node_shapes, 1.0)

    desired_position = system.cur_bone_ms[particle_index].copy()
    if params.projection_type == "SHORTEST_PATH":
        for shape in node_shapes:
            desired_position = collision.project_shortest_path_position(
                shape, desired_position, params.capsule_radius
            )
    elif params.projection_type == "DIRECTIONAL":
        reference_index = runtime["reference_index"]
        if reference_index >= 0 and system.active_mask[reference_index]:
            axis_ms = (
                system.cur_bone_ms[reference_index] - system.cur_bone_ms[particle_index]
            )
        else:
            axis_ms = frames.current_bone_axis(particle_index)
        axis_length = float(np.linalg.norm(axis_ms))
        if axis_length > 1e-8:
            axis_ms = axis_ms / axis_length
            for shape in node_shapes:
                desired_position = collision.project_directional_capsule_position(
                    shape,
                    desired_position,
                    axis_ms,
                    params.capsule_height,
                    params.capsule_radius,
                )

    system.prev_pos_ms[particle_index] = system.pos_ms[particle_index]
    system.pos_ms[particle_index] = desired_position
    system.vel_ms[particle_index] = 0.0
