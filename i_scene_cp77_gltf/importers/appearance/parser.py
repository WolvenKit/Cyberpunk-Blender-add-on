from types import MappingProxyType

from .model import ParsedAppearance
from ..common.entity_data import build_chunk_handle_lookup
from ...assetio.values import cname_value


def _components_by_type(components, type_name):
    return [
        component
        for component in components or ()
        if type(component) is dict and component.get("$type") == type_name
    ]


def parse_appearance_document(data):
    root = data["Data"]["RootChunk"]
    appearances = root.get("appearances") or []
    names = []
    by_name = {}
    components_by_name = {}
    chunks_by_name = {}
    parent_by_name = {}
    skinning_by_name = {}
    shape_by_name = {}
    light_by_name = {}
    for index, appearance in enumerate(appearances):
        if type(appearance) is not dict:
            continue
        app_data = appearance.get("Data") if type(appearance.get("Data")) is dict else {}
        name = cname_value(app_data.get("name"), str(index))
        names.append(name)
        by_name[name] = index
        components = app_data.get("components") or []
        compiled_data = app_data.get("compiledData")
        chunks = compiled_data.get("Data", {}).get("Chunks", []) if type(compiled_data) is dict else []
        components_by_name[name] = components
        chunks_by_name[name] = chunks
        parent_by_name[name] = build_chunk_handle_lookup(chunks, "parentTransform")
        skinning_by_name[name] = build_chunk_handle_lookup(chunks, "skinning")
        shape_by_name[name] = build_chunk_handle_lookup(chunks, "shape")
        light_by_name[name] = (
            _components_by_type(chunks, "entLightChannelComponent")
            + _components_by_type(components, "entLightChannelComponent")
        )
    return ParsedAppearance(
        appearances=tuple(appearances),
        appearance_names=tuple(names),
        appearances_by_name=MappingProxyType(by_name),
        components_by_appearance_name=MappingProxyType({key: tuple(value) for key, value in components_by_name.items()}),
        chunks_by_appearance_name=MappingProxyType({key: tuple(value) for key, value in chunks_by_name.items()}),
        parent_transform_lookup_by_appearance_name=MappingProxyType({key: MappingProxyType(value) for key, value in parent_by_name.items()}),
        skinning_lookup_by_appearance_name=MappingProxyType({key: MappingProxyType(value) for key, value in skinning_by_name.items()}),
        shape_lookup_by_appearance_name=MappingProxyType({key: MappingProxyType(value) for key, value in shape_by_name.items()}),
        light_channels_by_appearance_name=MappingProxyType({key: tuple(value) for key, value in light_by_name.items()}),
    )
