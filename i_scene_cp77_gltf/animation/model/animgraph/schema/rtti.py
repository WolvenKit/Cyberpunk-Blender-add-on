from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Any

from ..constants import ANIM_NODE_PREFIX
from . import enums, registry
from .type_utils import unwrap_indirect_type

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
class NodeDefinition:
    red_type: str
    short_name: str
    parent_chain: tuple[str, ...]
    output_link_type: str | None
    input_fields: tuple[InputFieldDef, ...]
    properties: tuple[PropertyDef, ...]
    category: str
    is_container: bool
    is_abstract: bool
    metadata_known: bool


def require_class(name_or_short: str) -> dict:
    rec = registry.get_class(name_or_short)
    if rec is None:
        raise KeyError(f"Unknown REDengine RTTI class: {name_or_short}")
    return rec


def is_graph_node_type(type_name: str) -> bool:
    """Whether a serialized $type is an animAnimNode_Base descendant"""
    text = str(type_name or "")
    return text.startswith(ANIM_NODE_PREFIX) and registry.is_node_class(text)


def _split_path(path: str) -> tuple[str, int, bool]:
    tail = str(path or "").rsplit(".", 1)[-1]
    if "[" in tail and tail.endswith("]"):
        base, rest = tail.split("[", 1)
        try:
            return base, int(rest[:-1]), True
        except (TypeError, ValueError):
            return base, -1, True
    return tail.split("[", 1)[0], -1, False


def input_socket_definitions(
    name_or_short: str, *, seed_array_inputs: bool = True
) -> tuple[InputFieldDef, ...]:
    defs: list[InputFieldDef] = []
    for field_name, link_type, is_array in registry.input_link_fields(name_or_short):
        if is_array and seed_array_inputs:
            for idx in range(VARIADIC_AUTHORING_SEED):
                path = f"{field_name}[{idx}]"
                defs.append(
                    InputFieldDef(
                        json_path=path,
                        caption=str(idx),
                        link_type=link_type,
                        field_name=field_name,
                        is_array=True,
                        array_index=idx,
                    )
                )
        else:
            field, idx, path_is_array = _split_path(field_name)
            defs.append(
                InputFieldDef(
                    json_path=field_name,
                    caption=registry.friendly_label(field_name),
                    link_type=link_type,
                    field_name=field,
                    is_array=is_array or path_is_array,
                    array_index=idx,
                )
            )
    return tuple(defs)


def enum_default(enum_type: str) -> str:
    opts = enums.options(enum_type, include_sentinel=False)
    if not opts:
        return ""
    return sorted(opts.items(), key=lambda kv: int(kv[1]))[0][0]


def _default_for_array() -> list:
    return []


def property_kind_from_type(
    type_name: str,
    *,
    field_name: str = "",
    parent_type: str = "",
    json_path: str = "",
    value: Any = None,
) -> tuple[str, Any, str, str, bool, str]:
    """Return editable property metadata for a REDengine type string"""
    t = str(type_name or "")
    enum_type = enums.resolve_enum_type(
        t,
        field_name=field_name,
        parent_type=parent_type,
        json_path=json_path,
        value=value,
    )
    if enum_type:
        is_flags = enums.is_flags(enum_type)
        return (
            ("FLAGS_ENUM" if is_flags else "ENUM"),
            enum_default(enum_type),
            t or enum_type,
            enum_type,
            is_flags,
            "",
        )
    if t.startswith("array:"):
        inner = t[len("array:") :]
        return "ARRAY", _default_for_array(), t, "", False, inner
    if t in {"Bool"}:
        return "BOOL", False, t, "", False, ""
    if t in {"Int8", "Int16", "Int32", "Int64"}:
        return "INT", 0, t, "", False, ""
    if t in {"Uint8", "Uint16", "Uint32", "Uint64"}:
        return "UINT", 0, t, "", False, ""
    if t in {"Float", "Double"}:
        return "FLOAT", 0.0, t, "", False, ""
    if t == "String":
        return "STRING", "", t, "", False, ""
    if t == "CName":
        return "CNAME", "None", t, "", False, ""
    if t == "animTransformIndex":
        return "TRANSFORM_INDEX", "None", t, "", False, ""
    if t == "animNamedTrackIndex":
        return "NAMED_TRACK_INDEX", "None", t, "", False, ""
    if t == "animVisualTagCondition":
        return "VISUAL_TAG_CONDITION", "None", t, "", False, ""
    if t == "animFloatClamp":
        return "FLOAT_CLAMP", (0.0, 1.0), t, "", False, ""
    if t == "Vector2":
        return "VECTOR2", (0.0, 0.0), t, "", False, ""
    if t in {"Vector3", "EulerAngles"}:
        return "VECTOR3", (0.0, 0.0, 0.0), t, "", False, ""
    if t == "Vector4":
        return "VECTOR4", (0.0, 0.0, 0.0, 0.0), t, "", False, ""
    if t == "Quaternion":
        return "QUATERNION", (0.0, 0.0, 0.0, 1.0), t, "", False, ""
    if t == "QsTransform":
        return (
            "QSTRANSFORM",
            {
                "$type": "QsTransform",
                "Rotation": {
                    "$type": "Quaternion",
                    "i": 0.0,
                    "j": 0.0,
                    "k": 0.0,
                    "r": 1.0,
                },
                "Scale": {"$type": "Vector4", "X": 1.0, "Y": 1.0, "Z": 1.0, "W": 1.0},
                "Translation": {
                    "$type": "Vector4",
                    "X": 0.0,
                    "Y": 0.0,
                    "Z": 0.0,
                    "W": 1.0,
                },
            },
            t,
            "",
            False,
            "",
        )
    if t == "curveData:Float":
        return "CURVE_FLOAT", registry.DEFAULT_FLOAT_CURVE, t, "", False, ""
    if t.startswith("handle:") or t.startswith("rRef:"):
        inner = unwrap_indirect_type(t)
        if registry.has_class(inner) and not registry.is_node_class(inner):
            return "HANDLE_STRUCT", {}, t, "", False, inner
        return "RAW_JSON", None, t, "", False, inner
    if not t:
        return "RAW_JSON", None, t, "", False, ""
    if registry.has_class(t) and not registry.is_node_class(t):
        return "STRUCT", {}, t, "", False, t

    return "RAW_JSON", {}, t, "", False, ""


def property_definitions(name_or_short: str) -> tuple[PropertyDef, ...]:
    red_type = registry.full_name(name_or_short)
    defs: list[PropertyDef] = []
    for prop in registry.all_properties(red_type):
        name = str(prop.get("name", ""))
        ptype = str(prop.get("type", ""))
        if not name:
            continue
        hidden = registry.is_hidden_field(name) or bool(prop.get("hidden", False))
        is_link = registry.is_link_type(ptype)
        if hidden or is_link:
            continue
        kind, default, red_type_hint, enum_type, is_flags, element_type = (
            property_kind_from_type(
                ptype, field_name=name, parent_type=red_type, json_path=name, value=None
            )
        )
        if "default" in prop:
            default = prop.get("default")
        defs.append(
            PropertyDef(
                name=name,
                red_type=red_type_hint or ptype,
                value_kind=kind,
                default=default,
                label=registry.friendly_label(name),
                enum_type=enum_type,
                is_flags=is_flags,
                is_array=ptype.startswith("array:"),
                element_type=element_type,
                is_hidden=False,
                is_link=False,
                source="rtti",
            )
        )
    return tuple(defs)


@cache
def node_definition(name_or_short: str) -> NodeDefinition:
    red_type = registry.full_name(name_or_short)
    require_class(red_type)
    short = registry.short_name(red_type)
    return NodeDefinition(
        red_type=red_type,
        short_name=short,
        parent_chain=registry.parent_chain(red_type, include_self=True),
        output_link_type=registry.output_kind(red_type),
        input_fields=input_socket_definitions(red_type, seed_array_inputs=True),
        properties=property_definitions(red_type),
        category="",
        is_container=registry.is_container(red_type),
        is_abstract=registry.is_abstract(red_type),
        metadata_known=True,
    )


def available_node_definitions(
    *, concrete_only: bool = True
) -> tuple[NodeDefinition, ...]:
    return tuple(
        node_definition(short)
        for short in registry.all_node_short_names(concrete_only=concrete_only)
    )


def stats() -> dict:
    meta = registry.stats()
    estats = enums.summary()
    all_defs = (
        available_node_definitions(concrete_only=False)
        if registry.has_metadata()
        else ()
    )
    return {
        "metadata_loaded": bool(meta.get("loaded")),
        "classes": int(meta.get("classes", 0) or 0),
        "anim_nodes": int(meta.get("anim_nodes", 0) or 0),
        "concrete_anim_nodes": int(meta.get("concrete_anim_nodes", 0) or 0),
        "link_properties": int(meta.get("link_properties", 0) or 0),
        "curve_float_properties": int(meta.get("curve_float_properties", 0) or 0),
        "node_definitions": len(all_defs),
        "enum_definitions": int(estats.get("enums", 0) or 0),
        "flag_enums": int(estats.get("flag_enums", 0) or 0),
    }
