from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....assetio.paths import local_path_key
from ....assetio.values import cname_text
from .topology import handle_index


def source_path_key(path: Any) -> str:
    text = str(path or "").strip()
    return local_path_key(text) if text else ""


def graph_animation_names(source_payload: Mapping[str, Any]) -> frozenset[str]:
    names = set()
    for node in handle_index(source_payload).values():
        if not isinstance(node, Mapping) or "animation" not in node:
            continue
        name = cname_text(node.get("animation"))
        if name and name != "None":
            names.add(str(name))
    return frozenset(names)


def available_animation_names(
    source_payload: Mapping[str, Any],
    actions: Any,
    *,
    source_path_property: str = "sourcePath",
) -> frozenset[str]:
    graph_names = graph_animation_names(source_payload)
    if actions is None:
        return frozenset()

    source_paths = set()
    for name in graph_names:
        action = actions.get(name) if hasattr(actions, "get") else None
        if action is None or not hasattr(action, "get"):
            continue
        key = source_path_key(action.get(source_path_property, ""))
        if key:
            source_paths.add(key)

    if not source_paths:
        return frozenset(
            name
            for name in graph_names
            if hasattr(actions, "get") and actions.get(name) is not None
        )

    try:
        candidates = tuple(actions)
    except TypeError:
        candidates = ()
    if candidates and isinstance(candidates[0], str) and hasattr(actions, "values"):
        candidates = tuple(actions.values())

    available = set()
    for action in candidates:
        if not hasattr(action, "get"):
            continue
        key = source_path_key(action.get(source_path_property, ""))
        if key in source_paths:
            name = str(getattr(action, "name", "") or "")
            if name:
                available.add(name)
    return frozenset(available)
