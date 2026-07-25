from __future__ import annotations

from typing import Any, Iterable, Mapping


def build_embedded_handle_lookup(
    components: Iterable[dict] | None,
    key: str,
) -> dict[Any, dict]:
    lookup: dict[Any, dict] = {}
    for component in components or ():
        value = component.get(key) if type(component) is dict else None
        if type(value) is not dict:
            continue
        handle_id = value.get("HandleId")
        if handle_id is not None and type(value.get("Data")) is dict:
            lookup[handle_id] = value
    return lookup


def resolve_component_handle_data(
    component: dict,
    lookup: Mapping[Any, dict] | None,
    key: str,
) -> dict | None:
    value = component.get(key) if type(component) is dict else None
    if type(value) is not dict:
        return None
    data = value.get("Data")
    if type(data) is dict:
        return data
    handle_id = value.get("HandleId")
    resolved = lookup.get(handle_id) if lookup is not None and handle_id is not None else None
    if type(resolved) is dict and type(resolved.get("Data")) is dict:
        return resolved["Data"]
    return None


def collect_handle_data(value: Any, lookup: dict) -> None:
    if isinstance(value, dict):
        data = value.get("Data")
        handle_id = value.get("HandleId")
        if handle_id is not None and isinstance(data, dict):
            lookup.setdefault(handle_id, data)
            lookup.setdefault(str(handle_id), data)
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


def resolve_handle_data(value: Any, lookup):
    return resolve_handle_reference(value, lookup)
