from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ....assetio.transform_values import vector3_from_data
from ....assetio.values import cname_text
from ...domain.animgraph.value import (
    clamp_degrees,
    clamp_to_range,
    critical_spring_step,
    damp_step,
    signal_initial,
    signal_step,
    signal_value,
    spring_damp_step,
    time_dependent_sinus,
    wrap_to_range,
)
from .base import ValueNodeHandler


def _has_link(node: Mapping[str, Any], path: str) -> bool:
    link = node.get(path)
    return isinstance(link, Mapping) and isinstance(link.get("node"), Mapping)


class IntLatchHandler(ValueNodeHandler):
    value_kind = "int"
    node_types = ("animAnimNode_IntLatch",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        # Latched from its input when activated.
        if key not in graph.states:
            graph.states[key] = graph.link("int", node, "input", None, visiting)
        return int(graph.states[key])


class FloatRandomHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatRandom",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        minimum, maximum = float(node.get("min", 0.0)), float(node.get("max", 1.0))
        if maximum < minimum:
            raise ValueError("FloatRandom maximum is smaller than its minimum")
        state = graph.states.get(key)
        if state is None:
            state = graph.random.uniform(minimum, maximum), 0.0
        value, elapsed = state
        if bool(node.get("rand", True)):
            elapsed += max(0.0, float(graph.inputs.graph_dt()))
            if elapsed >= float(node.get("cooldown", 1.0)):
                value, elapsed = graph.random.uniform(minimum, maximum), 0.0
        graph.states[key] = value, elapsed
        return value


class TimerHandler(ValueNodeHandler):
    node_types = ("animAnimNode_Timer",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        value = float(graph.states.get(key, 0.0)) + graph.inputs.raw_dt()
        graph.states[key] = value
        return value


class FloatLatchHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatLatch",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        if key not in graph.states:
            graph.states[key] = graph.link("float", node, "input", 0.0, visiting)
        return graph.states[key]


class DampFloatHandler(ValueNodeHandler):
    node_types = ("animAnimNode_DampFloat",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        target = graph.link(
            "float",
            node,
            "inputNode",
            float(node.get("defaultInitialValue", 0.0) or 0.0),
            visiting,
        )
        increase = graph.link(
            "float",
            node,
            "increaseSpeedNode",
            float(node.get("defaultIncreaseSpeed", 1.0) or 0.0),
            visiting,
        )
        decrease = graph.link(
            "float",
            node,
            "decreaseSpeedNode",
            float(node.get("defaultDecreaseSpeed", 1.0) or 0.0),
            visiting,
        )
        if key not in graph.states:
            initial = (
                float(node.get("defaultInitialValue", 0.0) or 0.0)
                if bool(node.get("startFromDefaultValue", False))
                else target
            )
            graph.states[key] = initial
        current = float(graph.states[key])
        use_range = bool(node.get("wrapAroundRange", False))
        value = damp_step(
            current,
            target,
            graph.inputs.raw_dt(),
            increase_speed=increase,
            decrease_speed=decrease,
            range_min=float(node.get("rangeMin", -180.0) or -180.0)
            if use_range
            else None,
            range_max=float(node.get("rangeMax", 180.0) or 180.0)
            if use_range
            else None,
        )
        graph.states[key] = value
        return value


class CriticalSpringDampHandler(ValueNodeHandler):
    node_types = ("animAnimNode_CriticalSpringDamp",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        target = graph.link("float", node, "inputNode", 0.0, visiting)
        if bool(node.get("useRange", False)):
            target = min(
                max(target, float(node.get("rangeMin", -180.0) or -180.0)),
                float(node.get("rangeMax", 180.0) or 180.0),
            )
        current, velocity = graph.states.get(key, (0.0, 0.0))
        smooth_time = max(1e-5, float(node.get("smoothTime", 1.0) or 1.0))
        value, velocity = critical_spring_step(
            float(current),
            float(velocity),
            target,
            graph.inputs.raw_dt(),
            frequency=1.0 / smooth_time,
        )
        graph.states[key] = (value, velocity)
        return value


class SignalHandler(ValueNodeHandler):
    node_types = ("animAnimNode_Signal",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        blend_in = max(0.0, float(node.get("blendIn", 0.0) or 0.0))
        blend_out = max(0.0, float(node.get("blendOut", 0.0) or 0.0))
        cooldown = float(
            node.get("cooldown", -1.0) if node.get("cooldown") is not None else -1.0
        )
        state = graph.states.get(key)
        if state is None:
            state = signal_initial(
                bool(node.get("defaultState", False)), blend_in, blend_out, cooldown
            )
        events = graph.inputs.external_events() | graph.inputs.anim_end_events()
        start_event, end_event = (
            cname_text(node.get("startEvent")),
            cname_text(node.get("endEvent")),
        )
        state = signal_step(
            state,
            graph.inputs.raw_dt(),
            started=bool(start_event) and start_event in events,
            ended=bool(end_event) and end_event in events,
            blend_in=blend_in,
            blend_out=blend_out,
            cooldown=cooldown,
        )
        graph.states[key] = state
        return signal_value(state, blend_in, blend_out)


class FloatTimeDependentSinusHandler(ValueNodeHandler):
    node_types = ("animAnimNode_FloatTimeDependentSinus",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        frequency = float(node.get("frequencyFactor", 1.0) or 1.0)
        elapsed = math.fmod(
            float(graph.states.get(key, 0.0)) + graph.inputs.raw_dt(),
            2.0 * math.pi / frequency,
        )
        graph.states[key] = elapsed
        return time_dependent_sinus(
            elapsed,
            float(node.get("min", 0.0) or 0.0),
            float(node.get("max", 0.0) or 0.0),
            frequency,
            float(node.get("phaseFactor", 0.0) or 0.0),
        )


class SpringDampHandler(ValueNodeHandler):
    node_types = ("animAnimNode_SpringDamp",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        wrap = bool(node.get("wrapAroundRange", False))
        range_min = float(node.get("rangeMin", 0.0) or 0.0)
        range_max = max(range_min, float(node.get("rangeMax", 0.0) or 0.0))
        default = float(node.get("defaultInitialValue", 0.0) or 0.0)
        has_input = _has_link(node, "inputNode")
        target = (
            graph.link("float", node, "inputNode", default, visiting)
            if has_input
            else default
        )
        if wrap:
            target = wrap_to_range(target, range_min, range_max)
        state = graph.states.get(key)
        if state is None:
            start = (
                target
                if has_input and not bool(node.get("startFromDefaultValue", False))
                else default
            )
            state = (wrap_to_range(start, range_min, range_max) if wrap else start, 0.0)
        state = spring_damp_step(
            state[0],
            state[1],
            target,
            graph.inputs.raw_dt(),
            mass=max(0.0001, float(node.get("massFactor", 1.0) or 1.0)),
            spring=max(0.0, float(node.get("springFactor", 0.0) or 0.0)),
            damp=max(0.0, float(node.get("dampFactor", 0.0) or 0.0)),
            time_step=max(0.0001, float(node.get("timeStep", 0.0) or 0.0)),
            wrap=wrap,
            range_min=range_min,
            range_max=range_max,
        )
        graph.states[key] = state
        return state[0]


class FloatCumulativeHandler(ValueNodeHandler):
    """Adds its input every update, or eases back to 0 at the reset speed"""

    node_types = ("animAnimNode_FloatCumulative",)

    def resets_on_activation(self, node) -> bool:
        return bool(node.get("resetOnActivation", False))

    def evaluate(self, graph, node, key, visiting):
        current = float(
            graph.states.get(key, float(node.get("defaultValue", 0.0) or 0.0))
        )
        default = float(node.get("defaultValue", 0.0) or 0.0)

        def limits(value):
            normalize = (
                graph.link("bool", node, "normalize180Input", None, visiting)
                if _has_link(node, "normalize180Input")
                else bool(node.get("normalize180", True))
            )
            if normalize:
                value = clamp_degrees(value)
            if bool(node.get("clamp", True)):
                value = min(
                    max(value, graph.link("float", node, "minValue", 0.0, visiting)),
                    graph.link("float", node, "maxValue", 0.0, visiting),
                )
            return value

        reset_speed = graph.link("float", node, "resetSpeed", 0.0, visiting)
        if _has_link(node, "override") and graph.link(
            "bool", node, "override", None, visiting
        ):
            value = limits(graph.link("float", node, "curValue", default, visiting))
        elif (
            event := cname_text(node.get("resetExternalEventName"))
        ) and event in graph.inputs.external_events():
            value = default
        elif abs(reset_speed) > 0.0 and current != 0.0:
            delta = abs(current * reset_speed * graph.inputs.raw_dt())
            value = (
                0.0
                if abs(delta) >= abs(current) or abs(current) < 0.1
                else current - math.copysign(delta, current)
            )
        else:
            value = limits(
                current + graph.link("float", node, "inputNode", 0.0, visiting)
            )
        graph.states[key] = value
        return value


class ValueBySpeedHandler(ValueNodeHandler):
    node_types = ("animAnimNode_ValueBySpeed",)
    holds_state = True

    def resets_on_activation(self, node) -> bool:
        return bool(node.get("resetOnActivation", False))

    def evaluate(self, graph, node, key, visiting):
        # Starts at its default and moves by its speed each second.
        current = float(
            graph.states.get(key, float(node.get("defaultValue", 0.0) or 0.0))
        )
        value = (
            current
            + graph.link("float", node, "speed", 0.0, visiting)
            * graph.inputs.graph_dt()
        )
        value = clamp_to_range(
            value,
            str(node.get("clampType", "None") or "None").split("::")[-1],
            float(node.get("rangeMin", 0.0) or 0.0),
            float(node.get("rangeMax", 0.0) or 0.0),
        )
        graph.states[key] = value
        return value


class DampVectorHandler(ValueNodeHandler):
    value_kind = "vector"
    node_types = ("animAnimNode_DampVector",)
    holds_state = True

    def evaluate(self, graph, node, key, visiting):
        default = vector3_from_data(node.get("defaultInitialValue"))
        target = graph.link("vector", node, "inputNode", default, visiting)
        increase = graph.link(
            "vector",
            node,
            "increaseSpeedNode",
            vector3_from_data(node.get("defaultIncreaseSpeed")),
            visiting,
        )
        decrease = graph.link(
            "vector",
            node,
            "decreaseSpeedNode",
            vector3_from_data(node.get("defaultDecreaseSpeed")),
            visiting,
        )
        if key not in graph.states:
            graph.states[key] = (
                default if bool(node.get("startFromDefaultValue", False)) else target
            )
        # Each component follows its input at its own increase or decrease speed.
        dt = graph.inputs.graph_dt()
        value = tuple(
            damp_step(current, goal, dt, increase_speed=up, decrease_speed=down)
            for current, goal, up, down in zip(
                graph.states[key], target, increase, decrease
            )
        )
        graph.states[key] = value
        return value
