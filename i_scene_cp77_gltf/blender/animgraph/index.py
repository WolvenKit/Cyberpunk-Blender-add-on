from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Tuple

from .access import get_attr, get_idprop, is_truthy

from ...animation.animgraph_constants import ANIM_NODE_PREFIX


DATAFLOW = 'dataflow'


def node_handle(node: Any) -> str:
    return str(get_attr(node, 'red_handle_id', '') or get_idprop(node, 'red_handle_id', '') or '')


def node_type(node: Any) -> str:
    return str(get_attr(node, 'red_type', '') or get_idprop(node, 'red_type', '') or '')


def node_is_pseudo(node: Any) -> bool:
    ntype = node_type(node)
    handle = node_handle(node)
    return bool(
        is_truthy(get_attr(node, 'red_pseudo', False))
        or str(ntype).startswith('editor')
        or str(handle).startswith('editor')
    )


def node_is_exportable(node: Any) -> bool:
    explicit = get_attr(node, 'red_exportable', None)
    if explicit is not None:
        return bool(explicit)
    return (not node_is_pseudo(node)) and node_type(node).startswith(ANIM_NODE_PREFIX)


def socket_exportable(socket: Any) -> bool:
    explicit = get_attr(socket, 'red_exportable', None)
    return True if explicit is None else bool(explicit)


def socket_semantics(socket: Any) -> str:
    return str(get_attr(socket, 'red_edge_semantics', '') or 'unknown')


def socket_role(socket: Any) -> str:
    return str(get_attr(socket, 'red_socket_role', '') or '')


def socket_owner(socket: Any) -> str:
    return str(get_attr(socket, 'red_owner_handle', '') or '')


def socket_source(socket: Any) -> str:
    return str(get_attr(socket, 'red_source_handle', '') or '')


def socket_target(socket: Any) -> str:
    return str(get_attr(socket, 'red_target_handle', '') or '')


def socket_path(socket: Any) -> str:
    return str(get_attr(socket, 'red_json_path', '') or '')


def socket_link_type(socket: Any) -> str:
    return str(get_attr(socket, 'red_link_type', '') or '')


def socket_ref_style(socket: Any) -> str:
    return str(get_attr(socket, 'red_ref_style', '') or '')


def iter_trees(root_tree: Any) -> Iterable[Any]:
    """Yield the root tree and reachable internal node groups once."""
    if root_tree is None:
        return
    seen = set()
    queue = deque([root_tree])
    while queue:
        tree = queue.popleft()
        key = getattr(tree, 'name_full', None) or getattr(tree, 'name', None) or id(tree)
        if key in seen:
            continue
        seen.add(key)
        yield tree
        for node in getattr(tree, 'nodes', []) or []:
            child = getattr(node, 'node_tree', None)
            if child is not None:
                ckey = getattr(child, 'name_full', None) or getattr(child, 'name', None) or id(child)
                if ckey not in seen:
                    queue.append(child)


            for prop_name in ('red_editor_subgraph_a_name', 'red_editor_subgraph_b_name'):
                tname = str(get_attr(node, prop_name, '') or '')
                if not tname:
                    continue
                try:
                    child_tree = __import__('bpy').data.node_groups.get(tname)
                except Exception:
                    child_tree = None
                if child_tree is not None:
                    ckey = getattr(child_tree, 'name_full', None) or getattr(child_tree, 'name', None) or id(child_tree)
                    if ckey not in seen:
                        queue.append(child_tree)


def _socket_snapshot(socket: Any) -> dict:
    return {
        'name': str(getattr(socket, 'name', '')),
        'role': socket_role(socket),
        'owner_handle': socket_owner(socket),
        'field_name': str(get_attr(socket, 'red_field_name', '') or ''),
        'json_path': socket_path(socket),
        'link_type': socket_link_type(socket),
        'array_index': int(get_attr(socket, 'red_array_index', -1) or -1),
        'exportable': socket_exportable(socket),
        'edge_semantics': socket_semantics(socket),
        'source_handle': socket_source(socket),
        'target_handle': socket_target(socket),
        'ref_style': socket_ref_style(socket),
        'pseudo': bool(get_attr(socket, 'red_pseudo', False)),
    }


def build_index(root_tree: Any) -> dict:
    """Build a HandleId-centric read-only index from Blender node trees."""
    nodes_by_handle: Dict[str, Any] = {}
    duplicate_handles: Dict[str, List[str]] = defaultdict(list)
    missing_handle_nodes: List[str] = []
    editor_exportable_nodes: List[str] = []
    unknown_semantic_links: List[str] = []
    unbound_sockets: List[dict] = []
    sockets_by_target_field: Dict[Tuple[str, str], Any] = {}
    links_by_target: Dict[Tuple[str, str], dict] = {}
    outgoing_by_source: Dict[str, List[dict]] = defaultdict(list)
    incoming_by_target: Dict[str, List[dict]] = defaultdict(list)

    counters = defaultdict(int)
    tree_names: List[str] = []

    for tree in iter_trees(root_tree):
        tree_names.append(str(getattr(tree, 'name', '<tree>')))
        counters['trees'] += 1
        for node in getattr(tree, 'nodes', []) or []:
            counters['nodes_total'] += 1
            nhandle = node_handle(node)
            ntype = node_type(node)
            pseudo = node_is_pseudo(node)
            exportable = node_is_exportable(node)
            if pseudo:
                counters['pseudo_nodes'] += 1
            if exportable:
                counters['exportable_nodes'] += 1
            if exportable and not nhandle:
                missing_handle_nodes.append(str(getattr(node, 'name', '<node>')))
            if pseudo and exportable:
                editor_exportable_nodes.append(str(getattr(node, 'name', '<node>')))
            if nhandle:
                if nhandle in nodes_by_handle:
                    duplicate_handles[nhandle].append(str(getattr(node, 'name', '<node>')))
                else:
                    nodes_by_handle[nhandle] = node
            if ntype.startswith(ANIM_NODE_PREFIX):
                counters['anim_node_objects'] += 1

            for prop in getattr(node, 'red_properties', []) or []:
                counters['node_properties_total'] += 1
                kind = str(get_attr(prop, 'value_kind', '') or 'UNKNOWN')
                counters[f'property_kind_{kind}'] += 1
                if kind == 'RAW_JSON':
                    counters['raw_preserved_properties'] += 1
                elif kind:
                    counters['typed_editable_properties'] += 1

            for socket in getattr(node, 'inputs', []) or []:
                counters['input_sockets'] += 1
                snap = _socket_snapshot(socket)
                if snap['exportable']:
                    counters['exportable_input_sockets'] += 1
                    ok = bool(snap['owner_handle'] and snap['json_path'] and snap['link_type'])
                    if ok:
                        counters['bound_exportable_input_sockets'] += 1
                        sockets_by_target_field[(snap['owner_handle'], snap['json_path'])] = socket
                    else:
                        unbound_sockets.append({'node': str(getattr(node, 'name', '<node>')), **snap})
                else:
                    counters['nonexportable_input_sockets'] += 1

            for socket in getattr(node, 'outputs', []) or []:
                counters['output_sockets'] += 1
                if socket_exportable(socket):
                    counters['exportable_output_sockets'] += 1
                else:
                    counters['nonexportable_output_sockets'] += 1

        for link in getattr(tree, 'links', []) or []:
            counters['links_total'] += 1
            from_sock = getattr(link, 'from_socket', None)
            to_sock = getattr(link, 'to_socket', None)
            from_node = getattr(link, 'from_node', None)
            to_node = getattr(link, 'to_node', None)
            if from_sock is None or to_sock is None:
                counters['broken_link_objects'] += 1
                continue
            semantics = socket_semantics(to_sock) or socket_semantics(from_sock)
            exportable = socket_exportable(to_sock) and socket_exportable(from_sock) and semantics == DATAFLOW
            if not semantics or semantics == 'unknown':
                unknown_semantic_links.append(
                    f"{getattr(from_node, 'name', '?')}.{getattr(from_sock, 'name', '?')} -> "
                    f"{getattr(to_node, 'name', '?')}.{getattr(to_sock, 'name', '?')}"
                )
            if exportable:
                source = socket_source(from_sock) or socket_owner(from_sock) or node_handle(from_node)
                target = socket_target(to_sock) or socket_owner(to_sock) or node_handle(to_node)
                path = socket_path(to_sock)
                entry = {
                    'source_handle': str(source or ''),
                    'target_handle': str(target or ''),
                    'target_field_path': path,
                    'link_type': socket_link_type(to_sock) or socket_link_type(from_sock),
                    'ref_style': socket_ref_style(to_sock),
                    'tree': str(getattr(tree, 'name', '<tree>')),
                }
                counters['dataflow_links'] += 1
                if entry['source_handle'] and entry['target_handle'] and entry['target_field_path']:
                    counters['roundtrip_ready_links'] += 1
                    links_by_target[(entry['target_handle'], entry['target_field_path'])] = entry
                    outgoing_by_source[entry['source_handle']].append(entry)
                    incoming_by_target[entry['target_handle']].append(entry)
                else:
                    counters['incomplete_dataflow_links'] += 1
            else:
                counters[f"{semantics or 'unknown'}_links"] += 1

    duplicate_summary = {h: names for h, names in duplicate_handles.items()}
    ready_nodes = max(0, counters['exportable_nodes'] - len(missing_handle_nodes))
    counters['roundtrip_ready_nodes'] = ready_nodes
    counters['missing_handle_nodes'] = len(missing_handle_nodes)
    counters['duplicate_handles'] = len(duplicate_summary)
    counters['editor_exportable_nodes'] = len(editor_exportable_nodes)
    counters['unbound_exportable_input_sockets'] = len(unbound_sockets)
    counters['unknown_semantic_links'] = len(unknown_semantic_links)

    return {
        'counters': dict(counters),
        'tree_names': tree_names,
        'nodes_by_handle': nodes_by_handle,
        'links_by_target': links_by_target,
        'outgoing_by_source': dict(outgoing_by_source),
        'incoming_by_target': dict(incoming_by_target),
        'sockets_by_target_field': sockets_by_target_field,
        'missing_handle_nodes': missing_handle_nodes,
        'duplicate_handles': duplicate_summary,
        'editor_exportable_nodes': editor_exportable_nodes,
        'unbound_sockets': unbound_sockets,
        'unknown_semantic_links': unknown_semantic_links,
    }


def audit_parser(parser: Any) -> dict:
    """Audit parser state immediately after import."""
    index = build_index(getattr(parser, 'root_tree', None))
    counters = dict(index['counters'])
    definitions = getattr(parser, 'definitions', {}) or {}
    bl_nodes = getattr(parser, 'bl_nodes', {}) or {}
    problems: List[str] = []

    counters['serialized_handle_definitions'] = len(definitions)
    counters['parser_nodes_by_handle'] = len(bl_nodes)
    missing_bl_nodes = sorted(str(h) for h in definitions if h not in bl_nodes)

    root_handles = [str(h) for h, data in definitions.items()
                    if isinstance(data, dict) and data.get('$type') == ANIM_NODE_PREFIX + 'Root']
    missing_non_root = [h for h in missing_bl_nodes if h not in set(root_handles)]
    counters['serialized_handles_without_visible_node'] = len(missing_bl_nodes)
    counters['serialized_nonroot_handles_without_visible_node'] = len(missing_non_root)

    metadata_known = 0
    metadata_unknown = 0
    json_extra_fields = 0
    metadata_missing_fields = 0
    try:
        from ...animation.animgraph.schema import rtti
        for _hid, data in definitions.items():
            ntype = str(data.get('$type', ''))
            if rtti.has_class(ntype):
                metadata_known += 1
                declared = {p.get('name') for p in rtti.all_properties(ntype)}
                actual = set(data.keys()) - {'$type'}
                json_extra_fields += len([k for k in actual if k not in declared])


                metadata_missing_fields += len([k for k in declared if k and k not in actual])
            else:
                metadata_unknown += 1
    except Exception as exc:
        problems.append(f"metadata coverage audit failed: {exc}")

    counters['metadata_known_imported_nodes'] = metadata_known
    counters['metadata_unknown_imported_nodes'] = metadata_unknown
    counters['json_fields_not_in_metadata'] = json_extra_fields
    counters['metadata_declared_fields_absent_from_json'] = metadata_missing_fields

    if counters.get('missing_handle_nodes'):
        problems.append(f"{counters['missing_handle_nodes']} exportable node(s) lack red_handle_id")
    if counters.get('duplicate_handles'):
        problems.append(f"{counters['duplicate_handles']} duplicate HandleId value(s) in Blender node projection")
    if counters.get('unbound_exportable_input_sockets'):
        problems.append(f"{counters['unbound_exportable_input_sockets']} exportable input socket(s) lack field binding")
    if counters.get('incomplete_dataflow_links'):
        problems.append(f"{counters['incomplete_dataflow_links']} dataflow link(s) lack source/target/path identity")
    if counters.get('editor_exportable_nodes'):
        problems.append(f"{counters['editor_exportable_nodes']} editor node(s) are marked exportable")
    if missing_non_root:
        problems.append(f"{len(missing_non_root)} serialized non-root HandleId definition(s) lack visible Blender nodes")

    counters['roundtrip_ready'] = int(not problems)
    summary = summarize_counters(counters)
    return {
        'counters': counters,
        'summary': summary,
        'problems': problems,
        'missing_handle_nodes': index['missing_handle_nodes'][:25],
        'unbound_sockets': index['unbound_sockets'][:25],
        'unknown_semantic_links': index['unknown_semantic_links'][:25],
        'missing_serialized_nonroot_handles': missing_non_root[:25],
    }


def summarize_counters(counters: Dict[str, Any]) -> str:
    parts = [
        f"handles={counters.get('roundtrip_ready_nodes', 0)}/{counters.get('exportable_nodes', 0)}",
        f"bound-sockets={counters.get('bound_exportable_input_sockets', 0)}/{counters.get('exportable_input_sockets', 0)}",
        f"dataflow-links={counters.get('roundtrip_ready_links', 0)}/{counters.get('dataflow_links', 0)}",
        f"metadata-known={counters.get('metadata_known_imported_nodes', 0)}/{counters.get('serialized_handle_definitions', 0)}",
        f"raw-props={counters.get('raw_preserved_properties', 0)}",
        f"editor={counters.get('pseudo_nodes', 0)}",
        f"ready={bool(counters.get('roundtrip_ready', 0))}",
    ]
    return ' '.join(parts)


def report_for_tree(root_tree: Any) -> dict:
    index = build_index(root_tree)
    counters = dict(index['counters'])
    counters['roundtrip_ready'] = int(
        counters.get('missing_handle_nodes', 0) == 0
        and counters.get('duplicate_handles', 0) == 0
        and counters.get('unbound_exportable_input_sockets', 0) == 0
        and counters.get('incomplete_dataflow_links', 0) == 0
        and counters.get('editor_exportable_nodes', 0) == 0
    )
    return {
        'counters': counters,
        'summary': summarize_counters(counters),
        'problems': [],
    }


def write_report_to_tree(root_tree: Any, report: dict) -> None:
    if root_tree is None:
        return
    counters = report.get('counters', {}) if isinstance(report, dict) else {}
    problems = report.get('problems', []) if isinstance(report, dict) else []
    summary = report.get('summary', summarize_counters(counters)) if isinstance(report, dict) else ''
    try:
        root_tree['red_source_alignment_summary'] = summary
        root_tree['red_source_alignment_report'] = json.dumps({
            'counters': counters,
            'summary': summary,
            'problems': problems,
        }, sort_keys=True)
        root_tree['red_source_alignment_ready'] = bool(counters.get('roundtrip_ready', 0))
    except Exception:

        pass


def load_report_from_tree(root_tree: Any) -> dict:
    if root_tree is None:
        return {}
    raw = get_idprop(root_tree, 'red_source_alignment_report', '')
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return report_for_tree(root_tree)
