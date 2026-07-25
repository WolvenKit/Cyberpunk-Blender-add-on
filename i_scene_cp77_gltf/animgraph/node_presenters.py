from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, Iterable, Optional, Set

try:
    from .constants import ANIM_NODE_PREFIX
except Exception:
    ANIM_NODE_PREFIX = "animAnimNode_"


PRESENTER_GENERIC = "generic"
PRESENTER_VARIABLE_READER = "variable_reader"
PRESENTER_DANGLE_RUNTIME = "dangle_runtime"
PRESENTER_DANGLE_PARTICLE = "dangle_particle"
PRESENTER_DANGLE_CONE = "dangle_cone_constraint"
PRESENTER_MATH_EXPRESSION = "math_expression"
PRESENTER_CURVE_FLOAT = "curve_float"
PRESENTER_STATE_MACHINE = "state_machine"

_VARIABLE_SHORTS = {
    "BoolVariable",
    "IntVariable",
    "FloatVariable",
    "VectorVariable",
    "QuaternionVariable",
    "TransformVariable",
}

_MATH_SHORTS = {
    "MathExpressionFloat",
    "MathExpressionVector",
    "MathExpressionQuaternion",
    "MathExpressionPose",
}


_SKIP_FIELDS_BY_PRESENTER = {
    PRESENTER_DANGLE_RUNTIME: {"dangleConstraint"},
    PRESENTER_MATH_EXPRESSION: {"expressionData"},
}


@dataclass(frozen=True)
class PresenterInfo:
    id: str
    label: str
    description: str = ""


_PRESENTERS: Dict[str, PresenterInfo] = {
    PRESENTER_GENERIC: PresenterInfo(PRESENTER_GENERIC, "Generic", "RTTI-defined generic node editor"),
    PRESENTER_VARIABLE_READER: PresenterInfo(PRESENTER_VARIABLE_READER, "Variable Reader", "Bound graph variable value editor"),
    PRESENTER_DANGLE_RUNTIME: PresenterInfo(PRESENTER_DANGLE_RUNTIME, "Dangle", "Runtime Dangle node with editor-only payload projections"),
    PRESENTER_DANGLE_PARTICLE: PresenterInfo(PRESENTER_DANGLE_PARTICLE, "Dangle Particle", "Editor-only Dangle particle projection"),
    PRESENTER_DANGLE_CONE: PresenterInfo(PRESENTER_DANGLE_CONE, "Dangle Cone Constraint", "Editor-only Dangle cone constraint projection"),
    PRESENTER_MATH_EXPRESSION: PresenterInfo(PRESENTER_MATH_EXPRESSION, "Math Expression", "Compact MathExpression payload adaptor"),
    PRESENTER_CURVE_FLOAT: PresenterInfo(PRESENTER_CURVE_FLOAT, "Float Curve", "CurveFloatValue curveData editor adaptor"),
    PRESENTER_STATE_MACHINE: PresenterInfo(PRESENTER_STATE_MACHINE, "State Machine", "State-machine editor metadata adaptor"),
}


def _short(red_type: str) -> str:
    text = str(red_type or "")
    if text.startswith(ANIM_NODE_PREFIX):
        return text[len(ANIM_NODE_PREFIX):]
    return text


def presenter_id_for(red_type: str) -> str:
    """Return the presenter id for one REDengine or editor node type."""
    text = str(red_type or "")
    short = _short(text)
    if text == "editorDangleParticle":
        return PRESENTER_DANGLE_PARTICLE
    if text == "editorDangleConeConstraint":
        return PRESENTER_DANGLE_CONE
    if short == "Dangle":
        return PRESENTER_DANGLE_RUNTIME
    if short in _VARIABLE_SHORTS:
        return PRESENTER_VARIABLE_READER
    if short in _MATH_SHORTS:
        return PRESENTER_MATH_EXPRESSION
    if short == "CurveFloatValue":
        return PRESENTER_CURVE_FLOAT
    if short == "StateMachine":
        return PRESENTER_STATE_MACHINE
    return PRESENTER_GENERIC


def presenter_info(presenter_id: str) -> PresenterInfo:
    return _PRESENTERS.get(str(presenter_id or ""), _PRESENTERS[PRESENTER_GENERIC])


def presenter_ids() -> Set[str]:
    return set(_PRESENTERS)


def summary() -> dict:
    return {
        "presenters": len(_PRESENTERS),
        "ids": tuple(sorted(_PRESENTERS)),
    }


def configure_node(node: Any, red_type: str) -> str:
    """Attach presenter metadata to an imported node."""
    pid = presenter_id_for(red_type)
    try:
        node.red_presenter = pid
    except Exception:
        try:
            node["red_presenter"] = pid
        except Exception:
            pass
    return pid


def node_presenter_id(node: Any) -> str:
    try:
        pid = getattr(node, "red_presenter", "")
    except Exception:
        pid = ""
    if not pid:
        try:
            pid = node.get("red_presenter", "")
        except Exception:
            pid = ""
    if pid:
        return str(pid)
    try:
        return presenter_id_for(getattr(node, "red_type", ""))
    except Exception:
        return PRESENTER_GENERIC


def should_skip_property(red_type: str, key: str, value: Any = None) -> bool:
    pid = presenter_id_for(red_type)
    return str(key or "") in _SKIP_FIELDS_BY_PRESENTER.get(pid, set())


def post_import_projection(parser: Any, node: Any, handle_id: str, data: dict) -> None:
    """Run presenter-specific projection after generic import."""
    red_type = str((data or {}).get("$type", ""))
    pid = configure_node(node, red_type)
    if pid == PRESENTER_DANGLE_RUNTIME:
        _post_import_dangle(parser, node, handle_id, data)


def before_attach_properties(parser: Any, node: Any, data: dict) -> None:
    """Run presenter hooks before generic property attachment."""
    red_type = str((data or {}).get("$type", ""))
    pid = configure_node(node, red_type)
    if pid == PRESENTER_MATH_EXPRESSION:
        _attach_math_expression_payload(parser, node, data)


def seed_authored_node(node: Any, definition: Any) -> None:
    """Seed presenter-specific state for newly authored nodes."""
    try:
        configure_node(node, definition.red_type)
    except Exception:
        pass


def _post_import_dangle(parser: Any, node: Any, handle_id: str, data: dict) -> None:
    wrapper = data.get("dangleConstraint") if isinstance(data, dict) else None
    if not isinstance(wrapper, dict):
        return
    try:
        from . import dangle_editor
        particles, constraints, shapes = dangle_editor.create_dangle_editor_subgraphs(
            parser.root_tree, node, handle_id, wrapper)
        parser.dangle_editor_particles += particles
        parser.dangle_editor_constraints += constraints
        parser.dangle_editor_shapes += shapes
    except Exception as exc:
        try:
            parser.problems.append(f"dangle editor subgraph creation failed for {handle_id}: {exc}")
        except Exception:
            pass


def _attach_math_expression_payload(parser: Any, node: Any, data: dict) -> None:
    try:
        from . import math_expression
        from .properties import add_node_property
    except Exception:
        return
    if not isinstance(data, dict):
        return
    if not math_expression.is_math_expression_node_type(str(data.get("$type", ""))):
        return
    expr_data = data.get("expressionData") or data.get("data")
    if not isinstance(expr_data, dict):
        return

    try:
        node['red_math_expression_data_json'] = json.dumps(expr_data, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        pass

    parsed = math_expression.annotate_node(
        node,
        expr_data,
        expression_string=data.get("expressionString", ""),
        node_type=str(data.get("$type", "")),
    )
    if parsed.get("valid"):
        try:
            parser.math_expression_nodes += 1
            parser.math_expression_inputs += len(parsed.get("sockets", []))
        except Exception:
            pass

    tokens = math_expression.token_data(expr_data)
    if tokens:
        add_node_property(
            node,
            "expressionData.expression.Data.tokenData",
            tokens,
            json_path="expressionData.expression.Data.tokenData",
            label="tokenData",
            red_type_hint="array:Uint32",
        )
    values = math_expression.values_data(expr_data)
    if values:
        hint = "array:Float" if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values) else "array"
        add_node_property(
            node,
            "expressionData.expression.Data.valuesData",
            values,
            json_path="expressionData.expression.Data.valuesData",
            label="valuesData",
            red_type_hint=hint,
        )
