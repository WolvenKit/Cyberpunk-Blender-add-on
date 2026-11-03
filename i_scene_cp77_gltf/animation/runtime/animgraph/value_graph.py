from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from ...domain.animgraph.math_expression import (
    as_quaternion,
    as_vector,
    compile_node_expression,
)
from ...domain.animgraph.topology import reference_handle, resolve
from ...handlers.animgraph.registry import VALUE_NODE_HANDLERS

# Error-message names of each value kind.
_KIND_LABELS = {
    "int": "integer",
    "bool": "Boolean",
    "float": "float",
    "vector": "vector",
    "quaternion": "quaternion",
}
# Kinds whose results are kept for the rest of the frame.
_CACHED_KINDS = ("float", "vector", "quaternion")
_LINK_FALLBACKS = {"int": 0, "bool": False}


class ValueInputs(Protocol):
    """What value nodes read from outside the graph document"""

    def feature_values(self) -> Mapping[tuple[str, str], Any]: ...
    def external_events(self) -> frozenset[str]: ...
    def anim_end_events(self) -> frozenset[str]: ...
    def data_flow(self) -> Mapping[str, float]: ...
    def raw_dt(self) -> float: ...
    def graph_dt(self) -> float: ...
    def float_variable(self, name: str) -> float: ...
    def graph_variables(self) -> Iterable[Any]: ...
    def vector_input(self, group: str, name: str) -> tuple[float, float, float]: ...
    def world_to_model(
        self, vector: tuple[float, float, float], *, direction: bool
    ) -> tuple[float, float, float]:
        """A world-space position, or a direction, in the rig's model space"""


def _key(reference: Mapping[str, Any]) -> str:
    return reference_handle(reference) or f"inline:{id(reference)}"


class ValueGraph:
    def __init__(self, index: Mapping[str, Any], inputs: ValueInputs):
        self.index = index
        self.inputs = inputs
        self.states: dict[str, Any] = {}
        self.expression_plans: dict[str, Any] = {}
        self.random = random.Random()
        self._cache: dict[str, dict[str, Any]] = {kind: {} for kind in _CACHED_KINDS}
        # Keys of the value nodes evaluated this frame, for the solve results.
        self.evaluated: set[str] = set()

    def begin_frame(self) -> None:
        for cache in self._cache.values():
            cache.clear()
        self.evaluated.clear()

    def invalidate(self, *kinds: str) -> None:
        for kind in kinds:
            self._cache[kind].clear()

    def reset_node(self, handle: str, node: Mapping[str, Any]) -> None:
        """Drop the held state of a node whose branch was just activated, when its type resets on activation"""
        handler = VALUE_NODE_HANDLERS.get(str(node.get("$type", "") or ""))
        if handler is not None and handler.resets_on_activation(node):
            self.states.pop(handle, None)
            self._cache["float"].pop(handle, None)

    def value(
        self, kind: str, reference: Mapping[str, Any], visiting: set[str] | None = None
    ):
        """The value of a linked node of kind"""
        key = _key(reference)
        cache = self._cache.get(kind)
        if cache is not None:
            cached = cache.get(key)
            if cached is not None:
                return cached
        active = visiting if visiting is not None else set()
        label = _KIND_LABELS[kind]
        if key in active:
            raise ValueError(
                f"cycle detected while evaluating an AnimGraph {label} value"
            )
        active.add(key)
        try:
            node = resolve(reference, self.index)
            if not isinstance(node, Mapping):
                raise ValueError(f"AnimGraph {label} link has no source node")
            node_type = str(node.get("$type", "") or "")
            handler = VALUE_NODE_HANDLERS.get(node_type)
            if handler is None or handler.value_kind != kind:
                raise ValueError(
                    f"unsupported AnimGraph {label} node {node_type or '<unknown>'}"
                )
            value = handler.evaluate(self, node, key, active)
            self.evaluated.add(key)
            if kind == "float":
                value = float(value)
            elif kind == "vector":
                value = tuple(float(component) for component in value[:3])
            elif kind == "quaternion":
                value = tuple(float(component) for component in value[:4])
            if cache is not None:
                cache[key] = value
            return value
        finally:
            active.discard(key)

    def link(
        self,
        kind: str,
        node: Mapping[str, Any],
        path: str,
        fallback=None,
        visiting: set[str] | None = None,
    ):
        """The value linked at node[path], or fallback (the kind's default when None) without a link"""
        link = node.get(path)
        reference = link.get("node") if isinstance(link, Mapping) else None
        if not isinstance(reference, Mapping):
            if fallback is None:
                return _LINK_FALLBACKS[kind]
            if kind == "float":
                return float(fallback)
            if kind in ("vector", "quaternion"):
                return tuple(float(value) for value in fallback)
            return fallback
        return self.value(kind, reference, visiting)

    def linked(self, kind: str, handle: str, path: str, fallback):
        """The value linked at path of the node with handle, or fallback"""
        source_node = self.index.get(str(handle or ""))
        if not isinstance(source_node, Mapping):
            return (
                float(fallback)
                if kind == "float"
                else tuple(float(value) for value in fallback)
            )
        return self.link(kind, source_node, path, fallback)

    def expression_plan(self, node: Mapping[str, Any], key: str):
        """A MathExpression node's compiled expression and its (name, kind, socket) input bindings"""
        plan = self.expression_plans.get(key)
        if plan is None:
            expression, bindings = compile_node_expression(node)
            plan = (
                expression,
                tuple(
                    (binding.name, binding.kind, binding.socket) for binding in bindings
                ),
            )
            self.expression_plans[key] = plan
        return plan

    def expression_inputs(
        self, plan, visiting: set[str], track_values: Mapping[str, float] | None = None
    ) -> dict:
        """The variables of a compiled expression"""
        _expression, bindings = plan
        values: dict[str, Any] = {}
        for name, kind, socket in bindings:
            if kind == "float":
                track = str(socket.get("inputFloatTrack", "") or "")
                if track_values is not None and track and track in track_values:
                    values[name] = float(track_values[track])
                else:
                    values[name] = self.link("float", socket, "link", 0.0, visiting)
                continue
            link = socket.get("link")
            reference = link.get("node") if isinstance(link, Mapping) else None
            if kind == "vector":
                values[name] = as_vector(
                    self.value("vector", reference, visiting)
                    if isinstance(reference, Mapping)
                    else (0.0, 0.0, 0.0, 0.0)
                )
                continue
            if kind == "quaternion":
                values[name] = as_quaternion(
                    self.value("quaternion", reference, visiting)
                    if isinstance(reference, Mapping)
                    else (0.0, 0.0, 0.0, 1.0)
                )
                continue
            raise ValueError(f"unsupported MathExpression socket kind {kind!r}")
        return values
