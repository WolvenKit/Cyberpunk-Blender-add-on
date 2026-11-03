from types import MappingProxyType

from ...assetio.values import cname_value
from ..common.entity_data import component_name
from .model import ParsedEntity


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


def _index_components(components, component_data):
    components_by_name = {}
    all_components_by_name = {}
    slot_component_lookups = {}
    slot_components = []
    component_ids = set()
    component_data_ids = set()
    root_light_channels = []
    data_light_channels = []
    collider_components = []
    simple_collider_components = []
    vehicle_slot_component = None
    parent_transform_lookup = {}
    skinning_lookup = {}
    shape_lookup = {}

    for component in components or ():
        if type(component) is not dict:
            continue
        component_ids.add(id(component))
        name = component_name(component)
        if name:
            components_by_name.setdefault(name, component)
            all_components_by_name.setdefault(name, component)
            if vehicle_slot_component is None and name in ("vehicle_slots", "slots"):
                vehicle_slot_component = component
        slots = component.get("slots")
        if type(slots) is list:
            slot_components.append(component)
            if name and name not in slot_component_lookups:
                slot_component_lookups[name] = _build_slot_lookup(slots)
        if component.get("$type") == "entLightChannelComponent":
            root_light_channels.append(component)

    for component in component_data or ():
        if type(component) is not dict:
            continue
        component_data_ids.add(id(component))
        name = component_name(component)
        if name:
            all_components_by_name.setdefault(name, component)
        component_type = component.get("$type")
        if component_type == "entColliderComponent":
            collider_components.append(component)
        elif component_type == "entSimpleColliderComponent":
            simple_collider_components.append(component)
        elif component_type == "entLightChannelComponent":
            data_light_channels.append(component)
        for key, lookup in (
            ("parentTransform", parent_transform_lookup),
            ("skinning", skinning_lookup),
            ("shape", shape_lookup),
        ):
            target = component.get(key)
            if type(target) is dict and "HandleId" in target:
                lookup[target["HandleId"]] = target

    return {
        "components_by_name": components_by_name,
        "all_components_by_name": all_components_by_name,
        "slot_component_lookups": slot_component_lookups,
        "slot_components": tuple(slot_components),
        "component_ids": frozenset(component_ids),
        "component_data_ids": frozenset(component_data_ids),
        "parent_transform_lookup": parent_transform_lookup,
        "skinning_lookup": skinning_lookup,
        "shape_lookup": shape_lookup,
        "collider_components": tuple(collider_components),
        "simple_collider_components": tuple(simple_collider_components),
        "light_channel_components": tuple(data_light_channels + root_light_channels),
        "vehicle_slot_component": vehicle_slot_component,
    }


def _normalize_default_appearance(
    default_appearance, appearances, by_appearance, by_name
):
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
    component_data = (
        compiled_data.get("Data", {}).get("Chunks", [])
        if type(compiled_data) is dict
        else []
    )
    appearance_names, by_appearance, by_name = _build_app_lookup(appearances)
    default_appearance = _normalize_default_appearance(
        cname_value(root.get("defaultAppearance")),
        appearances,
        by_appearance,
        by_name,
    )
    all_components = tuple(components) + tuple(component_data)
    indexed = _index_components(components, component_data)
    return ParsedEntity(
        appearances=tuple(appearances),
        appearance_names=tuple(appearance_names),
        appearances_by_appearance=MappingProxyType(by_appearance),
        appearances_by_name=MappingProxyType(by_name),
        default_appearance=default_appearance,
        component_dicts=tuple(components),
        component_data=tuple(component_data),
        all_components=all_components,
        components_by_name=MappingProxyType(indexed["components_by_name"]),
        all_components_by_name=MappingProxyType(indexed["all_components_by_name"]),
        components_by_id=MappingProxyType(
            {id(component): component for component in components}
        ),
        slot_components=indexed["slot_components"],
        component_ids=indexed["component_ids"],
        component_data_ids=indexed["component_data_ids"],
        parent_transform_lookup=MappingProxyType(indexed["parent_transform_lookup"]),
        skinning_lookup=MappingProxyType(indexed["skinning_lookup"]),
        shape_lookup=MappingProxyType(indexed["shape_lookup"]),
        slot_component_lookups=MappingProxyType(indexed["slot_component_lookups"]),
        collider_components=indexed["collider_components"],
        simple_collider_components=indexed["simple_collider_components"],
        light_channel_components=indexed["light_channel_components"],
        resolved_dependencies=tuple(root.get("resolvedDependencies") or ()),
        vehicle_slot_component=indexed["vehicle_slot_component"],
    )
