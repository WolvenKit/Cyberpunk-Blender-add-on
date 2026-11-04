from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from ...core.log import get_logger
from ..armature_bones import resolve_pose_bone, with_ancestor_bones
from ..pose import (
    apply_engine_pose,
    apply_tracks,
    capture_engine_pose_bones,
    capture_reference_pose_ls,
    capture_reference_pose_ms,
)
from ..tracks import reference_track_values
from . import rig_binding
from .pose_nodes import register_default_handlers
from .pose_nodes.base import (
    BindingContext,
    PlanNameResolver,
    PosePreviewError,
    available_tracks,
    input_socket,
    linked_node,
    short_type,
)
from .pose_nodes.registry import POSE_NODE_HANDLERS

_LOG = get_logger(__name__)

register_default_handlers()

REFERENCE_POSE_TYPE = "animAnimNode_ReferencePoseTerminator"
OUTPUT_POSE_TYPE = "animAnimNode_Output"
TRANSPARENT_POSE_TYPES = {"animAnimNode_Join", "animAnimNode_SelectiveJoin"}


@dataclass(frozen=True)
class ChainPlan:
    chain: tuple[Any, ...]
    boundary: str
    specs: tuple[Any, ...]
    resolved: Mapping[str, str]
    required_bones: frozenset[str]
    parent_map: Mapping[str, str]
    reference_pose_ms: Mapping[str, Any]
    reference_pose_ls: Mapping[str, Any]
    requested_tracks: frozenset[str]
    runtime_specs: tuple[Any, ...]
    pose_bones: Mapping[str, Any]
    seed_reference_pose: bool = False
    reference_tracks: Mapping[str, float] | None = None
    handlers: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ChainExecution:
    state: Mapping[str, Any]
    tracks: Mapping[str, float]
    written_bones: frozenset[str]
    written_tracks: frozenset[str]
    dynamic_weights: int


def _red_type(node: Any) -> str:
    return str(getattr(node, "red_type", "") or "")


def _supported(node: Any) -> bool:
    return POSE_NODE_HANDLERS.supports(_red_type(node))


def _pose_input_socket(node: Any):
    red_type = _red_type(node)
    if red_type == "animAnimNode_Join":
        path = "input"
    elif red_type == OUTPUT_POSE_TYPE:
        path = "node"
    else:
        path = "inputLink"
    return input_socket(node, path)


def _pose_parent(node: Any):
    parent = linked_node(_pose_input_socket(node))
    visited = set()
    while parent is not None:
        identity = id(parent)
        if identity in visited:
            raise PosePreviewError("cycle detected in transparent pose links")
        visited.add(identity)
        if str(getattr(parent, "bl_idname", "") or "") == "NodeReroute":
            inputs = tuple(getattr(parent, "inputs", ()) or ())
            parent = linked_node(inputs[0] if inputs else None)
            continue
        if _red_type(parent) in TRANSPARENT_POSE_TYPES:
            parent = linked_node(_pose_input_socket(parent))
            continue
        break
    return parent


def pose_processing_chain(active_node: Any) -> tuple[tuple[Any, ...], str, bool]:
    """Supported pose nodes from the chain's boundary up to active_node"""
    if _red_type(active_node) == OUTPUT_POSE_TYPE:
        active_node = _pose_parent(active_node)
        if active_node is None:
            raise PosePreviewError("Output has no pose input")
    if _red_type(active_node) == REFERENCE_POSE_TYPE:
        return (), "ReferencePoseTerminator", True
    if not _supported(active_node):
        raise PosePreviewError("active node is not a supported pose-processing node")
    chain = []
    visited = set()
    current = active_node
    boundary = "current sampled armature pose"
    seed_reference_pose = False
    while current is not None and _supported(current):
        identity = id(current)
        if identity in visited:
            raise PosePreviewError(
                "cycle detected in the supported pose-processing chain"
            )
        visited.add(identity)
        chain.append(current)
        parent = _pose_parent(current)
        if parent is None:
            boundary = "unlinked pose input; current sampled armature pose"
            break
        if _red_type(parent) == REFERENCE_POSE_TYPE:
            boundary = "ReferencePoseTerminator"
            seed_reference_pose = True
            break
        if not _supported(parent):
            boundary_type = short_type(parent) or str(
                getattr(parent, "name", "") or "upstream node"
            )
            boundary = (
                f"{boundary_type}; current Blender pose used as its sampled output"
            )
            break
        current = parent
    chain.reverse()
    return tuple(chain), boundary, seed_reference_pose


def _handler(node: Any):
    handler = POSE_NODE_HANDLERS.get(_red_type(node))
    if handler is None:
        raise PosePreviewError(
            f"unsupported pose node type: {_red_type(node) or '<empty>'}"
        )
    return handler


def _names(handlers, specs, method: str) -> set[str]:
    names = set()
    for handler, spec in zip(handlers, specs):
        names.update(getattr(handler, method)(spec))
    names.discard("")
    return names


def _parent_map(armature: Any, names: set[str]) -> dict[str, str]:
    pose_bones = getattr(getattr(armature, "pose", None), "bones", None)
    result = {}
    for name in names:
        bone = pose_bones.get(name) if pose_bones is not None else None
        parent = getattr(bone, "parent", None) if bone is not None else None
        result[name] = str(getattr(parent, "name", "") or "")
    return result


def _plan(armature, chain, boundary, seed_reference_pose, handlers, specs) -> ChainPlan:
    resolved = {}
    for name in (
        *_names(handlers, specs, "bone_names"),
        *_names(handlers, specs, "optional_bone_names"),
    ):
        bone = resolve_pose_bone(armature, name)
        if bone is not None:
            resolved[name] = str(bone.name)
    required_bones = with_ancestor_bones(armature, set(resolved.values()))
    if seed_reference_pose:
        required_bones.update(
            str(bone.name)
            for bone in getattr(getattr(armature, "pose", None), "bones", ()) or ()
        )
    parent_map = _parent_map(armature, required_bones)
    available = available_tracks(armature)
    requested_tracks = _names(handlers, specs, "track_names")
    if seed_reference_pose:
        requested_tracks.update(available)
    requested_tracks.update(_names(handlers, specs, "optional_track_names") & available)
    requested_tracks.intersection_update(available)
    requested_tracks = frozenset(requested_tracks)
    names = PlanNameResolver(resolved, requested_tracks)
    return ChainPlan(
        chain,
        boundary,
        specs,
        resolved,
        frozenset(required_bones),
        parent_map,
        capture_reference_pose_ms(armature, required_bones),
        capture_reference_pose_ls(armature, required_bones),
        requested_tracks,
        tuple(
            handler.runtime_spec(spec, _red_type(node), names)
            for handler, node, spec in zip(handlers, chain, specs)
        ),
        {name: armature.pose.bones[name] for name in required_bones},
        seed_reference_pose,
        reference_track_values(armature, requested_tracks),
        handlers,
    )


def _executable(nodes, owner, armature, *, validate: bool):
    """(nodes, handlers, specs) whose bones and tracks the armature provides"""
    handlers = tuple(_handler(node) for node in nodes)
    specs = tuple(handler.spec(node, owner) for handler, node in zip(handlers, nodes))
    binding = BindingContext(armature)
    enabled = tuple(
        handler.executable(spec, index, binding, validate_schema=validate)
        for index, (handler, spec) in enumerate(zip(handlers, specs))
    )
    keep = [index for index, flag in enumerate(enabled) if flag]
    return (
        tuple(nodes[index] for index in keep),
        tuple(handlers[index] for index in keep),
        tuple(specs[index] for index in keep),
    )


def prepare_chain(
    tree: Any, active_node: Any, armature: Any | None = None, *, validate: bool = True
) -> ChainPlan:
    owner = rig_binding.binding_tree(tree) or tree
    armature = armature or rig_binding.bound_armature(owner)
    if armature is None:
        raise PosePreviewError("Bind this AnimGraph to an armature before evaluating")
    chain, boundary, seed_reference_pose = pose_processing_chain(active_node)
    chain, handlers, specs = _executable(chain, owner, armature, validate=validate)
    return _plan(armature, chain, boundary, seed_reference_pose, handlers, specs)


def prepare_node_operation(
    tree: Any, node: Any, armature: Any, *, validate: bool = True
) -> ChainPlan | None:
    """Prepare exactly one stateless pose node against the current branch input pose"""
    owner = rig_binding.binding_tree(tree) or tree
    if armature is None:
        raise PosePreviewError("Bind this AnimGraph to an armature before evaluating")
    chain, handlers, specs = _executable((node,), owner, armature, validate=validate)
    if not chain:
        return None
    return _plan(armature, chain, "branch input pose", False, handlers, specs)


def upstream_pose_processing_node(boundary_node: Any):
    parent = _pose_parent(boundary_node)
    if parent is None:
        return None
    if not _supported(parent) and _red_type(parent) != REFERENCE_POSE_TYPE:
        return None
    return parent


def prepare_upstream_chain(
    tree: Any, boundary_node: Any, armature: Any, *, validate: bool = True
) -> ChainPlan | None:
    node = upstream_pose_processing_node(boundary_node)
    if node is None:
        _LOG.debug(
            "AnimGraph upstream chain has no supported pose predecessor: boundary=%s",
            getattr(boundary_node, "name", "<unnamed>"),
        )
        return None
    plan = prepare_chain(tree, node, armature, validate=validate)
    _LOG.debug(
        "Prepared AnimGraph upstream chain: boundary=%s operations=%d bones=%d tracks=%d validate=%s",
        getattr(boundary_node, "name", "<unnamed>"),
        len(plan.specs),
        len(plan.required_bones),
        len(plan.requested_tracks),
        bool(validate),
    )
    return plan


def refresh_dynamic_chain_plan(plan: ChainPlan, tree: Any) -> ChainPlan:
    """Re-read linked dynamic weights"""
    if not any(
        handler.is_dynamic(spec) for handler, spec in zip(plan.handlers, plan.specs)
    ):
        return plan
    specs = list(plan.specs)
    runtime_specs = list(plan.runtime_specs)
    for index, (handler, node, spec) in enumerate(
        zip(plan.handlers, plan.chain, plan.specs)
    ):
        if handler.is_dynamic(spec):
            specs[index], runtime_specs[index] = handler.refresh(
                node, tree, spec, runtime_specs[index]
            )
    return replace(plan, specs=tuple(specs), runtime_specs=tuple(runtime_specs))


def evaluate_chain_state(plan: ChainPlan, armature: Any) -> ChainExecution:
    if plan.seed_reference_pose:
        state = dict(plan.reference_pose_ls)
        tracks = dict(plan.reference_tracks or {})
        written_bones = set(plan.pose_bones)
        written_tracks = set(plan.requested_tracks)
    else:
        state = capture_engine_pose_bones(plan.pose_bones, plan.reference_pose_ls)
        tracks = {
            name: float(armature.get(name, 0.0) or 0.0)
            for name in plan.requested_tracks
        }
        written_bones = set()
        written_tracks = set()
    dynamic_weights = 0
    for handler, spec in zip(plan.handlers, plan.runtime_specs):
        evaluation = handler.evaluate(spec, plan, state, tracks)
        written_bones.update(evaluation.written_bones)
        written_tracks.update(evaluation.written_tracks)
        dynamic_weights += evaluation.dynamic_weights
    return ChainExecution(
        state,
        tracks,
        frozenset(written_bones),
        frozenset(written_tracks),
        dynamic_weights,
    )


def apply_chain_execution(
    armature: Any, plan: ChainPlan, execution: ChainExecution
) -> tuple[int, int]:
    bone_count = apply_engine_pose(
        armature,
        {name: execution.state[name] for name in execution.written_bones},
        plan.reference_pose_ls,
    )
    track_count = apply_tracks(
        armature, {name: execution.tracks[name] for name in execution.written_tracks}
    )
    return bone_count, track_count
