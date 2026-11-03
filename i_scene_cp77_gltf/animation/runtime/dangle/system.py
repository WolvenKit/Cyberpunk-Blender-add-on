import numpy as np

from ...domain.dangle.constraints import (
    CONSTRAINT_CONE,
    CONSTRAINT_ELLIPSOID,
    CONSTRAINT_LINK,
    compile_rows,
)

TELEPORT_KEEP_SQ = 1.0
TELEPORT_RESET_SQ = 25.0


class DangleSystem:
    def __init__(self, node_ranges, node_solver_types):
        self.node_ranges = list(node_ranges)
        self.node_solver_types = list(node_solver_types)
        self.num_particles = self.node_ranges[-1][1] if self.node_ranges else 0
        self.particle_node_idx = np.zeros(self.num_particles, dtype=np.int32)
        for node_index, (start, end) in enumerate(self.node_ranges):
            self.particle_node_idx[start:end] = node_index
        self.node_slices = [slice(start, end) for start, end in self.node_ranges]
        self.node_indices = [
            np.arange(start, end, dtype=np.int32) for start, end in self.node_ranges
        ]
        self.dyng_particle_indices = (
            np.concatenate(
                [
                    self.node_indices[node_index]
                    for node_index, solver_type in enumerate(self.node_solver_types)
                    if solver_type == "DYNG"
                ]
            )
            if any(solver == "DYNG" for solver in self.node_solver_types)
            else np.empty(0, dtype=np.int32)
        )

        node_count = len(self.node_ranges)
        self.node_prev_ext_force_ms = np.zeros((node_count, 3), dtype=np.float32)
        self.node_cur_ext_force_ms = np.zeros((node_count, 3), dtype=np.float32)
        self.node_prev_grav_ms = np.zeros((node_count, 3), dtype=np.float32)
        self.node_cur_grav_ms = np.zeros((node_count, 3), dtype=np.float32)
        self.node_time_remainder = np.zeros(node_count, dtype=np.float64)
        self.node_damped_physics_steps = np.ones(node_count, dtype=np.float32)
        self.node_simulation_needs_initialization = np.array(
            [solver_type == "DYNG" for solver_type in self.node_solver_types],
            dtype=bool,
        )

        self.link_idx_a = None
        self.ell_idx = None
        self.cone_idx = None
        self.cone_proj_type = None
        self.cone_col_radius = None
        self.cone_col_height = None
        self.node_constraint_order = [()] * node_count

        self.node_col_shapes = [[] for _ in range(node_count)]
        self.col_shapes = []
        self.shape_stacks = {}

        self.position_projection_nodes = {}
        self.spring_nodes = {}
        self.pendulum_nodes = {}
        self.node_workspaces = []
        self.node_tracked_indices = []

    def allocate(self, tracked_count):
        """Per-bone arrays over the tracked index space (particles first, then extra bones)"""
        self.pos_ms = np.zeros((tracked_count, 3), dtype=np.float32)
        self.vel_ms = np.zeros((tracked_count, 3), dtype=np.float32)
        self.prev_pos_ms = np.zeros((tracked_count, 3), dtype=np.float32)

        self.prev_bone_ms = np.zeros((tracked_count, 3), dtype=np.float32)
        self.cur_bone_ms = np.zeros((tracked_count, 3), dtype=np.float32)
        self.interp_bone_ms = np.zeros((tracked_count, 3), dtype=np.float32)

        self.is_free = np.zeros(tracked_count, dtype=bool)
        self.active_mask = np.ones(tracked_count, dtype=bool)
        self.mass = np.ones(tracked_count, dtype=np.float32)
        self.inv_mass = np.ones(tracked_count, dtype=np.float32)
        self.damping = np.zeros(tracked_count, dtype=np.float32)
        self.pull_force = np.zeros(tracked_count, dtype=np.float32)

        self.col_radius = np.zeros(tracked_count, dtype=np.float32)
        self.col_height = np.zeros(tracked_count, dtype=np.float32)
        self.col_axis_ls = np.zeros((tracked_count, 3), dtype=np.float32)
        self.proj_type = np.zeros(tracked_count, dtype=np.int32)

    def set_links(self, idx_a, idx_b, types, lower, upper, rest, look_axes):
        if not idx_a:
            self.link_idx_a = None
            return
        self.link_idx_a = np.array(idx_a, dtype=np.int32)
        self.link_idx_b = np.array(idx_b, dtype=np.int32)
        self.link_types = np.array(types, dtype=np.int32)
        self.link_lower = np.array(lower, dtype=np.float32)
        self.link_upper = np.array(upper, dtype=np.float32)
        self.link_rest = np.array(rest, dtype=np.float32)
        self.link_look_axes = np.array(look_axes, dtype=np.float32)

    def set_ellipsoids(self, idx, radii, scale1, scale2):
        if not idx:
            self.ell_idx = None
            return
        self.ell_idx = np.array(idx, dtype=np.int32)
        self.ell_radii = np.array(radii, dtype=np.float32)
        self.ell_s1 = np.array(scale1, dtype=np.float32)
        self.ell_s2 = np.array(scale2, dtype=np.float32)

    def set_cones(
        self,
        idx,
        attach,
        types,
        cosines,
        half_sines,
        half_cosines,
        projection_types,
        radii,
        heights,
    ):
        if not idx:
            self.cone_idx = None
            self.cone_proj_type = None
            self.cone_col_radius = None
            self.cone_col_height = None
            return
        self.cone_idx = np.array(idx, dtype=np.int32)
        self.cone_attach = np.array(attach, dtype=np.int32)
        self.cone_type = np.array(types, dtype=np.int32)
        self.cone_cos = np.array(cosines, dtype=np.float32)
        self.cone_sin_hh = np.array(half_sines, dtype=np.float32)
        self.cone_cos_hh = np.array(half_cosines, dtype=np.float32)
        self.cone_proj_type = np.array(projection_types, dtype=np.int32)
        self.cone_col_radius = np.array(radii, dtype=np.float32)
        self.cone_col_height = np.array(heights, dtype=np.float32)

    def compile_workspaces(self):
        self.node_workspaces = []
        for node_index, node_slice in enumerate(self.node_slices):
            start, end = self.node_ranges[node_index]
            count = end - start
            configured_free = self.is_free[node_slice] & self.active_mask[node_slice]
            free_local = np.flatnonzero(configured_free).astype(np.int32, copy=False)
            fixed_local = np.flatnonzero(~configured_free).astype(np.int32, copy=False)
            node_indices = self.node_indices[node_index]
            configured_collision = self.active_mask[node_slice]
            collision_shortest = node_indices[
                configured_collision & (self.proj_type[node_slice] == 1)
            ]
            collision_directed = node_indices[
                configured_collision & (self.proj_type[node_slice] == 2)
            ]
            self.node_workspaces.append(
                {
                    "slice": node_slice,
                    "indices": node_indices,
                    "free_local": free_local,
                    "fixed_local": fixed_local,
                    "all_free": free_local.size == count,
                    "collision_shortest_indices": collision_shortest,
                    "collision_directed_indices": collision_directed,
                    "damping_factor": (
                        -self.damping[node_slice] * self.inv_mass[node_slice]
                    ).astype(np.float32, copy=True),
                    "pull_factor": (
                        self.pull_force[node_slice] * self.inv_mass[node_slice]
                    ).astype(np.float32, copy=True),
                    "inverse_mass": self.inv_mass[node_slice].copy(),
                    "acceleration": np.zeros((count, 3), dtype=np.float32),
                    "external_acceleration": np.zeros((count, 3), dtype=np.float32),
                    "damping_acceleration": np.zeros((count, 3), dtype=np.float32),
                    "pull_acceleration": np.zeros((count, 3), dtype=np.float32),
                    "half_velocity": np.zeros((count, 3), dtype=np.float32),
                    "predicted_position": np.zeros((count, 3), dtype=np.float32),
                    "corrected_velocity": np.zeros((count, 3), dtype=np.float32),
                    "damping_norm": np.zeros(count, dtype=np.float32),
                    "damping_safe_norm": np.ones(count, dtype=np.float32),
                    "clamped_damping": np.zeros((count, 3), dtype=np.float32),
                    "damping_limit_mask": np.zeros(count, dtype=bool),
                    "interpolated_external": np.zeros(3, dtype=np.float32),
                    "interpolated_gravity": np.zeros(3, dtype=np.float32),
                }
            )

    def build_constraint_sets(self):
        """Each node's constraint indices by kind, and the per-constraint rows the solver reads"""
        compile_rows(self)
        node_count = len(self.node_ranges)
        self.node_link_sel = [None] * node_count
        self.node_ell_sel = [None] * node_count
        self.node_cone_sel = [None] * node_count

        for node_index, (start, end) in enumerate(self.node_ranges):
            if self.link_idx_a is not None:
                selection = np.flatnonzero(
                    (self.link_idx_a >= start) & (self.link_idx_a < end)
                ).astype(np.int32, copy=False)
                if selection.size:
                    self.node_link_sel[node_index] = selection
            if self.ell_idx is not None:
                selection = np.flatnonzero(
                    (self.ell_idx >= start) & (self.ell_idx < end)
                ).astype(np.int32, copy=False)
                if selection.size:
                    self.node_ell_sel[node_index] = selection
            if self.cone_idx is not None:
                selection = np.flatnonzero(
                    (self.cone_idx >= start) & (self.cone_idx < end)
                ).astype(np.int32, copy=False)
                if selection.size:
                    self.node_cone_sel[node_index] = selection

    def node_selections(self, node_index):
        """The node's compiled constraint indices by kind (None where it has none)"""
        return {
            CONSTRAINT_LINK: self.node_link_sel[node_index],
            CONSTRAINT_ELLIPSOID: self.node_ell_sel[node_index],
            CONSTRAINT_CONE: self.node_cone_sel[node_index],
        }

    def single_particle_node_is_valid(self, nodes, node_index):
        """A PBD, spring or pendulum node runs only with its particle, parent and collision-shape bones present"""
        runtime = nodes.get(node_index)
        if runtime is None:
            return False
        particle_index = int(runtime["particle_index"])
        parent_index = int(runtime["parent_index"])
        if (
            not 0 <= particle_index < self.num_particles
            or not self.active_mask[particle_index]
        ):
            return False
        if parent_index < 0 or not self.active_mask[parent_index]:
            return False
        for shape in self.node_col_shapes[node_index]:
            shape_index = int(shape.get("bone_index", -1))
            if shape_index < 0 or not self.active_mask[shape_index]:
                return False
        return True

    def compile_tracked_indices(self):
        tracked_by_node = []
        tracked_count = len(self.pos_ms)
        for node_index, (start, end) in enumerate(self.node_ranges):
            tracked = set(range(start, end))

            link_selection = self.node_link_sel[node_index]
            if link_selection is not None:
                for raw_constraint_index in link_selection:
                    constraint_index = int(raw_constraint_index)
                    tracked.add(int(self.link_idx_a[constraint_index]))
                    tracked.add(int(self.link_idx_b[constraint_index]))

            ellipsoid_selection = self.node_ell_sel[node_index]
            if ellipsoid_selection is not None:
                for raw_constraint_index in ellipsoid_selection:
                    tracked.add(int(self.ell_idx[int(raw_constraint_index)]))

            cone_selection = self.node_cone_sel[node_index]
            if cone_selection is not None:
                for raw_constraint_index in cone_selection:
                    constraint_index = int(raw_constraint_index)
                    tracked.add(int(self.cone_idx[constraint_index]))
                    tracked.add(int(self.cone_attach[constraint_index]))

            for shape in self.node_col_shapes[node_index]:
                tracked.add(int(shape.get("bone_index", -1)))

            for runtime_map in (
                self.position_projection_nodes,
                self.spring_nodes,
                self.pendulum_nodes,
            ):
                runtime = runtime_map.get(node_index)
                if runtime is None:
                    continue
                tracked.add(int(runtime.get("particle_index", -1)))
                tracked.add(int(runtime.get("parent_index", -1)))
                tracked.add(int(runtime.get("reference_index", -1)))

            indices = np.asarray(
                sorted(
                    index
                    for index in tracked
                    if 0 <= index < tracked_count and self.active_mask[index]
                ),
                dtype=np.int32,
            )
            tracked_by_node.append(indices)
            workspace = self.node_workspaces[node_index]
            workspace["tracked_indices"] = indices
            extra_local = np.flatnonzero(indices >= self.num_particles).astype(
                np.int32, copy=False
            )
            workspace["tracked_extra_local"] = extra_local
            workspace["tracked_extra_indices"] = indices[extra_local]
            workspace["tracked_previous_positions"] = np.empty(
                (len(indices), 3), dtype=np.float32
            )
            workspace["tracked_current_positions"] = np.empty(
                (len(indices), 3), dtype=np.float32
            )
            workspace["tracked_interpolated_positions"] = np.empty(
                (len(indices), 3), dtype=np.float32
            )
        self.node_tracked_indices = tracked_by_node

    def initialize_node_forces(self, node_index, external_ms, gravity_ms):
        self.node_prev_ext_force_ms[node_index] = external_ms
        self.node_cur_ext_force_ms[node_index] = external_ms
        self.node_prev_grav_ms[node_index] = gravity_ms
        self.node_cur_grav_ms[node_index] = gravity_ms

    def push_node_forces(self, node_index, external_ms, gravity_ms):
        self.node_prev_ext_force_ms[node_index] = self.node_cur_ext_force_ms[node_index]
        self.node_cur_ext_force_ms[node_index] = external_ms
        self.node_prev_grav_ms[node_index] = self.node_cur_grav_ms[node_index]
        self.node_cur_grav_ms[node_index] = gravity_ms

    def resolve_teleport(self, distance_squared, model_change):
        """Carry DynG particles across a model-space jump, or return True when physics restarts"""
        dyng_indices = self.dyng_particle_indices
        if distance_squared > TELEPORT_RESET_SQ:
            self.pos_ms[dyng_indices] = self.cur_bone_ms[dyng_indices]
            self.vel_ms[dyng_indices] = 0.0
            return True
        if distance_squared > TELEPORT_KEEP_SQ and dyng_indices.size:
            rotation, translation = model_change()
            self.pos_ms[dyng_indices] = (
                np.dot(self.pos_ms[dyng_indices], rotation.T) + translation
            )
            self.vel_ms[dyng_indices] = np.dot(self.vel_ms[dyng_indices], rotation.T)
        return False
