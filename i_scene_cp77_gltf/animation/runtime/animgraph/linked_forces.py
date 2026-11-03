from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...domain.animgraph.math_expression import MathExpressionError
from ...domain.animgraph.topology import handle_index
from ...domain.animgraph.vector_preview import dangle_force_links, vector_input_key
from .value_graph import ValueGraph


class _ForceInputs:
    """Graph inputs of the force preview"""

    def __init__(self):
        self.values: Mapping[str, Any] = {}

    def feature_values(self):
        return {}

    def external_events(self) -> frozenset[str]:
        return frozenset()

    def anim_end_events(self) -> frozenset[str]:
        return frozenset()

    def data_flow(self):
        return {}

    def raw_dt(self) -> float:
        return 0.0

    def graph_dt(self) -> float:
        return 0.0

    def float_variable(self, name: str) -> float:
        raise MathExpressionError(
            f"Linked force preview has no AnimGraph variable {name!r}"
        )

    def graph_variables(self):
        return ()

    def vector_input(self, group: str, name: str):
        key = vector_input_key(group, name)
        if key not in self.values:
            raise MathExpressionError(f"Preview input {group}/{name} has no value")
        return self.values[key]


class LinkedForcePreview:
    """Evaluates the external-force vector graphs of linked Dangles from the preview's vector inputs"""

    def __init__(self, document, dangle_identities):
        self._references, self.requirements = dangle_force_links(
            document, dangle_identities
        )
        self._inputs = _ForceInputs()
        self._graph = ValueGraph(handle_index(document), self._inputs)

    @property
    def dangle_count(self) -> int:
        return len(self._references)

    def evaluate(
        self, dangle_identity, values: Mapping[str, Any]
    ) -> tuple[float, float, float]:
        identity = str(dangle_identity or "")
        reference = self._references.get(identity)
        if reference is None:
            raise MathExpressionError(
                f"No linked external-force preview program for {identity or 'Dangle'}"
            )
        self._inputs.values = values
        self._graph.begin_frame()
        return self._graph.value("vector", reference)
