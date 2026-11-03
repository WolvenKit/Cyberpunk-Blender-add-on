from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any

from ....animation.domain.animgraph.direct_conn import evaluate_direct_conn
from ....animation.model.animgraph import direct_conn
from .. import variables
from ..access import (
    node_property_float,
    node_property_map,
    node_property_string,
    property_bool,
    property_string,
)
from .base import (
    NodeEvaluation,
    PoseNodeHandler,
    PosePreviewError,
    input_socket,
    linked_node,
    short_type,
)
from .registry import register_pose_node_handler

# The playing graph's float values by node handle, while it evaluates the chain (see ``float_values``).
_FLOAT_BY_HANDLE: Callable[[str], float] | None = None


@contextmanager
def float_values(float_by_handle: Callable[[str], float] | None):
    """Read a float source the reader below cannot follow from float_by_handle"""
    global _FLOAT_BY_HANDLE
    previous, _FLOAT_BY_HANDLE = _FLOAT_BY_HANDLE, float_by_handle
    try:
        yield
    finally:
        _FLOAT_BY_HANDLE = previous


@dataclass(frozen=True)
class DirectConnSpec:
    source: str
    target: str
    channels: Mapping[str, bool]
    weight: float
    dynamic: bool


def _float_variable_value(node: Any, tree: Any) -> float:
    name = node_property_string(node, "variableName")
    if not name:
        raise PosePreviewError("linked FloatVariable has no variableName")
    try:
        return variables.float_variable_value(tree, name)
    except ValueError as error:
        raise PosePreviewError(str(error)) from error


def _constant_float_value(node: Any) -> float | None:
    properties = node_property_map(node)
    for key in ("value", "floatValue", "constant", "defaultValue", "result"):
        item = properties.get(key)
        if item is None:
            continue
        kind = str(getattr(item, "value_kind", "") or "")
        if kind in {"FLOAT", "INT", "UINT"}:
            attribute = "float_value" if kind == "FLOAT" else "int_value"
            return float(getattr(item, attribute, 0.0))
    return None


def resolve_float_node(
    node: Any, tree: Any, *, _visited: set[int] | None = None
) -> float:
    """Evaluate the float source feeding a dynamic weight through reroutes and pass-through nodes"""
    if node is None:
        raise PosePreviewError("dynamic float link has no source node")
    visited = _visited if _visited is not None else set()
    added = []
    current = node
    try:
        while current is not None:
            identity = id(current)
            if identity in visited:
                raise PosePreviewError("cycle detected while evaluating a float input")
            visited.add(identity)
            added.append(identity)

            if str(getattr(current, "bl_idname", "") or "") == "NodeReroute":
                inputs = tuple(getattr(current, "inputs", ()) or ())
                current = linked_node(inputs[0] if inputs else None)
                continue
            short = short_type(current)
            if short == "FloatVariable":
                return _float_variable_value(current, tree)
            constant = _constant_float_value(current)
            linked_float_inputs = []
            for socket in getattr(current, "inputs", ()) or ():
                if str(getattr(socket, "red_link_type", "") or "") != "animFloatLink":
                    continue
                source = linked_node(socket)
                if source is not None:
                    linked_float_inputs.append(source)
            if constant is not None and not linked_float_inputs:
                return constant
            if len(linked_float_inputs) == 1 and short in {
                "FloatJoin",
                "FloatPassthrough",
                "FloatValue",
            }:
                current = linked_float_inputs[0]
                continue
            handle = str(getattr(current, "red_handle_id", "") or "")
            if _FLOAT_BY_HANDLE is not None and handle:
                return float(_FLOAT_BY_HANDLE(handle))
            raise PosePreviewError(
                f"float node {short or getattr(current, 'name', '<node>')!r} is unsupported by the preview evaluator"
            )
        raise PosePreviewError("dynamic float link has no source node")
    finally:
        for identity in added:
            visited.discard(identity)


def _weight(node: Any, tree: Any) -> tuple[float, bool]:
    source = linked_node(input_socket(node, "weightNode"))
    if source is None:
        return node_property_float(node, "weight", 1.0), False
    return resolve_float_node(source, tree), True


@register_pose_node_handler(direct_conn.RED_TYPE)
class DirectConnHandler(PoseNodeHandler):
    label = "DirectConn"

    def spec(self, node, tree):
        properties = node_property_map(node)
        source = property_string(properties, "sourceTransformIndex")
        target = property_string(properties, "transformIndex")
        if not source or not target:
            raise PosePreviewError(
                f"DirectConn node {getattr(node, 'name', '<node>')!r} lacks source or target transform"
            )
        weight, dynamic = _weight(node, tree)
        return DirectConnSpec(
            source,
            target,
            {
                field: property_bool(properties, field)
                for field in direct_conn.CHANNEL_FIELDS
            },
            weight,
            dynamic,
        )

    def bone_names(self, spec):
        return {spec.source, spec.target}

    def executable(self, spec, index, binding, *, validate_schema):
        return binding.has_bone(spec.source) and binding.has_bone(spec.target)

    def evaluate(self, spec, plan, state, tracks):
        source_name = plan.resolved[spec.source]
        target_name = plan.resolved[spec.target]
        evaluation = evaluate_direct_conn(
            state[target_name], state[source_name], spec.channels, spec.weight
        )
        written = ()
        if evaluation.applied:
            state[target_name] = evaluation.transform
            written = (target_name,)
        return NodeEvaluation(written, (), int(spec.dynamic))

    def is_dynamic(self, spec):
        return spec.dynamic

    def refresh(self, node, tree, spec, runtime_spec):
        weight, _dynamic = _weight(node, tree)
        return replace(spec, weight=weight), replace(runtime_spec, weight=weight)
