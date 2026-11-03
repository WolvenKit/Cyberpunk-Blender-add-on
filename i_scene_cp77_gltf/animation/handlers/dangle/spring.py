<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
import math

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ....animation.blender_pose import interpolate_matrix_trs
from ....bartmoss.dynamics import damping_force
from . import collision, spaces
from .frame_time import AverageFrameTimeCalculator

_MIN_FRAME_TIME = 0.001
_MAX_FRAME_TIME = 0.1
_MAX_TIME_STEPS = 15
=======
import numpy as np

from ....bartmoss import single
from ....bartmoss.dynamics import damping_force
from ...domain.dangle.collision import project_shortest_path_position
from ...domain.dangle.frame_time import SmoothedFrameTime, fixed_rate_steps

>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
_MIN_DIRECTION_LENGTH = 0.0001
_DAMPING_ACCELERATION_LIMIT = 50.0


<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
def compile_spring_nodes(sim):
    sim._spring_nodes = {}
    for node_index, solver_type in enumerate(sim._node_solver_types):
        if solver_type != 'SPRING':
            continue
        start, end = sim._node_ranges[node_index]
        if end - start != 1:
            continue
        particle = sim.particles[start]
        pose_bone = sim.arm_obj.pose.bones.get(sim.bone_names[start])
        parent_index = -1
        if pose_bone is not None and pose_bone.parent is not None:
            parent_index = sim.resolve_bone_index(pose_bone.parent.name)
            if parent_index is None:
                parent_index = -1
        sim._spring_nodes[node_index] = {
            'particle_index': start,
            'parent_index': parent_index,
            'previous_parent_xform': Matrix.Identity(4),
            'needs_initialization': True,
            'frame_time_calculator': AverageFrameTimeCalculator(),
        }


def spring_node_is_valid(sim, node_index):
    runtime = getattr(sim, '_spring_nodes', {}).get(node_index)
    if runtime is None:
        return False
    particle_index = int(runtime['particle_index'])
    parent_index = int(runtime['parent_index'])
    if not 0 <= particle_index < sim.num_particles:
        return False
    if not sim.active_mask[particle_index]:
        return False
    if parent_index < 0 or not sim.active_mask[parent_index]:
        return False
    for shape in sim._node_col_shapes[node_index]:
        shape_index = int(shape.get('bone_index', -1))
        if shape_index < 0 or not sim.active_mask[shape_index]:
            return False
    return True


def _average_frame_time(runtime, frame_time):
    calculator = runtime.get('frame_time_calculator')
    if calculator is None:
        calculator = AverageFrameTimeCalculator()
        runtime['frame_time_calculator'] = calculator
    calculator.recalculate(frame_time)
    return calculator.average_frame_time


def _parent_red_rotation(parent_xform, arm_obj):
    basis_rotation = spaces.re_to_blender_bone_local_matrix(
        arm_obj
    ).to_quaternion()
    rotation = parent_xform.to_quaternion() @ basis_rotation
    rotation.normalize()
    return rotation


def _pull_origin_ms(parent_xform, origin_re, arm_obj):
    origin_bl = spaces.re_axis_to_blender_bone(origin_re, arm_obj)
    return parent_xform @ origin_bl


def _ellipsoid_rotation(parent_xform, orientation_degrees, arm_obj):
    parent_red_rotation = _parent_red_rotation(parent_xform, arm_obj)
    axis_x = parent_red_rotation @ Vector((1.0, 0.0, 0.0))
    axis_y = parent_red_rotation @ Vector((0.0, 1.0, 0.0))
    rotation_x = Quaternion(axis_x, math.radians(float(orientation_degrees[0])))
    rotation_y = Quaternion(axis_y, math.radians(float(orientation_degrees[1])))
    result = rotation_y @ rotation_x @ parent_red_rotation
    result.normalize()
    return result


def _calculate_acceleration(
    particle, pull_origin_ms, position_ms, velocity_ms,
    gravity_acceleration_ms, external_force_ms,
):
    mass = max(0.01, float(particle.mass))
=======
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
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
    inverse_mass = 1.0 / mass
    pull_force = (
        np.asarray(pull_origin_ms, dtype=np.float64)
        - np.asarray(position_ms, dtype=np.float64)
<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
    ) * float(particle.pull_force)
    damping = damping_force(
        velocity_ms,
        particle.damping,
        mass,
        _DAMPING_ACCELERATION_LIMIT,
    )
    net_force = (
        pull_force
        + damping
        + np.asarray(external_force_ms, dtype=np.float64)
    )
    return (
        net_force * inverse_mass
        + np.asarray(gravity_acceleration_ms, dtype=np.float64)
    )


def _clamp_to_constraint(sim, particle, parent_xform, position_ms):
    radius = max(0.0, float(particle.spring_constraint_radius))
    parent_position = np.asarray(parent_xform.translation, dtype=np.float64)
=======
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
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
    if radius == 0.0:
        return parent_position.copy()

    parent_to_bob = np.asarray(position_ms, dtype=np.float64) - parent_position
    parent_to_bob_length = float(np.linalg.norm(parent_to_bob))
    if parent_to_bob_length <= _MIN_DIRECTION_LENGTH:
        return np.asarray(position_ms, dtype=np.float64)

<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
    ellipsoid_rotation = _ellipsoid_rotation(
        parent_xform, particle.spring_constraint_orientation, sim.arm_obj
    )
    normalized_ms = Vector(parent_to_bob / parent_to_bob_length)
    normalized_es = ellipsoid_rotation.inverted() @ normalized_ms
=======
    normalized_ms = single.vec3(*(parent_to_bob / parent_to_bob_length).tolist())
    normalized_es = single.rotate(frame.inverse, normalized_ms)
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py

    sx = radius
    sy = radius
    scale = (
<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
        max(0.01, float(particle.spring_constraint_scale1))
        if normalized_es.z < 0.0
        else max(0.01, float(particle.spring_constraint_scale2))
    )
    sz = radius * scale
    scaled = Vector((
        normalized_es.x / sx,
        normalized_es.y / sy,
        normalized_es.z / sz,
    ))
    scaled_length = scaled.length
=======
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
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
    if scaled_length <= 1e-12:
        return np.asarray(position_ms, dtype=np.float64)
    max_distance = 1.0 / scaled_length

    if parent_to_bob_length > max_distance:
<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
        adjustment_es = Vector((
            normalized_es.x / (sx * sx),
            normalized_es.y / (sy * sy),
            normalized_es.z / (sz * sz),
        ))
        adjustment_ms = ellipsoid_rotation @ adjustment_es
        if adjustment_ms.length_squared > 1e-12:
            adjustment_ms.normalize()
            vector_ms = Vector(parent_to_bob)
            surface_vector_ms = normalized_ms * max_distance
            vector_ms -= adjustment_ms * (
                adjustment_ms.dot(vector_ms)
                - adjustment_ms.dot(surface_vector_ms)
=======
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
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
            )
            parent_to_bob = np.asarray(vector_ms, dtype=np.float64)

    corrected_length = float(np.linalg.norm(parent_to_bob))
    biggest_extent = max(sx, sz)
    if corrected_length > biggest_extent and corrected_length > 0.0:
        parent_to_bob *= biggest_extent / corrected_length
    return parent_position + parent_to_bob


<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
def step_spring_node(sim, node_index, raw_dt, time_dilation, skip_physics):
    if not spring_node_is_valid(sim, node_index):
        return

    runtime = sim._spring_nodes[node_index]
    particle_index = int(runtime['particle_index'])
    parent_index = int(runtime['parent_index'])
    particle = sim.particles[particle_index]
    node_shapes = sim._node_col_shapes[node_index]

    collision.update_collision_transforms_begin(sim, node_shapes)

    frame_time = max(0.0, float(raw_dt)) * max(0.0, float(time_dilation))
    average_frame_time = _average_frame_time(runtime, frame_time)
    clamped_frame_time = (
        min(_MAX_FRAME_TIME, max(_MIN_FRAME_TIME, average_frame_time))
        if abs(average_frame_time) > 0.00001
        else 0.0
    )
    simulation_fps = max(10.0, float(particle.spring_simulation_fps))
    time_steps = max(
        1,
        min(
            _MAX_TIME_STEPS,
            int(math.ceil(clamped_frame_time * simulation_fps)),
        ),
    )
    dt = clamped_frame_time / time_steps

    parent_xform = sim._cur_bone_xform[parent_index].copy()
    if skip_physics:
        runtime['needs_initialization'] = True

    if not runtime['needs_initialization']:
        previous_parent_xform = runtime['previous_parent_xform']
        gravity_acceleration_ms = sim._node_cur_grav_ms[node_index]
        external_force_ms = sim._node_cur_ext_force_ms[node_index]

        for step_index in range(time_steps):
            previous_position = sim.pos_ms[particle_index].copy()
            frame_progress = (step_index + 1.0) / time_steps
            parent_lerp = interpolate_matrix_trs(
                previous_parent_xform, parent_xform, frame_progress
            )
            pull_origin = _pull_origin_ms(
                parent_lerp,
                particle.spring_pull_force_origin_ls,
                sim.arm_obj,
            )

            acceleration = _calculate_acceleration(
                particle,
                pull_origin,
                sim.pos_ms[particle_index],
                sim.vel_ms[particle_index],
                gravity_acceleration_ms,
                external_force_ms,
            )
            sim.vel_ms[particle_index] += acceleration * (dt * 0.5)
            sim.pos_ms[particle_index] += sim.vel_ms[particle_index] * dt

            if particle.spring_projection_type == 'SHORTEST_PATH':
                collision.update_collision_transforms(
                    sim, frame_progress, node_shapes
                )
                for shape in node_shapes:
                    sim.pos_ms[particle_index] = (
                        collision.project_shortest_path_position(
                            shape,
                            sim.pos_ms[particle_index],
                            particle.spring_collision_radius,
                        )
                    )

            sim.pos_ms[particle_index] = _clamp_to_constraint(
                sim, particle, parent_lerp, sim.pos_ms[particle_index]
=======
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
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
            )

            if dt != 0.0:
                acceleration = _calculate_acceleration(
<<<<<<< Updated upstream:i_scene_cp77_gltf/collisiontools/dangles/sim/spring.py
                    particle,
                    pull_origin,
                    sim.pos_ms[particle_index],
                    sim.vel_ms[particle_index],
                    gravity_acceleration_ms,
                    external_force_ms,
                )
                sim.vel_ms[particle_index] = (
                    (sim.pos_ms[particle_index] - previous_position) / dt
                    + acceleration * (0.5 * dt)
                )

        if not (
            np.all(np.isfinite(sim.pos_ms[particle_index]))
            and np.all(np.isfinite(sim.vel_ms[particle_index]))
        ):
            runtime['needs_initialization'] = True

    if runtime['needs_initialization']:
        sim.vel_ms[particle_index] = 0.0
        sim.pos_ms[particle_index] = np.asarray(
            parent_xform.translation, dtype=np.float32
        )
        runtime['needs_initialization'] = False

    sim.prev_pos_ms[particle_index] = sim.pos_ms[particle_index]
    runtime['previous_parent_xform'] = parent_xform.copy()


def constraint_ellipsoid_transform(sim, particle, parent_xform):
    rotation = _ellipsoid_rotation(
        parent_xform, particle.spring_constraint_orientation, sim.arm_obj
    )
    result = rotation.to_matrix().to_4x4()
    result.translation = parent_xform.translation
    return result


def pull_force_origin_ms(sim, particle, parent_xform):
    return _pull_origin_ms(
        parent_xform, particle.spring_pull_force_origin_ls, sim.arm_obj
    )
=======
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
>>>>>>> Stashed changes:i_scene_cp77_gltf/animation/handlers/dangle/spring.py
