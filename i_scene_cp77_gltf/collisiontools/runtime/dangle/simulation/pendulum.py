import math

from mathutils import Matrix, Quaternion, Vector

from .....animation.handlers.dangle.pendulum import pendulum_node
from .....animation.model.dangle.frames import PendulumFrame, PendulumParams
from .....blender.pose import interpolate_matrix_trs
from . import spaces

_EPS = 1e-8
_X_AXIS = Vector((1.0, 0.0, 0.0))
_ORTHOGONAL_AXIS_LS = Vector((0.0, 0.0, 1.0))


def compile_pendulum_nodes(sim):
    sim.system.pendulum_nodes = {}
    for node_index, start, pose_bone, parent_index in sim.single_particle_nodes(
        "PENDULUM"
    ):
        axis_length = 0.0
        if pose_bone is not None and pose_bone.parent is not None:
            local_rest = (
                pose_bone.parent.bone.matrix_local.inverted()
                @ pose_bone.bone.matrix_local
            )
            axis_length = local_rest.translation.length
        sim.system.pendulum_nodes[node_index] = pendulum_node(
            start, parent_index, axis_length
        )
        sim._previous_parent_xforms[node_index] = Matrix.Identity(4)


def pendulum_params(particle):
    half_angle = max(0.0, min(180.0, float(particle.pendulum_half_aperture_angle)))
    # The limit rotation is built about a unit axis, so its quaternion is (cos, axis * sin) of these.
    half_rotation = Quaternion(_X_AXIS, math.radians(half_angle))
    return PendulumParams(
        mass=float(particle.mass),
        pull_force=float(particle.pull_force),
        damping=float(particle.damping),
        simulation_fps=float(particle.pendulum_simulation_fps),
        constraint_type=particle.pendulum_constraint_type,
        projection_type=particle.pendulum_projection_type,
        collision_radius=float(particle.pendulum_collision_radius),
        collision_height=float(particle.pendulum_collision_height),
        half_angle=half_angle,
        half_sine=half_rotation.x,
        half_cosine=half_rotation.w,
    )


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


def _constraint_rotation(sim, particle, parent_xform):
    parent_red = spaces.parent_red_rotation(parent_xform, sim.arm_obj)
    return (
        _additional_rotation(parent_red, particle.pendulum_constraint_orientation)
        @ parent_red
    )


def _node_inputs(sim, node_index):
    runtime = sim.system.pendulum_nodes[node_index]
    particle = sim.particles[int(runtime["particle_index"])]
    return (
        particle,
        sim._previous_parent_xforms[node_index],
        sim._cur_bone_xform[int(runtime["parent_index"])],
    )


def pendulum_frame(sim, node_index, progress):
    particle, previous, current = _node_inputs(sim, node_index)
    parent_lerp = interpolate_matrix_trs(previous, current, progress)
    constraint_rotation = _constraint_rotation(sim, particle, parent_lerp)
    initial_axis = constraint_rotation @ _X_AXIS
    initial_axis.normalize()
    orthogonal_axis = constraint_rotation @ _ORTHOGONAL_AXIS_LS
    orthogonal_axis.normalize()
    pull_ls = Vector(particle.pendulum_pull_force_direction_ls)
    pull_direction = constraint_rotation @ (
        pull_ls.normalized() if pull_ls.length_squared > _EPS else pull_ls
    )
    return PendulumFrame(
        tuple(parent_lerp.translation),
        tuple(initial_axis),
        tuple(orthogonal_axis),
        tuple(pull_direction),
    )


def pendulum_rest_frame(sim, node_index):
    particle, _previous, current = _node_inputs(sim, node_index)
    axis = _constraint_rotation(sim, particle, current) @ _X_AXIS
    return tuple(current.translation), tuple(axis)
