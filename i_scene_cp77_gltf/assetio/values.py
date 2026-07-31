from __future__ import annotations

from typing import Any


def cname_value(value: Any, default: Any = "") -> Any:
    """Return a CName payload while preserving legacy non-dict values."""
    if type(value) is dict:
        return value.get("$value", default)
    return value if value is not None else default


def cname_text(value: Any, default: str = "") -> str:
    """Return a CName payload normalized to text."""
    resolved = cname_value(value, default)
    return str(resolved or default)


def appearance_name(value: Any, default: str = "") -> str:
    return cname_text(value, default)


def first_dict_value(data: Any, *keys: str) -> dict:
    if not isinstance(data, dict):
        return {}
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def axis_value(data: Any, axis: str, default: Any = 0.0) -> Any:
    if not isinstance(data, dict):
        return default
    value = data.get(axis)
    if value is not None:
        return value
    value = data.get(axis.lower())
    if value is not None:
        return value
    properties = data.get("Properties")
    if isinstance(properties, dict):
        return axis_value(properties, axis, default)
    return default


def vector3(value: Any, default=(0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if not isinstance(value, dict):
        return tuple(float(component) for component in default)
    return tuple(
        float(axis_value(value, axis, default[index]))
        for index, axis in enumerate(("X", "Y", "Z"))
    )


def nested_dict(value: Any, *keys: str) -> dict:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def nested_value(value: Any, *keys: str, default: Any = "") -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default
