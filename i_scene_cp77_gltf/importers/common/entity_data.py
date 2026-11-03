from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ...assetio.values import cname_value


def component_name(component: Any, default: str = "") -> str:
    return cname_value(component.get("name"), default) if type(component) is dict else default


def build_component_lookup(components: Iterable[dict] | None) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for component in components or ():
        name = component_name(component)
        if name:
            lookup.setdefault(name, component)
    return lookup


def build_chunk_handle_lookup(
    chunks: Iterable[dict] | None,
    target_key: str,
    handle_key: str = "HandleId",
) -> dict[Any, dict]:
    lookup: dict[Any, dict] = {}
    for chunk in chunks or ():
        if type(chunk) is not dict:
            continue
        target = chunk.get(target_key)
        if type(target) is dict and handle_key in target:
            lookup[target[handle_key]] = target
    return lookup


def ent_appearance_name(ent_app: Any, default: str = "") -> str:
    return cname_value(ent_app.get("appearanceName"), default) if type(ent_app) is dict else default


def ent_template_appearance_name(ent_app: Any, default: str = "") -> str:
    return cname_value(ent_app.get("name"), default) if type(ent_app) is dict else default


def appearance_lookup_index(lookup: Mapping[str, Any] | None, key: str) -> int:
    if not key or not lookup:
        return -1
    try:
        return int(lookup.get(key, -1))
    except (TypeError, ValueError):
        return -1


def resolve_ent_appearance_alias(
    app_name: str,
    ent_apps: Sequence[dict],
    by_appearance: Mapping[str, Any] | None = None,
    by_name: Mapping[str, Any] | None = None,
) -> tuple[int, str]:
    if not app_name or app_name == "None":
        return -1, ""

    for lookup in (by_appearance, by_name):
        ent_app_idx = appearance_lookup_index(lookup, app_name)
        if 0 <= ent_app_idx < len(ent_apps):
            return ent_app_idx, ent_appearance_name(ent_apps[ent_app_idx], app_name)

    for ent_app_idx, ent_app in enumerate(ent_apps or ()):
        appearance = ent_appearance_name(ent_app)
        template_name = ent_template_appearance_name(ent_app)
        if app_name == appearance or app_name == template_name:
            return ent_app_idx, appearance or app_name

    return -1, ""


def resolve_requested_appearance_name(
    app_name: str,
    ent_default: str,
    ent_apps: Sequence[dict],
    by_appearance: Mapping[str, Any] | None,
    by_name: Mapping[str, Any] | None,
) -> str:
    if app_name == "default":
        if not ent_default:
            return "default"
        _, resolved_name = resolve_ent_appearance_alias(
            ent_default,
            ent_apps,
            by_appearance,
            by_name,
        )
        return resolved_name or ent_default

    _, resolved_name = resolve_ent_appearance_alias(
        app_name,
        ent_apps,
        by_appearance,
        by_name,
    )
    return resolved_name or app_name
