import numpy as np
import bpy
from mathutils import Vector, Matrix
from . import constraints, collision, spaces, spring, pendulum
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
        self._node_solver_types = []

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
            self._node_solver_types.append(
                dnode.chains[0].solver if dnode.chains else 'DYNG'
            )

        self.num_particles = len(self.particles)

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

        self.bone_idx_map = {}
        for i, name in enumerate(self.bone_names):
            self.bone_idx_map.setdefault(name, i)

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

        for node_index, solver_type in enumerate(self._node_solver_types):
            if solver_type not in {'PBD', 'SPRING', 'PENDULUM'}:
                continue
            start, end = self._node_ranges[node_index]
            if start >= end:
                continue
            particle = self.particles[start]
            pose_bone = self.arm_obj.pose.bones.get(particle.bone_name)
            required_names = []
            if solver_type == 'PBD':
                required_names.append(particle.direction_reference_bone)
            if pose_bone is not None and pose_bone.parent is not None:
                required_names.append(pose_bone.parent.name)
            for bone_name in required_names:
                if bone_name and bone_name not in self.bone_idx_map:
                    index = self.num_particles + len(self._extra_bone_names)
                    self.bone_idx_map[bone_name] = index
                    self._extra_bone_names.append(bone_name)
                    self.bone_names.append(bone_name)

        for drag_node in self.state.drag_nodes:
            source_name = drag_node.source_bone_name or drag_node.bone_name
            for bn in (source_name, drag_node.bone_name):
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

        node_count = len(self.state.dangle_nodes)
        self._node_prev_ext_force_ms = np.zeros((node_count, 3), dtype=np.float32)
        self._node_cur_ext_force_ms = np.zeros((node_count, 3), dtype=np.float32)
        self._node_prev_grav_ms = np.zeros((node_count, 3), dtype=np.float32)
        self._node_cur_grav_ms = np.zeros((node_count, 3), dtype=np.float32)
        self._node_time_remainder = np.zeros(node_count, dtype=np.float64)
        self._node_damped_physics_steps = np.ones(node_count, dtype=np.float32)
        self._node_simulation_needs_initialization = np.array(
            [solver_type == 'DYNG' for solver_type in self._node_solver_types],
            dtype=bool,
        )

        self._prev_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._cur_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._interp_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._input_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._last_output_bone_xform = [None for _ in range(total_tracked)]
        self._input_bone_basis = {}
        self._last_output_bone_basis = {}
        self._feedback_bone_names = set()

        self.prev_matrix_world = rig_obj.matrix_world.copy()

        self._init_state()
        self._initialize_node_forces()
        constraints.compile_constraints(self)
        collision.compile_collision_shapes(self)
        self._build_node_constraint_sets()
        self._build_authored_constraint_order()
        self._compile_position_projection_nodes()
        spring.compile_spring_nodes(self)
        pendulum.compile_pendulum_nodes(self)

        self.drag_post = DragPostProcessor(self)
        self.execution_plan = self._build_execution_plan()
        self._initialize_node_input_history()
        self._build_feedback_bone_set()

    def _build_execution_plan(self):
        plan = []
        operations = getattr(self.state, 'evaluation_order', ())
        config_to_runtime = getattr(
            self.drag_post, 'config_to_runtime', {}
        )
        for operation in operations:
            node_type = getattr(operation, 'node_type', '')
            node_index = int(getattr(operation, 'node_index', -1))
            if node_type == 'DANGLE':
                if 0 <= node_index < len(self._node_ranges):
                    plan.append(('DANGLE', node_index))
            elif node_type == 'DRAG':
                runtime_index = config_to_runtime.get(node_index)
                if runtime_index is not None:
                    plan.append(('DRAG', int(runtime_index)))

        if not plan:
            plan.extend(
                ('DANGLE', node_index)
                for node_index in range(len(self._node_ranges))
            )
            plan.extend(
                ('DRAG', runtime_index)
                for runtime_index in range(self.drag_post.num_drags)
            )
        return plan

    def _capture_tracked_pose(self):
        matrices = []
        for bone_name in self.bone_names:
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            matrices.append(
                pose_bone.matrix.copy()
                if pose_bone is not None else Matrix.Identity(4)
            )
        return matrices

    def _initialize_node_input_history(self):
        initial = self._capture_tracked_pose()
        node_count = len(self._node_ranges)
        self._node_input_previous = [
            [matrix.copy() for matrix in initial]
            for _ in range(node_count)
        ]
        self._node_input_current = [
            [matrix.copy() for matrix in initial]
            for _ in range(node_count)
        ]

    def _sample_base_input_pose(self):
        for index, bone_name in enumerate(self.bone_names):
            if not self.active_mask[index]:
                continue
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            if pose_bone is None:
                continue
            matrix = pose_bone.matrix.copy()
            self._input_bone_xform[index] = matrix.copy()
            self.cur_bone_ms[index] = np.asarray(
                matrix.translation, dtype=np.float32
            )
            self._cur_bone_xform[index] = matrix

    def _sample_node_input(self, node_index):
        previous = self._node_input_current[node_index]
        current = self._capture_tracked_pose()
        self._node_input_previous[node_index] = [
            matrix.copy() for matrix in previous
        ]
        self._node_input_current[node_index] = [
            matrix.copy() for matrix in current
        ]

        for index in range(len(self.bone_names)):
            previous_matrix = previous[index]
            current_matrix = current[index]
            self._prev_bone_xform[index] = previous_matrix.copy()
            self._cur_bone_xform[index] = current_matrix.copy()
            self.prev_bone_ms[index] = np.asarray(
                previous_matrix.translation, dtype=np.float32
            )
            self.cur_bone_ms[index] = np.asarray(
                current_matrix.translation, dtype=np.float32
            )
            self._input_bone_xform[index] = current_matrix.copy()

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
            node_solver = self._node_solver_types[
                int(self._particle_node_idx[i])
            ]
            if node_solver == 'SPRING':
                self.col_radius[i] = p_cfg.spring_collision_radius
                self.col_height[i] = 0.0
                axis_bl = spaces.re_axis_to_blender_bone(
                    (1.0, 0.0, 0.0), self.arm_obj
                )
                projection_type = p_cfg.spring_projection_type
            else:
                self.col_radius[i] = p_cfg.capsule_radius
                self.col_height[i] = p_cfg.capsule_height
                axis_bl = spaces.re_axis_to_blender_bone(
                    p_cfg.capsule_axis_ls, self.arm_obj
                )
                projection_type = (
                    p_cfg.pos_projection_type
                    if node_solver == 'PBD'
                    else p_cfg.dyng_projection_type
                )
            self.col_axis_ls[i] = np.array(axis_bl, dtype=np.float32)
            self.proj_type[i] = (
                1 if projection_type == 'SHORTEST_PATH'
                else (
                    2 if projection_type in {'DIRECTED', 'DIRECTIONAL'}
                    else 0
                )
            )

        for i, bn in enumerate(self.bone_names):
            pb = self.arm_obj.pose.bones.get(bn)
            if pb is None:
                self.active_mask[i] = False
                continue
            matrix = pb.matrix.copy()
            ms_head = np.array(matrix.translation, dtype=np.float32)
            self.prev_bone_ms[i] = ms_head
            self.cur_bone_ms[i] = ms_head
            self.interp_bone_ms[i] = ms_head
            self._prev_bone_xform[i] = matrix.copy()
            self._cur_bone_xform[i] = matrix.copy()
            self._interp_bone_xform[i] = matrix.copy()
            self._input_bone_xform[i] = matrix.copy()
            if i >= self.num_particles:
                self.pos_ms[i] = ms_head

    def _compile_position_projection_nodes(self):
        self._position_projection_nodes = {}
        for node_index, solver_type in enumerate(self._node_solver_types):
            if solver_type != 'PBD':
                continue
            start, end = self._node_ranges[node_index]
            if end - start != 1:
                continue
            particle = self.particles[start]
            pose_bone = self.arm_obj.pose.bones.get(particle.bone_name)
            parent_index = -1
            if pose_bone is not None and pose_bone.parent is not None:
                parent_index = self.bone_idx_map.get(pose_bone.parent.name, -1)
            reference_index = self.bone_idx_map.get(
                particle.direction_reference_bone, -1
            )
            self._position_projection_nodes[node_index] = {
                'particle_index': start,
                'parent_index': parent_index,
                'reference_index': reference_index,
            }

    def _position_projection_node_is_valid(self, node_index):
        runtime = self._position_projection_nodes.get(node_index)
        if runtime is None:
            return False
        particle_index = runtime['particle_index']
        if not self.active_mask[particle_index]:
            return False
        if runtime['parent_index'] < 0 or not self.active_mask[runtime['parent_index']]:
            return False
        for shape in self._node_col_shapes[node_index]:
            shape_index = self.bone_idx_map.get(shape['bone_name'], -1)
            if shape_index < 0 or not self.active_mask[shape_index]:
                return False
        return True

    def _step_position_projection_node(self, node_index):
        if not self._position_projection_node_is_valid(node_index):
            return

        runtime = self._position_projection_nodes[node_index]
        particle_index = runtime['particle_index']
        particle = self.particles[particle_index]
        node_shapes = self._node_col_shapes[node_index]

        collision.update_collision_transforms_begin(self, node_shapes)
        collision.update_collision_transforms(self, 1.0, node_shapes)

        desired_position = self.cur_bone_ms[particle_index].copy()
        projection_type = particle.pos_projection_type
        if projection_type == 'SHORTEST_PATH':
            for shape in node_shapes:
                desired_position = collision.project_shortest_path_position(
                    shape, desired_position, particle.capsule_radius
                )
        elif projection_type == 'DIRECTIONAL':
            reference_index = runtime['reference_index']
            if reference_index >= 0 and self.active_mask[reference_index]:
                axis_ms = (
                    self.cur_bone_ms[reference_index]
                    - self.cur_bone_ms[particle_index]
                )
            else:
                axis_ls = Vector(self.col_axis_ls[particle_index])
                if axis_ls.length_squared < 1e-8:
                    axis_ls = spaces.re_axis_to_blender_bone(
                        (1.0, 0.0, 0.0), self.arm_obj
                    )
                axis_ms = np.array(
                    self._cur_bone_xform[particle_index].to_quaternion()
                    @ axis_ls.normalized(),
                    dtype=np.float32,
                )
            axis_length = float(np.linalg.norm(axis_ms))
            if axis_length > 1e-8:
                axis_ms = axis_ms / axis_length
                for shape in node_shapes:
                    desired_position = collision.project_directional_capsule_position(
                        shape,
                        desired_position,
                        axis_ms,
                        particle.capsule_height,
                        particle.capsule_radius,
                    )

        self.prev_pos_ms[particle_index] = self.pos_ms[particle_index]
        self.pos_ms[particle_index] = desired_position
        self.vel_ms[particle_index] = 0.0

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

    def _build_authored_constraint_order(self):
        self._node_constraint_order = []
        for node_index, dnode in enumerate(self.state.dangle_nodes):
            link_map, ell_map, cone_map = {}, {}, {}
            link_i = ell_i = cone_i = 0
            start, _end = self._node_ranges[node_index]
            particle_offset = start
            for chain in dnode.chains:
                for particle in chain.particles:
                    for local_i, _cfg in enumerate(particle.link_constraints):
                        link_map[(particle.bone_name, local_i)] = link_i
                        link_i += 1
                    for local_i, _cfg in enumerate(particle.ellipsoid_constraints):
                        ell_map[(particle.bone_name, local_i)] = ell_i
                        ell_i += 1
                    for local_i, _cfg in enumerate(particle.pendulum_constraints):
                        cone_map[(particle.bone_name, local_i)] = cone_i
                        cone_i += 1
                    particle_offset += 1

            order = []
            for entry in getattr(dnode, 'constraint_order', []):
                key = (entry.particle_bone, int(entry.constraint_index))
                index = {
                    'LINK': link_map,
                    'ELLIPSOID': ell_map,
                    'CONE': cone_map,
                }.get(entry.constraint_type, {}).get(key)
                if index is not None:
                    order.append((entry.constraint_type, index))
            if not order:
                order.extend(('LINK', i) for i in range(link_i))
                order.extend(('ELLIPSOID', i) for i in range(ell_i))
                order.extend(('CONE', i) for i in range(cone_i))
            self._node_constraint_order.append(order)

    def _satisfy_constraints_in_authored_order(self, node_index):
        node_saved = self._save_constraint_arrays()
        try:
            for kind, index in self._node_constraint_order[node_index]:
                if kind == 'LINK' and 'link' in node_saved and index < len(node_saved['link'][0]):
                    self.link_idx_a = node_saved['link'][0][index:index + 1]
                    self.link_idx_b = node_saved['link'][1][index:index + 1]
                    self.link_types = node_saved['link'][2][index:index + 1]
                    self.link_lower = node_saved['link'][3][index:index + 1]
                    self.link_upper = node_saved['link'][4][index:index + 1]
                    self.link_rest = node_saved['link'][5][index:index + 1]
                    self.link_look_axes = node_saved['link'][6][index:index + 1]
                    constraints.satisfy_dyng_links_vectorized(self)
                elif kind == 'ELLIPSOID' and 'ell' in node_saved and index < len(node_saved['ell'][0]):
                    self.ell_idx = node_saved['ell'][0][index:index + 1]
                    self.ell_centers = node_saved['ell'][1][index:index + 1]
                    self.ell_radii = node_saved['ell'][2][index:index + 1]
                    self.ell_s1 = node_saved['ell'][3][index:index + 1]
                    self.ell_s2 = node_saved['ell'][4][index:index + 1]
                    self.ell_xform_ls = [node_saved['ell'][5][index]]
                    constraints.satisfy_dyng_ellipsoids_vectorized(self)
                elif kind == 'CONE' and 'cone' in node_saved and index < len(node_saved['cone'][0]):
                    self.cone_idx = node_saved['cone'][0][index:index + 1]
                    self.cone_attach = node_saved['cone'][1][index:index + 1]
                    self.cone_type = node_saved['cone'][2][index:index + 1]
                    self.cone_cos = node_saved['cone'][3][index:index + 1]
                    self.cone_sin_hh = node_saved['cone'][4][index:index + 1]
                    self.cone_cos_hh = node_saved['cone'][5][index:index + 1]
                    self.cone_xform_ls = [node_saved['cone'][6][index]]
                    self.cone_proj_type = node_saved['cone'][7][index:index + 1]
                    self.cone_col_radius = node_saved['cone'][8][index:index + 1]
                    self.cone_col_height = node_saved['cone'][9][index:index + 1]
                    constraints.satisfy_pendulums_vectorized(self)
        finally:
            if 'link' in node_saved:
                (self.link_idx_a, self.link_idx_b, self.link_types, self.link_lower,
                 self.link_upper, self.link_rest, self.link_look_axes) = node_saved['link']
            if 'ell' in node_saved:
                (self.ell_idx, self.ell_centers, self.ell_radii, self.ell_s1,
                 self.ell_s2, self.ell_xform_ls) = node_saved['ell']
            if 'cone' in node_saved:
                (self.cone_idx, self.cone_attach, self.cone_type, self.cone_cos,
                 self.cone_sin_hh, self.cone_cos_hh, self.cone_xform_ls,
                 self.cone_proj_type, self.cone_col_radius,
                 self.cone_col_height) = node_saved['cone']

    def _respond_constraint_collisions_in_authored_order(
        self, node_index, frame_progress, node_shapes
    ):
        if getattr(self, 'cone_idx', None) is None:
            return
        node_saved = self._save_constraint_arrays()
        try:
            for kind, index in self._node_constraint_order[node_index]:
                if kind != 'CONE' or 'cone' not in node_saved:
                    continue
                if index >= len(node_saved['cone'][0]):
                    continue
                self.cone_idx = node_saved['cone'][0][index:index + 1]
                self.cone_attach = node_saved['cone'][1][index:index + 1]
                self.cone_type = node_saved['cone'][2][index:index + 1]
                self.cone_cos = node_saved['cone'][3][index:index + 1]
                self.cone_sin_hh = node_saved['cone'][4][index:index + 1]
                self.cone_cos_hh = node_saved['cone'][5][index:index + 1]
                self.cone_xform_ls = [node_saved['cone'][6][index]]
                self.cone_proj_type = node_saved['cone'][7][index:index + 1]
                self.cone_col_radius = node_saved['cone'][8][index:index + 1]
                self.cone_col_height = node_saved['cone'][9][index:index + 1]
                collision.respond_to_cone_collisions(
                    self, frame_progress, node_shapes
                )
        finally:
            if 'cone' in node_saved:
                (self.cone_idx, self.cone_attach, self.cone_type, self.cone_cos,
                 self.cone_sin_hh, self.cone_cos_hh, self.cone_xform_ls,
                 self.cone_proj_type, self.cone_col_radius,
                 self.cone_col_height) = node_saved['cone']

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
        for i, bone_name in enumerate(self.bone_names):
            self.active_mask[i] = (
                self.arm_obj.pose.bones.get(bone_name) is not None
            )

    @staticmethod
    def _descendant_names(pose_bone):
        names = []
        stack = list(pose_bone.children)
        while stack:
            child = stack.pop()
            names.append(child.name)
            stack.extend(child.children)
        return names

    def _build_feedback_bone_set(self):
        names = {
            particle.bone_name
            for particle in self.particles
            if particle.bone_name
        }

        if getattr(self, 'link_idx_a', None) is not None:
            names.update(
                self.bone_names[int(index)]
                for index in self.link_idx_a
                if 0 <= int(index) < len(self.bone_names)
            )

        for runtime in getattr(self, '_position_projection_nodes', {}).values():
            parent_index = int(runtime.get('parent_index', -1))
            if 0 <= parent_index < len(self.bone_names):
                names.add(self.bone_names[parent_index])
        for runtime in getattr(self, '_spring_nodes', {}).values():
            parent_index = int(runtime.get('parent_index', -1))
            if 0 <= parent_index < len(self.bone_names):
                names.add(self.bone_names[parent_index])
        for runtime in getattr(self, '_pendulum_nodes', {}).values():
            parent_index = int(runtime.get('parent_index', -1))
            if 0 <= parent_index < len(self.bone_names):
                names.add(self.bone_names[parent_index])

        drag_post = getattr(self, 'drag_post', None)
        drag_indices = getattr(drag_post, 'drag_indices', ())
        names.update(
            self.bone_names[int(index)]
            for index in drag_indices
            if 0 <= int(index) < len(self.bone_names)
        )
        for index in drag_indices:
            index = int(index)
            if not 0 <= index < len(self.bone_names):
                continue
            pose_bone = self.arm_obj.pose.bones.get(self.bone_names[index])
            if pose_bone is not None:
                names.update(self._descendant_names(pose_bone))

        # Applying a model-space output to a pose bone rewrites local overrides for
        # every descendant that is restored or corrected afterward. Remove those
        # overrides before the next input sample as well.
        for particle in self.particles:
            pose_bone = self.arm_obj.pose.bones.get(particle.bone_name)
            if pose_bone is not None:
                names.update(self._descendant_names(pose_bone))

        lookat_sources = set()
        if getattr(self, 'link_idx_a', None) is not None:
            lookat_sources.update(int(index) for index in self.link_idx_a)
        for runtime in getattr(self, '_position_projection_nodes', {}).values():
            parent_index = int(runtime.get('parent_index', -1))
            if parent_index >= 0:
                lookat_sources.add(parent_index)
        for runtime in getattr(self, '_spring_nodes', {}).values():
            parent_index = int(runtime.get('parent_index', -1))
            if parent_index >= 0:
                lookat_sources.add(parent_index)
        for runtime in getattr(self, '_pendulum_nodes', {}).values():
            parent_index = int(runtime.get('parent_index', -1))
            if parent_index >= 0:
                lookat_sources.add(parent_index)

        for source_index in lookat_sources:
            if not 0 <= source_index < len(self.bone_names):
                continue
            source_bone = self.arm_obj.pose.bones.get(
                self.bone_names[source_index]
            )
            if source_bone is not None:
                names.update(self._descendant_names(source_bone))

        self._feedback_bone_names = {
            name for name in names
            if self.arm_obj.pose.bones.get(name) is not None
        }
        self._input_bone_basis = {
            name: self.arm_obj.pose.bones[name].matrix_basis.copy()
            for name in self._feedback_bone_names
        }
        self._last_output_bone_basis = {
            name: None for name in self._feedback_bone_names
        }

    def _restore_upstream_pose(self):
        changed = False
        for bone_name in self._feedback_bone_names:
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            if pose_bone is None:
                continue

            displayed_basis = pose_bone.matrix_basis.copy()
            last_output = self._last_output_bone_basis.get(bone_name)
            if not self._matrix_near(displayed_basis, last_output):
                self._input_bone_basis[bone_name] = displayed_basis.copy()

            input_basis = self._input_bone_basis.get(bone_name)
            if input_basis is None:
                continue
            if not self._matrix_near(displayed_basis, input_basis):
                pose_bone.matrix_basis = input_basis.copy()
                changed = True

        if changed:
            self.arm_obj.update_tag(refresh={'OBJECT'})
            bpy.context.view_layer.update()

    def _initialize_node_forces(self):
        for node_index, dnode in enumerate(self.state.dangle_nodes):
            external_ms = spaces.world_direction_to_model(
                self.arm_obj, dnode.external_force_ws
            )
            gravity_ms = spaces.world_direction_to_model(
                self.arm_obj, (0.0, 0.0, -dnode.gravity_ws)
            )
            self._node_prev_ext_force_ms[node_index] = external_ms
            self._node_cur_ext_force_ms[node_index] = external_ms
            self._node_prev_grav_ms[node_index] = gravity_ms
            self._node_cur_grav_ms[node_index] = gravity_ms

    @staticmethod
    def _matrix_near(left, right, epsilon=1e-5):
        if right is None:
            return False
        return all(
            abs(left[row][column] - right[row][column]) <= epsilon
            for row in range(4)
            for column in range(4)
        )

    def _begin_bone_frame(self):
        self._restore_upstream_pose()

        for i, bone_name in enumerate(self.bone_names):
            if not self.active_mask[i]:
                continue
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            if pose_bone is None:
                continue

            input_matrix = pose_bone.matrix.copy()
            self._input_bone_xform[i] = input_matrix.copy()
            self.prev_bone_ms[i] = self.cur_bone_ms[i]
            self.cur_bone_ms[i] = np.array(
                input_matrix.translation, dtype=np.float32
            )
            self._prev_bone_xform[i] = self._cur_bone_xform[i].copy()
            self._cur_bone_xform[i] = input_matrix.copy()

    def restore_upstream_pose(self):
        changed = False
        for bone_name in self._feedback_bone_names:
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            input_basis = self._input_bone_basis.get(bone_name)
            if pose_bone is None or input_basis is None:
                continue
            if not self._matrix_near(pose_bone.matrix_basis, input_basis):
                pose_bone.matrix_basis = input_basis.copy()
                changed = True

        if changed:
            self.arm_obj.update_tag(refresh={'OBJECT'})
            bpy.context.view_layer.update()

        self._last_output_bone_xform = [
            None for _ in self._last_output_bone_xform
        ]
        for bone_name in self._feedback_bone_names:
            self._last_output_bone_basis[bone_name] = None

    def capture_output_pose(self):
        for i, bone_name in enumerate(self.bone_names):
            if not self.active_mask[i]:
                self._last_output_bone_xform[i] = None
                continue
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            self._last_output_bone_xform[i] = (
                pose_bone.matrix.copy() if pose_bone is not None else None
            )

        for bone_name in self._feedback_bone_names:
            pose_bone = self.arm_obj.pose.bones.get(bone_name)
            self._last_output_bone_basis[bone_name] = (
                pose_bone.matrix_basis.copy()
                if pose_bone is not None else None
            )

    def _interpolate_bones(self, frame_progress):
        self.interp_bone_ms[:] = (
            self.prev_bone_ms
            + (self.cur_bone_ms - self.prev_bone_ms) * frame_progress
        )
        if len(self.bone_names) > self.num_particles:
            self.pos_ms[self.num_particles:] = self.interp_bone_ms[self.num_particles:]

        for i in range(len(self.bone_names)):
            if not self.active_mask[i]:
                continue
            previous = self._prev_bone_xform[i]
            current = self._cur_bone_xform[i]
            prev_loc, prev_rot, prev_scale = previous.decompose()
            cur_loc, cur_rot, cur_scale = current.decompose()
            self._interp_bone_xform[i] = Matrix.LocRotScale(
                prev_loc.lerp(cur_loc, frame_progress),
                prev_rot.slerp(cur_rot, frame_progress),
                prev_scale.lerp(cur_scale, frame_progress),
            )

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
            diff_transform = spaces.previous_model_to_current_model(
                self.prev_matrix_world, cur_mw
            )
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

    def _compute_accelerations(self, indices, grav_ms, ext_ms):
        indices = np.asarray(indices, dtype=np.int32)
        ext_accel = ext_ms * self.inv_mass[indices, np.newaxis]
        damp_accel = (
            self.vel_ms[indices]
            * (-self.damping[indices, np.newaxis] * self.inv_mass[indices, np.newaxis])
        )
        damp_norm = np.linalg.norm(damp_accel, axis=1, keepdims=True)
        safe_norm = np.where(damp_norm < 1e-6, 1.0, damp_norm)
        damp_accel = np.where(
            damp_norm > DAMPING_ACCEL_LIMIT,
            (damp_accel / safe_norm) * DAMPING_ACCEL_LIMIT,
            damp_accel,
        )
        pull_accel = (
            (self.interp_bone_ms[indices] - self.pos_ms[indices])
            * (
                self.pull_force[indices, np.newaxis]
                * self.inv_mass[indices, np.newaxis]
            )
        )
        acceleration = grav_ms + damp_accel + ext_accel + pull_accel
        valid = self.is_free[indices] & self.active_mask[indices]
        return np.where(valid[:, np.newaxis], acceleration, 0.0)

    def _update_node_forces(self):
        for node_index, dnode in enumerate(self.state.dangle_nodes):
            self._node_prev_ext_force_ms[node_index] = (
                self._node_cur_ext_force_ms[node_index]
            )
            self._node_cur_ext_force_ms[node_index] = (
                spaces.world_direction_to_model(
                    self.arm_obj, dnode.external_force_ws
                )
            )
            self._node_prev_grav_ms[node_index] = (
                self._node_cur_grav_ms[node_index]
            )
            self._node_cur_grav_ms[node_index] = (
                spaces.world_direction_to_model(
                    self.arm_obj, (0.0, 0.0, -dnode.gravity_ws)
                )
            )

    def _initialize_dyng_node_state(
        self, node_index, indices, node_shapes, reset_positions,
    ):
        if reset_positions:
            self.pos_ms[indices] = self.cur_bone_ms[indices]
            self.prev_pos_ms[indices] = self.cur_bone_ms[indices]

        self.vel_ms[indices] = 0.0
        self.prev_bone_ms[indices] = self.cur_bone_ms[indices]
        for raw_index in indices:
            index = int(raw_index)
            self._prev_bone_xform[index] = self._cur_bone_xform[index].copy()
            self._interp_bone_xform[index] = self._cur_bone_xform[index].copy()

        self._node_prev_ext_force_ms[node_index] = (
            self._node_cur_ext_force_ms[node_index]
        )
        self._node_prev_grav_ms[node_index] = (
            self._node_cur_grav_ms[node_index]
        )

        collision.initialize_collision_transforms(self, node_shapes)

    def _step_node(self, node_index, raw_dt, time_dilation, skip_physics):
        solver_type = self._node_solver_types[node_index]
        if solver_type == 'PBD':
            self._step_position_projection_node(node_index)
            return
        if solver_type == 'SPRING':
            spring.step_spring_node(
                self, node_index, raw_dt, time_dilation, skip_physics
            )
            return
        if solver_type == 'PENDULUM':
            pendulum.step_pendulum_node(
                self, node_index, raw_dt, time_dilation, skip_physics
            )
            return
        if solver_type != 'DYNG':
            return

        start, end = self._node_ranges[node_index]
        if start >= end:
            return
        indices = np.arange(start, end, dtype=np.int32)
        dnode = self.state.dangle_nodes[node_index]
        substep_time = max(0.001, float(dnode.substep_time))
        needs_initialization = bool(
            self._node_simulation_needs_initialization[node_index]
        )
        skip_node_physics = bool(skip_physics or needs_initialization)
        node_shapes = self._node_col_shapes[node_index]

        if skip_node_physics:
            self._initialize_dyng_node_state(
                node_index, indices, node_shapes, reset_positions=True
            )
            self._node_simulation_needs_initialization[node_index] = False

        if time_dilation < MIN_TIME_DILATION:
            if skip_node_physics:
                self._initialize_dyng_node_state(
                    node_index, indices, node_shapes, reset_positions=False
                )
            return

        self._node_time_remainder[node_index] += raw_dt
        raw_steps = int(self._node_time_remainder[node_index] / substep_time)
        self._node_time_remainder[node_index] -= raw_steps * substep_time

        lp_alpha = raw_dt / (LP_FILTER_RC + raw_dt)
        self._node_damped_physics_steps[node_index] += lp_alpha * (
            raw_steps - self._node_damped_physics_steps[node_index]
        )
        physics_steps = int(round(self._node_damped_physics_steps[node_index]))
        physics_steps = max(1, min(physics_steps, int(MAX_PHYSICS_STEPS)))
        dt = min(MAX_TIME_DILATION, time_dilation) * substep_time

        collision.update_collision_transforms_begin(self, node_shapes)
        self._swap_node_constraints(node_index)
        try:
            iterations = max(1, int(dnode.solver_iterations))
            valid = self.is_free[indices] & self.active_mask[indices]

            for step_index in range(physics_steps):
                frame_progress = (step_index + 1.0) / physics_steps
                self._interpolate_bones(frame_progress)
                interpolated_external = (
                    self._node_prev_ext_force_ms[node_index]
                    + (
                        self._node_cur_ext_force_ms[node_index]
                        - self._node_prev_ext_force_ms[node_index]
                    ) * frame_progress
                )
                interpolated_gravity = (
                    self._node_prev_grav_ms[node_index]
                    + (
                        self._node_cur_grav_ms[node_index]
                        - self._node_prev_grav_ms[node_index]
                    ) * frame_progress
                )
                self.prev_pos_ms[indices] = self.pos_ms[indices]

                if skip_node_physics:
                    self.pos_ms[indices] = np.where(
                        valid[:, np.newaxis],
                        self.pos_ms[indices],
                        self.interp_bone_ms[indices],
                    )
                else:
                    acceleration = self._compute_accelerations(
                        indices, interpolated_gravity, interpolated_external
                    )
                    half_velocity = (
                        self.vel_ms[indices] + acceleration * (dt * 0.5)
                    )
                    predicted = self.pos_ms[indices] + half_velocity * dt
                    self.pos_ms[indices] = np.where(
                        valid[:, np.newaxis],
                        predicted,
                        self.interp_bone_ms[indices],
                    )

                for _ in range(iterations):
                    self._satisfy_constraints_in_authored_order(node_index)
                    collision.respond_to_collisions_vectorized(
                        self, frame_progress, indices, node_shapes
                    )
                    self._respond_constraint_collisions_in_authored_order(
                        node_index, frame_progress, node_shapes
                    )

                if not skip_node_physics and dt > 0.0:
                    acceleration = self._compute_accelerations(
                        indices, interpolated_gravity, interpolated_external
                    )
                    corrected_velocity = (
                        (self.pos_ms[indices] - self.prev_pos_ms[indices]) / dt
                        + acceleration * (dt * 0.5)
                    )
                    self.vel_ms[indices] = np.where(
                        valid[:, np.newaxis], corrected_velocity, 0.0
                    )
        finally:
            self._restore_constraints()

        if skip_node_physics:
            self._initialize_dyng_node_state(
                node_index, indices, node_shapes, reset_positions=False
            )

    def step_simulation(
        self, raw_dt, time_dilation=1.0, operation_callback=None
    ):
        if not self.execution_plan:
            return

        self._update_kinematic_state()
        self._restore_upstream_pose()
        self._sample_base_input_pose()
        skip_physics = self._resolve_teleportation()
        self._update_node_forces()

        self._saved_constraints = self._save_constraint_arrays()
        self._saved_link_was_set = getattr(self, 'link_idx_a', None) is not None
        self._saved_ell_was_set = getattr(self, 'ell_idx', None) is not None
        self._saved_cone_was_set = getattr(self, 'cone_idx', None) is not None

        try:
            for operation_type, operation_index in self.execution_plan:
                if operation_type == 'DANGLE':
                    self._sample_node_input(operation_index)
                    self._step_node(
                        operation_index, raw_dt, time_dilation, skip_physics
                    )
                else:
                    self.drag_post.step_runtime(operation_index, raw_dt)

                if operation_callback is not None:
                    operation_callback(
                        self, operation_type, operation_index
                    )
        finally:
            self._restore_constraints()
            self._saved_constraints = {}

        if skip_physics:
            self.vel_ms[:self.num_particles].fill(0.0)

