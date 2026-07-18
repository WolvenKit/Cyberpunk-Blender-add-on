import math

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import collision, spaces
from .frame_time import AverageFrameTimeCalculator

_MIN_FRAME_TIME = 0.001
_MAX_FRAME_TIME = 0.1
_MAX_TIME_STEPS = 15
_DAMPING_ACCELERATION_LIMIT = 50.0
_EPS = 1e-8


def compile_pendulum_nodes(sim):
    sim._pendulum_nodes = {}
    for node_index, solver_type in enumerate(sim._node_solver_types):
        if solver_type != 'PENDULUM':
            continue
        start, end = sim._node_ranges[node_index]
        if end - start != 1:
            continue
        particle = sim.particles[start]
        pose_bone = sim.arm_obj.pose.bones.get(sim.bone_names[start])
        parent_index = -1
        axis_length = 0.0
        if pose_bone is not None and pose_bone.parent is not None:
            parent_index = sim.resolve_bone_index(pose_bone.parent.name)
            if parent_index is None:
                parent_index = -1
            local_rest = pose_bone.parent.bone.matrix_local.inverted() @ pose_bone.bone.matrix_local
            axis_length = local_rest.translation.length
        sim._pendulum_nodes[node_index] = {
            'particle_index': start,
            'parent_index': parent_index,
            'axis_length': float(axis_length),
            'previous_parent_xform': Matrix.Identity(4),
            'needs_initialization': True,
            'frame_time_calculator': AverageFrameTimeCalculator(),
        }


def pendulum_node_is_valid(sim, node_index):
    runtime = getattr(sim, '_pendulum_nodes', {}).get(node_index)
    if runtime is None:
        return False
    pi = int(runtime['particle_index'])
    parent = int(runtime['parent_index'])
    if not 0 <= pi < sim.num_particles or parent < 0:
        return False
    if not sim.active_mask[pi] or not sim.active_mask[parent]:
        return False
    for shape in sim._node_col_shapes[node_index]:
        shape_index = sim.resolve_bone_index(shape['bone_name'])
        if shape_index is None or shape_index < 0:
            return False
    return True


def _lerp_transform(previous, current, factor):
    pl, pr, ps = previous.decompose()
    cl, cr, cs = current.decompose()
    return Matrix.LocRotScale(pl.lerp(cl, factor), pr.slerp(cr, factor), ps.lerp(cs, factor))


def _additional_rotation(parent_rotation, orientation):
    x_axis = parent_rotation @ Vector((1.0, 0.0, 0.0))
    y_axis = parent_rotation @ Vector((0.0, 1.0, 0.0))
    z_axis = parent_rotation @ Vector((0.0, 0.0, 1.0))
    rx = Quaternion(x_axis, math.radians(float(orientation[0])))
    ry = Quaternion(y_axis, math.radians(float(orientation[1])))
    rz = Quaternion(z_axis, math.radians(float(orientation[2])))
    q = rz @ ry @ rx
    q.normalize()
    return q


def _parent_red_rotation(parent_xform, arm_obj):
    basis = spaces.re_to_blender_bone_local_matrix(arm_obj).to_quaternion()
    q = parent_xform.to_quaternion() @ basis
    q.normalize()
    return q


def _orthogonal(vector):
    x, y, z = vector
    if 0.81 * (x*x + y*y + z*z) - x*x < 0.0:
        return Vector((-z, 0.0, x))
    return Vector((0.0, z, -y))


def _constrain_direction(direction, initial_axis, orthogonal_axis, constraint_type, half_angle):
    v = Vector(direction)
    if constraint_type == 'HINGE_PLANE':
        v -= orthogonal_axis * orthogonal_axis.dot(v)
    elif constraint_type == 'HALF_CONE':
        dot = orthogonal_axis.dot(v)
        if dot > 0.0:
            v -= orthogonal_axis * dot
    if v.length_squared <= _EPS:
        v = initial_axis.copy()
    else:
        v.normalize()
    cos_half = math.cos(math.radians(half_angle))
    if initial_axis.dot(v) < cos_half:
        perpendicular = initial_axis.cross(v)
        if perpendicular.length_squared <= _EPS:
            perpendicular = orthogonal_axis.copy()
        perpendicular.normalize()
        v = Quaternion(perpendicular, math.radians(half_angle)) @ initial_axis
        v.normalize()
    return v


def _calculate_acceleration(particle, pull_direction_ms, velocity_ms, gravity_ms, external_force_ms):
    mass = max(0.01, float(particle.mass))
    pull_force = np.asarray(pull_direction_ms, dtype=np.float64) * float(particle.pull_force)
    damping_force = np.asarray(velocity_ms, dtype=np.float64) * -float(particle.damping)
    limit = _DAMPING_ACCELERATION_LIMIT * mass
    length = float(np.linalg.norm(damping_force))
    if length > limit and length > 0.0:
        damping_force *= limit / length
    return (
        pull_force + damping_force + np.asarray(external_force_ms, dtype=np.float64)
    ) / mass + np.asarray(gravity_ms, dtype=np.float64)


def _project_collision(sim, particle, parent_lerp, direction_ms, node_shapes, frame_progress, orthogonal_axis_ms):
    projection = particle.pendulum_projection_type
    if projection == 'DISABLED':
        return Vector(direction_ms)
    collision.update_collision_transforms(sim, frame_progress, node_shapes)
    result_ms = Vector(direction_ms)
    for shape in node_shapes:
        inv_rot = shape['rot_ms'].conjugated()
        parent_ss = np.asarray(inv_rot @ Vector(parent_lerp.translation - Vector(shape['pos_ms'])), dtype=np.float64)
        direction_ss = np.asarray(inv_rot @ result_ms.normalized(), dtype=np.float64)
        radius = max(0.0, float(particle.pendulum_collision_radius))
        length = max(0.0, float(particle.pendulum_collision_height) * 2.0)
        if collision._shape_distance_simplified(shape, parent_ss, radius) < 0.001:
            continue
        if collision.rounded_shape_overlap_value_ss(shape, parent_ss, direction_ss, length, radius) >= -1e-7:
            continue
        if projection == 'SHORTEST_PATH_ROTATIONAL':
            projected_ss = collision.shortest_path_rotational_projection_ss(
                shape, parent_ss, direction_ss, length, radius
            )
        elif projection == 'DIRECTED_ROTATIONAL' and particle.pendulum_constraint_type == 'HINGE_PLANE':
            axis_ss = np.asarray(inv_rot @ (-Vector(orthogonal_axis_ms)), dtype=np.float64)
            projected_ss = collision.directed_rotational_projection_ss(
                shape, parent_ss, direction_ss, length, radius, axis_ss
            )
        else:
            continue
        if np.linalg.norm(projected_ss) > _EPS:
            result_ms = shape['rot_ms'] @ Vector(projected_ss).normalized()
    return result_ms


def step_pendulum_node(sim, node_index, raw_dt, time_dilation, skip_physics):
    if not pendulum_node_is_valid(sim, node_index):
        return
    runtime = sim._pendulum_nodes[node_index]
    pi = int(runtime['particle_index'])
    parent_index = int(runtime['parent_index'])
    particle = sim.particles[pi]
    node_shapes = sim._node_col_shapes[node_index]
    collision.update_collision_transforms_begin(sim, node_shapes)

    calculator = runtime['frame_time_calculator']
    calculator.recalculate(max(0.0, float(raw_dt)) * max(0.0, float(time_dilation)))
    average = calculator.average_frame_time
    frame_time = min(_MAX_FRAME_TIME, max(_MIN_FRAME_TIME, average)) if abs(average) > 1e-5 else 0.0
    steps = max(1, min(_MAX_TIME_STEPS, int(math.ceil(frame_time * max(10.0, float(particle.pendulum_simulation_fps))))))
    dt = frame_time / steps

    parent_xform = sim._cur_bone_xform[parent_index].copy()
    axis_length = max(0.0, float(runtime['axis_length']))
    half_angle = max(0.0, min(180.0, float(particle.pendulum_half_aperture_angle)))
    if skip_physics:
        runtime['needs_initialization'] = True

    if half_angle > 0.0 and axis_length > 0.0 and not runtime['needs_initialization']:
        previous_parent = runtime['previous_parent_xform']
        for step_index in range(steps):
            previous_position = sim.pos_ms[pi].copy()
            progress = (step_index + 1.0) / steps
            parent_lerp = _lerp_transform(previous_parent, parent_xform, progress)
            parent_red = _parent_red_rotation(parent_lerp, sim.arm_obj)
            additional = _additional_rotation(parent_red, particle.pendulum_constraint_orientation)
            constraint_rotation = additional @ parent_red
            initial_axis = constraint_rotation @ Vector((1.0, 0.0, 0.0))
            initial_axis.normalize()
            orthogonal_ls = _orthogonal(Vector((1.0, 0.0, 0.0))).normalized()
            orthogonal_axis = constraint_rotation @ orthogonal_ls
            orthogonal_axis.normalize()
            pull_ls = Vector(particle.pendulum_pull_force_direction_ls)
            pull_direction = constraint_rotation @ (pull_ls.normalized() if pull_ls.length_squared > _EPS else pull_ls)

            acceleration = _calculate_acceleration(
                particle, pull_direction, sim.vel_ms[pi],
                sim._node_cur_grav_ms[node_index], sim._node_cur_ext_force_ms[node_index],
            )
            sim.vel_ms[pi] += acceleration * (dt * 0.5)
            sim.pos_ms[pi] += sim.vel_ms[pi] * dt

            direction = Vector(sim.pos_ms[pi] - np.asarray(parent_lerp.translation, dtype=np.float64))
            direction = _constrain_direction(
                direction, initial_axis, orthogonal_axis,
                particle.pendulum_constraint_type, half_angle,
            )
            direction = _project_collision(
                sim, particle, parent_lerp, direction, node_shapes, progress, orthogonal_axis
            )
            direction = _constrain_direction(
                direction, initial_axis, orthogonal_axis,
                particle.pendulum_constraint_type, half_angle,
            )
            sim.pos_ms[pi] = np.asarray(parent_lerp.translation + direction * axis_length, dtype=np.float32)
            if dt != 0.0:
                acceleration = _calculate_acceleration(
                    particle, pull_direction, sim.vel_ms[pi],
                    sim._node_cur_grav_ms[node_index], sim._node_cur_ext_force_ms[node_index],
                )
                sim.vel_ms[pi] = (
                    (sim.pos_ms[pi] - previous_position) / dt + acceleration * (0.5 * dt)
                )
        if not np.all(np.isfinite(sim.pos_ms[pi])) or not np.all(np.isfinite(sim.vel_ms[pi])):
            runtime['needs_initialization'] = True

    if half_angle <= 0.0 or axis_length <= 0.0 or runtime['needs_initialization']:
        sim.vel_ms[pi] = 0.0
        parent_red = _parent_red_rotation(parent_xform, sim.arm_obj)
        constraint_rotation = _additional_rotation(parent_red, particle.pendulum_constraint_orientation) @ parent_red
        axis = constraint_rotation @ Vector((1.0, 0.0, 0.0))
        sim.pos_ms[pi] = np.asarray(parent_xform.translation + axis * axis_length, dtype=np.float32)
        runtime['needs_initialization'] = False

    sim.prev_pos_ms[pi] = sim.pos_ms[pi]
    runtime['previous_parent_xform'] = parent_xform.copy()


def constraint_transform(sim, particle, parent_xform):
    parent_red = _parent_red_rotation(parent_xform, sim.arm_obj)
    rotation = _additional_rotation(parent_red, particle.pendulum_constraint_orientation) @ parent_red
    matrix = rotation.to_matrix().to_4x4()
    matrix.translation = parent_xform.translation
    return matrix
