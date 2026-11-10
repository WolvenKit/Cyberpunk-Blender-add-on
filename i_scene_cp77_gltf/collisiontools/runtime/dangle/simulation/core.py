import numpy as np
from mathutils import Matrix, Vector

from .....animation.domain.dangle.constraints import (
    CONSTRAINT_CONE,
    CONSTRAINT_ELLIPSOID,
    CONSTRAINT_LINK,
)
from .....animation.domain.rig.naming import bone_name_candidates
from .....animation.handlers.dangle import (
    dyng,
)
from .....animation.handlers.dangle import (
    pendulum as pendulum_solver,
)
from .....animation.handlers.dangle import (
    spring as spring_solver,
)
from .....animation.handlers.dangle.drag import DragConfig, DragSolver
from .....animation.model.dangle.frames import DyngParams, PositionProjectionParams
from .....animation.runtime.animgraph.runtime import AnimGraphRuntime
from .....animation.runtime.dangle.system import DangleSystem
from .....bartmoss.matrix import matrices_near
from .....blender.armature_bones import resolve_bone_name, resolve_pose_bone
from .....blender.pose import interpolate_matrix_trs, pose_bone_subtree_names
from ..graph_state import GraphPreviewState
from ..preview_plan import external_force, preview_operations
from . import collision, constraints, pendulum, solvers, spaces, spring
from .animgraph_host import DangleAnimGraphHost


class DyngSimulator:
    """Blender side of the dangle preview"""

    def _register_bone_aliases(self, authored_name, actual_name, index):
        for alias in bone_name_candidates(authored_name):
            self.bone_idx_map.setdefault(alias, index)
        for alias in bone_name_candidates(actual_name):
            self.bone_idx_map.setdefault(alias, index)

    def _append_extra_bone(self, authored_name):
        authored_name = str(authored_name or "")
        if not authored_name:
            return -1
        actual_name = resolve_bone_name(self.arm_obj, authored_name)
        if not actual_name:
            return -1
        existing = self._actual_bone_idx.get(actual_name)
        if existing is not None:
            self._register_bone_aliases(authored_name, actual_name, existing)
            return existing
        index = len(self.bone_names)
        self._actual_bone_idx[actual_name] = index
        self.bone_names.append(actual_name)
        self._register_bone_aliases(authored_name, actual_name, index)
        return index

    def resolve_bone_index(self, bone_name, particle_index=None, node_index=None):
        if node_index is None and particle_index is not None:
            particle_node_idx = self.system.particle_node_idx
            if 0 <= int(particle_index) < len(particle_node_idx):
                node_index = int(particle_node_idx[int(particle_index)])
        if node_index is not None and 0 <= int(node_index) < len(self._node_bone_maps):
            node_map = self._node_bone_maps[int(node_index)]
            for alias in bone_name_candidates(bone_name):
                index = node_map.get(alias)
                if index is not None:
                    return index
        for alias in bone_name_candidates(bone_name):
            index = self.bone_idx_map.get(alias)
            if index is not None:
                return index
        actual_name = resolve_bone_name(self.arm_obj, bone_name)
        return self.bone_idx_map.get(actual_name) if actual_name else None

    def __init__(
        self,
        rig_obj,
        linked_force_runtime=None,
        source_payload=None,
        view_layer_update=None,
        graph_tree=None,
    ):
        self.arm_obj = rig_obj
        # With a graph, the whole graph plays on the rig through the graph's own preview settings.
        self.graph_tree = graph_tree
        self.state = (
            rig_obj.dangle_state
            if graph_tree is None
            else GraphPreviewState(rig_obj.dangle_state, graph_tree)
        )
        self._view_layer_update = view_layer_update
        self.linked_force_runtime = linked_force_runtime
        configuration_errors = spaces.state_configuration_errors(self.state)
        if configuration_errors:
            raise ValueError(configuration_errors[0])

        self.particles = []
        node_ranges = []
        node_solver_types = []

        offset = 0
        for dnode in self.state.dangle_nodes:
            start = offset
            for ch in dnode.chains:
                for p in ch.particles:
                    self.particles.append(p)
                    offset += 1
            node_ranges.append((start, offset))
            node_solver_types.append(dnode.chains[0].solver if dnode.chains else "DYNG")

        self.system = system = DangleSystem(node_ranges, node_solver_types)
        self._node_bones_cached = np.asarray(
            [
                not spaces.dangle_node_missing_bones(
                    self.arm_obj, self.state, node_index
                )
                for node_index in range(len(node_ranges))
            ],
            dtype=bool,
        )
        executable_dangle_indices, _drag_indices = spaces.executable_node_indices(
            self.state
        )
        self._force_node_indices = tuple(
            node_index
            for node_index in sorted(executable_dangle_indices)
            if 0 <= node_index < len(self._node_bones_cached)
            and self._node_bones_cached[node_index]
        )

        self.authored_bone_names = [str(p.bone_name or "") for p in self.particles]
        self.bone_names = []
        self.bone_idx_map = {}
        self._actual_bone_idx = {}

        for particle_index, authored_name in enumerate(self.authored_bone_names):
            actual_name = (
                resolve_bone_name(self.arm_obj, authored_name) or authored_name
            )
            self._actual_bone_idx.setdefault(actual_name, particle_index)
            self.bone_names.append(actual_name)
            self._register_bone_aliases(authored_name, actual_name, particle_index)

        self._node_bone_maps = []
        for node_index, (start, end) in enumerate(system.node_ranges):
            node_map = {}
            for particle_index in range(start, end):
                authored_name = self.authored_bone_names[particle_index]
                actual_name = self.bone_names[particle_index]
                for alias in bone_name_candidates(authored_name):
                    node_map.setdefault(alias, particle_index)
                for alias in bone_name_candidates(actual_name):
                    node_map.setdefault(alias, particle_index)
            self._node_bone_maps.append(node_map)

        # Extra bones the nodes read, tracked after the particles.
        for shape in self.state.collision_shapes:
            self._append_extra_bone(shape.bone_name)
        for dnode in self.state.dangle_nodes:
            for shape in dnode.collision_shapes:
                self._append_extra_bone(shape.bone_name)
        for particle in self.particles:
            self._append_extra_bone(particle.direction_reference_bone)
            for constraints_group in (
                particle.link_constraints,
                particle.ellipsoid_constraints,
                particle.pendulum_constraints,
            ):
                for constraint in constraints_group:
                    self._append_extra_bone(constraint.target_bone)
        for node_index, solver_type in enumerate(system.node_solver_types):
            start, end = system.node_ranges[node_index]
            if solver_type not in {"PBD", "SPRING", "PENDULUM"} or start >= end:
                continue
            pose_bone = resolve_pose_bone(self.arm_obj, self.particles[start].bone_name)
            if pose_bone is not None and pose_bone.parent is not None:
                self._append_extra_bone(pose_bone.parent.name)
        for drag_node in self.state.drag_nodes:
            self._append_extra_bone(drag_node.source_bone_name or drag_node.bone_name)
            self._append_extra_bone(drag_node.bone_name)

        system.allocate(len(self.bone_names))
        self._pose_bones = [
            self.arm_obj.pose.bones.get(name) for name in self.bone_names
        ]

        total_tracked = len(self.bone_names)
        self._prev_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._cur_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._interp_bone_xform = [Matrix.Identity(4) for _ in range(total_tracked)]
        self._previous_parent_xforms = {}
        self._input_bone_basis = {}
        self._last_output_bone_basis = {}
        self._feedback_bone_names = set()
        self._feedback_pose_bones = {}
        self._written_bone_names = set()

        self.prev_matrix_world = rig_obj.matrix_world.copy()

        self._init_state()
        system.compile_workspaces()
        self._initialize_node_forces()
        constraints.compile_constraints(self)
        collision.compile_collision_shapes(self)
        system.build_constraint_sets()
        self._build_authored_constraint_order()
        self._compile_position_projection_nodes()
        spring.compile_spring_nodes(self)
        pendulum.compile_pendulum_nodes(self)
        solvers.compile_output_topology(self)
        system.compile_tracked_indices()

        self.drag_post = DragSolver(self._drag_configs(), self._bone_head_position)
        self.execution_plan = self._build_execution_plan()
        self.animgraph_host = DangleAnimGraphHost(self)
        self.animgraph_runtime = (
            None
            if self.state.preview_mode == "SELECTED"
            else AnimGraphRuntime(
                self.animgraph_host,
                getattr(self, "_execution_source_handles", ()),
                source_payload=source_payload,
            )
        )
        self._initialize_node_input_history()
        self._build_feedback_bone_set()

    def _drag_configs(self):
        configs = []
        for config_index, drag_node in enumerate(self.state.drag_nodes):
            source_index = self.resolve_bone_index(
                drag_node.source_bone_name or drag_node.bone_name
            )
            target_index = self.resolve_bone_index(drag_node.bone_name)
            if source_index is None or target_index is None:
                continue
            configs.append(
                DragConfig(
                    config_index=config_index,
                    source_index=source_index,
                    target_index=target_index,
                    simulation_fps=drag_node.simulation_fps,
                    source_speed_multiplier=drag_node.source_speed_multiplier,
                    has_overshoot=drag_node.has_overshoot,
                    overshoot_detection_min_speed=drag_node.overshoot_detection_min_speed,
                    overshoot_detection_max_speed=drag_node.overshoot_detection_max_speed,
                    overshoot_duration=drag_node.overshoot_duration,
                    use_steps=getattr(drag_node, "use_steps", False),
                    steps_target_speed_multiplier=getattr(
                        drag_node, "steps_target_speed_multiplier", 10000.0
                    ),
                    time_between_steps=getattr(drag_node, "time_between_steps", 0.1),
                    time_in_step=getattr(drag_node, "time_in_step", 0.1),
                )
            )
        return configs

    def _bone_head_position(self, tracked_index):
        pose_bone = self.arm_obj.pose.bones.get(self.bone_names[tracked_index])
        if pose_bone is None:
            return np.zeros(3, dtype=np.float32)
        return np.asarray(pose_bone.matrix.translation, dtype=np.float32)

    def _build_execution_plan(self):
        plan = []
        source_handles = []
        operations = preview_operations(self.state)
        config_to_runtime = getattr(self.drag_post, "config_to_runtime", {})
        for node_type, node_index, source_handle in operations:
            if node_type == "DANGLE":
                if 0 <= node_index < len(self.system.node_ranges):
                    plan.append(("DANGLE", node_index))
                    source_handles.append(source_handle)
            elif node_type == "DRAG":
                runtime_index = config_to_runtime.get(node_index)
                if runtime_index is not None:
                    plan.append(("DRAG", int(runtime_index)))
                    source_handles.append(source_handle)

        self._execution_source_handles = tuple(source_handles)
        return plan

    def _initialize_node_input_history(self):
        self._node_input_current = [
            [self._cur_bone_xform[int(index)].copy() for index in indices]
            for indices in self.system.node_tracked_indices
        ]

    def _sample_base_input_pose(self, model_matrices=None):
        system = self.system
        for raw_index in system.dyng_particle_indices:
            index = int(raw_index)
            pose_bone = self._pose_bones[index]
            if pose_bone is None or not system.active_mask[index]:
                continue
            matrix = None
            if model_matrices is not None and 0 <= index < len(self.bone_names):
                matrix = model_matrices.get(self.bone_names[index])
            matrix = matrix.copy() if matrix is not None else pose_bone.matrix.copy()
            system.cur_bone_ms[index] = matrix.translation
            self._cur_bone_xform[index] = matrix

    def _sample_node_input(self, node_index, model_matrices=None):
        system = self.system
        indices = system.node_tracked_indices[node_index]
        runtime = system.node_workspaces[node_index]
        previous_positions = runtime["tracked_previous_positions"]
        current_positions = runtime["tracked_current_positions"]
        previous = self._node_input_current[node_index]
        current = []

        for local_index, raw_index in enumerate(indices):
            index = int(raw_index)
            pose_bone = self._pose_bones[index]
            current_matrix = None
            if model_matrices is not None and 0 <= index < len(self.bone_names):
                current_matrix = model_matrices.get(self.bone_names[index])
            if current_matrix is None:
                current_matrix = (
                    pose_bone.matrix.copy()
                    if pose_bone is not None
                    else self._cur_bone_xform[index]
                )
            else:
                current_matrix = current_matrix.copy()
            previous_matrix = previous[local_index]
            current.append(current_matrix)
            self._prev_bone_xform[index] = previous_matrix
            self._cur_bone_xform[index] = current_matrix
            previous_positions[local_index] = previous_matrix.translation
            current_positions[local_index] = current_matrix.translation

        system.prev_bone_ms[indices] = previous_positions
        system.cur_bone_ms[indices] = current_positions
        self._node_input_current[node_index] = current

    def _init_state(self):
        system = self.system
        for i, p_cfg in enumerate(self.particles):
            pb = self._pose_bones[i]
            if pb:
                ms_head = np.array(pb.matrix.translation, dtype=np.float32)
                system.pos_ms[i] = ms_head
                system.prev_bone_ms[i] = ms_head
                system.cur_bone_ms[i] = ms_head

            system.is_free[i] = not p_cfg.is_pinned
            system.mass[i] = max(0.001, p_cfg.mass)
            system.inv_mass[i] = 0.0 if p_cfg.is_pinned else (1.0 / system.mass[i])
            system.damping[i] = p_cfg.damping
            system.pull_force[i] = p_cfg.pull_force
            node_solver = system.node_solver_types[int(system.particle_node_idx[i])]
            if node_solver == "SPRING":
                system.col_radius[i] = p_cfg.spring_collision_radius
                system.col_height[i] = 0.0
                axis_bl = spaces.re_axis_to_blender_bone((1.0, 0.0, 0.0), self.arm_obj)
                projection_type = p_cfg.spring_projection_type
            else:
                system.col_radius[i] = p_cfg.capsule_radius
                system.col_height[i] = p_cfg.capsule_height
                axis_bl = spaces.re_axis_to_blender_bone(
                    p_cfg.capsule_axis_ls, self.arm_obj
                )
                projection_type = (
                    p_cfg.pos_projection_type
                    if node_solver == "PBD"
                    else p_cfg.dyng_projection_type
                )
            system.col_axis_ls[i] = np.array(axis_bl, dtype=np.float32)
            system.proj_type[i] = (
                1
                if projection_type == "SHORTEST_PATH"
                else (2 if projection_type in {"DIRECTED", "DIRECTIONAL"} else 0)
            )

        for i, bn in enumerate(self.bone_names):
            pb = self._pose_bones[i]
            if pb is None:
                system.active_mask[i] = False
                continue
            matrix = pb.matrix.copy()
            ms_head = np.array(matrix.translation, dtype=np.float32)
            system.prev_bone_ms[i] = ms_head
            system.cur_bone_ms[i] = ms_head
            system.interp_bone_ms[i] = ms_head
            self._prev_bone_xform[i] = matrix.copy()
            self._cur_bone_xform[i] = matrix.copy()
            self._interp_bone_xform[i] = matrix.copy()
            if i >= system.num_particles:
                system.pos_ms[i] = ms_head

    def single_particle_nodes(self, solver_type):
        """(node index, particle index, pose bone, parent tracked index) of each one-particle node"""
        system = self.system
        for node_index, node_solver in enumerate(system.node_solver_types):
            start, end = system.node_ranges[node_index]
            if node_solver != solver_type or end - start != 1:
                continue
            pose_bone = self.arm_obj.pose.bones.get(self.bone_names[start])
            parent_index = None
            if pose_bone is not None and pose_bone.parent is not None:
                parent_index = self.resolve_bone_index(pose_bone.parent.name)
            yield (
                node_index,
                start,
                pose_bone,
                -1 if parent_index is None else parent_index,
            )

    def _compile_position_projection_nodes(self):
        system = self.system
        system.position_projection_nodes = {}
        for node_index, start, _pose_bone, parent_index in self.single_particle_nodes(
            "PBD"
        ):
            reference_index = self.resolve_bone_index(
                self.particles[start].direction_reference_bone, node_index=node_index
            )
            system.position_projection_nodes[node_index] = {
                "particle_index": start,
                "parent_index": parent_index,
                "reference_index": -1 if reference_index is None else reference_index,
            }

    def _build_authored_constraint_order(self):
        system = self.system
        system.node_constraint_order = []
        for node_index, dnode in enumerate(self.state.dangle_nodes):
            selections = system.node_selections(node_index)
            maps = {
                CONSTRAINT_LINK: {},
                CONSTRAINT_ELLIPSOID: {},
                CONSTRAINT_CONE: {},
            }
            offsets = {
                CONSTRAINT_LINK: 0,
                CONSTRAINT_ELLIPSOID: 0,
                CONSTRAINT_CONE: 0,
            }
            for chain in dnode.chains:
                for particle in chain.particles:
                    groups = (
                        (CONSTRAINT_LINK, particle.link_constraints),
                        (CONSTRAINT_ELLIPSOID, particle.ellipsoid_constraints),
                        (CONSTRAINT_CONE, particle.pendulum_constraints),
                    )
                    for kind, constraints_group in groups:
                        selection = selections[kind]
                        for local_index, _constraint in enumerate(constraints_group):
                            compiled_offset = offsets[kind]
                            if selection is not None and compiled_offset < len(
                                selection
                            ):
                                maps[kind][(particle.bone_name, local_index)] = int(
                                    selection[compiled_offset]
                                )
                            offsets[kind] += 1

            order = []
            for entry in getattr(dnode, "constraint_order", ()):
                kind = {
                    "LINK": CONSTRAINT_LINK,
                    "ELLIPSOID": CONSTRAINT_ELLIPSOID,
                    "CONE": CONSTRAINT_CONE,
                }.get(entry.constraint_type)
                index = maps.get(kind, {}).get(
                    (
                        entry.particle_bone,
                        int(entry.constraint_index),
                    )
                )
                if index is not None:
                    order.append((kind, index))
            if not order:
                for kind in (CONSTRAINT_LINK, CONSTRAINT_ELLIPSOID, CONSTRAINT_CONE):
                    selection = selections[kind]
                    if selection is not None:
                        order.extend((kind, int(index)) for index in selection)
            system.node_constraint_order.append(tuple(order))

    def _build_feedback_bone_set(self):
        system = self.system
        names = {
            self.bone_names[index]
            for index in range(system.num_particles)
            if self.bone_names[index]
        }

        if system.link_idx_a is not None:
            names.update(
                self.bone_names[int(index)]
                for index in system.link_idx_a
                if 0 <= int(index) < len(self.bone_names)
            )

        single_particle_nodes = (
            system.position_projection_nodes,
            system.spring_nodes,
            system.pendulum_nodes,
        )
        for runtime_map in single_particle_nodes:
            for runtime in runtime_map.values():
                parent_index = int(runtime.get("parent_index", -1))
                if 0 <= parent_index < len(self.bone_names):
                    names.add(self.bone_names[parent_index])

        drag_indices = self.drag_post.drag_indices
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
                names.update(pose_bone_subtree_names(pose_bone)[1:])

        # Clear descendant overrides before sampling the next input pose.
        for particle_index in range(system.num_particles):
            pose_bone = self.arm_obj.pose.bones.get(self.bone_names[particle_index])
            if pose_bone is not None:
                names.update(pose_bone_subtree_names(pose_bone)[1:])

        lookat_sources = set()
        if system.link_idx_a is not None:
            lookat_sources.update(int(index) for index in system.link_idx_a)
        for runtime_map in single_particle_nodes:
            for runtime in runtime_map.values():
                parent_index = int(runtime.get("parent_index", -1))
                if parent_index >= 0:
                    lookat_sources.add(parent_index)

        for source_index in lookat_sources:
            if not 0 <= source_index < len(self.bone_names):
                continue
            source_bone = self.arm_obj.pose.bones.get(self.bone_names[source_index])
            if source_bone is not None:
                names.update(pose_bone_subtree_names(source_bone)[1:])

        runtime = getattr(self, "animgraph_runtime", None)
        names.update(getattr(runtime, "required_bones", ()) or ())
        self._feedback_bone_names = {
            name for name in names if self.arm_obj.pose.bones.get(name) is not None
        }
        self._feedback_pose_bones = {
            name: self.arm_obj.pose.bones[name] for name in self._feedback_bone_names
        }
        self._input_bone_basis = {
            name: pose_bone.matrix_basis.copy()
            for name, pose_bone in self._feedback_pose_bones.items()
        }
        self._last_output_bone_basis = {
            name: None for name in self._feedback_bone_names
        }

    def _capture_upstream_pose_feedback(self):
        changed = False
        written = set(self._written_bone_names)
        for bone_name, pose_bone in self._feedback_pose_bones.items():
            displayed_basis = pose_bone.matrix_basis.copy()
            if bone_name not in written:
                if self._last_output_bone_basis.get(bone_name) is None:
                    previous_input = self._input_bone_basis.get(bone_name)
                    if not matrices_near(displayed_basis, previous_input):
                        changed = True
                    self._input_bone_basis[bone_name] = displayed_basis.copy()
                continue

            last_output = self._last_output_bone_basis.get(bone_name)
            if not matrices_near(displayed_basis, last_output):
                changed = True
                self._input_bone_basis[bone_name] = displayed_basis.copy()
        return changed

    def prepare_frame_change_upstream(self):
        if not getattr(self, "_timeline_playing", False):
            self._capture_upstream_pose_feedback()
            runtime = getattr(self, "animgraph_runtime", None)
            if runtime is not None and runtime.structured:
                runtime.capture_upstream_tracks()

        changed = False
        for bone_name, pose_bone in self._feedback_pose_bones.items():
            input_basis = self._input_bone_basis.get(bone_name)
            if input_basis is None:
                continue
            if not matrices_near(pose_bone.matrix_basis, input_basis):
                pose_bone.matrix_basis = input_basis.copy()
                changed = True

        runtime = getattr(self, "animgraph_runtime", None)
        if runtime is not None and runtime.structured:
            changed = runtime.restore_frame_change_upstream_tracks() or changed

        if changed:
            self.arm_obj.update_tag(refresh={"OBJECT"})
        return changed

    def capture_frame_change_upstream(self, depsgraph=None):
        source_armature = self.arm_obj
        source_pose_bones = self._feedback_pose_bones
        used_evaluated = False
        if depsgraph is not None:
            evaluated_get = getattr(self.arm_obj, "evaluated_get", None)
            if callable(evaluated_get):
                try:
                    evaluated_armature = evaluated_get(depsgraph)
                    evaluated_pose = getattr(evaluated_armature, "pose", None)
                    evaluated_bones = getattr(evaluated_pose, "bones", None)
                    if evaluated_bones is not None:
                        source_armature = evaluated_armature
                        source_pose_bones = evaluated_bones
                        used_evaluated = True
                except (ReferenceError, RuntimeError):
                    pass

        captured_bones = 0
        for bone_name, pose_bone in self._feedback_pose_bones.items():
            source_bone = (
                source_pose_bones.get(bone_name)
                if hasattr(source_pose_bones, "get")
                else None
            )
            if source_bone is None:
                source_bone = pose_bone
            self._input_bone_basis[bone_name] = source_bone.matrix_basis.copy()
            captured_bones += 1

        self._frame_change_capture_events = (
            getattr(self, "_frame_change_capture_events", 0) + 1
        )
        if used_evaluated:
            self._frame_change_evaluated_events = (
                getattr(self, "_frame_change_evaluated_events", 0) + 1
            )
        self._frame_change_input_bones = (
            getattr(self, "_frame_change_input_bones", 0) + captured_bones
        )

        runtime = getattr(self, "animgraph_runtime", None)
        if runtime is not None and runtime.structured:
            runtime.capture_frame_change_upstream_tracks(
                source_armature=source_armature
            )

        restored = False
        for bone_name, output_basis in self._last_output_bone_basis.items():
            if output_basis is None:
                continue
            pose_bone = self._feedback_pose_bones.get(bone_name)
            if pose_bone is None:
                continue
            if not matrices_near(pose_bone.matrix_basis, output_basis):
                pose_bone.matrix_basis = output_basis.copy()
                restored = True

        if runtime is not None and runtime.structured:
            restored = runtime.reapply_last_output_tracks() or restored

        if restored:
            self.arm_obj.update_tag(refresh={"OBJECT"})
        return restored

    def _restore_upstream_pose(self):
        self._capture_upstream_pose_feedback()
        changed = False
        written = tuple(self._written_bone_names)
        for bone_name in written:
            pose_bone = self._feedback_pose_bones.get(bone_name)
            if pose_bone is None:
                continue

            displayed_basis = pose_bone.matrix_basis.copy()

            input_basis = self._input_bone_basis.get(bone_name)
            if input_basis is None:
                continue
            if not matrices_near(displayed_basis, input_basis):
                pose_bone.matrix_basis = input_basis.copy()
                changed = True

        if changed:
            self.arm_obj.update_tag(refresh={"OBJECT"})
            callback = getattr(self, "_view_layer_update", None)
            if callable(callback):
                callback()
        self._written_bone_names.clear()

    def prepare_output_bones(self, bone_names):
        for bone_name in bone_names:
            if bone_name in self._written_bone_names:
                continue
            pose_bone = self._feedback_pose_bones.get(bone_name)
            if pose_bone is not None:
                self._input_bone_basis[bone_name] = pose_bone.matrix_basis.copy()

    def mark_output_bones(self, bone_names):
        self._written_bone_names.update(
            bone_name
            for bone_name in bone_names
            if bone_name in self._feedback_pose_bones
        )

    def _node_forces_ms(self):
        """Each force node's (external force, gravity) in model space"""
        world_to_model = self.arm_obj.matrix_world.to_quaternion().inverted()
        for node_index in self._force_node_indices:
            dnode = self.state.dangle_nodes[node_index]
            yield (
                node_index,
                world_to_model
                @ Vector(external_force(self.state, dnode, self.linked_force_runtime)),
                world_to_model @ Vector((0.0, 0.0, -dnode.gravity_ws)),
            )

    def _initialize_node_forces(self):
        for node_index, external_ms, gravity_ms in self._node_forces_ms():
            self.system.initialize_node_forces(node_index, external_ms, gravity_ms)

    def restore_upstream_pose(self, *, discard_partial_output=False):
        if discard_partial_output:
            # Failed-step writes are output, not subsequent animation or user input.
            self.capture_output_pose()
        written = tuple(self._written_bone_names)
        self._restore_upstream_pose()

        runtime = getattr(self, "animgraph_runtime", None)
        if runtime is not None:
            runtime.restore_upstream_tracks_final()

        for bone_name in written:
            self._last_output_bone_basis[bone_name] = None

    def capture_output_pose(self):
        for bone_name in self._written_bone_names:
            pose_bone = self._feedback_pose_bones.get(bone_name)
            self._last_output_bone_basis[bone_name] = (
                pose_bone.matrix_basis.copy() if pose_bone is not None else None
            )
        runtime = getattr(self, "animgraph_runtime", None)
        if runtime is not None:
            runtime.capture_output_tracks()

    def _resolve_teleportation(self):
        cur_mw = self.arm_obj.matrix_world
        diff_sq = (
            cur_mw.translation - self.prev_matrix_world.translation
        ).length_squared

        def model_change():
            diff_transform = spaces.previous_model_to_current_model(
                self.prev_matrix_world, cur_mw
            )
            return (
                np.array(diff_transform.to_quaternion().to_matrix(), dtype=np.float32),
                np.array(diff_transform.translation, dtype=np.float32),
            )

        skip_physics = self.system.resolve_teleport(diff_sq, model_change)
        self.prev_matrix_world = cur_mw.copy()
        return skip_physics

    def _update_node_forces(self):
        for node_index, external_ms, gravity_ms in self._node_forces_ms():
            self.system.push_node_forces(node_index, external_ms, gravity_ms)

    def _step_node(self, node_index, raw_dt, time_dilation, skip_physics):
        if (
            not 0 <= int(node_index) < len(self._node_bones_cached)
            or not self._node_bones_cached[int(node_index)]
        ):
            return
        system = self.system
        solver_type = system.node_solver_types[node_index]
        start, _end = system.node_ranges[node_index]
        if solver_type == "PBD":
            if node_index in system.position_projection_nodes:
                particle = self.particles[start]
                dyng.step_position_projection_node(
                    system,
                    node_index,
                    PositionProjectionParams(
                        particle.pos_projection_type,
                        particle.capsule_radius,
                        particle.capsule_height,
                    ),
                    self,
                )
            return
        if solver_type == "SPRING":
            if node_index in system.spring_nodes and spring_solver.step_spring_node(
                system,
                node_index,
                raw_dt,
                time_dilation,
                False,
                spring.spring_params(self.particles[start]),
                self,
            ):
                self._finish_parent_step(node_index, system.spring_nodes)
            return
        if solver_type == "PENDULUM":
            if (
                node_index in system.pendulum_nodes
                and pendulum_solver.step_pendulum_node(
                    system,
                    node_index,
                    raw_dt,
                    time_dilation,
                    False,
                    pendulum.pendulum_params(self.particles[start]),
                    self,
                )
            ):
                self._finish_parent_step(node_index, system.pendulum_nodes)
            return
        if solver_type != "DYNG":
            return
        dnode = self.state.dangle_nodes[node_index]
        dyng.step_dyng_node(
            system,
            node_index,
            raw_dt,
            time_dilation,
            skip_physics,
            DyngParams(dnode.substep_time, dnode.solver_iterations),
            self,
        )

    def _finish_parent_step(self, node_index, nodes):
        parent_index = int(nodes[node_index]["parent_index"])
        self._previous_parent_xforms[node_index] = self._cur_bone_xform[
            parent_index
        ].copy()

    def begin_shapes(self, shapes):
        collision.begin_shape_transforms(self, shapes)

    def initialize_shapes(self, shapes):
        collision.initialize_shape_transforms(self, shapes)

    def pose_shapes(self, shapes, progress):
        collision.pose_shapes(shapes, progress)

    def dyng_frame(self, node_index, progress):
        for raw_index in self.system.node_workspaces[node_index]["tracked_indices"]:
            index = int(raw_index)
            self._interp_bone_xform[index] = interpolate_matrix_trs(
                self._prev_bone_xform[index],
                self._cur_bone_xform[index],
                progress,
            )
        return constraints.dyng_frame(self, node_index)

    def reset_dyng_interpolation(self, node_index):
        start, end = self.system.node_ranges[node_index]
        for index in range(start, end):
            self._prev_bone_xform[index] = self._cur_bone_xform[index].copy()
            self._interp_bone_xform[index] = self._cur_bone_xform[index].copy()

    def current_bone_axis(self, particle_index):
        return constraints.capsule_axis_ms(
            self, self._cur_bone_xform[particle_index], particle_index
        )

    def spring_frame(self, node_index, progress):
        return spring.spring_frame(self, node_index, progress)

    def spring_rest_position(self, node_index):
        return spring.spring_rest_position(self, node_index)

    def pendulum_frame(self, node_index, progress):
        return pendulum.pendulum_frame(self, node_index, progress)

    def pendulum_rest_frame(self, node_index):
        return pendulum.pendulum_rest_frame(self, node_index)

    def step_simulation(self, raw_dt, time_dilation=1.0, operation_callback=None):
        runtime = getattr(self, "animgraph_runtime", None)
        if not self.execution_plan and not (runtime is not None and runtime.structured):
            return

        input_frame = None
        upstream_changed = False
        if runtime is not None and runtime.structured:
            if not getattr(self, "_timeline_playing", False):
                upstream_changed = bool(self._capture_upstream_pose_feedback())
                upstream_changed = (
                    bool(runtime.capture_upstream_tracks()) or upstream_changed
                )
            input_frame = runtime.capture_graph_input()
            dyng_names = tuple(
                self.bone_names[int(index)]
                for index in self.system.dyng_particle_indices
                if (
                    0 <= int(index) < len(self.bone_names)
                    and int(index) < len(self._pose_bones)
                    and self._pose_bones[int(index)] is not None
                )
            )
            model_matrices = self.animgraph_host.frame_model_matrices(
                input_frame, dyng_names
            )
            self._sample_base_input_pose(model_matrices=model_matrices)
        else:
            self._restore_upstream_pose()
            if runtime is not None:
                runtime.restore_upstream_tracks()
            self._sample_base_input_pose()
        skip_physics = self._resolve_teleportation()
        self._update_node_forces()

        if runtime is not None and runtime.structured:
            runtime.step_graph(
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback=operation_callback,
                input_frame=input_frame,
                sync_final=False,
            )
        else:
            for plan_index, (operation_type, operation_index) in enumerate(
                self.execution_plan
            ):
                if runtime is not None:
                    runtime.evaluate_before_operation(plan_index)
                if operation_type == "DANGLE":
                    self._sample_node_input(operation_index)
                    self._step_node(
                        operation_index, raw_dt, time_dilation, skip_physics
                    )
                else:
                    self.drag_post.step_runtime(operation_index, raw_dt)

                if operation_callback is not None:
                    operation_callback(self, operation_type, operation_index)

        if skip_physics:
            self.system.vel_ms[self.system.dyng_particle_indices] = 0.0
