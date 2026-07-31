from types import MappingProxyType

from .model import ParsedEntity
from ..common.entity_data import (
    build_chunk_handle_lookup,
    build_component_lookup,
    cname_value,
    component_name,
    resolve_requested_appearance_name,
)


def _build_app_lookup(appearances):
    by_appearance = {}
    by_name = {}
    appearance_names = []
    for index, app in enumerate(appearances or ()):
        if type(app) is not dict:
            continue
        appearance = cname_value(app.get("appearanceName"))
        if appearance:
            by_appearance.setdefault(appearance, index)
            appearance_names.append(appearance)
        name = cname_value(app.get("name"))
        if name:
            by_name.setdefault(name, index)
    return appearance_names, by_appearance, by_name


def _build_slot_lookup(slots):
    lookup = {}
    for slot in slots or ():
        if type(slot) is not dict:
            continue
        name = cname_value(slot.get("slotName"))
        if name:
            lookup.setdefault(name, slot)
    return lookup


def _build_slot_component_lookups(components):
    lookups = {}
    for component in components or ():
        if type(component) is not dict:
            continue
        name = component_name(component)
        slots = component.get("slots")
        if name and type(slots) is list:
            lookups.setdefault(name, _build_slot_lookup(slots))
    return lookups


def _components_by_type(components, type_name):
    return [
        component
        for component in components or ()
        if type(component) is dict and component.get("$type") == type_name
    ]


def _normalize_default_appearance(default_appearance, appearances, by_appearance, by_name):
    if not default_appearance or default_appearance == "None":
        return ""
    if default_appearance in by_appearance or default_appearance == "random":
        return default_appearance
    index = by_name.get(default_appearance, -1)
    if index >= 0:
        return cname_value(appearances[index].get("appearanceName"), default_appearance)
    return default_appearance


def parse_entity_document(data):
    root = data["Data"]["RootChunk"]
    compiled_data = root.get("compiledData")
    appearances = root.get("appearances") or []
    components = root.get("components") or []
    component_data = compiled_data.get("Data", {}).get("Chunks", []) if type(compiled_data) is dict else []
    appearance_names, by_appearance, by_name = _build_app_lookup(appearances)
    default_appearance = _normalize_default_appearance(
        cname_value(root.get("defaultAppearance")),
        appearances,
        by_appearance,
        by_name,
    )
    components_by_name = build_component_lookup(components)
    appearance_index_by_name = {}
    for index, name in enumerate(appearance_names):
        if name:
            appearance_index_by_name.setdefault(name, index)
    component_ids = {id(component) for component in components}
    component_data_ids = {id(component) for component in component_data}
    vehicle_slot_component = next(
        (
            component
            for component in components
            if component_name(component) in ("vehicle_slots", "slots")
        ),
        None,
    )
    return ParsedEntity(
        appearances=tuple(appearances),
        appearance_names=tuple(appearance_names),
        appearance_index_by_name=MappingProxyType(appearance_index_by_name),
        appearances_by_appearance=MappingProxyType(by_appearance),
        appearances_by_name=MappingProxyType(by_name),
        default_appearance=default_appearance,
        component_dicts=tuple(components),
        component_data=tuple(component_data),
        components_by_name=MappingProxyType(components_by_name),
        components_by_id=MappingProxyType({id(component): component for component in components}),
        component_ids=frozenset(component_ids),
        component_data_ids=frozenset(component_data_ids),
        parent_transform_lookup=MappingProxyType(build_chunk_handle_lookup(component_data, "parentTransform")),
        skinning_lookup=MappingProxyType(build_chunk_handle_lookup(component_data, "skinning")),
        shape_lookup=MappingProxyType(build_chunk_handle_lookup(component_data, "shape")),
        slot_component_lookups=MappingProxyType(_build_slot_component_lookups(components)),
        collider_components=tuple(_components_by_type(component_data, "entColliderComponent")),
        simple_collider_components=tuple(_components_by_type(component_data, "entSimpleColliderComponent")),
        light_channel_components=tuple(
            _components_by_type(component_data, "entLightChannelComponent")
            + _components_by_type(components, "entLightChannelComponent")
        ),
        resolved_dependencies=tuple(root.get("resolvedDependencies") or ()),
        vehicle_slot_component=vehicle_slot_component,
    )


def resolve_entity_appearance(parsed_entity, requested_app):
    if parsed_entity is None:
        return requested_app
    return resolve_requested_appearance_name(
        requested_app,
        parsed_entity.default_appearance,
        parsed_entity.appearances,
        parsed_entity.appearances_by_appearance,
        parsed_entity.appearances_by_name,
    )
