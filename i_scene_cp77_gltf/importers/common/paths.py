from __future__ import annotations

import os

from ...assetio.paths import depot_to_local_fragment


def depot_to_local_path(root: str, depot: str) -> str:
    return os.path.join(root, depot_to_local_fragment(depot)) if depot else ""


def expected_resource_path(
    raw_root: str, depot: str, *, append_json: bool = True
) -> str:
    path = os.path.join(raw_root, depot_to_local_fragment(depot))
    if append_json and path and not path.lower().endswith(".json"):
        path = f"{path}.json"
    return path
