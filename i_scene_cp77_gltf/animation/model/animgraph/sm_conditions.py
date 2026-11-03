from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ....assetio.values import cname_text
from .indices import cname
from .schema import enums, registry

CONDITION_PREFIX = "animAnimStateTransitionCondition_"
GROUP = "CompositeSimultaneous"
NO_CONDITION_TEXT = "(no condition)"


@dataclass(frozen=True)
class FieldSpec:
    name: str  # RED JSON key, e.g. "compareValue"
    kind: str  # "CNAME" | "FLOAT" | "INT" | "BOOL" | "ENUM"
    enum_type: str = ""  # e.g. "animCompareFunc", "animEFootPhase"
    default: Any = None


_CONDITION_BASE = "animIAnimStateTransitionCondition"
_GROUP_LIST_TYPE = "array:handle:" + _CONDITION_BASE


def _spec_for(name: str, rtti_type: str) -> FieldSpec | None:
    """The catalogue field for one RTTI property, with its type-based default"""
    kind, default, _red = registry.property_kind_from_type(rtti_type)
    if rtti_type == _GROUP_LIST_TYPE:
        return FieldSpec(name, "LIST")
    if kind == "CNAME":
        return FieldSpec(name, "CNAME", default="None")
    if kind in ("BOOL", "INT", "FLOAT"):
        return FieldSpec(name, kind, default=default)
    if kind == "ENUM" and enums.has_enum(rtti_type):
        zero = next(
            (
                opt
                for opt, value in enums.options(
                    rtti_type, include_sentinel=False
                ).items()
                if value == 0
            ),
            "",
        )
        return FieldSpec(name, "ENUM", rtti_type, zero)
    return None


def _build_catalogue() -> dict[str, tuple[FieldSpec, ...]]:
    """Every concrete condition class of the RTTI schema, with its fields"""
    table: dict[str, tuple[FieldSpec, ...]] = {}
    for name in registry.all_class_names():
        if not name.startswith(CONDITION_PREFIX) or registry.is_abstract(name):
            continue
        if _CONDITION_BASE not in registry.parent_chain(name):
            continue
        specs = []
        for prop in registry.all_properties(name):
            spec = _spec_for(str(prop.get("name", "")), str(prop.get("type", "")))
            if spec is not None:
                specs.append(spec)
        table[short_name(name)] = tuple(sorted(specs, key=lambda spec: spec.name))
    return table


_EDGE_TYPES = frozenset(
    {
        "IntEdgeFeature",
        "IntEdgeFromToFeature",
        "IntEdgeToFeature",
        "IntEdgeGreaterFromZeroFeature",
        "BoolEdgeFeature",
    }
)
_COMPARE_SYMBOLS = {
    "Equal": "=",
    "NotEqual": "!=",
    "Less": "<",
    "LessEqual": "<=",
    "Greater": ">",
    "GreaterEqual": ">=",
}


def short_name(type_name: str) -> str:
    """Condition type name without its RTTI prefix"""
    text = str(type_name or "")
    return text.removeprefix(CONDITION_PREFIX)


CONDITION_TYPES: dict[str, tuple[FieldSpec, ...]] = _build_catalogue()


def _default_value(spec: FieldSpec) -> Any:
    if spec.kind == "CNAME":
        return cname(spec.default)
    if spec.kind == "BOOL":
        return bool(spec.default)
    if spec.kind == "INT":
        return int(spec.default or 0)
    if spec.kind == "FLOAT":
        return float(spec.default or 0.0)
    return spec.default


def default_condition_data(short: str) -> dict:
    """A new Data dict for condition short with default field values"""
    data: dict = {"$type": CONDITION_PREFIX + short}
    if short == GROUP:
        data["conditions"] = []
        return data
    for spec in CONDITION_TYPES[short]:
        data[spec.name] = _default_value(spec)
    return data


def _num(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def _int_text(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _seconds(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    tenths = number * 10.0
    if abs(tenths - round(tenths)) < 1e-4:
        return f"{round(tenths) / 10.0:.1f}"
    return f"{number:g}"


def _name(data: Mapping, key: str) -> str:
    return cname_text(data.get(key), "")


def _feature_ref(data: Mapping) -> str:
    return f"{_name(data, 'featureName')}.{_name(data, 'featurePropertyName')}"


def _compare(data: Mapping, lhs: str, as_int: bool) -> str:
    func = str(data.get("compareFunc", "Equal"))
    symbol = _COMPARE_SYMBOLS.get(func, func)
    value = data.get("compareValue", 0)
    return f"{lhs} {symbol} {_int_text(value) if as_int else _num(value)}"


def _leaf_summary(short: str, data: Mapping) -> str:
    if short == "AnimEnd":
        return f"AnimEnd {_name(data, 'eventName')}"
    if short == "AnimEvent":
        return f"AnimEvent {_name(data, 'eventName')}"
    if short == "AnyAnimEnd":
        return "any AnimEnd"
    if short == "ExternalEvent":
        return f"{_name(data, 'eventName')} event"
    if short == "Timed":
        return f"after {_seconds(data.get('timeToFireTransition', 1.0))} s"
    if short == "FloatFeature":
        return _compare(data, _feature_ref(data), False)
    if short == "IntFeature":
        return _compare(data, _feature_ref(data), True)
    if short == "BoolFeature":
        return (
            f"{_feature_ref(data)} is {'true' if data.get('compareValue') else 'false'}"
        )
    if short in _EDGE_TYPES:
        return f"{short} {_feature_ref(data)}"
    if short in ("FloatVariable", "ModifiedFloatVariable"):
        return _compare(data, _name(data, "variableName"), False)
    if short == "IntVariable":
        return _compare(data, _name(data, "variableName"), True)
    if short == "BoolVariable":
        return f"{_name(data, 'variableName')} is {'true' if data.get('compareValue') else 'false'}"
    if short == "HasAnimation":
        return f"has anim {_name(data, 'animationName')}"
    if short == "WrapperValue":
        state = "set" if data.get("checkIfWrapperIsSet") else "unset"
        return f"wrapper {_name(data, 'wrapperName')} {state}"
    if short == "FootPhaseEvent":
        return f"foot {data.get('footPhase', 'RightUp')}"
    return short


def _data_of(wrapper: Any) -> Mapping | None:
    if isinstance(wrapper, Mapping):
        data = wrapper.get("Data")
        if isinstance(data, Mapping):
            return data
    return None


def _summarize_data(data: Mapping, nested: bool) -> str:
    short = short_name(data.get("$type", ""))
    if short != GROUP:
        return _leaf_summary(short, data)
    children = [
        _summarize_data(child, True)
        for child in (_data_of(w) for w in (data.get("conditions") or ()))
        if child is not None
    ]
    if not children:
        return NO_CONDITION_TEXT
    text = " & ".join(children)
    return f"({text})" if nested else text


def summarize_condition(wrapper: Mapping | None) -> str:
    """One-line human-readable description of a condition wrapper"""
    data = _data_of(wrapper)
    if data is None:
        return NO_CONDITION_TEXT
    return _summarize_data(data, False)


@dataclass
class FlatCondition:
    short: str
    depth: int
    handle: str  # "" for new
    fields: dict  # RED key -> JSON value (CName stays a CName dict)
    original: dict | None  # the original Data dict, for byte preservation


def flatten_condition(wrapper: Mapping | None) -> list[FlatCondition]:
    """Pre-order list of the condition tree"""
    out: list[FlatCondition] = []

    def walk(node: Any, depth: int) -> None:
        data = _data_of(node)
        if data is None:
            return
        short = short_name(data.get("$type", ""))
        skip = ("$type", "conditions") if short == GROUP else ("$type",)
        fields = {k: copy.deepcopy(v) for k, v in data.items() if k not in skip}
        out.append(
            FlatCondition(short, depth, str(node.get("HandleId", "")), fields, data)
        )
        if short == GROUP:
            for child in data.get("conditions") or ():
                walk(child, depth + 1)

    walk(wrapper, 0)
    return out


def _leaf_data(entry: FlatCondition) -> dict:
    """The Data dict for an entry, reusing the original when nothing changed"""
    full_type = CONDITION_PREFIX + entry.short
    original = entry.original
    if isinstance(original, Mapping) and original.get("$type") == full_type:
        data = copy.deepcopy(dict(original))
        for key in [
            k
            for k in data
            if k not in ("$type", "conditions") and k not in entry.fields
        ]:
            del data[key]
        for key, value in entry.fields.items():
            if key not in data or data[key] != value:
                data[key] = copy.deepcopy(value)
        return data
    data = {"$type": full_type}
    for key, value in entry.fields.items():
        data[key] = copy.deepcopy(value)
    return data


def build_condition(
    flat: Sequence[FlatCondition], new_handle: Callable[[], str]
) -> dict | None:
    """Rebuild a condition wrapper from a flat list, or None for an empty list"""
    entries = list(flat)
    if not entries:
        return None

    def build(index: int) -> tuple[dict, int]:
        entry = entries[index]
        data = _leaf_data(entry)
        children: list[dict] = []
        pos = index + 1
        while pos < len(entries) and entries[pos].depth > entry.depth:
            if entries[pos].depth == entry.depth + 1:
                child, pos = build(pos)
                children.append(child)
            else:
                pos += 1  # malformed jump deeper than +1: skip the orphan
        if entry.short == GROUP:
            data["conditions"] = children
        handle = entry.handle or new_handle()
        return {"HandleId": handle, "Data": data}, pos

    return build(0)[0]
