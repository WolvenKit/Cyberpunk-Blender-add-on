from __future__ import annotations

from ...assetio.paths import depot_path_key, strip_json_suffix


def phys_resource_key(path) -> str:
    value = depot_path_key(strip_json_suffix(str(path or "").strip()))
    return value if value.endswith(".phys") else ""


def phys_resource_matches(source, expected) -> bool:
    source_key = phys_resource_key(source)
    expected_key = phys_resource_key(expected)
    if not source_key or not expected_key:
        return False
    return source_key == expected_key or source_key.endswith(
        "/" + expected_key.lstrip("/")
    )


def normalize_phys_json_path(filepath) -> str:
    value = strip_json_suffix(filepath)
    if value.casefold().endswith(".phys"):
        value = value[:-5]
    return value + ".phys.json"
