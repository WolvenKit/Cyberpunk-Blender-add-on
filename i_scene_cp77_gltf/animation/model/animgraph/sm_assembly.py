from __future__ import annotations

import copy
import json
import struct
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .sm_conditions import build_condition

LISTS = ("transitions", "globalTransitions", "conditionalEntries")


@dataclass
class TransitionSpec:
    owner: str  # owning State handle; "__entry__" or "__any__" for pseudo owners
    list_name: str  # one of LISTS
    original_index: int  # index in its source list, -1 if new
    original: dict | None  # original wrapper {"HandleId", "Data"}; None if new
    handle: str  # HandleId ("new:N" for new)
    data: dict  # current Data values (RED keys), without "condition"/"targetStateIndex"
    conditions: list  # list[FlatCondition]
    target: str | None  # target State handle; None = no target
    condition_raw: Any = (
        None  # when set, written verbatim as "condition" (conditions is ignored)
    )


@dataclass
class Assembled:
    transitions: list
    globalTransitions: list
    conditionalEntries: list
    out_indices: dict  # State handle -> indices into transitions
    default_state_index: int


class AssemblyError(ValueError):
    pass


def _float32_bytes(value: float) -> bytes:
    try:
        return struct.pack("f", value)
    except OverflowError:
        return struct.pack("f", float("inf") if value > 0 else float("-inf"))


def float32_equal(a: float, b: float) -> bool:
    """True when both values are the same float32 once rounded"""
    return _float32_bytes(a) == _float32_bytes(b)


def tidy_float(value: float) -> float:
    """value with at most 9 significant digits, which keep every float32 exactly"""
    return float(f"{float(value):.9g}")


def tidy_floats(value: Any) -> Any:
    """value with tidy_float applied to every float in it"""
    if isinstance(value, float):
        return tidy_float(value)
    if isinstance(value, dict):
        return {key: tidy_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [tidy_floats(item) for item in value]
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_cname(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("$type") == "CName"
        and "$value" in value
    )


def _equivalent(old: Any, new: Any) -> bool:
    if (
        _is_number(old)
        and _is_number(new)
        and (isinstance(old, float) or isinstance(new, float))
    ):
        return float32_equal(float(old), float(new))
    if _is_cname(old) and _is_cname(new):
        return old.get("$value") == new.get("$value")
    return old == new


def overlay_data(original: Mapping | None, current: Mapping) -> dict:
    """original with every genuinely changed value of current applied"""
    result: dict = copy.deepcopy(dict(original)) if original else {}
    for key, value in current.items():
        if key in result and _equivalent(result[key], value):
            continue
        result[key] = copy.deepcopy(value)
    ordered: dict = {}
    if "$type" in result:
        ordered["$type"] = result["$type"]
    for key in sorted(k for k in result if k != "$type"):
        ordered[key] = result[key]
    return ordered


def _wrapper_for(
    spec: TransitionSpec,
    row: int,
    state_order: Sequence[str],
    new_handle: Callable[[], str],
) -> dict:
    if spec.target is None or spec.target not in state_order:
        raise AssemblyError(f"transition {spec.owner} row {row} has no target")
    original = spec.original
    original_data = original.get("Data") if original else None
    current = dict(spec.data)
    if spec.condition_raw is not None:
        current["condition"] = copy.deepcopy(spec.condition_raw)
    else:
        current["condition"] = build_condition(spec.conditions, new_handle)
    current["targetStateIndex"] = list(state_order).index(spec.target)
    data = overlay_data(original_data, current)
    if (
        original is not None
        and original_data is not None
        and original.get("HandleId") == spec.handle
        and json.dumps(original_data, sort_keys=True)
        == json.dumps(data, sort_keys=True)
    ):
        return original
    return {"HandleId": spec.handle, "Data": data}


def assemble(
    specs: Sequence[TransitionSpec],
    state_order: Sequence[str],
    default_target: str | None,
    new_handle: Callable[[], str],
    *,
    original_default: int | None = None,
) -> Assembled:
    """Rebuild the state machine lists from specs"""
    state_order = list(state_order)
    by_list: dict[str, list] = {name: [] for name in LISTS}
    row_counts: dict[tuple, int] = {}
    for spec in specs:
        if spec.list_name not in by_list:
            raise AssemblyError(f"unknown transition list {spec.list_name!r}")
        key = (spec.owner, spec.list_name)
        row_counts[key] = row_counts.get(key, 0) + 1
        by_list[spec.list_name].append((spec, row_counts[key]))

    lists: dict[str, list] = {}
    out_indices: dict[str, list] = {state: [] for state in state_order}
    for name in LISTS:
        entries = by_list[name]
        if name == "transitions":
            kept = sorted(
                (e for e in entries if e[0].original_index >= 0),
                key=lambda e: e[0].original_index,
            )
            added = [e for e in entries if e[0].original_index < 0]
            ordered = kept + added
        else:
            ordered = list(entries)
        lists[name] = [
            _wrapper_for(spec, row, state_order, new_handle) for spec, row in ordered
        ]
        if name == "transitions":
            final = {id(spec): index for index, (spec, _row) in enumerate(ordered)}
            for spec, _row in entries:
                out_indices.setdefault(spec.owner, []).append(final[id(spec)])

    if default_target is None:
        if original_default is None:
            raise AssemblyError(
                "default state is unknown: no default_target and no original_default"
            )
        default_index = original_default
    elif default_target in state_order:
        default_index = state_order.index(default_target)
    else:
        raise AssemblyError(f"default state {default_target} is not in the state order")
    return Assembled(
        lists["transitions"],
        lists["globalTransitions"],
        lists["conditionalEntries"],
        out_indices,
        default_index,
    )
