from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID, ANIM_NODE_PREFIX
from .. import index as graph_index
from ....animation.animgraph.schema import rtti
from .. import variables as variable_bindings
from .. import presenters as node_presenters
from ..property_codec import encode_node_property
from ..access import get_attr, get_idprop
from . import reporting


REPORT_KEY = 'red_roundtrip_audit_report'
SUMMARY_KEY = 'red_roundtrip_audit_summary'
READY_KEY = 'red_roundtrip_audit_ready'

BLOCKER_LIMIT = 200
WARNING_LIMIT = 200


ENCODABLE_KINDS = {
    'BOOL', 'INT', 'UINT', 'FLOAT', 'STRING', 'CNAME',
    'ENUM', 'FLAGS_ENUM',
    'TRANSFORM_INDEX', 'NAMED_TRACK_INDEX', 'VISUAL_TAG_CONDITION',
    'VECTOR2', 'VECTOR3', 'VECTOR4', 'QUATERNION', 'QSTRANSFORM',
    'FLOAT_CLAMP', 'CURVE_FLOAT', 'ARRAY', 'STRUCT', 'HANDLE_STRUCT',
    'NULL', 'RAW_JSON',
}


def _node_name(node: Any) -> str:
    return str(get_attr(node, 'name', '<node>') or '<node>')


def _node_label(node: Any) -> str:
    return str(get_attr(node, 'label', '') or _node_name(node))


def _node_handle(node: Any) -> str:
    return graph_index.node_handle(node)


def _node_type(node: Any) -> str:
    return graph_index.node_type(node)


def _node_is_exportable(node: Any) -> bool:
    return graph_index.node_is_exportable(node)


def _node_is_editor(node: Any) -> bool:
    return graph_index.node_is_pseudo(node)


def _socket_exportable(sock: Any) -> bool:
    return graph_index.socket_exportable(sock)


def _socket_semantics(sock: Any) -> str:
    return graph_index.socket_semantics(sock)


def _socket_path(sock: Any) -> str:
    return graph_index.socket_path(sock)


def _socket_link_type(sock: Any) -> str:
    return graph_index.socket_link_type(sock)


def _socket_source(sock: Any) -> str:
    return graph_index.socket_source(sock)


def _socket_owner(sock: Any) -> str:
    return graph_index.socket_owner(sock)


def _socket_target(sock: Any) -> str:
    return graph_index.socket_target(sock)


def _presenter_known(node_type: str, presenter_id: str) -> bool:
    if node_presenters is None:
        return bool(presenter_id)
    try:
        presenter = node_presenters.presenter_for_type(node_type)
        expected = getattr(presenter, 'id', '') or getattr(presenter, 'presenter_id', '')
        if not presenter_id:
            return False
        return presenter_id == expected or bool(expected)
    except Exception:
        return bool(presenter_id)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _variable_encode_preview(var: Any) -> Tuple[bool, str]:
    """Validate that one graph variable can be encoded as JSON."""
    vt = str(get_attr(var, 'var_type', ''))
    try:
        if vt == 'Bool':
            return True, _safe_json(bool(var.current_bool))
        if vt == 'Int':
            return True, _safe_json(int(var.current_int))
        if vt == 'Float':
            try:
                variable_bindings.clamp_float_variable(var)
            except Exception:
                pass
            return True, _safe_json(float(var.current_float))
        if vt == 'Vector':
            return True, _safe_json({'$type': 'Vector4', 'X': float(var.current_vector[0]), 'Y': float(var.current_vector[1]), 'Z': float(var.current_vector[2]), 'W': float(var.current_vector[3])})
        if vt == 'Quaternion':
            return True, _safe_json({'$type': 'Quaternion', 'i': float(var.current_vector[0]), 'j': float(var.current_vector[1]), 'k': float(var.current_vector[2]), 'r': float(var.current_vector[3])})
        if vt == 'Transform':
            raw = str(get_attr(var, 'current_json', '') or get_attr(var, 'current_value', ''))
            if raw:
                try:
                    json.loads(raw)
                    return True, raw
                except Exception:


                    return True, raw
            return True, ''

        raw = str(get_attr(var, 'current_json', '') or get_attr(var, 'current_value', ''))
        if raw:
            return True, raw
        return False, 'missing variable value'
    except Exception as exc:
        return False, str(exc)


def report_for_tree(tree: Any) -> dict:
    root = reporting.root_tree(tree)
    index = graph_index.build_index(root)
    source_counters = dict(index.get('counters', {}))

    counters: Dict[str, int] = defaultdict(int)
    blockers: List[str] = []
    warnings: List[str] = []
    details: Dict[str, list] = {
        'blocking': blockers,
        'warnings': warnings,
        'unbound_variables': [],
        'raw_properties': [],
        'encode_failures': [],
        'editor_exportable_nodes': [],
        'missing_property_paths': [],
        'invalid_enums': [],
    }

    nodes_by_handle = index.get('nodes_by_handle', {}) or {}

    for tree_obj in graph_index.iter_trees(root):
        counters['trees'] += 1
        for node in getattr(tree_obj, 'nodes', []) or []:
            counters['nodes_total'] += 1
            nname = _node_name(node)
            nlabel = _node_label(node)
            nhandle = _node_handle(node)
            ntype = _node_type(node)
            exportable = _node_is_exportable(node)
            editor = _node_is_editor(node)
            presenter = str(get_attr(node, 'red_presenter', '') or '')

            if editor:
                counters['editor_nodes_skipped'] += 1
            if editor and exportable:
                counters['editor_exportable_nodes'] += 1
                text = f"editor node marked exportable: {nname} ({ntype or '<no type>'})"
                reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                details['editor_exportable_nodes'].append(text)

            if not exportable:
                continue

            counters['runtime_nodes'] += 1
            if not nhandle:
                reporting.append_limited(blockers, f"runtime node lacks HandleId: {nname} ({ntype or '<no type>'})", limit=BLOCKER_LIMIT)
            if not ntype:
                reporting.append_limited(blockers, f"runtime node lacks red_type: {nname}", limit=BLOCKER_LIMIT)
            elif not ntype.startswith(ANIM_NODE_PREFIX):
                reporting.append_limited(blockers, f"exportable node is not animAnimNode_*: {nhandle or nname} {ntype}", limit=BLOCKER_LIMIT)
            elif not rtti.has_class(ntype):
                reporting.append_limited(blockers, f"runtime node has unknown RTTI class: {nhandle or nname} {ntype}", limit=BLOCKER_LIMIT)
            else:
                counters['runtime_nodes_schema_known'] += 1

            if not presenter:
                reporting.append_limited(blockers, f"runtime node lacks presenter id: {nhandle or nname} {ntype or '<no type>'}", limit=BLOCKER_LIMIT)
            elif not _presenter_known(ntype, presenter):
                reporting.append_limited(warnings, f"runtime node has non-standard presenter id {presenter!r}: {nhandle or nname} {ntype}", limit=WARNING_LIMIT)

            for prop in getattr(node, 'red_properties', []) or []:
                counters['properties_total'] += 1
                key = str(get_attr(prop, 'key', '') or '')
                path = str(get_attr(prop, 'json_path', '') or '')
                kind = str(get_attr(prop, 'value_kind', '') or '')
                label = f"{nhandle or nname}.{path or key or '<property>'}"

                if not path:
                    counters['properties_missing_json_path'] += 1
                    text = f"property lacks json_path: {label} ({kind or '<no kind>'})"
                    reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                    details['missing_property_paths'].append(text)

                if not kind or kind not in ENCODABLE_KINDS:
                    counters['properties_unknown_kind'] += 1
                    reporting.append_limited(blockers, f"property has unencodable value kind: {label} kind={kind!r}", limit=BLOCKER_LIMIT)
                    continue

                if kind == 'RAW_JSON':
                    counters['raw_properties'] += 1
                    text = f"raw preserved property: {label}"
                    reporting.append_limited(warnings, text, limit=WARNING_LIMIT)
                    details['raw_properties'].append(text)

                if kind in {'ENUM', 'FLAGS_ENUM'}:
                    enum_type = str(get_attr(prop, 'enum_type', '') or get_attr(prop, 'red_type', '') or '')
                    if not enum_type or not rtti.has_enum(enum_type):
                        counters['invalid_enum_properties'] += 1
                        text = f"enum property lacks known enum type: {label} enum={enum_type!r}"
                        reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                        details['invalid_enums'].append(text)

                if encode_node_property is None:
                    counters['properties_not_encoded_no_helper'] += 1
                    continue
                try:
                    encode_node_property(prop)
                    counters['properties_encodable'] += 1
                except Exception as exc:
                    counters['properties_encode_failed'] += 1
                    text = f"property encode failed: {label} ({kind}) -> {exc}"
                    reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                    details['encode_failures'].append(text)


            for sock in getattr(node, 'inputs', []) or []:
                if not _socket_exportable(sock):
                    continue
                counters['exportable_input_sockets'] += 1
                path = _socket_path(sock)
                link_type = _socket_link_type(sock)
                owner = _socket_owner(sock) or nhandle
                if not owner or not path or not link_type:
                    counters['input_sockets_missing_binding'] += 1
                    reporting.append_limited(blockers, f"exportable input socket lacks binding: {nhandle or nname}.{getattr(sock, 'name', '<socket>')} owner={owner!r} path={path!r} link={link_type!r}", limit=BLOCKER_LIMIT)
                else:
                    counters['exportable_input_sockets_bound'] += 1


    duplicates = index.get('duplicate_handles', {}) or {}
    for handle, names in duplicates.items():
        counters['duplicate_handles'] += 1
        reporting.append_limited(blockers, f"duplicate HandleId {handle}: {', '.join(map(str, names[:6]))}", limit=BLOCKER_LIMIT)


    for tree_obj in graph_index.iter_trees(root):
        for link in getattr(tree_obj, 'links', []) or []:
            from_sock = getattr(link, 'from_socket', None)
            to_sock = getattr(link, 'to_socket', None)
            from_node = getattr(link, 'from_node', None)
            to_node = getattr(link, 'to_node', None)
            if from_sock is None or to_sock is None:
                counters['broken_link_objects'] += 1
                reporting.append_limited(blockers, 'broken Blender link object with missing socket', limit=BLOCKER_LIMIT)
                continue
            semantics = _socket_semantics(to_sock) or _socket_semantics(from_sock)
            if semantics != graph_index.DATAFLOW:
                counters['non_dataflow_links_skipped'] += 1

                if _socket_exportable(from_sock) and _socket_exportable(to_sock):
                    counters['non_dataflow_exportable_links'] += 1
                    reporting.append_limited(blockers, f"non-dataflow link is exportable: {getattr(from_node, 'name', '?')} -> {getattr(to_node, 'name', '?')} semantics={semantics!r}", limit=BLOCKER_LIMIT)
                continue

            counters['dataflow_links'] += 1
            source = _socket_source(from_sock) or _socket_owner(from_sock) or _node_handle(from_node)
            target = _socket_target(to_sock) or _socket_owner(to_sock) or _node_handle(to_node)
            path = _socket_path(to_sock)
            link_type = _socket_link_type(to_sock)
            if not source or not target or not path or not link_type:
                counters['dataflow_links_incomplete'] += 1
                reporting.append_limited(blockers, f"dataflow link lacks identity: {getattr(from_node, 'name', '?')} -> {getattr(to_node, 'name', '?')} source={source!r} target={target!r} path={path!r} type={link_type!r}", limit=BLOCKER_LIMIT)
                continue
            if source not in nodes_by_handle:
                counters['dataflow_links_missing_source_node'] += 1
                reporting.append_limited(blockers, f"dataflow link source handle has no exportable node projection: source={source} target={target}.{path}", limit=BLOCKER_LIMIT)
            if target not in nodes_by_handle:
                counters['dataflow_links_missing_target_node'] += 1
                reporting.append_limited(blockers, f"dataflow link target handle has no exportable node projection: source={source} target={target}.{path}", limit=BLOCKER_LIMIT)
            counters['dataflow_links_encodable'] += 1


    root_vars = list(getattr(root, 'variables', []) or [])
    counters['variables_total'] = len(root_vars)
    for var in root_vars:
        ok, msg = _variable_encode_preview(var)
        if ok:
            counters['variables_encodable'] += 1
        else:
            counters['variables_encode_failed'] += 1
            reporting.append_limited(blockers, f"variable encode failed: {getattr(var, 'var_type', '?')} {getattr(var, 'name', '<unnamed>')} -> {msg}", limit=BLOCKER_LIMIT)

    try:
        variable_bindings.bind_all_variables(root)
    except Exception:
        pass
    unbound_nodes: List[str] = []
    for tree_obj in graph_index.iter_trees(root):
        for node in getattr(tree_obj, 'nodes', []) or []:
            try:
                if not variable_bindings.is_variable_node(node):
                    continue
                if not bool(get_idprop(node, 'red_variable_bound', False)):
                    vt = variable_bindings.variable_type_for_node(node)
                    name = variable_bindings.node_variable_name(node)
                    handle = _node_handle(node)
                    text = f"{handle or _node_name(node)} {vt}Variable {name or '<unnamed>'}"
                    unbound_nodes.append(text)
            except Exception:
                continue
    counters['variable_nodes_unbound'] = len(unbound_nodes)
    for text in unbound_nodes[:WARNING_LIMIT]:
        reporting.append_limited(warnings, f"unbound variable reader node: {text}", limit=WARNING_LIMIT)
        details['unbound_variables'].append(text)


    for key, value in source_counters.items():
        if isinstance(value, int):
            counters[f'source_{key}'] = int(value)

    blocking_count = len(blockers)
    warning_count = len(warnings)
    counters['blocking_issues'] = blocking_count
    counters['warnings'] = warning_count
    counters['ready'] = int(blocking_count == 0)

    summary = summarize(counters)
    return {
        'version': 1,
        'ready': bool(counters['ready']),
        'summary': summary,
        'counters': dict(counters),
        'blocking': blockers,
        'warnings': warnings,
        'details': details,
    }


def summarize(counters: Dict[str, Any]) -> str:
    return (
        f"ready={bool(counters.get('ready', 0))} "
        f"nodes={counters.get('runtime_nodes_schema_known', 0)}/{counters.get('runtime_nodes', 0)} "
        f"properties={counters.get('properties_encodable', 0)}/{counters.get('properties_total', 0)} "
        f"inputs={counters.get('exportable_input_sockets_bound', 0)}/{counters.get('exportable_input_sockets', 0)} "
        f"links={counters.get('dataflow_links_encodable', 0)}/{counters.get('dataflow_links', 0)} "
        f"variables={counters.get('variables_encodable', 0)}/{counters.get('variables_total', 0)} "
        f"editor-skipped={counters.get('editor_nodes_skipped', 0)} "
        f"blockers={counters.get('blocking_issues', 0)} "
        f"warnings={counters.get('warnings', 0)}"
    )


def run_and_store(tree: Any) -> dict:
    report = report_for_tree(tree)
    reporting.write_report(tree, report, report_key=REPORT_KEY, summary_key=SUMMARY_KEY, ready_key=READY_KEY)
    return report


class REDENGINE_OT_validate_roundtrip(bpy.types.Operator):
    bl_idname = 'redengine.validate_roundtrip'
    bl_label = 'Validate Round Trip'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and getattr(tree, 'bl_idname', '') == ANIMGRAPH_TREE_ID

    def execute(self, context):
        tree = context.space_data.node_tree
        report = run_and_store(tree)
        counters = report.get('counters', {})
        summary = report.get('summary', '')
        if report.get('ready'):
            self.report({'INFO'}, f"Round-trip audit ready: {summary}")
        else:
            self.report({'WARNING'}, f"Round-trip audit blockers={counters.get('blocking_issues', 0)} warnings={counters.get('warnings', 0)}")
        return {'FINISHED'}
