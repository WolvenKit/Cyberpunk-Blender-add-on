from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ...model.animgraph.frames import BranchFrame


@dataclass(slots=True)
class PoseOpState:
    """One pose operation's inputs"""

    program_node: Any
    handle: str
    node_type: str
    data: Mapping[str, Any]
    child: BranchFrame
    pose: dict
    tracks: dict
    track_values: dict
    ik_targets: tuple


class NameResolver(Protocol):
    """Maps a node's authored bone and track names to the bound rig's"""

    def resolve_structured_bone(
        self, authored: str, *, required: bool = False
    ) -> str: ...

    def resolve_structured_track(
        self, authored: str, *, required: bool = False
    ) -> str: ...


def resolve_bones(context: NameResolver, data, keys, *, optional: bool = False) -> None:
    """Replaces the authored bone names under keys with the bound rig's"""
    for key in keys:
        authored = str(data.get(key, "") or "")
        if authored or not optional:
            data[key] = context.resolve_structured_bone(authored, required=False)


def resolve_tracks(
    context: NameResolver, data, keys, *, optional: bool = False
) -> None:
    """Replaces the authored track names under keys with the bound rig's"""
    for key in keys:
        authored = str(data.get(key, "") or "")
        if authored or not optional:
            data[key] = context.resolve_structured_track(authored, required=False)


class PoseOpHandler:
    """Maps a pose operation node's document data for evaluation and evaluates it"""

    node_types: tuple[str, ...] = ()
    bone_fields: tuple[str, ...] = ()
    track_fields: tuple[str, ...] = ()
    uses_tracks: bool | None = None

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, self.bone_fields)
        resolve_tracks(context, data, self.track_fields)
        if self.uses_tracks is not None:
            data["_usesTracks"] = self.uses_tracks
        return data

    def evaluate(self, context, op: PoseOpState):
        raise NotImplementedError


@dataclass(slots=True)
class ExecutionStep:
    """One program node's execution inputs"""

    program_node: Any
    raw_dt: float
    time_dilation: float
    skip_physics: bool
    operation_callback: Any
    frame_cache: dict
    input_frame: BranchFrame
    additive_branch: Any
    cache_key: Any
    child: BranchFrame | None = None
    handle: str | None = None


def execute_child(
    context, step: ExecutionStep, index: int, *, additive_branch=None
) -> BranchFrame:
    """The program node's child index executed with the step's inputs"""
    return context._execute_program(
        step.program_node.children[index],
        step.raw_dt,
        step.time_dilation,
        step.skip_physics,
        step.operation_callback,
        step.frame_cache,
        step.input_frame,
        step.additive_branch if additive_branch is None else additive_branch,
    )


def execute_first_child(context, step: ExecutionStep) -> BranchFrame:
    """The program node's first child executed with the step's inputs, or the input frame when it has none"""
    return (
        execute_child(context, step, 0)
        if step.program_node.children
        else step.input_frame
    )


class GraphNodeHandler:
    """Executes one program-node kind of a compiled AnimGraph and returns its branch frame"""

    kinds: tuple[str, ...] = ()
    kind_prefixes: tuple[str, ...] = ()
    after_child = False

    def execute(self, context, step: ExecutionStep):
        raise NotImplementedError


class ValueNodeHandler:
    """Evaluates one value node type for graph, the ValueGraph evaluating the link"""

    value_kind = "float"
    node_types: tuple[str, ...] = ()
    holds_state = False

    def resets_on_activation(self, node) -> bool:
        """Whether the node's held value is dropped when its branch is activated"""
        return self.holds_state

    def evaluate(self, graph, node, key: str, visiting: set[str]):
        raise NotImplementedError
