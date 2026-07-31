from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, Set

from ...animation.animgraph_constants import ANIM_NODE_PREFIX


PRESENTER_GENERIC = "generic"
PRESENTER_VARIABLE_READER = "variable_reader"
PRESENTER_DANGLE_RUNTIME = "dangle_runtime"
PRESENTER_DANGLE_PARTICLE = "dangle_particle"
PRESENTER_DANGLE_CONE = "dangle_cone_constraint"


_POST_IMPORT_HOOKS = {}
_NODE_DRAW_HOOKS = {}
NODE_DRAW_FALLBACK = "*"


def register_post_import_hook(presenter_id: str, callback) -> None:
    if not presenter_id or callback is None:
        raise ValueError("presenter_id and callback are required")
    existing = _POST_IMPORT_HOOKS.get(presenter_id)
    if existing is not None and existing is not callback:
        raise RuntimeError(f"post-import hook already registered for {presenter_id}")
    _POST_IMPORT_HOOKS[presenter_id] = callback


def unregister_post_import_hook(presenter_id: str, callback=None) -> None:
    existing = _POST_IMPORT_HOOKS.get(presenter_id)
    if existing is None:
        return
    if callback is not None and existing is not callback:
        return
    _POST_IMPORT_HOOKS.pop(presenter_id, None)


def register_node_draw_hook(presenter_id: str, callback) -> None:
    if not presenter_id or callback is None:
        raise ValueError("presenter_id and callback are required")
    hooks = _NODE_DRAW_HOOKS.setdefault(str(presenter_id), [])
    if callback not in hooks:
        hooks.append(callback)


def unregister_node_draw_hook(presenter_id: str, callback=None) -> None:
    key = str(presenter_id or "")
    hooks = _NODE_DRAW_HOOKS.get(key)
    if not hooks:
        return
    if callback is None:
        _NODE_DRAW_HOOKS.pop(key, None)
        return
    while callback in hooks:
        hooks.remove(callback)
    if not hooks:
        _NODE_DRAW_HOOKS.pop(key, None)


def draw_node(node, context, layout) -> None:
    presenter_id = node_presenter_id(node)
    specific = tuple(_NODE_DRAW_HOOKS.get(presenter_id, ()))
    callbacks = specific or tuple(_NODE_DRAW_HOOKS.get(NODE_DRAW_FALLBACK, ()))
    for callback in callbacks:
        callback(node, context, layout)
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
    hook = _POST_IMPORT_HOOKS.get(PRESENTER_DANGLE_RUNTIME)
    if hook is None:
        return
    try:
        particles, constraints, shapes = hook(parser, node, handle_id, data)
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
        from ...animation.animgraph.model import math_expression
        from .property_codec import add_node_property
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
