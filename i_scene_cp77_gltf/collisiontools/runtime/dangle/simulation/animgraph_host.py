from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import bpy
from mathutils import Matrix, Quaternion, Vector

from .....animation.domain.animgraph import animation_scope
from .....animation.domain.animgraph.variable import (
    resolve_float_variable,
    rig_float_value,
)
from .....animation.domain.clip.additive import (
    ADDITIVE_STORAGE_REFERENCE_APPLIED,
    normalize_additive_storage,
)
from .....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from .....animation.model.animgraph.frames import BranchFrame, TrackSnapshot
from .....animation.model.animgraph.handles import normalized_source_handle
from .....animation.runtime.animgraph.host import (
    LookAtControls,
    PreviewSettings,
    SourceClip,
)
from .....animation.services.rig.repository import RigRepository
from .....assetio.documents import DocumentSession
from .....assetio.paths import local_path_key
from .....bartmoss.matrix import matrices_near
from .....blender.action_metadata import armature_track_names
from .....blender.animgraph import chain as pose_chain
from .....blender.animgraph import variables
from .....blender.animgraph.pose_nodes.direct_conn import float_values
from .....blender.armature_bones import (
    resolve_pose_bone,
    rig_space_contract,
    with_ancestor_bones,
)
from .....blender.facial.graph import bind_graph, claim_session
from .....blender.keyframes import get_action_fcurves
from .....blender.pose import (
    capture_reference_pose_ls,
    capture_tracks,
    matrix_from_qs,
    model_matrix_to_basis,
    qs_from_matrix,
    restore_tracks,
)
from .....blender.rig_metadata import (
    load_rig_part_masks,
    load_rig_part_rotation_ms,
    source_rig_part_bindings,
    source_rig_paths,
)
from .....blender.tracks import reference_track_values
from .....gltf.provenance import SOURCE_PATH_KEY
from . import solvers, spaces


@dataclass(frozen=True)
class DangleStep:
    """One dangle node's simulated model matrices and the bones it writes"""

    matrices: Mapping[str, Any]
    apply_names: Any
    base_matrices: Mapping[str, Any]


def _node_handle(node: Any) -> str:
    return normalized_source_handle(getattr(node, "red_handle_id", ""))


class DangleAnimGraphHost:
    """An armature, its bound AnimGraph node tree and the dangle simulator stepping it"""

    def __init__(self, simulator: Any):
        self.simulator = simulator
        self.armature = simulator.arm_obj
        self.root_tree = self._root_tree()
        self.has_graph = self.root_tree is not None
        self.graph_name = getattr(self.root_tree, "name", "<none>")
        self._frame_pose_bones: dict[str, Any] = {}
        self._reference_matrices: dict[str, Any] = {}
        self._bind_matrices: dict[str, Any] = {}
        self._bind_inverse_matrices: dict[str, Any] = {}
        self._curve_cache: dict[tuple[int, int], tuple[Any, ...]] = {}
        self._float_by_handle = None

    @property
    def name(self) -> str:
        return getattr(self.armature, "name", "<unnamed>")

    @property
    def settings(self) -> PreviewSettings:
        state = self.simulator.state
        return PreviewSettings(
            graph_path=str(getattr(state, "animgraph_source_path", "") or ""),
            visual_tags=str(state.preview_visual_tags or ""),
            component_tags=str(getattr(state, "preview_component_tags", "") or ""),
            skeletal_lod=int(getattr(state, "preview_skeletal_lod", 0) or 0),
            performance_mode=bool(getattr(state, "preview_performance_mode", False)),
        )

    def _root_tree(self):
        name = str(getattr(self.simulator.state, "animgraph_tree_name", "") or "")
        tree = bpy.data.node_groups.get(name) if name else None
        if tree is None or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
            return None
        return variables.root_tree_for(tree) or tree

    def nodes_by_handle(self) -> dict[str, Any]:
        if self.root_tree is None:
            return {}
        result = {}
        for tree in variables.related_trees(self.root_tree):
            for node in getattr(tree, "nodes", ()) or ():
                handle = _node_handle(node)
                if handle:
                    result.setdefault(handle, node)
        return result

    def graph_variables(self):
        return getattr(self.root_tree, "variables", ()) or ()

    def float_variable_value(
        self, name: str, rig_inputs: Mapping[str, float] | None
    ) -> float:
        rig_values = self.armature if rig_inputs is None else rig_inputs
        return resolve_float_variable(
            name, getattr(self.root_tree, "variables", ()), rig_values, undeclared=0.0
        )

    def rig_float_value(self, name: str):
        return rig_float_value(self.armature, name)

    def available_animation_names(
        self, source_payload: Mapping[str, Any]
    ) -> frozenset[str]:
        return animation_scope.available_animation_names(
            source_payload,
            getattr(getattr(bpy, "data", None), "actions", None),
            source_path_property=SOURCE_PATH_KEY,
        )

    def bind_values(self, float_by_handle) -> None:
        """The playing graph's float values by node handle"""
        self._float_by_handle = float_by_handle

    def prepare_node_operation(self, node):
        with float_values(self._float_by_handle):
            return pose_chain.prepare_node_operation(
                self.root_tree, node, self.armature, validate=True
            )

    def prepare_upstream_chain(self, boundary):
        with float_values(self._float_by_handle):
            return pose_chain.prepare_upstream_chain(
                self.root_tree, boundary, self.armature, validate=True
            )

    def refresh_chain(self, plan):
        with float_values(self._float_by_handle):
            return pose_chain.refresh_dynamic_chain_plan(plan, self.root_tree)

    def evaluate_chain(self, plan):
        return pose_chain.evaluate_chain_state(plan, self.armature)

    def apply_chain(self, plan, execution) -> tuple[int, int]:
        return pose_chain.apply_chain_execution(self.armature, plan, execution)

    def resolve_bone(self, name: str) -> str | None:
        pose_bone = resolve_pose_bone(self.armature, name)
        return str(pose_bone.name) if pose_bone is not None else None

    def bone_parent(self, name: str) -> str | None:
        bone = self.armature.pose.bones.get(name)
        parent = bone.parent if bone is not None else None
        return str(parent.name) if parent is not None else None

    def bone_descendants(self, name: str) -> tuple[str, ...]:
        bone = self.armature.pose.bones.get(name)
        descendants = list(bone.children) if bone is not None else []
        names = []
        while descendants:
            child = descendants.pop()
            names.append(str(child.name))
            descendants.extend(child.children)
        return tuple(names)

    def with_ancestor_bones(self, names: Iterable[str]) -> set[str]:
        return with_ancestor_bones(self.armature, names)

    def rig_tags(self) -> tuple[Any, ...]:
        arm_data = getattr(self.armature, "data", None)
        return tuple(
            arm_data.get("cp77_rig_tags", ()) if hasattr(arm_data, "get") else ()
        )

    def rig_space_contract(self):
        return rig_space_contract(self.armature)

    def rig_part_masks(self):
        return load_rig_part_masks(self.armature)

    def rig_part_rotation_ms(self):
        return load_rig_part_rotation_ms(self.armature)

    def source_rig_paths(self) -> tuple[str, ...]:
        return tuple(source_rig_paths(self.armature))

    def source_rig_part_bindings(self) -> tuple[Mapping[str, str], ...]:
        # The part picked for the graph binds it, whatever its file is called now; else the armature's own records
        # (an entity's component bindings) do.
        part = str(getattr(self.root_tree, "red_rig_part", "") or "")
        if part and local_path_key(part) in {
            local_path_key(path) for path in self.source_rig_paths()
        }:
            return ({"graph": self.settings.graph_path, "path": part},)
        return tuple(source_rig_part_bindings(self.armature))

    def load_rig_datas(self, paths: Iterable[str]) -> tuple[Any, ...]:
        with DocumentSession() as documents:
            repository = RigRepository(documents)
            return tuple(repository.load(path, required=True) for path in paths)

    def track_names(self) -> tuple[str, ...]:
        return tuple(armature_track_names(self.armature))

    def has_track(self, name: str) -> bool:
        return name in self.armature

    def track_snapshot(self, name: str, source: Any = None) -> TrackSnapshot:
        owner = source if source is not None else self.armature
        return TrackSnapshot(name in owner, float(owner.get(name, 0.0) or 0.0))

    def capture_tracks(self, names: Iterable[str]) -> dict[str, TrackSnapshot]:
        return capture_tracks(self.armature, names)

    def restore_tracks(self, snapshots: Mapping[str, TrackSnapshot]) -> None:
        restore_tracks(self.armature, snapshots)

    def reference_track_values(self, names: Iterable[str]):
        return reference_track_values(self.armature, names)

    def bind_facial_graph(self):
        return bind_graph(self.armature)

    def claim_facial_session(self, session, owner) -> None:
        claim_session(session, owner)

    def clip(self, name: str) -> SourceClip | None:
        action = bpy.data.actions.get(name)
        if action is None:
            return None
        return SourceClip(
            str(getattr(action, "name", "") or ""),
            float(action.frame_range[0]),
            float(action.frame_range[1]),
            str(action.get("animationType", "Normal") or "Normal"),
            int(action.as_pointer()) if hasattr(action, "as_pointer") else id(action),
            action,
        )

    def clip_events(self, clip: SourceClip):
        action = clip.handle
        return action.get("animEvents") if hasattr(action, "get") else None

    def _clip_curves(self, clip: SourceClip):
        armature_key = (
            int(self.armature.as_pointer())
            if hasattr(self.armature, "as_pointer")
            else id(self.armature)
        )
        key = (clip.key, armature_key)
        curves = self._curve_cache.get(key)
        if curves is None:
            curves = tuple(get_action_fcurves(clip.handle, self.armature) or ())
            self._curve_cache[key] = curves
        return curves

    def sample_clip(self, clip: SourceClip, frame: float):
        bones: dict[str, dict[str, list[float]]] = {}
        tracks: dict[str, float] = {}
        for curve in self._clip_curves(clip):
            path = str(getattr(curve, "data_path", "") or "")
            index = int(getattr(curve, "array_index", 0) or 0)
            value = float(curve.evaluate(float(frame)))
            prefix = 'pose.bones["'
            if path.startswith(prefix):
                end = path.find('"]', len(prefix))
                if end < 0:
                    continue
                name = path[len(prefix) : end]
                prop = path[end + 2 :].lstrip(".")
                state = bones.setdefault(
                    name,
                    {
                        "location": [0.0, 0.0, 0.0],
                        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                )
                values = state.get(prop)
                if values is not None and 0 <= index < len(values):
                    values[index] = value
                continue
            if path.startswith('["') and path.endswith('"]'):
                tracks[path[2:-2]] = value
        return bones, tracks

    def clip_basis(self, components: Mapping[str, Any], red_pose_bridge: bool):
        basis = (
            Matrix.Translation(Vector(components["location"]))
            @ Quaternion(components["rotation_quaternion"]).to_matrix().to_4x4()
            @ Matrix.Diagonal((*components["scale"], 1.0))
        )
        if red_pose_bridge:
            basis = spaces.blender_bone_additive_transform_to_red(basis, self.armature)
        return qs_from_matrix(basis)

    def additive_storage_mode(self) -> str:
        scene = getattr(bpy.context, "scene", None)
        settings = (
            getattr(scene, "cp77_additive_preview", None) if scene is not None else None
        )
        return normalize_additive_storage(
            getattr(settings, "storage_mode", ADDITIVE_STORAGE_REFERENCE_APPLIED)
            if settings is not None
            else ADDITIVE_STORAGE_REFERENCE_APPLIED
        )

    def frame_bone_names(self) -> tuple[str, ...]:
        return tuple(getattr(self.simulator, "_feedback_pose_bones", {}))

    def reference_pose_ls(self, names: Iterable[str]):
        return capture_reference_pose_ls(self.armature, names)

    def bind_frame_pose(
        self, names, reference_pose, bind_pose, *, count_distinct: bool
    ) -> int:
        """Snapshot the frame's pose bones with their bind and reference matrices"""
        self._frame_pose_bones = dict(
            getattr(self.simulator, "_feedback_pose_bones", {})
        )
        self._reference_matrices = {
            name: matrix_from_qs(reference_pose[name])
            for name in names
            if name in reference_pose
        }
        self._bind_matrices = {
            name: matrix_from_qs(bind_pose[name]) for name in names if name in bind_pose
        }
        self._bind_inverse_matrices = {
            name: matrix.inverted_safe() for name, matrix in self._bind_matrices.items()
        }
        if not count_distinct:
            return 0
        return sum(
            1
            for name in names
            if name in self._reference_matrices
            and name in self._bind_matrices
            and any(
                abs(
                    self._reference_matrices[name][row][column]
                    - self._bind_matrices[name][row][column]
                )
                > 1e-6
                for row in range(4)
                for column in range(4)
            )
        )

    def physical_parent_map(self) -> dict[str, str]:
        frame_bones = getattr(self.simulator, "_feedback_pose_bones", {})
        names = set(frame_bones)
        result = {}
        for name, pose_bone in frame_bones.items():
            parent = getattr(pose_bone, "parent", None)
            parent_name = str(getattr(parent, "name", "") or "")
            result[name] = parent_name if parent_name in names else ""
        return result

    def capture_pose(
        self, names, *, use_input_basis: bool, red_pose_bridge: bool
    ) -> dict[str, Any]:
        """Engine-local transforms of names"""
        cached_basis = (
            getattr(self.simulator, "_input_bone_basis", {}) if use_input_basis else {}
        )
        source = (
            ((name, self._frame_pose_bones.get(name)) for name in names)
            if names
            else self._frame_pose_bones.items()
        )
        pose = {}
        for name, pose_bone in source:
            if pose_bone is None:
                continue
            bind_matrix = self._bind_matrices.get(name)
            if bind_matrix is None:
                raise KeyError(f"Bind pose is missing bone {name!r}")
            basis = cached_basis.get(name)
            if basis is None:
                basis = pose_bone.matrix_basis
            if red_pose_bridge:
                basis = spaces.blender_bone_additive_transform_to_red(
                    basis, self.armature
                )
            pose[name] = qs_from_matrix(bind_matrix @ basis)
        return pose

    def _basis(self, transform, name: str, red_pose_bridge: bool):
        basis = self._bind_inverse_matrices[name] @ matrix_from_qs(transform)
        if red_pose_bridge:
            basis = spaces.red_additive_transform_to_blender_bone(basis, self.armature)
        return basis

    def write_pose(
        self, pose: Mapping[str, Any], names: Iterable[str], red_pose_bridge: bool
    ) -> int:
        writes = 0
        for name in names:
            pose_bone = self._frame_pose_bones.get(name)
            if pose_bone is None:
                continue
            transform = pose.get(name)
            if transform is None or name not in self._bind_inverse_matrices:
                continue
            basis = self._basis(transform, name, red_pose_bridge)
            current_basis = pose_bone.matrix_basis
            if all(
                current_basis[row][column] == basis[row][column]
                for row in range(4)
                for column in range(4)
            ):
                continue
            pose_bone.matrix_basis = basis
            writes += 1
        return writes

    def basis_translations(
        self, pose: Mapping[str, Any], names: Iterable[str], red_pose_bridge: bool
    ) -> list:
        """(bone, pose-bone basis translation) of the named transforms, for tracing"""
        rows = []
        for name in names:
            transform = pose.get(name)
            if transform is None or name not in self._bind_inverse_matrices:
                continue
            basis = self._basis(transform, name, red_pose_bridge)
            rows.append(
                (
                    name,
                    tuple(round(float(basis[index][3]), 6) for index in range(3)),
                )
            )
        return rows

    def output_basis_changed(self, name: str) -> bool:
        """Whether a bone's basis moved since the simulator last wrote it"""
        pose_bone = self._frame_pose_bones.get(name)
        prior_basis = getattr(self.simulator, "_last_output_bone_basis", {}).get(name)
        return (
            pose_bone is not None
            and prior_basis is not None
            and not matrices_near(pose_bone.matrix_basis, prior_basis)
        )

    def tag_update(self) -> None:
        self.armature.update_tag(refresh={"OBJECT"})

    def sync_pose(self) -> None:
        self.armature.update_tag(refresh={"OBJECT"})
        callback = getattr(self.simulator, "_view_layer_update", None)
        if callable(callback):
            callback()

    def prepare_output_bones(self, names) -> None:
        self.simulator.prepare_output_bones(names)

    def mark_output_bones(self, names) -> None:
        self.simulator.mark_output_bones(names)

    @staticmethod
    def frame_model_matrices(
        frame: BranchFrame, names: Iterable[str]
    ) -> dict[str, Any]:
        cache: dict[str, Any] = {}
        visiting: set[str] = set()

        def resolve(name: str):
            if name in cache:
                return cache[name]
            chain = []
            current = name
            while current and current not in cache:
                if current not in frame.pose:
                    raise KeyError(f"AnimGraph frame is missing transform {current!r}")
                if current in visiting:
                    raise ValueError(f"AnimGraph frame hierarchy cycle at {current!r}")
                visiting.add(current)
                chain.append(current)
                current = str(frame.parent_map.get(current, "") or "")

            result = cache.get(current) if current else None
            try:
                for bone_name in reversed(chain):
                    local = matrix_from_qs(frame.pose[bone_name])
                    result = (result @ local) if result is not None else local
                    cache[bone_name] = result
                return cache[name]
            finally:
                for bone_name in chain:
                    visiting.discard(bone_name)

        if frame.model_space:
            for raw_name in names:
                name = str(raw_name or "")
                if name:
                    if name not in frame.pose:
                        raise KeyError(f"AnimGraph frame is missing transform {name!r}")
                    cache[name] = matrix_from_qs(frame.pose[name])
            return cache

        for raw_name in names:
            name = str(raw_name or "")
            if name:
                resolve(name)
        return cache

    def dangle_config_by_handle(self) -> dict[str, int]:
        return {
            normalized_source_handle(getattr(node, "source_handle", "")): index
            for index, node in enumerate(self.simulator.state.dangle_nodes)
            if normalized_source_handle(getattr(node, "source_handle", ""))
        }

    def drag_config_by_handle(self) -> dict[str, int]:
        return {
            normalized_source_handle(getattr(node, "source_handle", "")): index
            for index, node in enumerate(self.simulator.state.drag_nodes)
            if normalized_source_handle(getattr(node, "source_handle", ""))
        }

    def dangle_frame_requirements(self, config_index: int) -> tuple[str, ...]:
        names = set()
        tracked = self.simulator.system.node_tracked_indices[config_index]
        pose_bones = tuple(getattr(self.simulator, "_pose_bones", ()) or ())
        for raw_index in tracked:
            index = int(raw_index)
            if (
                0 <= index < len(self.simulator.bone_names)
                and index < len(pose_bones)
                and pose_bones[index] is not None
            ):
                names.add(str(self.simulator.bone_names[index]))
        topologies = getattr(self.simulator, "_node_output_topology", ())
        if 0 <= config_index < len(topologies):
            names.update(
                str(name) for name in topologies[config_index].get("pose_bones", {})
            )
        return tuple(name for name in names if name)

    def structured_base_frame_requirements(self) -> tuple[str, ...]:
        names = set()
        bone_names = tuple(getattr(self.simulator, "bone_names", ()) or ())
        pose_bones = tuple(getattr(self.simulator, "_pose_bones", ()) or ())
        indices = self.simulator.system.dyng_particle_indices
        for raw_index in indices:
            index = int(raw_index)
            if (
                0 <= index < len(bone_names)
                and index < len(pose_bones)
                and pose_bones[index] is not None
            ):
                name = str(bone_names[index] or "")
                if name:
                    names.add(name)
        return tuple(sorted(names))

    def step_dangle_node(
        self,
        config_index: int,
        child: BranchFrame,
        raw_dt: float,
        time_dilation: float,
        skip_physics: bool,
    ) -> DangleStep:
        required = self.dangle_frame_requirements(config_index)
        base_matrices = self.frame_model_matrices(child, required)
        self.simulator._sample_node_input(config_index, model_matrices=base_matrices)
        self.simulator._step_node(config_index, raw_dt, time_dilation, skip_physics)
        matrices, apply_names = solvers._compose_dangle_node_matrices(
            self.simulator, config_index, base_matrices=base_matrices
        )
        return DangleStep(matrices, apply_names, base_matrices)

    def dangle_applied_names(self, step: DangleStep):
        return step.apply_names

    def dangle_output_pose(
        self, step: DangleStep, child: BranchFrame
    ) -> dict[str, Any]:
        """child's pose with the dangle node's simulated bones written into it"""
        matrices, base_matrices = step.matrices, step.base_matrices
        pose = dict(child.pose)
        if child.model_space:
            for name in step.apply_names:
                model = matrices.get(name)
                if model is not None:
                    pose[name] = qs_from_matrix(model)
            return pose
        for name in step.apply_names:
            model = matrices.get(name)
            if model is None:
                continue
            pose_bone = self._frame_pose_bones.get(name)
            bind_matrix = self._bind_matrices.get(name)
            if pose_bone is None or bind_matrix is None:
                continue
            parent_name = str(child.parent_map.get(name, "") or "")
            parent_model = (
                matrices.get(parent_name, base_matrices.get(parent_name))
                if parent_name
                else None
            )
            basis = model_matrix_to_basis(pose_bone, model, parent_model)
            if basis is None:
                local = (
                    parent_model.inverted_safe() @ model
                    if parent_model is not None
                    else model
                )
            else:
                local = bind_matrix @ basis
            pose[name] = qs_from_matrix(local)
        return pose

    def drag_runtime_index(self, config_index: int):
        return self.simulator.drag_post.config_to_runtime.get(config_index)

    def step_drag(self, runtime_index: int, raw_dt: float, operation_callback) -> None:
        self.simulator.drag_post.step_runtime(int(runtime_index), raw_dt)
        if operation_callback is not None:
            operation_callback(self.simulator, "DRAG", int(runtime_index))

    def reset_drag(self, runtime_index: int) -> None:
        self.simulator.drag_post.reset_runtime(int(runtime_index))

    def is_playing(self) -> bool:
        return bool(self.simulator.state.is_playing)

    def consume_external_events(self) -> frozenset[str]:
        state = getattr(self.simulator, "state", None)
        if state is None:
            return frozenset()
        events = frozenset(
            item.strip()
            for item in str(getattr(state, "preview_external_events", "") or "").split(
                ","
            )
            if item.strip()
        )
        if events:
            state.preview_external_events = ""
        return events

    def preview_wrapper_variables(self) -> frozenset[str]:
        names = str(
            getattr(self.simulator.state, "preview_wrapper_variables", "") or ""
        )
        return frozenset(name.strip() for name in names.split(",") if name.strip())

    def preview_features_json(self) -> str:
        return str(
            getattr(self.simulator.state, "preview_anim_features_json", "") or ""
        )

    def preview_vector_input(self, group: str, name: str):
        for item in getattr(self.simulator.state, "preview_vector_inputs", ()) or ():
            if str(getattr(item, "group", "") or "") != group:
                continue
            if str(getattr(item, "input_name", "") or "") == name:
                return tuple(getattr(item, "value", (0.0, 0.0, 0.0)))
        return None

    def look_at_controls(self) -> LookAtControls:
        controls = getattr(self.simulator, "state", None)
        return LookAtControls(
            bool(getattr(controls, "preview_look_at_enabled", False)),
            str(getattr(controls, "preview_look_at_part", "Eyes") or "Eyes"),
            float(getattr(controls, "preview_look_at_speed", 60.0)),
        )

    def look_at_target(self) -> tuple[float, float, float]:
        controls = getattr(self.simulator, "state", None)
        target_object = getattr(controls, "preview_look_at_object", None)
        if target_object is not None:
            return tuple(
                spaces.world_position_to_model(
                    self.armature, target_object.matrix_world.translation
                )
            )
        return tuple(getattr(controls, "preview_look_at_target", (0.0, 3.0, 1.6)))

    def world_vector_to_model(
        self, vector, *, direction: bool
    ) -> tuple[float, float, float]:
        return tuple(
            spaces.world_vector_to_model(self.armature, vector, direction=direction)
        )

    def frame_change_counters(self) -> tuple[int, int, float]:
        return (
            int(getattr(self.simulator, "_frame_change_capture_events", 0)),
            int(getattr(self.simulator, "_frame_change_evaluated_events", 0)),
            float(getattr(self.simulator, "_frame_change_input_bones", 0)),
        )
