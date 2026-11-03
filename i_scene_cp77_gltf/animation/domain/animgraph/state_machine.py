from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, Protocol

from ....assetio.values import cname_or_empty
from .topology import PreviewBoundary, reference_handle, resolve
from .value import float_compare


def interpolation_progress(progress: float, interpolation_type: str) -> float:
    t = max(0.0, min(1.0, float(progress)))
    mode = str(interpolation_type or "Linear")
    if mode == "EaseIn":
        return t * t * t
    if mode == "EaseOut":
        inv = 1.0 - t
        return 1.0 - inv * inv * inv
    if mode == "EaseInOut":
        if t < 0.5:
            return 4.0 * t * t * t
        inv = -2.0 * t + 2.0
        return 1.0 - (inv * inv * inv) * 0.5
    return t


class ConditionInputs(Protocol):
    """What variable, animation event and animation conditions read from the playing graph"""

    def float_variable(self, name: str) -> float: ...
    def bool_variable(self, name: str) -> bool: ...
    def fired_anim_events(self) -> frozenset[str]: ...
    def has_animation(self, name: str) -> bool: ...


_FLOAT_EPSILON = 1.1920929e-07


def _variable_compare(compare_func: Any, value: float, target: float) -> bool:
    """Whether a float variable condition's values are equal within a float's epsilon"""
    op = str(compare_func or "Equal").split("::")[-1]
    if op == "Equal":
        return abs(value - target) <= _FLOAT_EPSILON
    if op == "NotEqual":
        return abs(value - target) >= _FLOAT_EPSILON
    return float_compare(op, value, target)


def _condition_key(condition: Mapping[str, Any], fallback: Any) -> Any:
    handle = str(condition.get("_handle", "") or "")
    return ("handle", handle) if handle else fallback


def _feature_key(condition: Mapping[str, Any]) -> tuple[str, str]:
    return cname_or_empty(condition.get("featureName")), cname_or_empty(
        condition.get("featurePropertyName")
    )


def evaluate_condition(
    condition: Mapping[str, Any] | None,
    *,
    features: Mapping[tuple[str, str], Any],
    external_events: frozenset[str],
    anim_end_events: frozenset[str],
    history: MutableMapping[Any, Any] | None = None,
    frame_id: int | None = None,
    dt: float = 0.0,
    key: Any = ("condition", 0),
    wrapper_variables: frozenset[str] = frozenset(),
    inputs: ConditionInputs | None = None,
) -> bool:
    """Whether condition is met"""
    if not isinstance(condition, Mapping):
        return False
    node_type = str(condition.get("$type", "") or "")
    state_key = _condition_key(condition, key)
    if node_type == "animAnimStateTransitionCondition_ExternalEvent":
        return cname_or_empty(condition.get("eventName")) in external_events
    if node_type == "animAnimStateTransitionCondition_AnimEnd":
        return cname_or_empty(condition.get("eventName")) in anim_end_events
    if node_type == "animAnimStateTransitionCondition_AnyAnimEnd":
        return bool(anim_end_events)
    if node_type == "animAnimStateTransitionCondition_WrapperValue":
        # Met when whether the named anim wrapper variable is set matches checkIfWrapperIsSet.
        is_set = cname_or_empty(condition.get("wrapperName")) in wrapper_variables
        return is_set == bool(condition.get("checkIfWrapperIsSet", True))
    if node_type in {
        "animAnimStateTransitionCondition_FloatVariable",
        "animAnimStateTransitionCondition_BoolVariable",
    }:
        name = cname_or_empty(condition.get("variableName"))
        if node_type.endswith("BoolVariable"):
            value = (
                bool(inputs.bool_variable(name))
                if inputs is not None and name
                else False
            )
            return value == bool(condition.get("compareValue", False))
        value = (
            float(inputs.float_variable(name)) if inputs is not None and name else 0.0
        )
        target = float(condition.get("compareValue", 0.0) or 0.0)
        return _variable_compare(condition.get("compareFunc", "Equal"), value, target)
    if node_type == "animAnimStateTransitionCondition_AnimEvent":
        return (
            inputs is not None
            and cname_or_empty(condition.get("eventName")) in inputs.fired_anim_events()
        )
    if node_type == "animAnimStateTransitionCondition_HasAnimation":
        return inputs is not None and inputs.has_animation(
            cname_or_empty(condition.get("animationName"))
        )
    if node_type == "animAnimStateTransitionCondition_Timed":
        duration = float(
            condition.get("timeToFireTransition", condition.get("time", 0.0)) or 0.0
        )
        if history is None:
            return duration <= 0.0
        state = history.get(state_key)
        if not isinstance(state, dict):
            state = {"remaining": duration, "frame": None}
            history[state_key] = state
        if frame_id is None or state.get("frame") != frame_id:
            state["remaining"] = float(state.get("remaining", duration)) - float(dt)
            state["frame"] = frame_id
        return float(state["remaining"]) < 0.0
    if node_type in {
        "animAnimStateTransitionCondition_IntEdgeFeature",
        "animAnimStateTransitionCondition_IntEdgeFromToFeature",
        "animAnimStateTransitionCondition_IntEdgeToFeature",
        "animAnimStateTransitionCondition_IntEdgeGreaterFromZeroFeature",
        "animAnimStateTransitionCondition_BoolEdgeFeature",
    }:
        raw = features.get(
            _feature_key(condition),
            False if node_type.endswith("BoolEdgeFeature") else 0,
        )
        current = bool(raw) if node_type.endswith("BoolEdgeFeature") else int(raw)
        if history is None:
            previous = False if isinstance(current, bool) else 0
        else:
            state = history.get(state_key)
            if not isinstance(state, dict):
                state = {
                    "current": False if isinstance(current, bool) else 0,
                    "previous": False if isinstance(current, bool) else 0,
                    "frame": None,
                }
                history[state_key] = state
            if frame_id is None or state.get("frame") != frame_id:
                state["previous"] = state.get(
                    "current", False if isinstance(current, bool) else 0
                )
                state["current"] = current
                state["frame"] = frame_id
            previous = state.get("previous", False if isinstance(current, bool) else 0)
            current = state.get("current", current)
        if node_type == "animAnimStateTransitionCondition_IntEdgeFromToFeature":
            return int(previous) == int(condition.get("fromValue", 0) or 0) and int(
                current
            ) == int(condition.get("toValue", 0) or 0)
        if node_type == "animAnimStateTransitionCondition_IntEdgeToFeature":
            return int(previous) != int(current) and int(current) == int(
                condition.get("toValue", 0) or 0
            )
        if (
            node_type
            == "animAnimStateTransitionCondition_IntEdgeGreaterFromZeroFeature"
        ):
            threshold = int(
                condition.get("greaterThenValue", condition.get("greaterThanValue", 0))
                or 0
            )
            return int(previous) == 0 and int(current) > threshold
        return previous != current
    if node_type in {
        "animAnimStateTransitionCondition_IntFeature",
        "animAnimStateTransitionCondition_FloatFeature",
        "animAnimStateTransitionCondition_BoolFeature",
    }:
        raw = features.get(_feature_key(condition), 0)
        if node_type.endswith("BoolFeature"):
            target = bool(condition.get("compareValue", True))
            return bool(raw) == target
        if node_type.endswith("IntFeature"):
            return float_compare(
                condition.get("compareFunc", "Equal"),
                int(raw),
                int(condition.get("compareValue", 0) or 0),
            )
        return float_compare(
            condition.get("compareFunc", "Equal"),
            float(raw),
            float(condition.get("compareValue", 0.0) or 0.0),
        )
    if node_type == "animAnimStateTransitionCondition_CompositeSimultaneous":
        return all(
            evaluate_condition(
                child.get("Data", child) if isinstance(child, Mapping) else None,
                features=features,
                external_events=external_events,
                anim_end_events=anim_end_events,
                history=history,
                frame_id=frame_id,
                dt=dt,
                key=(state_key, index),
                wrapper_variables=wrapper_variables,
                inputs=inputs,
            )
            for index, child in enumerate(condition.get("conditions", ()) or ())
        )
    raise ValueError(
        f"unsupported state transition condition {node_type or '<unknown>'}"
    )


def reset_condition(
    condition: Mapping[str, Any] | None,
    history: MutableMapping[Any, Any] | None,
    key: Any = ("condition", 0),
) -> None:
    if history is None or not isinstance(condition, Mapping):
        return
    state_key = _condition_key(condition, key)
    node_type = str(condition.get("$type", "") or "")
    if node_type == "animAnimStateTransitionCondition_Timed":
        history[state_key] = {
            "remaining": float(
                condition.get("timeToFireTransition", condition.get("time", 0.0)) or 0.0
            ),
            "frame": None,
        }
    if node_type == "animAnimStateTransitionCondition_CompositeSimultaneous":
        for index, child in enumerate(condition.get("conditions", ()) or ()):
            reset_condition(
                child.get("Data", child) if isinstance(child, Mapping) else None,
                history,
                (state_key, index),
            )


@dataclass(frozen=True)
class TransitionChoice:
    target_state: int
    priority: int
    forced: bool
    duration: float
    index: int


def choose_transition(
    transitions,
    indices,
    *,
    features: Mapping[tuple[str, str], Any],
    external_events: frozenset[str],
    anim_end_events: frozenset[str],
    history: MutableMapping[Any, Any] | None = None,
    frame_id: int | None = None,
    dt: float = 0.0,
    key_prefix: Any = "transition",
    wrapper_variables: frozenset[str] = frozenset(),
    inputs: ConditionInputs | None = None,
) -> TransitionChoice | None:
    best = None
    for transition_index in indices:
        try:
            index = int(transition_index)
            transition = transitions[index]
        except (IndexError, TypeError, ValueError):
            continue
        if not isinstance(transition, Mapping) or not bool(
            transition.get("isEnabled", True)
        ):
            continue
        forced = bool(transition.get("isForcedToTrue", False))
        condition = transition.get("condition")
        if not forced and (
            not isinstance(condition, Mapping)
            or not evaluate_condition(
                condition,
                features=features,
                external_events=external_events,
                anim_end_events=anim_end_events,
                history=history,
                frame_id=frame_id,
                dt=dt,
                key=(key_prefix, index),
                wrapper_variables=wrapper_variables,
                inputs=inputs,
            )
        ):
            continue
        choice = TransitionChoice(
            int(transition.get("targetStateIndex", 0) or 0),
            int(transition.get("priority", 0) or 0),
            forced,
            float(transition.get("duration", 0.0) or 0.0),
            index,
        )
        if best is None or (
            not best.forced and (choice.forced or choice.priority > best.priority)
        ):
            best = choice
    return best


def prefer_transition(
    left: TransitionChoice | None, right: TransitionChoice | None
) -> TransitionChoice | None:
    """The transition that wins between two candidates"""
    if left is None:
        return right
    if right is None:
        return left
    if left.forced:
        return left
    if right.forced:
        return right
    return right if right.priority > left.priority else left


def _condition_data(reference, index):
    value = resolve(reference, index) if isinstance(reference, Mapping) else None
    if not isinstance(value, Mapping):
        return None
    data = dict(value)
    data["_handle"] = (
        reference_handle(reference) if isinstance(reference, Mapping) else ""
    )
    if data.get("$type") == "animAnimStateTransitionCondition_CompositeSimultaneous":
        data["conditions"] = tuple(
            _condition_data(item, index) for item in data.get("conditions", ()) or ()
        )
    return data


def _interpolator_data(reference, index):
    value = resolve(reference, index) if isinstance(reference, Mapping) else None
    if not isinstance(value, Mapping):
        return None
    return {
        "$type": str(value.get("$type", "") or ""),
        "interpolationType": str(value.get("interpolationType", "Linear") or "Linear"),
    }


def _transition_data(reference, index):
    value = resolve(reference, index) if isinstance(reference, Mapping) else None
    if not isinstance(value, Mapping):
        return None
    return {
        "targetStateIndex": int(value.get("targetStateIndex", 0) or 0),
        "priority": int(value.get("priority", 0) or 0),
        "duration": float(value.get("duration", 0.0) or 0.0),
        "isEnabled": bool(value.get("isEnabled", True)),
        "isForcedToTrue": bool(value.get("isForcedToTrue", False)),
        "canRequestInertialization": bool(
            value.get("canRequestInertialization", False)
        ),
        "condition": _condition_data(value.get("condition"), index),
        "interpolator": _interpolator_data(value.get("interpolator"), index),
    }


def state_machine_data(node, index):
    """The state machine's states, transitions and interpolators, and its state references"""
    state_refs = list(node.get("states") or ())
    if not state_refs:
        raise PreviewBoundary("StateMachine has no states")
    states = []
    for state_ref in state_refs:
        state = resolve(state_ref, index)
        if not isinstance(state, Mapping):
            raise PreviewBoundary("StateMachine contains an unresolved state")
        states.append(
            {
                "name": cname_or_empty(state.get("name")),
                "outTransitionIndices": tuple(
                    int(v) for v in state.get("outTransitionIndices", ()) or ()
                ),
                "preventTransitionsInActivationFrame": bool(
                    state.get("preventTransitionsInActivationFrame", False)
                ),
                "tags": tuple(
                    tag
                    for tag in (
                        cname_or_empty(item) for item in state.get("tags") or ()
                    )
                    if tag
                ),
            }
        )
    transitions = tuple(
        _transition_data(item, index) for item in node.get("transitions", ()) or ()
    )
    global_transitions = tuple(
        _transition_data(item, index)
        for item in node.get("globalTransitions", ()) or ()
    )
    conditional_entries = tuple(
        _transition_data(item, index)
        for item in node.get("conditionalEntries", ()) or ()
    )
    if any(
        item is None for item in transitions + global_transitions + conditional_entries
    ):
        raise PreviewBoundary("StateMachine contains an unresolved transition")
    return {
        "defaultStateIndex": int(node.get("defaultStateIndex", 0) or 0),
        "states": tuple(states),
        "transitions": transitions,
        "globalTransitions": global_transitions,
        "conditionalEntries": conditional_entries,
        "anyStateInterpolator": _interpolator_data(
            node.get("anyStateInterpolator"), index
        ),
    }, state_refs
