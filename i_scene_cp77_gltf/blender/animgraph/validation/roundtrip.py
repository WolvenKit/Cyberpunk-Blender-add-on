from __future__ import annotations

import json
from collections import defaultdict
<<<<<<< Updated upstream
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
=======
from typing import Any

from ....animation.model.animgraph import sm_conditions
from ....animation.model.animgraph.constants import ANIM_NODE_PREFIX
from ....animation.model.animgraph.schema import enums, registry
from ....core.log import debug_exception, get_logger, log_once
from .. import (
    index as graph_index,
)
from .. import (
    presenters,
    sm_edit,
    sm_records,
    sm_sockets,
    variables,
)
from ..access import get_attr, get_idprop
from ..property_codec import encode_node_property
from ..sm_records import ENTRY_RED_TYPE, _pseudo_node
from . import reporting

_LOG = get_logger(__name__)


REPORT_KEY = "red_roundtrip_audit_report"
SUMMARY_KEY = "red_roundtrip_audit_summary"
READY_KEY = "red_roundtrip_audit_ready"
>>>>>>> Stashed changes

BLOCKER_LIMIT = 200
WARNING_LIMIT = 200


<<<<<<< Updated upstream
ENCODABLE_KINDS = {
    'BOOL', 'INT', 'UINT', 'FLOAT', 'STRING', 'CNAME',
    'ENUM', 'FLAGS_ENUM',
    'TRANSFORM_INDEX', 'NAMED_TRACK_INDEX', 'VISUAL_TAG_CONDITION',
    'VECTOR2', 'VECTOR3', 'VECTOR4', 'QUATERNION', 'QSTRANSFORM',
    'FLOAT_CLAMP', 'CURVE_FLOAT', 'ARRAY', 'STRUCT', 'HANDLE_STRUCT',
    'NULL', 'RAW_JSON',
=======
# Fields of a state machine node that its transition records now model. A raw
# preserved property under one of these is not reported for a machine that has
# records (the rows are edited and exported from the records, not from the raw JSON).
RECORD_MODELED_FIELDS = frozenset(
    {
        "transitions",
        "globalTransitions",
        "conditionalEntries",
        "anyStateInterpolator",
    }
)


ENCODABLE_KINDS = {
    "BOOL",
    "INT",
    "UINT",
    "FLOAT",
    "STRING",
    "CNAME",
    "ENUM",
    "FLAGS_ENUM",
    "TRANSFORM_INDEX",
    "NAMED_TRACK_INDEX",
    "VISUAL_TAG_CONDITION",
    "VECTOR2",
    "VECTOR3",
    "VECTOR4",
    "QUATERNION",
    "QSTRANSFORM",
    "FLOAT_CLAMP",
    "CURVE_FLOAT",
    "ARRAY",
    "STRUCT",
    "HANDLE_STRUCT",
    "NULL",
    "RAW_JSON",
>>>>>>> Stashed changes
}


def _node_name(node: Any) -> str:
<<<<<<< Updated upstream
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
=======
    return str(get_attr(node, "name", "<node>") or "<node>")


def _node_label(node: Any) -> str:
    return str(get_attr(node, "label", "") or _node_name(node))


def _presenter_known(node_type: str, presenter_id: str) -> bool:
    if presenters is None:
        return bool(presenter_id)
    try:
        expected = presenters.presenter_id_for(node_type)
        return bool(presenter_id) and presenter_id == expected
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_presenter_known", type(error).__name__),
            "presenter known: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return bool(presenter_id)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
<<<<<<< Updated upstream
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
=======
    except (TypeError, ValueError):
        return str(value)


def _variable_encode_preview(var: Any) -> tuple[bool, str]:
    """Validate that one graph variable can be encoded as JSON"""
    vt = str(get_attr(var, "var_type", ""))
    try:
        if vt == "Bool":
            return True, _safe_json(bool(var.current_bool))
        if vt == "Int":
            return True, _safe_json(int(var.current_int))
        if vt == "Float":
            return True, _safe_json(float(var.current_float))
        if vt == "Vector":
            return True, _safe_json(
                {
                    "$type": "Vector4",
                    "X": float(var.current_vector[0]),
                    "Y": float(var.current_vector[1]),
                    "Z": float(var.current_vector[2]),
                    "W": float(var.current_vector[3]),
                }
            )
        if vt == "Quaternion":
            return True, _safe_json(
                {
                    "$type": "Quaternion",
                    "i": float(var.current_vector[0]),
                    "j": float(var.current_vector[1]),
                    "k": float(var.current_vector[2]),
                    "r": float(var.current_vector[3]),
                }
            )
        if vt == "Transform":
            raw = str(
                get_attr(var, "current_json", "") or get_attr(var, "current_value", "")
            )
>>>>>>> Stashed changes
            if raw:
                try:
                    json.loads(raw)
                    return True, raw
<<<<<<< Updated upstream
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
=======
                except (TypeError, ValueError):
                    return True, raw
            return True, ""

        raw = str(
            get_attr(var, "current_json", "") or get_attr(var, "current_value", "")
        )
        if raw:
            return True, raw
        return False, "missing variable value"
    except Exception as exc:
        debug_exception(
            _LOG, "Could not encode a %s variable for the round-trip preview", vt
        )
        return False, str(exc)


def _is_record_modeled(node: Any, path: str) -> bool:
    """True for a raw property of a state machine with records that the records replace"""
    if not (
        sm_sockets.is_state_machine(node)
        and bool(get_attr(node, "red_sm_records", False))
    ):
        return False
    head = path.split(".", 1)[0].split("[", 1)[0]
    return head in RECORD_MODELED_FIELDS


def _sm_label(node: Any) -> str:
    return str(
        get_attr(node, "label", "") or get_attr(node, "name", "") or "state machine"
    )


def _owner_label(owner: Any, container: Any) -> str:
    if owner is container:
        return _sm_label(container)
    return sm_edit.source_label(owner)


def _has_empty_group(conditions: list) -> bool:
    """True when an ALL-of group in the flat pre-order list has no child entry"""
    for index, entry in enumerate(conditions):
        if entry.short != sm_conditions.GROUP:
            continue
        following = conditions[index + 1] if index + 1 < len(conditions) else None
        if following is None or following.depth <= entry.depth:
            return True
    return False


def _audit_state_machine(
    sm_node: Any, counters: dict[str, int], blockers: list[str], warnings: list[str]
) -> None:
    """Transition rules for one state machine container that has records"""
    tree = get_attr(sm_node, "node_tree", None)
    if tree is None:
        return
    counters["state_machines_with_records"] += 1
    sm_label = _sm_label(sm_node)
    states = {
        str(get_attr(node, "red_handle_id", "") or "")
        for node in tree.nodes
        if sm_edit.is_state(node)
    }
    states.discard("")

    for note in sm_edit.import_notes(sm_node):
        counters["transitions_listed_twice"] += 1
        reporting.append_limited(
            warnings,
            f"state machine {sm_label}: {note} (dismiss in the States panel)",
            limit=WARNING_LIMIT,
        )

    entry = _pseudo_node(tree, ENTRY_RED_TYPE)
    if entry is not None and sm_edit.default_row(entry) is None:
        counters["default_state_unset"] += 1
        reporting.append_limited(
            blockers,
            f"state machine {sm_label}: the default state is not set",
            limit=BLOCKER_LIMIT,
        )

    for owner in sm_edit.transition_owners(sm_node):
        label = _owner_label(owner, sm_node)
        for n, rec in enumerate(owner.red_transitions):
            counters["transition_records"] += 1
            if rec.list_name == sm_records.DEFAULT_LIST:
                if rec.target_handle not in states:
                    counters["default_state_unset"] += 1
                    reporting.append_limited(
                        blockers,
                        f"state machine {sm_label}: the default state is not set",
                        limit=BLOCKER_LIMIT,
                    )
                continue
            if rec.target_handle not in states:
                counters["transitions_without_target"] += 1
                reporting.append_limited(
                    blockers,
                    f"transition has no target: {label} row {n + 1}",
                    limit=BLOCKER_LIMIT,
                )
            if owner is sm_node:
                counters["transitions_kept_on_container"] += 1
                reporting.append_limited(
                    warnings,
                    f"transition kept on the state machine (no state lists it): {sm_label} row {n + 1}",
                    limit=WARNING_LIMIT,
                )
            if _has_empty_group(sm_records.record_conditions(rec)):
                counters["transitions_with_empty_group"] += 1
                reporting.append_limited(
                    warnings,
                    f"empty condition group: {label} row {n + 1}",
                    limit=WARNING_LIMIT,
                )


def report_for_tree(tree: Any) -> dict:
    root = reporting.root_tree(tree)
    index = graph_index.build_index(root)
    source_counters = dict(index.get("counters", {}))

    counters: dict[str, int] = defaultdict(int)
    blockers: list[str] = []
    warnings: list[str] = []
    details: dict[str, list] = {
        "blocking": blockers,
        "warnings": warnings,
        "unbound_variables": [],
        "raw_properties": [],
        "encode_failures": [],
        "editor_exportable_nodes": [],
        "missing_property_paths": [],
        "invalid_enums": [],
    }

    nodes_by_handle = index.get("nodes_by_handle", {}) or {}

    # Transition rules first: their findings must not be crowded out of the
    # limited warning list by the many raw-property notes.
    for tree_obj in graph_index.iter_trees(root):
        for node in getattr(tree_obj, "nodes", []) or []:
            if not sm_sockets.is_state_machine(node):
                continue
            for text in sm_records.structure_problems(node):
                counters["state_machine_structure_problems"] += 1
                reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
            if bool(get_attr(node, "red_sm_records", False)):
                _audit_state_machine(node, counters, blockers, warnings)

    for tree_obj in graph_index.iter_trees(root):
        counters["trees"] += 1
        for node in getattr(tree_obj, "nodes", []) or []:
            counters["nodes_total"] += 1
            nname = _node_name(node)
            nlabel = _node_label(node)
            nhandle = graph_index.node_handle(node)
            ntype = graph_index.node_type(node)
            exportable = graph_index.node_is_exportable(node)
            editor = graph_index.node_is_pseudo(node)
            presenter = str(get_attr(node, "red_presenter", "") or "")

            if editor:
                counters["editor_nodes_skipped"] += 1
            if editor and exportable:
                counters["editor_exportable_nodes"] += 1
                text = (
                    f"editor node marked exportable: {nname} ({ntype or '<no type>'})"
                )
                reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                details["editor_exportable_nodes"].append(text)
>>>>>>> Stashed changes

            if not exportable:
                continue

<<<<<<< Updated upstream
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
=======
            counters["runtime_nodes"] += 1
            if not nhandle:
                reporting.append_limited(
                    blockers,
                    f"runtime node lacks HandleId: {nname} ({ntype or '<no type>'})",
                    limit=BLOCKER_LIMIT,
                )
            if not ntype:
                reporting.append_limited(
                    blockers,
                    f"runtime node lacks red_type: {nname}",
                    limit=BLOCKER_LIMIT,
                )
            elif not ntype.startswith(ANIM_NODE_PREFIX):
                reporting.append_limited(
                    blockers,
                    f"exportable node is not animAnimNode_*: {nhandle or nname} {ntype}",
                    limit=BLOCKER_LIMIT,
                )
            elif not registry.has_class(ntype):
                reporting.append_limited(
                    blockers,
                    f"runtime node has unknown RTTI class: {nhandle or nname} {ntype}",
                    limit=BLOCKER_LIMIT,
                )
            else:
                counters["runtime_nodes_schema_known"] += 1

            if not presenter:
                reporting.append_limited(
                    blockers,
                    f"runtime node lacks presenter id: {nhandle or nname} {ntype or '<no type>'}",
                    limit=BLOCKER_LIMIT,
                )
            elif not _presenter_known(ntype, presenter):
                reporting.append_limited(
                    warnings,
                    f"runtime node has non-standard presenter id {presenter!r}: {nhandle or nname} {ntype}",
                    limit=WARNING_LIMIT,
                )

            for prop in getattr(node, "red_properties", []) or []:
                counters["properties_total"] += 1
                key = str(get_attr(prop, "key", "") or "")
                path = str(get_attr(prop, "json_path", "") or "")
                kind = str(get_attr(prop, "value_kind", "") or "")
                label = f"{nhandle or nname}.{path or key or '<property>'}"

                if not path:
                    counters["properties_missing_json_path"] += 1
                    text = f"property lacks json_path: {label} ({kind or '<no kind>'})"
                    reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                    details["missing_property_paths"].append(text)

                if not kind or kind not in ENCODABLE_KINDS:
                    counters["properties_unknown_kind"] += 1
                    reporting.append_limited(
                        blockers,
                        f"property has unencodable value kind: {label} kind={kind!r}",
                        limit=BLOCKER_LIMIT,
                    )
                    continue

                if kind == "RAW_JSON":
                    if _is_record_modeled(node, path or key):
                        counters["raw_properties_modeled_by_records"] += 1
                    else:
                        counters["raw_properties"] += 1
                        text = f"raw preserved property: {label}"
                        reporting.append_limited(warnings, text, limit=WARNING_LIMIT)
                        details["raw_properties"].append(text)

                if kind in {"ENUM", "FLAGS_ENUM"}:
                    enum_type = str(
                        get_attr(prop, "enum_type", "")
                        or get_attr(prop, "red_type", "")
                        or ""
                    )
                    if not enum_type or not enums.has_enum(enum_type):
                        counters["invalid_enum_properties"] += 1
                        text = f"enum property lacks known enum type: {label} enum={enum_type!r}"
                        reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                        details["invalid_enums"].append(text)

                if encode_node_property is None:
                    counters["properties_not_encoded_no_helper"] += 1
                    continue
                try:
                    encode_node_property(prop)
                    counters["properties_encodable"] += 1
                except Exception as exc:
                    debug_exception(
                        _LOG,
                        "Could not encode property %s for the round-trip report",
                        label,
                    )
                    counters["properties_encode_failed"] += 1
                    text = f"property encode failed: {label} ({kind}) -> {exc}"
                    reporting.append_limited(blockers, text, limit=BLOCKER_LIMIT)
                    details["encode_failures"].append(text)

            for sock in getattr(node, "inputs", []) or []:
                if not graph_index.socket_exportable(sock):
                    continue
                counters["exportable_input_sockets"] += 1
                path = graph_index.socket_path(sock)
                link_type = graph_index.socket_link_type(sock)
                owner = graph_index.socket_owner(sock) or nhandle
                if not owner or not path or not link_type:
                    counters["input_sockets_missing_binding"] += 1
                    reporting.append_limited(
                        blockers,
                        f"exportable input socket lacks binding: {nhandle or nname}.{getattr(sock, 'name', '<socket>')} owner={owner!r} path={path!r} link={link_type!r}",
                        limit=BLOCKER_LIMIT,
                    )
                else:
                    counters["exportable_input_sockets_bound"] += 1

    duplicates = index.get("duplicate_handles", {}) or {}
    for handle, names in duplicates.items():
        counters["duplicate_handles"] += 1
        reporting.append_limited(
            blockers,
            f"duplicate HandleId {handle}: {', '.join(map(str, names[:6]))}",
            limit=BLOCKER_LIMIT,
        )

    for tree_obj in graph_index.iter_trees(root):
        for link in getattr(tree_obj, "links", []) or []:
            from_sock = getattr(link, "from_socket", None)
            to_sock = getattr(link, "to_socket", None)
            from_node = getattr(link, "from_node", None)
            to_node = getattr(link, "to_node", None)
            if from_sock is None or to_sock is None:
                counters["broken_link_objects"] += 1
                reporting.append_limited(
                    blockers,
                    "broken Blender link object with missing socket",
                    limit=BLOCKER_LIMIT,
                )
                continue
            semantics = graph_index.socket_semantics(
                to_sock
            ) or graph_index.socket_semantics(from_sock)
            if semantics != graph_index.DATAFLOW:
                counters["non_dataflow_links_skipped"] += 1

                if graph_index.socket_exportable(
                    from_sock
                ) and graph_index.socket_exportable(to_sock):
                    counters["non_dataflow_exportable_links"] += 1
                    reporting.append_limited(
                        blockers,
                        f"non-dataflow link is exportable: {getattr(from_node, 'name', '?')} -> {getattr(to_node, 'name', '?')} semantics={semantics!r}",
                        limit=BLOCKER_LIMIT,
                    )
                continue

            counters["dataflow_links"] += 1
            source = (
                graph_index.socket_source(from_sock)
                or graph_index.socket_owner(from_sock)
                or graph_index.node_handle(from_node)
            )
            target = (
                graph_index.socket_target(to_sock)
                or graph_index.socket_owner(to_sock)
                or graph_index.node_handle(to_node)
            )
            path = graph_index.socket_path(to_sock)
            link_type = graph_index.socket_link_type(to_sock)
            if not source or not target or not path or not link_type:
                counters["dataflow_links_incomplete"] += 1
                reporting.append_limited(
                    blockers,
                    f"dataflow link lacks identity: {getattr(from_node, 'name', '?')} -> {getattr(to_node, 'name', '?')} source={source!r} target={target!r} path={path!r} type={link_type!r}",
                    limit=BLOCKER_LIMIT,
                )
                continue
            if source not in nodes_by_handle:
                counters["dataflow_links_missing_source_node"] += 1
                reporting.append_limited(
                    blockers,
                    f"dataflow link source handle has no exportable node projection: source={source} target={target}.{path}",
                    limit=BLOCKER_LIMIT,
                )
            if target not in nodes_by_handle:
                counters["dataflow_links_missing_target_node"] += 1
                reporting.append_limited(
                    blockers,
                    f"dataflow link target handle has no exportable node projection: source={source} target={target}.{path}",
                    limit=BLOCKER_LIMIT,
                )
            counters["dataflow_links_encodable"] += 1

    root_vars = list(getattr(root, "variables", []) or [])
    counters["variables_total"] = len(root_vars)
    for var in root_vars:
        ok, msg = _variable_encode_preview(var)
        if ok:
            counters["variables_encodable"] += 1
        else:
            counters["variables_encode_failed"] += 1
            reporting.append_limited(
                blockers,
                f"variable encode failed: {getattr(var, 'var_type', '?')} {getattr(var, 'name', '<unnamed>')} -> {msg}",
                limit=BLOCKER_LIMIT,
            )

    try:
        variables.bind_all_variables(root)
    except Exception:
        debug_exception(_LOG, "AnimGraph variable binding details")
    unbound_nodes: list[str] = []
    for tree_obj in graph_index.iter_trees(root):
        for node in getattr(tree_obj, "nodes", []) or []:
            try:
                if not variables.is_variable_node(node):
                    continue
                if not bool(get_idprop(node, "red_variable_bound", False)):
                    vt = variables.variable_type_for_node(node)
                    name = variables.node_variable_name(node)
                    handle = graph_index.node_handle(node)
                    text = f"{handle or _node_name(node)} {vt}Variable {name or '<unnamed>'}"
                    unbound_nodes.append(text)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("report_for_tree", type(error).__name__),
                    "report for tree: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
    counters["variable_nodes_unbound"] = len(unbound_nodes)
    for text in unbound_nodes[:WARNING_LIMIT]:
        reporting.append_limited(
            warnings, f"unbound variable reader node: {text}", limit=WARNING_LIMIT
        )
        details["unbound_variables"].append(text)

    for key, value in source_counters.items():
        if isinstance(value, int):
            counters[f"source_{key}"] = int(value)

    blocking_count = len(blockers)
    warning_count = len(warnings)
    counters["blocking_issues"] = blocking_count
    counters["warnings"] = warning_count
    counters["ready"] = int(blocking_count == 0)

    summary = summarize(counters)
    return {
        "version": 1,
        "ready": bool(counters["ready"]),
        "summary": summary,
        "counters": dict(counters),
        "blocking": blockers,
        "warnings": warnings,
        "details": details,
    }


def summarize(counters: dict[str, Any]) -> str:
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
    reporting.write_report(
        tree,
        report,
        report_key=REPORT_KEY,
        summary_key=SUMMARY_KEY,
        ready_key=READY_KEY,
    )
    return report
>>>>>>> Stashed changes
