
import math
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix


# Bone-space conversion constant
# Rotation(+90deg, Z) applied as:  bone_re_compat = bone_blender @ RE_BONE_CONV
# This makes column-0 (X) of the result = bone forward direction.
# For axis vectors:  bl_axis = RE_BONE_CONV @ re_axis   maps (1,0,0)->(0,1,0)
RE_BONE_CONV = Quaternion((0, 0, 1), math.radians(90)).to_matrix().to_4x4()


def _resolve_bone(sim, particle_idx, bone_name):
    """Resolve a bone name to a flat particle index."""
    if hasattr(sim, '_node_bone_maps') and hasattr(sim, '_particle_node_idx'):
        ni = int(sim._particle_node_idx[particle_idx])
        idx = sim._node_bone_maps[ni].get(bone_name)
        if idx is not None:
            return idx
    return sim.bone_idx_map.get(bone_name)


# Compilation — build flat numpy arrays from the authored property groups.

def compile_constraints(sim):
    _compile_links(sim)
    _compile_ellipsoids(sim)
    _compile_cones(sim)


#  Links 
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

            # Rest distance: prefer cached value, else compute from pose
            if c.explicit_rest_distance > 0.0:
                rest.append(c.explicit_rest_distance)
            else:
                rest.append(
                    float(np.linalg.norm(sim.pos_ms[i] - sim.pos_ms[tgt_idx]))
                )

            # Per-link look-at axis:
            # Stored in Blender bone-local space (Y=forward) since v3.6.
            bl_axis = Vector(getattr(c, 'look_at_axis', (0.0, 1.0, 0.0)))
            if bl_axis.length_squared > 1e-8:
                bl_axis.normalize()
            else:
                bl_axis = Vector((0, 1, 0))  # Blender bone-forward fallback
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


#  Ellipsoids 
def _compile_ellipsoids(sim):
    ell_idx, ell_centers, ell_radii, ell_s1, ell_s2 = [], [], [], [], []
    ell_xform_ls = []  # per-ellipsoid local-space 4x4 (RE_BONE_CONV @ authored)

    for i, p_cfg in enumerate(sim.particles):
        for c in p_cfg.ellipsoid_constraints:
            tgt_idx = _resolve_bone(sim, i, c.target_bone)
            if tgt_idx is not None:
                ell_idx.append(i)
                ell_centers.append(tgt_idx)
                ell_radii.append(c.radius)
                ell_s1.append(c.scale1)
                ell_s2.append(c.scale2)

                # Build local-space transform from authored quat + offset
                xf = getattr(c, 'ellipsoid_transform_ls_quat',
                             (1.0, 0.0, 0.0, 0.0))
                q = Quaternion(xf)  # already wxyz
                off = Vector(getattr(c, 'ellipsoid_transform_ls_offset',
                                     (0.0, 0.0, 0.0)))
                ls_mat = q.to_matrix().to_4x4()
                ls_mat.translation = off
                # Pre-multiply by RE_BONE_CONV (same convention as cones):
                # ellipsoidTransformMS = bone_BL @ RE_BONE_CONV @ ellipsoidTransformLS
                ell_xform_ls.append(RE_BONE_CONV @ ls_mat)

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


#  Cones (Pendulums) 
def _compile_cones(sim):
    """
    Compile Cone Constraints.
    """
    c_idx, c_attach, c_type, c_cos, c_sin_hh, c_cos_hh = (
        [], [], [], [], [], []
    )
    c_cone_xform_adjusted = []  # list of 4x4 Matrices (already converted)
    c_proj_type = []   # pendulum projection type (0=disabled)
    c_col_radius = []  # cone collision capsule radius
    c_col_height = []  # cone collision capsule height extent

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

            # Cone collision capsule fields (for respond_to_cone_collisions)
            proj_val = {
                'DISABLED': 0,
                'SHORTEST_PATH_ROTATIONAL': 1,
                'DIRECTED_ROTATIONAL': 2,
            }.get(getattr(c, 'projection_type', 'DISABLED'), 0)
            c_proj_type.append(proj_val)
            c_col_radius.append(getattr(c, 'cone_collision_radius', 0.0))
            c_col_height.append(getattr(c, 'cone_collision_height', 0.0))

            # Parse coneTransformLS from authored quaternion (wxyz order)
            xf = getattr(c, 'cone_transform_ls_quat', (1.0, 0.0, 0.0, 0.0))
            q = Quaternion(xf)  # already wxyz
            raw_ls = q.to_matrix().to_4x4()

            adjusted_ls = RE_BONE_CONV @ raw_ls
            c_cone_xform_adjusted.append(adjusted_ls)

    if c_idx:
        sim.cone_idx        = np.array(c_idx, dtype=np.int32)
        sim.cone_attach     = np.array(c_attach, dtype=np.int32)
        sim.cone_type       = np.array(c_type, dtype=np.int32)
        sim.cone_cos        = np.array(c_cos, dtype=np.float32)
        sim.cone_sin_hh     = np.array(c_sin_hh, dtype=np.float32)
        sim.cone_cos_hh     = np.array(c_cos_hh, dtype=np.float32)
        sim.cone_xform_ls   = c_cone_xform_adjusted  # already includes RE_BONE_CONV
        sim.cone_proj_type  = np.array(c_proj_type, dtype=np.int32)
        sim.cone_col_radius = np.array(c_col_radius, dtype=np.float32)
        sim.cone_col_height = np.array(c_col_height, dtype=np.float32)
    else:
        sim.cone_idx        = None
        sim.cone_proj_type  = None
        sim.cone_col_radius = None
        sim.cone_col_height = None

    # Legacy aliases
    sim.pen_idx = sim.cone_idx if hasattr(sim, 'cone_idx') else None


# Link Solver

def satisfy_dyng_links_vectorized(sim):
    """Satisfy Distance Links"""
    if sim.link_idx_a is None:
        return

    p1 = sim.pos_ms[sim.link_idx_a]
    p2 = sim.pos_ms[sim.link_idx_b]
    diff = p2 - p1

    cur_len = np.linalg.norm(diff, axis=1)
    zero_mask = cur_len < 1e-6
    diff[zero_mask] = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    cur_len[zero_mask] = 1.0

    norm_diff = diff / cur_len[:, np.newaxis]
    desired_len = np.copy(sim.link_rest)

    # KeepFixedDistance: target = lower_ratio * rest
    fixed_mask = sim.link_types == 0
    desired_len[fixed_mask] = (
        sim.link_lower[fixed_mask] * sim.link_rest[fixed_mask]
    )

    # KeepVariableDistance: clamp current length to [lower*rest, upper*rest]
    var_mask = sim.link_types == 1
    desired_len[var_mask] = np.clip(
        cur_len[var_mask],
        sim.link_lower[var_mask] * sim.link_rest[var_mask],
        sim.link_upper[var_mask] * sim.link_rest[var_mask],
    )

    # Greater: enforce minimum
    grt_mask = sim.link_types == 2
    desired_len[grt_mask] = np.maximum(
        cur_len[grt_mask],
        sim.link_lower[grt_mask] * sim.link_rest[grt_mask],
    )

    # Closer: enforce maximum
    cls_mask = sim.link_types == 3
    desired_len[cls_mask] = np.minimum(
        cur_len[cls_mask],
        sim.link_upper[cls_mask] * sim.link_rest[cls_mask],
    )

    error = cur_len - desired_len
    active_mask = np.abs(error) > 1e-7
    if not np.any(active_mask):
        return

    # Mass-weighted bilateral correction
    m1 = sim.mass[sim.link_idx_a]
    m2 = sim.mass[sim.link_idx_b]
    free1 = sim.is_free[sim.link_idx_a] & sim.active_mask[sim.link_idx_a]
    free2 = sim.is_free[sim.link_idx_b] & sim.active_mask[sim.link_idx_b]

    m_total = m1 + m2
    f1 = np.where(
        free1 & free2, 1.0 - (m1 / m_total), np.where(free1, 1.0, 0.0)
    )
    f2 = np.where(
        free1 & free2, 1.0 - (m2 / m_total), np.where(free2, 1.0, 0.0)
    )

    active_error = error * active_mask
    corr_1 = (active_error * f1)[:, np.newaxis]
    corr_2 = (active_error * f2)[:, np.newaxis]

    np.add.at(sim.pos_ms, sim.link_idx_a,  norm_diff * corr_1)
    np.add.at(sim.pos_ms, sim.link_idx_b, -norm_diff * corr_2)


# Ellipsoid Solver

def satisfy_dyng_ellipsoids_vectorized(sim):
    """Satisfy Ellipsoid Constraints"""
    if sim.ell_idx is None:
        return

    active_free = sim.is_free[sim.ell_idx] & sim.active_mask[sim.ell_idx]
    if not np.any(active_free):
        return

    #  Compute per-ellipsoid model-space center + Z-axis 
    n_active = int(np.sum(active_free))
    af_indices = np.where(active_free)[0]
    center_ms_all = np.zeros((n_active, 3), dtype=np.float32)
    z_axis_all = np.zeros((n_active, 3), dtype=np.float32)

    has_xforms = hasattr(sim, 'ell_xform_ls') and len(sim.ell_xform_ls) > 0

    for li, ai in enumerate(af_indices):
        ci = sim.ell_centers[ai]
        if has_xforms and ai < len(sim.ell_xform_ls):
            bone_xf = sim._interp_bone_xform[ci]
            ell_ms = bone_xf @ sim.ell_xform_ls[ai]
            center_ms_all[li] = np.array(ell_ms.translation, dtype=np.float32)
            z_axis_all[li] = np.array(
                ell_ms.to_quaternion() @ Vector((0, 0, 1)), dtype=np.float32
            )
        else:
            center_ms_all[li] = sim.interp_bone_ms[ci]
            z_axis_all[li] = np.array([0, 0, 1], dtype=np.float32)

    idx   = sim.ell_idx[active_free]
    pos   = sim.pos_ms[idx]
    radii = sim.ell_radii[active_free]
    s1    = sim.ell_s1[active_free]
    s2    = sim.ell_s2[active_free]

    center_to_p = pos - center_ms_all
    dist = np.linalg.norm(center_to_p, axis=1)

    valid = dist > 1e-4
    if not np.any(valid):
        return

    idx         = idx[valid]
    center_ms   = center_ms_all[valid]
    z_axis      = z_axis_all[valid]
    center_to_p = center_to_p[valid]
    dist        = dist[valid]
    radii       = radii[valid]
    s1          = s1[valid]
    s2          = s2[valid]

    direction = center_to_p / dist[:, np.newaxis]

    # Z component in ellipsoid frame = dot(direction, z_axis)
    z_comp = np.sum(direction * z_axis, axis=1)
    z_scale = np.where(z_comp < 0, s1, s2)

    # XY distance in ellipsoid frame = |direction - z_comp * z_axis|
    z_proj = z_comp[:, np.newaxis] * z_axis
    xy_vec = direction - z_proj
    xy_len = np.linalg.norm(xy_vec, axis=1)

    # Scaled ellipsoid test:  (xy/r)^2 + (z/(r*z_scale))^2
    scaled_xy = xy_len / radii
    scaled_z  = z_comp / (radii * z_scale)
    scaled_len = np.sqrt(scaled_xy * scaled_xy + scaled_z * scaled_z)

    # Effective maximum distance from center along this direction
    max_dist = np.where(scaled_len > 1e-8, 1.0 / scaled_len, 1e8)

    outside = dist > max_dist
    if np.any(outside):
        sim.pos_ms[idx[outside]] = (
            center_ms[outside]
            + direction[outside] * max_dist[outside][:, np.newaxis]
        )


# Cone (Pendulum) Solver

def satisfy_pendulums_vectorized(sim):
    """Satisfy Cone (Pendulum) Constraints"""
    if sim.cone_idx is None:
        return

    for ci in range(len(sim.cone_idx)):
        p_idx     = sim.cone_idx[ci]
        a_idx     = sim.cone_attach[ci]
        c_type    = sim.cone_type[ci]
        cos_half  = sim.cone_cos[ci]
        sin_hh    = sim.cone_sin_hh[ci]
        cos_hh    = sim.cone_cos_hh[ci]
        xform_ls  = sim.cone_xform_ls[ci]   # already RE_BONE_CONV @ raw_ls

        if not (sim.is_free[p_idx] and sim.active_mask[p_idx]):
            continue

        # coneTransformMS = attachBone_BL @ (RE_BONE_CONV @ coneTransformLS)
        attach_xform = sim._interp_bone_xform[a_idx]
        cone_xform_ms = attach_xform @ xform_ls

        cone_origin_ms = Vector(cone_xform_ms.translation)
        cone_rot       = cone_xform_ms.to_quaternion()

        # Cone axis = X-axis of coneTransformMS (now correctly along bone chain)
        initial_axis = Vector(cone_rot @ Vector((1, 0, 0)))
        initial_axis.normalize()

        constrained_pos = Vector(sim.pos_ms[p_idx])
        attachment_pos  = Vector(sim.pos_ms[a_idx])

        cone_to_particle = constrained_pos - cone_origin_ms

        #  HingePlane / HalfCone: project out the Z-axis component 
        if c_type != 0:  # not pure Cone
            ortho_axis = Vector(cone_rot @ Vector((0, 0, 1)))
            ortho_axis.normalize()

            if c_type == 1:  # HingePlane: remove all Z-component
                dot_z = cone_to_particle.dot(ortho_axis)
                cone_to_particle -= ortho_axis * dot_z
            elif c_type == 2:  # HalfCone: remove positive Z only
                dot_z = cone_to_particle.dot(ortho_axis)
                if dot_z > 0:
                    cone_to_particle -= ortho_axis * dot_z

        if cone_to_particle.length_squared < 1e-12:
            continue

        cone_to_particle.normalize()

        #  Check if outside cone aperture 
        dot_val = initial_axis.dot(cone_to_particle)
        if dot_val < cos_half:
            # Rotate initial_axis to the cone boundary using Rodrigues
            perp = initial_axis.cross(cone_to_particle)
            perp_len = perp.length
            if perp_len > 1e-6:
                perp.normalize()
                q_rot = Quaternion(
                    (cos_hh, perp.x * sin_hh, perp.y * sin_hh, perp.z * sin_hh)
                )
                cone_to_particle = q_rot @ initial_axis
                cone_to_particle.normalize()

        #  Distance preservation via sphere-ray intersection 
        original_dist = (attachment_pos - constrained_pos).length
        if original_dist < 1e-6:
            continue

        oc = cone_origin_ms - attachment_pos
        b_coeff = 2.0 * oc.dot(cone_to_particle)
        c_coeff = oc.length_squared - original_dist * original_dist
        discriminant = b_coeff * b_coeff - 4.0 * c_coeff

        if discriminant >= 0:
            sqrt_disc = discriminant ** 0.5
            t1 = (-b_coeff + sqrt_disc) * 0.5
            t2 = (-b_coeff - sqrt_disc) * 0.5

            candidates = sorted([t for t in [t1, t2] if t >= 0])
            if candidates:
                new_pos = cone_origin_ms + cone_to_particle * candidates[0]
            else:
                t_closest = max(0.0, -b_coeff * 0.5)
                closest = cone_origin_ms + cone_to_particle * t_closest
                to_closest = closest - attachment_pos
                if to_closest.length > 1e-6:
                    to_closest.normalize()
                new_pos = attachment_pos + to_closest * original_dist
        else:
            t_closest = max(0.0, -b_coeff * 0.5)
            closest = cone_origin_ms + cone_to_particle * t_closest
            to_closest = closest - attachment_pos
            if to_closest.length > 1e-6:
                to_closest.normalize()
            new_pos = attachment_pos + to_closest * original_dist

        sim.pos_ms[p_idx] = np.array(new_pos, dtype=np.float32)