from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ...animation.model.animgraph import math_expression
from ...animation.model.animgraph.constants import ANIM_NODE_PREFIX
from ...core.log import debug_exception, get_logger, log_once
from .property_codec import add_node_property

_LOG = get_logger(__name__)


PRESENTER_GENERIC = "generic"
PRESENTER_VARIABLE_READER = "variable_reader"
PRESENTER_DANGLE_RUNTIME = "dangle_runtime"
PRESENTER_DANGLE_PARTICLE = "dangle_particle"
PRESENTER_DANGLE_CONE = "dangle_cone_constraint"
PRESENTER_DIRECT_CONN = "direct_conn_constraint"
PRESENTER_SIMPLE_BOUNCE = "simple_bounce"
PRESENTER_POINT_CONSTRAINT = "point_constraint"
PRESENTER_AIM_CONSTRAINT = "aim_constraint"


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


_PRESENTERS: dict[str, PresenterInfo] = {
    PRESENTER_GENERIC: PresenterInfo(
        PRESENTER_GENERIC, "Generic", "RTTI-defined generic node editor"
    ),
    PRESENTER_VARIABLE_READER: PresenterInfo(
        PRESENTER_VARIABLE_READER,
        "Variable Reader",
        "Bound graph variable value editor",
    ),
    PRESENTER_DANGLE_RUNTIME: PresenterInfo(
        PRESENTER_DANGLE_RUNTIME,
        "Dangle",
        "Runtime Dangle node with editor-only payload projections",
    ),
    PRESENTER_DANGLE_PARTICLE: PresenterInfo(
        PRESENTER_DANGLE_PARTICLE,
        "Dangle Particle",
        "Editor-only Dangle particle projection",
    ),
    PRESENTER_DANGLE_CONE: PresenterInfo(
        PRESENTER_DANGLE_CONE,
        "Dangle Cone Constraint",
        "Editor-only Dangle cone constraint projection",
    ),
    PRESENTER_DIRECT_CONN: PresenterInfo(
        PRESENTER_DIRECT_CONN,
        "Direct Connection Constraint",
        "Copies selected source transform channels into a target pose transform",
    ),
    PRESENTER_SIMPLE_BOUNCE: PresenterInfo(
        PRESENTER_SIMPLE_BOUNCE,
        "Simple Bounce",
        "Drives transform and track channels from signed relative transform distance",
    ),
    PRESENTER_POINT_CONSTRAINT: PresenterInfo(
        PRESENTER_POINT_CONSTRAINT,
        "Point Constraint",
        "Moves one transform toward a normalized weighted average of input model-space positions",
    ),
    PRESENTER_AIM_CONSTRAINT: PresenterInfo(
        PRESENTER_AIM_CONSTRAINT,
        "Aim Constraint",
        "Rotates one transform so authored local forward/up axes aim at model-space target and up points",
    ),
    PRESENTER_MATH_EXPRESSION: PresenterInfo(
        PRESENTER_MATH_EXPRESSION,
        "Math Expression",
        "Compact MathExpression payload adaptor",
    ),
    PRESENTER_CURVE_FLOAT: PresenterInfo(
        PRESENTER_CURVE_FLOAT, "Float Curve", "CurveFloatValue curveData editor adaptor"
    ),
    PRESENTER_STATE_MACHINE: PresenterInfo(
        PRESENTER_STATE_MACHINE,
        "State Machine",
        "State-machine editor metadata adaptor",
    ),
}


def _short(red_type: str) -> str:
    text = str(red_type or "")
    if text.startswith(ANIM_NODE_PREFIX):
        return text[len(ANIM_NODE_PREFIX) :]
    return text


def presenter_id_for(red_type: str) -> str:
    """Return the presenter id for one REDengine or editor node type"""
    text = str(red_type or "")
    short = _short(text)
    if text == "editorDangleParticle":
        return PRESENTER_DANGLE_PARTICLE
    if text == "editorDangleConeConstraint":
        return PRESENTER_DANGLE_CONE
    if short == "Dangle":
        return PRESENTER_DANGLE_RUNTIME
    if short == "DirectConnConstraint":
        return PRESENTER_DIRECT_CONN
    if short == "SimpleBounce":
        return PRESENTER_SIMPLE_BOUNCE
    if short == "PointConstraint":
        return PRESENTER_POINT_CONSTRAINT
    if short in {
        "AimConstraint",
        "AimConstraint_ObjectUp",
        "AimConstraint_ObjectRotationUp",
    }:
        return PRESENTER_AIM_CONSTRAINT
    if short in _VARIABLE_SHORTS:
        return PRESENTER_VARIABLE_READER
    if short in _MATH_SHORTS:
        return PRESENTER_MATH_EXPRESSION
    if short == "CurveFloatValue":
        return PRESENTER_CURVE_FLOAT
    if short == "StateMachine":
        return PRESENTER_STATE_MACHINE
    return PRESENTER_GENERIC


def summary() -> dict:
    return {
        "presenters": len(_PRESENTERS),
        "ids": tuple(sorted(_PRESENTERS)),
    }


def _record_import_state_failure(parser: Any, presenter_id: str, red_type: str) -> None:
    counts = getattr(parser, "presenter_import_failures", None)
    if not isinstance(counts, dict):
        counts = {}
        try:
            parser.presenter_import_failures = counts
        except (
            AttributeError,
            KeyError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_record_import_state_failure", type(error).__name__),
                "record import state failure: fell back after %s",
                error,
                exc_info=True,
            )
            counts = {}
    key = str(presenter_id or PRESENTER_GENERIC)
    count = int(counts.get(key, 0)) + 1
    counts[key] = count
    # One traceback per presenter is useful. Repeating the same recoverable
    # projection failure for every node makes DEBUG logs unusable.
    if count == 1:
        _LOG.debug(
            "AnimGraph %s import-state capture failed for %s; further failures of this presenter are summarized",
            key,
            red_type,
            exc_info=True,
        )


def configure_node(node: Any, red_type: str) -> str:
    """Attach presenter metadata to an imported node"""
    pid = presenter_id_for(red_type)
    try:
        node.red_presenter = pid
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("configure_node 1", type(error).__name__),
            "configure node: fell back after %s",
            error,
            exc_info=True,
        )
        try:
            node["red_presenter"] = pid
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("configure_node 2", type(error).__name__),
                "configure node: fell back after %s",
                error,
                exc_info=True,
            )
    return pid


def node_presenter_id(node: Any) -> str:
    try:
        pid = getattr(node, "red_presenter", "")
    except (AttributeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("node_presenter_id 1", type(error).__name__),
            "node presenter id: fell back after %s",
            error,
            exc_info=True,
        )
        pid = ""
    if not pid:
        try:
            pid = node.get("red_presenter", "")
        except (AttributeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("node_presenter_id 2", type(error).__name__),
                "node presenter id: fell back after %s",
                error,
                exc_info=True,
            )
            pid = ""
    if pid:
        return str(pid)
    return presenter_id_for(getattr(node, "red_type", ""))


def should_skip_property(red_type: str, key: str) -> bool:
    pid = presenter_id_for(red_type)
    if pid == PRESENTER_DIRECT_CONN and str(key or "") in {
        "sourceTransform",
        "isSourceTransformResaved",
    }:
        return True
    if pid == PRESENTER_SIMPLE_BOUNCE and str(key or "") in {
        "areChannelsResaved",
        "transformOutputs",
        "trackOutputs",
        "targetTransform",
        "targetTransformAxis",
        "outputAngleTrack",
    }:
        return True
    if pid == PRESENTER_POINT_CONSTRAINT and str(key or "") in {
        "areSourceChannelsResaved",
        "inputTransforms",
        "preprocessedWeights",
        "inputWeightedTransforms",
    }:
        return True
    if (
        pid == PRESENTER_AIM_CONSTRAINT
        and str(red_type or "") == "animAnimNode_AimConstraint"
        and str(key or "")
        in {"areSourceChannelsResaved", "targetTransforms", "upTransform"}
    ):
        return True
    return str(key or "") in _SKIP_FIELDS_BY_PRESENTER.get(pid, set())


def post_import_projection(parser: Any, node: Any, handle_id: str, data: dict) -> None:
    """Run presenter-specific projection after generic import"""
    red_type = str((data or {}).get("$type", ""))
    pid = configure_node(node, red_type)
    if pid == PRESENTER_DANGLE_RUNTIME:
        _post_import_dangle(parser, node, handle_id, data)


def before_attach_properties(parser: Any, node: Any, data: dict) -> None:
    """Run presenter hooks before generic property attachment"""
    red_type = str((data or {}).get("$type", ""))
    pid = configure_node(node, red_type)
    if pid == PRESENTER_MATH_EXPRESSION:
        _attach_math_expression_payload(parser, node, data)
    elif pid == PRESENTER_DIRECT_CONN:
        try:
            from . import direct_conn

            direct_conn.capture_import_state(node, data)
        except Exception:
            debug_exception(_LOG, "DirectConn import state details")
            _record_import_state_failure(parser, pid, red_type)
    elif pid == PRESENTER_SIMPLE_BOUNCE:
        try:
            from . import simple_bounce

            simple_bounce.capture_import_state(node, data)
        except Exception:
            debug_exception(_LOG, "SimpleBounce import state details")
            _record_import_state_failure(parser, pid, red_type)
    elif pid == PRESENTER_POINT_CONSTRAINT:
        try:
            from . import point_constraint

            point_constraint.capture_import_state(node, data)
        except Exception:
            debug_exception(_LOG, "PointConstraint import state details")
            _record_import_state_failure(parser, pid, red_type)
    elif pid == PRESENTER_AIM_CONSTRAINT:
        try:
            from . import aim_constraint

            aim_constraint.capture_import_state(node, data)
        except Exception:
            debug_exception(_LOG, "AimConstraint import state details")
            _record_import_state_failure(parser, pid, red_type)


def seed_authored_node(node: Any, definition: Any) -> None:
    """Seed presenter-specific state for newly authored nodes"""
    try:
        pid = configure_node(node, definition.red_type)
        if pid == PRESENTER_DIRECT_CONN:
            from . import direct_conn

            direct_conn.seed_authored_state(node)
        elif pid == PRESENTER_SIMPLE_BOUNCE:
            from . import simple_bounce

            simple_bounce.seed_authored_state(node)
        elif pid == PRESENTER_POINT_CONSTRAINT:
            from . import point_constraint

            point_constraint.seed_authored_state(node)
        elif pid == PRESENTER_AIM_CONSTRAINT:
            from . import aim_constraint

            aim_constraint.seed_authored_state(node)
    except Exception:
        _LOG.debug(
            "AnimGraph authored presenter state initialization failed for %s",
            getattr(definition, "red_type", "<unknown>"),
            exc_info=True,
        )


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
            parser.problems.append(
                f"dangle editor subgraph creation failed for {handle_id}: {exc}"
            )
        except (AttributeError, TypeError):
            _LOG.debug(
                "AnimGraph parser could not record dangle projection failure for %s",
                handle_id,
                exc_info=True,
            )


def _attach_math_expression_payload(parser: Any, node: Any, data: dict) -> None:
    if not isinstance(data, dict):
        return
    if not math_expression.is_math_expression_node_type(str(data.get("$type", ""))):
        return
    expr_data = data.get("expressionData") or data.get("data")
    if not isinstance(expr_data, dict):
        return

    try:
        node["red_math_expression_data_json"] = json.dumps(
            expr_data, ensure_ascii=False, separators=(",", ":")
        )
    except (AttributeError, TypeError, ValueError):
        _LOG.debug("AnimGraph math-expression payload storage failed", exc_info=True)

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
        except (AttributeError, TypeError):
            _LOG.debug(
                "AnimGraph math-expression counters could not be updated", exc_info=True
            )

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
        hint = (
            "array:Float"
            if all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in values
            )
            else "array"
        )
        add_node_property(
            node,
            "expressionData.expression.Data.valuesData",
            values,
            json_path="expressionData.expression.Data.valuesData",
            label="valuesData",
            red_type_hint=hint,
        )
