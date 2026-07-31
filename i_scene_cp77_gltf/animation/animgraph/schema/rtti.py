from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import metadata, enums
from .type_utils import unwrap_indirect_type
from ...animgraph_constants import ANIM_NODE_PREFIX


LINK_TYPES = metadata.LINK_TYPES
VARIADIC_AUTHORING_SEED = 2


@dataclass(frozen=True)
class InputFieldDef:
    json_path: str
    caption: str
    link_type: str
    field_name: str
    is_array: bool = False
    array_index: int = -1


@dataclass(frozen=True)
class PropertyDef:
    name: str
    red_type: str
    value_kind: str
    default: Any
    label: str
    enum_type: str = ""
    is_flags: bool = False
    is_array: bool = False
    element_type: str = ""
    is_hidden: bool = False
    is_link: bool = False
    source: str = "rtti"


@dataclass(frozen=True)
class ClassDefinition:
    red_type: str
    parent_chain: Tuple[str, ...]
    properties: Tuple[PropertyDef, ...]
    is_graph_node: bool
    is_owned_payload: bool
    is_abstract: bool
    metadata_known: bool


@dataclass(frozen=True)
class NodeDefinition:
    red_type: str
    short_name: str
    parent_chain: Tuple[str, ...]
    output_link_type: Optional[str]
    input_fields: Tuple[InputFieldDef, ...]
    properties: Tuple[PropertyDef, ...]
    category: str
    is_container: bool
    is_abstract: bool
    metadata_known: bool


def full_name(name_or_short: str) -> str:
    return metadata.full_name(name_or_short)


def short_name(name_or_full: str) -> str:
    return metadata.short_name(name_or_full)


def has_metadata() -> bool:
    return metadata.has_metadata()


def has_class(name_or_short: str) -> bool:
    return metadata.has_class(name_or_short)


def require_class(name_or_short: str) -> dict:
    rec = metadata.get_class(name_or_short)
    if rec is None:
        raise KeyError(f"Unknown REDengine RTTI class: {name_or_short}")
    return rec


def is_graph_node_class(name_or_short: str) -> bool:
    return str(full_name(name_or_short) or '').startswith(ANIM_NODE_PREFIX)


def is_known_struct_or_payload_type(type_name: str) -> bool:
    t = unwrap_indirect_type(type_name)
    return bool(t and has_class(t) and not is_graph_node_class(t))


def is_owned_payload_class(name_or_short: str) -> bool:
    return bool(has_class(name_or_short) and not is_graph_node_class(name_or_short))


def parent_of(name_or_short: str) -> str:
    return metadata.parent_of(name_or_short)


def parent_chain(name_or_short: str, *, include_self: bool = True) -> Tuple[str, ...]:
    return tuple(metadata.parent_chain(name_or_short, include_self=include_self))


def all_properties(name_or_short: str) -> Tuple[dict, ...]:
    return tuple(metadata.all_properties(name_or_short))


def declared_properties(name_or_short: str) -> Tuple[dict, ...]:
    return tuple(metadata.declared_properties(name_or_short))


def property_type_map(name_or_short: str) -> Dict[str, str]:
    return metadata.property_type_map(name_or_short)


def ordered_field_names(name_or_short: str, actual_keys: Iterable[str]) -> List[str]:
    return metadata.ordered_field_names(name_or_short, actual_keys)


def is_hidden_field(field_name: str) -> bool:
    return metadata._is_hidden_field(field_name)


def is_link_type(type_name: str) -> bool:
    return metadata.is_link_type(type_name)


def link_kind_from_type(type_name: str) -> Optional[str]:
    return metadata.link_kind_from_type(type_name)


def output_kind(name_or_short: str) -> Optional[str]:
    return metadata.output_kind(name_or_short)


def is_container(name_or_short: str) -> bool:
    return metadata.is_container(name_or_short)


def is_abstract(name_or_short: str) -> bool:
    return metadata.is_abstract(name_or_short)


def available_node_types(*, concrete_only: bool = True) -> Tuple[str, ...]:
    return tuple(metadata.all_node_short_names(concrete_only=concrete_only))


def _friendly(field: str) -> str:
    if not field:
        return field
    text = str(field)
    out = [text[0].upper()]
    for ch in text[1:]:
        if ch == '_':
            out.append(' ')
            continue
        if ch.isupper() and out and out[-1] != ' ':
            out.append(' ')
        out.append(ch)
    friendly = ''.join(out)
    for suffix in (" Link", " Node"):
        if friendly.endswith(suffix):
            return friendly[:-len(suffix)]
    return friendly


def _split_path(path: str) -> Tuple[str, int, bool]:
    tail = str(path or '').rsplit('.', 1)[-1]
    if '[' in tail and tail.endswith(']'):
        base, rest = tail.split('[', 1)
        try:
            return base, int(rest[:-1]), True
        except Exception:
            return base, -1, True
    return tail.split('[', 1)[0], -1, False


def input_socket_definitions(name_or_short: str, *, seed_array_inputs: bool = True) -> Tuple[InputFieldDef, ...]:
    defs: List[InputFieldDef] = []
    for field_name, link_type, is_array in metadata.input_link_fields(name_or_short):
        if is_array and seed_array_inputs:
            for idx in range(VARIADIC_AUTHORING_SEED):
                path = f"{field_name}[{idx}]"
                defs.append(InputFieldDef(
                    json_path=path,
                    caption=str(idx),
                    link_type=link_type,
                    field_name=field_name,
                    is_array=True,
                    array_index=idx,
                ))
        else:
            field, idx, path_is_array = _split_path(field_name)
            defs.append(InputFieldDef(
                json_path=field_name,
                caption=_friendly(field_name),
                link_type=link_type,
                field_name=field,
                is_array=is_array or path_is_array,
                array_index=idx,
            ))
    return tuple(defs)


def resolve_enum_type(type_name: str = '', *, field_name: str = '', parent_type: str = '', json_path: str = '', value: Any = None) -> str:
    return enums.resolve_enum_type(type_name, field_name=field_name, parent_type=parent_type, json_path=json_path, value=value)


def has_enum(enum_type: str) -> bool:
    return enums.has_enum(enum_type)


def is_flag_enum(enum_type: str) -> bool:
    return enums.is_flags(enum_type)


def enum_items(enum_type: str, *, include_sentinel: bool = False):
    return enums.enum_items(enum_type, include_sentinel=include_sentinel)


def enum_options(enum_type: str, *, include_sentinel: bool = False):
    return enums.options(enum_type, include_sentinel=include_sentinel)


def enum_default(enum_type: str) -> str:
    opts = enums.options(enum_type, include_sentinel=False)
    if not opts:
        return ''
    return sorted(opts.items(), key=lambda kv: int(kv[1]))[0][0]


def enum_value_for_name(enum_type: str, option_name: str):
    return enums.value_for_name(enum_type, option_name)


def enum_normalize_choice(enum_type: str, value: Any) -> str:
    return enums.normalize_choice(enum_type, value)


def enum_decoded_value_text(enum_type: str, value: Any) -> str:
    return enums.decoded_value_text(enum_type, value)


def enum_encode_value(enum_type: str, value_text: Any, *, storage: str = 'name', raw_value: Any = '') -> Any:
    return enums.encode_value(enum_type, value_text, storage=storage, raw_value=raw_value)


def flags_summary(enum_type: str, value_text: Any, raw_value: Any = '') -> str:
    return enums.flags_summary(enum_type, value_text, raw_value)


def _default_for_array(element_type: str) -> list:
    return []


def property_kind_from_type(type_name: str, *, field_name: str = '', parent_type: str = '', json_path: str = '', value: Any = None) -> Tuple[str, Any, str, str, bool, str]:
    """Return editable property metadata for a REDengine type string."""
    t = str(type_name or '')
    enum_type = resolve_enum_type(t, field_name=field_name, parent_type=parent_type, json_path=json_path, value=value)
    if enum_type:
        is_flags = is_flag_enum(enum_type)
        return ('FLAGS_ENUM' if is_flags else 'ENUM'), enum_default(enum_type), t or enum_type, enum_type, is_flags, ''
    if t.startswith('array:'):
        inner = t[len('array:'):]
        return 'ARRAY', _default_for_array(inner), t, '', False, inner
    if t in {'Bool'}:
        return 'BOOL', False, t, '', False, ''
    if t in {'Int8', 'Int16', 'Int32', 'Int64'}:
        return 'INT', 0, t, '', False, ''
    if t in {'Uint8', 'Uint16', 'Uint32', 'Uint64'}:
        return 'UINT', 0, t, '', False, ''
    if t in {'Float', 'Double'}:
        return 'FLOAT', 0.0, t, '', False, ''
    if t == 'String':
        return 'STRING', '', t, '', False, ''
    if t == 'CName':
        return 'CNAME', 'None', t, '', False, ''
    if t == 'animTransformIndex':
        return 'TRANSFORM_INDEX', 'None', t, '', False, ''
    if t == 'animNamedTrackIndex':
        return 'NAMED_TRACK_INDEX', 'None', t, '', False, ''
    if t == 'animVisualTagCondition':
        return 'VISUAL_TAG_CONDITION', 'None', t, '', False, ''
    if t == 'animFloatClamp':
        return 'FLOAT_CLAMP', (0.0, 1.0), t, '', False, ''
    if t == 'Vector2':
        return 'VECTOR2', (0.0, 0.0), t, '', False, ''
    if t in {'Vector3', 'EulerAngles'}:
        return 'VECTOR3', (0.0, 0.0, 0.0), t, '', False, ''
    if t == 'Vector4':
        return 'VECTOR4', (0.0, 0.0, 0.0, 0.0), t, '', False, ''
    if t == 'Quaternion':
        return 'QUATERNION', (0.0, 0.0, 0.0, 1.0), t, '', False, ''
    if t == 'QsTransform':
        return 'QSTRANSFORM', {
            '$type': 'QsTransform',
            'Rotation': {'$type': 'Quaternion', 'i': 0.0, 'j': 0.0, 'k': 0.0, 'r': 1.0},
            'Scale': {'$type': 'Vector4', 'X': 1.0, 'Y': 1.0, 'Z': 1.0, 'W': 1.0},
            'Translation': {'$type': 'Vector4', 'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'W': 1.0},
        }, t, '', False, ''
    if t == 'curveData:Float':
        return 'CURVE_FLOAT', metadata.DEFAULT_FLOAT_CURVE, t, '', False, ''
    if t.startswith('handle:') or t.startswith('rRef:'):
        inner = unwrap_indirect_type(t)
        if has_class(inner) and not is_graph_node_class(inner):
            return 'HANDLE_STRUCT', {}, t, '', False, inner
        return 'RAW_JSON', None, t, '', False, inner
    if not t:
        return 'RAW_JSON', None, t, '', False, ''
    if has_class(t) and not is_graph_node_class(t):
        return 'STRUCT', {}, t, '', False, t

    return 'RAW_JSON', {}, t, '', False, ''


def property_definition_for_field(parent_type: str, field_name: str) -> Optional[PropertyDef]:
    for prop in property_definitions(parent_type):
        if prop.name == field_name:
            return prop
    return None


def property_definitions(name_or_short: str) -> Tuple[PropertyDef, ...]:
    red_type = full_name(name_or_short)
    defs: List[PropertyDef] = []
    for prop in metadata.all_properties(red_type):
        name = str(prop.get('name', ''))
        ptype = str(prop.get('type', ''))
        if not name:
            continue
        hidden = is_hidden_field(name)
        is_link = metadata.is_link_type(ptype)
        if hidden or is_link:
            continue
        kind, default, red_type_hint, enum_type, is_flags, element_type = property_kind_from_type(
            ptype, field_name=name, parent_type=red_type, json_path=name, value=None)
        defs.append(PropertyDef(
            name=name,
            red_type=red_type_hint or ptype,
            value_kind=kind,
            default=default,
            label=_friendly(name),
            enum_type=enum_type,
            is_flags=is_flags,
            is_array=ptype.startswith('array:'),
            element_type=element_type,
            is_hidden=False,
            is_link=False,
            source='rtti',
        ))
    return tuple(defs)


@lru_cache(maxsize=None)
def class_definition(name_or_short: str) -> ClassDefinition:
    red_type = full_name(name_or_short)
    require_class(red_type)
    return ClassDefinition(
        red_type=red_type,
        parent_chain=parent_chain(red_type, include_self=True),
        properties=property_definitions(red_type),
        is_graph_node=is_graph_node_class(red_type),
        is_owned_payload=is_owned_payload_class(red_type),
        is_abstract=is_abstract(red_type),
        metadata_known=True,
    )


@lru_cache(maxsize=None)
def node_definition(name_or_short: str) -> NodeDefinition:
    red_type = full_name(name_or_short)
    require_class(red_type)
    short = short_name(red_type)
    return NodeDefinition(
        red_type=red_type,
        short_name=short,
        parent_chain=parent_chain(red_type, include_self=True),
        output_link_type=output_kind(red_type),
        input_fields=input_socket_definitions(red_type, seed_array_inputs=True),
        properties=property_definitions(red_type),
        category="",
        is_container=is_container(red_type),
        is_abstract=is_abstract(red_type),
        metadata_known=True,
    )


def available_node_definitions(*, concrete_only: bool = True) -> Tuple[NodeDefinition, ...]:
    return tuple(node_definition(short) for short in available_node_types(concrete_only=concrete_only))


def stats() -> dict:
    meta = metadata.stats()
    estats = enums.summary()
    all_defs = available_node_definitions(concrete_only=False) if metadata.has_metadata() else ()
    return {
        'metadata_loaded': bool(meta.get('loaded')),
        'classes': int(meta.get('classes', 0) or 0),
        'anim_nodes': int(meta.get('anim_nodes', 0) or 0),
        'concrete_anim_nodes': int(meta.get('concrete_anim_nodes', 0) or 0),
        'link_properties': int(meta.get('link_properties', 0) or 0),
        'curve_float_properties': int(meta.get('curve_float_properties', 0) or 0),
        'node_definitions': len(all_defs),
        'enum_definitions': int(estats.get('enums', 0) or 0),
        'flag_enums': int(estats.get('flag_enums', 0) or 0),
    }
