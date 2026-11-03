from __future__ import annotations

<<<<<<< Updated upstream
from typing import Any


def cname_value(value: Any, default: Any = "") -> Any:
    """Return a CName payload while preserving legacy non-dict values."""
    if type(value) is dict:
        return value.get("$value", default)
    return value if value is not None else default


def cname_text(value: Any, default: str = "") -> str:
    """Return a CName payload normalized to text."""
=======
import copy
import json
import math
from collections.abc import Mapping
from typing import Any

from ..bartmoss.single import f32


def handle_data(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    data = value.get("Data")
    return data if isinstance(data, dict) else value


def strict_handle_data(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    data = value.get("Data", value)
    return data if isinstance(data, dict) else {}


def handle_id(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("HandleId", "") or value.get("HandleRefId", "") or "")


def cname_value(value: Any, default: Any = "") -> Any:
    """Return a CName payload from mapping and scalar encodings"""
    if type(value) is dict:
        if "$value" in value:
            return value["$value"]
        if "value" in value:
            return value["value"]
        return default
    return value if value is not None else default


def cname_entry(name: Any, template: Any = None) -> dict:
    """The document form of a CName"""
    if isinstance(template, dict):
        entry = copy.deepcopy(template)
        entry["$value"] = name
        return entry
    return {"$type": "CName", "$storage": "string", "$value": name}


def cname_text(value: Any, default: str = "") -> str:
    """Return a CName payload normalized to text"""
>>>>>>> Stashed changes
    resolved = cname_value(value, default)
    return str(resolved or default)


<<<<<<< Updated upstream
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
=======
_WRAPPER_KEYS = ("Value", "value", "$value")


def unwrapped(value: Any, keys=_WRAPPER_KEYS) -> Any:
    """value with WolvenKit's wrapped forms opened as deep as they nest"""
    while isinstance(value, Mapping):
        for key in keys:
            if key in value:
                value = value[key]
                break
        else:
            return value
    return value


def coerce_float(
    value: Any, default: float = 0.0, *, unwrap: bool = True, finite: bool = True
) -> float:
    """value as a float"""
    if unwrap:
        value = unwrapped(value)
    if isinstance(value, Mapping):
        return float(default)
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError):
        return float(default)
    if finite and not math.isfinite(result):
        return float(default)
    return result


def coerce_int(value: Any, default: int = 0, *, unwrap: bool = True) -> int:
    """value as an int"""
    if unwrap:
        value = unwrapped(value)
    try:
        return int(value)
    except (OverflowError, TypeError, ValueError):
        return int(default)


def vector2(value: Any, default=(0.0, 0.0)) -> tuple[float, float]:
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        x, y = value[0], value[1]
    elif isinstance(value, dict):
        x, y = value.get("X", default[0]), value.get("Y", default[1])
    else:
        return float(default[0]), float(default[1])
    result = (
        coerce_float(x, float("nan"), unwrap=False),
        coerce_float(y, float("nan"), unwrap=False),
    )
    # One unusable component makes the whole vector unusable.
    if not all(math.isfinite(component) for component in result):
        return float(default[0]), float(default[1])
    return result
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
=======


def build_embedded_handle_lookup(components, key: str) -> dict[Any, dict]:
    lookup: dict[Any, dict] = {}
    for component in components or ():
        value = component.get(key) if type(component) is dict else None
        if type(value) is not dict:
            continue
        handle = value.get("HandleId")
        if handle is not None and type(value.get("Data")) is dict:
            lookup[handle] = value
    return lookup


# Not HandleIndex: the first handle of an id wins here, references can be component-scoped, typed inline values count.
def collect_handle_data(value: Any, lookup: dict) -> None:
    if isinstance(value, dict):
        data = value.get("Data")
        handle = value.get("HandleId")
        if handle is not None and isinstance(data, dict):
            lookup.setdefault(handle, data)
            lookup.setdefault(str(handle), data)
        for child in value.values():
            collect_handle_data(child, lookup)
    elif isinstance(value, (list, tuple)):
        for child in value:
            collect_handle_data(child, lookup)


def resolve_handle_reference(value: Any, lookup=None, component=None):
    if not isinstance(value, dict):
        return None
    data = value.get("Data")
    if isinstance(data, dict):
        return data
    handle_ref = value.get("HandleRefId")
    if handle_ref is not None and lookup is not None:
        if component is not None and hasattr(lookup, "get_for_component"):
            referenced = lookup.get_for_component(component, handle_ref)
        else:
            referenced = lookup.get(handle_ref)
            if referenced is None:
                referenced = lookup.get(str(handle_ref))
        if isinstance(referenced, dict) and isinstance(referenced.get("Data"), dict):
            return referenced["Data"]
        if isinstance(referenced, dict):
            return referenced
    return value if "$type" in value else None


def resolve_component_handle_data(component: dict, lookup, key: str) -> dict | None:
    value = component.get(key) if type(component) is dict else None
    if type(value) is not dict:
        return None
    data = value.get("Data")
    if type(data) is dict:
        return data
    handle = value.get("HandleId")
    resolved = lookup.get(handle) if lookup is not None and handle is not None else None
    if type(resolved) is dict and type(resolved.get("Data")) is dict:
        return resolved["Data"]
    return None


def field_float(data, key, default=0.0):
    value = data.get(key, default) if isinstance(data, dict) else default
    if isinstance(value, dict):
        value = value.get("$value", default)
    return coerce_float(value, default, unwrap=False)


COLOR_CHANNELS = ("Red", "Green", "Blue", "Alpha")


def color_bytes(
    color: Any, default: float = 255.0, count: int = 3
) -> tuple[float, ...]:
    """The first count channels of a game Color as the 0-255 numbers it holds"""
    return tuple(
        field_float(color, channel, default) for channel in COLOR_CHANNELS[:count]
    )


def plain_value(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict) or hasattr(value, "keys"):
        return {str(key): plain_value(value[key]) for key in value}
    try:
        return [plain_value(item) for item in value]
    except TypeError:
        return str(value)


def json_text(value: Any) -> str:
    """Compact, key-sorted JSON text that keeps non-ASCII characters"""
    return json.dumps(
        value,
        default=plain_value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def json_object(payload: Any) -> dict:
    """The JSON object stored as payload text"""
    try:
        value = json.loads(str(payload or "{}"))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def json_array(payload: Any) -> list:
    """The JSON array stored as payload text"""
    try:
        value = json.loads(str(payload or "[]"))
    except (TypeError, ValueError):
        return []
    return list(value) if isinstance(value, list) else []


def cname_or_empty(value: Any) -> str:
    """A CName as text, with the null CName 'None' as ''"""
    text = cname_text(value)
    return "" if text == "None" else text


def float32_entry(value: float) -> int | float:
    """The document form of a float field"""
    printed = float(f"{f32(float(value)):.9g}")
    return int(printed) if printed.is_integer() else printed


def resource_path_entry(depot_path: str, flags: str = "Default") -> dict:
    """The document form of a resource reference to depot_path"""
    return {
        "DepotPath": {
            "$type": "ResourcePath",
            "$storage": "string",
            "$value": str(depot_path),
        },
        "Flags": flags,
    }


def resource_path_text(value: Any) -> str:
    """The depot path a resource reference names, or ''"""
    if not isinstance(value, Mapping):
        return ""
    depot = value.get("DepotPath")
    if isinstance(depot, Mapping):
        text = cname_or_empty(depot)
    else:
        text = (
            cname_or_empty(depot)
            if depot is not None
            else cname_or_empty(value.get("$value"))
        )
    return "" if text == "0" else text
>>>>>>> Stashed changes
