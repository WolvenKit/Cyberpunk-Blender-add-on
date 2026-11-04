import math

import numpy as np

from ....bartmoss import single
from ....bartmoss.dynamics import damping_force
from ....bartmoss.rounded_shapes import (
    directed_rotational_projection,
    rounded_box_signed_distance,
    shortest_path_rotational_projection,
    swept_capsule_box_overlap,
)
from ...domain.dangle.frame_time import SmoothedFrameTime, fixed_rate_steps

_DAMPING_ACCELERATION_LIMIT = 50.0
_EPS = 1e-8


def pendulum_node(particle_index, parent_index, axis_length):
    return {
        "particle_index": particle_index,
        "parent_index": parent_index,
        "axis_length": float(axis_length),
        "needs_initialization": True,
        "frame_time_calculator": SmoothedFrameTime(),
    }


def _constrain_direction(direction, frame, params):
    initial_axis = frame.initial_axis
    orthogonal_axis = frame.orthogonal_axis
    v = direction
    if params.constraint_type == "HINGE_PLANE":
        v = single.sub(v, single.scale(orthogonal_axis, single.dot(orthogonal_axis, v)))
    elif params.constraint_type == "HALF_CONE":
        dot = single.dot(orthogonal_axis, v)
        if dot > 0.0:
            v = single.sub(v, single.scale(orthogonal_axis, dot))
    if single.length_squared(v) <= _EPS:
        v = initial_axis
    else:
        v = single.normalized(v)
    cos_half = math.cos(math.radians(params.half_angle))
    if single.dot(initial_axis, v) < cos_half:
        perpendicular = single.cross(initial_axis, v)
        if single.length_squared(perpendicular) <= _EPS:
            perpendicular = orthogonal_axis
        perpendicular = single.normalized(perpendicular)
        rotation = single.axis_angle_quat(
            perpendicular, params.half_sine, params.half_cosine
        )
        v = single.normalized(single.rotate(rotation, initial_axis))
    return v


def _calculate_acceleration(
    params, pull_direction_ms, velocity_ms, gravity_ms, external_force_ms
):
    mass = max(0.01, float(params.mass))
    pull_force = np.asarray(pull_direction_ms, dtype=np.float64) * float(
        params.pull_force
    )
    damping = damping_force(
        velocity_ms,
        params.damping,
        mass,
        _DAMPING_ACCELERATION_LIMIT,
    )
    return (
        pull_force + damping + np.asarray(external_force_ms, dtype=np.float64)
    ) / mass + np.asarray(gravity_ms, dtype=np.float64)


def _project_collision(
    params, frame, direction_ms, node_shapes, frame_progress, frames
):
    projection = params.projection_type
    if projection == "DISABLED":
        return direction_ms
    frames.pose_shapes(node_shapes, frame_progress)
    result_ms = direction_ms
    for shape in node_shapes:
        rotation = shape["rot_q"]
        inverse = single.conjugate(rotation)
        parent_ss = np.asarray(
            single.rotate(
                inverse, single.sub(frame.parent_position, shape["pos_ms"].tolist())
            ),
            dtype=np.float64,
        )
        direction_ss = np.asarray(
            single.rotate(inverse, single.normalized(result_ms)), dtype=np.float64
        )
        radius = max(0.0, float(params.collision_radius))
        length = max(0.0, float(params.collision_height) * 2.0)
        if (
            rounded_box_signed_distance(
                shape["extents"], shape["radius"], parent_ss, radius
            )
            < 0.001
        ):
            continue
        if (
            swept_capsule_box_overlap(
                shape["extents"],
                shape["radius"],
                parent_ss,
                direction_ss,
                length,
                radius,
            )
            >= -1e-7
        ):
            continue
        if projection == "SHORTEST_PATH_ROTATIONAL":
            projected_ss = shortest_path_rotational_projection(
                shape["extents"],
                shape["radius"],
                parent_ss,
                direction_ss,
                length,
                radius,
            )
        elif (
            projection == "DIRECTED_ROTATIONAL"
            and params.constraint_type == "HINGE_PLANE"
        ):
            axis_ss = np.asarray(
                single.rotate(inverse, single.negate(frame.orthogonal_axis)),
                dtype=np.float64,
            )
            projected_ss = directed_rotational_projection(
                shape["extents"],
                shape["radius"],
                parent_ss,
                direction_ss,
                length,
                radius,
                axis_ss,
            )
        else:
            continue
        if np.linalg.norm(projected_ss) > _EPS:
            result_ms = single.rotate(
                rotation, single.normalized(single.vec3(*projected_ss))
            )
    return result_ms


def step_pendulum_node(
    system, node_index, raw_dt, time_dilation, skip_physics, params, frames
):
    """Advance one pendulum node, or return False when the node cannot run"""
    if not system.single_particle_node_is_valid(system.pendulum_nodes, node_index):
        return False
    runtime = system.pendulum_nodes[node_index]
    pi = int(runtime["particle_index"])
    node_shapes = system.node_col_shapes[node_index]
    position = system.pos_ms
    velocity = system.vel_ms
    frames.begin_shapes(node_shapes)

    calculator = runtime["frame_time_calculator"]
    calculator.recalculate(max(0.0, float(raw_dt)) * max(0.0, float(time_dilation)))
    dt, steps = fixed_rate_steps(
        calculator.average_frame_time, max(10.0, float(params.simulation_fps))
    )

    axis_length = max(0.0, float(runtime["axis_length"]))
    half_angle = params.half_angle
    if skip_physics:
        runtime["needs_initialization"] = True

    if half_angle > 0.0 and axis_length > 0.0 and not runtime["needs_initialization"]:
        gravity_ms = system.node_cur_grav_ms[node_index]
        external_force_ms = system.node_cur_ext_force_ms[node_index]
        for step_index in range(steps):
            previous_position = position[pi].copy()
            progress = (step_index + 1.0) / steps
            frame = frames.pendulum_frame(node_index, progress)

            acceleration = _calculate_acceleration(
                params,
                frame.pull_direction,
                velocity[pi],
                gravity_ms,
                external_force_ms,
            )
            velocity[pi] += acceleration * (dt * 0.5)
            position[pi] += velocity[pi] * dt

            direction = single.vec3(
                *(
                    position[pi] - np.asarray(frame.parent_position, dtype=np.float64)
                ).tolist()
            )
            direction = _constrain_direction(direction, frame, params)
            direction = _project_collision(
                params, frame, direction, node_shapes, progress, frames
            )
            direction = _constrain_direction(direction, frame, params)
            position[pi] = np.asarray(
                single.add(frame.parent_position, single.scale(direction, axis_length)),
                dtype=np.float32,
            )
            if dt != 0.0:
                acceleration = _calculate_acceleration(
                    params,
                    frame.pull_direction,
                    velocity[pi],
                    gravity_ms,
                    external_force_ms,
                )
                velocity[pi] = (
                    position[pi] - previous_position
                ) / dt + acceleration * (0.5 * dt)
        if not np.all(np.isfinite(position[pi])) or not np.all(
            np.isfinite(velocity[pi])
        ):
            runtime["needs_initialization"] = True

    if half_angle <= 0.0 or axis_length <= 0.0 or runtime["needs_initialization"]:
        velocity[pi] = 0.0
        parent_position, axis = frames.pendulum_rest_frame(node_index)
        position[pi] = np.asarray(
            single.add(parent_position, single.scale(axis, axis_length)),
            dtype=np.float32,
        )
        runtime["needs_initialization"] = False

    system.prev_pos_ms[pi] = position[pi]
    return True
