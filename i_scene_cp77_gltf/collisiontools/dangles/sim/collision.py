
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix
from .constraints import RE_BONE_CONV


def compile_collision_shapes(sim):
    """Build runtime collision shape data from addon properties."""
    sim.col_shapes = []
    for shape in sim.state.collision_shapes:
        # Build local-space transform matrix from offset + rotation
        rot_wxyz = shape.rotation_ls_quat
        ls_quat = Quaternion(rot_wxyz)
        ls_mat = ls_quat.to_matrix().to_4x4()
        ls_mat.translation = Vector(shape.offset_ls)

        # Pre-multiply RE_BONE_CONV, same convention as constraints.py
        adjusted_ls = RE_BONE_CONV @ ls_mat

        sim.col_shapes.append({
            'bone_name':  shape.bone_name,
            'is_capsule': shape.shape_type == 'CAPSULE',
            'radius':     shape.radius,
            'height':     shape.height_extent,
            'ls_mat':     adjusted_ls,
            # Runtime transforms: full QsTransform (prev + current)
            'prev_xform_ms': Matrix.Identity(4),
            'cur_xform_ms':  Matrix.Identity(4),
            # Interpolated for substep
            'pos_ms':      np.zeros(3, dtype=np.float32),
            'rot_ms':      Quaternion(),  # identity
            'axis_ms':     np.array([0, 0, 1], dtype=np.float32),
        })


def update_collision_transforms_begin(sim):
    """
    Called once per frame before the substep loop.
    """
    for shape in sim.col_shapes:
        shape['prev_xform_ms'] = shape['cur_xform_ms'].copy()

        pb = sim.arm_obj.pose.bones.get(shape['bone_name'])
        if not pb:
            continue

        # pb.matrix is in armature space (= model space)
        bone_mat_ms = pb.matrix
        # Full composition: shape_ms = bone_ms @ shape_ls
        shape_ms = bone_mat_ms @ shape['ls_mat']
        shape['cur_xform_ms'] = shape_ms


def update_collision_transforms(sim, frame_progress):
    """Interpolate collision shapes for the current substep (lerp + slerp)."""
    t = frame_progress
    for shape in sim.col_shapes:
        prev = shape['prev_xform_ms']
        cur = shape['cur_xform_ms']

        # Lerp translation
        t_prev = prev.translation
        t_cur = cur.translation
        interp_t = t_prev.lerp(t_cur, t)
        shape['pos_ms'] = np.array(interp_t, dtype=np.float32)

        # Slerp rotation
        q_prev = prev.to_quaternion()
        q_cur = cur.to_quaternion()
        interp_q = q_prev.slerp(q_cur, t)
        shape['rot_ms'] = interp_q

        if shape['is_capsule']:
            # Capsule Z-axis in model space from the interpolated shape rotation
            axis_ms = interp_q @ Vector((0.0, 0.0, 1.0))
            shape['axis_ms'] = np.array(axis_ms, dtype=np.float32)


def _closest_point_on_segment(p, a, b):
    """Closest point on segment a→b to each point in p (batched)."""
    ab = b - a
    ap = p - a
    ab_sq = np.sum(ab * ab, axis=-1)
    ab_sq = np.where(ab_sq < 1e-6, 1.0, ab_sq)
    t = np.clip(np.sum(ap * ab, axis=-1) / ab_sq, 0.0, 1.0)
    return a + t[:, np.newaxis] * ab


def _closest_point_on_segment_single(p, a, b):
    """Closest point on segment a→b to single point p (Vector or np)."""
    ab = b - a
    ap = p - a
    ab_sq = np.dot(ab, ab)
    if ab_sq < 1e-6:
        return a.copy()
    t = max(0.0, min(1.0, np.dot(ap, ab) / ab_sq))
    return a + ab * t


def respond_to_collisions_vectorized(sim, frame_progress):
    """Particle-level collision: ShortestPath and Directed projection types."""
    if not sim.col_shapes:
        return

    update_collision_transforms(sim, frame_progress)

    active_mask = sim.is_free & sim.active_mask & (sim.proj_type > 0)
    if not np.any(active_mask):
        return

    idx = np.where(active_mask)[0]
    p_pos   = sim.pos_ms[idx]
    p_types = sim.proj_type[idx]
    p_radii = sim.col_radius[idx]

    for shape in sim.col_shapes:
        c_pos    = shape['pos_ms']
        c_radius = shape['radius']

        if shape['is_capsule']:
            c_half_vec = shape['axis_ms'] * shape['height']
            c_a = c_pos - c_half_vec
            c_b = c_pos + c_half_vec
        else:
            c_a = c_pos
            c_b = c_pos

        # ShortestPath projection (sphere test)
        sp_mask = p_types == 1
        if np.any(sp_mask):
            sp_pos   = p_pos[sp_mask]
            sp_radii = p_radii[sp_mask]

            closest_on_c = _closest_point_on_segment(sp_pos, c_a, c_b)
            diff = sp_pos - closest_on_c
            dist = np.linalg.norm(diff, axis=-1)
            min_dist = sp_radii + c_radius

            pen_mask = dist < min_dist
            if np.any(pen_mask):
                pen_idx   = idx[sp_mask][pen_mask]
                push_dist = min_dist[pen_mask] - dist[pen_mask]
                safe_dist = np.where(
                    dist[pen_mask] < 1e-6, 1e-6, dist[pen_mask]
                )
                push_dir = diff[pen_mask] / safe_dist[:, np.newaxis]
                sim.pos_ms[pen_idx] += push_dir * push_dist[:, np.newaxis]

        # Directed projection (capsule-axis aligned push)
        dir_mask = p_types == 2
        if np.any(dir_mask):
            dir_pos   = p_pos[dir_mask]
            dir_radii = p_radii[dir_mask]
            dir_heights = sim.col_height[idx[dir_mask]]
            dir_idx_global = idx[dir_mask]

            # Compute capsule axes in model space from bone transforms
            dir_axes = np.zeros_like(dir_pos)
            for li, b_idx in enumerate(dir_idx_global):
                xform = sim._interp_bone_xform[b_idx]
                axis_ls = Vector(sim.col_axis_ls[b_idx])
                if axis_ls.length_squared < 1e-8:
                    axis_ls = Vector((0.5, 0, 0))
                axis_ms = xform.to_quaternion() @ axis_ls.normalized()
                dir_axes[li] = np.array(axis_ms, dtype=np.float32)

            # Test 3 points along the particle capsule
            p_half_vec = dir_axes * dir_heights[:, np.newaxis]
            test_points = np.stack(
                [dir_pos - p_half_vec, dir_pos, dir_pos + p_half_vec], axis=1
            )

            for pt_idx in range(3):
                pts = test_points[:, pt_idx, :]
                closest_on_c = _closest_point_on_segment(pts, c_a, c_b)
                diff = pts - closest_on_c
                dist = np.linalg.norm(diff, axis=-1)
                min_dist = dir_radii + c_radius

                pen_mask = dist < min_dist
                if np.any(pen_mask):
                    pen_idx_global = dir_idx_global[pen_mask]
                    safe_dist = np.where(
                        dist[pen_mask] < 1e-6, 1e-6, dist[pen_mask]
                    )
                    radial_dir = diff[pen_mask] / safe_dist[:, np.newaxis]
                    radial_push = min_dist[pen_mask] - dist[pen_mask]
                    optimal_push = radial_dir * radial_push[:, np.newaxis]
                    axis_vec = dir_axes[pen_mask]
                    push_along = np.sum(optimal_push * axis_vec, axis=-1)
                    sim.pos_ms[pen_idx_global] += (
                        axis_vec * push_along[:, np.newaxis]
                    )



def respond_to_cone_collisions(sim, frame_progress):
    """
    For each cone constraint with collision enabled, test the capsule segment
    (attachment → constrained) against body shapes and rotate to resolve.
    """
    if not hasattr(sim, 'cone_idx') or sim.cone_idx is None:
        return
    if not sim.col_shapes:
        return

    for ci in range(len(sim.cone_idx)):
        p_idx = sim.cone_idx[ci]
        a_idx = sim.cone_attach[ci]

        proj_type = sim.cone_proj_type[ci]
        if proj_type == 0:  # Disabled
            continue

        cap_radius = sim.cone_col_radius[ci]
        cap_height = sim.cone_col_height[ci]

        if cap_radius <= 0.0 and cap_height <= 0.0:
            continue

        if not (sim.is_free[p_idx] and sim.active_mask[p_idx]):
            continue

        constrained_pos = sim.pos_ms[p_idx].copy()
        attachment_pos = sim.pos_ms[a_idx].copy()

        parent_to_bob = constrained_pos - attachment_pos
        seg_len = np.linalg.norm(parent_to_bob)
        if seg_len < 1e-6:
            continue
        parent_to_bob_dir = parent_to_bob / seg_len

        for shape in sim.col_shapes:
            c_pos = shape['pos_ms']
            c_rot = shape['rot_ms']
            c_radius = shape['radius']

            # Transform positions to shape-local space
            inv_rot = c_rot.conjugated()
            attach_ss = np.array(
                inv_rot @ Vector(attachment_pos - c_pos), dtype=np.float32
            )
            dir_ss = np.array(
                inv_rot @ Vector(parent_to_bob_dir), dtype=np.float32
            )

            # Check attachment isn't already inside the shape
            attach_dist = _shape_distance_simplified(
                shape, attach_ss, cap_radius
            )
            if attach_dist < 0.001:
                continue  # Attachment inside shape — can't resolve

            # Test capsule overlap: sample along the segment
            # Simplified overlap test for sphere/capsule body shapes
            if shape['is_capsule']:
                c_half_vec = np.array(
                    inv_rot @ Vector((0, 0, shape['height'])), dtype=np.float32
                )
                c_a_ss = -c_half_vec
                c_b_ss = c_half_vec
            else:
                c_a_ss = np.zeros(3, dtype=np.float32)
                c_b_ss = np.zeros(3, dtype=np.float32)

            # Test multiple points along the cone capsule segment
            n_test = 3
            any_overlap = False
            for ti in range(n_test):
                t_frac = ti / max(1, n_test - 1)
                test_pt = attach_ss + dir_ss * (seg_len * t_frac)
                closest = _closest_point_on_segment_single(
                    test_pt, c_a_ss, c_b_ss
                )
                diff = test_pt - closest
                dist = np.linalg.norm(diff)
                if dist < cap_radius + c_radius:
                    any_overlap = True
                    break

            if not any_overlap:
                continue

            #  Resolve via ShortestPathRotational 
            # Find the direction that moves the segment out of the shape.
            # Strategy: push the midpoint of the capsule segment away from
            # the closest point on the body shape, then re-derive direction.
            mid_ss = attach_ss + dir_ss * (seg_len * 0.5)
            closest_mid = _closest_point_on_segment_single(
                mid_ss, c_a_ss, c_b_ss
            )
            push_vec_ss = mid_ss - closest_mid
            push_len = np.linalg.norm(push_vec_ss)

            if push_len < 1e-6:
                # Degenerate — push along arbitrary perpendicular
                push_vec_ss = _perpendicular(dir_ss)
                push_len = 1.0

            push_dir_ss = push_vec_ss / push_len
            needed_push = (cap_radius + c_radius) - push_len
            if needed_push <= 0:
                continue

            # Rotate the direction in shape-space: project the push onto
            # the plane perpendicular to the attachment→bob direction
            radial_component = push_dir_ss - dir_ss * np.dot(push_dir_ss, dir_ss)
            radial_len = np.linalg.norm(radial_component)
            if radial_len < 1e-6:
                radial_component = _perpendicular(dir_ss)
                radial_len = np.linalg.norm(radial_component)
            radial_component /= radial_len

            # Compute rotation angle needed
            rotation_angle = np.arcsin(
                min(1.0, needed_push / max(seg_len * 0.5, 1e-6))
            )

            # Build rotation: rotate dir_ss toward radial_component
            new_dir_ss = (
                dir_ss * np.cos(rotation_angle)
                + radial_component * np.sin(rotation_angle)
            )
            new_dir_len = np.linalg.norm(new_dir_ss)
            if new_dir_len > 1e-6:
                new_dir_ss /= new_dir_len

            # Transform back to model space
            new_dir_ms = np.array(
                c_rot @ Vector(new_dir_ss), dtype=np.float32
            )

            # New position: preserve distance from attachment
            new_pos = attachment_pos + new_dir_ms * seg_len
            sim.pos_ms[p_idx] = new_pos

            # Update local state for subsequent shapes
            constrained_pos = new_pos
            parent_to_bob = constrained_pos - attachment_pos
            seg_len_check = np.linalg.norm(parent_to_bob)
            if seg_len_check > 1e-6:
                parent_to_bob_dir = parent_to_bob / seg_len_check


def _shape_distance_simplified(shape, point_ss, particle_radius):
    """
    Simplified distance from point (in shape space) to the body shape surface.
    Returns positive if outside, negative if inside.
    """
    c_radius = shape['radius']
    if shape['is_capsule']:
        c_height = shape['height']
        # Closest point on capsule axis segment
        c_a = np.array([0, 0, -c_height], dtype=np.float32)
        c_b = np.array([0, 0, c_height], dtype=np.float32)
        closest = _closest_point_on_segment_single(point_ss, c_a, c_b)
        dist = np.linalg.norm(point_ss - closest)
    else:
        dist = np.linalg.norm(point_ss)
    return dist - c_radius - particle_radius


def _perpendicular(v):
    """Return a vector perpendicular to v."""
    if abs(v[0]) < 0.9:
        cross = np.cross(v, np.array([1, 0, 0], dtype=np.float32))
    else:
        cross = np.cross(v, np.array([0, 1, 0], dtype=np.float32))
    n = np.linalg.norm(cross)
    return cross / n if n > 1e-6 else np.array([0, 1, 0], dtype=np.float32)
