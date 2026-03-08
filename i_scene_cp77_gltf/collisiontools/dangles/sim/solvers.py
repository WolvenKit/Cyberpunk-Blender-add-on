
import math
import bpy
import numpy as np
from mathutils import Vector, Matrix, Quaternion


def update_simulation(sim, raw_dt, time_dilation=1.0):
    sim.step_simulation(raw_dt, time_dilation)
    _apply_transforms_to_armature(sim)


def _build_lookat_map(sim):
    """Build a map of which bone should look at each particle, and with what axis."""
    lookat_map = {}

    for i, p_cfg in enumerate(sim.particles):
        dnode = sim.particle_dnode_map[i]
        pb = sim.arm_obj.pose.bones.get(p_cfg.bone_name)
        if pb and pb.parent:
            parent_idx = sim.bone_idx_map.get(pb.parent.name)

            bl_axis = Vector(getattr(dnode, 'look_at_axis', (0.0, 1.0, 0.0)))
            if bl_axis.length_squared < 1e-8:
                bl_axis = Vector((0, 1, 0))
            lookat_map[i] = (parent_idx, bl_axis.normalized(), False)

    if getattr(sim, 'link_idx_a', None) is not None:
        for li in range(len(sim.link_idx_a)):
            bone1_idx = sim.link_idx_a[li]
            bone2_idx = sim.link_idx_b[li]
            axis = Vector(sim.link_look_axes[li])
            if axis.length_squared < 1e-8:
                axis = Vector((0, 1, 0))
            lookat_map[bone2_idx] = (bone1_idx, axis.normalized(), True)

    return lookat_map


def _build_overlap_priority(sim):
    """For bones in multiple DangleNodes, pick the particle index with the highest solver_iterations."""
    best = {}
    for i, p in enumerate(sim.particles):
        dnode = sim.particle_dnode_map[i]
        dn_iters = dnode.solver_iterations
        bn = p.bone_name
        if bn not in best or dn_iters >= best[bn][1]:
            best[bn] = (i, dn_iters, dnode)
    return {bn: (idx, dn) for bn, (idx, _, dn) in best.items()}


def _apply_transforms_to_armature(sim):
    arm = sim.arm_obj
    if arm.mode != 'POSE':
        return

    overlap = _build_overlap_priority(sim)
    lookat_map = _build_lookat_map(sim)

    active_indices = set()
    for bn, (idx, _dn) in overlap.items():
        active_indices.add(idx)

    sorted_indices = sorted(
        active_indices,
        key=lambda i: arm.data.bones.find(sim.bone_names[i]),
    )

    requires_update = False

    for i in sorted_indices:
        if not sim.active_mask[i]:
            continue

        pb = arm.pose.bones.get(sim.bone_names[i])
        if not pb:
            continue

        dnode  = sim.particle_dnode_map[i]
        alpha  = getattr(dnode, 'alpha', 1.0)
        rotate_parent = getattr(dnode, 'rotate_parent_to_look_at', True)

        target_pos = Vector(sim.pos_ms[i])

        # Parent look-at rotation
        if rotate_parent and i in lookat_map:
            source_idx, look_axis, obligatory = lookat_map[i]

            if source_idx is not None:
                source_pb = arm.pose.bones.get(sim.bone_names[source_idx])
                if source_pb:
                    parent_mat = source_pb.matrix.copy()
                    parent_q   = parent_mat.to_quaternion()

                    from_parent_to_dangle = target_pos - parent_mat.translation
                    if from_parent_to_dangle.length_squared > 1e-8:
                        from_parent_to_dangle.normalize()

                        current_look = parent_q @ look_axis
                        dot_check = current_look.dot(from_parent_to_dangle)

                        if obligatory or abs(dot_check - 1.0) < 0.001:
                            target_rot = (
                                current_look.rotation_difference(
                                    from_parent_to_dangle
                                )
                                @ parent_q
                            )

                            if alpha < 1.0:
                                target_rot = parent_q.slerp(target_rot, alpha)

                            new_parent_mat = (
                                target_rot.to_matrix().to_4x4()
                            )
                            new_parent_mat.translation = parent_mat.translation
                            source_pb.matrix = new_parent_mat
                            requires_update = True

        # Set dangle bone position
        dangle_mat = pb.matrix.copy()
        if alpha < 1.0:
            target_pos = dangle_mat.translation.lerp(target_pos, alpha)

        dangle_mat.translation = target_pos
        pb.matrix = dangle_mat
        requires_update = True

    if requires_update:
        bpy.context.evaluated_depsgraph_get().update()
