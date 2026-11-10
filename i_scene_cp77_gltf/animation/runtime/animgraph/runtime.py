from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

from ....assetio.paths import local_path_key
from ....assetio.transform_values import qs_transform_from_data, vector3_from_data
from ....assetio.values import cname_or_empty, cname_text
from ....bartmoss.qs_transform import relative_to
from ....core.log import TRACE, debug_exception, get_logger
from ....redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ....redSpace.engine_pose import EngineSpacePose, engine_value_to_frame
from ...domain.animgraph.animation_scope import graph_animation_names
from ...domain.animgraph.blends import blend_two_inputs, blend_two_weight
from ...domain.animgraph.branch_frames import (
    identity_frame,
    interpolate_frames,
    missing_clip_frame,
    scope_signature,
    track_snapshots_equal,
)
from ...domain.animgraph.exploration import exploration_animation, exploration_inputs
from ...domain.animgraph.facial_mixer import FacialMixerState, advance_mixer
from ...domain.animgraph.look_at import (
    LookAtControllerState,
    LookAtRequest,
    inactive_graph_inputs,
)
from ...domain.animgraph.pose_program import (
    ENGINE_SPACE_POSE_OPS,
    compile_pose_program,
    program_handles,
)
from ...domain.animgraph.pose_space import (
    build_hierarchy_plan,
    model_transform,
    pose_ls_to_ms,
    pose_ms_to_ls,
)
from ...domain.animgraph.shared_meta_pose import (
    build_binding,
    build_part_scope,
    evaluate_shared_meta_pose,
)
from ...domain.animgraph.stack import (
    extend_tracks,
    extend_transforms,
    extender_size,
    paired_remove_counts,
    shrink_tracks,
    shrink_transforms,
)
from ...domain.animgraph.switch import (
    SyncEntry,
    selected_input_index,
    switch_state_weights,
    synced_clip_time,
)
from ...domain.animgraph.topology import (
    handle_index,
    layout_order_handles,
    reference_handle,
)
from ...domain.animgraph.trajectory_meta_pose import (
    PREDICTIVE_LOOK_AT_TRACKS,
    apply_predictive_look_at_rotation,
)
from ...domain.animgraph.workspot import (
    WorkspotHubState,
    advance_workspot_hub,
    workspot_blending,
    workspot_inputs,
)
from ...domain.clip.additive import (
    ADDITIVE_LOCAL,
    ADDITIVE_STORAGE_REFERENCE_APPLIED,
    TRACK_BASE,
    TRACK_INTERPOLATE,
    additive_branch_active,
    convert_pose_to_additive_local,
    evaluate_blend_additive,
    evaluate_shared_meta_pose_additive,
    final_additive_weight,
    is_additive_animation_type,
    recover_reference_applied_transform,
    reference_or_identity_pose,
    sampled_animation_track_seed,
    sampled_animation_transform,
)
from ...domain.clip.timing import (
    advance_source_clip_time,
    clip_events_passed,
    one_shot_weight,
    source_clip_sample_frame,
)
from ...domain.rig.assembly import merge_rig_datas
from ...domain.rig.naming import merged_bone_name
from ...handlers.animgraph.base import ExecutionStep, PoseOpState
from ...handlers.animgraph.registry import POSE_OP_HANDLERS, graph_node_handler
from ...model.animgraph.frames import BranchFrame, TrackSnapshot
from ...model.animgraph.handles import normalized_source_handle
from ...model.animgraph.results import SolveResults
from ...model.clip.metadata import FPS
from ...model.events.codec import event_array
from .foot_phase_sync import FootPhaseTrack, foot_phase_synced_time
from .host import AnimGraphHost
from .value_graph import ValueGraph

_LOG = get_logger(__name__)


@dataclass(frozen=True)
class OperationBinding:
    source_handle: str
    boundary_node: Any | None
    plan: Any | None
    required_bones: frozenset[str]
    required_tracks: frozenset[str]


class AnimGraphRuntime:
    def __init__(
        self,
        host: AnimGraphHost,
        source_handles: Iterable[str],
        source_payload: Mapping[str, Any] | None = None,
    ):
        self.host = host
        self.bindings: list[OperationBinding] = []
        self.required_bones: set[str] = set()
        self.required_tracks: set[str] = set()
        self.owned_bones: set[str] = set()
        self.owned_tracks: set[str] = set()
        self._owner_scope_bound = False
        self._meta_rig_paths: tuple[str, ...] = ()
        self._meta_rig_datas: tuple[Any, ...] = ()
        self._meta_rig_part_bindings: tuple[Mapping[str, str], ...] = ()
        self._meta_rig_scope = None
        self._meta_rig_merged_data = None
        self._red_pose_bridge = False
        self._facial_session = None
        self._facial_binding = None
        self._facial_root_bridge_bones: tuple[str, ...] | None = None
        self._facial_owner_parent_overrides: dict[str, str] | None = None
        self._facial_owner_reference_overrides: dict[str, Any] | None = None
        self._facial_owner_reference_track_overrides: dict[str, float] | None = None
        self._facial_owner_resolved_names: tuple[str, ...] | None = None
        self._meta_parent_frame_current: BranchFrame | None = None
        self._facial_transform_trace_stages: set[str] = set()
        self._input_tracks: dict[str, TrackSnapshot] = {}
        self._last_output_tracks: dict[str, TrackSnapshot | None] = {}
        self._written_tracks: set[str] = set()
        self.structured = False
        self.program = None
        self._linear_program: tuple[Any, ...] = ()
        self._input_capture_bones: tuple[str, ...] = ()
        self._nodes = host.nodes_by_handle()
        self._pose_plans: dict[str, Any] = {}
        self._blend_data: dict[str, dict[str, Any]] = {}
        self._blend_active: dict[str, bool] = {}
        self._additive_data: dict[str, dict[str, Any]] = {}
        self._additive_active: dict[str, bool] = {}
        self._additive_masks: dict[str, Mapping[str, float] | None] = {}
        self._additive_previous_track_values: dict[str, float] = {}
        self._source_anim_times: dict[str, float] = {}
        self._one_shot_running: dict[str, bool] = {}
        self._workspot_states: dict[str, WorkspotHubState] = {}
        self._exploration_states: dict[str, tuple[tuple, float]] = {}
        # Values nodes publish by tag during a frame's update, read by TagValue.
        self._data_flow: dict[str, float] = {}
        self._blend_weights: dict[str, tuple[float, ...]] = {}
        # Each node's output frame in the last step, by normalized handle, for the results and the viewed node.
        self._last_frames: dict[str, BranchFrame] = {}
        # Handles of the pose nodes the last step executed, on additive branches too.
        self._ran_handles: set[str] = set()
        # Each program node's inputs by the field they come from, for the program it was read from.
        self._input_field_names: dict[str, tuple[str, ...]] = {}
        self._input_fields_program = None
        # A node whose output pose the rig shows instead of the graph's final pose.
        self.view_handle: str | None = None
        self._source_anim_first_frames: dict[
            tuple[str, int], tuple[dict[str, Any], dict[str, float]]
        ] = {}
        self._source_anim_advanced_frame: dict[str, int] = {}
        self._source_index: dict[str, dict[str, Any]] = {}
        self._source_root_reference: Any = None
        self._float_variable_names: frozenset[str] = frozenset()
        self._rig_float_inputs = None
        self._rotate_angles: dict[str, float] = {}
        self._quaternion_rotations: dict[str, tuple[float, float, float, float]] = {}
        # Extra transforms written by AdditionalTransform: name -> (parent, reference QsTransform).
        self._extra_transforms: dict[str, tuple[str, Any]] = {}
        self._translation_values: dict[str, tuple[float, float, float]] = {}
        self._additional_track_times: dict[str, float] = {}
        self._state_machine_states: dict[str, int] = {}
        self._state_machine_blends: dict[str, dict[str, Any]] = {}
        self._state_condition_history: dict[Any, Any] = {}
        self._switch_selected: dict[str, int] = {}
        self._blend_two_active: dict[str, frozenset[int]] = {}
        # Each Blend2's weight as it last played, for the sync data gathered before its next update.
        self._blend_two_weight: dict[str, float] = {}
        self._switch_blends: dict[str, tuple[int, float]] = {}
        self._switch_active: dict[str, frozenset[int]] = {}
        self._state_machine_pending: dict[str, int] = {}
        self._state_machine_transition_delay: set[str] = set()
        self._anim_end_events: set[str] = set()
        # Names of the clip events the playing clips passed this frame, for AnimEvent conditions.
        self._anim_events: set[str] = set()
        # Each clip's events, read once per clip.
        self._clip_events: dict[str, tuple[Mapping[str, Any], ...]] = {}
        self._available_animations: frozenset[str] = frozenset()
        self._missing_active_animations_logged: set[tuple[str, str]] = set()
        self._external_events_this_frame: frozenset[str] = frozenset()
        self._preview_feature_cache: dict[tuple[str, str], Any] | None = None
        self._current_raw_dt = 0.0
        self._current_graph_dt = 0.0
        self._shared_meta_binding = None
        self._shared_meta_nodes: dict[str, Any] = {}
        self._stack_transform_names: set[str] = set()
        self._stack_track_names: set[str] = set()
        self._missing_optional_bones: set[str] = set()
        self._missing_optional_tracks: set[str] = set()
        self._stack_data_by_handle: dict[str, dict[str, Any]] = {}
        self._pure_pose_handles: set[str] = set()
        self._look_at_data: dict[str, dict[str, Any]] = {}
        self._look_at_states: dict[str, LookAtControllerState] = {}
        self._facial_mixer_data: dict[str, dict[str, Any]] = {}
        self._facial_mixer_states: dict[str, FacialMixerState] = {}
        self._trajectory_meta_data: dict[str, dict[str, Any]] = {}
        self._internal_graph_inputs: dict[tuple[str, str], Any] = {}
        self._blender_pose_dirty = False
        self._perf_frames = 0
        self._previous_anim_end_events: frozenset[str] = frozenset()
        self._mask_blend_active: dict[str, bool] = {}
        self._blend_multiple_selection: dict[str, tuple[int, int, float]] = {}
        self._blend_multiple_active: dict[str, frozenset[int]] = {}
        self._time_warp_progress: dict[str, float] = {}
        self._foot_phase_tracks: dict[tuple[str, float], Any] = {}
        self._rig_part_cache: (
            dict[str, tuple[dict[str, float], frozenset[str]]] | None
        ) = None
        self._missing_blink_animations: set[str] = set()
        self._source_action_types_logged: set[tuple] = set()
        self._execution_trace: list[dict[str, Any]] = []
        self._last_program_node: dict[str, Any] | None = None
        self._inertialization_states: dict[str, Any] = {}
        # (frame, duration) of the latest inertialization request; read by Inertialization nodes.
        self._inertialization_request: tuple[int, float] = (-1, 0.0)
        self._perf_capture = 0.0
        self._perf_execute = 0.0
        self._perf_final_restore = 0.0
        self._perf_restore_calls = 0
        self._perf_restore_writes = 0
        self._perf_depsgraph_updates = 0
        self._perf_depsgraph_time = 0.0
        self._perf_dangle = 0.0
        self._perf_drag = 0.0
        self._perf_stack = 0.0
        self._perf_pose_ops = 0.0
        self._perf_pose_op_types: dict[str, float] = {}
        self._perf_pose_space = 0.0
        self._perf_shared_meta = 0.0
        self._perf_blend = 0.0
        self._perf_step_total = 0.0
        self._perf_draw = 0.0
        self._frame_cache_names: tuple[str, ...] = ()
        self._reference_pose_ls: dict[str, Any] = {}
        self._bind_pose_ls: dict[str, Any] = {}
        self._reference_model_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._pose_hierarchy_plan_cache: dict[tuple[Any, ...], Any] = {}
        self._last_graph_output_pose: dict[str, Any] = {}
        self._perf_semantic_dirty_bones = 0
        self._perf_deferred_final_syncs = 0
        self._drag_config_by_handle = host.drag_config_by_handle()
        self._dangle_config_by_handle = host.dangle_config_by_handle()
        self.values = ValueGraph(self._source_index, self)
        if source_payload is not None:
            self._compile_structured(source_payload)
        if not self.structured:
            self._compile(tuple(source_handles))
        self._input_tracks = host.capture_tracks(self.required_tracks)
        self._last_output_tracks = {name: None for name in self.required_tracks}
        _LOG.debug(
            "Compiled Dangle AnimGraph runtime: mode=%s bindings=%d bones=%d tracks=%d graph=%s",
            "branch" if self.structured else "linear",
            len(self.bindings),
            len(self.required_bones),
            len(self.required_tracks),
            host.graph_name,
        )

    def resolve_structured_bone(self, authored: str, *, required: bool = False) -> str:
        name = str(authored or "")
        if not name or name in self._stack_transform_names:
            return name
        resolved = self.host.resolve_bone(name)
        if resolved is None:
            if required:
                raise ValueError(
                    f"AnimGraph pose preview requires missing bone {name!r}"
                )
            self._missing_optional_bones.add(name)
            return name
        self.required_bones.add(resolved)
        return resolved

    def resolve_structured_track(self, authored: str, *, required: bool = False) -> str:
        name = str(authored or "")
        if not name or name in self._stack_track_names:
            return name
        known = set(self.host.track_names())
        exists = name in known if known else self.host.has_track(name)
        if required and not exists:
            raise ValueError(f"AnimGraph pose preview requires missing track {name!r}")
        if exists:
            self.required_tracks.add(name)
        elif name:
            self._missing_optional_tracks.add(name)
        return name

    def _map_stack_data(self, program_node) -> dict[str, Any]:
        data = dict(program_node.data)
        if program_node.kind == "STACK_TRANSFORMS_EXTEND":
            entries = []
            for raw in data.get("entries", ()):
                item = dict(raw)
                parent = str(item.get("parent", "") or "")
                snap = str(item.get("snapTargetBone", "") or "")
                offset = str(item.get("offsetSpaceBone", "") or "")
                item["parent"] = self.resolve_structured_bone(
                    parent, required=parent not in self._stack_transform_names
                )
                item["snapTargetBone"] = self.resolve_structured_bone(
                    snap, required=False
                )
                item["offsetSpaceBone"] = self.resolve_structured_bone(
                    offset, required=False
                )
                item["_referenceQs"] = qs_transform_from_data(
                    item.get("referenceTransformLs")
                )
                item["_offsetQs"] = qs_transform_from_data(item.get("offset"))
                entries.append(item)
            data["entries"] = tuple(entries)
        return data

    def _map_pure_pose_data(self, program_node) -> dict[str, Any]:
        data = dict(program_node.data)
        node_type = program_node.node_type
        handler = POSE_OP_HANDLERS.get(node_type)
        if handler is not None:
            data = handler.map_data(self, program_node, node_type, data)
        return data

    def _load_meta_rig_context(self, *, required: bool = False):
        if self._meta_rig_scope is not None:
            return self._meta_rig_paths, self._meta_rig_datas, self._meta_rig_scope
        paths = self.host.source_rig_paths()
        part_bindings = self.host.source_rig_part_bindings()
        graph_path = self.host.settings.graph_path
        if not paths or not graph_path:
            if required:
                raise ValueError(
                    "MetaRig part ownership requires source-rig metadata and the imported AnimGraph path"
                )
            return (), (), None
        try:
            rig_datas = self.host.load_rig_datas(paths)
            scope = build_part_scope(graph_path, paths, rig_datas, part_bindings)
            merged_data = merge_rig_datas(rig_datas, self.host.name)
        except Exception as exc:
            if required:
                raise ValueError(
                    f"MetaRig part ownership binding failed: {exc}"
                ) from exc
            if part_bindings:
                _LOG.warning(
                    "MetaRig part ownership binding failed for %s",
                    graph_path,
                    exc_info=True,
                )
            else:
                debug_exception(
                    _LOG, "MetaRig part ownership unavailable for %s", graph_path
                )
            return (), (), None
        self._meta_rig_paths = paths
        self._meta_rig_datas = rig_datas
        self._meta_rig_part_bindings = part_bindings
        self._meta_rig_scope = scope
        self._meta_rig_merged_data = merged_data
        return paths, rig_datas, scope

    def _compile_meta_rig_ownership(self) -> None:
        _paths, _datas, scope = self._load_meta_rig_context(required=False)
        if scope is None:
            return
        for authored in scope.transform_names:
            name = self.resolve_structured_bone(authored, required=True)
            if name:
                self.owned_bones.add(name)
        known_tracks = set(self.host.track_names())
        for raw_name in scope.track_names:
            name = str(raw_name or "")
            if not name:
                continue
            if name not in known_tracks and not self.host.has_track(name):
                continue
            self.owned_tracks.add(name)
            self.required_tracks.add(name)
        self._owner_scope_bound = True
        owner_binding = next(
            (
                value
                for value in self._meta_rig_part_bindings
                if local_path_key(str(value.get("path", "") or ""))
                == local_path_key(scope.owner_path)
                or local_path_key(str(value.get("source_path", "") or ""))
                == local_path_key(scope.owner_path)
            ),
            {},
        )
        _LOG.debug(
            "Bound MetaRig graph ownership: part=%s index=%d component=%s graph=%s transforms=%d tracks=%d",
            scope.owner_name or scope.owner_path,
            scope.owner_index,
            str(owner_binding.get("component", "") or "<unknown>"),
            str(owner_binding.get("graph", "") or "<name-match>"),
            len(self.owned_bones),
            len(self.owned_tracks),
        )

    def _graph_output_bones(self) -> tuple[str, ...]:
        if self._owner_scope_bound:
            owned = self.owned_bones
            return tuple(name for name in self.host.frame_bone_names() if name in owned)
        return tuple(self.host.frame_bone_names())

    def _graph_output_tracks(self) -> tuple[str, ...]:
        if self._owner_scope_bound:
            owned = self.owned_tracks
            return tuple(name for name in self.required_tracks if name in owned)
        return tuple(self.required_tracks)

    def _compile_shared_meta_pose_binding(self, program_nodes) -> None:
        shared_nodes = [
            node
            for node in program_nodes
            if node.kind
            in {
                "SHARED_META_POSE",
                "FACIAL_SHARED_META_POSE",
                "SHARED_META_POSE_ADDITIVE",
            }
        ]
        if not shared_nodes:
            return
        graph_path = self.host.settings.graph_path
        try:
            paths, rig_datas, _scope = self._load_meta_rig_context(required=True)
            binding = build_binding(
                graph_path, paths, rig_datas, self._meta_rig_part_bindings
            )
        except Exception as exc:
            _LOG.warning("SharedMetaPose context binding failed: %s", exc)
            raise ValueError(f"SharedMetaPose context binding failed: {exc}") from exc

        mapped_bones = []
        for name in binding.transform_names:
            mapped_bones.append(self.resolve_structured_bone(name, required=True))
        mapped_tracks = []
        for name in binding.track_names:
            mapped_tracks.append(self.resolve_structured_track(name, required=True))
        self._shared_meta_binding = binding.with_resolved_names(
            mapped_bones, mapped_tracks
        )
        for program_node in shared_nodes:
            handle = normalized_source_handle(program_node.handle)
            graph_node = self._nodes.get(handle)
            if graph_node is None:
                raise ValueError(
                    f"SharedMetaPose node handle {handle!r} is missing from the Blender graph"
                )
            self._shared_meta_nodes[handle] = graph_node
        _LOG.debug(
            "Bound SharedMetaPose context: part=%s index=%d parent_parts=%d transforms=%d tracks=%d",
            binding.owner_name or binding.owner_path,
            binding.owner_index,
            binding.owner_index,
            len(mapped_bones),
            len(mapped_tracks),
        )
        _LOG.debug(
            "SharedMetaPose mapped transforms=%s tracks=%s",
            tuple(mapped_bones),
            tuple(mapped_tracks),
        )

    def _compile_additive_mask(self, mask_name: str) -> Mapping[str, float] | None:
        name = str(mask_name or "")
        if not name or name == "None":
            return None
        _paths, rig_datas, _scope = self._load_meta_rig_context(required=True)
        for rig_data in rig_datas:
            for part in getattr(rig_data, "parts", ()) or ():
                if (
                    not isinstance(part, Mapping)
                    or cname_text(part.get("name")) != name
                ):
                    continue
                weights: dict[str, float] = {}
                bone_names = tuple(getattr(rig_data, "bone_names", ()) or ())
                for entry in part.get("mask", ()) or ():
                    if not isinstance(entry, Mapping):
                        continue
                    try:
                        index = int(entry.get("index"))
                        weight = float(entry.get("weight", 0.0))
                    except (TypeError, ValueError):
                        continue
                    if not 0 <= index < len(bone_names):
                        continue
                    authored = merged_bone_name(bone_names[index])
                    resolved = self.resolve_structured_bone(authored, required=True)
                    if resolved:
                        weights[resolved] = weight
                return weights
        _LOG.debug(
            "BlendAdditive mask %r is not present in the merged rig; using the full pose",
            name,
        )
        return None

    def _stack_remove_counts(
        self, extender_type: str, shrinker_type: str
    ) -> dict[str, int]:
        """Shrinker remove counts from extender pairing over the whole graph"""
        items = []
        for handle in layout_order_handles(
            self._source_root_reference, self._source_index
        ):
            node = self._source_index.get(handle)
            node_type = (
                str(node.get("$type", "") or "") if isinstance(node, Mapping) else ""
            )
            if node_type in {extender_type, shrinker_type}:
                items.append(
                    (
                        normalized_source_handle(handle),
                        node_type == extender_type,
                        cname_or_empty(node.get("tag")),
                        extender_size(node_type, node)
                        if node_type == extender_type
                        else 0,
                    )
                )
        return paired_remove_counts(items)

    def _build_linear_program(self, root) -> tuple[Any, ...]:
        if root is None:
            return ()
        allowed = {
            "INPUT",
            "REFERENCE",
            "IDENTITY",
            "SHARED_META_POSE",
            "SHARED_META_POSE_ADDITIVE",
            "TRAJECTORY_FROM_META_POSE",
            "POSE_LS_TO_MS",
            "POSE_MS_TO_LS",
            "STACK_TRANSFORMS_EXTEND",
            "STACK_TRANSFORMS_SHRINK",
            "STACK_TRACKS_EXTEND",
            "STACK_TRACKS_SHRINK",
            "POSE_OP",
            "SLOT_PASSTHROUGH",
        }
        chain = []
        seen = set()
        current = root
        while current is not None:
            identity = id(current)
            if (
                identity in seen
                or current.kind not in allowed
                or len(current.children) > 1
            ):
                return ()
            if current.kind == "POSE_OP":
                handle = normalized_source_handle(current.handle)
                if handle not in self._pure_pose_handles:
                    return ()
            seen.add(identity)
            chain.append(current)
            current = current.children[0] if current.children else None
        chain.reverse()
        return tuple(chain)

    def _compile_structured(self, source_payload: Mapping[str, Any]) -> None:
        if not self.host.has_graph:
            return
        root_chunk = source_payload.get("Data", {}).get("RootChunk", {})
        root_reference = root_chunk.get("rootNode")
        self._source_root_reference = root_reference
        graph_animations = graph_animation_names(source_payload)
        available_animations = self.host.available_animation_names(source_payload)
        self._available_animations = frozenset(available_animations)
        try:
            index = handle_index(source_payload)
            self._source_index = index
            self.values.index = index
            self.host.bind_values(
                lambda handle: self.values.value("float", {"HandleRefId": handle})
            )
            self._float_variable_names = frozenset(
                cname_text(node.get("variableName"))
                for node in index.values()
                if node.get("$type") == "animAnimNode_FloatVariable"
            )
            settings = self.host.settings
            tags = frozenset(
                tag.strip() for tag in settings.visual_tags.split(",") if tag.strip()
            )
            rig_tags = frozenset(
                str(tag)
                for tag in self.host.rig_tags()
                if str(tag or "") and str(tag) != "None"
            )
            component_tags = frozenset(
                tag.strip() for tag in settings.component_tags.split(",") if tag.strip()
            )
            plan = compile_pose_program(
                root_reference,
                index,
                visual_tags=tags,
                skeletal_lod=settings.skeletal_lod,
                performance_mode=settings.performance_mode,
                available_animations=available_animations,
                rig_tags=rig_tags,
                parent_tags=component_tags,
            )
        except (KeyError, TypeError, ValueError) as exc:
            _LOG.error(
                "AnimGraph runtime compile failed: rig=%s graph=%s root_handle=%s "
                "graph_animations=%r available_animations=%r missing_graph_animations=%r error=%s",
                self.host.name,
                self.host.settings.graph_path,
                reference_handle(root_reference) or "<inline>",
                tuple(sorted(graph_animations)),
                tuple(sorted(available_animations)),
                tuple(sorted(set(graph_animations) - set(available_animations))),
                exc,
            )
            raise ValueError(f"AnimGraph branch program compile failed: {exc}") from exc
        _LOG.debug(
            "AnimGraph runtime compile context: rig=%s graph=%s root_handle=%s root_kind=%s "
            "lod=%d performance_mode=%s visual_tags=%r rig_tags=%r graph_animations=%r "
            "available_animations=%r missing_graph_animations=%r boundaries=%r",
            self.host.name,
            self.host.settings.graph_path,
            reference_handle(root_reference) or "<inline>",
            getattr(plan.root, "kind", "<none>") if plan.root is not None else "<none>",
            self.host.settings.skeletal_lod,
            self.host.settings.performance_mode,
            tuple(sorted(tags)),
            tuple(sorted(rig_tags)),
            tuple(sorted(graph_animations)),
            tuple(sorted(available_animations)),
            tuple(sorted(set(graph_animations) - set(available_animations))),
            tuple(plan.boundaries),
        )
        if plan.boundaries:
            raise ValueError("Graph preview unavailable: " + "\n".join(plan.boundaries))
        if plan.root is None:
            return
        stack = [plan.root]
        seen_slots = set()
        while stack:
            program_node = stack.pop()
            identity = id(program_node)
            if identity in seen_slots:
                continue
            seen_slots.add(identity)
            if (
                program_node.kind == "SLOT_PASSTHROUGH"
                and program_node.data.get("slotType")
                == "animAnimNode_GraphSlotConditions"
                and int(program_node.data.get("selectedConditionIndex", -1)) >= 0
            ):
                _LOG.debug(
                    "GraphSlotConditions fallback active: rig=%s handle=%s path=%s "
                    "condition_index=%d condition_type=%s condition_value=%r graph=%r "
                    "injected_graph_evaluated=False fallback=inputLink",
                    self.host.name,
                    program_node.handle or "<inline>",
                    program_node.path,
                    int(program_node.data.get("selectedConditionIndex", -1)),
                    str(
                        program_node.data.get("selectedConditionType", "")
                        or "<unknown>"
                    ),
                    str(program_node.data.get("selectedConditionValue", "") or ""),
                    str(program_node.data.get("selectedGraph", "") or ""),
                )
            stack.extend(reversed(program_node.children))
        has_structured_nodes = bool(plan.blend_handles) or any(
            program_handles(plan.root, kind=kind)
            for kind in (
                "POSE_OP",
                "LOOK_AT_CONTROLLER",
                "FACIAL_MIXER",
                "TRAJECTORY_FROM_META_POSE",
                "SHARED_META_POSE",
                "FACIAL_SHARED_META_POSE",
                "SHARED_META_POSE_ADDITIVE",
                "IDENTITY",
                "SK_ANIM",
                "STACK_TRANSFORMS_EXTEND",
                "STACK_TRANSFORMS_SHRINK",
                "STACK_TRACKS_EXTEND",
                "STACK_TRACKS_SHRINK",
                "STATE_MACHINE",
                "SLOT_PASSTHROUGH",
                "SWITCH",
                "BLEND_TWO",
                "INERTIALIZATION",
                "BLEND_MULTIPLE",
                "BLEND_MASK_DYNAMIC",
                "WORKSPOT_HUB",
                "NPC_EXPLORATION",
            )
        )
        if not has_structured_nodes:
            return
        self.program = plan.root
        nodes = []
        seen = set()
        stack = [plan.root]
        while stack:
            program_node = stack.pop()
            identity = id(program_node)
            if identity in seen:
                continue
            seen.add(identity)
            nodes.append(program_node)
            if program_node.kind == "STACK_TRANSFORMS_EXTEND":
                self._stack_transform_names.update(
                    str(item.get("name", "") or "")
                    for item in program_node.data.get("entries", ())
                )
            elif program_node.kind == "STACK_TRACKS_EXTEND":
                self._stack_track_names.update(
                    str(item.get("name", "") or "")
                    for item in program_node.data.get("entries", ())
                )
            elif (
                program_node.kind == "POSE_OP"
                and program_node.node_type == "animAnimNode_AdditionalTransform"
            ):
                for item in program_node.data.get("entries", ()):
                    self._extra_transforms.setdefault(
                        item["name"],
                        (
                            str(item.get("parent", "") or ""),
                            qs_transform_from_data(item.get("reference")),
                        ),
                    )
                    self._stack_transform_names.add(item["name"])
            stack.extend(program_node.children)
        self._stack_transform_names.discard("")
        self._stack_track_names.discard("")
        self._compile_meta_rig_ownership()
        self._compile_shared_meta_pose_binding(nodes)
        if any(
            node.node_type
            in {"animAnimNode_Sermo", "animAnimNode_FacialSharedMetaPose"}
            for node in nodes
        ):
            self._facial_session, self._facial_binding = self.host.bind_facial_graph()
            self.required_bones.update(
                name for name in self._facial_binding.bone_names if name
            )
            self.required_tracks.update(self._facial_binding.track_names)

        for program_node in nodes:
            handle = normalized_source_handle(program_node.handle)
            if program_node.kind == "POSE_OP":
                if program_node.data:
                    self._pure_pose_handles.add(handle)
                    mapped = self._map_pure_pose_data(program_node)
                    self._pose_plans[handle] = mapped
                else:
                    node = self._nodes.get(handle)
                    if node is None:
                        raise ValueError(
                            f"AnimGraph pose operation handle {handle!r} is missing from the Blender graph"
                        )
                    prepared = self.host.prepare_node_operation(node)
                    if prepared is not None:
                        self._pose_plans[handle] = prepared
                        self.required_bones.update(prepared.required_bones)
                        self.required_tracks.update(prepared.requested_tracks)
            elif program_node.kind == "LOOK_AT_CONTROLLER":
                mapped = dict(program_node.data)
                parts = []
                for raw in mapped.get("orderedBodyParts", ()) or ():
                    item = dict(raw)
                    bone = str(item.get("defaultPositionBoneName", "") or "")
                    item["defaultPositionBoneName"] = self.resolve_structured_bone(
                        bone, required=False
                    )
                    parts.append(item)
                mapped["orderedBodyParts"] = tuple(parts)
                settings = []
                for raw in mapped.get("stateMachinesSettings", ()) or ():
                    item = dict(raw)
                    bone = str(item.get("sphereAttachmentBone", "") or "")
                    item["sphereAttachmentBone"] = self.resolve_structured_bone(
                        bone, required=False
                    )
                    for key in (
                        "enableFloatTrack",
                        "eyesOverrideFloatTrack",
                        "coneLimitReached",
                    ):
                        track = str(item.get(key, "") or "")
                        item[key] = (
                            self.resolve_structured_track(track, required=False)
                            if track
                            else ""
                        )
                    settings.append(item)
                mapped["stateMachinesSettings"] = tuple(settings)
                self._look_at_data[handle] = mapped
                self._look_at_states[handle] = LookAtControllerState()
                self._internal_graph_inputs.update(inactive_graph_inputs(mapped))
            elif program_node.kind == "FACIAL_MIXER":
                self._facial_mixer_data[handle] = dict(program_node.data)
                self._facial_mixer_states[handle] = FacialMixerState()
            elif program_node.kind == "TRAJECTORY_FROM_META_POSE":
                target = str(program_node.data.get("metaPoseTrajectoryLs", "") or "")
                target = (
                    self.resolve_structured_bone(target, required=True)
                    if target
                    else ""
                )
                source = self.resolve_structured_bone("Trajectory", required=True)
                known_tracks = set(self.host.track_names())
                predictive = ()
                if all(name in known_tracks for name in PREDICTIVE_LOOK_AT_TRACKS):
                    predictive = tuple(
                        self.resolve_structured_track(name, required=True)
                        for name in PREDICTIVE_LOOK_AT_TRACKS
                    )
                self._trajectory_meta_data[handle] = {
                    "target": target,
                    "source": source,
                    "predictiveTracks": predictive,
                }
            elif program_node.kind == "BLEND_OVERRIDE":
                mapped = dict(program_node.data)
                mapped_bones = []
                # A listed bone or track the rig does not have is skipped: one graph's lists (a weapon's, say)
                # name bones only some of the rigs it runs on have.
                for item in mapped.get("bones", ()):
                    authored = str(item.get("bone", "") or "")
                    resolved = self.resolve_structured_bone(authored)
                    if resolved and authored not in self._missing_optional_bones:
                        mapped_bones.append(
                            {"bone": resolved, "weight": float(item.get("weight", 1.0))}
                        )
                        if (
                            mapped.get("blendMethod") == "BoneBranch"
                            and resolved not in self._stack_transform_names
                        ):
                            self.required_bones.update(
                                self.host.bone_descendants(resolved)
                            )
                mapped["bones"] = tuple(mapped_bones)
                mapped_tracks = []
                for item in mapped.get("tracks", ()):
                    name = str(item.get("track", "") or "")
                    track = self.resolve_structured_track(name) if name else ""
                    if track and name not in self._missing_optional_tracks:
                        mapped_tracks.append(
                            {"track": track, "weight": float(item.get("weight", 1.0))}
                        )
                mapped["tracks"] = tuple(mapped_tracks)
                if bool(mapped.get("blendAllTracks", False)):
                    self.required_tracks.update(self.host.track_names())
                if mapped.get("blendMethod") == "Mask":
                    self._require_rig_part_bones(mapped.get("maskName", ""))
                self._blend_data[handle] = mapped
                self._blend_active[handle] = False
            elif program_node.kind == "BLEND_MASK_DYNAMIC":
                for mask_name in program_node.data.get("masks", ()):
                    self._require_rig_part_bones(mask_name)
            elif program_node.kind == "BLEND_ADDITIVE":
                mapped = dict(program_node.data)
                self._additive_data[handle] = mapped
                self._additive_masks[handle] = self._compile_additive_mask(
                    str(mapped.get("maskName", "") or "")
                )
                self._additive_active[handle] = False
                previous_track = str(mapped.get("previousFrameWeightTrack", "") or "")
                if previous_track:
                    mapped["previousFrameWeightTrack"] = self.resolve_structured_track(
                        previous_track, required=True
                    )
                    self._additive_previous_track_values[handle] = float(
                        mapped.get("previousFrameWeightDefault", 0.0) or 0.0
                    )
                if str(mapped.get("blendTracks", "AGBT_Add")).split("::")[-1] not in {
                    "AGBT_BasePose",
                    "BasePose",
                    "0",
                }:
                    self.required_tracks.update(self.host.track_names())

            elif program_node.kind in {"SK_ANIM", "WORKSPOT_HUB", "NPC_EXPLORATION"}:
                self.required_bones.update(self.owned_bones)
                self.required_tracks.update(self.host.track_names())

        # Pair by tag; serialized editor IDs are not runtime authority.
        transform_remove_counts = self._stack_remove_counts(
            "animAnimNode_StackTransformsExtender",
            "animAnimNode_StackTransformsShrinker",
        )
        track_remove_counts = self._stack_remove_counts(
            "animAnimNode_StackTracksExtender", "animAnimNode_StackTracksShrinker"
        )

        # Map stack physical references only after all virtual names are known.
        for program_node in nodes:
            if program_node.kind.startswith("STACK_"):
                handle = normalized_source_handle(program_node.handle)
                mapped = self._map_stack_data(program_node)
                if program_node.kind == "STACK_TRANSFORMS_SHRINK":
                    mapped["removeCount"] = transform_remove_counts.get(handle, 0)
                elif program_node.kind == "STACK_TRACKS_SHRINK":
                    mapped["removeCount"] = track_remove_counts.get(handle, 0)
                self._stack_data_by_handle[handle] = mapped

        dangle_handles = tuple(program_handles(plan.root, kind="DANGLE"))
        drag_handles = tuple(program_handles(plan.root, kind="DRAG"))
        self._red_pose_bridge = bool(
            (
                (self._owner_scope_bound and self._meta_rig_merged_data is not None)
                or self._facial_binding is not None
            )
            and not dangle_handles
            and not drag_handles
        )
        if self._facial_binding is not None:
            if not self._red_pose_bridge:
                raise ValueError(
                    "Sermo requires the local-pose graph bridge; mixed dangle/drag graphs are not supported"
                )
            self.host.claim_facial_session(self._facial_session, self)
        for raw_handle in dangle_handles:
            handle = normalized_source_handle(raw_handle)
            config_index = self._dangle_config_by_handle.get(handle)
            if config_index is None:
                continue
            self.required_bones.update(
                self.host.dangle_frame_requirements(config_index)
            )
        if dangle_handles:
            self.required_bones.update(self.host.structured_base_frame_requirements())

        self.required_bones.update(self.host.with_ancestor_bones(self.required_bones))
        self._linear_program = self._build_linear_program(plan.root)
        self._input_capture_bones = ()
        if (
            self._red_pose_bridge
            and self._owner_scope_bound
            and self._linear_program
            and self._linear_program[0].kind == "REFERENCE"
        ):
            capture_bones = set(self.required_bones - self.owned_bones)
            binding = self._shared_meta_binding
            if binding is not None:
                capture_bones.update(binding.transform_names)
            self._input_capture_bones = tuple(
                sorted(name for name in capture_bones if name)
            )
            _LOG.debug(
                "AnimGraph input capture scope: %d/%d physical transforms",
                len(self._input_capture_bones),
                len(self.required_bones),
            )
        if self._owner_scope_bound:
            dependency_only = tuple(sorted(self.required_bones - self.owned_bones))
            _LOG.debug(
                "MetaRig Graph transform scope: owned=%d dependency_only=%d dependencies=%s",
                len(self.owned_bones),
                len(dependency_only),
                dependency_only,
            )
        self.structured = True
        if self._missing_optional_bones or self._missing_optional_tracks:
            _LOG.debug(
                "AnimGraph optional bindings unavailable and inactive: bones=%r tracks=%r",
                tuple(sorted(self._missing_optional_bones)),
                tuple(sorted(self._missing_optional_tracks)),
            )
        _LOG.debug(
            "Compiled branch-local AnimGraph preview: lod=%d performance_mode=%s blend_override=%d blend_additive=%d shared_meta=%d shared_meta_additive=%d trajectory_meta=%d dangles=%d drags=%d pose_ops=%d stack_transforms=%d stack_tracks=%d",
            self.host.settings.skeletal_lod,
            self.host.settings.performance_mode,
            len(program_handles(plan.root, kind="BLEND_OVERRIDE")),
            len(program_handles(plan.root, kind="BLEND_ADDITIVE")),
            len(program_handles(plan.root, kind="SHARED_META_POSE")),
            len(program_handles(plan.root, kind="SHARED_META_POSE_ADDITIVE")),
            len(program_handles(plan.root, kind="TRAJECTORY_FROM_META_POSE")),
            len(dangle_handles),
            len(drag_handles),
            len(self._pose_plans),
            len(self._stack_transform_names),
            len(self._stack_track_names),
        )
        if self._linear_program:
            _LOG.debug(
                "AnimGraph static command stream: commands=%d",
                len(self._linear_program),
            )
        if self._red_pose_bridge:
            _LOG.debug(
                "AnimGraph pose bridge: REDengine local pose -> Blender bone-space output"
            )

    def _compile(self, source_handles: tuple[str, ...]) -> None:
        if not self.host.has_graph:
            _LOG.warning(
                "Dangle preview has no bound AnimGraph tree; upstream pose evaluation is disabled"
            )
            self.bindings = [
                OperationBinding(handle, None, None, frozenset(), frozenset())
                for handle in source_handles
            ]
            return
        for raw_handle in source_handles:
            handle = normalized_source_handle(raw_handle)
            boundary = self._nodes.get(handle)
            if boundary is None:
                if handle and handle not in {"editor", "fallback"}:
                    raise ValueError(
                        f"AnimGraph operation source handle {handle!r} was not found in the bound graph"
                    )
                self.bindings.append(
                    OperationBinding(handle, None, None, frozenset(), frozenset())
                )
                continue
            try:
                plan = self.host.prepare_upstream_chain(boundary)
            except Exception as exc:
                raise ValueError(
                    f"AnimGraph chain before {handle or '<operation>'}: {exc}"
                ) from exc
            bones = frozenset(plan.required_bones) if plan is not None else frozenset()
            tracks = (
                frozenset(plan.requested_tracks) if plan is not None else frozenset()
            )
            self.required_bones.update(bones)
            self.required_tracks.update(tracks)
            self.bindings.append(
                OperationBinding(handle, boundary, plan, bones, tracks)
            )

    def evaluate_before_operation(self, operation_index: int) -> None:
        if not self.host.has_graph or not 0 <= operation_index < len(self.bindings):
            return
        binding = self.bindings[operation_index]
        if binding.plan is None:
            return
        plan = self.host.refresh_chain(binding.plan)
        execution = self.host.evaluate_chain(plan)
        self.host.prepare_output_bones(execution.written_bones)
        self._prepare_output_tracks(execution.written_tracks)
        bone_count, track_count = self.host.apply_chain(plan, execution)
        self.host.mark_output_bones(execution.written_bones)
        self._written_tracks.update(execution.written_tracks)
        if bone_count or track_count:
            self.host.sync_pose()

    def _resolved_source_pose(
        self, names: Iterable[str], rig_datas, field: str
    ) -> dict[str, Any]:
        names = tuple(str(name) for name in names)
        requested = set(names)
        source: dict[str, Any] = {}
        for rig_data in rig_datas:
            raw_names = tuple(getattr(rig_data, "bone_names", ()) or ())
            transforms = tuple(getattr(rig_data, field, ()) or ())
            if len(transforms) != len(raw_names):
                if field == "bone_transforms":
                    transforms = tuple(getattr(rig_data, "apose_ls", ()) or ())
                if len(transforms) != len(raw_names):
                    continue
            for raw_name, raw_transform in zip(raw_names, transforms):
                authored = merged_bone_name(str(raw_name or ""))
                resolved = self.host.resolve_bone(authored)
                if resolved is None:
                    continue
                if resolved in requested and resolved not in source:
                    source[resolved] = qs_transform_from_data(raw_transform)
        missing = [name for name in names if name not in source]
        if missing:
            raise KeyError(
                f"MetaRig source {field} is missing AnimGraph transform(s): "
                + ", ".join(missing[:8])
                + (" ..." if len(missing) > 8 else "")
            )
        return {name: source[name] for name in names}

    def drives_facial_session(self, session) -> bool:
        """Whether this preview solves the facial session itself, so the frame solver must skip it"""
        return bool(
            self.structured
            and self._facial_session is session
            and self.host.is_playing()
        )

    def _facial_root_bridge_names(self) -> tuple[str, ...]:
        cached = self._facial_root_bridge_bones
        if cached is not None:
            return cached
        if self._facial_binding is None:
            self._facial_root_bridge_bones = ()
            return ()
        _paths, rig_datas, scope = self._load_meta_rig_context(required=True)
        if scope is None or not 0 <= int(scope.owner_index) < len(rig_datas):
            self._facial_root_bridge_bones = ()
            return ()
        rig_data = rig_datas[int(scope.owner_index)]
        raw_source_names = getattr(rig_data, "bone_names", ())
        source_names = tuple(raw_source_names) if raw_source_names is not None else ()
        raw_parent_indices = getattr(rig_data, "parent_indices", ())
        parent_indices = (
            tuple(int(value) for value in raw_parent_indices)
            if raw_parent_indices is not None
            else ()
        )
        if not source_names or merged_bone_name(source_names[0]) != "Root":
            self._facial_root_bridge_bones = ()
            return ()
        physical_parents = self.host.physical_parent_map()
        root_name = self.host.resolve_bone("Root") or "Root"
        result = []
        for source_index in range(1, min(len(source_names), len(parent_indices))):
            if parent_indices[source_index] != 0:
                continue
            name = self.host.resolve_bone(merged_bone_name(source_names[source_index]))
            if name is None:
                continue
            merged_parent = str(physical_parents.get(name, "") or "")
            if merged_parent and merged_parent != root_name:
                result.append(name)
        self._facial_root_bridge_bones = tuple(result)
        if result:
            _LOG.debug(
                "Facial MetaRig skipped-parent compensation: transforms=%s",
                tuple(result),
            )
        return self._facial_root_bridge_bones

    def _facial_owner_context(self):
        if self._facial_binding is None:
            return None
        _paths, rig_datas, scope = self._load_meta_rig_context(required=True)
        if scope is None or not 0 <= int(scope.owner_index) < len(rig_datas):
            return None
        return rig_datas[int(scope.owner_index)]

    def _facial_owner_names(self) -> tuple[str, ...]:
        resolved = self._facial_owner_resolved_names
        if resolved is not None:
            return resolved
        rig_data = self._facial_owner_context()
        names = []
        if rig_data is not None:
            raw_source_names = getattr(rig_data, "bone_names", ())
            source_names = (
                tuple(raw_source_names) if raw_source_names is not None else ()
            )
            for raw_name in source_names:
                names.append(
                    self.host.resolve_bone(merged_bone_name(str(raw_name or ""))) or ""
                )
        resolved = tuple(names)
        self._facial_owner_resolved_names = resolved
        return resolved

    def _facial_owner_parent_map(
        self, physical_parents: Mapping[str, str]
    ) -> dict[str, str]:
        overrides = self._facial_owner_parent_overrides
        if overrides is None:
            rig_data = self._facial_owner_context()
            overrides = {}
            if rig_data is not None:
                resolved = self._facial_owner_names()
                raw_parent_indices = getattr(rig_data, "parent_indices", ())
                parent_indices = (
                    tuple(int(value) for value in raw_parent_indices)
                    if raw_parent_indices is not None
                    else ()
                )
                for index, name in enumerate(resolved):
                    if not name:
                        continue
                    parent_index = (
                        parent_indices[index] if index < len(parent_indices) else -1
                    )
                    parent_name = (
                        resolved[parent_index]
                        if 0 <= parent_index < len(resolved)
                        else ""
                    )
                    overrides[name] = parent_name
            self._facial_owner_parent_overrides = overrides
            mismatches = tuple(
                (name, str(physical_parents.get(name, "") or ""), parent)
                for name, parent in sorted(overrides.items())
                if str(physical_parents.get(name, "") or "") != parent
            )
            if mismatches:
                _LOG.debug(
                    "Facial graph owner-space hierarchy overrides: transforms=%s",
                    mismatches,
                )
        result = dict(physical_parents)
        result.update(overrides)
        return result

    def _facial_owner_reference_pose(
        self, base_reference: Mapping[str, Any]
    ) -> dict[str, Any]:
        overrides = self._facial_owner_reference_overrides
        if overrides is None:
            rig_data = self._facial_owner_context()
            overrides = {}
            if rig_data is not None:
                resolved = self._facial_owner_names()
                raw_transforms = getattr(rig_data, "bone_transforms", ())
                transforms = tuple(raw_transforms) if raw_transforms is not None else ()
                if len(resolved) != len(transforms):
                    raise ValueError("Facial owner rig reference pose is incomplete")
                for name, raw_transform in zip(resolved, transforms):
                    if name:
                        overrides[name] = qs_transform_from_data(raw_transform)
            self._facial_owner_reference_overrides = overrides
        result = dict(base_reference)
        result.update(overrides)
        return result

    def _facial_owner_reference_tracks(
        self, base_reference: Mapping[str, float]
    ) -> dict[str, float]:
        overrides = self._facial_owner_reference_track_overrides
        if overrides is None:
            overrides = {}
            binding = self._facial_binding
            if binding is not None:
                overrides = {
                    str(name): float(value)
                    for name, value in zip(binding.track_names, binding.track_defaults)
                    if str(name or "")
                }
            self._facial_owner_reference_track_overrides = overrides
        result = dict(base_reference)
        result.update(overrides)
        return result

    def _trace_facial_frame(self, stage: str, frame: BranchFrame) -> None:
        traced = self._facial_transform_trace_stages
        if stage in traced:
            return
        traced.add(stage)
        names = ("Spine2", "Spine3", "Neck", "Neck1", "Head")
        binding = self._facial_binding
        binding_names = tuple(getattr(binding, "bone_names", ()) or ())
        used_indices = tuple(getattr(binding, "used_bone_indices", ()) or ())
        sermo_used = frozenset(
            binding_names[index]
            for index in used_indices
            if 0 <= int(index) < len(binding_names)
        )
        model_cache: dict[str, Any] = {}
        rows = []
        for name in names:
            local = frame.pose.get(name)
            if local is None:
                continue
            try:
                model = model_transform(name, frame.pose, frame.parent_map, model_cache)
                model_t = tuple(round(float(value), 6) for value in model.translation)
            except (KeyError, ValueError):
                model_t = None
            reference = frame.reference_pose.get(name)
            rows.append(
                (
                    name,
                    str(frame.parent_map.get(name, "") or ""),
                    tuple(round(float(value), 6) for value in local.translation),
                    model_t,
                    tuple(round(float(value), 6) for value in reference.translation)
                    if reference is not None
                    else None,
                    name in sermo_used,
                )
            )
        _LOG.log(
            TRACE,
            "Facial transform trace: stage=%s fields=(bone,parent,local_t,model_t,reference_t,sermo_used) transforms=%s",
            stage,
            tuple(rows),
        )

    def _trace_facial_restore_basis(self, stage: str, frame: BranchFrame) -> None:
        traced = self._facial_transform_trace_stages
        if stage in traced:
            return
        traced.add(stage)
        rows = self.host.basis_translations(
            frame.pose,
            ("Spine2", "Spine3", "Neck", "Neck1", "Head"),
            self._red_pose_bridge,
        )
        _LOG.log(
            TRACE,
            "Facial transform trace: stage=%s fields=(bone,blender_basis_t) transforms=%s",
            stage,
            tuple(rows),
        )

    def _facial_graph_input_frame(self, meta_frame: BranchFrame) -> BranchFrame:
        if self._facial_binding is None or not self._owner_scope_bound:
            return meta_frame
        owner_names = frozenset(name for name in self._facial_owner_names() if name)
        owner_parents = self._facial_owner_parent_map(meta_frame.parent_map)
        owner_reference = self._facial_owner_reference_pose(meta_frame.reference_pose)
        owner_reference_tracks = self._facial_owner_reference_tracks(
            meta_frame.reference_tracks
        )
        pose = {
            name: owner_reference[name]
            for name in owner_names
            if name in owner_reference
        }
        tracks = {}
        owner_track_names = tuple(
            getattr(self._facial_binding, "track_names", ()) or ()
        )
        for name in owner_track_names:
            if not name:
                continue
            previous = meta_frame.tracks.get(
                name, TrackSnapshot(False, owner_reference_tracks.get(name, 0.0))
            )
            tracks[name] = TrackSnapshot(
                previous.existed, float(owner_reference_tracks.get(name, 0.0))
            )
        owner_parent_map = {
            name: (parent if parent in owner_names else "")
            for name in owner_names
            if (parent := str(owner_parents.get(name, "") or ""))
            or name in owner_parents
        }
        frame = BranchFrame(
            pose,
            tracks,
            owner_parent_map,
            {
                name: owner_reference[name]
                for name in owner_names
                if name in owner_reference
            },
            {
                name: float(owner_reference_tracks.get(name, 0.0))
                for name in owner_track_names
                if name
            },
            meta_frame.transform_scopes,
            meta_frame.track_scopes,
            False,
            ik_targets=meta_frame.ik_targets,
        )
        self._trace_facial_frame("owner_reference_input", frame)
        return frame

    def _facial_shared_parent_pose(self, meta_frame: BranchFrame) -> dict[str, Any]:
        binding = self._shared_meta_binding
        if binding is None:
            return {}
        bridges = frozenset(self._facial_root_bridge_names())
        model_cache: dict[str, Any] = {}
        result = {}
        for name in binding.transform_names:
            value = meta_frame.pose.get(name)
            if value is None:
                continue
            if name in bridges:
                value = model_transform(
                    name, meta_frame.pose, meta_frame.parent_map, model_cache
                )
            result[name] = value
        return result

    def _facial_part_frame_to_meta(
        self, frame: BranchFrame, meta_input: BranchFrame
    ) -> BranchFrame:
        if self._facial_binding is None or not self._owner_scope_bound:
            return frame
        physical_parents = meta_input.parent_map
        bridges = frozenset(self._facial_root_bridge_names())
        pose = dict(meta_input.pose)
        for name in self.owned_bones:
            if name in frame.pose:
                pose[name] = frame.pose[name]
        model_cache: dict[str, Any] = {}
        for name in bridges:
            model = frame.pose.get(name)
            if model is None:
                continue
            parent = str(physical_parents.get(name, "") or "")
            if not parent:
                pose[name] = model
                continue
            parent_model = model_transform(parent, pose, physical_parents, model_cache)
            pose[name] = relative_to(parent_model, model)
        return BranchFrame(
            pose,
            frame.tracks,
            physical_parents,
            meta_input.reference_pose,
            meta_input.reference_tracks,
            frame.transform_scopes,
            frame.track_scopes,
            frame.model_space,
            ik_targets=frame.ik_targets,
        )

    def _engine_reference_pose(self, names: Iterable[str]) -> dict[str, Any]:
        names = tuple(names)
        if self._meta_rig_datas:
            return self._resolved_source_pose(
                names, self._meta_rig_datas, "bone_transforms"
            )
        if self._facial_binding is not None:
            source = dict(
                zip(
                    self._facial_binding.bone_names, self._facial_binding.reference_pose
                )
            )
            missing = set(names) - source.keys()
            if missing:
                raise KeyError(
                    "Facial rig source pose is missing transforms: "
                    + ", ".join(sorted(missing))
                )
            return {name: source[name] for name in names}
        merged = self._meta_rig_merged_data
        if merged is None:
            raise ValueError(
                "REDengine AnimGraph pose bridge requires merged MetaRig source data"
            )
        return self._resolved_source_pose(names, (merged,), "bone_transforms")

    def _engine_bind_pose(self, names: Iterable[str]) -> dict[str, Any]:
        names = tuple(names)
        merged = self._meta_rig_merged_data
        if merged is not None:
            source = {}
            for raw_name, raw_transform in zip(
                getattr(merged, "bone_names", ()) or (),
                getattr(merged, "apose_ls", ()) or (),
            ):
                authored = merged_bone_name(str(raw_name or ""))
                resolved = self.host.resolve_bone(authored)
                if resolved is None:
                    continue
                source[resolved] = qs_transform_from_data(raw_transform)
            missing = [str(name) for name in names if str(name) not in source]
            if missing:
                raise KeyError(
                    "Merged MetaRig A-pose is missing AnimGraph transform(s): "
                    + ", ".join(missing[:8])
                    + (" ..." if len(missing) > 8 else "")
                )
            return {str(name): source[str(name)] for name in names}
        return self._engine_reference_pose(names)

    def _ensure_frame_pose_cache(self) -> None:
        names = self.host.frame_bone_names()
        if names == self._frame_cache_names:
            return
        blender_reference = self.host.reference_pose_ls(names)
        reference_pose = (
            self._engine_reference_pose(names)
            if self._red_pose_bridge
            else blender_reference
        )
        bind_pose = (
            self._engine_bind_pose(names)
            if self._red_pose_bridge
            else blender_reference
        )
        self._frame_cache_names = names
        self._reference_pose_ls = dict(reference_pose)
        self._bind_pose_ls = dict(bind_pose)
        distinct = self.host.bind_frame_pose(
            names, reference_pose, bind_pose, count_distinct=self._red_pose_bridge
        )
        if self._red_pose_bridge:
            _LOG.debug(
                "AnimGraph pose baselines: reference=boneTransforms bind=aPoseLS distinct=%d/%d",
                distinct,
                len(names),
            )

    def _reference_pose(self):
        self._ensure_frame_pose_cache()
        return self._reference_pose_ls

    def _reference_track_values(self) -> dict[str, float]:
        return {
            name: float(value)
            for name, value in self.host.reference_track_values(
                frozenset(str(name) for name in self.required_tracks)
            ).items()
        }

    def _capture_frame(self) -> BranchFrame:
        reference_pose = dict(self._reference_pose())
        self._ensure_frame_pose_cache()
        pose = self.host.capture_pose(
            (), use_input_basis=False, red_pose_bridge=self._red_pose_bridge
        )
        defaults = self._reference_track_values()
        tracks = self.host.capture_tracks(self.required_tracks)
        for name, snapshot in tuple(tracks.items()):
            if not snapshot.existed:
                tracks[name] = TrackSnapshot(False, float(defaults.get(name, 0.0)))
        return BranchFrame(
            pose,
            tracks,
            self.host.physical_parent_map(),
            reference_pose,
            defaults,
        )

    def _capture_input_frame(self) -> BranchFrame:
        reference_pose = dict(self._reference_pose())
        self._ensure_frame_pose_cache()
        capture_names = self._input_capture_bones
        pose = dict(reference_pose) if capture_names else {}
        pose.update(
            self.host.capture_pose(
                capture_names,
                use_input_basis=True,
                red_pose_bridge=self._red_pose_bridge,
            )
        )
        defaults = self._reference_track_values()
        tracks = {}
        for name in self.required_tracks:
            snapshot = self._input_tracks.get(name)
            if snapshot is not None and snapshot.existed:
                tracks[name] = snapshot
                continue
            captured = self.host.track_snapshot(name)
            tracks[name] = (
                captured
                if captured.existed
                else TrackSnapshot(False, float(defaults.get(name, 0.0)))
            )
        parent_map = self.host.physical_parent_map()
        bone_space = self._frames_in_bone_space()
        for name, (parent, reference) in self._extra_transforms.items():
            if name in pose:
                continue
            parent_map[name] = parent if parent in pose else ""
            if bone_space:
                # Authored as an engine transform; the frame holds the imported rig's bone space.
                reference = engine_value_to_frame(
                    reference, relative_to_parent=bool(parent_map[name])
                )
            pose[name] = reference
            reference_pose[name] = reference
        return BranchFrame(
            pose,
            tracks,
            parent_map,
            reference_pose,
            self._reference_track_values(),
        )

    def _execute_dangle_frame(
        self,
        config_index: int,
        child: BranchFrame,
        raw_dt: float,
        time_dilation: float,
        skip_physics: bool,
    ) -> BranchFrame:
        step = self.host.step_dangle_node(
            config_index, child, raw_dt, time_dilation, skip_physics
        )
        if not self.host.dangle_applied_names(step):
            return child
        if not child.model_space:
            self._ensure_frame_pose_cache()
        pose = self.host.dangle_output_pose(step, child)
        return BranchFrame(
            pose,
            child.tracks,
            child.parent_map,
            child.reference_pose,
            child.reference_tracks,
            child.transform_scopes,
            child.track_scopes,
            child.model_space,
            ik_targets=child.ik_targets,
        )

    def mark_blender_pose_dirty(self) -> None:
        self._blender_pose_dirty = True

    def _sync_blender_pose(self) -> None:
        started = perf_counter()
        self.host.sync_pose()
        self._perf_depsgraph_updates += 1
        self._perf_depsgraph_time += perf_counter() - started
        self._blender_pose_dirty = False

    def _capture_after_child(self, child: BranchFrame) -> BranchFrame:
        if child.model_space:
            raise ValueError(
                "Blender-backed AnimGraph operation cannot capture a model-space BranchFrame"
            )
        captured = self._capture_frame()
        physical_bones = set(captured.pose)
        physical_tracks = set(captured.tracks)
        pose = {
            name: value
            for name, value in child.pose.items()
            if name not in physical_bones
        }
        pose.update(captured.pose)
        tracks = {
            name: value
            for name, value in child.tracks.items()
            if name not in physical_tracks
        }
        tracks.update(captured.tracks)
        return BranchFrame(
            pose,
            tracks,
            child.parent_map,
            child.reference_pose,
            child.reference_tracks,
            child.transform_scopes,
            child.track_scopes,
            child.model_space,
            ik_targets=child.ik_targets,
        )

    def _semantic_dirty_bones(self, frame: BranchFrame) -> tuple[str, ...]:
        if self._owner_scope_bound:
            names = self._graph_output_bones()
        else:
            names = self._frame_cache_names or self.host.frame_bone_names()
        previous = self._last_graph_output_pose
        if not previous:
            return names
        dirty = []
        for name in names:
            current = frame.pose.get(name)
            if current != previous.get(name):
                dirty.append(name)
                continue
            if self.host.output_basis_changed(name):
                dirty.append(name)
        return tuple(dirty)

    def _restore_frame(
        self,
        frame: BranchFrame,
        *,
        bone_names: Iterable[str] | None = None,
        track_names: Iterable[str] | None = None,
        sync: bool = True,
    ) -> None:
        if bool(getattr(frame, "model_space", False)):
            raise ValueError(
                "AnimGraph output is still model-space; PoseMsToLs is required before Blender output"
            )
        self._perf_restore_calls += 1
        self._ensure_frame_pose_cache()
        self._trace_facial_restore_basis("blender_restore", frame)
        names = tuple(bone_names) if bone_names is not None else self._frame_cache_names
        writes = self.host.write_pose(frame.pose, names, self._red_pose_bridge)
        track_changes = {}
        allowed_tracks = (
            set(track_names) if track_names is not None else set(self.required_tracks)
        )
        for name, snapshot in frame.tracks.items():
            if name not in allowed_tracks:
                continue
            current = self.host.track_snapshot(name)
            if current.existed != snapshot.existed or current.value != snapshot.value:
                track_changes[name] = snapshot
        if track_changes:
            self.host.restore_tracks(track_changes)
            self._blender_pose_dirty = True
        self._perf_restore_writes += writes
        if writes:
            self._blender_pose_dirty = True
        if self._blender_pose_dirty:
            if sync:
                self._sync_blender_pose()
            else:
                self.host.tag_update()
                self._perf_deferred_final_syncs += 1

    def _reference_frame(self, input_frame: BranchFrame) -> BranchFrame:
        reference = dict(input_frame.reference_pose)
        defaults = dict(input_frame.reference_tracks)
        pose = dict(input_frame.pose)
        reset_bones = (
            set(reference)
            if self._facial_binding is not None and self._owner_scope_bound
            else self.owned_bones
            if self._owner_scope_bound
            else set(reference)
        )
        for name in reset_bones:
            if name in reference:
                pose[name] = reference[name]
        tracks = dict(input_frame.tracks)
        reset_tracks = (
            set(defaults)
            if self._facial_binding is not None and self._owner_scope_bound
            else self.owned_tracks
            if self._owner_scope_bound
            else set(defaults)
        )
        for name in reset_tracks:
            previous = tracks.get(name)
            existed = (
                previous.existed if previous is not None else self.host.has_track(name)
            )
            tracks[name] = TrackSnapshot(existed, float(defaults.get(name, 0.0)))
        return BranchFrame(
            pose,
            tracks,
            input_frame.parent_map,
            reference,
            defaults,
            input_frame.transform_scopes,
            input_frame.track_scopes,
        )

    def _pose_hierarchy_plan(self, frame: BranchFrame):
        key = (scope_signature(frame), tuple(frame.pose))
        plan = self._pose_hierarchy_plan_cache.get(key)
        if plan is None:
            plan = build_hierarchy_plan(tuple(frame.pose), frame.parent_map)
            self._pose_hierarchy_plan_cache[key] = plan
        return plan

    def _pose_ls_to_ms(self, frame: BranchFrame) -> BranchFrame:
        if frame.model_space:
            return frame
        pose = pose_ls_to_ms(
            frame.pose, frame.parent_map, self._pose_hierarchy_plan(frame)
        )
        return BranchFrame(
            pose,
            frame.tracks,
            frame.parent_map,
            frame.reference_pose,
            frame.reference_tracks,
            frame.transform_scopes,
            frame.track_scopes,
            True,
            ik_targets=frame.ik_targets,
        )

    def _pose_ms_to_ls(self, frame: BranchFrame) -> BranchFrame:
        if not frame.model_space:
            return frame
        pose = pose_ms_to_ls(
            frame.pose, frame.parent_map, self._pose_hierarchy_plan(frame)
        )
        return BranchFrame(
            pose,
            frame.tracks,
            frame.parent_map,
            frame.reference_pose,
            frame.reference_tracks,
            frame.transform_scopes,
            frame.track_scopes,
            False,
            ik_targets=frame.ik_targets,
        )

    def float_variable(self, name: str) -> float:
        return self.host.float_variable_value(name, self._rig_float_inputs)

    def _capture_float_variable_inputs(self):
        self._rig_float_inputs = {}
        for name in self._float_variable_names:
            value = self.host.rig_float_value(name)
            if value is not None:
                self._rig_float_inputs[name] = value

    def _consume_preview_external_events(self) -> frozenset[str]:
        return self.host.consume_external_events()

    # ValueInputs: what the graph's value nodes read from the preview.

    def external_events(self) -> frozenset[str]:
        return self._external_events_this_frame

    def wrapper_variables(self) -> frozenset[str]:
        """The anim wrapper variables set for this preview"""
        return self.host.preview_wrapper_variables()

    def anim_end_events(self) -> frozenset[str]:
        return frozenset(self._previous_anim_end_events)

    def data_flow(self) -> dict[str, float]:
        return self._data_flow

    def raw_dt(self) -> float:
        return self._current_raw_dt

    def graph_dt(self) -> float:
        return self._current_graph_dt

    def graph_variables(self):
        return self.host.graph_variables()

    def bool_variable(self, name: str) -> bool:
        """A declared Boolean graph variable's preview value, false when the graph declares none by that name"""
        for variable in self.host.graph_variables():
            if (
                str(getattr(variable, "name", "") or "") == name
                and str(getattr(variable, "var_type", "")) == "Bool"
            ):
                return bool(getattr(variable, "current_bool", False))
        return False

    def fired_anim_events(self) -> frozenset[str]:
        return frozenset(self._anim_events)

    def has_animation(self, name: str) -> bool:
        return name in self._available_animations

    def world_to_model(
        self, vector, *, direction: bool = False
    ) -> tuple[float, float, float]:
        return tuple(self.host.world_vector_to_model(vector, direction=direction))

    def vector_input(self, group: str, name: str):
        """A VectorInput's value"""
        value = (
            self.feature_values().get((group, name))
            if (group, name) in self._internal_graph_inputs
            else None
        )
        if value is None:
            supplied = self.host.preview_vector_input(group, name)
            if supplied is not None:
                value = vector3_from_data(supplied)
        if value is None:
            value = vector3_from_data(self.feature_values().get((group, name)))
        return value

    def feature_values(self) -> dict[tuple[str, str], Any]:
        if self._preview_feature_cache is not None:
            return self._preview_feature_cache
        raw = self.host.preview_features_json().strip()
        if not raw:
            self._preview_feature_cache = dict(self._internal_graph_inputs)
            return self._preview_feature_cache
        try:
            value = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"AnimGraph preview feature JSON is invalid: {exc}"
            ) from exc
        if not isinstance(value, Mapping):
            raise ValueError("AnimGraph preview feature JSON must be an object")
        result: dict[tuple[str, str], Any] = {}
        for feature, properties in value.items():
            if isinstance(properties, Mapping):
                for property_name, property_value in properties.items():
                    result[(str(feature), str(property_name))] = property_value
                continue
            text = str(feature)
            if "/" in text:
                feature_name, property_name = text.split("/", 1)
                result[(feature_name, property_name)] = properties
        result.update(self._internal_graph_inputs)
        self._preview_feature_cache = result
        return result

    def _branch_reachable_source_handles(self, program_node) -> frozenset[str]:
        pending = [
            normalized_source_handle(handle) for handle in program_handles(program_node)
        ]
        seen = set()
        while pending:
            handle = pending.pop()
            if not handle or handle in seen:
                continue
            seen.add(handle)
            node = self._source_index.get(handle)
            if not isinstance(node, Mapping):
                continue
            stack = list(node.values())
            while stack:
                value = stack.pop()
                if isinstance(value, Mapping):
                    reference = normalized_source_handle(reference_handle(value))
                    if reference and reference not in seen:
                        pending.append(reference)
                        continue
                    stack.extend(value.values())
                elif isinstance(value, (list, tuple)):
                    stack.extend(value)
        return frozenset(seen)

    def _source_anim_sync_clip(self, program_node):
        data = program_node.data
        animation = str(data.get("animation", "") or "")
        clip = self.host.clip(animation) if animation else None
        if clip is None:
            return None
        frame_start, frame_end, clip_front, clip_end = self._source_action_clip(
            clip, data
        )
        duration = (float(frame_end) - float(frame_start)) / float(FPS)
        handle = normalized_source_handle(program_node.handle)
        return (
            handle,
            duration,
            float(self._source_anim_times.get(handle, clip_front)),
            clip_end,
        )

    def _gather_sync_entries(self, program_node, weight: float, entries: list) -> None:
        """Collect clip progress below a pose input"""
        selections = self._switch_selected
        blends = self._switch_blends
        actives = self._switch_active
        pending = [(program_node, float(weight))]
        while pending:
            node, node_weight = pending.pop()
            if (
                node.kind == "SK_ANIM"
                and node.children
                and not self._one_shot_is_running(node)
            ):
                pending.append((node.children[0], node_weight))
            elif node.kind == "SK_ANIM":
                clip = self._source_anim_sync_clip(node)
                if clip is not None:
                    _handle, duration, current, _clip_end = clip
                    entries.append(
                        SyncEntry(
                            duration,
                            current,
                            node_weight,
                            str(node.data.get("animation", "") or ""),
                        )
                    )
            elif node.kind == "SWITCH":
                handle = normalized_source_handle(node.handle)
                for index, input_weight in reversed(
                    switch_state_weights(
                        float(node.data.get("blendTime", 0.0)),
                        selections.get(handle),
                        blends.get(handle),
                        actives.get(handle, frozenset()),
                    )
                ):
                    pending.append((node.children[index], node_weight * input_weight))
            elif node.kind == "BLEND_MULTIPLE":
                first, second, alpha = self._blend_multiple_selection.get(
                    normalized_source_handle(node.handle),
                    (-1, -1, 0.0),
                )
                for index, input_weight in ((second, alpha), (first, 1.0 - alpha)):
                    if 0 <= index < len(node.children) and input_weight > 0.0:
                        pending.append(
                            (node.children[index], node_weight * input_weight)
                        )
            elif node.kind == "BLEND_ADDITIVE" and node.children:
                # Only the base input carries progress.
                pending.append((node.children[0], node_weight))
            elif node.kind == "BLEND_TWO":
                handle = normalized_source_handle(node.handle)
                weight_two = self._blend_two_weight.get(handle, 0.0)
                for index in sorted(
                    self._blend_two_active.get(handle, frozenset()), reverse=True
                ):
                    share = weight_two if index == 1 else 1.0 - weight_two
                    if index < len(node.children) and share > 0.0:
                        pending.append((node.children[index], node_weight * share))
            elif len(node.children) == 1:
                pending.append((node.children[0], node_weight))

    def _foot_phase_track(
        self, animation: str, duration: float
    ) -> FootPhaseTrack | None:
        cache = self._foot_phase_tracks
        key = (animation, round(float(duration), 6))
        if key not in cache:
            clip = self.host.clip(animation) if animation else None
            phases = []
            raw_events = self.host.clip_events(clip) if clip is not None else None
            if raw_events is not None:
                try:
                    events = event_array(raw_events, clip.name)
                except ValueError:
                    events = ()
                frame_start = clip.frame_start
                for event in events:
                    if (
                        isinstance(event, Mapping)
                        and str(event.get("type", "") or "") == "FootPhase"
                    ):
                        phases.append(
                            (
                                str(event.get("footPhase", "") or ""),
                                (
                                    float(
                                        event.get("startFrame", frame_start)
                                        or frame_start
                                    )
                                    - frame_start
                                )
                                / float(FPS),
                                max(
                                    0.0,
                                    float(event.get("durationInFrames", 0.0) or 0.0),
                                )
                                / float(FPS),
                            )
                        )
            synchronizer = FootPhaseTrack(duration, phases)
            cache[key] = synchronizer if synchronizer.ok else None
        return cache[key]

    def _sync_branch(self, program_node, progress) -> None:
        """Retime a freshly activated input to the gathered progress"""
        selections = self._switch_selected
        blends = self._switch_blends
        actives = self._switch_active
        pending = [program_node]
        while pending:
            node = pending.pop()
            if (
                node.kind == "SK_ANIM"
                and node.children
                and not self._one_shot_is_running(node)
            ):
                pending.append(node.children[0])
            elif node.kind == "SK_ANIM":
                if node.node_type == "animAnimNode_SkFrameAnim":
                    continue
                clip = self._source_anim_sync_clip(node)
                if clip is None:
                    continue
                handle, duration, current, clip_end = clip
                clip_progress = progress
                if isinstance(progress, tuple):
                    # By foot phase: the time at the source clip's phase progress in this clip's matching phase.
                    source = progress[1]
                    target_time = foot_phase_synced_time(
                        self._foot_phase_track(source.animation, source.duration)
                        if source is not None
                        else None,
                        source.current_time if source is not None else 0.0,
                        self._foot_phase_track(
                            str(node.data.get("animation", "") or ""), duration
                        ),
                    )
                    clip_progress = target_time / duration if duration > 0.0 else 0.0
                synced = synced_clip_time(
                    clip_progress,
                    duration,
                    current,
                    clip_end=clip_end,
                    looped=bool(node.data.get("isLooped", False)),
                )
                if synced is not None:
                    self._source_anim_times[handle] = synced
            elif node.kind == "SWITCH":
                handle = normalized_source_handle(node.handle)
                active = actives.get(handle, frozenset())
                if active:
                    indices = [
                        index
                        for index, _weight in switch_state_weights(
                            float(node.data.get("blendTime", 0.0)),
                            selections.get(handle),
                            blends.get(handle),
                            active,
                        )
                    ]
                else:
                    count = min(
                        int(node.data.get("numInputs", len(node.children)) or 0),
                        len(node.children),
                    )
                    weight = (
                        self.values.linked("float", handle, "weightNode", 0.0)
                        if node.data.get("hasWeightNode")
                        else 0.0
                    )
                    selected = selected_input_index(weight, count)
                    indices = [selected] if selected >= 0 else []
                    if selected >= 0:
                        selections[handle] = selected
                        blends.pop(handle, None)
                        actives[handle] = frozenset(indices)
                pending.extend(node.children[index] for index in indices)
            elif node.kind == "BLEND_MULTIPLE":
                first, second, alpha = self._blend_multiple_selection.get(
                    normalized_source_handle(node.handle),
                    (-1, -1, 0.0),
                )
                pending.extend(
                    node.children[index]
                    for index, enabled in ((first, alpha < 1.0), (second, alpha > 0.0))
                    if enabled and 0 <= index < len(node.children)
                )
            elif node.kind == "BLEND_ADDITIVE" and node.children:
                # The base input is synced, and the added input while it plays.
                handle = normalized_source_handle(node.handle)
                pending.append(node.children[0])
                active = self._additive_active.get(handle)
                if active is None:
                    # Just reset with its branch: whether the added input plays is decided now, as on activation,
                    # so its own execution finds it active and does not reset the retimed clips.
                    data = self._additive_data.get(handle, {})
                    weight = final_additive_weight(
                        self._additive_control(handle, data),
                        data.get("biasValue", 0.0),
                        data.get("scaleValue", 1.0),
                    )
                    active = self._additive_active[handle] = additive_branch_active(
                        weight
                    )
                if active and len(node.children) > 1:
                    pending.append(node.children[1])
            elif node.kind == "BLEND_TWO":
                handle = normalized_source_handle(node.handle)
                active = self._blend_two_active.get(handle)
                if active is None:
                    # A Blend2 reached here was just reset with its branch: it is given its inputs now, so its own
                    # execution finds them active and does not reset the retimed clips.
                    minimum, maximum = (
                        float(node.data["minInputValue"]),
                        float(node.data["maxInputValue"]),
                    )
                    value = self.values.linked("float", handle, "weightNode", minimum)
                    weight = blend_two_weight(value, minimum, maximum)
                    active = self._blend_two_active[handle] = blend_two_inputs(weight)
                    self._blend_two_weight[handle] = weight
                pending.extend(
                    node.children[index]
                    for index in sorted(active)
                    if index < len(node.children)
                )
            elif len(node.children) == 1:
                pending.append(node.children[0])

    def _additive_control(self, handle: str, data: Mapping[str, Any]) -> float:
        """A BlendAdditive's control value"""
        if str(data.get("previousFrameWeightTrack", "") or ""):
            default = data.get("previousFrameWeightDefault", 0.0) or 0.0
            return float(self._additive_previous_track_values.get(handle, default))
        return (
            self.values.linked("float", handle, "weightNode", 0.0)
            if data.get("hasWeightNode")
            else 0.0
        )

    def _rig_part_mask(
        self, name: str
    ) -> tuple[dict[str, float], frozenset[str]] | None:
        """Bone weights and model-space-rotation bones of a rig part, or None when unknown"""
        cache = self._rig_part_cache
        if cache is None:
            masks = self.host.rig_part_masks()
            rotation = self.host.rig_part_rotation_ms()
            cache = self._rig_part_cache = {
                part: (weights, frozenset(rotation.get(part, ())))
                for part, weights in masks.items()
            }
        return cache.get(str(name or ""))

    def _require_rig_part_bones(self, name: str) -> None:
        part = self._rig_part_mask(name)
        if part is None:
            return
        for bone in part[0]:
            resolved = self.host.resolve_bone(bone)
            if resolved is not None:
                self.required_bones.add(resolved)

    def _request_inertialization(self, duration: float) -> None:
        frame, previous = self._inertialization_request
        if frame == self._perf_frames:
            duration = max(float(duration), previous)
        self._inertialization_request = (self._perf_frames, float(duration))

    def _reset_branch_activation(self, program_node) -> None:
        for raw_handle in program_handles(program_node, kind="SK_ANIM"):
            handle = normalized_source_handle(raw_handle)
            self._source_anim_times.pop(handle, None)
            self._source_anim_advanced_frame.pop(handle, None)
            self._one_shot_running.pop(handle, None)
        for raw_handle in program_handles(program_node, kind="POSE_OP"):
            handle = normalized_source_handle(raw_handle)
            source = self._source_index.get(handle, {})
            node_type = (
                str(source.get("$type", "") or "")
                if isinstance(source, Mapping)
                else ""
            )
            if node_type == "animAnimNode_RotateBone" and bool(
                source.get("resetOnActivation", True)
            ):
                self._rotate_angles.pop(handle, None)
            elif node_type == "animAnimNode_RotateBoneByQuaternion" and bool(
                source.get("resetOnActivation", True)
            ):
                self._quaternion_rotations.pop(handle, None)
            elif node_type == "animAnimNode_TranslateBone" and bool(
                source.get("resetOnActivation", True)
            ):
                self._translation_values.pop(handle, None)
            elif node_type == "animAnimNode_AdditionalFloatTrack":
                self._additional_track_times.pop(handle, None)
        for handle in self._branch_reachable_source_handles(program_node):
            source = self._source_index.get(handle)
            if isinstance(source, Mapping):
                self.values.reset_node(handle, source)
        for raw_handle in program_handles(program_node, kind="LOOK_AT_CONTROLLER"):
            state = self._look_at_states.get(normalized_source_handle(raw_handle))
            if state is not None:
                state.clear()
                values = inactive_graph_inputs(
                    self._look_at_data.get(normalized_source_handle(raw_handle), {})
                )
                self._internal_graph_inputs.update(values)
                if self._preview_feature_cache is not None:
                    self._preview_feature_cache.update(values)
                self.values.invalidate("vector", "float")
        for raw_handle in program_handles(program_node, kind="FACIAL_MIXER"):
            state = self._facial_mixer_states.get(normalized_source_handle(raw_handle))
            if state is not None:
                state.clear()
        for raw_handle in program_handles(program_node, kind="BLEND_ADDITIVE"):
            self._additive_active.pop(normalized_source_handle(raw_handle), None)
        for raw_handle in program_handles(program_node, kind="BLEND_TWO"):
            self._blend_two_active.pop(normalized_source_handle(raw_handle), None)
            self._blend_two_weight.pop(normalized_source_handle(raw_handle), None)
            self._time_warp_progress.pop(normalized_source_handle(raw_handle), None)
        for raw_handle in program_handles(program_node, kind="BLEND_MASK_DYNAMIC"):
            self._mask_blend_active.pop(normalized_source_handle(raw_handle), None)
        for raw_handle in program_handles(program_node, kind="BLEND_MULTIPLE"):
            self._blend_multiple_active.pop(normalized_source_handle(raw_handle), None)
            self._time_warp_progress.pop(normalized_source_handle(raw_handle), None)
        for raw_handle in program_handles(program_node, kind="INERTIALIZATION"):
            self._inertialization_states.pop(normalized_source_handle(raw_handle), None)
        for raw_handle in program_handles(program_node, kind="SWITCH"):
            switch_handle = normalized_source_handle(raw_handle)
            self._switch_selected.pop(switch_handle, None)
            self._switch_blends.pop(switch_handle, None)
            self._switch_active.pop(switch_handle, None)
            self._time_warp_progress.pop(switch_handle, None)
        drag_handles = program_handles(program_node, kind="DRAG")
        for handle in drag_handles:
            config_index = self._drag_config_by_handle.get(
                normalized_source_handle(handle)
            )
            if config_index is None:
                continue
            runtime_index = self.host.drag_runtime_index(config_index)
            if runtime_index is not None:
                self.host.reset_drag(runtime_index)

    def _reference_model_pose(self, frame: BranchFrame) -> dict[str, Any]:
        key = (
            scope_signature(frame),
            isinstance(frame.reference_pose, EngineSpacePose),
            tuple(frame.reference_pose),
        )
        cached = self._reference_model_cache.get(key)
        if cached is not None:
            return cached
        cache = {}
        for name in frame.reference_pose:
            model_transform(name, frame.reference_pose, frame.parent_map, cache)
        self._reference_model_cache[key] = cache
        return cache

    def _frames_in_bone_space(self) -> bool:
        """True when frames hold the imported rig's Blender bone-local transforms rather than engine ones"""
        return (
            not self._red_pose_bridge
            and self.host.rig_space_contract() == RIG_SPACE_CONTRACT_CURRENT
        )

    def _execute_pure_pose_op(
        self, program_node, child: BranchFrame, *, copy_frame: bool = True
    ) -> BranchFrame:
        if (
            program_node.node_type not in ENGINE_SPACE_POSE_OPS
            or not self._frames_in_bone_space()
        ):
            return self._evaluate_pure_pose_op(
                program_node, child, copy_frame=copy_frame
            )
        # The frame keeps the imported rig's bone space; the operation sees and writes engine
        # transforms (pose and reference), converted through the rig space contract.
        pose = dict(child.pose) if copy_frame else child.pose
        tracks = dict(child.tracks) if copy_frame else child.tracks
        view = EngineSpacePose(pose, child.parent_map, model_space=child.model_space)
        engine_child = replace(
            child,
            pose=view,
            tracks=tracks,
            reference_pose=EngineSpacePose(child.reference_pose, child.parent_map),
        )
        result = self._evaluate_pure_pose_op(
            program_node, engine_child, copy_frame=False
        )
        view.commit()
        return replace(result, pose=pose, reference_pose=child.reference_pose)

    def _evaluate_pure_pose_op(
        self, program_node, child: BranchFrame, *, copy_frame: bool = True
    ) -> BranchFrame:
        handle = normalized_source_handle(program_node.handle)
        data = self._pose_plans[handle]
        pose = dict(child.pose) if copy_frame else child.pose
        tracks = dict(child.tracks) if copy_frame else child.tracks
        node_type = program_node.node_type
        ik_targets = child.ik_targets
        track_values = (
            {name: snap.value for name, snap in tracks.items()}
            if bool(data.get("_usesTracks", True))
            else {}
        )
        handler = POSE_OP_HANDLERS.get(node_type)
        if handler is None:
            raise ValueError(f"unsupported pure pose operation {node_type}")
        op = PoseOpState(
            program_node,
            handle,
            node_type,
            data,
            child,
            pose,
            tracks,
            track_values,
            ik_targets,
        )
        evaluation = handler.evaluate(self, op)
        if isinstance(evaluation, BranchFrame):
            return evaluation
        tracks, track_values, ik_targets = op.tracks, op.track_values, op.ik_targets
        if not evaluation.applied:
            reason = str(getattr(evaluation, "reason", "") or "")
            weight = getattr(evaluation, "weight", None)
            if weight is None:
                weight = getattr(evaluation, "constraint_weight", None)
            if reason == "nonpositive weight" or (
                reason == "" and weight is not None and not (float(weight) > 0.0)
            ):
                return child
            if (
                "absent from the pose" in reason
                or "has no valid parent" in reason
                or "target track is absent" in reason
            ):
                return child
            if node_type == "animAnimNode_TwistConstraint" and not (
                getattr(evaluation, "transforms_written", ())
                or getattr(evaluation, "tracks_written", ())
            ):
                return child
            raise ValueError(
                f"{node_type} {handle or program_node.path}: {reason or 'operation was not applied'}"
            )
        for name in getattr(evaluation, "tracks_written", ()):
            prior = tracks.get(name, TrackSnapshot(False, 0.0))
            exists = (
                prior.existed
                or name in self._stack_track_names
                or node_type == "animAnimNode_AdditionalFloatTrack"
            )
            tracks[name] = TrackSnapshot(exists, float(track_values[name]))
        if not copy_frame:
            return (
                child
                if ik_targets is child.ik_targets
                else replace(child, ik_targets=ik_targets)
            )
        return BranchFrame(
            pose,
            tracks,
            child.parent_map,
            child.reference_pose,
            child.reference_tracks,
            child.transform_scopes,
            child.track_scopes,
            child.model_space,
            ik_targets=ik_targets,
        )

    def _execute_stack_node(
        self, program_node, child: BranchFrame, *, copy_frame: bool = True
    ) -> BranchFrame:
        handle = normalized_source_handle(program_node.handle)
        data = self._stack_data_by_handle[handle]
        pose = dict(child.pose) if copy_frame else child.pose
        tracks = dict(child.tracks) if copy_frame else child.tracks
        parents = dict(child.parent_map) if copy_frame else child.parent_map
        reference_pose = (
            dict(child.reference_pose) if copy_frame else child.reference_pose
        )
        reference_tracks = (
            dict(child.reference_tracks) if copy_frame else child.reference_tracks
        )
        transform_scopes = child.transform_scopes
        track_scopes = child.track_scopes
        kind = program_node.kind
        if kind == "STACK_TRANSFORMS_EXTEND":
            if self._frames_in_bone_space():
                # Stack transforms are authored, snapped and offset as engine transforms.
                pose_view = EngineSpacePose(
                    pose, parents, model_space=child.model_space
                )
                reference_view = EngineSpacePose(reference_pose, parents)
                transform_scopes, evaluation = extend_transforms(
                    pose_view,
                    parents,
                    reference_view,
                    transform_scopes,
                    data,
                    model_space=child.model_space,
                )
                pose_view.commit()
                reference_view.commit()
            else:
                transform_scopes, evaluation = extend_transforms(
                    pose,
                    parents,
                    reference_pose,
                    transform_scopes,
                    data,
                    model_space=child.model_space,
                )
        elif kind == "STACK_TRANSFORMS_SHRINK":
            transform_scopes, evaluation = shrink_transforms(
                pose, parents, reference_pose, transform_scopes, data
            )
        elif kind == "STACK_TRACKS_EXTEND":
            values = {name: snap.value for name, snap in tracks.items()}
            track_scopes, evaluation = extend_tracks(
                values, reference_tracks, track_scopes, data
            )
            for name, value in values.items():
                previous = tracks.get(name)
                tracks[name] = TrackSnapshot(
                    previous.existed if previous is not None else True, float(value)
                )
        elif kind == "STACK_TRACKS_SHRINK":
            values = {name: snap.value for name, snap in tracks.items()}
            track_scopes, evaluation = shrink_tracks(
                values, reference_tracks, track_scopes, data
            )
            removed = set(evaluation.names) if evaluation.applied else set()
            for name in removed:
                tracks.pop(name, None)
        else:
            raise ValueError(f"unsupported stack operation {kind}")
        if not evaluation.applied:
            raise ValueError(
                f"{program_node.node_type} {handle or program_node.path}: {evaluation.reason}"
            )
        return BranchFrame(
            pose,
            tracks,
            parents,
            reference_pose,
            reference_tracks,
            tuple(transform_scopes),
            tuple(track_scopes),
            child.model_space,
            ik_targets=child.ik_targets,
        )

    def _execute_shared_meta_frame(
        self,
        program_node,
        child: BranchFrame,
        input_frame: BranchFrame,
        *,
        additive: bool,
        copy_frame: bool = True,
    ) -> BranchFrame:
        node_name = "SharedMetaPoseAdditive" if additive else "SharedMetaPose"
        if child.model_space:
            raise ValueError(f"{node_name} preview requires local-space input")
        binding = self._shared_meta_binding
        if binding is None:
            raise ValueError(f"{node_name} has no bound parent-pose context")
        handle = normalized_source_handle(program_node.handle)
        data = program_node.data
        weight = (
            self.values.linked("float", handle, "weightLink", 1.0)
            if data.get("hasWeightNode")
            else 1.0
        )
        pose = dict(child.pose) if copy_frame else child.pose
        tracks = dict(child.tracks) if copy_frame else child.tracks
        track_values = {name: snap.value for name, snap in tracks.items()}
        parent_frame = self._meta_parent_frame_current or input_frame
        parent_pose = (
            self._facial_shared_parent_pose(parent_frame)
            if self._facial_binding is not None and self._owner_scope_bound
            else parent_frame.pose
        )
        parent_tracks = {name: snap.value for name, snap in parent_frame.tracks.items()}
        if additive:
            parent_reference_pose = (
                self._engine_bind_pose(binding.transform_names)
                if binding.transform_names
                else {}
            )
            evaluation = evaluate_shared_meta_pose_additive(
                pose,
                track_values,
                parent_pose,
                parent_tracks,
                parent_reference_pose,
                parent_frame.reference_tracks,
                binding.transform_names,
                binding.track_names,
                weight=weight,
                additive_type=data.get("additiveType", "AGAT_Local"),
                blend_tracks=data.get("blendTracks", "AGBT_Add"),
                convert_parent_pose_to_additive=bool(
                    data.get("convertParentPoseToAdditive", True)
                ),
            )
        else:
            evaluation = evaluate_shared_meta_pose(
                pose,
                track_values,
                parent_pose,
                parent_tracks,
                binding.transform_names,
                binding.track_names,
                weight,
            )
        for name in evaluation.tracks_written:
            before = tracks.get(name, TrackSnapshot(False, 0.0))
            parent = parent_frame.tracks.get(name, TrackSnapshot(False, 0.0))
            tracks[name] = TrackSnapshot(
                before.existed or parent.existed, float(track_values[name])
            )
        result = BranchFrame(
            pose,
            tracks,
            child.parent_map,
            child.reference_pose,
            child.reference_tracks,
            child.transform_scopes,
            child.track_scopes,
            child.model_space,
            ik_targets=child.ik_targets,
        )
        if not additive:
            self._trace_facial_frame("shared_meta_output", result)
        return result

    def _execute_trajectory_from_meta_pose_frame(
        self,
        program_node,
        child: BranchFrame,
        input_frame: BranchFrame,
        *,
        copy_frame: bool = True,
    ) -> BranchFrame:
        if child.model_space:
            raise ValueError("TrajectoryFromMetaPose requires local-space input")
        handle = normalized_source_handle(program_node.handle)
        data = self._trajectory_meta_data.get(handle, {})
        target = str(data.get("target", "") or "")
        if not target or target not in child.pose:
            return child
        source = str(data.get("source", "") or "")
        parent_frame = self._meta_parent_frame_current or input_frame
        trajectory = parent_frame.pose.get(source)
        if trajectory is None:
            trajectory = child.reference_pose.get(target)
        if trajectory is None:
            return child
        predictive = tuple(data.get("predictiveTracks", ()) or ())
        if len(predictive) == 3:
            values = {
                canonical: float(input_frame.tracks[name].value)
                for canonical, name in zip(PREDICTIVE_LOOK_AT_TRACKS, predictive)
                if name in input_frame.tracks
            }
            trajectory = apply_predictive_look_at_rotation(trajectory, values)
        pose = dict(child.pose) if copy_frame else child.pose
        pose[target] = trajectory
        return BranchFrame(
            pose,
            child.tracks,
            child.parent_map,
            child.reference_pose,
            child.reference_tracks,
            child.transform_scopes,
            child.track_scopes,
            child.model_space,
            ik_targets=child.ik_targets,
        )

    def _sync_look_at_request(self, handle, state, data):
        controls = self.host.look_at_controls()
        active = controls.enabled
        part = controls.part
        configured = {
            str(item.get("partName", ""))
            for item in data.get("stateMachinesSettings", ())
        }
        configured.update(
            str(item.get("partAlias", ""))
            for item in data.get("stateMachinesSettings", ())
        )
        key = "preview"
        previous = state.service_requests.get(key)
        if active and part not in configured:
            available = {
                str(item.get(key, ""))
                for value in self._look_at_data.values()
                for item in value.get("stateMachinesSettings", ())
                for key in ("partName", "partAlias")
            }
            if part not in available:
                raise ValueError(
                    f"Look-at body part {part!r} is not present in this graph"
                )
        if active and part in configured:
            target = self.host.look_at_target()
            speed = controls.speed
            request = LookAtRequest(part, target, speed, speed)
            state.service_requests[key] = request
            changed = previous is None or previous.part != part
        else:
            changed = previous is not None
            state.service_requests.pop(key, None)
        if changed:
            for mixer in self._facial_mixer_states.values():
                mixer.notify_look_at()

    def _advance_facial_mixer_frame(self, state, data, frame, dt):
        def duration(name):
            clip = self.host.clip(name)
            if clip is None:
                missing = self._missing_blink_animations
                if name not in missing:
                    missing.add(name)
                    _LOG.warning("Look-at blink animation unavailable: %s", name)
                return 0.0
            return max(0.0, (clip.frame_end - clip.frame_start) / float(FPS))

        def sample(name, seconds):
            clip = self.host.clip(name)
            if clip is None:
                return {}
            return self.host.sample_clip(clip, clip.frame_start + seconds * float(FPS))[
                1
            ]

        features = self.feature_values()
        values = advance_mixer(
            state,
            dt,
            data=data,
            tracks={
                name: float(snapshot.value) for name, snapshot in frame.tracks.items()
            },
            transition_duration=float(
                features.get(("lookAt", "lookAtTransitionDuration"), 0.0)
            ),
            transition_pitch=float(
                features.get(("lookAt", "lookAtTransitionPitch"), 0.0)
            ),
            animation_duration=duration,
            sample_tracks=sample,
        )
        written = {
            name: value
            for name, value in values.items()
            if value != frame.tracks[name].value
        }
        if not written:
            return frame
        result = replace(frame, tracks=dict(frame.tracks))
        for name, value in written.items():
            result.tracks[name] = TrackSnapshot(frame.tracks[name].existed, value)
        return result

    def _source_action_clip(
        self, clip, data: Mapping[str, Any]
    ) -> tuple[float, float, float, float]:
        frame_start = clip.frame_start
        frame_end = clip.frame_end
        clip_front = float(data.get("clipFront", 0.0) or 0.0)
        clip_end = float(data.get("clipEnd", 0.0) or 0.0)
        phase = str(data.get("phase", "") or "")
        if phase and phase != "None":
            raw_events = self.host.clip_events(clip)
            if raw_events is not None:
                try:
                    events = event_array(raw_events, clip.name)
                except ValueError:
                    events = ()
                for event in events:
                    if not isinstance(event, Mapping):
                        continue
                    if str(event.get("type", "") or "") != "Phase":
                        continue
                    if str(event.get("eventName", "") or "") != phase:
                        continue
                    start = float(event.get("startFrame", frame_start) or frame_start)
                    duration = max(
                        0.0, float(event.get("durationInFrames", 0.0) or 0.0)
                    )
                    end = min(frame_end, start + duration)
                    clip_front += max(0.0, (start - frame_start) / float(FPS))
                    clip_end += max(0.0, (frame_end - end) / float(FPS))
                    break
        return frame_start, frame_end, clip_front, clip_end

    def _clip_event_list(self, clip) -> tuple[Mapping[str, Any], ...]:
        events = self._clip_events.get(clip.name)
        if events is None:
            raw_events = self.host.clip_events(clip)
            try:
                events = (
                    tuple(
                        event
                        for event in event_array(raw_events, clip.name)
                        if isinstance(event, Mapping)
                    )
                    if raw_events is not None
                    else ()
                )
            except ValueError:
                events = ()
            self._clip_events[clip.name] = events
        return events

    def _emit_source_anim_end(self, data: Mapping[str, Any]) -> None:
        self._anim_end_events.add("At least one animation ended")
        event_name = str(data.get("animLoopEventName", "") or "")
        if (
            bool(data.get("fireAnimLoopEvent", False))
            and event_name
            and event_name != "None"
        ):
            self._anim_end_events.add(event_name)

    def _sampled_action_frame(
        self,
        handle,
        animation,
        clip,
        data,
        sample_frame,
        first_sample_frame,
        input_frame,
    ) -> BranchFrame:
        """An action's pose and tracks at sample_frame over input_frame's reference and layout"""
        bone_components, sampled_tracks = self.host.sample_clip(clip, sample_frame)
        action_type = clip.animation_type
        action_is_additive = is_additive_animation_type(action_type)
        storage_mode = self.host.additive_storage_mode() if action_is_additive else ""
        pose = reference_or_identity_pose(
            input_frame.reference_pose, additive=action_is_additive
        )
        for name, values in bone_components.items():
            reference = input_frame.reference_pose.get(name)
            if reference is None:
                continue
            sampled = self.host.clip_basis(values, self._red_pose_bridge)
            if (
                action_is_additive
                and storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED
            ):
                bind = self._bind_pose_ls.get(name)
                if bind is None:
                    raise KeyError(
                        f"Bind pose is missing additive source transform {name!r}"
                    )
                pose[name] = recover_reference_applied_transform(
                    reference, bind, sampled
                )
            else:
                pose[name] = sampled_animation_transform(
                    reference, sampled, action_type
                )

        seeded_tracks = sampled_animation_track_seed(
            {name: snapshot.value for name, snapshot in input_frame.tracks.items()},
            action_type,
        )
        tracks = {
            name: TrackSnapshot(snapshot.existed, float(seeded_tracks[name]))
            for name, snapshot in input_frame.tracks.items()
        }
        for name, value in sampled_tracks.items():
            if name in tracks:
                tracks[name] = TrackSnapshot(tracks[name].existed, value)

        logged_types = self._source_action_types_logged
        type_key = (handle, animation, action_type, storage_mode)
        if type_key not in logged_types:
            logged_types.add(type_key)
            _LOG.debug(
                "AnimGraph source action sampling: animation=%s handle=%s animation_type=%s storage=%s pose_domain=%s",
                animation,
                handle,
                action_type,
                storage_mode or "absolute",
                "additive" if action_is_additive else "absolute",
            )

        if bool(data.get("convertToAdditive", False)):
            cache_key = (handle, clip.key, storage_mode)
            cached_first = self._source_anim_first_frames.get(cache_key)
            if cached_first is None:
                first_components, first_tracks = self.host.sample_clip(
                    clip, first_sample_frame
                )
                first_pose = reference_or_identity_pose(
                    input_frame.reference_pose, additive=action_is_additive
                )
                for name, values in first_components.items():
                    reference = input_frame.reference_pose.get(name)
                    if reference is None:
                        continue
                    sampled = self.host.clip_basis(values, self._red_pose_bridge)
                    if (
                        action_is_additive
                        and storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED
                    ):
                        bind = self._bind_pose_ls.get(name)
                        if bind is None:
                            raise KeyError(
                                f"Bind pose is missing additive source transform {name!r}"
                            )
                        first_pose[name] = recover_reference_applied_transform(
                            reference, bind, sampled
                        )
                    else:
                        first_pose[name] = sampled_animation_transform(
                            reference, sampled, action_type
                        )
                cached_first = (first_pose, first_tracks)
                self._source_anim_first_frames[cache_key] = cached_first
            first_pose, first_tracks = cached_first
            pose = convert_pose_to_additive_local(first_pose, pose)
            for name, snapshot in tuple(tracks.items()):
                current = float(snapshot.value)
                first_default = (
                    0.0
                    if action_is_additive
                    else float(input_frame.reference_tracks.get(name, 0.0))
                )
                first = float(first_tracks.get(name, first_default))
                tracks[name] = TrackSnapshot(snapshot.existed, current - first)

        return BranchFrame(
            pose,
            tracks,
            input_frame.parent_map,
            input_frame.reference_pose,
            input_frame.reference_tracks,
            input_frame.transform_scopes,
            input_frame.track_scopes,
            input_frame.model_space,
            ik_targets=input_frame.ik_targets,
        )

    def _action_at_time(
        self, handle, animation, time_seconds, input_frame, additive_branch, *, absolute
    ) -> BranchFrame:
        """A clip sampled at time_seconds, or the missing-clip output"""
        clip = self.host.clip(animation) if animation else None
        if clip is None:
            return missing_clip_frame(input_frame, additive_branch)
        frame_start, frame_end = clip.frame_start, clip.frame_end
        sample_frame = max(
            frame_start, min(frame_end, frame_start + float(time_seconds) * float(FPS))
        )
        frame = self._sampled_action_frame(
            handle, animation, clip, {}, sample_frame, frame_start, input_frame
        )
        if not absolute or not is_additive_animation_type(clip.animation_type):
            return frame
        base = self._reference_frame(input_frame)
        pose = dict(base.pose)
        base_tracks = {name: snapshot.value for name, snapshot in base.tracks.items()}
        evaluate_blend_additive(
            pose,
            frame.pose,
            base_tracks,
            {name: snapshot.value for name, snapshot in frame.tracks.items()},
            weight=1.0,
            additive_type=ADDITIVE_LOCAL,
            blend_tracks=TRACK_INTERPOLATE,
        )
        tracks = {
            name: TrackSnapshot(snapshot.existed, float(base_tracks[name]))
            for name, snapshot in base.tracks.items()
        }
        return BranchFrame(
            pose,
            tracks,
            base.parent_map,
            base.reference_pose,
            base.reference_tracks,
            base.transform_scopes,
            base.track_scopes,
            base.model_space,
            ik_targets=base.ik_targets,
        )

    def _one_shot_is_running(self, program_node) -> bool:
        return self._one_shot_running.get(
            normalized_source_handle(program_node.handle), True
        )

    def _execute_one_shot(
        self,
        program_node,
        raw_dt,
        time_dilation,
        skip_physics,
        operation_callback,
        frame_cache,
        input_frame,
        additive_branch,
    ) -> BranchFrame:
        """SkOneShotAnim, playing its clip once over the input pose"""
        base = self._execute_program(
            program_node.children[0],
            raw_dt,
            time_dilation,
            skip_physics,
            operation_callback,
            frame_cache,
            input_frame,
            additive_branch,
        )
        handle = normalized_source_handle(program_node.handle)
        if not self._one_shot_running.get(handle, True):
            return base
        animation = str(program_node.data.get("animation", "") or "")
        clip = self.host.clip(animation) if animation else None
        if clip is None:
            self._one_shot_running[handle] = False
            return base
        duration = clip.duration
        _start, _end, clip_front, _clip_end = self._source_action_clip(
            clip, program_node.data
        )
        time_seconds = float(self._source_anim_times.get(handle, clip_front))
        shot = self._sample_source_action(
            program_node,
            input_frame,
            additive_branch=bool(additive_branch),
            raw_dt=raw_dt,
        )
        if (
            duration <= 0.0
            or float(self._source_anim_times.get(handle, clip_front)) / duration >= 1.0
        ):
            self._one_shot_running[handle] = False
        weight = one_shot_weight(
            time_seconds,
            duration,
            program_node.data.get("blendIn", 0.0),
            program_node.data.get("blendOut", 0.0),
        )
        if not is_additive_animation_type(clip.animation_type):
            return interpolate_frames(base, shot, weight)
        pose = dict(base.pose)
        base_tracks = {name: snapshot.value for name, snapshot in base.tracks.items()}
        evaluate_blend_additive(
            pose,
            shot.pose,
            base_tracks,
            {},
            weight=weight,
            additive_type=ADDITIVE_LOCAL,
            blend_tracks=TRACK_BASE,
        )
        return BranchFrame(
            pose,
            dict(base.tracks),
            base.parent_map,
            base.reference_pose,
            base.reference_tracks,
            base.transform_scopes,
            base.track_scopes,
            base.model_space,
            ik_targets=base.ik_targets,
        )

    def _execute_workspot_hub(
        self, program_node, raw_dt, input_frame, additive_branch
    ) -> BranchFrame:
        """WorkspotHub, playing the workspot clip from the UpdateWorkspot preview features"""
        if self._facial_binding is not None:
            raise ValueError(
                "WorkspotHub facial idle playback is not implemented by Graph preview"
            )
        handle = normalized_source_handle(program_node.handle)
        state = self._workspot_states.setdefault(handle, WorkspotHubState())

        def duration_of(animation):
            clip = self.host.clip(animation) if animation else None
            return clip.duration if clip is not None else None

        advance_workspot_hub(
            state,
            workspot_inputs(self.feature_values(), cname_or_empty),
            float(raw_dt),
            duration_of,
        )
        current = self._action_at_time(
            f"{handle}:current",
            state.current.animation,
            state.current.current_time,
            input_frame,
            additive_branch,
            absolute=True,
        )
        if not workspot_blending(state.blend_weight) or state.blend_weight <= 0.0:
            return current
        upcoming = self._action_at_time(
            f"{handle}:next",
            state.next.animation,
            state.next.current_time,
            input_frame,
            additive_branch,
            absolute=True,
        )
        return interpolate_frames(current, upcoming, state.blend_weight)

    def _execute_npc_exploration(
        self, program_node, raw_dt, input_frame, additive_branch
    ) -> BranchFrame:
        """NPCExploration, playing the traversal clip for the exploration preview features"""
        handle = normalized_source_handle(program_node.handle)
        inputs = exploration_inputs(self.feature_values())
        previous = self._exploration_states.get(handle)
        time_seconds = (
            previous[1] if previous is not None and previous[0] == inputs else 0.0
        )
        animation = exploration_animation(*inputs)
        clip = self.host.clip(animation) if animation else None
        if clip is None:
            self._exploration_states[handle] = (inputs, time_seconds)
            return missing_clip_frame(input_frame, additive_branch)
        result = self._action_at_time(
            handle,
            animation,
            time_seconds,
            input_frame,
            additive_branch,
            absolute=False,
        )
        self._exploration_states[handle] = (
            inputs,
            min(time_seconds + float(raw_dt), clip.duration),
        )
        return result

    def _sample_source_action(
        self,
        program_node,
        input_frame: BranchFrame,
        *,
        additive_branch: bool,
        raw_dt: float,
    ) -> BranchFrame:
        handle = normalized_source_handle(program_node.handle)
        data = program_node.data
        animation = str(data.get("animation", "") or "")
        clip = self.host.clip(animation) if animation else None
        if clip is None:
            if animation:
                missing_key = (handle, animation)
                logged = self._missing_active_animations_logged
                if missing_key not in logged:
                    logged.add(missing_key)
                    _LOG.warning(
                        "AnimGraph active source animation unavailable: animation=%s handle=%s additive_branch=%s; using reference/identity fallback",
                        animation,
                        handle,
                        bool(additive_branch),
                    )
            self._emit_source_anim_end(data)
            return missing_clip_frame(input_frame, additive_branch)

        frame_start, frame_end, clip_front, clip_end = self._source_action_clip(
            clip, data
        )
        time_seconds = float(self._source_anim_times.get(handle, clip_front))
        sample_frame = source_clip_sample_frame(
            time_seconds,
            frame_start=frame_start,
            frame_end=frame_end,
            clip_front=clip_front,
            clip_end=clip_end,
            fps=FPS,
            looped=bool(data.get("isLooped", False)),
        )
        frame = self._sampled_action_frame(
            handle,
            animation,
            clip,
            data,
            sample_frame,
            frame_start + clip_front * float(FPS),
            input_frame,
        )
        pose, tracks = frame.pose, frame.tracks
        if self._source_anim_advanced_frame.get(handle) != self._perf_frames:
            end_time = max(
                clip_front, (frame_end - frame_start) / float(FPS) - clip_end
            )
            span = max(0.0, end_time - clip_front)
            time_step = float(raw_dt)
            if bool(data.get("hasSpeedLink", False)):
                time_step *= self.values.linked("float", handle, "speedLink", 1.0)
            elif bool(data.get("hasDurationLink", False)):
                duration = max(
                    0.0, self.values.linked("float", handle, "durationLink", span)
                )
                if duration > 0.0 and span > 0.0:
                    time_step *= span / duration
            next_time, ended = advance_source_clip_time(
                time_seconds,
                time_step,
                clip_front=clip_front,
                clip_end_time=end_time,
                looped=bool(data.get("isLooped", False)),
            )
            # A clip collects its events unless told not to.
            events = (
                self._clip_event_list(clip) if data.get("collectEvents", True) else ()
            )
            if events:
                self._anim_events.update(
                    clip_events_passed(
                        events,
                        time_seconds,
                        next_time,
                        frame_start=frame_start,
                        fps=float(FPS),
                        clip_front=clip_front,
                        clip_end_time=end_time,
                        wrapped=ended and bool(data.get("isLooped", False)),
                        first=handle not in self._source_anim_times,
                    )
                )
            if ended:
                self._emit_source_anim_end(data)
            if data.get("pushDataByTag"):
                self._data_flow[data["pushDataByTag"]] = (
                    (time_seconds - clip_front) / span if span > 0.0 else 0.0
                )
            self._source_anim_times[handle] = next_time
            self._source_anim_advanced_frame[handle] = self._perf_frames
        return BranchFrame(
            pose,
            tracks,
            input_frame.parent_map,
            input_frame.reference_pose,
            input_frame.reference_tracks,
            input_frame.transform_scopes,
            input_frame.track_scopes,
            input_frame.model_space,
            ik_targets=input_frame.ik_targets,
        )

    def _execute_linear_program(self, input_frame: BranchFrame) -> BranchFrame:
        frame = input_frame
        for program_node in self._linear_program:
            kind = program_node.kind
            if kind == "INPUT":
                frame = input_frame
                continue
            if kind == "REFERENCE":
                frame = self._reference_frame(input_frame)
                continue
            if kind == "IDENTITY":
                frame = identity_frame(input_frame)
                continue
            if kind == "SLOT_PASSTHROUGH":
                continue
            if kind in ("SHARED_META_POSE", "SHARED_META_POSE_ADDITIVE"):
                started = perf_counter()
                frame = self._execute_shared_meta_frame(
                    program_node,
                    frame,
                    input_frame,
                    additive=kind == "SHARED_META_POSE_ADDITIVE",
                    copy_frame=False,
                )
                self._perf_shared_meta += perf_counter() - started
                continue
            if kind == "TRAJECTORY_FROM_META_POSE":
                started = perf_counter()
                frame = self._execute_trajectory_from_meta_pose_frame(
                    program_node, frame, input_frame, copy_frame=False
                )
                self._perf_shared_meta += perf_counter() - started
                continue
            if kind == "POSE_LS_TO_MS":
                started = perf_counter()
                frame = self._pose_ls_to_ms(frame)
                self._perf_pose_space += perf_counter() - started
                continue
            if kind == "POSE_MS_TO_LS":
                started = perf_counter()
                frame = self._pose_ms_to_ls(frame)
                self._perf_pose_space += perf_counter() - started
                continue
            if kind.startswith("STACK_"):
                started = perf_counter()
                frame = self._execute_stack_node(program_node, frame, copy_frame=False)
                self._perf_stack += perf_counter() - started
                continue
            if kind == "POSE_OP":
                started = perf_counter()
                frame = self._execute_pure_pose_op(
                    program_node, frame, copy_frame=False
                )
                elapsed = perf_counter() - started
                self._perf_pose_ops += elapsed
                self._perf_pose_op_types[program_node.node_type] = (
                    self._perf_pose_op_types.get(program_node.node_type, 0.0) + elapsed
                )
                continue
            raise ValueError(f"unsupported static AnimGraph command {kind}")
        return frame

    def _execute_program(
        self,
        program_node,
        raw_dt,
        time_dilation,
        skip_physics,
        operation_callback,
        frame_cache,
        input_frame,
        additive_branch=False,
    ):
        current_node = {
            "kind": str(getattr(program_node, "kind", "") or ""),
            "node_type": str(getattr(program_node, "node_type", "") or ""),
            "handle": normalized_source_handle(getattr(program_node, "handle", "")),
            "path": str(getattr(program_node, "path", "") or ""),
            "additive_branch": bool(additive_branch),
        }
        self._last_program_node = current_node
        if current_node["handle"]:
            self._ran_handles.add(current_node["handle"])
        trace = self._execution_trace
        trace.append(current_node)
        if len(trace) > 32:
            del trace[:-32]
        base_cache_key = (
            program_node.handle or f"{program_node.kind}:{program_node.path}"
        )
        cache_key = (base_cache_key, bool(additive_branch))
        if cache_key in frame_cache:
            return frame_cache[cache_key]
        kind = program_node.kind
        handler = graph_node_handler(kind)
        step = ExecutionStep(
            program_node,
            raw_dt,
            time_dilation,
            skip_physics,
            operation_callback,
            frame_cache,
            input_frame,
            additive_branch,
            cache_key,
        )
        if handler is not None and not handler.after_child:
            return handler.execute(self, step)

        child = (
            self._execute_program(
                program_node.children[0],
                raw_dt,
                time_dilation,
                skip_physics,
                operation_callback,
                frame_cache,
                input_frame,
                additive_branch,
            )
            if program_node.children
            else input_frame
        )
        handle = normalized_source_handle(program_node.handle)
        if handler is not None:
            step.child, step.handle = child, handle
            return handler.execute(self, step)
        if kind == "POSE_OP" and handle in self._pure_pose_handles:
            node_started = perf_counter()
            result = self._execute_pure_pose_op(program_node, child)
            elapsed = perf_counter() - node_started
            self._perf_pose_ops += elapsed
            self._perf_pose_op_types[program_node.node_type] = (
                self._perf_pose_op_types.get(program_node.node_type, 0.0) + elapsed
            )
            frame_cache[cache_key] = result
            return result
        if kind == "DANGLE":
            config_index = self._dangle_config_by_handle.get(handle)
            if config_index is None:
                raise ValueError(f"Dangle handle {handle!r} has no imported simulation")
            started = perf_counter()
            result = self._execute_dangle_frame(
                config_index, child, raw_dt, time_dilation, skip_physics
            )
            self._perf_dangle += perf_counter() - started
            frame_cache[cache_key] = result
            return result

        self._restore_frame(child)
        if kind == "POSE_OP":
            plan = self._pose_plans.get(handle)
            if plan is not None:
                plan = self.host.refresh_chain(plan)
                execution = self.host.evaluate_chain(plan)
                self.host.apply_chain(plan, execution)
                self._written_tracks.update(execution.written_tracks)
                if execution.written_bones or execution.written_tracks:
                    self.host.sync_pose()
        elif kind == "DRAG":
            config_index = self._drag_config_by_handle.get(handle)
            if config_index is None:
                raise ValueError(f"Drag handle {handle!r} has no imported simulation")
            runtime_index = self.host.drag_runtime_index(config_index)
            if runtime_index is None:
                raise ValueError(f"Drag handle {handle!r} has no executable runtime")
            started = perf_counter()
            self.host.step_drag(runtime_index, raw_dt, operation_callback)
            self._perf_drag += perf_counter() - started
        result = self._capture_after_child(child)
        frame_cache[cache_key] = result
        return result

    def capture_graph_input(self) -> BranchFrame:
        started = perf_counter()
        frame = self._capture_input_frame()
        self._perf_capture += perf_counter() - started
        return frame

    def step_graph(
        self,
        raw_dt,
        time_dilation,
        skip_physics,
        operation_callback=None,
        input_frame: BranchFrame | None = None,
        sync_final: bool = False,
    ) -> None:
        if not self.structured or self.program is None:
            raise RuntimeError("branch-local graph runtime is not compiled")
        self._current_raw_dt = float(raw_dt)
        self._current_graph_dt = float(raw_dt) * float(time_dilation)
        self._capture_float_variable_inputs()
        self.values.begin_frame()
        self._previous_anim_end_events = frozenset(self._anim_end_events)
        self._anim_end_events.clear()
        self._anim_events.clear()
        self._data_flow.clear()
        self._blend_weights.clear()
        self._ran_handles.clear()
        self._external_events_this_frame = self._consume_preview_external_events()
        self._preview_feature_cache = None
        self.feature_values()
        if input_frame is None:
            capture_started = perf_counter()
            input_frame = self._capture_frame()
            self._perf_capture += perf_counter() - capture_started
        meta_input_frame = input_frame
        self._trace_facial_frame("meta_input", meta_input_frame)
        input_frame = self._facial_graph_input_frame(meta_input_frame)
        self._meta_parent_frame_current = (
            meta_input_frame if input_frame is not meta_input_frame else None
        )
        output_bones = self._graph_output_bones()
        output_tracks = self._graph_output_tracks()
        self.host.prepare_output_bones(output_bones)
        self.host.mark_output_bones(output_bones)
        for name in output_tracks:
            self._prepare_output_tracks((name,))
        self._written_tracks.update(output_tracks)
        execute_started = perf_counter()
        try:
            if self._linear_program:
                output = self._execute_linear_program(input_frame)
                self._last_frames = {}
            else:
                frame_cache = {}
                output = self._execute_program(
                    self.program,
                    raw_dt,
                    time_dilation,
                    skip_physics,
                    operation_callback,
                    frame_cache,
                    input_frame,
                )
                self._last_frames = {
                    normalized_source_handle(key[0]): frame
                    for key, frame in frame_cache.items()
                    if not key[1] and frame is not None
                }
                if self.view_handle in self._last_frames:
                    # A node inside a PoseLsToMs section holds a model-space pose; the rig shows it in local space.
                    output = self._pose_ms_to_ls(self._last_frames[self.view_handle])
        except Exception as error:
            try:
                features = self.feature_values()
            except Exception as feature_error:
                debug_exception(
                    _LOG,
                    "Could not read the graph feature values for the failure report",
                )
                features = {
                    (
                        "<diagnostic>",
                        "feature_error",
                    ): f"{type(feature_error).__name__}: {feature_error}"
                }
            _LOG.error(
                "AnimGraph runtime evaluation failed: rig=%s graph=%s node=%r raw_dt=%.9f "
                "time_dilation=%.6f skip_physics=%s external_events=%r anim_end_events=%r "
                "features=%r state_machines=%r pending_states=%r transition_delay=%r switches=%r error=%s",
                self.host.name,
                self.host.settings.graph_path,
                self._last_program_node,
                float(raw_dt),
                float(time_dilation),
                bool(skip_physics),
                tuple(sorted(self._external_events_this_frame)),
                tuple(sorted(self._anim_end_events)),
                dict(features),
                dict(self._state_machine_states),
                dict(self._state_machine_pending),
                tuple(sorted(self._state_machine_transition_delay)),
                dict(self._switch_selected),
                error,
            )
            _LOG.error(
                "AnimGraph runtime execution trace: %r",
                tuple(self._execution_trace),
            )
            self._meta_parent_frame_current = None
            raise
        self._perf_execute += perf_counter() - execute_started
        self._trace_facial_frame("part_output", output)
        output = self._facial_part_frame_to_meta(output, meta_input_frame)
        self._trace_facial_frame("meta_output", output)
        self._meta_parent_frame_current = None
        restore_started = perf_counter()
        dirty_bones = self._semantic_dirty_bones(output)
        self._perf_semantic_dirty_bones += len(dirty_bones)
        self._restore_frame(
            output,
            bone_names=dirty_bones,
            track_names=output_tracks,
            sync=bool(sync_final),
        )
        self._last_graph_output_pose = {
            name: output.pose[name] for name in output_bones if name in output.pose
        }
        self._perf_final_restore += perf_counter() - restore_started
        self._written_tracks.update(output_tracks)
        self._perf_frames += 1

    def _input_fields(self) -> dict[str, tuple[str, ...]]:
        """Each program node's inputs, in child order, by the field they come from"""
        if self._input_fields_program is not self.program:
            fields, seen = {}, set()
            pending = [self.program] if self.program is not None else []
            while pending:
                node = pending.pop()
                if id(node) in seen:
                    continue
                seen.add(id(node))
                if node.children:
                    fields.setdefault(
                        normalized_source_handle(node.handle),
                        tuple(
                            str(child.path).rsplit(".", 1)[-1]
                            for child in node.children
                        ),
                    )
                    pending.extend(node.children)
            self._input_field_names, self._input_fields_program = fields, self.program
        return self._input_field_names

    def results(self) -> SolveResults:
        """What the last step solved"""
        transitions = {}
        for handle, blend in self._state_machine_blends.items():
            duration = max(1e-8, float(blend.get("duration", 0.0) or 0.0))
            progress = min(1.0, float(blend.get("elapsed", 0.0) or 0.0) / duration)
            transitions[handle] = (int(blend["source"]), int(blend["target"]), progress)
        values = {
            normalized_source_handle(key)
            for key in self.values.evaluated
            if not key.startswith("inline:")
        }
        ran = frozenset(self._ran_handles | values)
        fields = self._input_fields()
        weights = {
            handle: dict(zip(fields.get(handle, ()), shares))
            for handle, shares in self._blend_weights.items()
        }
        for handle, selected in self._switch_selected.items():
            if handle in ran and handle not in weights:
                weights[handle] = {
                    name: float(index == selected)
                    for index, name in enumerate(fields.get(handle, ()))
                }
        return SolveResults(
            ran,
            dict(self._state_machine_states),
            transitions,
            dict(self._switch_selected),
            weights,
        )

    def frame_pose(self, handle: str) -> dict[str, Any]:
        """The output bones' pose node handle produced in the last step"""
        frame = self._last_frames.get(handle)
        if frame is None:
            return {}
        return {
            name: frame.pose[name]
            for name in self._graph_output_bones()
            if name in frame.pose
        }

    def has_pose(self, handle: str) -> bool:
        """Whether node handle output a pose in the last step"""
        return handle in self._last_frames

    def last_output_pose(self) -> dict[str, Any]:
        return dict(self._last_graph_output_pose)

    def performance_hotspots(self) -> str | None:
        frames = max(1, int(self._perf_frames))
        timings = self._perf_pose_op_types
        if not timings:
            return None
        ranked = sorted(timings.items(), key=lambda item: item[1], reverse=True)[:8]
        return "; ".join(
            f"{name.removeprefix('animAnimNode_')}={(seconds / frames) * 1000.0:.2f}ms"
            for name, seconds in ranked
        )

    def performance_summary(self) -> str | None:
        frames = int(self._perf_frames)
        if frames <= 0:
            return None
        total = self._perf_capture + self._perf_execute + self._perf_final_restore
        capture_events, evaluated_events, input_bones = (
            self.host.frame_change_counters()
        )
        return (
            "frames=%d simulation=%.2fms graph=%.2fms draw=%.2fms capture=%.2fms "
            "execute=%.2fms final_restore=%.2fms "
            "depsgraph=%.2fms/%d (%.2f/frame) restore_calls=%d restore_writes=%d "
            "semantic_dirty=%.2f/frame deferred_final_syncs=%d "
            "frame_capture=%d evaluated_capture=%d input_bones=%.2f/event "
            "stack=%.2fms pose_space=%.2fms pose_ops=%.2fms shared=%.2fms blend=%.2fms "
            "dangle=%.2fms drag=%.2fms"
            % (
                frames,
                (self._perf_step_total / frames) * 1000.0,
                (total / frames) * 1000.0,
                (self._perf_draw / frames) * 1000.0,
                (self._perf_capture / frames) * 1000.0,
                (self._perf_execute / frames) * 1000.0,
                (self._perf_final_restore / frames) * 1000.0,
                self._perf_depsgraph_time * 1000.0,
                self._perf_depsgraph_updates,
                self._perf_depsgraph_updates / frames,
                self._perf_restore_calls,
                self._perf_restore_writes,
                self._perf_semantic_dirty_bones / frames,
                self._perf_deferred_final_syncs,
                capture_events,
                evaluated_events,
                input_bones / max(1, capture_events),
                (self._perf_stack / frames) * 1000.0,
                (self._perf_pose_space / frames) * 1000.0,
                (self._perf_pose_ops / frames) * 1000.0,
                (self._perf_shared_meta / frames) * 1000.0,
                (self._perf_blend / frames) * 1000.0,
                (self._perf_dangle / frames) * 1000.0,
                (self._perf_drag / frames) * 1000.0,
            )
        )

    def record_step_total(self, elapsed: float) -> None:
        self._perf_step_total += max(0.0, float(elapsed))

    def record_draw_time(self, elapsed: float) -> None:
        self._perf_draw += max(0.0, float(elapsed))

    def _restore_written_tracks(self) -> tuple[str, ...]:
        """Write the upstream values back over the tracks this runtime wrote and return their names"""
        written = tuple(self._written_tracks)
        if written:
            self.host.restore_tracks(
                {name: self._input_tracks[name] for name in written}
            )
        self._written_tracks.clear()
        return written

    def restore_upstream_tracks(self) -> None:
        self.capture_upstream_tracks()
        self._restore_written_tracks()

    def capture_frame_change_upstream_tracks(self, source_armature=None) -> None:
        for name in self.required_tracks:
            self._input_tracks[name] = self.host.track_snapshot(name, source_armature)

    def restore_frame_change_upstream_tracks(self) -> bool:
        if not self._input_tracks:
            return False
        current = {
            name: self.host.track_snapshot(name) for name in self.required_tracks
        }
        changed = any(
            name in self._input_tracks
            and not track_snapshots_equal(current.get(name), self._input_tracks[name])
            for name in self.required_tracks
        )
        if changed:
            self.host.restore_tracks(
                {
                    name: self._input_tracks[name]
                    for name in self.required_tracks
                    if name in self._input_tracks
                },
            )
        return changed

    def reapply_last_output_tracks(self) -> bool:
        outputs = {
            name: snapshot
            for name, snapshot in self._last_output_tracks.items()
            if snapshot is not None
        }
        if not outputs:
            return False
        changed = any(
            not track_snapshots_equal(self.host.track_snapshot(name), snapshot)
            for name, snapshot in outputs.items()
        )
        if changed:
            self.host.restore_tracks(outputs)
        return changed

    def capture_upstream_tracks(self) -> bool:
        changed = False
        written = set(self._written_tracks)
        for name in self.required_tracks:
            current = self.host.track_snapshot(name)
            if name not in written:
                if self._last_output_tracks.get(name) is None:
                    previous_input = self._input_tracks.get(name)
                    if previous_input is None or not track_snapshots_equal(
                        previous_input, current
                    ):
                        changed = True
                    self._input_tracks[name] = current
                continue
            last_output = self._last_output_tracks.get(name)
            if not track_snapshots_equal(last_output, current):
                changed = True
                self._input_tracks[name] = current
        return changed

    def _prepare_output_tracks(self, track_names: Iterable[str]) -> None:
        for name in track_names:
            if name not in self._written_tracks:
                self._input_tracks[name] = self.host.track_snapshot(name)

    def capture_output_tracks(self) -> None:
        for name in self._written_tracks:
            self._last_output_tracks[name] = self.host.track_snapshot(name)

    def restore_upstream_tracks_final(self) -> None:
        for name in self._restore_written_tracks():
            self._last_output_tracks[name] = None
