from __future__ import annotations

import os
<<<<<<< Updated upstream
from functools import lru_cache
from typing import Any


def normalize_depot_path(value: Any) -> str:
    return str(value or "").replace("\\", os.sep).replace("/", os.sep)


@lru_cache(maxsize=65536)
def path_key(value: str) -> str:
    if not value:
        return ""
    return os.path.normcase(os.path.normpath(str(value)))


norm_path_key = path_key


@lru_cache(maxsize=65536)
def depot_path_key(value: str) -> str:
    """Return a stable identity for an authored depot-relative path."""
    return str(value or "").replace("\\", "/").strip().lower()


@lru_cache(maxsize=65536)
def absolute_path_key(value: str) -> str:
    if not value:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(value)))


def same_path(left: str, right: str) -> bool:
    return path_key(left) == path_key(right)


def trim_name(name: Any, max_len: int = 63) -> str:
    return str(name)[: int(max_len)]


def _raw_depot_path_from_value(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    depot_path = value.get("DepotPath")
    if isinstance(depot_path, dict):
        return str(depot_path.get("$value", "") or "")
    if isinstance(depot_path, str):
        return depot_path
    return str(value.get("$value", "") or "")


def depot_path_from_value(value: Any, *, normalize: bool = True) -> str:
    resolved = _raw_depot_path_from_value(value)
    return normalize_depot_path(resolved) if normalize else resolved
=======
from typing import Any

from ...assetio.paths import depot_to_local_fragment
from ...assetio.values import resource_path_text


def depot_path_from_value(value: Any, *, normalize: bool = True) -> str:
    resolved = resource_path_text(value)
    return depot_to_local_fragment(resolved) if normalize else resolved
>>>>>>> Stashed changes


def depot_path(data: Any, *keys: str, normalize: bool = True) -> str:
    if not isinstance(data, dict):
        return ""
    for key in keys:
        resolved = depot_path_from_value(data.get(key), normalize=normalize)
        if resolved:
            return resolved
    return ""


<<<<<<< Updated upstream
def depot_path_value(data: Any, *keys: str) -> str:
    """Return an authored depot path without filesystem normalization."""
    return depot_path(data, *keys, normalize=False)


def depot_to_local_path(root: str, depot: str) -> str:
    return os.path.join(root, depot).replace("\\", os.sep) if depot else ""


def expected_resource_path(raw_root: str, depot: str, *, append_json: bool = True) -> str:
    path = os.path.join(raw_root, normalize_depot_path(depot))
=======
def depot_to_local_path(root: str, depot: str) -> str:
    return os.path.join(root, depot_to_local_fragment(depot)) if depot else ""


def expected_resource_path(
    raw_root: str, depot: str, *, append_json: bool = True
) -> str:
    path = os.path.join(raw_root, depot_to_local_fragment(depot))
>>>>>>> Stashed changes
    if append_json and path and not path.lower().endswith(".json"):
        path = f"{path}.json"
    return path
