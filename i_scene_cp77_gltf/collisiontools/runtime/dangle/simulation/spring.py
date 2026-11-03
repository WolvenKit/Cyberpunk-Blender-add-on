import math

from mathutils import Matrix, Quaternion, Vector

from .....animation.handlers.dangle.spring import spring_node
from .....animation.model.dangle.frames import SpringFrame, SpringParams
from .....blender.pose import interpolate_matrix_trs
from . import spaces


def compile_spring_nodes(sim):
    sim.system.spring_nodes = {}
    for node_index, start, _pose_bone, parent_index in sim.single_particle_nodes(
        "SPRING"
    ):
        sim.system.spring_nodes[node_index] = spring_node(start, parent_index)
        sim._previous_parent_xforms[node_index] = Matrix.Identity(4)


def spring_params(particle):
    return SpringParams(
        mass=float(particle.mass),
        pull_force=float(particle.pull_force),
        damping=float(particle.damping),
        simulation_fps=float(particle.spring_simulation_fps),
        projection_type=particle.spring_projection_type,
        collision_radius=particle.spring_collision_radius,
        constraint_radius=float(particle.spring_constraint_radius),
        constraint_scale1=float(particle.spring_constraint_scale1),
        constraint_scale2=float(particle.spring_constraint_scale2),
    )


def _ellipsoid_rotation(parent_xform, orientation_degrees, arm_obj):
    parent_red_rotation = spaces.parent_red_rotation(parent_xform, arm_obj)
    axis_x = parent_red_rotation @ Vector((1.0, 0.0, 0.0))
    axis_y = parent_red_rotation @ Vector((0.0, 1.0, 0.0))
    rotation_x = Quaternion(axis_x, math.radians(float(orientation_degrees[0])))
    rotation_y = Quaternion(axis_y, math.radians(float(orientation_degrees[1])))
    result = rotation_y @ rotation_x @ parent_red_rotation
    result.normalize()
    return result


def _parent_xforms(sim, node_index):
    parent_index = int(sim.system.spring_nodes[node_index]["parent_index"])
    return sim._previous_parent_xforms[node_index], sim._cur_bone_xform[parent_index]


def spring_frame(sim, node_index, progress):
    previous, current = _parent_xforms(sim, node_index)
    particle = sim.particles[int(sim.system.spring_nodes[node_index]["particle_index"])]
    parent_lerp = interpolate_matrix_trs(previous, current, progress)
    rotation = _ellipsoid_rotation(
        parent_lerp, particle.spring_constraint_orientation, sim.arm_obj
    )
    return SpringFrame(
        tuple(parent_lerp.translation),
        tuple(pull_force_origin_ms(sim.arm_obj, particle, parent_lerp)),
        tuple(rotation),
        tuple(rotation.inverted()),
    )


def spring_rest_position(sim, node_index):
    return tuple(_parent_xforms(sim, node_index)[1].translation)


def constraint_ellipsoid_transform(arm_obj, particle, parent_xform):
    rotation = _ellipsoid_rotation(
        parent_xform, particle.spring_constraint_orientation, arm_obj
    )
    result = rotation.to_matrix().to_4x4()
    result.translation = parent_xform.translation
    return result


def pull_force_origin_ms(arm_obj, particle, parent_xform):
    return parent_xform @ spaces.re_axis_to_blender_bone(
        particle.spring_pull_force_origin_ls, arm_obj
    )
