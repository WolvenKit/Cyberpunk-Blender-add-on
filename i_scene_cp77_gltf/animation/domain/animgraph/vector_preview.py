from __future__ import annotations

from dataclasses import dataclass

from ....assetio.values import cname_text
from ....core.log import get_logger
from ...model.animgraph.math_expression import (
    expression_string_value,
    iter_expression_socket_links,
)
from .math_expression import (
    MathExpressionError,
    compile_expression,
    compile_node_expression,
)
from .topology import handle_index, reference_handle, resolve

_LOG = get_logger(__name__)


@dataclass(frozen=True)
class VectorInputRequirement:
    key: str
    group: str
    name: str
    source_handle: str


def vector_input_key(group, name):
    return f"{group or ''!s}\x1f{name or ''!s}"


def _vector_requirements(
    reference, index, visiting
) -> tuple[VectorInputRequirement, ...]:
    """The preview inputs a linked vector graph reads"""
    node = resolve(reference, index)
    if not isinstance(node, dict):
        raise MathExpressionError("Vector preview link does not resolve to a node")
    handle = reference_handle(reference)
    identity = handle or f"inline:{id(node)}"
    if identity in visiting:
        raise MathExpressionError(
            f"Vector preview graph contains a cycle at {identity}"
        )
    visiting.add(identity)
    try:
        node_type = str(node.get("$type", ""))
        if node_type == "animAnimNode_VectorInput":
            group = cname_text(node.get("group"))
            name = cname_text(node.get("name"))
            if not name or name == "None":
                raise MathExpressionError("VectorInput has no input name")
            return (
                VectorInputRequirement(
                    vector_input_key(group, name), group, name, handle
                ),
            )
        if node_type != "animAnimNode_MathExpressionVector":
            raise MathExpressionError(
                f"Unsupported linked vector node {node_type or '<unknown>'}"
            )

        formula = expression_string_value(node.get("expressionString"))
        if not formula:
            raise MathExpressionError("MathExpressionVector has no expressionString")
        expression = compile_expression(formula)
        variable_names = tuple(variable.name for variable in expression.variables)
        sockets = list(iter_expression_socket_links(node.get("expressionData")))
        sockets.sort(
            key=lambda item: int(
                item[3].get("expressionVarId", item[3].get("index", 0))
            )
        )
        if len(variable_names) != len(sockets):
            raise MathExpressionError(
                f"MathExpressionVector {formula!r} exposes {len(sockets)} input socket(s) "
                f"but references {len(variable_names)} variable(s)"
            )
        compile_node_expression(node)
        requirements = []
        seen = set()
        for variable_name, (_path, _caption, link, summary) in zip(
            variable_names, sockets
        ):
            if summary.get("kind") != "Vector":
                raise MathExpressionError(
                    f"MathExpressionVector input {variable_name!r} uses unsupported {summary.get('kind', 'unknown')} socket"
                )
            target = link.get("node")
            if target is None:
                raise MathExpressionError(
                    f"MathExpressionVector input {variable_name!r} is unlinked"
                )
            for requirement in _vector_requirements(target, index, visiting):
                if requirement.key not in seen:
                    seen.add(requirement.key)
                    requirements.append(requirement)
        return tuple(requirements)
    finally:
        visiting.remove(identity)


def collect_vector_input_requirements(document):
    index = handle_index(document)
    requirements = []
    seen = set()
    for handle, node in index.items():
        if (
            not isinstance(node, dict)
            or node.get("$type") != "animAnimNode_VectorInput"
        ):
            continue
        group = cname_text(node.get("group"))
        name = cname_text(node.get("name"))
        if not name or name == "None":
            continue
        key = vector_input_key(group, name)
        if key in seen:
            continue
        seen.add(key)
        requirements.append(VectorInputRequirement(key, group, name, str(handle)))
    return tuple(requirements)


def _dangle_force_reference(dangle_node, index):
    simulation = resolve(dangle_node.get("dangleConstraint"), index)
    if not isinstance(simulation, dict):
        return None
    owner = (
        simulation.get("particlesContainer")
        if simulation.get("$type") == "animDangleConstraint_SimulationDyng"
        else simulation
    )
    if not isinstance(owner, dict):
        return None
    link = owner.get("externalForceWsLink")
    if not isinstance(link, dict):
        return None
    return link.get("node")


def dangle_force_links(document, dangle_identities):
    """The external-force link of each linked Dangle and the preview inputs they read"""
    identities = tuple(str(identity or "") for identity in dangle_identities)
    index = handle_index(document)
    references = {}
    requirements = []
    seen = set()
    _LOG.debug("Compiling linked Dangle force preview: requested=%d", len(identities))
    for identity in identities:
        if not identity.startswith("handle:"):
            raise MathExpressionError(
                f"Linked external-force Dangle has unsupported source identity {identity!r}"
            )
        handle = identity.split(":", 1)[1]
        dangle_node = index.get(handle)
        if (
            not isinstance(dangle_node, dict)
            or dangle_node.get("$type") != "animAnimNode_Dangle"
        ):
            raise MathExpressionError(f"Dangle source handle {handle} does not resolve")
        reference = _dangle_force_reference(dangle_node, index)
        if reference is None:
            continue
        needed = _vector_requirements(reference, index, set())
        references[identity] = reference
        _LOG.debug("Compiled linked Dangle force %s: inputs=%d", identity, len(needed))
        for requirement in needed:
            if requirement.key not in seen:
                seen.add(requirement.key)
                requirements.append(requirement)
    _LOG.debug(
        "Compiled AnimGraph linked forces: dangles=%d external_inputs=%d",
        len(references),
        len(requirements),
    )
    return references, tuple(requirements)


def collect_dangle_force_requirements(document, dangle_identities):
    return dangle_force_links(document, dangle_identities)[1]
