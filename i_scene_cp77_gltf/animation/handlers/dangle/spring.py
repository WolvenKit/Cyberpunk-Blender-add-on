import numpy as np

from ....bartmoss import single
from ....bartmoss.dynamics import damping_force
from ...domain.dangle.collision import project_shortest_path_position
from ...domain.dangle.frame_time import SmoothedFrameTime, fixed_rate_steps

_MIN_DIRECTION_LENGTH = 0.0001
_DAMPING_ACCELERATION_LIMIT = 50.0


def spring_node(particle_index, parent_index):
    return {
        "particle_index": particle_index,
        "parent_index": parent_index,
        "needs_initialization": True,
        "frame_time_calculator": SmoothedFrameTime(),
    }


def _calculate_acceleration(
    params,
    pull_origin_ms,
    position_ms,
    velocity_ms,
    gravity_acceleration_ms,
    external_force_ms,
):
    mass = max(0.01, float(params.mass))
    inverse_mass = 1.0 / mass
    pull_force = (
        np.asarray(pull_origin_ms, dtype=np.float64)
        - np.asarray(position_ms, dtype=np.float64)
    ) * float(params.pull_force)
    damping = damping_force(
        velocity_ms,
        params.damping,
        mass,
        _DAMPING_ACCELERATION_LIMIT,
    )
    net_force = pull_force + damping + np.asarray(external_force_ms, dtype=np.float64)
    return net_force * inverse_mass + np.asarray(
        gravity_acceleration_ms, dtype=np.float64
    )


def _clamp_to_constraint(params, frame, position_ms):
    radius = max(0.0, float(params.constraint_radius))
    parent_position = np.asarray(frame.parent_position, dtype=np.float64)
    if radius == 0.0:
        return parent_position.copy()

    parent_to_bob = np.asarray(position_ms, dtype=np.float64) - parent_position
    parent_to_bob_length = float(np.linalg.norm(parent_to_bob))
    if parent_to_bob_length <= _MIN_DIRECTION_LENGTH:
        return np.asarray(position_ms, dtype=np.float64)

    normalized_ms = single.vec3(*(parent_to_bob / parent_to_bob_length).tolist())
    normalized_es = single.rotate(frame.inverse, normalized_ms)

    sx = radius
    sy = radius
    scale = (
        max(0.01, float(params.constraint_scale1))
        if normalized_es[2] < 0.0
        else max(0.01, float(params.constraint_scale2))
    )
    sz = radius * scale
    scaled = single.vec3(
        normalized_es[0] / sx,
        normalized_es[1] / sy,
        normalized_es[2] / sz,
    )
    scaled_length = single.length(scaled)
    if scaled_length <= 1e-12:
        return np.asarray(position_ms, dtype=np.float64)
    max_distance = 1.0 / scaled_length

    if parent_to_bob_length > max_distance:
        adjustment_es = single.vec3(
            normalized_es[0] / (sx * sx),
            normalized_es[1] / (sy * sy),
            normalized_es[2] / (sz * sz),
        )
        adjustment_ms = single.rotate(frame.rotation, adjustment_es)
        if single.length_squared(adjustment_ms) > 1e-12:
            adjustment_ms = single.normalized(adjustment_ms)
            vector_ms = single.vec3(*parent_to_bob.tolist())
            surface_vector_ms = single.scale(normalized_ms, max_distance)
            vector_ms = single.sub(
                vector_ms,
                single.scale(
                    adjustment_ms,
                    (
                        single.dot(adjustment_ms, vector_ms)
                        - single.dot(adjustment_ms, surface_vector_ms)
                    ),
                ),
            )
            parent_to_bob = np.asarray(vector_ms, dtype=np.float64)

    corrected_length = float(np.linalg.norm(parent_to_bob))
    biggest_extent = max(sx, sz)
    if corrected_length > biggest_extent and corrected_length > 0.0:
        parent_to_bob *= biggest_extent / corrected_length
    return parent_position + parent_to_bob


def step_spring_node(
    system, node_index, raw_dt, time_dilation, skip_physics, params, frames
):
    """Advance one spring node, or return False when the node cannot run"""
    if not system.single_particle_node_is_valid(system.spring_nodes, node_index):
        return False

    runtime = system.spring_nodes[node_index]
    particle_index = int(runtime["particle_index"])
    node_shapes = system.node_col_shapes[node_index]
    position = system.pos_ms
    velocity = system.vel_ms

    frames.begin_shapes(node_shapes)

    calculator = runtime["frame_time_calculator"]
    calculator.recalculate(max(0.0, float(raw_dt)) * max(0.0, float(time_dilation)))
    dt, time_steps = fixed_rate_steps(
        calculator.average_frame_time, max(10.0, float(params.simulation_fps))
    )

    if skip_physics:
        runtime["needs_initialization"] = True

    if not runtime["needs_initialization"]:
        gravity_acceleration_ms = system.node_cur_grav_ms[node_index]
        external_force_ms = system.node_cur_ext_force_ms[node_index]
        shortest_path = params.projection_type == "SHORTEST_PATH"

        for step_index in range(time_steps):
            previous_position = position[particle_index].copy()
            frame_progress = (step_index + 1.0) / time_steps
            frame = frames.spring_frame(node_index, frame_progress)

            acceleration = _calculate_acceleration(
                params,
                frame.pull_origin,
                position[particle_index],
                velocity[particle_index],
                gravity_acceleration_ms,
                external_force_ms,
            )
            velocity[particle_index] += acceleration * (dt * 0.5)
            position[particle_index] += velocity[particle_index] * dt

            if shortest_path:
                frames.pose_shapes(node_shapes, frame_progress)
                for shape in node_shapes:
                    position[particle_index] = project_shortest_path_position(
                        shape,
                        position[particle_index],
                        params.collision_radius,
                    )

            position[particle_index] = _clamp_to_constraint(
                params, frame, position[particle_index]
            )

            if dt != 0.0:
                acceleration = _calculate_acceleration(
                    params,
                    frame.pull_origin,
                    position[particle_index],
                    velocity[particle_index],
                    gravity_acceleration_ms,
                    external_force_ms,
                )
                velocity[particle_index] = (
                    position[particle_index] - previous_position
                ) / dt + acceleration * (0.5 * dt)

        if not (
            np.all(np.isfinite(position[particle_index]))
            and np.all(np.isfinite(velocity[particle_index]))
        ):
            runtime["needs_initialization"] = True

    if runtime["needs_initialization"]:
        velocity[particle_index] = 0.0
        position[particle_index] = np.asarray(
            frames.spring_rest_position(node_index), dtype=np.float32
        )
        runtime["needs_initialization"] = False

    system.prev_pos_ms[particle_index] = position[particle_index]
    return True
