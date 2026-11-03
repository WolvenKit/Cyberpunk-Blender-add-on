from __future__ import annotations

import os
from typing import Any

from ...assetio.paths import depot_to_local_fragment
from ...assetio.values import resource_path_text


def depot_path_from_value(value: Any, *, normalize: bool = True) -> str:
    resolved = resource_path_text(value)
    return depot_to_local_fragment(resolved) if normalize else resolved


def depot_path(data: Any, *keys: str, normalize: bool = True) -> str:
    if not isinstance(data, dict):
        return ""
    for key in keys:
        resolved = depot_path_from_value(data.get(key), normalize=normalize)
        if resolved:
            return resolved
    return ""


def depot_to_local_path(root: str, depot: str) -> str:
    return os.path.join(root, depot_to_local_fragment(depot)) if depot else ""


def expected_resource_path(
    raw_root: str, depot: str, *, append_json: bool = True
) -> str:
    path = os.path.join(raw_root, depot_to_local_fragment(depot))
    if append_json and path and not path.lower().endswith(".json"):
        path = f"{path}.json"
    return path
