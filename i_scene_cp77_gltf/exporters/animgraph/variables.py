from typing import Any, Dict, List

import bpy

from ...blender.animgraph.access import get_idprop
from .tree_state import root_tree
from .values import cname, decode_optional, quaternion, vector4

def _decode_raw_entry(var: Any) -> Dict[str, Any]:
    raw = decode_optional(getattr(var, 'raw_json', ''), {})
    return raw if isinstance(raw, dict) else {}

def encode_variable_entry(var: Any) -> Dict[str, Any]:
    """Encode one graph variable entry using its typed value fields."""
    entry = _decode_raw_entry(var)
    data = entry.get('Data') if isinstance(entry.get('Data'), dict) else {}
    vt = str(getattr(var, 'var_type', '') or '')

    type_by_var = {
        'Bool': 'animAnimVariableBool',
        'Int': 'animAnimVariableInt',
        'Float': 'animAnimVariableFloat',
        'Vector': 'animAnimVariableVector',
        'Quaternion': 'animAnimVariableQuaternion',
        'Transform': 'animAnimVariableTransform',
    }
    data['$type'] = str(data.get('$type') or type_by_var.get(vt, 'animAnimVariable'))
    data['name'] = cname(str(getattr(var, 'name', '') or 'None'))

    if hasattr(var, 'enable_debug') and ('enableDebug' in data or vt in {'Bool', 'Int', 'Float'}):
        data['enableDebug'] = int(bool(getattr(var, 'enable_debug', False)))

    if vt == 'Bool':
        data['default'] = int(bool(getattr(var, 'default_bool', False)))
        data['value'] = int(bool(getattr(var, 'current_bool', False)))
    elif vt == 'Int':
        data['default'] = int(getattr(var, 'default_int', 0))
        data['value'] = int(getattr(var, 'current_int', 0))

    elif vt == 'Float':
        data['default'] = float(getattr(var, 'default_float', 0.0))
        data['value'] = float(getattr(var, 'current_float', 0.0))
        if bool(getattr(var, 'has_float_range', False)) or 'min' in data or 'max' in data:
            data['min'] = float(getattr(var, 'min_float', 0.0))
            data['max'] = float(getattr(var, 'max_float', 0.0))
    elif vt == 'Vector':
        data['default'] = vector4(getattr(var, 'default_vector', (0, 0, 0, 1)))
        cur = list(getattr(var, 'current_vector', (0, 0, 0, 1)))
        while len(cur) < 4:
            cur.append(1.0 if len(cur) == 3 else 0.0)

        data['x'] = float(cur[0]); data['y'] = float(cur[1]); data['z'] = float(cur[2]); data['w'] = float(cur[3])
    elif vt == 'Quaternion':
        data['default'] = quaternion(getattr(var, 'default_vector', (0, 0, 0, 1)))


        data.setdefault('pitch', 0)
        data.setdefault('roll', 0)
        data.setdefault('yaw', 0)
    elif vt == 'Transform':

        if 'default' not in data:
            default_json = decode_optional(getattr(var, 'default_json', ''), None)
            if default_json is not None:
                data['default'] = default_json
        if 'value' not in data:
            current_json = decode_optional(getattr(var, 'current_json', ''), None)
            if current_json is not None:
                data['value'] = current_json

    entry['Data'] = data
    handle_id = str(getattr(var, 'handle_id', '') or entry.get('HandleId', '') or '')
    if handle_id:
        entry['HandleId'] = handle_id
    return entry

def encode_root_variables(tree: bpy.types.NodeTree) -> Dict[str, Any]:
    root = root_tree(tree) or tree
    handle = str(get_idprop(root, 'red_variables_handle', '') or '')
    wrapper: Dict[str, Any] = {}
    data: Dict[str, Any] = {'$type': 'animAnimVariableContainer'}

    arrays = {
        'Bool': 'boolVariables',
        'Float': 'floatVariables',
        'Int': 'intVariables',
        'Quaternion': 'quaternionVariables',
        'Transform': 'transformVariables',
        'Vector': 'vectorVariables',
    }
    grouped: Dict[str, List[Dict[str, Any]]] = {array_name: [] for array_name in arrays.values()}
    for var in getattr(root, 'variables', []) or []:
        array_name = str(getattr(var, 'source_array', '') or arrays.get(str(getattr(var, 'var_type', '')), ''))
        if not array_name:
            continue
        grouped.setdefault(array_name, []).append(encode_variable_entry(var))
    for array_name, values in grouped.items():
        data[array_name] = values

    wrapper['Data'] = data
    if handle:
        wrapper['HandleId'] = handle
    return wrapper
