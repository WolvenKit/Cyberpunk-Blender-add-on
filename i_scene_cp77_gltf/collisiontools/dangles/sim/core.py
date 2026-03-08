import math
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion
from . import constraints, collision
from .drag import DragPostProcessor

DAMPING_ACCEL_LIMIT = 50.0
MIN_TIME_DILATION   = 0.05
MAX_TIME_DILATION   = 1.0
MAX_PHYSICS_STEPS   = 3.0
LP_FILTER_RC        = 1.0

TELEPORT_KEEP_SQ  = 1.0
TELEPORT_RESET_SQ = 25.0

class DyngSimulator:
    def __init__(self, rig_obj):
        self.arm_obj = rig_obj
        self.state = rig_obj.dangle_state

        self.particles = []
        self.particle_dnode_map = []
        self._node_ranges = []
        self._node_iters = []

        offset = 0
        for dnode in self.state.dangle_nodes:
            start = offset
            for ch in dnode.chains:
                for p in ch.particles:
                    self.particles.append(p)
                    self.particle_dnode_map.append(dnode)
                    offset += 1
            self._node_ranges.append((start, offset))
            self._node_iters.append(dnode.solver_iterations)

        self.num_particles = len(self.particles)
        if self.num_particles == 0:
            return

        self.bone_names = [p.bone_name for p in self.particles]

        self._node_bone_maps = []
        for ni in range(len(self._node_ranges)):
            start, end = self._node_ranges[ni]
            nmap = {}
            for pi in range(start, end):
                bn = self.particles[pi].bone_name
                if bn not in nmap:
                    nmap[bn] = pi
            self._node_bone_maps.append(nmap)

        self._particle_node_idx = np.zeros(self.num_particles, dtype=np.int32)
        for ni, (start, end) in enumerate(self._node_ranges):
            self._particle_node_idx[start:end] = ni

        self.bone_idx_map = {name: i for i, name in enumerate(self.bone_names)}

        self._extra_bone_names = []
        for shape in self.state.collision_shapes:
            bn = shape.bone_name
            if bn and bn not in self.bone_idx_map:
                idx = self.num_particles + len(self._extra_bone_names)
                self.bone_idx_map[bn] = idx
                self._extra_bone_names.append(bn)
                self.bone_names.append(bn)

        for dnode in self.state.dangle_nodes:
            for shape in dnode.collision_shapes:
                bn = shape.bone_name
                if bn and bn not in self.bone_idx_map:
                    idx = self.num_particles + len(self._extra_bone_names)
                    self.bone_idx_map[bn] = idx
                    self._extra_bone_names.append(bn)
                    self.bone_names.append(bn)

        total_tracked = self.num_particles + len(self._extra_bone_names)

        self.pos_ms = np.zeros((total_tracked, 3), dtype=np.float32)
        self.vel_ms = np.zeros((total_tracked, 3), dtype=np.float32)
        self.prev_pos_ms = np.zeros((total_tracked, 3), dtype=np.float32)

        self.prev_bone_ms = np.zeros((total_tracked, 3), dtype=np.float32)
        self.cur_bone_ms = np.zeros((total_tracked, 3), dtype=np.float32)
        self.interp_bone_ms = np.zeros((total_tracked, 3), dtype=np.float32)

        self.is_free = np.zeros(total_tracked, dtype=bool)
        self.active_mask = np.ones(total_tracked, dtype=bool)
        self.mass = np.ones(total_tracked, dtype=np.float32)
        self.inv_mass = np.ones(total_tracked, dtype=np.float32)
        self.damping = np.zeros(total_tracked, dtype=np.float32)
        self.pull_force = np.zeros(total_tracked, dtype=np.float32)

        self.col_radius = np.zeros(total_tracked, dtype=np.float32)
        self.col_height = np.zeros(total_tracked, dtype=np.float32)
        self.col_axis_ls = np.zeros((total_tracked, 3), dtype=np.float32)
        self.proj_type = np.zeros(total_tracked, dtype=np.int32)

        self.prev_ext_force_ms = np.zeros(3, dtype=np.float32)
        self.cur_ext_force_ms = np.zeros(3, dtype=np.float32)
        self.prev_grav_ms = np.zeros(3, dtype=np.float32)
        self.cur_grav_ms = np.zeros(3, dtype=np.float32)

        self._interp_bone_xform = [Matrix.Identity(4)] * total_tracked

        self.time_remainder = 0.0
        self.damped_physics_steps = 1.0
        self.prev_matrix_world = rig_obj.matrix_world.copy()

        self._init_state()
        constraints.compile_constraints(self)
        collision.compile_collision_shapes(self)
        self._build_node_constraint_sets()

        self.drag_post = DragPostProcessor(self)

    def _init_state(self):
        for i, p_cfg in enumerate(self.particles):
            pb = self.arm_obj.pose.bones.get(p_cfg.bone_name)
            if pb:
                ms_head = np.array(pb.matrix.translation, dtype=np.float32)
                self.pos_ms[i] = ms_head
                self.prev_bone_ms[i] = ms_head
                self.cur_bone_ms[i] = ms_head

            self.is_free[i] = not p_cfg.is_pinned
            self.mass[i] = max(0.001, p_cfg.mass)
            self.inv_mass[i] = 0.0 if p_cfg.is_pinned else (1.0 / self.mass[i])
            self.damping[i] = p_cfg.damping
            self.pull_force[i] = p_cfg.pull_force
            self.col_radius[i] = p_cfg.capsule_radius
            self.col_height[i] = p_cfg.capsule_height
            self.col_axis_ls[i] = p_cfg.capsule_axis_ls
            self.proj_type[i] = (
                1 if p_cfg.dyng_projection_type == 'SHORTEST_PATH'
                else (2 if p_cfg.dyng_projection_type == 'DIRECTED' else 0)
            )

        for j, bn in enumerate(self._extra_bone_names):
            idx = self.num_particles + j
            pb = self.arm_obj.pose.bones.get(bn)
            if pb:
                ms_head = np.array(pb.matrix.translation, dtype=np.float32)
                self.prev_bone_ms[idx] = ms_head
                self.cur_bone_ms[idx] = ms_head

    def _build_node_constraint_sets(self):
        n_nodes = len(self.state.dangle_nodes)
        self._node_link_sel = [None] * n_nodes
        self._node_ell_sel = [None] * n_nodes
        self._node_cone_sel = [None] * n_nodes

        for ni in range(n_nodes):
            start, end = self._node_ranges[ni]
            pset = np.arange(start, end, dtype=np.int32)

            if getattr(self, 'link_idx_a', None) is not None:
                mask = np.isin(self.link_idx_a, pset)
                sel = np.where(mask)[0]
                if len(sel) > 0:
                    self._node_link_sel[ni] = sel

            if getattr(self, 'ell_idx', None) is not None:
                mask = np.isin(self.ell_idx, pset)
                sel = np.where(mask)[0]
                if len(sel) > 0:
                    self._node_ell_sel[ni] = sel

            if getattr(self, 'cone_idx', None) is not None:
                mask = np.isin(self.cone_idx, pset)
                sel = np.where(mask)[0]
                if len(sel) > 0:
                    self._node_cone_sel[ni] = sel

    def _save_constraint_arrays(self):
        saved = {}
        if getattr(self, 'link_idx_a', None) is not None:
            saved['link'] = (
                self.link_idx_a, self.link_idx_b, self.link_types,
                self.link_lower, self.link_upper, self.link_rest,
                self.link_look_axes,
            )
        if getattr(self, 'ell_idx', None) is not None:
            saved['ell'] = (
                self.ell_idx, self.ell_centers, self.ell_radii,
                self.ell_s1, self.ell_s2, self.ell_xform_ls,
            )
        if getattr(self, 'cone_idx', None) is not None:
            saved['cone'] = (
                self.cone_idx, self.cone_attach, self.cone_type,
                self.cone_cos, self.cone_sin_hh, self.cone_cos_hh,
                self.cone_xform_ls,
                self.cone_proj_type, self.cone_col_radius,
                self.cone_col_height,
            )
        return saved

    def _swap_node_constraints(self, node_idx):
        sel = self._node_link_sel[node_idx]
        if sel is not None and getattr(self, 'link_idx_a', None) is not None:
            self.link_idx_a = self._saved_constraints['link'][0][sel]
            self.link_idx_b = self._saved_constraints['link'][1][sel]
            self.link_types = self._saved_constraints['link'][2][sel]
            self.link_lower = self._saved_constraints['link'][3][sel]
            self.link_upper = self._saved_constraints['link'][4][sel]
            self.link_rest = self._saved_constraints['link'][5][sel]
            self.link_look_axes = self._saved_constraints['link'][6][sel]
        elif getattr(self, '_saved_link_was_set', False):
            self.link_idx_a = None

        sel = self._node_ell_sel[node_idx]
        if sel is not None and 'ell' in self._saved_constraints:
            self.ell_idx = self._saved_constraints['ell'][0][sel]
            self.ell_centers = self._saved_constraints['ell'][1][sel]
            self.ell_radii = self._saved_constraints['ell'][2][sel]
            self.ell_s1 = self._saved_constraints['ell'][3][sel]
            self.ell_s2 = self._saved_constraints['ell'][4][sel]
            self.ell_xform_ls = [
                self._saved_constraints['ell'][5][j] for j in sel
            ]
        elif getattr(self, '_saved_ell_was_set', False):
            self.ell_idx = None

        sel = self._node_cone_sel[node_idx]
        if sel is not None and 'cone' in self._saved_constraints:
            self.cone_idx = self._saved_constraints['cone'][0][sel]
            self.cone_attach = self._saved_constraints['cone'][1][sel]
            self.cone_type = self._saved_constraints['cone'][2][sel]
            self.cone_cos = self._saved_constraints['cone'][3][sel]
            self.cone_sin_hh = self._saved_constraints['cone'][4][sel]
            self.cone_cos_hh = self._saved_constraints['cone'][5][sel]
            self.cone_xform_ls = [
                self._saved_constraints['cone'][6][j] for j in sel
            ]
            self.cone_proj_type = self._saved_constraints['cone'][7][sel]
            self.cone_col_radius = self._saved_constraints['cone'][8][sel]
            self.cone_col_height = self._saved_constraints['cone'][9][sel]
        elif getattr(self, '_saved_cone_was_set', False):
            self.cone_idx = None

    def _restore_constraints(self):
        saved = self._saved_constraints
        if 'link' in saved:
            (self.link_idx_a, self.link_idx_b, self.link_types,
             self.link_lower, self.link_upper, self.link_rest,
             self.link_look_axes) = saved['link']
        if 'ell' in saved:
            (self.ell_idx, self.ell_centers, self.ell_radii,
             self.ell_s1, self.ell_s2, self.ell_xform_ls) = saved['ell']
        if 'cone' in saved:
            (self.cone_idx, self.cone_attach, self.cone_type,
             self.cone_cos, self.cone_sin_hh, self.cone_cos_hh,
             self.cone_xform_ls,
             self.cone_proj_type, self.cone_col_radius,
             self.cone_col_height) = saved['cone']

    def _update_kinematic_state(self):
        for i, bname in enumerate(self.bone_names):
            pb = self.arm_obj.pose.bones.get(bname)
            if pb is None:
                self.active_mask[i] = False
            else:
                hidden = pb.bone.hide or getattr(pb.bone, 'hide_viewport', False)
                self.active_mask[i] = not hidden

    def _update_bone_xforms(self):
        for i, bname in enumerate(self.bone_names):
            if not self.active_mask[i]:
                continue
            pb = self.arm_obj.pose.bones.get(bname)
            if pb:
                self._interp_bone_xform[i] = pb.matrix.copy()

    def _resolve_teleportation(self):
        cur_mw = self.arm_obj.matrix_world
        diff_sq = (
            cur_mw.translation - self.prev_matrix_world.translation
        ).length_squared
        skip_physics = False

        if diff_sq > TELEPORT_RESET_SQ:
            self.pos_ms[:self.num_particles] = (
                self.cur_bone_ms[:self.num_particles]
            )
            self.vel_ms.fill(0.0)
            skip_physics = True
        elif diff_sq > TELEPORT_KEEP_SQ:
            diff_transform = self.prev_matrix_world.inverted() @ cur_mw
            diff_rot_mat = np.array(
                diff_transform.to_quaternion().to_matrix(), dtype=np.float32
            )
            diff_trans = np.array(diff_transform.translation, dtype=np.float32)
            self.pos_ms[:self.num_particles] = (
                np.dot(self.pos_ms[:self.num_particles], diff_rot_mat.T)
                + diff_trans
            )
            self.vel_ms[:self.num_particles] = np.dot(
                self.vel_ms[:self.num_particles], diff_rot_mat.T
            )

        self.prev_matrix_world = cur_mw.copy()
        return skip_physics

    def _compute_accelerations(self, grav_ms, ext_ms):
        n = self.num_particles
        ext_accel = ext_ms * self.inv_mass[:n, np.newaxis]
        damp_accel = (
            self.vel_ms[:n]
            * (-self.damping[:n, np.newaxis] * self.inv_mass[:n, np.newaxis])
        )
        damp_norm = np.linalg.norm(damp_accel, axis=1, keepdims=True)
        safe_norm = np.where(damp_norm < 1e-6, 1.0, damp_norm)
        exceeds = damp_norm > DAMPING_ACCEL_LIMIT
        damp_accel = np.where(
            exceeds, (damp_accel / safe_norm) * DAMPING_ACCEL_LIMIT, damp_accel
        )
        pull_accel = (
            (self.interp_bone_ms[:n] - self.pos_ms[:n])
            * (self.pull_force[:n, np.newaxis] * self.inv_mass[:n, np.newaxis])
        )
        accel = grav_ms + damp_accel + ext_accel + pull_accel
        valid_mask = self.is_free[:n] & self.active_mask[:n]
        return np.where(valid_mask[:, np.newaxis], accel, 0.0)

    def step_simulation(self, raw_dt, time_dilation=1.0):
        if self.num_particles == 0:
            return

        n = self.num_particles
        self._update_kinematic_state()
        skip_physics = self._resolve_teleportation()

        substep_time = max(0.001, self.state.substep_time)

        self.time_remainder += raw_dt
        raw_physics_steps = int(self.time_remainder / substep_time)
        self.time_remainder -= raw_physics_steps * substep_time

        lp_alpha = raw_dt / (LP_FILTER_RC + raw_dt)
        self.damped_physics_steps += lp_alpha * (
            raw_physics_steps - self.damped_physics_steps
        )
        physics_steps = int(round(self.damped_physics_steps))
        physics_steps = max(1, min(physics_steps, int(MAX_PHYSICS_STEPS)))

        if time_dilation < MIN_TIME_DILATION:
            return

        substep_time_dilated = (
            min(MAX_TIME_DILATION, time_dilation) * substep_time
        )

        mw_inv_rot = self.arm_obj.matrix_world.to_quaternion().inverted()
        self.prev_ext_force_ms[:] = self.cur_ext_force_ms
        self.cur_ext_force_ms[:] = (
            mw_inv_rot @ Vector(self.state.external_force_ws)
        )
        self.prev_grav_ms[:] = self.cur_grav_ms
        physx_grav = bpy.context.scene.physx.gravity if bpy.context else Vector((0, 0, -9.81))
        self.cur_grav_ms[:] = (
            mw_inv_rot @ Vector(physx_grav)
        )

        total_tracked = len(self.bone_names)
        for i in range(total_tracked):
            if not self.active_mask[i]:
                continue
            pb = self.arm_obj.pose.bones.get(self.bone_names[i])
            if pb:
                self.prev_bone_ms[i] = self.cur_bone_ms[i]
                self.cur_bone_ms[i] = np.array(
                    pb.matrix.translation, dtype=np.float32
                )

        valid_mask = self.is_free[:n] & self.active_mask[:n]

        max_solver_iters = max(self._node_iters) if self._node_iters else 1
        if skip_physics:
            max_solver_iters = max(max_solver_iters, 1)

        self._saved_constraints = self._save_constraint_arrays()
        self._saved_link_was_set = getattr(self, 'link_idx_a', None) is not None
        self._saved_ell_was_set = getattr(self, 'ell_idx', None) is not None
        self._saved_cone_was_set = getattr(self, 'cone_idx', None) is not None

        collision.update_collision_transforms_begin(self)
        self._update_bone_xforms()

        num_nodes = len(self.state.dangle_nodes)

        for step in range(physics_steps):
            frame_progress = (step + 1.0) / physics_steps

            interp_ext = (
                self.prev_ext_force_ms
                + (self.cur_ext_force_ms - self.prev_ext_force_ms)
                * frame_progress
            )
            interp_grav = (
                self.prev_grav_ms
                + (self.cur_grav_ms - self.prev_grav_ms) * frame_progress
            )
            self.interp_bone_ms = (
                self.prev_bone_ms
                + (self.cur_bone_ms - self.prev_bone_ms) * frame_progress
            )
            self.prev_pos_ms[:n] = self.pos_ms[:n]

            if not skip_physics:
                accel = self._compute_accelerations(interp_grav, interp_ext)
                vel_half = (
                    self.vel_ms[:n] + accel * (substep_time_dilated * 0.5)
                )
                pred_pos = self.pos_ms[:n] + vel_half * substep_time_dilated
                self.pos_ms[:n] = np.where(
                    valid_mask[:, np.newaxis],
                    pred_pos,
                    self.interp_bone_ms[:n],
                )
            else:
                self.pos_ms[:n] = np.where(
                    valid_mask[:, np.newaxis],
                    self.pos_ms[:n],
                    self.interp_bone_ms[:n],
                )

            for iteration in range(max_solver_iters):
                for ni in range(num_nodes):
                    if iteration >= self._node_iters[ni]:
                        continue
                    self._swap_node_constraints(ni)
                    constraints.satisfy_dyng_links_vectorized(self)
                    constraints.satisfy_dyng_ellipsoids_vectorized(self)
                    constraints.satisfy_pendulums_vectorized(self)
                self._restore_constraints()

                collision.respond_to_collisions_vectorized(self, frame_progress)
                collision.respond_to_cone_collisions(self, frame_progress)

            if not skip_physics and substep_time_dilated > 0.0:
                accel = self._compute_accelerations(interp_grav, interp_ext)
                derived_vel = (
                    (self.pos_ms[:n] - self.prev_pos_ms[:n])
                    / substep_time_dilated
                    + accel * (0.5 * substep_time_dilated)
                )
                self.vel_ms[:n] = np.where(
                    valid_mask[:, np.newaxis], derived_vel, 0.0
                )

        if skip_physics:
            self.vel_ms.fill(0.0)

        self._saved_constraints = {}

        if self.drag_post.num_drags > 0:
            self.drag_post.step(raw_dt)