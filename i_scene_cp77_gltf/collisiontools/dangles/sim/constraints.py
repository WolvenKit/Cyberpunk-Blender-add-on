import math

import numpy as np
from mathutils import Quaternion, Vector

from . import spaces

RE_BONE_CONV = spaces.RE_TO_BLENDER_BONE_LOCAL_CURRENT


def _resolve_bone(sim, particle_idx, bone_name):
    """Resolve a source bone name against the active rig."""
    resolver = getattr(sim, "resolve_bone_index", None)
    if resolver is not None:
        return resolver(bone_name, particle_index=particle_idx)
    return sim.bone_idx_map.get(bone_name)


def compile_constraints(sim):
    _compile_links(sim)
    _compile_ellipsoids(sim)
    _compile_cones(sim)

def _compile_links(sim):
    idx_a, idx_b, l_types, lower, upper, rest, look_axes = (
        [], [], [], [], [], [], []
    )

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.link_constraints:
            tgt_idx = _resolve_bone(sim, i, c.target_bone)
            if tgt_idx is None:
                continue
            idx_a.append(i)
            idx_b.append(tgt_idx)

            t_val = {
                'FIXED': 0, 'VARIABLE': 1, 'GREATER': 2, 'CLOSER': 3
            }.get(c.link_type, 0)
            l_types.append(t_val)
            lower.append(c.lower_ratio * 0.01)
            upper.append(c.upper_ratio * 0.01)

            if c.explicit_rest_distance > 0.0:
                rest.append(c.explicit_rest_distance)
            else:
                source_bone = spaces.resolve_data_bone(sim.arm_obj, p_cfg.bone_name)
                target_bone = spaces.resolve_data_bone(sim.arm_obj, c.target_bone)
                if source_bone is not None and target_bone is not None:
                    rest.append(float((
                        source_bone.head_local - target_bone.head_local
                    ).length))
                else:
                    rest.append(float(np.linalg.norm(
                        sim.pos_ms[i] - sim.pos_ms[tgt_idx]
                    )))

            re_axis = Vector(getattr(c, 'look_at_axis', (1.0, 0.0, 0.0)))
            if re_axis.length_squared < 1e-8:
                re_axis = Vector((1.0, 0.0, 0.0))
            bl_axis = spaces.re_axis_to_blender_bone(
                re_axis, sim.arm_obj
            ).normalized()
            look_axes.append(list(bl_axis))

    if idx_a:
        sim.link_idx_a     = np.array(idx_a, dtype=np.int32)
        sim.link_idx_b     = np.array(idx_b, dtype=np.int32)
        sim.link_types     = np.array(l_types, dtype=np.int32)
        sim.link_lower     = np.array(lower, dtype=np.float32)
        sim.link_upper     = np.array(upper, dtype=np.float32)
        sim.link_rest      = np.array(rest, dtype=np.float32)
        sim.link_look_axes = np.array(look_axes, dtype=np.float32)
    else:
        sim.link_idx_a = None

def _compile_ellipsoids(sim):
    ell_idx, ell_centers, ell_radii, ell_s1, ell_s2 = [], [], [], [], []
    ell_xform_ls = []

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.ellipsoid_constraints:
            tgt_idx = _resolve_bone(sim, i, c.target_bone)
            if tgt_idx is not None:
                ell_idx.append(i)
                ell_centers.append(tgt_idx)
                ell_radii.append(c.radius)
                ell_s1.append(c.scale1)
                ell_s2.append(c.scale2)

                xf = getattr(c, 'ellipsoid_transform_ls_quat',
                             (1.0, 0.0, 0.0, 0.0))
                q = Quaternion(xf)
                off = Vector(getattr(c, 'ellipsoid_transform_ls_offset',
                                     (0.0, 0.0, 0.0)))
                ls_mat = q.to_matrix().to_4x4()
                ls_mat.translation = off
                ell_xform_ls.append(
                    spaces.re_local_transform_to_blender_bone(
                        ls_mat, sim.arm_obj
                    )
                )

    if ell_idx:
        sim.ell_idx      = np.array(ell_idx, dtype=np.int32)
        sim.ell_centers  = np.array(ell_centers, dtype=np.int32)
        sim.ell_radii    = np.array(ell_radii, dtype=np.float32)
        sim.ell_s1       = np.array(ell_s1, dtype=np.float32)
        sim.ell_s2       = np.array(ell_s2, dtype=np.float32)
        sim.ell_xform_ls = ell_xform_ls
    else:
        sim.ell_idx = None
        sim.ell_xform_ls = []


def _compile_cones(sim):
    c_idx, c_attach, c_type, c_cos, c_sin_hh, c_cos_hh = (
        [], [], [], [], [], []
    )
    c_cone_xform_adjusted = []
    c_proj_type = []
    c_col_radius = []
    c_col_height = []

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.pendulum_constraints:
            tgt_idx = _resolve_bone(sim, i, c.target_bone)
            if tgt_idx is None:
                continue

            c_idx.append(i)
            c_attach.append(tgt_idx)

            t_val = {
                'CONE': 0, 'HINGE_PLANE': 1, 'HALF_CONE': 2
            }.get(c.constraint_type, 0)
            c_type.append(t_val)

            half_angle_rad = math.radians(c.half_aperture_angle)
            c_cos.append(math.cos(half_angle_rad))
            c_sin_hh.append(math.sin(half_angle_rad * 0.5))
            c_cos_hh.append(math.cos(half_angle_rad * 0.5))

            proj_val = {
                'DISABLED': 0,
                'SHORTEST_PATH_ROTATIONAL': 1,
                'DIRECTED_ROTATIONAL': 2,
            }.get(getattr(c, 'projection_type', 'DISABLED'), 0)
            c_proj_type.append(proj_val)
            c_col_radius.append(getattr(c, 'cone_collision_radius', 0.0))
            c_col_height.append(getattr(c, 'cone_collision_height', 0.0))

            xf = getattr(c, 'cone_transform_ls_quat', (1.0, 0.0, 0.0, 0.0))
            q = Quaternion(xf)
            raw_ls = q.to_matrix().to_4x4()
            raw_ls.translation = Vector(
                getattr(c, 'cone_transform_ls_offset', (0.0, 0.0, 0.0))
            )

            adjusted_ls = spaces.re_local_transform_to_blender_bone(
                raw_ls, sim.arm_obj
            )
            c_cone_xform_adjusted.append(adjusted_ls)

    if c_idx:
        sim.cone_idx        = np.array(c_idx, dtype=np.int32)
        sim.cone_attach     = np.array(c_attach, dtype=np.int32)
        sim.cone_type       = np.array(c_type, dtype=np.int32)
        sim.cone_cos        = np.array(c_cos, dtype=np.float32)
        sim.cone_sin_hh     = np.array(c_sin_hh, dtype=np.float32)
        sim.cone_cos_hh     = np.array(c_cos_hh, dtype=np.float32)
        sim.cone_xform_ls   = c_cone_xform_adjusted
        sim.cone_proj_type  = np.array(c_proj_type, dtype=np.int32)
        sim.cone_col_radius = np.array(c_col_radius, dtype=np.float32)
        sim.cone_col_height = np.array(c_col_height, dtype=np.float32)
    else:
        sim.cone_idx        = None
        sim.cone_proj_type  = None
        sim.cone_col_radius = None
        sim.cone_col_height = None

    sim.pen_idx = sim.cone_idx if hasattr(sim, 'cone_idx') else None


def satisfy_dyng_link_at(sim, constraint_index):
    if sim.link_idx_a is None:
        return

    ci = int(constraint_index)
    p1_index = int(sim.link_idx_a[ci])
    p2_index = int(sim.link_idx_b[ci])
    difference = sim._constraint_vector
    np.subtract(
        sim.pos_ms[p2_index], sim.pos_ms[p1_index], out=difference
    )
    current_length = np.linalg.norm(difference)
    if current_length < np.float32(1e-6):
        nx = np.float32(1.0)
        ny = np.float32(0.0)
        nz = np.float32(0.0)
    else:
        inverse_length = np.float32(1.0) / current_length
        nx = difference[0] * inverse_length
        ny = difference[1] * inverse_length
        nz = difference[2] * inverse_length

    rest_length = sim.link_rest[ci]
    lower_length = sim.link_lower[ci] * rest_length
    upper_length = sim.link_upper[ci] * rest_length
    link_type = int(sim.link_types[ci])
    if link_type == 0:
        desired_length = lower_length
    elif link_type == 1:
        desired_length = np.clip(
            current_length, lower_length, upper_length
        )
    elif link_type == 2:
        desired_length = np.maximum(current_length, lower_length)
    else:
        desired_length = np.minimum(current_length, upper_length)

    error = current_length - desired_length
    if np.abs(error) <= np.float32(1e-7):
        return

    free1 = bool(sim.is_free[p1_index] and sim.active_mask[p1_index])
    free2 = bool(sim.is_free[p2_index] and sim.active_mask[p2_index])
    if not free1 and not free2:
        return
    if free1 and free2:
        mass1 = sim.mass[p1_index]
        mass2 = sim.mass[p2_index]
        total_mass = mass1 + mass2
        factor1 = np.float32(1.0) - mass1 / total_mass
        factor2 = np.float32(1.0) - mass2 / total_mass
    else:
        factor1 = np.float32(1.0 if free1 else 0.0)
        factor2 = np.float32(1.0 if free2 else 0.0)

    correction1 = error * factor1
    correction2 = error * factor2
    if correction1 != 0.0:
        sim.pos_ms[p1_index, 0] += nx * correction1
        sim.pos_ms[p1_index, 1] += ny * correction1
        sim.pos_ms[p1_index, 2] += nz * correction1
    if correction2 != 0.0:
        sim.pos_ms[p2_index, 0] -= nx * correction2
        sim.pos_ms[p2_index, 1] -= ny * correction2
        sim.pos_ms[p2_index, 2] -= nz * correction2


def satisfy_dyng_links_vectorized(sim):
    if sim.link_idx_a is None:
        return
    for constraint_index in range(len(sim.link_idx_a)):
        satisfy_dyng_link_at(sim, constraint_index)


def satisfy_dyng_ellipsoid_at(sim, constraint_index):
    if sim.ell_idx is None:
        return

    ci = int(constraint_index)
    particle_index = int(sim.ell_idx[ci])
    if not (sim.is_free[particle_index] and sim.active_mask[particle_index]):
        return

    center_index = int(sim.ell_centers[ci])
    if ci < len(sim.ell_xform_ls):
        ellipsoid_ms = sim._interp_bone_xform[center_index] @ sim.ell_xform_ls[ci]
        center = ellipsoid_ms.translation
        z_axis = ellipsoid_ms.to_quaternion() @ Vector((0.0, 0.0, 1.0))
    else:
        center = Vector(sim.interp_bone_ms[center_index])
        z_axis = Vector((0.0, 0.0, 1.0))

    offset = Vector(sim.pos_ms[particle_index]) - center
    distance = offset.length
    if distance <= 1e-4:
        return
    direction = offset / distance
    z_component = direction.dot(z_axis)
    z_scale = float(sim.ell_s1[ci] if z_component < 0.0 else sim.ell_s2[ci])
    radius = float(sim.ell_radii[ci])
    if radius <= 0.0 or abs(z_scale) <= 1e-12:
        return

    xy_vector = direction - z_axis * z_component
    scaled_xy = xy_vector.length / radius
    scaled_z = z_component / (radius * z_scale)
    scaled_length = math.sqrt(scaled_xy * scaled_xy + scaled_z * scaled_z)
    maximum_distance = 1.0 / scaled_length if scaled_length > 1e-8 else 1e8
    if distance > maximum_distance:
        sim.pos_ms[particle_index] = center + direction * maximum_distance


def satisfy_dyng_ellipsoids_vectorized(sim):
    if sim.ell_idx is None:
        return
    for constraint_index in range(len(sim.ell_idx)):
        satisfy_dyng_ellipsoid_at(sim, constraint_index)


def _distance_preserving_ray_position(
    line_start, line_direction, sphere_center, sphere_radius, previous_position,
):
    """Match REDengine's sphere-line branch selection for cone constraints."""
    line_start = np.asarray(line_start, dtype=np.float64)
    direction = np.asarray(line_direction, dtype=np.float64)
    sphere_center = np.asarray(sphere_center, dtype=np.float64)
    previous = np.asarray(previous_position, dtype=np.float64)

    direction_length = float(np.linalg.norm(direction))
    if direction_length <= 1e-12:
        return previous.astype(np.float32)
    direction /= direction_length

    oc = line_start - sphere_center
    b_coeff = 2.0 * float(np.dot(oc, direction))
    c_coeff = float(np.dot(oc, oc)) - float(sphere_radius) ** 2
    discriminant = b_coeff * b_coeff - 4.0 * c_coeff

    candidates = []
    if discriminant >= -1e-12:
        sqrt_disc = math.sqrt(max(0.0, discriminant))
        far_alpha = (-b_coeff + sqrt_disc) * 0.5
        near_alpha = (-b_coeff - sqrt_disc) * 0.5
        if near_alpha >= 0.0:
            candidates.append(line_start + direction * near_alpha)
        if far_alpha >= 0.0 and (
            not candidates or abs(far_alpha - near_alpha) > 1e-10
        ):
            candidates.append(line_start + direction * far_alpha)

    if candidates:
        return min(
            candidates,
            key=lambda point: float(np.dot(point - previous, point - previous)),
        ).astype(np.float32)

    alpha = max(0.0, float(np.dot(direction, previous - line_start)))
    return (line_start + direction * alpha).astype(np.float32)


def satisfy_pendulum_at(sim, constraint_index):
    if sim.cone_idx is None:
        return

    ci = int(constraint_index)
    particle_index = int(sim.cone_idx[ci])
    attachment_index = int(sim.cone_attach[ci])
    if not (sim.is_free[particle_index] and sim.active_mask[particle_index]):
        return

    cone_transform = (
        sim._interp_bone_xform[attachment_index] @ sim.cone_xform_ls[ci]
    )
    cone_origin = cone_transform.translation
    cone_rotation = cone_transform.to_quaternion()
    initial_axis = cone_rotation @ Vector((1.0, 0.0, 0.0))
    if initial_axis.length_squared <= 1e-12:
        return
    initial_axis.normalize()

    constrained_position = Vector(sim.pos_ms[particle_index])
    attachment_position = Vector(sim.pos_ms[attachment_index])
    cone_to_particle = constrained_position - cone_origin
    constraint_type = int(sim.cone_type[ci])
    if constraint_type != 0:
        orthogonal_axis = cone_rotation @ Vector((0.0, 0.0, 1.0))
        if orthogonal_axis.length_squared > 1e-12:
            orthogonal_axis.normalize()
            orthogonal_component = cone_to_particle.dot(orthogonal_axis)
            if constraint_type == 1 or orthogonal_component > 0.0:
                cone_to_particle -= orthogonal_axis * orthogonal_component

    if cone_to_particle.length_squared < 1e-12:
        return
    cone_to_particle.normalize()
    if initial_axis.dot(cone_to_particle) < float(sim.cone_cos[ci]):
        perpendicular = initial_axis.cross(cone_to_particle)
        if perpendicular.length > 1e-6:
            perpendicular.normalize()
            rotation = Quaternion((
                float(sim.cone_cos_hh[ci]),
                perpendicular.x * float(sim.cone_sin_hh[ci]),
                perpendicular.y * float(sim.cone_sin_hh[ci]),
                perpendicular.z * float(sim.cone_sin_hh[ci]),
            ))
            cone_to_particle = rotation @ initial_axis
            cone_to_particle.normalize()

    original_distance = (attachment_position - constrained_position).length
    if original_distance < 1e-6:
        return
    sim.pos_ms[particle_index] = _distance_preserving_ray_position(
        cone_origin,
        cone_to_particle,
        attachment_position,
        original_distance,
        constrained_position,
    )


def satisfy_pendulums_vectorized(sim):
    if sim.cone_idx is None:
        return
    for constraint_index in range(len(sim.cone_idx)):
        satisfy_pendulum_at(sim, constraint_index)

