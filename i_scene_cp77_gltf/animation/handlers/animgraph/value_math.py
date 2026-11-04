from __future__ import annotations

from collections.abc import Mapping

from ....assetio.transform_values import vector3_from_data
from ....bartmoss.quaternion import nlerp_xyzw, slerp_scalar_xyzw
from ...domain.animgraph.curve_points import sample_curve
from ...domain.animgraph.value import (
    direction_to_euler,
    float_compare,
    float_math,
    map_range_clamped,
)
from .base import ValueNodeHandler


class MathExpressionFloatHandler(ValueNodeHandler):
    node_types = ("animAnimNode_MathExpressionFloat",)

    def evaluate(self, graph, node, key, visiting):
        plan = graph.expression_plan(node, key)
        return plan[0].evaluate_scalar(graph.expression_inputs(plan, visiting))


class MathExpressionVectorHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_MathExpressionVector",)

    def evaluate(self, graph, node, key, visiting):
        plan = graph.expression_plan(node, key)
        return plan[0].evaluate_vector(graph.expression_inputs(plan, visiting)).tuple()


class MathExpressionQuaternionHandler(ValueNodeHandler):
    value_kind = "quaternion"
    node_types = ("animAnimNode_MathExpressionQuaternion",)

    def evaluate(self, graph, node, key, visiting):
        plan = graph.expression_plan(node, key)
        return (
            plan[0].evaluate_quaternion(graph.expression_inputs(plan, visiting)).tuple()
        )


class FloatClampHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatClamp",)

    def evaluate(self, graph, node, key, visiting):
        raw = graph.link("float", node, "inputNode", 0.0, visiting)
        return min(
            max(raw, float(node.get("min", 0.0) or 0.0)),
            float(node.get("max", 0.0) or 0.0),
        )


class CurveFloatValueHandler(ValueNodeHandler):
    node_types = ("animAnimNode_CurveFloatValue",)

    def evaluate(self, graph, node, key, visiting):
        argument = graph.link("float", node, "argument", 0.0, visiting)
        return sample_curve(node.get("curveData"), argument, 0.0)


class FloatMathOpHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatMathOp",)

    def evaluate(self, graph, node, key, visiting):
        first = graph.link("float", node, "firstInputNode", 0.0, visiting)
        second = graph.link("float", node, "secondInputNode", 0.0, visiting)
        return float_math(
            str(node.get("operationType", "AGMO_Abs") or "AGMO_Abs"), first, second
        )


class FloatComparatorHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatComparator",)

    def evaluate(self, graph, node, key, visiting):
        first = graph.link(
            "float",
            node,
            "firstInputLink",
            float(node.get("firstValue", 0.0) or 0.0),
            visiting,
        )
        second = graph.link(
            "float",
            node,
            "secondInputLink",
            float(node.get("secondValue", 0.0) or 0.0),
            visiting,
        )
        compare = str(node.get("operation", "AGCF_Equal") or "AGCF_Equal")
        branch = (
            "trueInputLink"
            if float_compare(compare, first, second)
            else "falseInputLink"
        )
        fallback_key = "trueValue" if branch == "trueInputLink" else "falseValue"
        return graph.link(
            "float", node, branch, float(node.get(fallback_key, 0.0) or 0.0), visiting
        )


class DirectionToEulerHandler(ValueNodeHandler):
    node_types = ("animAnimNode_DirectionToEuler",)

    def evaluate(self, graph, node, key, visiting):
        link = node.get("inputNode")
        target = link.get("node") if isinstance(link, Mapping) else None
        if not isinstance(target, Mapping):
            return 0.0
        return direction_to_euler(
            graph.value("vector", target, visiting),
            vector3_from_data(node.get("initialForwardVector")),
            str(node.get("conversionType", "Pitch") or "Pitch"),
        )


# Vector components by axis; the add-on's vectors carry three, so W reads 0.
_AXES = {"X": 0, "Y": 1, "Z": 2}


def _enum(node, field: str, default: str) -> str:
    return str(node.get(field, default) or default).split("::")[-1]


def _weight(graph, node, visiting) -> float:
    return min(1.0, max(0.0, graph.link("float", node, "weight", 0.0, visiting)))


class CoordinateFromVectorHandler(ValueNodeHandler):
    node_types = ("animAnimNode_CoordinateFromVector",)

    def evaluate(self, graph, node, key, visiting):
        axis = _AXES.get(_enum(node, "vectorCoodrinateType", "X"))
        vector = graph.link("vector", node, "input", (0.0, 0.0, 0.0), visiting)
        return float(vector[axis]) if axis is not None else 0.0


class FloatInterpolationHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatInterpolation",)

    def evaluate(self, graph, node, key, visiting):
        # Linear whatever the interpolation type says.
        value = graph.link("float", node, "inputNode", 0.0, visiting)
        return map_range_clamped(
            value,
            *(float(node.get(name, 0.0) or 0.0) for name in ("x1", "x2", "y1", "y2")),
        )


class VectorInterpolationHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_VectorInterpolation",)

    def evaluate(self, graph, node, key, visiting):
        weight = _weight(graph, node, visiting)
        first = graph.link("vector", node, "firstInput", (0.0, 0.0, 0.0), visiting)
        second = graph.link("vector", node, "secondInput", (0.0, 0.0, 0.0), visiting)
        return tuple(a + (b - a) * weight for a, b in zip(first, second))


class QuaternionInterpolationHandler(ValueNodeHandler):
    value_kind = "quaternion"
    node_types = ("animAnimNode_QuaternionInterpolation",)

    def evaluate(self, graph, node, key, visiting):
        weight = _weight(graph, node, visiting)
        first = graph.link(
            "quaternion", node, "firstInput", (0.0, 0.0, 0.0, 1.0), visiting
        )
        second = graph.link(
            "quaternion", node, "secondInput", (0.0, 0.0, 0.0, 1.0), visiting
        )
        mode = _enum(node, "interpolationType", "Linear")
        if mode == "Spherical":
            return slerp_scalar_xyzw(first, second, weight)
        if mode != "Linear":
            raise ValueError(f"unsupported QuaternionInterpolation type {mode}")
        return tuple(
            float(component) for component in nlerp_xyzw(first, second, weight)
        )


class VectorWsToMsHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_VectorWsToMs",)

    def evaluate(self, graph, node, key, visiting):
        link = node.get("vectorWs")
        target = link.get("node") if isinstance(link, Mapping) else None
        if not isinstance(target, Mapping):
            return (0.0, 0.0, 0.0)
        # A position is moved into the rig's space; a direction is only turned.
        direction = _enum(node, "type", "Position") == "Direction"
        return tuple(
            graph.inputs.world_to_model(
                graph.value("vector", target, visiting), direction=direction
            )
        )
