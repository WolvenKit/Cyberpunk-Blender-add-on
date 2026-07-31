from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

ANIM_NODE_PREFIX = "animAnimNode_"

LINK_TYPES = frozenset({
    "animPoseLink",
    "animFloatLink",
    "animVectorLink",
    "animIntLink",
    "animBoolLink",
    "animQuaternionLink",
    "animTransformLink",
})

OUTPUT_PARENT_KIND = {
    "animAnimNode_FloatValue": "animFloatLink",
    "animAnimNode_IntValue": "animIntLink",
    "animAnimNode_BoolValue": "animBoolLink",
    "animAnimNode_VectorValue": "animVectorLink",
    "animAnimNode_QuaternionValue": "animQuaternionLink",
    "animAnimNode_TransformValue": "animTransformLink",
}

NO_OUTPUT_FULL = frozenset({"animAnimNode_Output"})
CONTAINER_FULL = "animAnimNode_Container"


HIDDEN_FIELDS = frozenset({
    "$type",
    "id",
    "nodes",
    "states",
    "frozenState",
    "transitions",
    "globalTransitions",
    "conditionalEntries",
    "anyStateInterpolator",
    "outTransitionIndices",
    "profileTimers",
    "poseInfoLogger",
    "solo",
    "debugValueProvider",
})
HIDDEN_FIELD_PREFIXES = ("vis",)

INTEGER_TYPES = frozenset({
    "Int8", "Int16", "Int32", "Int64",
    "Uint8", "Uint16", "Uint32", "Uint64",
})
FLOAT_TYPES = frozenset({"Float", "Double"})
STRING_TYPES = frozenset({"String"})
VECTOR_TYPES = {
    "Vector2": ("VECTOR2", (0.0, 0.0)),
    "Vector3": ("VECTOR3", (0.0, 0.0, 0.0)),
    "Vector4": ("VECTOR4", (0.0, 0.0, 0.0, 0.0)),
    "EulerAngles": ("VECTOR3", (0.0, 0.0, 0.0)),
}

DEFAULT_FLOAT_CURVE = {
    "InterpolationType": "BezierCubic",
    "LinkType": "ESLT_Normal",
    "Elements": [
        {"Point": 0.0, "Value": 0.0},
        {"Point": 1.0, "Value": 1.0},
    ],
}


def _metadata_path() -> str:
    return os.path.join(os.path.dirname(__file__), "newanimnodes.json")


@lru_cache(maxsize=1)
def _records() -> Tuple[Dict[str, dict], bool]:
    path = _metadata_path()
    if not os.path.exists(path):
        return {}, False
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return {}, False
    by_name = {}
    for row in rows if isinstance(rows, list) else []:
        name = row.get("name") if isinstance(row, dict) else None
        if isinstance(name, str) and name:
            by_name[name] = row
    return by_name, bool(by_name)


def has_metadata() -> bool:
    return _records()[1]


def full_name(name_or_short: str) -> str:
    if not name_or_short:
        return name_or_short
    if name_or_short.startswith(ANIM_NODE_PREFIX):
        return name_or_short
    if name_or_short.startswith('anim'):
        return name_or_short
    return ANIM_NODE_PREFIX + name_or_short


def short_name(name_or_short: str) -> str:
    if name_or_short.startswith(ANIM_NODE_PREFIX):
        return name_or_short[len(ANIM_NODE_PREFIX):]
    return name_or_short


def get_class(name_or_short: str) -> Optional[dict]:
    records, _ok = _records()
    return records.get(full_name(name_or_short)) or records.get(name_or_short)


def has_class(name_or_short: str) -> bool:
    return get_class(name_or_short) is not None


def parent_of(name_or_short: str) -> str:
    rec = get_class(name_or_short)
    return str(rec.get("parent", "")) if rec else ""


def parent_chain(name_or_short: str, *, include_self: bool = True) -> List[str]:
    """Return the known inheritance chain from root to class."""
    records, _ok = _records()
    full = full_name(name_or_short)
    chain: List[str] = []
    seen = set()
    cur = full
    while cur and cur in records and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = str(records[cur].get("parent", ""))
    if not include_self and chain:
        chain = chain[1:]
    chain.reverse()
    return chain


def is_subclass_of(name_or_short: str, ancestor: str) -> bool:
    ancestor_full = full_name(ancestor) if ancestor.startswith("anim") or not ancestor.startswith("I") else ancestor
    return ancestor_full in parent_chain(name_or_short, include_self=True)


def is_abstract(name_or_short: str) -> bool:
    rec = get_class(name_or_short)
    if not rec:
        return False
    try:
        return bool(int(rec.get("flags", 0)) & 1)
    except Exception:
        return False


def all_node_short_names(*, concrete_only: bool = True) -> List[str]:
    records, _ok = _records()
    out = []
    for name in records:
        if not name.startswith(ANIM_NODE_PREFIX):
            continue
        if concrete_only and is_abstract(name):
            continue
        out.append(short_name(name))
    return sorted(out)


def all_properties(name_or_short: str) -> List[dict]:
    """Return inherited property metadata in declaration order."""
    records, _ok = _records()
    props: List[dict] = []
    seen = set()
    for cls in parent_chain(name_or_short, include_self=True):
        rec = records.get(cls) or {}
        for prop in rec.get("properties", []) or []:
            pname = prop.get("name")
            if not pname:
                continue


            if pname in seen:
                props = [p for p in props if p.get("name") != pname]
            seen.add(pname)
            props.append(prop)
    return props


def declared_properties(name_or_short: str) -> List[dict]:
    rec = get_class(name_or_short)
    return list(rec.get("properties", []) or []) if rec else []


def property_type_map(name_or_short: str) -> Dict[str, str]:
    return {str(p.get("name")): str(p.get("type", "")) for p in all_properties(name_or_short)}


def ordered_field_names(name_or_short: str, actual_keys: Iterable[str]) -> List[str]:
    """Order JSON keys by metadata declaration order while preserving extras."""
    keys = list(actual_keys)
    declared = [str(p.get("name")) for p in all_properties(name_or_short)]
    order = {name: i for i, name in enumerate(declared)}
    return sorted(keys, key=lambda k: (order.get(k, 10_000), keys.index(k)))


def link_kind_from_type(type_name: str) -> Optional[str]:
    if type_name in LINK_TYPES:
        return type_name
    if type_name.startswith("array:"):
        inner = type_name[len("array:"):]
        if inner in LINK_TYPES:
            return inner
    return None


def is_link_type(type_name: str) -> bool:
    return link_kind_from_type(type_name) is not None


def input_link_fields(name_or_short: str) -> List[Tuple[str, str, bool]]:
    """Return metadata-declared input link fields."""
    fields: List[Tuple[str, str, bool]] = []
    for prop in all_properties(name_or_short):
        pname = str(prop.get("name", ""))
        ptype = str(prop.get("type", ""))
        kind = link_kind_from_type(ptype)
        if not pname or kind is None:
            continue
        fields.append((pname, kind, ptype.startswith("array:")))
    return fields


def output_kind(name_or_short: str) -> Optional[str]:
    """Return the REDengine link kind emitted by this node class."""
    full = full_name(name_or_short)
    if full in NO_OUTPUT_FULL:
        return None
    if has_class(full):
        for ancestor, kind in OUTPUT_PARENT_KIND.items():
            if is_subclass_of(full, ancestor):
                return kind
        return "animPoseLink"
    return None


def is_container(name_or_short: str) -> bool:
    if has_class(name_or_short):
        return is_subclass_of(name_or_short, CONTAINER_FULL)
    return False


def _is_hidden_field(name: str) -> bool:
    if name in HIDDEN_FIELDS:
        return True
    if any(name.startswith(prefix) for prefix in HIDDEN_FIELD_PREFIXES):
        return True
    return False


def property_kind_from_type(type_name: str) -> Tuple[str, Any, str]:
    """Map a REDengine metadata type to editable property metadata."""
    t = str(type_name or "")
    if t == "Bool":
        return "BOOL", False, t
    if t in INTEGER_TYPES:
        return "INT", 0, t
    if t in FLOAT_TYPES:
        return "FLOAT", 0.0, t
    if t in STRING_TYPES:
        return "STRING", "", t
    if t == "CName":
        return "CNAME", "None", t
    if t == "animTransformIndex":
        return "TRANSFORM_INDEX", "None", t
    if t == "animNamedTrackIndex":
        return "NAMED_TRACK_INDEX", "None", t
    if t == "animVisualTagCondition":
        return "VISUAL_TAG_CONDITION", "None", t
    if t == "animFloatClamp":
        return "FLOAT_CLAMP", (0.0, 1.0), t
    if t in VECTOR_TYPES:
        kind, default = VECTOR_TYPES[t]
        return kind, default, t
    if t == "Quaternion":
        return "QUATERNION", (0.0, 0.0, 0.0, 1.0), t
    if t == "QsTransform":
        return "QSTRANSFORM", {"$type": "QsTransform", "Rotation": {"$type": "Quaternion", "i": 0.0, "j": 0.0, "k": 0.0, "r": 1.0}, "Translation": {"$type": "Vector4", "X": 0.0, "Y": 0.0, "Z": 0.0, "W": 1.0}, "Scale": {"$type": "Vector4", "X": 1.0, "Y": 1.0, "Z": 1.0, "W": 1.0}}, t
    if t == "curveData:Float":
        return "CURVE_FLOAT", DEFAULT_FLOAT_CURVE, t
    if t == "curveData:Vector4":
        return "RAW_JSON", {"InterpolationType": "Linear", "LinkType": "ESLT_Normal", "Elements": []}, t
    if t.startswith("array:") or t.startswith("handle:") or t.startswith("rRef:"):
        return "RAW_JSON", [] if t.startswith("array:") else None, t


    return "ENUM", "", t


def editable_property_fields(name_or_short: str) -> List[Tuple[str, str, Any, str, str]]:
    """Return editable fields for a newly authored node."""
    result: List[Tuple[str, str, Any, str, str]] = []
    for prop in all_properties(name_or_short):
        name = str(prop.get("name", ""))
        ptype = str(prop.get("type", ""))
        if not name or _is_hidden_field(name):
            continue
        if is_link_type(ptype):
            continue

        if ptype.startswith("array:") or ptype.startswith("handle:") or ptype.startswith("rRef:"):
            continue
        kind, default, red_type = property_kind_from_type(ptype)
        result.append((name, kind, default, red_type, _friendly(name)))
    return result


def curve_float_fields(name_or_short: str) -> List[str]:
    return [str(p.get("name")) for p in all_properties(name_or_short)
            if str(p.get("type", "")) == "curveData:Float"]


def _friendly(field: str) -> str:
    if not field:
        return field
    out = [field[0].upper()]
    for ch in field[1:]:
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


def stats() -> dict:
    records, ok = _records()
    if not ok:
        return {"loaded": False}
    node_names = [n for n in records if n.startswith(ANIM_NODE_PREFIX)]
    link_props = 0
    curve_float_props = 0
    for n in node_names:
        for p in all_properties(n):
            t = str(p.get("type", ""))
            if is_link_type(t):
                link_props += 1
            if t == "curveData:Float":
                curve_float_props += 1
    return {
        "loaded": True,
        "classes": len(records),
        "anim_nodes": len(node_names),
        "concrete_anim_nodes": len(all_node_short_names(concrete_only=True)),
        "link_properties": link_props,
        "curve_float_properties": curve_float_props,
    }
