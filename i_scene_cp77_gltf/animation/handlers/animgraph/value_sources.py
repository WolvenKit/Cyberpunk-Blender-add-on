from __future__ import annotations

from collections.abc import Mapping

from ....assetio.transform_values import vector3_from_data
from ....assetio.values import cname_text
from ...domain.animgraph.math_expression import as_quaternion
from ...domain.animgraph.value import slot_name_hash
from .base import ValueNodeHandler


def _declared_variable(graph, name: str, var_type: str, label: str):
    for variable in graph.inputs.graph_variables():
        if str(getattr(variable, "name", "") or "") != name:
            continue
        if str(getattr(variable, "var_type", "") or "") != var_type:
            raise ValueError(
                f"AnimGraph variable {name!r} is not a{'n' if var_type == 'Int' else ''} {var_type}"
            )
        return variable
    raise ValueError(f"AnimGraph {label} variable {name!r} is not declared")


class IntInputHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_IntInput",)

    def evaluate(self, graph, node, key, visiting):
        group = cname_text(node.get("group"))
        name = cname_text(node.get("name"))
        raw = graph.inputs.feature_values().get((group, name), 0)
        try:
            return int(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"AnimGraph integer input {group or '<none>'}/{name or '<none>'} is not numeric"
            ) from exc


class IntVariableHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_IntVariable",)

    def evaluate(self, graph, node, key, visiting):
        variable = _declared_variable(
            graph, cname_text(node.get("variableName")), "Int", "integer"
        )
        return int(getattr(variable, "current_int", 0))


class IntConstantHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_IntConstant",)

    def evaluate(self, graph, node, key, visiting):
        return int(node.get("value", 0))


class IntJoinHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_IntJoin",)

    def evaluate(self, graph, node, key, visiting):
        return graph.link("int", node, "input", None, visiting)


class FloatToIntConverterHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_FloatToIntConverter",)

    def evaluate(self, graph, node, key, visiting):
        return int(graph.link("float", node, "inputNode", 0.0, visiting))


class NameHashConstantHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_NameHashConstant",)

    def evaluate(self, graph, node, key, visiting):
        return slot_name_hash(cname_text(node.get("value")))


class BoolInputHandler(ValueNodeHandler):
    value_kind = "bool"
    node_types = ("animAnimNode_BoolInput",)

    def evaluate(self, graph, node, key, visiting):
        group = cname_text(node.get("group"))
        name = cname_text(node.get("name"))
        raw = graph.inputs.feature_values().get((group, name), False)
        if not isinstance(raw, (bool, int, float)) or raw not in (False, True):
            raise ValueError(
                f"AnimGraph Boolean input {group or '<none>'}/{name or '<none>'} must be true, false, 0, or 1"
            )
        return bool(raw)


class BoolVariableHandler(ValueNodeHandler):
    value_kind = "bool"
    node_types = ("animAnimNode_BoolVariable",)

    def evaluate(self, graph, node, key, visiting):
        variable = _declared_variable(
            graph, cname_text(node.get("variableName")), "Bool", "Boolean"
        )
        return bool(getattr(variable, "current_bool", False))


class BoolConstantHandler(ValueNodeHandler):
    value_kind = "bool"
    node_types = ("animAnimNode_BoolConstant",)

    def evaluate(self, graph, node, key, visiting):
        return bool(node.get("value", False))


class BoolJoinHandler(ValueNodeHandler):
    value_kind = "bool"
    node_types = ("animAnimNode_BoolJoin",)

    def evaluate(self, graph, node, key, visiting):
        return graph.link("bool", node, "input", None, visiting)


class FloatToBoolConverterHandler(ValueNodeHandler):
    value_kind = "bool"
    node_types = ("animAnimNode_FloatToBoolConverter",)

    def evaluate(self, graph, node, key, visiting):
        return graph.link("float", node, "inputNode", 0.0, visiting) != 0.0


class FloatInputHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatInput",)

    def evaluate(self, graph, node, key, visiting):
        group = cname_text(node.get("group"))
        name = cname_text(node.get("name"))
        raw = graph.inputs.feature_values().get((group, name), 0.0)
        try:
            return float(raw)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"AnimGraph float input {group or '<none>'}/{name or '<none>'} is not numeric"
            ) from error


class FloatVariableHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatVariable",)

    def evaluate(self, graph, node, key, visiting):
        return graph.inputs.float_variable(cname_text(node.get("variableName")))


class IntToFloatConverterHandler(ValueNodeHandler):
    node_types = ("animAnimNode_IntToFloatConverter",)

    def evaluate(self, graph, node, key, visiting):
        return graph.link("int", node, "inputNode", None, visiting)


class BoolToFloatConverterHandler(ValueNodeHandler):
    node_types = ("animAnimNode_BoolToFloatConverter",)

    def evaluate(self, graph, node, key, visiting):
        return 1.0 if graph.link("bool", node, "inputNode", None, visiting) else 0.0


class FloatConstantHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatConstant", "animAnimNode_FloatValue")

    def evaluate(self, graph, node, key, visiting):
        return float(
            node.get("value", node.get("floatValue", node.get("constant", 0.0))) or 0.0
        )


class FloatJoinHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatJoin", "animAnimNode_FloatPassthrough")

    def evaluate(self, graph, node, key, visiting):
        return graph.link("float", node, "input", 0.0, visiting)


class WrapperValueHandler(ValueNodeHandler):
    node_types = ("animAnimNode_WrapperValue",)

    def evaluate(self, graph, node, key, visiting):
        names = tuple(cname_text(name) for name in node.get("wrapperNames", ()) or ())
        # Wrapper activation is represented by a declared preview variable.
        declared = frozenset(str(item.name) for item in graph.inputs.graph_variables())
        operation = str(node.get("logicOp", "AGLO_Or")).split("::")[-1]
        if operation not in {"AGLO_Or", "AGLO_And"}:
            raise ValueError(f"Unsupported WrapperValue logic operation {operation}")
        present = [name in declared for name in names if name]
        enabled = bool(names) and (
            any(present) if operation == "AGLO_Or" else all(present)
        )
        return float(not enabled if bool(node.get("oneMinus", False)) else enabled)


class EventHandler(ValueNodeHandler):
    node_types = ("animAnimNode_Event",)

    def evaluate(self, graph, node, key, visiting):
        events = graph.inputs.external_events() | graph.inputs.anim_end_events()
        value_key = (
            "eventValue"
            if cname_text(node.get("eventName")) in events
            else "defaultValue"
        )
        return float(node.get(value_key, 1.0 if value_key == "eventValue" else 0.0))


class TagValueHandler(ValueNodeHandler):
    node_types = ("animAnimNode_TagValue",)

    def evaluate(self, graph, node, key, visiting):
        tag = cname_text(node.get("tag"))
        data_flow = graph.inputs.data_flow()
        if tag in data_flow:
            value = float(data_flow[tag])
            return 1.0 - value if bool(node.get("oneMinus", False)) else value
        return float(node.get("defaultValue", 0.0) or 0.0)


class AnimSetTagValueHandler(ValueNodeHandler):
    node_types = ("animAnimNode_AnimSetTagValue",)

    def evaluate(self, graph, node, key, visiting):
        # 1 when a loaded anim set carries any of the tags; preview loads no tagged anim sets.
        return 0.0


class EventValueHandler(ValueNodeHandler):
    node_types = ("animAnimNode_EventValue",)

    def evaluate(self, graph, node, key, visiting):
        # Set from valued anim events, which preview clips do not fire; otherwise the default.
        return float(node.get("defaultValue", 0.0) or 0.0)


class MultiBoolToFloatValueHandler(ValueNodeHandler):
    node_types = ("animAnimNode_MultiBoolToFloatValue",)

    def evaluate(self, graph, node, key, visiting):
        features = graph.inputs.feature_values()
        inputs = [
            bool(
                features.get(
                    (cname_text(entry.get("group")), cname_text(entry.get("name"))),
                    False,
                )
            )
            for entry in node.get("inputsData", ()) or ()
            if isinstance(entry, Mapping)
        ]
        on_true, on_false = (
            float(node.get("onTrue", 1.0)),
            float(node.get("onFalse", 0.0)),
        )
        passed = all(inputs) if bool(node.get("allMustBeTrue", False)) else any(inputs)
        return on_true if passed else on_false


class VectorConstantHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_VectorConstant", "animAnimNode_VectorValue")

    def evaluate(self, graph, node, key, visiting):
        return vector3_from_data(node.get("value"))


class VectorInputHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_VectorInput",)

    def evaluate(self, graph, node, key, visiting):
        return graph.inputs.vector_input(
            cname_text(node.get("group")), cname_text(node.get("name"))
        )


class VectorJoinHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_VectorJoin", "animAnimNode_VectorPassthrough")

    def evaluate(self, graph, node, key, visiting):
        return graph.link("vector", node, "input", (0.0, 0.0, 0.0), visiting)


class QuaternionConstantHandler(ValueNodeHandler):
    value_kind = "quaternion"
    node_types = ("animAnimNode_QuaternionConstant", "animAnimNode_QuaternionValue")

    def evaluate(self, graph, node, key, visiting):
        return as_quaternion(node.get("value", (0.0, 0.0, 0.0, 1.0))).tuple()


class QuaternionInputHandler(ValueNodeHandler):
    value_kind = "quaternion"
    node_types = ("animAnimNode_QuaternionInput",)

    def evaluate(self, graph, node, key, visiting):
        group = cname_text(node.get("group"))
        name = cname_text(node.get("name"))
        return as_quaternion(
            graph.inputs.feature_values().get((group, name), (0.0, 0.0, 0.0, 1.0))
        ).tuple()


class QuaternionJoinHandler(ValueNodeHandler):
    value_kind = "quaternion"
    node_types = ("animAnimNode_QuaternionJoin", "animAnimNode_QuaternionPassthrough")

    def evaluate(self, graph, node, key, visiting):
        return graph.link("quaternion", node, "input", (0.0, 0.0, 0.0, 1.0), visiting)


class FPPCameraSharedVarHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FPPCameraSharedVar",)

    def evaluate(self, graph, node, key, visiting):
        # The first-person camera's pitch, which only gameplay's camera sets: a preview reads it from its features.
        raw = graph.inputs.feature_values().get(("fppCamera", "sharedVar"), 0.0)
        try:
            return float(raw)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "AnimGraph fppCamera/sharedVar feature is not numeric"
            ) from error
