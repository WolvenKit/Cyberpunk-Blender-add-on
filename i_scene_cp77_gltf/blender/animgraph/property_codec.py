from __future__ import annotations

<<<<<<< Updated upstream
import json
from typing import Any, Iterable, Optional, Tuple

from ...animation.animgraph.schema import rtti
from ...animation.animgraph.model import math_expression
from ...animation.animgraph.model.value_codec import cname_value, number
from ...redSpace.qs_transform import encode_qs_transform

_SIMPLE_KIND_TYPES = {
    'Bool': 'BOOL',
    'Float': 'FLOAT',
    'Double': 'FLOAT',
    'String': 'STRING',
    'CName': 'CNAME',
    'Int8': 'INT', 'Int16': 'INT', 'Int32': 'INT', 'Int64': 'INT',
    'Uint8': 'UINT', 'Uint16': 'UINT', 'Uint32': 'UINT', 'Uint64': 'UINT',
    'Vector2': 'VECTOR2', 'Vector3': 'VECTOR3', 'Vector4': 'VECTOR4',
    'EulerAngles': 'VECTOR3',
    'Quaternion': 'QUATERNION',
    'QsTransform': 'QSTRANSFORM',
    'animTransformIndex': 'TRANSFORM_INDEX',
    'animNamedTrackIndex': 'NAMED_TRACK_INDEX',
    'animVisualTagCondition': 'VISUAL_TAG_CONDITION',
    'animFloatClamp': 'FLOAT_CLAMP',
}

def pretty_label(key: str) -> str:
    """Return a readable UI label for a serialized field path."""
    if not key:
        return key
    text = key.replace('.', ' ').replace('[', ' ').replace(']', '')
    out = [text[0].upper()]
    for ch in text[1:]:
        if ch == '_':
            out.append(' ')
            continue
        if ch.isupper() and out and out[-1] not in (' ', '['):
            out.append(' ')
        out.append(ch)
    return ''.join(out).strip()

def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)

=======
from collections.abc import Iterable
from typing import Any

from ...animation.model.animgraph import math_expression
from ...animation.model.animgraph.schema import enums, registry
from ...assetio import animgraph_json as json_io
from ...assetio.transform_values import encode_qs_transform
from ...assetio.values import cname_text, coerce_float
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

# The curve a property without curve data starts from, and the flag on one whose source curve was null.
_SEEDED_CURVE = {
    "InterpolationType": "BezierCubic",
    "LinkType": "ESLT_Normal",
    "Elements": [{"Point": 0.0, "Value": 0.0}, {"Point": 1.0, "Value": 1.0}],
}
_NULL_CURVE_KEY = "red_curve_null"

_SIMPLE_KIND_TYPES = {
    "Bool": "BOOL",
    "Float": "FLOAT",
    "Double": "FLOAT",
    "String": "STRING",
    "CName": "CNAME",
    "Int8": "INT",
    "Int16": "INT",
    "Int32": "INT",
    "Int64": "INT",
    "Uint8": "UINT",
    "Uint16": "UINT",
    "Uint32": "UINT",
    "Uint64": "UINT",
    "Vector2": "VECTOR2",
    "Vector3": "VECTOR3",
    "Vector4": "VECTOR4",
    "EulerAngles": "VECTOR3",
    "Quaternion": "QUATERNION",
    "QsTransform": "QSTRANSFORM",
    "animTransformIndex": "TRANSFORM_INDEX",
    "animNamedTrackIndex": "NAMED_TRACK_INDEX",
    "animVisualTagCondition": "VISUAL_TAG_CONDITION",
    "animFloatClamp": "FLOAT_CLAMP",
}


def pretty_label(key: str) -> str:
    """Return a readable UI label for a serialized field path"""
    if not key:
        return key
    text = key.replace(".", " ").replace("[", " ").replace("]", "")
    out = [text[0].upper()]
    for ch in text[1:]:
        if ch == "_":
            out.append(" ")
            continue
        if ch.isupper() and out and out[-1] not in (" ", "["):
            out.append(" ")
        out.append(ch)
    return "".join(out).strip()


def _safe_json_dumps(value: Any) -> str:
    try:
        return json_io.dumps(value, indent=None)
    except TypeError:
        return repr(value)


>>>>>>> Stashed changes
def _safe_json_loads(text: str, default: Any = None) -> Any:
    if not text:
        return default
    try:
<<<<<<< Updated upstream
        return json.loads(text)
    except Exception:
        return default


def _uint_string(value: Any, default: str = '0') -> str:
    """Return a decimal string for unsigned REDengine integers."""
=======
        return json_io.loads(text)
    except (TypeError, ValueError):
        return default


def _uint_string(value: Any, default: str = "0") -> str:
    """Return a decimal string for unsigned REDengine integers"""
>>>>>>> Stashed changes
    try:
        if value is None:
            return default
        n = int(value)
<<<<<<< Updated upstream
        if n < 0:
            n = 0
        return str(n)
    except Exception:
        return default

=======
        n = max(n, 0)
        return str(n)
    except (TypeError, ValueError, OverflowError):
        return default


>>>>>>> Stashed changes
def _uint_from_string(value: Any, default: int = 0) -> int:
    try:
        text = str(value).strip()
        if not text:
            return default
        n = int(text, 0)
        return max(0, n)
<<<<<<< Updated upstream
    except Exception:
        return default

def _is_curve_float_data(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    elements = value.get('Elements')
    if not isinstance(elements, list):
        return False
    if 'InterpolationType' not in value and 'LinkType' not in value:
        return False
    return all(isinstance(e, dict) and 'Point' in e and 'Value' in e for e in elements)

def _is_math_expression_data(value: Any) -> bool:
    return isinstance(value, dict) and value.get('$type') == 'animMathExpressionNodeData'

def _is_qstransform(value: Any) -> bool:
    return isinstance(value, dict) and value.get('$type') == 'QsTransform'

def _handled_payload(value: Any) -> Tuple[str, dict, str, str]:
    """Return owned-payload metadata for HandleId/Data wrappers."""
    if not isinstance(value, dict):
        return '', {}, '', ''
    data = value.get('Data')
    if not isinstance(data, dict):
        return '', {}, '', ''
    t = str(data.get('$type', ''))
    if not t or rtti is None:
        return '', {}, '', ''
    try:
        if rtti.has_class(t) and not rtti.is_graph_node_class(t):
            return 'HANDLE_STRUCT', data, str(value.get('HandleId', '') or ''), str(value.get('HandleRefId', '') or '')
    except Exception:
        pass
    return '', {}, '', ''

def _known_struct_payload(value: Any, hint: str = '') -> Tuple[str, dict]:
    if not isinstance(value, dict):
        return '', {}
    t = str(value.get('$type') or hint or '')
    if not t or rtti is None:
        return '', {}
    try:
        if rtti.has_class(t) and not rtti.is_graph_node_class(t):
            return t, value
    except Exception:
        pass
    return '', {}

def _metadata_type_for(parent_type: str, field: str) -> str:
    if not parent_type or not field:
        return ''
    if rtti is not None:
        try:
            for prop in rtti.all_properties(parent_type):
                if prop.get('name') == field:
                    return str(prop.get('type', ''))
        except Exception:
            pass
    return ''
=======
    except (TypeError, ValueError, OverflowError):
        return default


def _is_curve_float_data(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    elements = value.get("Elements")
    if not isinstance(elements, list):
        return False
    if "InterpolationType" not in value and "LinkType" not in value:
        return False
    return all(isinstance(e, dict) and "Point" in e and "Value" in e for e in elements)


def _is_qstransform(value: Any) -> bool:
    return isinstance(value, dict) and value.get("$type") == "QsTransform"


def _handled_payload(value: Any) -> tuple[str, dict, str, str]:
    """Return owned-payload metadata for HandleId/Data wrappers"""
    if not isinstance(value, dict):
        return "", {}, "", ""
    data = value.get("Data")
    if not isinstance(data, dict):
        return "", {}, "", ""
    t = str(data.get("$type", ""))
    if not t:
        return "", {}, "", ""
    if registry.has_class(t) and not registry.is_node_class(t):
        return (
            "HANDLE_STRUCT",
            data,
            str(value.get("HandleId", "") or ""),
            str(value.get("HandleRefId", "") or ""),
        )
    return "", {}, "", ""


def _handle_wrapper_payload(value: Any) -> dict | None:
    """Data of a HandleId/HandleRefId wrapper, or None for anything else"""
    if not isinstance(value, dict) or not isinstance(value.get("Data"), dict):
        return None
    if "HandleId" not in value and "HandleRefId" not in value:
        return None
    return value["Data"]


def _rewrap_handle(raw_json: str, encoded: Any) -> Any:
    """Put an encoded struct back inside the handle wrapper it was decoded from"""
    if (
        not isinstance(encoded, dict)
        or "HandleId" in encoded
        or "HandleRefId" in encoded
    ):
        return encoded
    wrapper = _safe_json_loads(raw_json, None)
    if _handle_wrapper_payload(wrapper) is None:
        return encoded
    out = {key: wrapper[key] for key in ("HandleId", "HandleRefId") if key in wrapper}
    out["Data"] = encoded
    return out


def _known_struct_payload(value: Any, hint: str = "") -> tuple[str, dict]:
    if not isinstance(value, dict):
        return "", {}
    t = str(value.get("$type") or hint or "")
    if not t:
        return "", {}
    if registry.has_class(t) and not registry.is_node_class(t):
        return t, value
    return "", {}


def _metadata_type_for(parent_type: str, field: str) -> str:
    if not parent_type or not field:
        return ""
    for prop in registry.all_properties(parent_type):
        if prop.get("name") == field:
            return str(prop.get("type", ""))
    return ""

>>>>>>> Stashed changes

def _is_link_type(type_name: str) -> bool:
    if not type_name:
        return False
<<<<<<< Updated upstream
    if rtti is not None:
        try:
            return rtti.is_link_type(type_name)
        except Exception:
            return False
    return False

def _is_hidden_field(name: str) -> bool:
    if not name or name == '$type':
        return True
    if rtti is not None:
        try:
            return rtti.is_hidden_field(name)
        except Exception:
            pass
    return False

def _is_enum_type(type_name: str) -> bool:
    if not type_name or rtti is None:
        return False
    try:
        return rtti.has_enum(type_name)
    except Exception:
        return False

def _resolve_enum_type(type_name: str = '', *, field_name: str = '', parent_type: str = '', json_path: str = '', value: Any = None) -> str:
    if rtti is None:
        return ''
    try:
        return rtti.resolve_enum_type(type_name, field_name=field_name, parent_type=parent_type, json_path=json_path, value=value)
    except Exception:
        return ''

def _is_flag_enum(type_name: str) -> bool:
    if rtti is None:
        return False
    try:
        return rtti.is_flag_enum(type_name)
    except Exception:
        return False
=======
    return registry.is_link_type(type_name)


def _is_hidden_field(name: str) -> bool:
    if not name or name == "$type":
        return True
    return registry.is_hidden_field(name)


def _is_enum_type(type_name: str) -> bool:
    if not type_name:
        return False
    return enums.has_enum(type_name)

>>>>>>> Stashed changes

def _is_simple_type_hint(type_name: str) -> bool:
    if not type_name:
        return False
<<<<<<< Updated upstream
    if type_name.startswith('array:') or type_name.startswith('handle:') or type_name.startswith('rRef:'):
        return False
    if type_name in _SIMPLE_KIND_TYPES:
        return True
    if type_name == 'enum' or _is_enum_type(type_name):
        return True
    return False

def _infer_type_from_value(value: Any, hint: str = '') -> str:
    if hint:
        return hint
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'Bool'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'Int32'
    if isinstance(value, float):
        return 'Float'
    if isinstance(value, str):
        return 'String'
    if isinstance(value, dict):
        t = str(value.get('$type', ''))
        if t:
            return t
        if _is_curve_float_data(value):
            return 'curveData:Float'
    return ''
=======
    if (
        type_name.startswith("array:")
        or type_name.startswith("handle:")
        or type_name.startswith("rRef:")
    ):
        return False
    if type_name in _SIMPLE_KIND_TYPES:
        return True
    if type_name == "enum" or _is_enum_type(type_name):
        return True
    return False


def _infer_type_from_value(value: Any, hint: str = "") -> str:
    if hint:
        return hint
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "Bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "Int32"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, str):
        return "String"
    if isinstance(value, dict):
        t = str(value.get("$type", ""))
        if t:
            return t
        if _is_curve_float_data(value):
            return "curveData:Float"
    return ""

>>>>>>> Stashed changes

def _set_vector(target: Any, size: int, values: Iterable[Any]) -> None:
    target.vector_size = size
    vals = list(values)
    for i in range(4):
<<<<<<< Updated upstream
        target.vector_value[i] = number(vals[i], 0.0) if i < len(vals) else 0.0

def _read_vec(value: Any, keys: Tuple[str, ...], defaults: Tuple[float, ...]) -> Tuple[float, ...]:
    if not isinstance(value, dict):
        return defaults
    return tuple(number(value.get(k), defaults[i]) for i, k in enumerate(keys))

def _set_qstransform(target: Any, value: Any) -> None:
    target.value_kind = 'QSTRANSFORM'
    target.red_type = target.red_type or 'QsTransform'
    rot = value.get('Rotation', {}) if isinstance(value, dict) else {}
    trans = value.get('Translation', {}) if isinstance(value, dict) else {}
    scale = value.get('Scale', {}) if isinstance(value, dict) else {}
    rvals = _read_vec(rot, ('i', 'j', 'k', 'r'), (0.0, 0.0, 0.0, 1.0))
    tvals = _read_vec(trans, ('X', 'Y', 'Z', 'W'), (0.0, 0.0, 0.0, 1.0))
    svals = _read_vec(scale, ('X', 'Y', 'Z', 'W'), (1.0, 1.0, 1.0, 1.0))
=======
        target.vector_value[i] = (
            coerce_float(vals[i], 0.0, unwrap=False) if i < len(vals) else 0.0
        )


def _read_vec(
    value: Any, keys: tuple[str, ...], defaults: tuple[float, ...]
) -> tuple[float, ...]:
    if not isinstance(value, dict):
        return defaults
    return tuple(
        coerce_float(value.get(k), defaults[i], unwrap=False)
        for i, k in enumerate(keys)
    )


def _set_qstransform(target: Any, value: Any) -> None:
    target.value_kind = "QSTRANSFORM"
    target.red_type = target.red_type or "QsTransform"
    rot = value.get("Rotation", {}) if isinstance(value, dict) else {}
    trans = value.get("Translation", {}) if isinstance(value, dict) else {}
    scale = value.get("Scale", {}) if isinstance(value, dict) else {}
    rvals = _read_vec(rot, ("i", "j", "k", "r"), (0.0, 0.0, 0.0, 1.0))
    tvals = _read_vec(trans, ("X", "Y", "Z", "W"), (0.0, 0.0, 0.0, 1.0))
    svals = _read_vec(scale, ("X", "Y", "Z", "W"), (1.0, 1.0, 1.0, 1.0))
>>>>>>> Stashed changes
    for i, v in enumerate(tvals):
        target.qs_translation[i] = v
    for i, v in enumerate(rvals):
        target.qs_rotation[i] = v
    for i, v in enumerate(svals):
        target.qs_scale[i] = v

<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
def _encode_qstransform(target: Any) -> dict:
    return encode_qs_transform(
        target.qs_rotation,
        target.qs_translation[:3],
        target.qs_scale[:3],
        translation_w=float(target.qs_translation[3]),
        scale_w=float(target.qs_scale[3]),
<<<<<<< Updated upstream
        quaternion_order='xyzw',
    )

=======
        quaternion_order="xyzw",
    )


>>>>>>> Stashed changes
def _struct_field_type(struct_type: str, field_name: str, value: Any) -> str:
    hinted = _metadata_type_for(struct_type, field_name)
    if hinted:
        return hinted
    return _infer_type_from_value(value)

<<<<<<< Updated upstream
def _decode_struct_fields_into(target: Any, data: dict, struct_type: str, *, value_kind: str = 'STRUCT', handle_id: str = '', ref_id: str = '') -> bool:
    if not isinstance(data, dict) or not struct_type:
        return False
    if rtti is None:
        return False
    try:
        if not rtti.has_class(struct_type):
            return False
    except Exception:
=======

def _decode_struct_fields_into(
    target: Any,
    data: dict,
    struct_type: str,
    *,
    value_kind: str = "STRUCT",
    handle_id: str = "",
    ref_id: str = "",
) -> bool:
    if not isinstance(data, dict) or not struct_type:
        return False
    if not registry.has_class(struct_type):
>>>>>>> Stashed changes
        return False

    target.value_kind = value_kind
    target.red_type = struct_type
    target.array_element_type = struct_type
<<<<<<< Updated upstream
    target.string_value = str(handle_id or ref_id or '')
    try:
        target.struct_handle_id = str(handle_id or '')
        target.struct_ref_id = str(ref_id or '')
    except Exception:
        pass


    target.array_items.clear()
    element = target.array_items.add()
    element.label = 'Data'
    element.red_type = struct_type
    element.raw_json = _safe_json_dumps(data)

    keys = [k for k in data.keys() if not _is_hidden_field(k)]
    order = {}
    try:
        order = {str(p.get('name')): i for i, p in enumerate(rtti.all_properties(struct_type))}
    except Exception:
        order = {}
    original_order = {k: i for i, k in enumerate(data.keys())}
=======
    target.string_value = str(handle_id or ref_id or "")
    try:
        target.struct_handle_id = str(handle_id or "")
        target.struct_ref_id = str(ref_id or "")
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_decode_struct_fields_into", type(error).__name__),
            "decode struct fields into: fell back after %s",
            error,
            exc_info=True,
        )

    target.array_items.clear()
    element = target.array_items.add()
    element.label = "Data"
    element.red_type = struct_type
    element.raw_json = _safe_json_dumps(data)

    keys = [k for k in data if not _is_hidden_field(k)]
    order = {
        str(prop.get("name")): index
        for index, prop in enumerate(registry.all_properties(struct_type))
    }
    original_order = {k: i for i, k in enumerate(data)}
>>>>>>> Stashed changes
    keys.sort(key=lambda k: (order.get(k, 9999), original_order.get(k, 9999)))

    decoded = 0
    for key in keys:
        v = data.get(key)
        hint = _struct_field_type(struct_type, key, v)

<<<<<<< Updated upstream

        if hint.startswith('array:') or hint.startswith('handle:') or hint.startswith('rRef:') or _is_link_type(hint):
            continue
        stype, _sdata = _known_struct_payload(v, hint)
        if stype:


=======
        if (
            hint.startswith("array:")
            or hint.startswith("handle:")
            or hint.startswith("rRef:")
            or _is_link_type(hint)
        ):
            continue
        stype, _sdata = _known_struct_payload(v, hint)
        if stype:
>>>>>>> Stashed changes
            continue
        f = _add_array_field(element, key, v, red_type_hint=hint)
        if f is not None:
            decoded += 1

    element.summary = _element_summary(element)
    return decoded > 0

<<<<<<< Updated upstream
def _decode_simple_into(target: Any, value: Any, *, red_type_hint: str = '', field_name: str = '', json_path: str = '', parent_type: str = '') -> bool:
    """Decode scalar and simple-struct storage into editable property fields."""
    enum_type = _resolve_enum_type(red_type_hint, field_name=field_name, parent_type=parent_type, json_path=json_path, value=value)
    if enum_type:
        target.value_kind = 'FLAGS_ENUM' if _is_flag_enum(enum_type) else 'ENUM'
        target.red_type = enum_type
        target.enum_type = enum_type
        target.enum_storage = 'value' if isinstance(value, int) and not isinstance(value, bool) else 'name'
        try:
            if rtti is not None:
                target.enum_raw_value = str(rtti.enum_value_for_name(enum_type, value) if isinstance(value, str) else value)
                target.string_value = rtti.enum_decoded_value_text(enum_type, value)
                choice = rtti.enum_normalize_choice(enum_type, value)
                try:
                    target.enum_choice = choice
                except Exception:
                    target.enum_choice = '__RAW__'
            else:
                target.string_value = str(value)
        except Exception:
            target.string_value = str(value)
        return True
    if red_type_hint == 'enum':
        red_type_hint = ''
=======

def _decode_simple_into(
    target: Any,
    value: Any,
    *,
    red_type_hint: str = "",
    field_name: str = "",
    json_path: str = "",
    parent_type: str = "",
) -> bool:
    """Decode scalar and simple-struct storage into editable property fields"""
    enum_type = enums.resolve_enum_type(
        red_type_hint,
        field_name=field_name,
        parent_type=parent_type,
        json_path=json_path,
        value=value,
    )
    if enum_type:
        target.value_kind = "FLAGS_ENUM" if enums.is_flags(enum_type) else "ENUM"
        target.red_type = enum_type
        target.enum_type = enum_type
        target.enum_storage = (
            "value"
            if isinstance(value, int) and not isinstance(value, bool)
            else "name"
        )
        try:
            target.enum_raw_value = str(
                enums.value_for_name(enum_type, value)
                if isinstance(value, str)
                else value
            )
            target.string_value = enums.decoded_value_text(enum_type, value)
            choice = enums.normalize_choice(enum_type, value)
            try:
                target.enum_choice = choice
            except (TypeError, ValueError):
                target.enum_choice = "__RAW__"
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_decode_simple_into", type(error).__name__),
                "decode simple into: fell back after %s",
                error,
                exc_info=True,
            )
            target.string_value = str(value)
        return True
    if red_type_hint == "enum":
        red_type_hint = ""
>>>>>>> Stashed changes

    handled_kind, handled_data, handle_id, ref_id = _handled_payload(value)
    if handled_kind:
        return _decode_struct_fields_into(
<<<<<<< Updated upstream
            target, handled_data, str(handled_data.get('$type', '')),
            value_kind='HANDLE_STRUCT', handle_id=handle_id, ref_id=ref_id)

    struct_type, struct_data = _known_struct_payload(value, red_type_hint)
    if struct_type:
        return _decode_struct_fields_into(target, struct_data, struct_type, value_kind='STRUCT')

    inferred = _infer_type_from_value(value, red_type_hint)
    if inferred.startswith('array:') or _is_link_type(inferred):
        return False
    if inferred == 'null':
        target.value_kind = 'NULL'
        target.red_type = 'null'
        target.editable = False
        return True
    if inferred == 'curveData:Float':
        return False
    if inferred == 'QsTransform' or _is_qstransform(value):
        _set_qstransform(target, value if isinstance(value, dict) else {})
        target.red_type = 'QsTransform'
        return True

    if isinstance(value, dict) and 'HandleId' in value and isinstance(value.get('Data'), dict) and '$type' not in value:
        inner = value['Data']
        ok = _decode_simple_into(target, inner, red_type_hint=red_type_hint, field_name=field_name, json_path=json_path, parent_type=parent_type)
        if ok and not target.red_type:
            target.red_type = inner.get('$type', '')
        return ok

    if value is None:
        target.value_kind = 'NULL'
        target.red_type = 'null'
        target.editable = False
        return True
    if isinstance(value, bool):
        target.value_kind = 'BOOL'
        target.red_type = red_type_hint or 'Bool'
        target.bool_value = value
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        if str(red_type_hint).startswith('Uint'):
            target.value_kind = 'UINT'
            target.red_type = red_type_hint or 'Uint32'
            target.string_value = _uint_string(value)
            return True
        target.value_kind = 'INT'
        target.red_type = red_type_hint or 'Int32'


        ivalue = int(value)
        if ivalue > 2147483647:
            target.value_kind = 'UINT'
            target.red_type = red_type_hint or 'Uint32'
            target.string_value = _uint_string(ivalue)
            return True
        if ivalue < -2147483648:
            ivalue = -2147483648
        target.int_value = ivalue
        return True
    if isinstance(value, float):
        target.value_kind = 'FLOAT'
        target.red_type = red_type_hint or 'Float'
        target.float_value = value
        return True
    if isinstance(value, str):
        if red_type_hint == 'CName':
            target.value_kind = 'CNAME'
        elif red_type_hint and red_type_hint != 'String':
            target.value_kind = 'ENUM'
        else:
            target.value_kind = 'STRING'
        target.red_type = red_type_hint or 'String'
=======
            target,
            handled_data,
            str(handled_data.get("$type", "")),
            value_kind="HANDLE_STRUCT",
            handle_id=handle_id,
            ref_id=ref_id,
        )

    struct_type, struct_data = _known_struct_payload(value, red_type_hint)
    if struct_type:
        return _decode_struct_fields_into(
            target, struct_data, struct_type, value_kind="STRUCT"
        )

    inferred = _infer_type_from_value(value, red_type_hint)
    if inferred.startswith("array:") or _is_link_type(inferred):
        return False
    if inferred == "null":
        target.value_kind = "NULL"
        target.red_type = "null"
        target.editable = False
        return True
    if inferred == "curveData:Float":
        return False
    if red_type_hint == "Bool" and isinstance(value, (bool, int)):
        target.value_kind = "BOOL"
        target.red_type = "Bool"
        target.bool_value = bool(value)
        return True
    if (
        red_type_hint in {"Float", "Double"}
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        target.value_kind = "FLOAT"
        target.red_type = red_type_hint
        target.float_value = float(value)
        return True
    if inferred == "QsTransform" or _is_qstransform(value):
        _set_qstransform(target, value if isinstance(value, dict) else {})
        target.red_type = "QsTransform"
        return True

    if (
        isinstance(value, dict)
        and "HandleId" in value
        and isinstance(value.get("Data"), dict)
        and "$type" not in value
    ):
        inner = value["Data"]
        ok = _decode_simple_into(
            target,
            inner,
            red_type_hint=red_type_hint,
            field_name=field_name,
            json_path=json_path,
            parent_type=parent_type,
        )
        if ok and not target.red_type:
            target.red_type = inner.get("$type", "")
        return ok

    if value is None:
        target.value_kind = "NULL"
        target.red_type = "null"
        target.editable = False
        return True
    if isinstance(value, bool):
        target.value_kind = "BOOL"
        target.red_type = red_type_hint or "Bool"
        target.bool_value = value
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        if str(red_type_hint).startswith("Uint"):
            target.value_kind = "UINT"
            target.red_type = red_type_hint or "Uint32"
            target.string_value = _uint_string(value)
            return True
        target.value_kind = "INT"
        target.red_type = red_type_hint or "Int32"

        ivalue = int(value)
        if ivalue > 2147483647:
            target.value_kind = "UINT"
            target.red_type = red_type_hint or "Uint32"
            target.string_value = _uint_string(ivalue)
            return True
        ivalue = max(ivalue, -2147483648)
        target.int_value = ivalue
        return True
    if isinstance(value, float):
        target.value_kind = "FLOAT"
        target.red_type = red_type_hint or "Float"
        target.float_value = value
        return True
    if isinstance(value, str):
        if red_type_hint == "CName":
            target.value_kind = "CNAME"
        elif red_type_hint and red_type_hint != "String":
            target.value_kind = "ENUM"
        else:
            target.value_kind = "STRING"
        target.red_type = red_type_hint or "String"
>>>>>>> Stashed changes
        target.string_value = value
        return True
    if not isinstance(value, dict):
        return False

<<<<<<< Updated upstream
    t = str(value.get('$type', red_type_hint or ''))
    target.red_type = t
    if t == 'CName':
        target.value_kind = 'CNAME'
        target.string_value = str(value.get('$value', ''))
        return True
    if t == 'animTransformIndex':
        target.value_kind = 'TRANSFORM_INDEX'
        target.string_value = cname_value(value.get('name'))
        return True
    if t == 'animNamedTrackIndex':
        target.value_kind = 'NAMED_TRACK_INDEX'
        target.string_value = cname_value(value.get('name'))
        return True
    if t == 'animVisualTagCondition':
        target.value_kind = 'VISUAL_TAG_CONDITION'
        target.string_value = cname_value(value.get('visualTag'))
        return True
    if t == 'animFloatClamp':
        target.value_kind = 'FLOAT_CLAMP'
        _set_vector(target, 2, (value.get('min', 0.0), value.get('max', 0.0)))
        return True
    if t == 'Vector2':
        target.value_kind = 'VECTOR2'
        _set_vector(target, 2, (value.get('X', 0.0), value.get('Y', 0.0)))
        return True
    if t == 'Vector3':
        target.value_kind = 'VECTOR3'
        _set_vector(target, 3, (value.get('X', 0.0), value.get('Y', 0.0), value.get('Z', 0.0)))
        return True
    if t in {'Vector4', 'EulerAngles'}:
        target.value_kind = 'VECTOR4' if t == 'Vector4' else 'VECTOR3'
        if t == 'Vector4':
            _set_vector(target, 4, (value.get('X', 0.0), value.get('Y', 0.0), value.get('Z', 0.0), value.get('W', 0.0)))
        else:
            _set_vector(target, 3, (value.get('Pitch', value.get('X', 0.0)), value.get('Yaw', value.get('Y', 0.0)), value.get('Roll', value.get('Z', 0.0))))
        return True
    if t == 'Quaternion':
        target.value_kind = 'QUATERNION'
        _set_vector(target, 4, (value.get('i', 0.0), value.get('j', 0.0), value.get('k', 0.0), value.get('r', 1.0)))
        return True


    return False

def _field_summary(field: Any) -> str:
    kind = field.value_kind
    if kind == 'BOOL':
        return str(bool(field.bool_value))
    if kind == 'INT':
        return str(int(field.int_value))
    if kind == 'UINT':
        return str(field.string_value or '0')
    if kind == 'FLOAT':
        return f'{float(field.float_value):g}'
    if kind in {'STRING', 'CNAME', 'ENUM', 'FLAGS_ENUM', 'TRANSFORM_INDEX', 'NAMED_TRACK_INDEX', 'VISUAL_TAG_CONDITION'}:
        return str(field.string_value)
    if kind in {'VECTOR2', 'VECTOR3', 'VECTOR4', 'QUATERNION', 'FLOAT_CLAMP'}:
        n = max(1, min(4, int(getattr(field, 'vector_size', 4))))
        return '(' + ', '.join(f'{float(field.vector_value[i]):g}' for i in range(n)) + ')'
    if kind == 'QSTRANSFORM':
        t = field.qs_translation
        r = field.qs_rotation
        return f'T=({t[0]:g},{t[1]:g},{t[2]:g}) R=({r[0]:g},{r[1]:g},{r[2]:g},{r[3]:g})'
    if kind in {'STRUCT', 'HANDLE_STRUCT'}:
        t = getattr(field, 'array_element_type', '') or getattr(field, 'red_type', '') or 'struct'
        h = getattr(field, 'struct_handle_id', '') or getattr(field, 'struct_ref_id', '')
        return f'{t} {h}'.strip()
    if kind == 'MATH_EXPRESSION':
        return str(getattr(field, 'string_value', '') or 'Math Expression')
    if kind == 'NULL':
        return 'null'
    return field.red_type or kind

def _element_summary(element: Any) -> str:
    pieces = []
    preferred = ('transformToChange', 'sourceBone', 'offsetSpaceBone', 'name', 'tag', 'value', 'offset')
    fields = list(getattr(element, 'fields', ()))
=======
    t = str(value.get("$type", red_type_hint or ""))
    target.red_type = t
    if t == "CName":
        target.value_kind = "CNAME"
        target.string_value = str(value.get("$value", ""))
        return True
    if t == "animTransformIndex":
        target.value_kind = "TRANSFORM_INDEX"
        target.string_value = cname_text(value.get("name"))
        return True
    if t == "animNamedTrackIndex":
        target.value_kind = "NAMED_TRACK_INDEX"
        target.string_value = cname_text(value.get("name"))
        return True
    if t == "animVisualTagCondition":
        target.value_kind = "VISUAL_TAG_CONDITION"
        target.string_value = cname_text(value.get("visualTag"))
        return True
    if t == "animFloatClamp":
        target.value_kind = "FLOAT_CLAMP"
        target.clamp_use_min = bool(value.get("useMin", False))
        target.clamp_use_max = bool(value.get("useMax", False))
        _set_vector(target, 2, (value.get("min", -1.0), value.get("max", 1.0)))
        return True
    if t == "Vector2":
        target.value_kind = "VECTOR2"
        _set_vector(target, 2, (value.get("X", 0.0), value.get("Y", 0.0)))
        return True
    if t == "Vector3":
        target.value_kind = "VECTOR3"
        _set_vector(
            target, 3, (value.get("X", 0.0), value.get("Y", 0.0), value.get("Z", 0.0))
        )
        return True
    if t in {"Vector4", "EulerAngles"}:
        target.value_kind = "VECTOR4" if t == "Vector4" else "VECTOR3"
        if t == "Vector4":
            _set_vector(
                target,
                4,
                (
                    value.get("X", 0.0),
                    value.get("Y", 0.0),
                    value.get("Z", 0.0),
                    value.get("W", 0.0),
                ),
            )
        else:
            _set_vector(
                target,
                3,
                (
                    value.get("Pitch", value.get("X", 0.0)),
                    value.get("Yaw", value.get("Y", 0.0)),
                    value.get("Roll", value.get("Z", 0.0)),
                ),
            )
        return True
    if t == "Quaternion":
        target.value_kind = "QUATERNION"
        _set_vector(
            target,
            4,
            (
                value.get("i", 0.0),
                value.get("j", 0.0),
                value.get("k", 0.0),
                value.get("r", 1.0),
            ),
        )
        return True

    return False


def _field_summary(field: Any) -> str:
    kind = field.value_kind
    if kind == "BOOL":
        return str(bool(field.bool_value))
    if kind == "INT":
        return str(int(field.int_value))
    if kind == "UINT":
        return str(field.string_value or "0")
    if kind == "FLOAT":
        return f"{float(field.float_value):g}"
    if kind in {
        "STRING",
        "CNAME",
        "ENUM",
        "FLAGS_ENUM",
        "TRANSFORM_INDEX",
        "NAMED_TRACK_INDEX",
        "VISUAL_TAG_CONDITION",
    }:
        return str(field.string_value)
    if kind in {"VECTOR2", "VECTOR3", "VECTOR4", "QUATERNION", "FLOAT_CLAMP"}:
        n = max(1, min(4, int(getattr(field, "vector_size", 4))))
        return (
            "(" + ", ".join(f"{float(field.vector_value[i]):g}" for i in range(n)) + ")"
        )
    if kind == "QSTRANSFORM":
        t = field.qs_translation
        r = field.qs_rotation
        return f"T=({t[0]:g},{t[1]:g},{t[2]:g}) R=({r[0]:g},{r[1]:g},{r[2]:g},{r[3]:g})"
    if kind in {"STRUCT", "HANDLE_STRUCT"}:
        t = (
            getattr(field, "array_element_type", "")
            or getattr(field, "red_type", "")
            or "struct"
        )
        h = getattr(field, "struct_handle_id", "") or getattr(
            field, "struct_ref_id", ""
        )
        return f"{t} {h}".strip()
    if kind == "MATH_EXPRESSION":
        return str(getattr(field, "string_value", "") or "Math Expression")
    if kind == "NULL":
        return "null"
    return field.red_type or kind


def _element_summary(element: Any) -> str:
    pieces = []
    preferred = (
        "transformToChange",
        "sourceBone",
        "offsetSpaceBone",
        "name",
        "tag",
        "value",
        "offset",
    )
    fields = list(getattr(element, "fields", ()))
>>>>>>> Stashed changes
    by_key = {f.key: f for f in fields}
    for key in preferred:
        f = by_key.get(key)
        if f is not None:
            s = _field_summary(f)
            if s:
<<<<<<< Updated upstream
                pieces.append(f'{pretty_label(key)}={s}')
=======
                pieces.append(f"{pretty_label(key)}={s}")
>>>>>>> Stashed changes
        if len(pieces) >= 3:
            break
    if not pieces:
        for f in fields[:3]:
<<<<<<< Updated upstream
            pieces.append(f'{f.label or pretty_label(f.key)}={_field_summary(f)}')
    return '  '.join(pieces)

def _set_curve_from_json(item: Any, value: Any) -> None:
    item.value_kind = 'CURVE_FLOAT'
    item.red_type = item.red_type or 'curveData:Float'
    item.curve_interpolation_type = str(value.get('InterpolationType', 'BezierCubic'))
    item.curve_link_type = str(value.get('LinkType', 'ESLT_Normal'))
    item.curve_points.clear()
    for element in value.get('Elements', ()):  # type: ignore[union-attr]
        point = item.curve_points.add()
        point.point = float(element.get('Point', 0.0) or 0.0)
        point.value = float(element.get('Value', 0.0) or 0.0)
    item.curve_points_index = min(max(0, item.curve_points_index), max(0, len(item.curve_points) - 1))

def reset_curve_property_from_raw_json(item: Any) -> bool:
    value = _safe_json_loads(getattr(item, 'raw_json', ''), None)
=======
            pieces.append(f"{f.label or pretty_label(f.key)}={_field_summary(f)}")
    return "  ".join(pieces)


def _set_curve_from_json(item: Any, value: Any) -> None:
    item.value_kind = "CURVE_FLOAT"
    item.red_type = item.red_type or "curveData:Float"
    item.curve_interpolation_type = str(value.get("InterpolationType", "BezierCubic"))
    item.curve_link_type = str(value.get("LinkType", "ESLT_Normal"))
    item.curve_points.clear()
    for element in value.get("Elements", ()):  # type: ignore[union-attr]
        point = item.curve_points.add()
        point.point = float(element.get("Point", 0.0) or 0.0)
        point.value = float(element.get("Value", 0.0) or 0.0)
    item.curve_points_index = min(
        max(0, item.curve_points_index), max(0, len(item.curve_points) - 1)
    )


def reset_curve_property_from_raw_json(item: Any) -> bool:
    value = _safe_json_loads(getattr(item, "raw_json", ""), None)
>>>>>>> Stashed changes
    if not _is_curve_float_data(value):
        return False
    _set_curve_from_json(item, value)
    return True

<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
def sort_curve_points(item: Any) -> None:
    values = sorted((float(p.point), float(p.value)) for p in item.curve_points)
    item.curve_points.clear()
    for x, y in values:
        point = item.curve_points.add()
        point.point = x
        point.value = y
<<<<<<< Updated upstream
    item.curve_points_index = min(max(0, item.curve_points_index), max(0, len(item.curve_points) - 1))

def encode_curve_property(item: Any) -> dict:
    return {
        'InterpolationType': str(item.curve_interpolation_type or 'BezierCubic'),
        'LinkType': str(item.curve_link_type or 'ESLT_Normal'),
        'Elements': [
            {'Point': float(point.point), 'Value': float(point.value)}
            for point in item.curve_points
        ],
    }

def _set_math_expression_from_json(item: Any, value: Any) -> None:
    item.value_kind = 'MATH_EXPRESSION'
    item.red_type = 'animMathExpressionNodeData'
    parsed = math_expression.parse_expression_data(value) if math_expression is not None else {}
    item.string_value = str(parsed.get('summary', 'Math Expression'))
    item.raw_json = _safe_json_dumps(value)

def encode_math_expression_property(item: Any) -> Any:
    return _safe_json_loads(getattr(item, 'raw_json', ''), {})

def clear_node_properties(owner: Any) -> None:
    props = getattr(owner, 'red_properties', None)
    if props is not None:
        props.clear()

def _add_array_field(element: Any, key: str, value: Any, *, red_type_hint: str = '', label: Optional[str] = None) -> Optional[Any]:
=======
    item.curve_points_index = min(
        max(0, item.curve_points_index), max(0, len(item.curve_points) - 1)
    )


def encode_curve_property(item: Any) -> dict | None:
    """The curve as curveData"""
    curve = {
        "InterpolationType": str(item.curve_interpolation_type or "BezierCubic"),
        "LinkType": str(item.curve_link_type or "ESLT_Normal"),
        "Elements": [
            {"Point": float(point.point), "Value": float(point.value)}
            for point in item.curve_points
        ],
    }
    if item.get(_NULL_CURVE_KEY) and curve == _SEEDED_CURVE:
        return None
    return curve


def _set_math_expression_from_json(item: Any, value: Any) -> None:
    item.value_kind = "MATH_EXPRESSION"
    item.red_type = "animMathExpressionNodeData"
    parsed = (
        math_expression.parse_expression_data(value)
        if math_expression is not None
        else {}
    )
    item.string_value = str(parsed.get("summary", "Math Expression"))
    item.raw_json = _safe_json_dumps(value)


def encode_math_expression_property(item: Any) -> Any:
    return _safe_json_loads(getattr(item, "raw_json", ""), {})


def clear_node_properties(owner: Any) -> None:
    props = getattr(owner, "red_properties", None)
    if props is not None:
        props.clear()


def _add_array_field(
    element: Any,
    key: str,
    value: Any,
    *,
    red_type_hint: str = "",
    label: str | None = None,
) -> Any | None:
>>>>>>> Stashed changes
    field = element.fields.add()
    field.key = key
    field.label = label or pretty_label(key)
    field.red_type = red_type_hint or _infer_type_from_value(value)
    field.raw_json = _safe_json_dumps(value)
<<<<<<< Updated upstream
    ok = _decode_simple_into(field, value, red_type_hint=red_type_hint, field_name=key, json_path=key, parent_type=element.red_type)
=======
    ok = _decode_simple_into(
        field,
        value,
        red_type_hint=red_type_hint,
        field_name=key,
        json_path=key,
        parent_type=element.red_type,
    )
>>>>>>> Stashed changes
    if not ok:
        element.fields.remove(len(element.fields) - 1)
        return None
    return field

<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
def _element_field_type(struct_type: str, field_name: str, value: Any) -> str:
    hinted = _metadata_type_for(struct_type, field_name)
    if hinted:
        return hinted
    if isinstance(value, dict):
<<<<<<< Updated upstream
        t = str(value.get('$type', ''))
        if t:
            return t
        if _is_curve_float_data(value):
            return 'curveData:Float'
    if isinstance(value, bool):
        return 'Bool'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'Int32'
    if isinstance(value, float):
        return 'Float'
    if isinstance(value, str):
        return 'enum'
    return ''

def _decode_struct_element(element: Any, value: dict, element_type: str) -> bool:
    struct_type = str(value.get('$type') or element_type or '')
    element.red_type = struct_type
    keys = [k for k in value.keys() if not _is_hidden_field(k)]

    order = {}
    if rtti is not None and struct_type:
        try:
            order = {str(p.get('name')): i for i, p in enumerate(rtti.all_properties(struct_type))}
        except Exception:
=======
        t = str(value.get("$type", ""))
        if t:
            return t
        if _is_curve_float_data(value):
            return "curveData:Float"
    if isinstance(value, bool):
        return "Bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "Int32"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, str):
        return "enum"
    return ""


def _decode_struct_element(element: Any, value: dict, element_type: str) -> bool:
    struct_type = str(value.get("$type") or element_type or "")
    element.red_type = struct_type
    keys = [k for k in value if not _is_hidden_field(k)]

    order = {}
    if struct_type:
        try:
            order = {
                str(p.get("name")): i
                for i, p in enumerate(registry.all_properties(struct_type))
            }
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_decode_struct_element", type(error).__name__),
                "decode struct element: fell back after %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes
            order = {}
    keys.sort(key=lambda k: (order.get(k, 9999), list(value.keys()).index(k)))

    decoded = 0
    for key in keys:
        v = value.get(key)
        hint = _element_field_type(struct_type, key, v)
<<<<<<< Updated upstream
        if hint.startswith('array:') or hint.startswith('handle:') or hint.startswith('rRef:') or _is_link_type(hint):
            continue
        if hint and not _is_simple_type_hint(hint):

=======
        if (
            hint.startswith("array:")
            or hint.startswith("handle:")
            or hint.startswith("rRef:")
            or _is_link_type(hint)
        ):
            continue
        if hint and not _is_simple_type_hint(hint):
>>>>>>> Stashed changes
            continue
        f = _add_array_field(element, key, v, red_type_hint=hint)
        if f is not None:
            decoded += 1
    element.summary = _element_summary(element)
    return decoded > 0

<<<<<<< Updated upstream
def _set_array_from_json(item: Any, value: Any, red_type_hint: str = '') -> bool:
    if not isinstance(value, list):
        return False
    if red_type_hint and not red_type_hint.startswith('array:'):
        return False
    item.value_kind = 'ARRAY'
    item.red_type = red_type_hint or 'array'
    item.array_element_type = red_type_hint[6:] if red_type_hint.startswith('array:') else ''
=======

def _set_array_from_json(item: Any, value: Any, red_type_hint: str = "") -> bool:
    if not isinstance(value, list):
        return False
    if red_type_hint and not red_type_hint.startswith("array:"):
        return False
    item.value_kind = "ARRAY"
    item.red_type = red_type_hint or "array"
    item.array_element_type = (
        red_type_hint[6:] if red_type_hint.startswith("array:") else ""
    )
>>>>>>> Stashed changes
    item.array_items.clear()

    successes = 0
    for idx, element_value in enumerate(value):
        element = item.array_items.add()
<<<<<<< Updated upstream
        element.label = f'[{idx}]'
        element.raw_json = _safe_json_dumps(element_value)
        element.red_type = item.array_element_type or _infer_type_from_value(element_value)


        if item.array_element_type and _is_simple_type_hint(item.array_element_type):
            f = _add_array_field(element, 'value', element_value, red_type_hint=item.array_element_type, label='Value')
=======
        element.label = f"[{idx}]"
        element.raw_json = _safe_json_dumps(element_value)
        element.red_type = item.array_element_type or _infer_type_from_value(
            element_value
        )

        if item.array_element_type and _is_simple_type_hint(item.array_element_type):
            f = _add_array_field(
                element,
                "value",
                element_value,
                red_type_hint=item.array_element_type,
                label="Value",
            )
>>>>>>> Stashed changes
            if f is not None:
                element.summary = _field_summary(f)
                successes += 1
                continue

<<<<<<< Updated upstream

        if not isinstance(element_value, dict):
            f = _add_array_field(element, 'value', element_value, red_type_hint=_infer_type_from_value(element_value), label='Value')
=======
        if not isinstance(element_value, dict):
            f = _add_array_field(
                element,
                "value",
                element_value,
                red_type_hint=_infer_type_from_value(element_value),
                label="Value",
            )
>>>>>>> Stashed changes
            if f is not None:
                element.summary = _field_summary(f)
                successes += 1
                continue

        if isinstance(element_value, dict):
<<<<<<< Updated upstream
            etype = str(element_value.get('$type') or item.array_element_type or '')
            if etype == 'QsTransform' or _is_qstransform(element_value):
                f = _add_array_field(element, 'value', element_value, red_type_hint='QsTransform', label='Value')
                if f is not None:
                    element.red_type = 'QsTransform'
                    element.summary = _field_summary(f)
                    successes += 1
                    continue
=======
            etype = str(element_value.get("$type") or item.array_element_type or "")
            if etype == "QsTransform" or _is_qstransform(element_value):
                f = _add_array_field(
                    element,
                    "value",
                    element_value,
                    red_type_hint="QsTransform",
                    label="Value",
                )
                if f is not None:
                    element.red_type = "QsTransform"
                    element.summary = _field_summary(f)
                    successes += 1
                    continue
            wrapped = _handle_wrapper_payload(element_value)
            if wrapped is not None:
                # Owned handle element: edit its Data fields, keep the wrapper in raw_json.
                if _decode_struct_element(
                    element, wrapped, str(wrapped.get("$type", ""))
                ):
                    successes += 1
                    continue
                element.fields.clear()
                element.red_type = str(wrapped.get("$type", "") or etype)
                element.summary = element.red_type or "Raw JSON"
                successes += 1
                continue
>>>>>>> Stashed changes
            if _decode_struct_element(element, element_value, etype):
                successes += 1
                continue

<<<<<<< Updated upstream

        element.summary = element.red_type or 'Raw JSON'


    if value and successes == 0:
        item.array_items.clear()
        item.value_kind = 'RAW_JSON'
        item.red_type = red_type_hint or 'array'
        return False
    item.array_items_index = min(max(0, item.array_items_index), max(0, len(item.array_items) - 1))
    return True

=======
        element.summary = element.red_type or "Raw JSON"

    if value and successes == 0:
        item.array_items.clear()
        item.value_kind = "RAW_JSON"
        item.red_type = red_type_hint or "array"
        return False
    item.array_items_index = min(
        max(0, item.array_items_index), max(0, len(item.array_items) - 1)
    )
    return True


>>>>>>> Stashed changes
def add_node_property(
    owner: Any,
    key: str,
    value: Any,
    *,
<<<<<<< Updated upstream
    json_path: Optional[str] = None,
    label: Optional[str] = None,
    editable: bool = True,
    red_type_hint: Optional[str] = None,
) -> Optional[Any]:
    collection = getattr(owner, 'red_properties', None)
=======
    json_path: str | None = None,
    label: str | None = None,
    editable: bool = True,
    red_type_hint: str | None = None,
) -> Any | None:
    collection = getattr(owner, "red_properties", None)
>>>>>>> Stashed changes
    if collection is None:
        return None
    item = collection.add()
    item.key = key
    item.json_path = json_path or key
    item.label = label or pretty_label(key)
    item.editable = editable
    item.raw_json = _safe_json_dumps(value)
    _decode_into_property(item, value, red_type_hint=red_type_hint)
    return item

<<<<<<< Updated upstream
def seed_node_property(
    owner: Any,
    key: str,
    value_kind: str,
    default: Any = None,
    *,
    red_type: str = '',
    label: Optional[str] = None,
    editable: bool = True,
    red_type_hint: Optional[str] = None,
) -> Optional[Any]:
    collection = getattr(owner, 'red_properties', None)
    if collection is None:
        return None
    item = collection.add()
    item.key = key
    item.json_path = key
    item.label = label or pretty_label(key)
    item.value_kind = value_kind
    item.red_type = red_type
    item.editable = editable
    _assign_default(item, default)
    item.raw_json = _safe_json_dumps(encode_node_property(item))
    return item

def _decode_into_property(item: Any, value: Any, *, red_type_hint: Optional[str] = None) -> None:
    hint = str(red_type_hint or '')
    if hint:
        item.red_type = hint
        if hint == 'curveData:Float':
            if _is_curve_float_data(value):
                _set_curve_from_json(item, value)
            else:
                default = None
                _set_curve_from_json(item, default or {'InterpolationType': 'BezierCubic', 'LinkType': 'ESLT_Normal', 'Elements': [{'Point': 0.0, 'Value': 0.0}, {'Point': 1.0, 'Value': 1.0}]})
            item.red_type = 'curveData:Float'
            return
        if hint.startswith('array:') and isinstance(value, list):
=======

def _decode_into_property(
    item: Any, value: Any, *, red_type_hint: str | None = None
) -> None:
    hint = str(red_type_hint or "")
    payload = value.get("Data", {}) if isinstance(value, dict) else {}
    if (
        isinstance(payload, dict)
        and payload.get("$type") == "animPoseBlendMethod_BoneBranch"
    ):
        _set_array_from_json(
            item, payload.get("bones") or [], "array:animOverrideBlendBoneInfo"
        )
        item.value_kind = "POSE_BLEND_METHOD"
        item.red_type = payload["$type"]
        item.struct_handle_id = str(value.get("HandleId", ""))
        item.struct_ref_id = str(value.get("HandleRefId", ""))
        item.expanded = True
        for element in item.array_items:
            element.expanded = True
        return
    if hint:
        item.red_type = hint
        if hint == "curveData:Float":
            if _is_curve_float_data(value):
                _set_curve_from_json(item, value)
            else:
                # The editor shows a straight curve to start from; a null one exports null again until edited.
                _set_curve_from_json(item, _SEEDED_CURVE)
                item[_NULL_CURVE_KEY] = value is None
            item.red_type = "curveData:Float"
            return
        if hint.startswith("array:") and isinstance(value, list):
>>>>>>> Stashed changes
            if _set_array_from_json(item, value, hint):
                return

    if isinstance(value, list):
        if _set_array_from_json(item, value, hint):
            return
    if isinstance(value, dict) and _is_curve_float_data(value):
        _set_curve_from_json(item, value)
        return
<<<<<<< Updated upstream
    if isinstance(value, dict) and _is_math_expression_data(value):
        _set_math_expression_from_json(item, value)
        return
    if _decode_simple_into(item, value, red_type_hint=hint, field_name=item.key, json_path=item.json_path):
        return

    item.value_kind = 'RAW_JSON'
    item.red_type = item.red_type or hint or type(value).__name__
    item.string_value = ''

def _assign_default(item: Any, default: Any) -> None:
    kind = item.value_kind
    if kind == 'BOOL':
        item.bool_value = bool(default)
    elif kind == 'INT':
        item.int_value = int(default or 0)
    elif kind == 'UINT':
        item.string_value = _uint_string(default)
    elif kind == 'FLOAT':
        item.float_value = float(default or 0.0)
    elif kind in {'STRING', 'CNAME', 'ENUM', 'FLAGS_ENUM', 'TRANSFORM_INDEX', 'NAMED_TRACK_INDEX', 'VISUAL_TAG_CONDITION'}:
        item.string_value = '' if default is None else str(default)
    elif kind in {'VECTOR2', 'VECTOR3', 'VECTOR4', 'QUATERNION', 'FLOAT_CLAMP'}:
        sizes = {'VECTOR2': 2, 'FLOAT_CLAMP': 2, 'VECTOR3': 3, 'VECTOR4': 4, 'QUATERNION': 4}
        item.vector_size = sizes[kind]
        vals = list(default or [])
        for i in range(min(item.vector_size, len(vals))):
            item.vector_value[i] = float(vals[i])
        if kind == 'QUATERNION' and len(vals) < 4:
            item.vector_value[3] = 1.0
    elif kind == 'QSTRANSFORM':
        _set_qstransform(item, default if isinstance(default, dict) else {})
    elif kind == 'CURVE_FLOAT':
        value = default if isinstance(default, dict) else {'InterpolationType': 'BezierCubic', 'LinkType': 'ESLT_Normal', 'Elements': []}
        _set_curve_from_json(item, value)
    elif kind == 'ARRAY':
        _set_array_from_json(item, default if isinstance(default, list) else [], item.red_type)
    elif kind in {'STRUCT', 'HANDLE_STRUCT'}:
        value = default if isinstance(default, dict) else {'$type': item.red_type or item.array_element_type}
        if kind == 'HANDLE_STRUCT' and isinstance(value, dict) and isinstance(value.get('Data'), dict):
            _decode_struct_fields_into(item, value['Data'], str(value['Data'].get('$type', item.array_element_type or item.red_type)), value_kind='HANDLE_STRUCT', handle_id=str(value.get('HandleId', '')), ref_id=str(value.get('HandleRefId', '')))
        else:
            _decode_struct_fields_into(item, value, str(value.get('$type', item.array_element_type or item.red_type)), value_kind=kind)
    elif kind == 'MATH_EXPRESSION':
        _set_math_expression_from_json(item, default if isinstance(default, dict) else {'$type': 'animMathExpressionNodeData'})
    elif kind == 'RAW_JSON':
        item.raw_json = default if isinstance(default, str) else _safe_json_dumps(default)
    elif kind == 'NULL':
        item.editable = False

def encode_struct_property(item: Any) -> Any:
    elements = list(getattr(item, 'array_items', ()))
    element = elements[0] if elements else None
    base = _safe_json_loads(getattr(element, 'raw_json', '') if element is not None else getattr(item, 'raw_json', ''), {})
    if not isinstance(base, dict):
        base = {}
    struct_type = getattr(item, 'array_element_type', '') or getattr(item, 'red_type', '')
    if struct_type.startswith('handle:') or struct_type.startswith('rRef:'):
        struct_type = ''
    if struct_type:
        base.setdefault('$type', struct_type)
    if element is not None:
        for field in getattr(element, 'fields', ()):
            base[field.key] = encode_simple_value(field)
    if getattr(item, 'value_kind', '') == 'HANDLE_STRUCT':
        wrapper = _safe_json_loads(getattr(item, 'raw_json', ''), {})
        if not isinstance(wrapper, dict):
            wrapper = {}
        wrapper['Data'] = base
        handle_id = getattr(item, 'struct_handle_id', '') or getattr(item, 'string_value', '')
        ref_id = getattr(item, 'struct_ref_id', '')
        if handle_id:
            wrapper['HandleId'] = str(handle_id)
            wrapper.pop('HandleRefId', None)
        elif ref_id:
            wrapper['HandleRefId'] = str(ref_id)
            wrapper.pop('HandleId', None)
        return wrapper
    return base

def encode_simple_value(item: Any) -> Any:
    kind = item.value_kind
    red_type = item.red_type
    if kind == 'BOOL':
        return bool(item.bool_value)
    if kind == 'INT':
        return int(item.int_value)
    if kind == 'UINT':
        return _uint_from_string(getattr(item, 'string_value', '0'))
    if kind == 'FLOAT':
        return float(item.float_value)
    if kind == 'STRING':
        return str(item.string_value)
    if kind in {'ENUM', 'FLAGS_ENUM'}:
        if rtti is not None:
            try:
                return rtti.enum_encode_value(getattr(item, 'enum_type', '') or red_type, getattr(item, 'string_value', ''), storage=getattr(item, 'enum_storage', 'name'), raw_value=getattr(item, 'enum_raw_value', ''))
            except Exception:
                pass
        return str(item.string_value)
    if kind == 'CNAME':
        return {'$type': red_type or 'CName', '$storage': 'string', '$value': str(item.string_value)}
    if kind == 'TRANSFORM_INDEX':
        return {'$type': red_type or 'animTransformIndex', 'name': {'$type': 'CName', '$storage': 'string', '$value': str(item.string_value)}}
    if kind == 'NAMED_TRACK_INDEX':
        return {'$type': red_type or 'animNamedTrackIndex', 'name': {'$type': 'CName', '$storage': 'string', '$value': str(item.string_value)}}
    if kind == 'VISUAL_TAG_CONDITION':
        return {'$type': red_type or 'animVisualTagCondition', 'visualTag': {'$type': 'CName', '$storage': 'string', '$value': str(item.string_value)}}
    if kind == 'FLOAT_CLAMP':
        return {'$type': red_type or 'animFloatClamp', 'min': float(item.vector_value[0]), 'max': float(item.vector_value[1])}
    if kind == 'VECTOR2':
        return {'$type': red_type or 'Vector2', 'X': float(item.vector_value[0]), 'Y': float(item.vector_value[1])}
    if kind == 'VECTOR3':

        if red_type == 'EulerAngles':
            return {'$type': 'EulerAngles', 'Pitch': float(item.vector_value[0]), 'Yaw': float(item.vector_value[1]), 'Roll': float(item.vector_value[2])}
        return {'$type': red_type or 'Vector3', 'X': float(item.vector_value[0]), 'Y': float(item.vector_value[1]), 'Z': float(item.vector_value[2])}
    if kind == 'VECTOR4':
        return {'$type': red_type or 'Vector4', 'X': float(item.vector_value[0]), 'Y': float(item.vector_value[1]), 'Z': float(item.vector_value[2]), 'W': float(item.vector_value[3])}
    if kind == 'QUATERNION':
        return {'$type': red_type or 'Quaternion', 'i': float(item.vector_value[0]), 'j': float(item.vector_value[1]), 'k': float(item.vector_value[2]), 'r': float(item.vector_value[3])}
    if kind == 'QSTRANSFORM':
        return _encode_qstransform(item)
    if kind == 'CURVE_FLOAT':
        return encode_curve_property(item)
    if kind in {'STRUCT', 'HANDLE_STRUCT'}:
        return encode_struct_property(item)
    if kind == 'MATH_EXPRESSION':
        return encode_math_expression_property(item)
    if kind == 'NULL':
        return None
    if kind == 'RAW_JSON':
        return _safe_json_loads(item.raw_json, item.raw_json)
    return _safe_json_loads(getattr(item, 'raw_json', ''), getattr(item, 'string_value', ''))
=======
    if math_expression.is_math_expression_data(value):
        _set_math_expression_from_json(item, value)
        return
    if _decode_simple_into(
        item, value, red_type_hint=hint, field_name=item.key, json_path=item.json_path
    ):
        return

    item.value_kind = "RAW_JSON"
    item.red_type = item.red_type or hint or type(value).__name__
    item.string_value = ""


def encode_struct_property(item: Any) -> Any:
    elements = list(getattr(item, "array_items", ()))
    element = elements[0] if elements else None
    base = _safe_json_loads(
        getattr(element, "raw_json", "")
        if element is not None
        else getattr(item, "raw_json", ""),
        {},
    )
    if not isinstance(base, dict):
        base = {}
    struct_type = getattr(item, "array_element_type", "") or getattr(
        item, "red_type", ""
    )
    if struct_type.startswith("handle:") or struct_type.startswith("rRef:"):
        struct_type = ""
    if struct_type:
        base.setdefault("$type", struct_type)
    if element is not None:
        for field in getattr(element, "fields", ()):
            base[field.key] = encode_simple_value(field)
    if getattr(item, "value_kind", "") == "HANDLE_STRUCT":
        wrapper = _safe_json_loads(getattr(item, "raw_json", ""), {})
        if not isinstance(wrapper, dict):
            wrapper = {}
        wrapper["Data"] = base
        handle_id = getattr(item, "struct_handle_id", "") or getattr(
            item, "string_value", ""
        )
        ref_id = getattr(item, "struct_ref_id", "")
        if handle_id:
            wrapper["HandleId"] = str(handle_id)
            wrapper.pop("HandleRefId", None)
        elif ref_id:
            wrapper["HandleRefId"] = str(ref_id)
            wrapper.pop("HandleId", None)
        return wrapper
    return base


def encode_simple_value(item: Any) -> Any:
    kind = item.value_kind
    red_type = item.red_type
    if kind == "BOOL":
        # WolvenKit serializes CBool as 0/1.
        return int(bool(item.bool_value))
    if kind == "INT":
        return int(item.int_value)
    if kind == "UINT":
        return _uint_from_string(getattr(item, "string_value", "0"))
    if kind == "FLOAT":
        return float(item.float_value)
    if kind == "STRING":
        return str(item.string_value)
    if kind in {"ENUM", "FLAGS_ENUM"}:
        try:
            return enums.encode_value(
                getattr(item, "enum_type", "") or red_type,
                getattr(item, "string_value", ""),
                storage=getattr(item, "enum_storage", "name"),
                raw_value=getattr(item, "enum_raw_value", ""),
            )
        except (KeyError, TypeError, ValueError):
            pass
        return str(item.string_value)
    if kind == "CNAME":
        return {
            "$type": red_type or "CName",
            "$storage": "string",
            "$value": str(item.string_value),
        }
    if kind == "TRANSFORM_INDEX":
        return {
            "$type": red_type or "animTransformIndex",
            "name": {
                "$type": "CName",
                "$storage": "string",
                "$value": str(item.string_value),
            },
        }
    if kind == "NAMED_TRACK_INDEX":
        return {
            "$type": red_type or "animNamedTrackIndex",
            "name": {
                "$type": "CName",
                "$storage": "string",
                "$value": str(item.string_value),
            },
        }
    if kind == "VISUAL_TAG_CONDITION":
        return {
            "$type": red_type or "animVisualTagCondition",
            "visualTag": {
                "$type": "CName",
                "$storage": "string",
                "$value": str(item.string_value),
            },
        }
    if kind == "FLOAT_CLAMP":
        return {
            "$type": red_type or "animFloatClamp",
            "useMin": bool(getattr(item, "clamp_use_min", False)),
            "useMax": bool(getattr(item, "clamp_use_max", False)),
            "min": float(item.vector_value[0]),
            "max": float(item.vector_value[1]),
        }
    if kind == "VECTOR2":
        return {
            "$type": red_type or "Vector2",
            "X": float(item.vector_value[0]),
            "Y": float(item.vector_value[1]),
        }
    if kind == "VECTOR3":
        if red_type == "EulerAngles":
            return {
                "$type": "EulerAngles",
                "Pitch": float(item.vector_value[0]),
                "Yaw": float(item.vector_value[1]),
                "Roll": float(item.vector_value[2]),
            }
        return {
            "$type": red_type or "Vector3",
            "X": float(item.vector_value[0]),
            "Y": float(item.vector_value[1]),
            "Z": float(item.vector_value[2]),
        }
    if kind == "VECTOR4":
        return {
            "$type": red_type or "Vector4",
            "X": float(item.vector_value[0]),
            "Y": float(item.vector_value[1]),
            "Z": float(item.vector_value[2]),
            "W": float(item.vector_value[3]),
        }
    if kind == "QUATERNION":
        return {
            "$type": red_type or "Quaternion",
            "i": float(item.vector_value[0]),
            "j": float(item.vector_value[1]),
            "k": float(item.vector_value[2]),
            "r": float(item.vector_value[3]),
        }
    if kind == "QSTRANSFORM":
        return _encode_qstransform(item)
    if kind == "CURVE_FLOAT":
        return encode_curve_property(item)
    if kind in {"STRUCT", "HANDLE_STRUCT"}:
        return encode_struct_property(item)
    if kind == "MATH_EXPRESSION":
        return encode_math_expression_property(item)
    if kind == "NULL":
        return None
    if kind == "RAW_JSON":
        return _safe_json_loads(item.raw_json, item.raw_json)
    return _safe_json_loads(
        getattr(item, "raw_json", ""), getattr(item, "string_value", "")
    )

>>>>>>> Stashed changes

def encode_array_property(item: Any) -> list:
    out = []
    for element in item.array_items:
        fields = list(element.fields)
        if not fields:
            out.append(_safe_json_loads(element.raw_json, element.raw_json))
            continue
<<<<<<< Updated upstream
        if len(fields) == 1 and fields[0].key == 'value':
=======
        if len(fields) == 1 and fields[0].key == "value":
>>>>>>> Stashed changes
            out.append(encode_simple_value(fields[0]))
            continue
        base = _safe_json_loads(element.raw_json, {})
        if not isinstance(base, dict):
            base = {}
<<<<<<< Updated upstream
        if element.red_type:
            base.setdefault('$type', element.red_type)
        for field in fields:
            base[field.key] = encode_simple_value(field)
        out.append(base)
    return out

def encode_node_property(item: Any) -> Any:
    if item.value_kind == 'ARRAY':
        return encode_array_property(item)
    return encode_simple_value(item)

def encode_node_properties(owner: Any) -> dict:
    result = {}
    for item in getattr(owner, 'red_properties', ()):
        result[item.key] = encode_node_property(item)
    return result
=======
        payload = _handle_wrapper_payload(base)
        target = payload if payload is not None else base
        if element.red_type and not element.red_type.startswith("handle:"):
            target.setdefault("$type", element.red_type)
        for field in fields:
            target[field.key] = encode_simple_value(field)
        out.append(base)
    return out


def encode_node_property(item: Any) -> Any:
    if item.value_kind == "POSE_BLEND_METHOD":
        wrapper = _safe_json_loads(item.raw_json, {})
        payload = wrapper.setdefault("Data", {"$type": item.red_type})
        payload["bones"] = encode_array_property(item)
        return wrapper
    if item.value_kind == "ARRAY":
        return encode_array_property(item)
    return _rewrap_handle(getattr(item, "raw_json", ""), encode_simple_value(item))


def encode_node_properties(owner: Any) -> dict:
    result = {}
    for item in getattr(owner, "red_properties", ()):
        result[item.key] = encode_node_property(item)
    return result


def property_by_key(owner, key: str):
    props = getattr(owner, "red_properties", None)
    if not props:
        return None
    for item in props:
        if item.key == key:
            return item
    return None
>>>>>>> Stashed changes
