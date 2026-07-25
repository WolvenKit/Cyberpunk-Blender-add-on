from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import bpy

from .constants import ANIMGRAPH_TREE_ID, ANIM_NODE_PREFIX
from .properties import encode_node_property
try:
    from . import rtti_schema
except Exception:
    rtti_schema = None
try:
    from . import variable_bindings
except Exception:
    variable_bindings = None
try:
    from . import math_expression
except Exception:
    math_expression = None


TEXT_SELECTED_NODE = "REDengine Encoded Selected Node"
TEXT_ROOT_VARIABLES = "REDengine Encoded Root Variables"
TEXT_ACTIVE_TREE = "REDengine Encoded Active Tree"
TEXT_ROOTCHUNK_JSON = "REDengine Encoded RootChunk JSON"
TEXT_EXPORT_REVERSAL_AUDIT = "REDengine Export Reversal Audit"


ANIM_BASE_SERIALIZED_DEFAULT_FIELDS = frozenset({
    'id',
    'poseInfoLogger',
    'visAxes',
    'visMask',
    'visNames',
    'visPostPose',
    'visPostPoseColor',
    'visPrePose',
    'visPrePoseColor',
    'visRigPartMask',
    'visWhenActive',
})


NULL_ARRAY_DEFAULT_FIELDS = frozenset({
    'visMask',
})


NON_SERIALIZED_DEFAULT_FIELDS = frozenset({
    'debug',
    'debugFlag',
    'debugValueProvider',
    'debugMotion',
    'drawFirstFrame',
    'drawLastFrame',
    'drawFootstepFrameRU',
    'drawFootstepFrameRF',
    'drawFootstepFrameLU',
    'drawFootstepFrameLF',
    'drawFootstepFrameTimeOffset',
    'jsonPropertiesLoadedSuccessfully',
    'jsonPropertiesInput',
    'visTransition',
    'visTransitionDuration',
    'isInTestMode',
    'testIdleA',
    'testIdleB',
    'testIdleTransitionWeight',
    'entries',
})


def _get(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _idprop_get(obj: Any, key: str, default: Any = None) -> Any:
    try:
        return obj.get(key, default)
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _json_loads(text: Any, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(str(text))
    except Exception:
        return default


def _root_tree(tree: Optional[bpy.types.NodeTree]) -> Optional[bpy.types.NodeTree]:
    if tree is None:
        return None
    if variable_bindings is not None:
        try:
            return variable_bindings.root_tree_for(tree) or tree
        except Exception:
            pass
    parent_name = _idprop_get(tree, 'red_parent_graph', '')
    if parent_name:
        parent = bpy.data.node_groups.get(str(parent_name))
        if parent is not None and _get(parent, 'bl_idname', '') == ANIMGRAPH_TREE_ID:
            return parent
    return tree


def _runtime_node(node: Any) -> bool:
    red_type = str(_get(node, 'red_type', '') or '')
    if not red_type.startswith(ANIM_NODE_PREFIX):
        return False
    explicit = _get(node, 'red_exportable', None)
    if explicit is not None and not bool(explicit):
        return False
    return True


def _new_runtime_data_for_node(node: Any) -> Dict[str, Any]:
    """Return current-schema runtime Data for an authored node."""
    red_type = str(_get(node, 'red_type', '') or 'animAnimNode_Unknown')
    data = schema_default_data_for_type(red_type)
    data['$type'] = red_type
    return data


def _path_parts(path: str) -> List[Tuple[str, Optional[int]]]:
    """Parse REDengine JSON paths such as a.b[0].c."""
    out: List[Tuple[str, Optional[int]]] = []
    for segment in str(path or '').split('.'):
        if not segment:
            continue
        m = re.match(r'^([^\[]+)(?:\[(\d+)\])?$', segment)
        if not m:
            out.append((segment, None))
            continue
        name = m.group(1)
        idx = int(m.group(2)) if m.group(2) is not None else None
        out.append((name, idx))
    return out


def _ensure_list_size(values: List[Any], index: int) -> None:
    while len(values) <= index:
        values.append({})


def set_json_path(root: Dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted or indexed JSON path, creating containers as needed."""
    parts = _path_parts(path)
    if not parts:
        return
    obj: Any = root
    for i, (name, idx) in enumerate(parts):
        last = i == len(parts) - 1
        if idx is None:
            if last:
                if isinstance(obj, dict):
                    obj[name] = value
                return
            if not isinstance(obj, dict):
                return
            current = obj.get(name)
            if not isinstance(current, dict):
                current = {}
                obj[name] = current
            obj = current
        else:
            if not isinstance(obj, dict):
                return
            current = obj.get(name)
            if not isinstance(current, list):
                current = []
                obj[name] = current
            _ensure_list_size(current, idx)
            if last:
                current[idx] = value
                return
            if not isinstance(current[idx], dict):
                current[idx] = {}
            obj = current[idx]


def _handled_payload_path(root: Dict[str, Any], path: str) -> str:
    """Map editable paths through preserved HandleId/Data wrappers."""
    parts = _path_parts(path)
    if not parts or not isinstance(root, dict):
        return path
    name, idx = parts[0]
    if idx is None:
        current = root.get(name)
        if isinstance(current, dict) and isinstance(current.get('Data'), dict) and len(parts) > 1:
            return f"{name}.Data." + '.'.join(
                f"{n}[{i}]" if i is not None else n for n, i in parts[1:]
            )
    else:
        arr = root.get(name)
        if isinstance(arr, list) and 0 <= idx < len(arr):
            current = arr[idx]
            if isinstance(current, dict) and isinstance(current.get('Data'), dict) and len(parts) > 1:
                return f"{name}[{idx}].Data." + '.'.join(
                    f"{n}[{i}]" if i is not None else n for n, i in parts[1:]
                )
    return path


def set_export_socket_path(root: Dict[str, Any], path: str, value: Any) -> None:
    """Set a socket-link path through owned-payload wrappers."""
    set_json_path(root, _handled_payload_path(root, path), value)

def _link_source_handle(input_socket: bpy.types.NodeSocket) -> str:
    links = list(getattr(input_socket, 'links', []) or [])
    if links:
        source_node = getattr(links[0], 'from_node', None)
        handle = str(_get(source_node, 'red_handle_id', '') or '')
        if handle:
            return handle
    return str(_get(input_socket, 'red_source_handle', '') or '')


def _encode_link_wrapper(input_socket: bpy.types.NodeSocket) -> Dict[str, Any]:
    link_type = str(_get(input_socket, 'red_link_type', '') or '')
    source_handle = _link_source_handle(input_socket)
    wrapper: Dict[str, Any] = {'$type': link_type or 'animPoseLink'}
    if source_handle:


        wrapper['node'] = {'HandleRefId': str(source_handle)}
    else:
        wrapper['node'] = None
    return wrapper


def _iter_exportable_input_sockets(node: bpy.types.Node) -> Iterable[bpy.types.NodeSocket]:
    for sock in getattr(node, 'inputs', []) or []:
        if not bool(_get(sock, 'red_exportable', True)):
            continue
        if str(_get(sock, 'red_socket_role', '') or '') not in {'', 'input'}:
            continue
        if str(_get(sock, 'red_edge_semantics', '') or 'dataflow') != 'dataflow':
            continue
        path = str(_get(sock, 'red_json_path', '') or '')
        link_type = str(_get(sock, 'red_link_type', '') or '')
        if path and link_type:
            yield sock


def _schema_cname(value: str = 'None') -> Dict[str, Any]:
    return {'$type': 'CName', '$storage': 'string', '$value': str(value or 'None')}


def _schema_vector3(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Dict[str, Any]:
    return {'$type': 'Vector3', 'X': float(x), 'Y': float(y), 'Z': float(z)}


def _schema_vector4(x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 0.0) -> Dict[str, Any]:
    return {'$type': 'Vector4', 'X': float(x), 'Y': float(y), 'Z': float(z), 'W': float(w)}


def _schema_quaternion() -> Dict[str, Any]:
    return {'$type': 'Quaternion', 'i': 0.0, 'j': 0.0, 'k': 0.0, 'r': 1.0}


def _schema_qstransform() -> Dict[str, Any]:
    return {
        '$type': 'QsTransform',
        'Rotation': _schema_quaternion(),
        'Scale': _schema_vector4(1.0, 1.0, 1.0, 1.0),
        'Translation': _schema_vector4(0.0, 0.0, 0.0, 1.0),
    }


def _schema_color() -> Dict[str, Any]:
    return {'$type': 'Color', 'Alpha': 0, 'Blue': 0, 'Green': 0, 'Red': 0}


def _schema_resource_path() -> Dict[str, Any]:
    return {'$type': 'ResourcePath', '$storage': 'uint64', '$value': '0'}


def _unwrap_type_name(type_name: str) -> str:
    t = str(type_name or '')
    for prefix in ('handle:', 'rRef:'):
        if t.startswith(prefix):
            return t[len(prefix):]
    return t


def _is_schema_link_type(type_name: str) -> bool:
    if rtti_schema is not None:
        try:
            return bool(rtti_schema.is_link_type(type_name))
        except Exception:
            pass
    return str(type_name or '') in {
        'animPoseLink', 'animFloatLink', 'animVectorLink', 'animIntLink',
        'animBoolLink', 'animQuaternionLink', 'animTransformLink',
    }


def _default_link_wrapper(link_type: str) -> Dict[str, Any]:
    return {'$type': str(link_type or 'animPoseLink'), 'node': None}


def schema_default_value(type_name: str, *, field_name: str = '', parent_type: str = '', _depth: int = 0) -> Any:
    """Return the deterministic REDengine default for one RTTI field."""
    t = str(type_name or '')
    if _depth > 8:
        return None

    if t.startswith('array:'):
        if field_name in NULL_ARRAY_DEFAULT_FIELDS:
            return None
        return []
    if _is_schema_link_type(t):
        return _default_link_wrapper(t)


    if t.startswith('handle:'):
        return None
    if t.startswith('rRef:'):
        return {'DepotPath': _schema_resource_path(), 'Flags': 'Default'}

    if rtti_schema is not None:
        try:
            enum_type = rtti_schema.resolve_enum_type(t, field_name=field_name, parent_type=parent_type, json_path=field_name, value=None)
            if enum_type:
                return rtti_schema.enum_default(enum_type)
        except Exception:
            pass

    if t == 'Bool':
        return 0
    if t in {'Int8', 'Int16', 'Int32', 'Int64'}:
        return 0
    if t in {'Uint8', 'Uint16', 'Uint32', 'Uint64'}:
        if field_name == 'id':
            return 4294967295
        return 0
    if t in {'Float', 'Double'}:
        return 0
    if t == 'String':
        return ''
    if t == 'CName':
        return _schema_cname('None')
    if t == 'ResourcePath':
        return _schema_resource_path()
    if t == 'Color':
        return _schema_color()
    if t == 'Vector2':
        return {'$type': 'Vector2', 'X': 0.0, 'Y': 0.0}
    if t == 'Vector3':
        return _schema_vector3()
    if t == 'Vector4':
        return _schema_vector4()
    if t == 'EulerAngles':
        return {'$type': 'EulerAngles', 'Pitch': 0.0, 'Yaw': 0.0, 'Roll': 0.0}
    if t == 'Quaternion':
        return _schema_quaternion()
    if t == 'QsTransform':
        return _schema_qstransform()
    if t == 'animTransformIndex':
        return {'$type': 'animTransformIndex', 'name': _schema_cname('None')}
    if t == 'animNamedTrackIndex':
        return {'$type': 'animNamedTrackIndex', 'name': _schema_cname('None')}
    if t == 'animVisualTagCondition':
        return {'$type': 'animVisualTagCondition', 'visualTag': _schema_cname('None')}
    if t == 'animFloatClamp':
        return {'$type': 'animFloatClamp', 'min': 0.0, 'max': 1.0}
    if t == 'curveData:Float':
        try:
            from .metadata_schema import DEFAULT_FLOAT_CURVE
            return json.loads(json.dumps(DEFAULT_FLOAT_CURVE))
        except Exception:
            return {'InterpolationType': 'BezierCubic', 'LinkType': 'ESLT_Normal', 'Elements': [{'Point': 0.0, 'Value': 0.0}, {'Point': 1.0, 'Value': 1.0}]}


    if rtti_schema is not None:
        inner = _unwrap_type_name(t)
        try:
            if inner and rtti_schema.has_class(inner) and not rtti_schema.is_graph_node_class(inner):
                return schema_default_struct_for_type(inner, _depth=_depth + 1)
        except Exception:
            pass

    return None


def schema_default_struct_for_type(red_type: str, *, _depth: int = 0) -> Dict[str, Any]:
    out: Dict[str, Any] = {'$type': str(red_type or '')}
    if rtti_schema is None or not red_type:
        return out
    try:
        props = rtti_schema.all_properties(red_type)
    except Exception:
        return out
    for prop in props:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get('name', '') or '')
        ptype = str(prop.get('type', '') or '')
        if not name or name == '$type':
            continue
        if name in NON_SERIALIZED_DEFAULT_FIELDS:
            continue
        out[name] = schema_default_value(ptype, field_name=name, parent_type=red_type, _depth=_depth + 1)
    return out


def schema_default_data_for_type(red_type: str) -> Dict[str, Any]:
    """Materialize current-schema default Data for one runtime node type."""
    data: Dict[str, Any] = {'$type': str(red_type or 'animAnimNode_Unknown')}
    if rtti_schema is None or not red_type:
        return data
    try:
        chain = rtti_schema.parent_chain(red_type, include_self=True)
    except Exception:
        chain = (red_type,)
    for owner_type in chain:
        try:
            props = rtti_schema.declared_properties(owner_type)
        except Exception:
            props = ()
        for prop in props:
            if not isinstance(prop, dict):
                continue
            name = str(prop.get('name', '') or '')
            ptype = str(prop.get('type', '') or '')
            if not name or name == '$type':
                continue
            if name in NON_SERIALIZED_DEFAULT_FIELDS:
                continue


            if owner_type == f'{ANIM_NODE_PREFIX}Base' and name not in ANIM_BASE_SERIALIZED_DEFAULT_FIELDS:
                continue
            data[name] = schema_default_value(ptype, field_name=name, parent_type=owner_type)


        if owner_type == f'{ANIM_NODE_PREFIX}Base':
            data.setdefault('visWhenActive', 0)

    data['$type'] = str(red_type or data.get('$type', 'animAnimNode_Unknown'))
    return data


def _container_subtree(node: Any) -> Optional[bpy.types.NodeTree]:
    tree = getattr(node, 'node_tree', None)
    if tree is not None and getattr(tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID:
        return tree
    return None


def _runtime_nodes_in_tree(tree: Optional[bpy.types.NodeTree]) -> List[bpy.types.Node]:
    if tree is None:
        return []
    nodes = [node for node in _tree_nodes(tree) if _runtime_node(node)]
    nodes.sort(key=_node_sort_key)
    return nodes


def _json_idprop(obj: Any, key: str, default: Any) -> Any:
    value = _json_loads(_idprop_get(obj, key, ''), default)
    return default if value is None and default is not None else value


def _top_path(path: str) -> str:
    text = str(path or '')
    if not text:
        return ''
    head = text.split('.', 1)[0]
    if '[' in head:
        head = head.split('[', 1)[0]
    return head


def _source_data_keys(node: Any) -> Optional[set]:
    raw = _json_loads(_idprop_get(node, 'red_source_data_keys_json', ''), None)
    if raw is None:
        handle = str(_get(node, 'red_handle_id', '') or '')
        if handle.startswith('new:'):
            return None
        raise ValueError(f'missing required source metadata: red_source_data_keys_json on HandleId {handle or "<unknown>"}')
    if not isinstance(raw, list):
        handle = str(_get(node, 'red_handle_id', '') or '')
        raise ValueError(f'invalid required source metadata: red_source_data_keys_json on HandleId {handle or "<unknown>"}')
    return {str(key) for key in raw if str(key)}


def _apply_source_field_shape(node: Any, data: Dict[str, Any]) -> None:
    """Remove schema defaults that were absent from the imported node."""
    keys = _source_data_keys(node)
    if keys is None:
        return
    allowed = set(keys)
    allowed.add('$type')

    for item in getattr(node, 'red_properties', []) or []:
        top = _top_path(str(getattr(item, 'json_path', '') or getattr(item, 'key', '') or ''))
        if top:
            allowed.add(top)

    for sock in _iter_exportable_input_sockets(node):
        top = _top_path(str(_get(sock, 'red_json_path', '') or ''))
        if top:
            allowed.add(top)

    preserved = _json_idprop(node, 'red_preserved_export_fields_json', {})
    if isinstance(preserved, dict):
        allowed.update(str(key) for key in preserved.keys())

    for field in ('nodes', 'states', 'frozenState', 'transitions', 'globalTransitions', 'conditionalEntries', 'anyStateInterpolator', 'outTransitionIndices'):
        if field in data and field in keys:
            allowed.add(field)

    for key in list(data.keys()):
        if key not in allowed:
            data.pop(key, None)


def _red_type(node: Any) -> str:
    return str(_get(node, 'red_type', '') or '')


def _handle(node: Any) -> str:
    return str(_get(node, 'red_handle_id', '') or '')


def _is_type(node: Any, short_name: str) -> bool:
    return _red_type(node) == f'{ANIM_NODE_PREFIX}{short_name}'


def _state_order_handles(sm_node: Any, sm_tree: bpy.types.NodeTree) -> List[str]:
    sm_handle = _handle(sm_node)
    pseudo_name = f'editorStateMachineOutput_{sm_handle}'
    pseudo = getattr(sm_tree, 'nodes', {}).get(pseudo_name) if sm_tree is not None else None
    handles = _json_loads(_idprop_get(pseudo, 'red_state_handles', ''), []) if pseudo is not None else []
    if isinstance(handles, list):
        return [str(h) for h in handles if h is not None]
    return []


def _ordered_state_nodes(sm_node: Any, sm_tree: bpy.types.NodeTree) -> List[bpy.types.Node]:
    states = [node for node in _runtime_nodes_in_tree(sm_tree) if _is_type(node, 'State')]
    by_handle = {_handle(node): node for node in states if _handle(node)}
    ordered: List[bpy.types.Node] = []
    for handle in _state_order_handles(sm_node, sm_tree):
        node = by_handle.pop(handle, None)
        if node is not None:
            ordered.append(node)
    ordered.extend(sorted(by_handle.values(), key=_node_sort_key))
    return ordered


def _state_frozen_node(sm_tree: bpy.types.NodeTree) -> Optional[bpy.types.Node]:
    frozen = [node for node in _runtime_nodes_in_tree(sm_tree) if _is_type(node, 'StateFrozen')]
    if not frozen:
        return None
    frozen.sort(key=_node_sort_key)
    return frozen[0]


def _encode_tree_runtime_entries(
    tree: Optional[bpy.types.NodeTree],
    *,
    embed_containers: bool,
    _stack: Optional[set] = None,
    exclude_handles: Optional[set] = None,
    predicate=None,
) -> List[Dict[str, Any]]:
    if tree is None:
        return []
    entries: List[Dict[str, Any]] = []
    exclude_handles = exclude_handles or set()
    for child in _runtime_nodes_in_tree(tree):
        handle = _handle(child)
        if handle in exclude_handles:
            continue
        if predicate is not None and not predicate(child):
            continue
        entries.append(encode_runtime_node_entry(child, embed_containers=embed_containers, _stack=_stack))
    return entries


def _embed_state_out_transition_indices(node: bpy.types.Node, data: Dict[str, Any]) -> None:
    if not (_is_type(node, 'State') or _is_type(node, 'StateFrozen')):
        return
    if 'red_state_outTransitionIndices_json' in node:
        indices = _json_idprop(node, 'red_state_outTransitionIndices_json', [])
        data['outTransitionIndices'] = indices if isinstance(indices, list) else []


def _embed_state_machine_fields(node: bpy.types.Node, data: Dict[str, Any], _stack: set) -> None:
    sm_tree = _container_subtree(node)
    if sm_tree is None:
        return

    states = _ordered_state_nodes(node, sm_tree)
    data['states'] = [
        encode_runtime_node_entry(state, embed_containers=True, _stack=_stack)
        for state in states
    ]

    frozen = _state_frozen_node(sm_tree)
    data['frozenState'] = (
        encode_runtime_node_entry(frozen, embed_containers=True, _stack=_stack)
        if frozen is not None else None
    )


    for key in ('transitions', 'conditionalEntries', 'globalTransitions'):
        prop = f'red_sm_{key}_json'
        if prop in node:
            value = _json_idprop(node, prop, [])
            data[key] = value if isinstance(value, list) else []
    if 'red_sm_anyStateInterpolator_json' in node:
        data['anyStateInterpolator'] = _json_loads(_idprop_get(node, 'red_sm_anyStateInterpolator_json', ''), None)


def _embed_generic_nodes_container(node: bpy.types.Node, data: Dict[str, Any], _stack: set) -> None:
    child_tree = _container_subtree(node)
    if child_tree is None:
        return
    if 'nodes' in data or _is_type(node, 'State') or _is_type(node, 'StateFrozen'):
        data['nodes'] = _encode_tree_runtime_entries(child_tree, embed_containers=True, _stack=_stack)


def _embed_container_fields(node: bpy.types.Node, data: Dict[str, Any], _stack: set) -> None:
    red_type = _red_type(node)
    if not red_type:
        return
    _embed_state_out_transition_indices(node, data)
    short = red_type.replace(ANIM_NODE_PREFIX, '')
    if short in {'StateMachine', 'LocomotionMachine'} or 'states' in data:
        _embed_state_machine_fields(node, data, _stack)
        return
    _embed_generic_nodes_container(node, data, _stack)


def _apply_preserved_export_fields(node: Any, data: Dict[str, Any]) -> None:
    """Restore preserved owned-payload fields before editable overlays."""
    fields = _json_idprop(node, 'red_preserved_export_fields_json', {})
    if not isinstance(fields, dict):
        return
    for key, value in fields.items():
        if not key or str(key).startswith('$'):
            continue
        try:
            data[str(key)] = _json_clone(value)
        except Exception:
            data[str(key)] = value


def _apply_preserved_math_expression_data(node: Any, data: Dict[str, Any]) -> None:
    """Restore hidden MathExpression payload state before editable overlays."""
    red_type = str(_get(node, 'red_type', '') or '')
    if not red_type.startswith(f'{ANIM_NODE_PREFIX}MathExpression'):
        return
    expr = _json_idprop(node, 'red_math_expression_data_json', None)
    if isinstance(expr, dict):
        data['expressionData'] = expr


_MATH_EXPRESSION_SOCKET_ARRAYS = {
    'floatSockets': ('animFloatLink', 'animAnimMathExpressionFloatSocket'),
    'vectorSockets': ('animVectorLink', 'animAnimMathExpressionVectorSocket'),
    'quaternionSockets': ('animQuaternionLink', 'animAnimMathExpressionQuaternionSocket'),
}

_MATH_EXPRESSION_RETURN_BY_TYPE = {
    f'{ANIM_NODE_PREFIX}MathExpressionFloat': 1,
    f'{ANIM_NODE_PREFIX}MathExpressionVector': 2,
    f'{ANIM_NODE_PREFIX}MathExpressionQuaternion': 3,
}


def _is_math_expression_node(node: Any) -> bool:
    return str(_get(node, 'red_type', '') or '').startswith(f'{ANIM_NODE_PREFIX}MathExpression')


def _math_expression_data(data: Dict[str, Any]) -> Dict[str, Any]:
    expr = data.get('expressionData')
    if not isinstance(expr, dict):
        expr = {'$type': 'animMathExpressionNodeData'}
        data['expressionData'] = expr
    expr.setdefault('$type', 'animMathExpressionNodeData')
    for array_name in _MATH_EXPRESSION_SOCKET_ARRAYS:
        if not isinstance(expr.get(array_name), list):
            expr[array_name] = []
    return expr


def _math_expression_payload_data(node: Any, expr: Dict[str, Any]) -> Dict[str, Any]:
    expression = expr.get('expression')
    if not isinstance(expression, dict):
        expression = {}
        expr['expression'] = expression
    handle = str(_idprop_get(node, 'red_math_expression_handle', '') or '')
    if handle and not expression.get('HandleId') and not expression.get('HandleRefId'):
        expression['HandleId'] = handle
    payload = expression.get('Data')
    if not isinstance(payload, dict):
        payload = {}
        expression['Data'] = payload
    payload.setdefault('$type', 'mathExprExpression')
    payload.setdefault('returnVarType', _MATH_EXPRESSION_RETURN_BY_TYPE.get(str(_get(node, 'red_type', '') or ''), 0))
    payload.setdefault('tokenData', [])
    payload.setdefault('valuesData', [])
    return payload


def _math_socket_path(path: str) -> Optional[Tuple[str, int]]:
    for array_name in _MATH_EXPRESSION_SOCKET_ARRAYS:
        prefix = f'expressionData.{array_name}['
        if not str(path or '').startswith(prefix):
            continue
        rest = str(path)[len(prefix):]
        index_text = rest.split(']', 1)[0]
        try:
            return array_name, int(index_text)
        except Exception:
            return None
    return None


def _ensure_math_socket(expr: Dict[str, Any], array_name: str, index: int) -> Dict[str, Any]:
    link_type, struct_type = _MATH_EXPRESSION_SOCKET_ARRAYS[array_name]
    arr = expr.get(array_name)
    if not isinstance(arr, list):
        arr = []
        expr[array_name] = arr
    _ensure_list_size(arr, index)
    item = arr[index]
    if not isinstance(item, dict):
        item = {}
        arr[index] = item
    item.setdefault('$type', struct_type)
    item.setdefault('expressionVarId', index)
    if array_name == 'floatSockets':
        item.setdefault('inputFloatTrack', {'$type': 'animNamedTrackIndex', 'name': _cname('None')})
    link = item.get('link')
    if not isinstance(link, dict):
        item['link'] = {'$type': link_type, 'node': None}
    else:
        link.setdefault('$type', link_type)
        link.setdefault('node', None)
    return item


def _finalize_math_expression_data(node: Any, data: Dict[str, Any]) -> None:
    """Finalize MathExpression payload structure after editable overlays."""
    if not _is_math_expression_node(node):
        return
    expr = _math_expression_data(data)
    payload = _math_expression_payload_data(node, expr)


    for item in getattr(node, 'red_properties', []) or []:
        path = str(getattr(item, 'json_path', '') or getattr(item, 'key', '') or '')
        if path == 'expressionData.expression.Data.tokenData':
            payload['tokenData'] = encode_node_property(item)
        elif path == 'expressionData.expression.Data.valuesData':
            payload['valuesData'] = encode_node_property(item)


    for sock in _iter_exportable_input_sockets(node):
        parsed = _math_socket_path(str(_get(sock, 'red_json_path', '') or ''))
        if parsed is None:
            continue
        array_name, index = parsed
        item = _ensure_math_socket(expr, array_name, index)
        item['link'] = _encode_link_wrapper(sock)

def encode_runtime_node_data(
    node: bpy.types.Node,
    *,
    embed_containers: bool = False,
    _stack: Optional[set] = None,
) -> Dict[str, Any]:
    """Encode one runtime node Data object from editable properties and sockets."""
    if not _runtime_node(node):
        raise ValueError('active node is not an exportable REDengine runtime node')
    data = _new_runtime_data_for_node(node)
    data['$type'] = str(_get(node, 'red_type', '') or data.get('$type', ''))
    _apply_preserved_export_fields(node, data)
    _apply_preserved_math_expression_data(node, data)

    for item in getattr(node, 'red_properties', []) or []:
        path = str(getattr(item, 'json_path', '') or getattr(item, 'key', '') or '')
        if not path:
            continue
        set_json_path(data, path, encode_node_property(item))

    for sock in _iter_exportable_input_sockets(node):
        set_export_socket_path(data, str(sock.red_json_path), _encode_link_wrapper(sock))

    _finalize_math_expression_data(node, data)

    if embed_containers:
        if _stack is None:
            _stack = set()
        handle = _handle(node)
        if handle and handle in _stack:
            _apply_source_field_shape(node, data)
            return data
        if handle:
            _stack.add(handle)
        try:
            _embed_container_fields(node, data, _stack)
        finally:
            if handle:
                _stack.discard(handle)

    _apply_source_field_shape(node, data)
    return data


def encode_runtime_node_entry(
    node: bpy.types.Node,
    *,
    embed_containers: bool = False,
    _stack: Optional[set] = None,
) -> Dict[str, Any]:
    handle = str(_get(node, 'red_handle_id', '') or '')
    if not handle:
        raise ValueError('runtime node is missing red_handle_id')
    return {'HandleId': handle, 'Data': encode_runtime_node_data(node, embed_containers=embed_containers, _stack=_stack)}


def encode_selected_node(context: bpy.types.Context) -> Dict[str, Any]:
    node = getattr(context, 'active_node', None)
    if node is None:
        raise ValueError('no active node')
    return encode_runtime_node_entry(node)


def _cname(value: str) -> Dict[str, Any]:
    return {'$type': 'CName', '$storage': 'string', '$value': str(value or 'None')}


def _vec4(values: Iterable[Any], *, default_w: float = 1.0) -> Dict[str, Any]:
    vals = list(values)
    while len(vals) < 4:
        vals.append(default_w if len(vals) == 3 else 0.0)
    return {'$type': 'Vector4', 'X': float(vals[0]), 'Y': float(vals[1]), 'Z': float(vals[2]), 'W': float(vals[3])}


def _quat(values: Iterable[Any]) -> Dict[str, Any]:
    vals = list(values)
    while len(vals) < 4:
        vals.append(1.0 if len(vals) == 3 else 0.0)
    return {'$type': 'Quaternion', 'i': float(vals[0]), 'j': float(vals[1]), 'k': float(vals[2]), 'r': float(vals[3])}


def _decode_raw_entry(var: Any) -> Dict[str, Any]:
    raw = _json_loads(getattr(var, 'raw_json', ''), {})
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
    data['name'] = _cname(str(getattr(var, 'name', '') or 'None'))

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
        data['default'] = _vec4(getattr(var, 'default_vector', (0, 0, 0, 1)))
        cur = list(getattr(var, 'current_vector', (0, 0, 0, 1)))
        while len(cur) < 4:
            cur.append(1.0 if len(cur) == 3 else 0.0)

        data['x'] = float(cur[0]); data['y'] = float(cur[1]); data['z'] = float(cur[2]); data['w'] = float(cur[3])
    elif vt == 'Quaternion':
        data['default'] = _quat(getattr(var, 'default_vector', (0, 0, 0, 1)))


        data.setdefault('pitch', 0)
        data.setdefault('roll', 0)
        data.setdefault('yaw', 0)
    elif vt == 'Transform':

        if 'default' not in data:
            default_json = _json_loads(getattr(var, 'default_json', ''), None)
            if default_json is not None:
                data['default'] = default_json
        if 'value' not in data:
            current_json = _json_loads(getattr(var, 'current_json', ''), None)
            if current_json is not None:
                data['value'] = current_json

    entry['Data'] = data
    handle_id = str(getattr(var, 'handle_id', '') or entry.get('HandleId', '') or '')
    if handle_id:
        entry['HandleId'] = handle_id
    return entry


def encode_root_variables(tree: bpy.types.NodeTree) -> Dict[str, Any]:
    root = _root_tree(tree) or tree
    handle = str(_idprop_get(root, 'red_variables_handle', '') or '')
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


def _tree_bool(tree: Any, key: str) -> bool:
    return bool(_idprop_get(tree, key, False))


def _node_sort_key(node: Any) -> Tuple[int, int, float, float, str]:
    handle = str(_get(node, 'red_handle_id', '') or '')
    numeric = 0
    value = 0
    if handle.isdigit():
        numeric = 1
        value = int(handle)
    try:
        loc = getattr(node, 'location', None)
        x = float(getattr(loc, 'x', 0.0))
        y = float(getattr(loc, 'y', 0.0))
    except Exception:
        x = 0.0
        y = 0.0

    return (0 if numeric else 1, value, x, y, str(getattr(node, 'name', '')))


def _tree_nodes(tree: bpy.types.NodeTree) -> List[bpy.types.Node]:
    try:
        return list(getattr(tree, 'nodes', []) or [])
    except Exception:
        return []


def _is_editor_projection_node(node: Any) -> bool:
    if _runtime_node(node):
        return False
    red_type = str(_get(node, 'red_type', '') or '')
    handle = str(_get(node, 'red_handle_id', '') or '')
    if red_type or handle:
        return True
    if bool(_get(node, 'red_pseudo', False)):
        return True


    return True


def _collect_tree_link_references(entries: List[Dict[str, Any]], local_handles: set) -> Tuple[List[Dict[str, str]], int]:
    refs: List[Dict[str, str]] = []
    local_count = 0

    def walk(value: Any, owner_handle: str = '', path: str = '') -> None:
        nonlocal local_count
        if isinstance(value, dict):
            node_ref = value.get('node')
            if isinstance(node_ref, dict):
                ref = str(node_ref.get('HandleRefId', '') or node_ref.get('HandleId', '') or '')
                if ref:
                    if ref in local_handles:
                        local_count += 1
                    else:
                        refs.append({'owner': owner_handle, 'path': path, 'target': ref})
            for key, child in value.items():
                child_path = f'{path}.{key}' if path else str(key)
                walk(child, owner_handle=owner_handle, path=child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, owner_handle=owner_handle, path=f'{path}[{index}]')

    for entry in entries:
        handle = str(entry.get('HandleId', '') or '')
        walk(entry.get('Data'), owner_handle=handle, path='Data')
    return refs, local_count


def encode_active_tree(tree: bpy.types.NodeTree) -> Dict[str, Any]:
    if tree is None or getattr(tree, 'bl_idname', '') != ANIMGRAPH_TREE_ID:
        raise ValueError('active editor tree is not a REDengine animGraph tree')

    all_nodes = _tree_nodes(tree)
    runtime_nodes = [node for node in all_nodes if _runtime_node(node)]
    skipped_nodes = [node for node in all_nodes if node not in runtime_nodes and _is_editor_projection_node(node)]
    runtime_nodes.sort(key=_node_sort_key)

    entries: List[Dict[str, Any]] = []
    blockers: List[str] = []
    warnings: List[str] = []
    seen: Dict[str, str] = {}

    for node in runtime_nodes:
        handle = str(_get(node, 'red_handle_id', '') or '')
        if not handle:
            blockers.append(f'{getattr(node, "name", "<node>")}: missing red_handle_id')
            continue
        if handle in seen:
            blockers.append(f'duplicate HandleId {handle}: {seen[handle]} and {getattr(node, "name", "<node>")}')
            continue
        seen[handle] = str(getattr(node, 'name', '<node>'))
        try:
            entries.append(encode_runtime_node_entry(node, embed_containers=False))
        except Exception as exc:
            blockers.append(f'{handle} {getattr(node, "name", "<node>")}: {exc}')

    local_handles = {str(entry.get('HandleId', '')) for entry in entries if entry.get('HandleId')}
    external_refs, local_ref_count = _collect_tree_link_references(entries, local_handles)
    if external_refs:
        warnings.append(f'{len(external_refs)} encoded HandleRefId reference(s) target nodes outside the active tree')

    root = _root_tree(tree) or tree
    summary = {
        'runtimeNodes': len(runtime_nodes),
        'encodedNodes': len(entries),
        'editorSkipped': len(skipped_nodes),
        'localHandleRefs': local_ref_count,
        'externalHandleRefs': len(external_refs),
        'blockers': len(blockers),
        'warnings': len(warnings),
        'ready': len(blockers) == 0,
    }
    return {
        'tree': str(getattr(tree, 'name', '<tree>')),
        'rootTree': str(getattr(root, 'name', '<root>')),
        'internalSubgraph': _tree_bool(tree, 'red_internal_subgraph'),
        'editorSubgraph': _tree_bool(tree, 'red_editor_subgraph'),
        'ordering': 'diagnostic numeric HandleId order; not final RootChunk/nodesToInit order',
        'summary': summary,
        'blockers': blockers,
        'warnings': warnings,
        'externalReferences': external_refs,
        'nodes': entries,
    }


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _is_full_handle_entry(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get('HandleId')) and isinstance(value.get('Data'), dict)


def _is_ref_handle_entry(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get('HandleRefId')) and 'Data' not in value


def _entry_handle_value(value: Any) -> str:
    if not isinstance(value, dict):
        return ''
    return str(value.get('HandleId', '') or value.get('HandleRefId', '') or '')


def _collect_full_handle_entries(value: Any, out: Dict[str, Dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if _is_full_handle_entry(value):
            handle = str(value.get('HandleId') or '')
            if handle and handle not in out:
                out[handle] = value
        for child in value.values():
            _collect_full_handle_entries(child, out)
    elif isinstance(value, list):
        for child in value:
            _collect_full_handle_entries(child, out)


def _is_link_wrapper(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    link_type = str(value.get('$type', '') or '')
    return bool(link_type) and link_type.startswith('anim') and link_type.endswith('Link') and 'node' in value


def normalize_inline_first_references(root_entry: Dict[str, Any], extra_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Rewrite handle references into WolvenKit inline-first shape."""
    handle_map: Dict[str, Dict[str, Any]] = {}
    _collect_full_handle_entries(root_entry, handle_map)


    if extra_entries:
        _collect_full_handle_entries(extra_entries, handle_map)

    stats = {
        'knownHandles': len(handle_map),
        'fullEntries': 0,
        'refEntries': 0,
        'linkInlined': 0,
        'linkRefs': 0,
        'repeatEntriesCollapsed': 0,
        'unknownRefs': 0,
        'cycleRefs': 0,
    }
    seen: set = set()
    stack: set = set()

    def normalize_value(value: Any) -> Any:
        if _is_full_handle_entry(value):
            return normalize_entry(value)
        if _is_ref_handle_entry(value):


            handle = _entry_handle_value(value)
            if handle and handle not in handle_map:
                stats['unknownRefs'] += 1
            stats['refEntries'] += 1
            return {'HandleRefId': handle} if handle else value
        if isinstance(value, dict):
            if _is_link_wrapper(value):
                node_ref = value.get('node')
                if isinstance(node_ref, dict):
                    if _is_full_handle_entry(node_ref):
                        value['node'] = normalize_entry(node_ref)
                    else:
                        target = str(node_ref.get('HandleRefId', '') or node_ref.get('HandleId', '') or '')
                        if target:
                            value['node'] = inline_or_ref(target)
                        else:
                            value['node'] = None
                elif node_ref is not None:
                    value['node'] = None


                for key, child in list(value.items()):
                    if key == 'node':
                        continue
                    value[key] = normalize_value(child)
                return value
            for key, child in list(value.items()):
                value[key] = normalize_value(child)
            return value
        if isinstance(value, list):
            return [normalize_value(child) for child in value]
        return value

    def normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        handle = str(entry.get('HandleId', '') or '')
        if not handle or not isinstance(entry.get('Data'), dict):
            return entry
        if handle in seen:
            stats['repeatEntriesCollapsed'] += 1
            stats['refEntries'] += 1
            return {'HandleRefId': handle}
        if handle in stack:
            stats['cycleRefs'] += 1
            stats['refEntries'] += 1
            return {'HandleRefId': handle}
        seen.add(handle)
        stack.add(handle)
        stats['fullEntries'] += 1
        try:
            entry['Data'] = normalize_value(entry.get('Data'))
        finally:
            stack.discard(handle)
        return entry

    def inline_or_ref(target: str) -> Dict[str, Any]:
        target = str(target or '')
        if not target:
            return {'HandleRefId': target}
        if target in seen:
            stats['linkRefs'] += 1
            return {'HandleRefId': target}
        if target in stack:
            stats['cycleRefs'] += 1
            stats['linkRefs'] += 1
            return {'HandleRefId': target}
        source = handle_map.get(target)
        if source is None:
            stats['unknownRefs'] += 1
            stats['linkRefs'] += 1
            return {'HandleRefId': target}
        stats['linkInlined'] += 1
        return normalize_entry(_json_clone(source))

    normalized = normalize_entry(root_entry)
    return {'root': normalized, 'stats': stats}


def _feature_entry(feature: Any) -> Dict[str, Any]:
    name = str(_get(feature, 'name', '') or 'None')
    class_name = str(_get(feature, 'class_name', '') or name or 'None')
    return {
        '$type': 'animAnimFeatureEntry',
        'className': _cname(class_name or 'None'),
        'debugEnabled': int(bool(_get(feature, 'debug_enabled', False))),
        'forceAllocate': int(bool(_get(feature, 'force_allocate', False))),
        'name': _cname(name or 'None'),
    }


def encode_anim_features(tree: bpy.types.NodeTree) -> List[Dict[str, Any]]:
    root = _root_tree(tree) or tree
    features = list(getattr(root, 'features', []) or [])
    if not features:
        return []
    return [_feature_entry(feature) for feature in features]


def _require_source_metadata(root: bpy.types.NodeTree, key: str) -> Any:
    """Return required import metadata or fail before export."""
    try:
        if key in root:
            return root[key]
    except Exception:
        pass
    raise ValueError(f"missing required source metadata: {key}; reimport the animgraph")


def _source_root_output_spec(root: bpy.types.NodeTree) -> Dict[str, Any]:
    _require_source_metadata(root, 'red_root_output_json')
    spec = _json_idprop(root, 'red_root_output_json', None)
    if not isinstance(spec, dict):
        raise ValueError('invalid required source metadata: red_root_output_json')
    return spec


def _root_output_link(root: bpy.types.NodeTree, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Encode Root.outputNode from stored source metadata."""
    spec = _source_root_output_spec(root)
    link_type = str(spec.get('link_type') or 'animPoseLink')
    if not spec.get('present'):


        return {'$type': link_type, 'node': None}

    handle = str(spec.get('handle') or '')
    wrapper = {'$type': link_type}
    wrapper['node'] = {'HandleRefId': handle} if handle else None
    return wrapper


def _source_ordered_root_entries(root: bpy.types.NodeTree, entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return root.Data.nodes in imported membership order."""
    by_handle: Dict[str, Dict[str, Any]] = {}
    encoded_order: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        handle = str(entry.get('HandleId', '') or '')
        if not handle:
            continue
        by_handle[handle] = entry
        encoded_order.append(handle)

    _require_source_metadata(root, 'red_root_nodes_order_json')
    specs_raw = _json_idprop(root, 'red_root_nodes_order_json', None)
    if not isinstance(specs_raw, list):
        raise ValueError('invalid required source metadata: red_root_nodes_order_json')
    specs = specs_raw
    out: List[Dict[str, Any]] = []
    used: set = set()
    missing: List[str] = []
    malformed = 0

    for spec in specs:
        if isinstance(spec, dict):
            handle = str(spec.get('handle', '') or spec.get('HandleId', '') or spec.get('HandleRefId', '') or '')
            inline = bool(spec.get('inline', False))
        else:
            handle = str(spec or '')
            inline = False
        if not handle:
            malformed += 1
            continue
        if handle in used:


            out.append({'HandleRefId': handle})
            continue
        used.add(handle)
        source = by_handle.get(handle)
        if inline and source is not None:
            out.append(_json_clone(source))
        else:
            if source is None:
                missing.append(handle)
            out.append({'HandleRefId': handle})

    source_known_handles: set = set()
    if specs:
        for spec in specs:
            if isinstance(spec, dict):
                h = str(spec.get('handle', '') or spec.get('HandleId', '') or spec.get('HandleRefId', '') or '')
            else:
                h = str(spec or '')
            if h:
                source_known_handles.add(h)
        refs_raw = _json_idprop(root, 'red_nodes_to_init_refs_json', [])
        if isinstance(refs_raw, list):
            source_known_handles.update(str(value) for value in refs_raw if value)
        source_known_handles.add(_root_handle(root))

    appended: List[str] = []
    for handle in encoded_order:
        if handle in used:
            continue


        if specs and handle in source_known_handles:
            continue
        appended.append(handle)
        used.add(handle)
        out.append(_json_clone(by_handle[handle]))

    meta = {
        'sourceOrderEntries': len(specs),
        'emittedEntries': len(out),
        'fullEntries': sum(1 for item in out if isinstance(item, dict) and item.get('HandleId')),
        'refEntries': sum(1 for item in out if isinstance(item, dict) and item.get('HandleRefId')),
        'missingSourceHandles': missing,
        'appendedNewHandles': appended,
        'malformedSourceOrderSpecs': malformed,
        'usedSourceOrder': bool(specs),
    }
    return out, meta


def _default_root_chunk_scalars(entries: List[Dict[str, Any]], root: bpy.types.NodeTree) -> Dict[str, Any]:
    has_mixer_slot = any(
        isinstance(entry.get('Data'), dict) and entry['Data'].get('$type') == f'{ANIM_NODE_PREFIX}MixerSlot'
        for entry in entries
    )
    data = {
        '$type': 'animAnimGraph',
        'additionalAnimDatabases': [],
        'animFeatures': [],
        'cookingPlatform': 'PLATFORM_None',
        'hackAlwaysSample': 0,
        'hasMixerSlot': int(has_mixer_slot),
        'isPaused': 0,
        'jsonFilesDirectory': '',
        'nodesToInit': [],
        'oneFrameToggle': 0,
        'staticCommandsRig': {'DepotPath': _schema_resource_path(), 'Flags': 'Default'},
        'timeDeltaMultiplier': 1,
        'useAnimCommands': 0,
        'useAnimCommandsForCrowd': 0,
        'useAnimStaticCommands': 0,
        'useLunaticMode': 0,
    }
    _require_source_metadata(root, 'red_rootchunk_scalars_json')
    scalars = _json_idprop(root, 'red_rootchunk_scalars_json', None)
    if not isinstance(scalars, dict):
        raise ValueError('invalid required source metadata: red_rootchunk_scalars_json')
    for key, value in scalars.items():
        if key == '$type' or key == 'nodesToInit' or key == 'rootNode' or key == 'variables':
            continue
        data[key] = value
    data['$type'] = 'animAnimGraph'
    return data


def _root_handle(root: bpy.types.NodeTree) -> str:
    handle = str(_idprop_get(root, 'red_root_handle', '') or '')
    if not handle:
        handle = str(_idprop_get(root, 'red_nodes_to_init_root_handle', '') or '')
    return handle or '0'


def encode_root_node(root: bpy.types.NodeTree, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    root_handle = _root_handle(root)
    _require_source_metadata(root, 'red_root_data_fields_json')
    root_fields = _json_idprop(root, 'red_root_data_fields_json', None)
    if not isinstance(root_fields, dict):
        raise ValueError('invalid required source metadata: red_root_data_fields_json')
    root_data = dict(root_fields)
    root_data['$type'] = f'{ANIM_NODE_PREFIX}Root'
    ordered_entries, membership_meta = _source_ordered_root_entries(root, entries)
    root_data['nodes'] = ordered_entries
    root_data['outputNode'] = _root_output_link(root, entries)
    try:
        root['red_last_root_membership_export_summary'] = json.dumps(membership_meta, separators=(',', ':'))
    except Exception:
        pass
    return {'HandleId': root_handle, 'Data': root_data}


def _nodes_to_init_ref_handles(root: bpy.types.NodeTree, root_handle: str, entries: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
    """Return compact nodesToInit HandleRefId ordering."""
    local_handles = {str(entry.get('HandleId', '') or '') for entry in entries if isinstance(entry, dict)}
    _require_source_metadata(root, 'red_nodes_to_init_refs_json')
    refs_raw = _json_idprop(root, 'red_nodes_to_init_refs_json', None)
    if not isinstance(refs_raw, list):
        raise ValueError('invalid required source metadata: red_nodes_to_init_refs_json')
    refs = [str(value) for value in refs_raw]

    seen = set()
    result: List[str] = []
    duplicates = 0
    root_duplicates = 0
    for ref in refs:
        if not ref:
            continue
        if ref == str(root_handle):
            root_duplicates += 1
            continue
        if ref in seen:
            duplicates += 1
            continue
        seen.add(ref)
        result.append(ref)

    known_handles = set(local_handles)


    meta = {
        'sourceCount': int(_idprop_get(root, 'red_nodes_to_init_count', 0) or 0),
        'refCount': len(result),
        'duplicateRefs': duplicates,
        'rootRefDuplicates': root_duplicates,
        'inlineAfterRoot': int(_idprop_get(root, 'red_nodes_to_init_inline_after_root', 0) or 0),
        'refsNotInRootTree': len([ref for ref in result if ref not in known_handles]),
    }
    return result, meta


def encode_nodes_to_init(root: bpy.types.NodeTree, root_entry: Dict[str, Any], entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    root_handle = str(root_entry.get('HandleId', '') or _root_handle(root))
    ref_handles, meta = _nodes_to_init_ref_handles(root, root_handle, entries)
    nodes_to_init: List[Dict[str, Any]] = [root_entry]
    nodes_to_init.extend({'HandleRefId': ref} for ref in ref_handles)
    meta['fullRootEntries'] = 1
    meta['totalEntries'] = len(nodes_to_init)
    return nodes_to_init, meta


def encode_rootchunk_payload(tree: bpy.types.NodeTree) -> Dict[str, Any]:
    """Encode the public root node tree as a WolvenKit RootChunk."""
    root = _root_tree(tree) or tree
    if root is None or getattr(root, 'bl_idname', '') != ANIMGRAPH_TREE_ID:
        raise ValueError('active editor tree is not a REDengine animGraph tree')

    entries = _encode_tree_runtime_entries(root, embed_containers=True, _stack=set())
    root_entry = encode_root_node(root, entries)
    ref_style = normalize_inline_first_references(root_entry, entries)
    root_entry = ref_style.get('root') or root_entry
    ref_style_meta = ref_style.get('stats') if isinstance(ref_style, dict) else {}
    nodes_to_init, init_meta = encode_nodes_to_init(root, root_entry, entries)
    init_meta['referenceStyle'] = ref_style_meta
    try:
        root['red_last_nodes_to_init_export_summary'] = json.dumps(init_meta, separators=(',', ':'))
        root['red_last_reference_style_export_summary'] = json.dumps(ref_style_meta, separators=(',', ':'))
    except Exception:
        pass

    root_chunk = _default_root_chunk_scalars(entries, root)
    root_chunk['animFeatures'] = encode_anim_features(root)
    root_chunk['nodesToInit'] = nodes_to_init
    root_chunk['rootNode'] = {'HandleRefId': str(root_entry.get('HandleId', '') or _root_handle(root))}
    root_chunk['variables'] = encode_root_variables(root)
    return root_chunk


def encode_wolvenkit_json(tree: bpy.types.NodeTree) -> Dict[str, Any]:
    root = _root_tree(tree) or tree
    root_chunk = encode_rootchunk_payload(root)
    archive_name = str(getattr(root, 'name', '') or 'animgraph')
    if not archive_name.endswith('.animgraph') and not archive_name.endswith('.animgraph.json'):
        archive_name = f'{archive_name}.animgraph'

    source_header = _json_loads(_idprop_get(root, 'red_source_header_json', ''), {})
    header = dict(source_header) if isinstance(source_header, dict) else {}
    header.setdefault('WolvenKitVersion', '8.18.2')
    header.setdefault('WKitJsonVersion', '0.0.9')
    header.setdefault('GameVersion', 2310)
    header['ExportedDateTime'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    header['DataType'] = 'CR2W'
    header.setdefault('ArchiveFileName', archive_name)

    source_data = _json_loads(_idprop_get(root, 'red_source_data_meta_json', ''), {})
    data = dict(source_data) if isinstance(source_data, dict) else {}
    data.setdefault('Version', 195)
    data.setdefault('BuildVersion', 0)
    data.setdefault('EmbeddedFiles', [])
    data['RootChunk'] = root_chunk
    return {'Header': header, 'Data': data}


def encode_rootchunk_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    root_chunk = (((payload or {}).get('Data') or {}).get('RootChunk') or {}) if isinstance(payload, dict) else {}
    nodes_to_init = root_chunk.get('nodesToInit') if isinstance(root_chunk, dict) else []
    nodes_to_init = nodes_to_init if isinstance(nodes_to_init, list) else []
    root_ref = root_chunk.get('rootNode') if isinstance(root_chunk, dict) else {}
    root_handle = ''
    if isinstance(root_ref, dict):
        root_handle = str(root_ref.get('HandleRefId', '') or root_ref.get('HandleId', '') or '')
    root_entry = nodes_to_init[0] if nodes_to_init and isinstance(nodes_to_init[0], dict) else {}
    root_data = root_entry.get('Data') if isinstance(root_entry, dict) and isinstance(root_entry.get('Data'), dict) else {}
    nodes = root_data.get('nodes') if isinstance(root_data, dict) else []
    variables = root_chunk.get('variables') if isinstance(root_chunk, dict) else {}
    variable_data = variables.get('Data') if isinstance(variables, dict) else {}
    variable_count = 0
    if isinstance(variable_data, dict):
        for key in ('boolVariables', 'floatVariables', 'intVariables', 'quaternionVariables', 'transformVariables', 'vectorVariables'):
            values = variable_data.get(key)
            if isinstance(values, list):
                variable_count += len(values)
    root_output = (root_data.get('outputNode') or {}) if isinstance(root_data, dict) else {}
    output_ref = ''
    if isinstance(root_output, dict) and isinstance(root_output.get('node'), dict):
        output_ref = str(root_output['node'].get('HandleRefId', '') or root_output['node'].get('HandleId', '') or '')
    root_node_full = sum(1 for item in nodes if isinstance(item, dict) and item.get('HandleId')) if isinstance(nodes, list) else 0
    root_node_refs = sum(1 for item in nodes if isinstance(item, dict) and item.get('HandleRefId')) if isinstance(nodes, list) else 0
    return {
        'rootHandle': root_handle or str(root_entry.get('HandleId', '') or '') if isinstance(root_entry, dict) else root_handle,
        'rootOutputRef': output_ref,
        'rootNodes': len(nodes) if isinstance(nodes, list) else 0,
        'rootNodeFullEntries': root_node_full,
        'rootNodeRefEntries': root_node_refs,
        'variables': variable_count,
        'animFeatures': len(root_chunk.get('animFeatures') or []) if isinstance(root_chunk, dict) else 0,
        'nodesToInit': len(nodes_to_init),
        'nodesToInitRefs': max(0, len(nodes_to_init) - 1),
    }


def _json_path_get(root: Any, path: str) -> Tuple[bool, Any]:
    def resolve(use_wrappers: bool) -> Tuple[bool, Any]:
        obj = root
        parts = _path_parts(path)
        for pos, (name, idx) in enumerate(parts):
            if idx is None:
                if not isinstance(obj, dict) or name not in obj:
                    return False, None
                obj = obj[name]
            else:
                if not isinstance(obj, dict):
                    return False, None
                arr = obj.get(name)
                if not isinstance(arr, list) or idx < 0 or idx >= len(arr):
                    return False, None
                obj = arr[idx]
            if use_wrappers and pos < len(parts) - 1 and isinstance(obj, dict) and isinstance(obj.get('Data'), dict):
                obj = obj.get('Data')
        return True, obj

    ok, value = resolve(False)
    if ok:
        return ok, value
    return resolve(True)


def _json_equal(a: Any, b: Any) -> bool:
    try:
        return json.dumps(a, ensure_ascii=False, sort_keys=True, separators=(',', ':')) == json.dumps(b, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    except Exception:
        return a == b


def _related_trees_for_export(root: Any) -> List[Any]:
    if variable_bindings is not None:
        try:
            return list(variable_bindings.related_trees(root) or [root])
        except Exception:
            pass
    return [root]


def _collect_payload_handle_graph(payload: Dict[str, Any]) -> Dict[str, Any]:
    defined: Dict[str, Dict[str, Any]] = {}
    duplicate_counts: Dict[str, int] = {}
    refs: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            hid = str(value.get('HandleId', '') or '')
            if hid and isinstance(value.get('Data'), dict):
                if hid in defined:
                    duplicate_counts[hid] = duplicate_counts.get(hid, 1) + 1
                else:
                    defined[hid] = value
            ref = str(value.get('HandleRefId', '') or '')
            if ref:
                refs.append(ref)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    missing = sorted({ref for ref in refs if ref not in defined}, key=lambda h: (0 if str(h).isdigit() else 1, int(h) if str(h).isdigit() else 0, str(h)))
    return {
        'defined': defined,
        'refs': refs,
        'missing': missing,
        'duplicates': duplicate_counts,
    }


def _variable_count_from_payload(payload: Dict[str, Any]) -> int:
    root_chunk = (((payload or {}).get('Data') or {}).get('RootChunk') or {}) if isinstance(payload, dict) else {}
    variables = root_chunk.get('variables') if isinstance(root_chunk, dict) else {}
    data = variables.get('Data') if isinstance(variables, dict) else {}
    total = 0
    if isinstance(data, dict):
        for key in ('boolVariables', 'floatVariables', 'intVariables', 'quaternionVariables', 'transformVariables', 'vectorVariables'):
            arr = data.get(key)
            if isinstance(arr, list):
                total += len(arr)
    return total


def export_reversal_audit_for_payload(tree: bpy.types.NodeTree, payload: Dict[str, Any]) -> Dict[str, Any]:
    root = _root_tree(tree) or tree
    graph = _collect_payload_handle_graph(payload)
    defined = graph['defined']
    counters: Dict[str, int] = {
        'runtimeNodes': 0,
        'nodesMissingHandle': 0,
        'nodesMissingType': 0,
        'nodesWrongTypeFamily': 0,
        'nodesMissingInExport': 0,
        'nodesMissingData': 0,
        'nodeTypeMismatches': 0,
        'propertiesTotal': 0,
        'propertiesEncodable': 0,
        'propertiesRoundtripped': 0,
        'propertiesMissingPath': 0,
        'propertiesEncodeFailed': 0,
        'propertiesMissingInExport': 0,
        'propertiesValueMismatched': 0,
        'socketsTotal': 0,
        'socketsRoundtripped': 0,
        'preservedFieldsTotal': 0,
        'preservedFieldsRoundtripped': 0,
        'preservedFieldsMissingInExport': 0,
        'socketsMissingBinding': 0,
        'socketsMissingInExport': 0,
        'socketsBadWrapper': 0,
        'socketsLinkTypeMismatched': 0,
        'socketsSourceMismatched': 0,
        'socketsUnexpectedSource': 0,
        'definedHandleIds': len(defined),
        'referencedHandleRefs': len(set(graph['refs'])),
        'missingHandleRefs': len(graph['missing']),
        'duplicateHandleIds': len(graph['duplicates']),
        'nodesToInit': 0,
        'rootNodes': 0,
        'variables': _variable_count_from_payload(payload),
        'blockers': 0,
        'warnings': 0,
        'ready': 0,
    }
    blocking: List[str] = []
    warnings: List[str] = []
    details = {'nodes': [], 'properties': [], 'preservedFields': [], 'sockets': [], 'references': [], 'variables': []}

    def block(text: str, bucket: str) -> None:
        blocking.append(text)
        if bucket in details:
            details[bucket].append(text)

    root_chunk = (((payload or {}).get('Data') or {}).get('RootChunk') or {}) if isinstance(payload, dict) else {}
    nodes_to_init = root_chunk.get('nodesToInit') if isinstance(root_chunk, dict) else []
    counters['nodesToInit'] = len(nodes_to_init) if isinstance(nodes_to_init, list) else 0
    root_entry = nodes_to_init[0] if isinstance(nodes_to_init, list) and nodes_to_init else {}
    root_data = root_entry.get('Data') if isinstance(root_entry, dict) else {}
    root_nodes = root_data.get('nodes') if isinstance(root_data, dict) else []
    counters['rootNodes'] = len(root_nodes) if isinstance(root_nodes, list) else 0

    for handle in graph['missing']:
        block(f'missing HandleRefId target: {handle}', 'references')
    for handle, count in sorted(graph['duplicates'].items()):
        block(f'duplicate HandleId definition: {handle} count={count}', 'references')

    for tree_obj in _related_trees_for_export(root):
        for node in getattr(tree_obj, 'nodes', []) or []:
            if not _runtime_node(node):
                continue
            counters['runtimeNodes'] += 1
            handle = str(_get(node, 'red_handle_id', '') or '')
            red_type = str(_get(node, 'red_type', '') or '')
            if not handle:
                counters['nodesMissingHandle'] += 1
                block(f'runtime node missing HandleId: {getattr(node, "name", "<node>")}', 'nodes')
                continue
            if not red_type:
                counters['nodesMissingType'] += 1
                block(f'runtime node missing red_type: {handle}', 'nodes')
            elif not red_type.startswith(ANIM_NODE_PREFIX):
                counters['nodesWrongTypeFamily'] += 1
                block(f'runtime node type is not animAnimNode_*: {handle} {red_type}', 'nodes')
            entry = defined.get(handle)
            if entry is None:
                counters['nodesMissingInExport'] += 1
                block(f'runtime node missing from export: {handle} {red_type}', 'nodes')
                data = None
            else:
                data = entry.get('Data')
                if not isinstance(data, dict):
                    counters['nodesMissingData'] += 1
                    block(f'runtime node missing Data in export: {handle}', 'nodes')
                    data = None
                elif red_type and data.get('$type') != red_type:
                    counters['nodeTypeMismatches'] += 1
                    block(f'runtime node type mismatch: {handle} expected={red_type} got={data.get("$type")}', 'nodes')

            for item in getattr(node, 'red_properties', []) or []:
                counters['propertiesTotal'] += 1
                path = str(getattr(item, 'json_path', '') or getattr(item, 'key', '') or '')
                if not path:
                    counters['propertiesMissingPath'] += 1
                    block(f'encoded property lacks JSON path: {handle}.{getattr(item, "key", "<property>")}', 'properties')
                    continue
                try:
                    expected = encode_node_property(item)
                    counters['propertiesEncodable'] += 1
                except Exception as exc:
                    counters['propertiesEncodeFailed'] += 1
                    block(f'encoded property failed: {handle}.{path} -> {exc}', 'properties')
                    continue
                ok, actual = _json_path_get(data, path) if isinstance(data, dict) else (False, None)
                if not ok:
                    counters['propertiesMissingInExport'] += 1
                    block(f'encoded property path missing from export: {handle}.{path}', 'properties')
                elif not _json_equal(expected, actual):
                    counters['propertiesValueMismatched'] += 1
                    block(f'encoded property value mismatch: {handle}.{path}', 'properties')
                else:
                    counters['propertiesRoundtripped'] += 1

            preserved_fields = _json_idprop(node, 'red_preserved_export_fields_json', {})
            if isinstance(preserved_fields, dict):
                for key in preserved_fields.keys():
                    counters['preservedFieldsTotal'] += 1
                    if not isinstance(data, dict) or str(key) not in data:
                        counters['preservedFieldsMissingInExport'] += 1
                        block(f'preserved owned payload field missing from export: {handle}.{key}', 'preservedFields')
                    else:
                        counters['preservedFieldsRoundtripped'] += 1

            for sock in _iter_exportable_input_sockets(node):
                counters['socketsTotal'] += 1
                path = str(_get(sock, 'red_json_path', '') or '')
                link_type = str(_get(sock, 'red_link_type', '') or '')
                source = _link_source_handle(sock)
                if not path or not link_type:
                    counters['socketsMissingBinding'] += 1
                    block(f'socket missing export binding: {handle}.{getattr(sock, "name", "<socket>")}', 'sockets')
                    continue
                ok, wrapper = _json_path_get(data, path) if isinstance(data, dict) else (False, None)
                if not ok:
                    counters['socketsMissingInExport'] += 1
                    block(f'socket JSON path missing from export: {handle}.{getattr(sock, "name", "<socket>")} path={path}', 'sockets')
                    continue
                if not isinstance(wrapper, dict):
                    counters['socketsBadWrapper'] += 1
                    block(f'socket JSON wrapper is not an object: {handle}.{getattr(sock, "name", "<socket>")} path={path}', 'sockets')
                    continue
                if str(wrapper.get('$type', '') or '') != link_type:
                    counters['socketsLinkTypeMismatched'] += 1
                    block(f'socket link type mismatch: {handle}.{getattr(sock, "name", "<socket>")} expected={link_type} got={wrapper.get("$type")}', 'sockets')
                    continue
                node_ref = wrapper.get('node')
                actual_source = ''
                if isinstance(node_ref, dict):
                    actual_source = str(node_ref.get('HandleRefId', '') or node_ref.get('HandleId', '') or '')
                if source and actual_source != source:
                    counters['socketsSourceMismatched'] += 1
                    block(f'socket source mismatch: {handle}.{getattr(sock, "name", "<socket>")} expected={source} got={actual_source or "null"}', 'sockets')
                elif not source and actual_source:
                    counters['socketsUnexpectedSource'] += 1
                    block(f'socket unexpectedly has source: {handle}.{getattr(sock, "name", "<socket>")} got={actual_source}', 'sockets')
                else:
                    counters['socketsRoundtripped'] += 1

    counters['blockers'] = len(blocking)
    counters['warnings'] = len(warnings)
    counters['ready'] = int(not blocking)
    summary = (
        f"ready={not blocking} "
        f"nodes={counters['runtimeNodes'] - counters['nodesMissingInExport']}/{counters['runtimeNodes']} "
        f"properties={counters['propertiesRoundtripped']}/{counters['propertiesEncodable']} "
        f"sockets={counters['socketsRoundtripped']}/{counters['socketsTotal']} "
        f"preserved={counters['preservedFieldsRoundtripped']}/{counters['preservedFieldsTotal']} "
        f"refsMissing={counters['missingHandleRefs']} duplicates={counters['duplicateHandleIds']} "
        f"blockers={counters['blockers']} warnings={counters['warnings']}"
    )
    return {
        'version': 1,
        'scope': 'export-reversal-projection-coverage',
        'ready': bool(counters['ready']),
        'summary': summary,
        'counters': counters,
        'blocking': blocking,
        'warnings': warnings,
        'details': details,
    }


def _write_text_block(name: str, value: Any, *, copy_to_clipboard: bool = True) -> bpy.types.Text:
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
    else:
        text.clear()
    rendered = _json_dumps(value)
    text.write(rendered)
    if copy_to_clipboard:
        try:
            bpy.context.window_manager.clipboard = rendered
        except Exception:
            pass
    return text


class REDENGINE_OT_encode_rootchunk_json(bpy.types.Operator):
    bl_idname = 'redengine.encode_rootchunk_json'
    bl_label = 'Encode RootChunk JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        try:
            tree = context.space_data.node_tree
            payload = encode_wolvenkit_json(tree)
            text = _write_text_block(TEXT_ROOTCHUNK_JSON, payload, copy_to_clipboard=False)
            summary = encode_rootchunk_summary(payload)
            self.report(
                {'INFO'},
                f"Encoded RootChunk JSON to Text: {text.name} "
                f"root={summary.get('rootHandle', '') or '<none>'} "
                f"nodes={summary.get('rootNodes', 0)} "
                f"full={summary.get('rootNodeFullEntries', 0)} "
                f"refs={summary.get('rootNodeRefEntries', 0)} "
                f"root-output={summary.get('rootOutputRef', '') or 'null'} "
                f"variables={summary.get('variables', 0)} "
                f"nodesToInit={summary.get('nodesToInit', 0)} "
                f"initRefs={summary.get('nodesToInitRefs', 0)}"
            )
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode RootChunk JSON: {exc}")
            return {'CANCELLED'}


class REDENGINE_OT_encode_selected_node(bpy.types.Operator):
    bl_idname = 'redengine.encode_selected_node'
    bl_label = 'Encode Selected Node JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        node = getattr(context, 'active_node', None)
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
            and node is not None
            and _runtime_node(node)
        )

    def execute(self, context):
        try:
            entry = encode_selected_node(context)
            text = _write_text_block(TEXT_SELECTED_NODE, entry)
            self.report({'INFO'}, f"Encoded selected node to Text: {text.name} (also copied to clipboard)")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode selected node: {exc}")
            return {'CANCELLED'}


class REDENGINE_OT_encode_root_variables(bpy.types.Operator):
    bl_idname = 'redengine.encode_root_variables'
    bl_label = 'Encode Root Variables JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        try:
            wrapper = encode_root_variables(context.space_data.node_tree)
            text = _write_text_block(TEXT_ROOT_VARIABLES, wrapper)
            self.report({'INFO'}, f"Encoded root variables to Text: {text.name} (also copied to clipboard)")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode root variables: {exc}")
            return {'CANCELLED'}


class REDENGINE_OT_encode_active_tree(bpy.types.Operator):
    bl_idname = 'redengine.encode_active_tree'
    bl_label = 'Encode Active Tree JSON'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.node_tree is not None
            and getattr(space.node_tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        try:
            payload = encode_active_tree(context.space_data.node_tree)


            text = _write_text_block(TEXT_ACTIVE_TREE, payload, copy_to_clipboard=False)
            summary = payload.get('summary', {}) if isinstance(payload, dict) else {}
            self.report(
                {'INFO'},
                f"Encoded active tree to Text: {text.name} "
                f"nodes={summary.get('encodedNodes', 0)}/{summary.get('runtimeNodes', 0)} "
                f"editor-skipped={summary.get('editorSkipped', 0)} "
                f"blockers={summary.get('blockers', 0)} warnings={summary.get('warnings', 0)}"
            )
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to encode active tree: {exc}")
            return {'CANCELLED'}
