from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import bpy

from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID, ANIM_NODE_PREFIX
from .property_codec import encode_node_property
from ...animation.animgraph.model.value_codec import cname_value, number, int_number

VAR_NODE_BY_TYPE = {
    'Bool': 'BoolVariable',
    'Int': 'IntVariable',
    'Float': 'FloatVariable',
    'Vector': 'VectorVariable',
    'Quaternion': 'QuaternionVariable',
    'Transform': 'TransformVariable',
}

VAR_KIND_BY_TYPE = {
    'Bool': 'BOOL',
    'Int': 'INT',
    'Float': 'FLOAT',
    'Vector': 'VECTOR4',
    'Quaternion': 'QUATERNION',
    'Transform': 'QSTRANSFORM',
}

VAR_ARRAY_BY_TYPE = {
    'Bool': 'boolVariables',
    'Int': 'intVariables',
    'Float': 'floatVariables',
    'Vector': 'vectorVariables',
    'Quaternion': 'quaternionVariables',
    'Transform': 'transformVariables',
}


def _vector(value: Any, keys: Tuple[str, ...], defaults: Tuple[float, ...]) -> Tuple[float, float, float, float]:
    if not isinstance(value, dict):
        vals = list(defaults)
    else:
        vals = [number(value.get(k), defaults[i]) for i, k in enumerate(keys)]
    while len(vals) < 4:
        vals.append(0.0 if len(vals) < 3 else 1.0)
    return tuple(vals[:4])  # type: ignore[return-value]


def _format_vec(vals: Iterable[float], labels: Tuple[str, ...]) -> str:
    items = list(vals)
    return ', '.join(f'{label}={items[i]:g}' for i, label in enumerate(labels) if i < len(items))


def variable_value_text(var: Any, *, current: bool = True) -> str:
    vt = getattr(var, 'var_type', '')
    if vt == 'Bool':
        return 'true' if (var.current_bool if current else var.default_bool) else 'false'
    if vt == 'Int':
        return str(int(var.current_int if current else var.default_int))
    if vt == 'Float':
        return f'{float(var.current_float if current else var.default_float):g}'
    if vt == 'Vector':
        vals = var.current_vector if current else var.default_vector
        return _format_vec(vals, ('X', 'Y', 'Z', 'W'))
    if vt == 'Quaternion':
        vals = var.current_vector if current else var.default_vector
        return _format_vec(vals, ('i', 'j', 'k', 'r'))
    if vt == 'Transform':
        return var.current_value if current else var.default_value
    return var.current_value if current else var.default_value


def _has_float_range_json(inner: dict) -> bool:
    return isinstance(inner, dict) and ('min' in inner or 'max' in inner)


def clamp_float_variable(var: Any) -> None:
    if str(getattr(var, 'var_type', '')) != 'Float' or not bool(getattr(var, 'has_float_range', False)):
        return
    lo = float(getattr(var, 'min_float', 0.0))
    hi = float(getattr(var, 'max_float', 0.0))
    if hi < lo:
        lo, hi = hi, lo
        var.min_float = lo
        var.max_float = hi
    var.current_float = max(lo, min(hi, float(getattr(var, 'current_float', 0.0))))
    var.default_float = max(lo, min(hi, float(getattr(var, 'default_float', 0.0))))


def variable_range_text(var: Any) -> str:
    if str(getattr(var, 'var_type', '')) != 'Float' or not bool(getattr(var, 'has_float_range', False)):
        return ''
    return f'{float(var.min_float):g} .. {float(var.max_float):g}'

def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return '' if value is None else str(value)


def set_variable_from_json(slot: Any, var_type: str, inner: dict, entry: dict, array_name: str = '') -> None:
    """Populate a graph variable slot from REDengine JSON."""
    slot.var_type = var_type
    slot.value_kind = VAR_KIND_BY_TYPE.get(var_type, 'STRING')
    slot.source_array = array_name or VAR_ARRAY_BY_TYPE.get(var_type, '')
    slot.handle_id = str(entry.get('HandleId', ''))
    slot.name = cname_value(inner.get('name')) or '<unnamed>'
    slot.bound_name = slot.name
    slot.enable_debug = bool(inner.get('enableDebug'))
    slot.raw_json = _json_text(entry)
    slot.default_json = _json_text(inner.get('default'))
    slot.current_json = _json_text(inner.get('value'))

    default = inner.get('default')
    value = inner.get('value')

    if var_type == 'Bool':
        slot.default_bool = bool(default)
        slot.current_bool = bool(value)
    elif var_type == 'Int':
        slot.default_int = int_number(default)
        slot.current_int = int_number(value)
    elif var_type == 'Float':
        slot.default_float = number(default)
        slot.current_float = number(value)
        slot.has_float_range = _has_float_range_json(inner)
        slot.min_float = number(inner.get('min'))
        slot.max_float = number(inner.get('max'))
        clamp_float_variable(slot)
    elif var_type == 'Vector':
        for i, v in enumerate(_vector(default, ('X', 'Y', 'Z', 'W'), (0, 0, 0, 0))):
            slot.default_vector[i] = v
        for i, v in enumerate(_vector(value, ('X', 'Y', 'Z', 'W'), (0, 0, 0, 0))):
            slot.current_vector[i] = v
    elif var_type == 'Quaternion':
        for i, v in enumerate(_vector(default, ('i', 'j', 'k', 'r'), (0, 0, 0, 1))):
            slot.default_vector[i] = v
        for i, v in enumerate(_vector(value, ('i', 'j', 'k', 'r'), (0, 0, 0, 1))):
            slot.current_vector[i] = v
    elif var_type == 'Transform':


        pass

    slot.default_value = variable_value_text(slot, current=False)
    slot.current_value = variable_value_text(slot, current=True)


def sync_variable_summary(slot: Any) -> None:
    """Refresh cached value summaries after typed value edits."""
    try:
        clamp_float_variable(slot)
        slot.default_value = variable_value_text(slot, current=False)
        slot.current_value = variable_value_text(slot, current=True)
        if str(getattr(slot, 'var_type', '')) == 'Float':
            slot.default_json = _json_text(float(slot.default_float))
            slot.current_json = _json_text(float(slot.current_float))
    except Exception:
        pass


def root_tree_for(tree: Optional[bpy.types.NodeTree]) -> Optional[bpy.types.NodeTree]:
    if tree is None:
        return None
    if getattr(tree, 'bl_idname', '') != ANIMGRAPH_TREE_ID:
        return None
    parent_name = ''
    try:
        parent_name = str(tree.get('red_parent_graph', ''))
    except Exception:
        parent_name = ''
    if parent_name:
        parent = bpy.data.node_groups.get(parent_name)
        if parent is not None and getattr(parent, 'bl_idname', '') == ANIMGRAPH_TREE_ID:
            return parent
    return tree


def related_trees(root_tree: bpy.types.NodeTree) -> List[bpy.types.NodeTree]:
    root = root_tree_for(root_tree) or root_tree
    out: List[bpy.types.NodeTree] = []
    for tree in bpy.data.node_groups:
        if getattr(tree, 'bl_idname', '') != ANIMGRAPH_TREE_ID:
            continue
        if tree == root:
            out.append(tree)
            continue
        try:
            if str(tree.get('red_parent_graph', '')) == root.name:
                out.append(tree)
        except Exception:
            pass
    return out


def _node_short_type(node: bpy.types.Node) -> str:
    typ = getattr(node, 'red_type', '')
    if typ.startswith(ANIM_NODE_PREFIX):
        return typ[len(ANIM_NODE_PREFIX):]
    return typ


def is_variable_node(node: bpy.types.Node) -> bool:
    return _node_short_type(node) in set(VAR_NODE_BY_TYPE.values())


def variable_type_for_node(node: bpy.types.Node) -> str:
    short = _node_short_type(node)
    for vt, suffix in VAR_NODE_BY_TYPE.items():
        if short == suffix:
            return vt
    return ''


def _prop_by_key(node: bpy.types.Node, key: str):
    props = getattr(node, 'red_properties', None)
    if not props:
        return None
    for item in props:
        if item.key == key:
            return item
    return None


def node_variable_name(node: bpy.types.Node) -> str:
    item = _prop_by_key(node, 'variableName')
    if item is None:
        return ''
    if getattr(item, 'value_kind', '') == 'CNAME':
        return str(getattr(item, 'string_value', ''))
    try:
        value = encode_node_property(item)
        return cname_value(value)
    except Exception:
        return str(getattr(item, 'string_value', ''))


def set_node_variable_name(node: bpy.types.Node, new_name: str) -> None:
    item = _prop_by_key(node, 'variableName')
    if item is None:
        return
    try:
        item.string_value = str(new_name)
        item.raw_json = json.dumps({'$type': 'CName', '$storage': 'string', '$value': str(new_name)}, ensure_ascii=False, sort_keys=True)
    except Exception:
        pass


def _variable_lookup(root_tree: bpy.types.NodeTree) -> Dict[Tuple[str, str], Any]:
    root = root_tree_for(root_tree) or root_tree
    return {(str(v.var_type), str(v.name)): v for v in getattr(root, 'variables', [])}


def _set_node_binding(node: bpy.types.Node, var: Optional[Any], *, requested_name: str = '', var_type: str = '') -> None:
    if var is None:
        node['red_variable_bound'] = False
        node['red_variable_name'] = requested_name
        node['red_variable_type'] = var_type
        node['red_variable_handle'] = ''
        node['red_variable_current_value'] = '<unbound>' if requested_name else ''
        node['red_variable_default_value'] = ''
        node['red_variable_range'] = ''
        short = _node_short_type(node)
        node.label = f'{short}: {requested_name}' if requested_name else short
        return

    node['red_variable_bound'] = True
    node['red_variable_name'] = str(var.name)
    node['red_variable_type'] = str(var.var_type)
    node['red_variable_handle'] = str(var.handle_id)
    node['red_variable_current_value'] = variable_value_text(var, current=True)
    node['red_variable_default_value'] = variable_value_text(var, current=False)
    node['red_variable_range'] = variable_range_text(var)
    short = _node_short_type(node)
    node.label = f'{short}: {var.name}'


def bind_all_variables(root_tree: bpy.types.NodeTree) -> Dict[str, int]:
    """Resolve variable-reader nodes against root-tree declarations."""
    root = root_tree_for(root_tree) or root_tree
    lookup = _variable_lookup(root)
    consumers: Dict[Tuple[str, str], List[str]] = {key: [] for key in lookup.keys()}
    bound = 0
    unbound = 0

    for tree in related_trees(root):
        for node in tree.nodes:
            if not is_variable_node(node):
                continue
            vt = variable_type_for_node(node)
            name = node_variable_name(node)
            var = lookup.get((vt, name))
            if var is None:
                _set_node_binding(node, None, requested_name=name, var_type=vt)
                unbound += 1
                continue
            _set_node_binding(node, var)
            consumers.setdefault((vt, str(var.name)), []).append(str(getattr(node, 'red_handle_id', '') or node.name))
            bound += 1

    try:
        root.red_variable_sync_suspended = True
    except Exception:
        pass
    try:
        for var in root.variables:
            key = (str(var.var_type), str(var.name))
            handles = [h for h in consumers.get(key, []) if h]
            var.consumer_count = len(handles)
            var.consumer_handles = ', '.join(handles)
            var.bound_name = str(var.name)
            sync_variable_summary(var)
    finally:
        try:
            root.red_variable_sync_suspended = False
        except Exception:
            pass

    try:
        root['red_variable_bound_nodes'] = bound
        root['red_variable_unbound_nodes'] = unbound
    except Exception:
        pass
    return {'bound': bound, 'unbound': unbound}


def propagate_variable_to_nodes(var: Any) -> None:
    """Apply one edited root variable to matching reader nodes."""
    root = root_tree_for(getattr(var, 'id_data', None))
    if root is None:
        return
    if bool(getattr(root, 'red_variable_sync_suspended', False)):
        return

    try:
        root.red_variable_sync_suspended = True
    except Exception:
        pass
    try:
        original_name = str(getattr(var, 'bound_name', '') or '')
        new_name = str(getattr(var, 'name', '') or '')
        vt = str(getattr(var, 'var_type', '') or '')
        sync_variable_summary(var)

        for tree in related_trees(root):
            for node in tree.nodes:
                if not is_variable_node(node):
                    continue
                if variable_type_for_node(node) != vt:
                    continue
                node_name = node_variable_name(node)
                if original_name and node_name == original_name and new_name and new_name != original_name:
                    set_node_variable_name(node, new_name)
                    node_name = new_name
                if node_name == new_name:
                    _set_node_binding(node, var)

        var.bound_name = new_name
    finally:
        try:
            root.red_variable_sync_suspended = False
        except Exception:
            pass


    bind_all_variables(root)


def on_variable_value_updated(var: Any, context=None) -> None:
    propagate_variable_to_nodes(var)
