import math

import numpy as np
from mathutils import Quaternion, Vector

from .....animation.domain.dangle.constraints import (
    CONE_PROJECTION_TYPES,
    CONE_TYPES,
    LINK_TYPES,
)
from .....animation.model.dangle.frames import ConeFrame, DyngFrame, EllipsoidFrame
from .....blender.armature_bones import resolve_data_bone
from . import spaces
from .state_validation import require_local_particle_index


def compile_constraints(sim):
    _compile_links(sim)
    _compile_ellipsoids(sim)
    _compile_cones(sim)


def _compile_links(sim):
    idx_a, idx_b, l_types, lower, upper, rest, look_axes = ([], [], [], [], [], [], [])

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.link_constraints:
            tgt_idx = sim.resolve_bone_index(c.target_bone, particle_index=i)
            if tgt_idx is None:
                continue
            idx_a.append(i)
            idx_b.append(tgt_idx)

            l_types.append(LINK_TYPES.get(c.link_type, 0))
            lower.append(c.lower_ratio * 0.01)
            upper.append(c.upper_ratio * 0.01)

            if c.explicit_rest_distance > 0.0:
                rest.append(c.explicit_rest_distance)
            else:
                source_bone = resolve_data_bone(sim.arm_obj, p_cfg.bone_name)
                target_bone = resolve_data_bone(sim.arm_obj, c.target_bone)
                if source_bone is not None and target_bone is not None:
                    rest.append(
                        float((source_bone.head_local - target_bone.head_local).length)
                    )
                else:
                    rest.append(
                        float(
                            np.linalg.norm(
                                sim.system.pos_ms[i] - sim.system.pos_ms[tgt_idx]
                            )
                        )
                    )

            re_axis = Vector(getattr(c, "look_at_axis", (1.0, 0.0, 0.0)))
            if re_axis.length_squared < 1e-8:
                re_axis = Vector((1.0, 0.0, 0.0))
            bl_axis = spaces.re_axis_to_blender_bone(re_axis, sim.arm_obj).normalized()
            look_axes.append(list(bl_axis))

    sim.system.set_links(idx_a, idx_b, l_types, lower, upper, rest, look_axes)


def _compile_ellipsoids(sim):
    ell_idx, ell_radii, ell_s1, ell_s2 = [], [], [], []
    ell_xform_ls = []

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.ellipsoid_constraints:
            tgt_idx = sim.resolve_bone_index(c.target_bone, particle_index=i)
            if tgt_idx is not None:
                # The target bone resolves to one particle, which must lie in this node's particle range.
                tgt_idx = require_local_particle_index(
                    sim.system.particle_node_idx, i, tgt_idx, c.target_bone
                )
                ell_idx.append(tgt_idx)
                ell_radii.append(c.radius)
                ell_s1.append(c.scale1)
                ell_s2.append(c.scale2)
                ell_xform_ls.append(
                    spaces.re_local_matrix(
                        getattr(c, "ellipsoid_transform_ls_quat", (1.0, 0.0, 0.0, 0.0)),
                        getattr(c, "ellipsoid_transform_ls_offset", (0.0, 0.0, 0.0)),
                        sim.arm_obj,
                    )
                )

    sim.system.set_ellipsoids(ell_idx, ell_radii, ell_s1, ell_s2)
    sim.ell_xform_ls = ell_xform_ls


def _compile_cones(sim):
    c_idx, c_attach, c_type, c_cos, c_sin_hh, c_cos_hh = ([], [], [], [], [], [])
    c_cone_xform_adjusted = []
    c_proj_type = []
    c_col_radius = []
    c_col_height = []

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.pendulum_constraints:
            tgt_idx = sim.resolve_bone_index(c.target_bone, particle_index=i)
            if tgt_idx is None:
                continue

            c_idx.append(i)
            c_attach.append(tgt_idx)
            c_type.append(CONE_TYPES.get(c.constraint_type, 0))

            half_angle_rad = math.radians(c.half_aperture_angle)
            c_cos.append(math.cos(half_angle_rad))
            c_sin_hh.append(math.sin(half_angle_rad * 0.5))
            c_cos_hh.append(math.cos(half_angle_rad * 0.5))

            c_proj_type.append(
                CONE_PROJECTION_TYPES.get(getattr(c, "projection_type", "DISABLED"), 0)
            )
            c_col_radius.append(getattr(c, "cone_collision_radius", 0.0))
            c_col_height.append(getattr(c, "cone_collision_height", 0.0))
            c_cone_xform_adjusted.append(
                spaces.re_local_matrix(
                    getattr(c, "cone_transform_ls_quat", (1.0, 0.0, 0.0, 0.0)),
                    getattr(c, "cone_transform_ls_offset", (0.0, 0.0, 0.0)),
                    sim.arm_obj,
                )
            )

    sim.system.set_cones(
        c_idx,
        c_attach,
        c_type,
        c_cos,
        c_sin_hh,
        c_cos_hh,
        c_proj_type,
        c_col_radius,
        c_col_height,
    )
    sim.cone_xform_ls = c_cone_xform_adjusted


def capsule_axis_ms(sim, xform, particle_index):
    """A particle's capsule axis rotated by a bone frame (float32)"""
    axis_ls = Vector(sim.system.col_axis_ls[particle_index])
    if axis_ls.length_squared < 1e-8:
        axis_ls = spaces.re_axis_to_blender_bone((1.0, 0.0, 0.0), sim.arm_obj)
    return np.array(
        xform.to_quaternion() @ axis_ls.normalized(),
        dtype=np.float32,
    )


_IDENTITY = Quaternion()
_X_AXIS = Vector((1.0, 0.0, 0.0))
_Z_AXIS = Vector((0.0, 0.0, 1.0))


def dyng_frame(sim, node_index):
    """Ellipsoid and cone frames and directed capsule axes of a DynG node from the interpolated bones"""
    system = sim.system
    interpolated = sim._interp_bone_xform

    ellipsoids = {}
    selection = system.node_ell_sel[node_index]
    if selection is not None:
        for raw_index in selection:
            ci = int(raw_index)
            if ci < len(sim.ell_xform_ls):
                ellipsoid_ms = (
                    interpolated[int(system.ell_idx[ci])] @ sim.ell_xform_ls[ci]
                )
                center = ellipsoid_ms.translation
                rotation = ellipsoid_ms.to_quaternion()
            else:
                center = Vector(system.interp_bone_ms[int(system.ell_idx[ci])])
                rotation = _IDENTITY
            ellipsoids[ci] = EllipsoidFrame(
                tuple(center), tuple(rotation), tuple(rotation.inverted())
            )

    cones = {}
    selection = system.node_cone_sel[node_index]
    if selection is not None:
        for raw_index in selection:
            ci = int(raw_index)
            cone_transform = (
                interpolated[int(system.cone_attach[ci])] @ sim.cone_xform_ls[ci]
            )
            cone_rotation = cone_transform.to_quaternion()
            initial_axis = cone_rotation @ _X_AXIS
            initial_axis = (
                tuple(initial_axis.normalized())
                if initial_axis.length_squared > 1e-12
                else None
            )
            raw_orthogonal = cone_rotation @ _Z_AXIS
            orthogonal_axis = (
                tuple(raw_orthogonal.normalized())
                if int(system.cone_type[ci]) != 0
                and raw_orthogonal.length_squared > 1e-12
                else None
            )
            cones[ci] = ConeFrame(
                tuple(cone_transform.translation),
                initial_axis,
                orthogonal_axis,
                tuple(raw_orthogonal),
            )

    directed_axes = {}
    if system.node_col_shapes[node_index]:
        for raw_index in system.node_workspaces[node_index][
            "collision_directed_indices"
        ]:
            particle_index = int(raw_index)
            directed_axes[particle_index] = capsule_axis_ms(
                sim, interpolated[particle_index], particle_index
            )

    return DyngFrame(ellipsoids, cones, directed_axes)
