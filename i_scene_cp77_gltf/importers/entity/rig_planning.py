from __future__ import annotations

import heapq
from collections.abc import Mapping, Sequence
from typing import Any

from ..common.entity_data import component_name
from ..common.handles import resolve_component_handle_data
from ..common.paths import depot_path_value
from ...assetio.values import cname_value


def animated_component_control_target(
    component: dict,
    lookup: Mapping[Any, dict] | None = None,
) -> str:
    data = resolve_component_handle_data(component, lookup, "controlBinding")
    if type(data) is not dict or data.get("enabled", 1) == 0:
        return ""
    return cname_value(data.get("bindName"))


def is_animated_rig_component(component: Any) -> bool:
    return (
        type(component) is dict
        and component.get("$type") == "entAnimatedComponent"
        and bool(depot_path_value(component, "rig"))
    )


def is_deformation_rig_component(component: Any) -> bool:
    if type(component) is not dict:
        return False
    name = component_name(component).lower()
    rig_path = depot_path_value(component, "rig").replace("\\", "/").lower()
    return (
        "deformation" in name
        or "/deformations_rig/" in rig_path
        or rig_path.endswith("_deformations.rig")
        or rig_path.endswith("_deformation.rig")
    )


def _promote_deformation_control_targets(
    components: Sequence[dict],
    control_targets: Mapping[int, str] | None = None,
) -> list[dict]:
    components = list(components or ())
    if len(components) < 2:
        return components

    component_by_name: dict[str, dict] = {}
    for component in components:
        name = component_name(component)
        if name:
            component_by_name.setdefault(name, component)

    authorities: list[dict] = []
    authority_ids: set[int] = set()
    targets = control_targets or {}
    for component in components:
        if not is_deformation_rig_component(component):
            continue
        target = component_by_name.get(targets.get(id(component), ""))
        if target is None or id(target) in authority_ids:
            continue
        authority_ids.add(id(target))
        authorities.append(target)

    if not authorities:
        return components
    return authorities + [
        component for component in components if id(component) not in authority_ids
    ]


def order_animated_rig_components(
    components: Sequence[dict],
    control_targets: Mapping[int, str] | None = None,
) -> tuple[list[dict], tuple[str, ...]]:
    components = list(components or ())
    count = len(components)
    if count < 2:
        return components, ()

    first_index_by_name: dict[str, int] = {}
    for index, component in enumerate(components):
        name = component_name(component)
        if name:
            first_index_by_name.setdefault(name, index)

    targets = control_targets or {}
    dependency_counts = [0] * count
    dependents: list[list[int]] = [[] for _ in range(count)]
    for index, component in enumerate(components):
        target_index = first_index_by_name.get(targets.get(id(component), ""))
        if target_index is None or target_index == index:
            continue
        dependency_counts[index] = 1
        dependents[target_index].append(index)

    ready = [index for index, value in enumerate(dependency_counts) if value == 0]
    heapq.heapify(ready)
    emitted = [False] * count
    result: list[dict] = []
    while ready:
        index = heapq.heappop(ready)
        if emitted[index]:
            continue
        emitted[index] = True
        result.append(components[index])
        for dependent_index in dependents[index]:
            dependency_counts[dependent_index] = 0
            if not emitted[dependent_index]:
                heapq.heappush(ready, dependent_index)

    messages: list[str] = []
    if len(result) != count:
        remaining = [
            component for index, component in enumerate(components) if not emitted[index]
        ]
        names = ", ".join(component_name(component, "<unnamed>") for component in remaining)
        messages.append(
            "animation control binding cycle detected; preserving source order for: " + names
        )
        result.extend(remaining)

    return _promote_deformation_control_targets(result, targets), tuple(messages)
