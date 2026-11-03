from __future__ import annotations

import json
from typing import Any, Dict, List

import bpy

from ...animation.animgraph_constants import ANIM_NODE_PREFIX
from ...blender.animgraph.property_codec import encode_node_property
from ...blender.animgraph import variables as variable_bindings
from ...blender.animgraph.access import get_attr
from .tree_state import root_tree
from .paths import _iter_exportable_input_sockets, _link_source_handle, _json_path_get
from .nodes import _runtime_node, _json_idprop

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
    root = root_tree(tree) or tree
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
            handle = str(get_attr(node, 'red_handle_id', '') or '')
            red_type = str(get_attr(node, 'red_type', '') or '')
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
                path = str(get_attr(sock, 'red_json_path', '') or '')
                link_type = str(get_attr(sock, 'red_link_type', '') or '')
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
