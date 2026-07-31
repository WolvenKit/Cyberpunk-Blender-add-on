from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...blender.animgraph import index as graph_index
from ...blender.animgraph.validation import roundtrip as roundtrip_audit
from ...blender.animgraph.validation import reporting


REPORT_KEY = 'red_graph_validator_report'
SUMMARY_KEY = 'red_graph_validator_summary'
READY_KEY = 'red_graph_validator_ready'

BLOCKER_LIMIT = 200
WARNING_LIMIT = 200


def _unique_extend(target: List[str], source: Any, *, limit: int) -> None:
    if not isinstance(source, (list, tuple)):
        return
    seen = set(target)
    for item in source:
        text = str(item)
        if text in seen:
            continue
        reporting.append_limited(target, text, limit=limit)
        seen.add(text)
        if len(target) >= limit:
            break


def _source_alignment_stage(root: Any) -> dict:
    report = graph_index.report_for_tree(root)
    counters = dict(report.get('counters', {}) or {})
    blocking: List[str] = []

    checks = (
        ('missing_handle_nodes', 'runtime node lacks HandleId'),
        ('duplicate_handles', 'duplicate HandleId in Blender projection'),
        ('unbound_exportable_input_sockets', 'exportable input socket lacks REDengine binding'),
        ('incomplete_dataflow_links', 'dataflow link lacks source/target/path identity'),
        ('editor_exportable_nodes', 'editor-only node is marked exportable'),
    )
    for key, label in checks:
        count = int(counters.get(key, 0) or 0)
        if count:
            reporting.append_limited(blocking, f'{label}: {count}', limit=BLOCKER_LIMIT)

    return {
        'ready': bool(counters.get('roundtrip_ready', 0)) and not blocking,
        'summary': report.get('summary', ''),
        'counters': counters,
        'blocking': blocking,
        'warnings': list(report.get('problems', []) or []),
    }


def _roundtrip_stage(root: Any) -> dict:
    report = roundtrip_audit.report_for_tree(root)
    return {
        'ready': bool(report.get('ready', False)),
        'summary': report.get('summary', ''),
        'counters': dict(report.get('counters', {}) or {}),
        'blocking': list(report.get('blocking', []) or []),
        'warnings': list(report.get('warnings', []) or []),
        'details': report.get('details', {}) if isinstance(report.get('details', {}), dict) else {},
    }


def _export_stage(root: Any, payload: Optional[Dict[str, Any]] = None) -> dict:
    try:


        from ...exporters.animgraph import audit, root as root_export

        generated = payload if isinstance(payload, dict) else root_export.encode_wolvenkit_json(root)
        audit = audit.export_reversal_audit_for_payload(root, generated)
        counters = dict(audit.get('counters', {}) or {})
        blocking = list(audit.get('blocking', []) or [])
        warnings = list(audit.get('warnings', []) or [])
        return {
            'ready': bool(audit.get('ready', False)),
            'summary': audit.get('summary', ''),
            'counters': counters,
            'blocking': blocking,
            'warnings': warnings,
            'details': audit.get('details', {}) if isinstance(audit.get('details', {}), dict) else {},
        }
    except Exception as exc:
        return {
            'ready': False,
            'summary': f'export dry-run failed: {exc}',
            'counters': {},
            'blocking': [f'export dry-run failed: {exc}'],
            'warnings': [],
            'details': {},
        }


def _combined_counters(source: dict, roundtrip: dict, export: dict) -> Dict[str, int]:
    sc = source.get('counters', {}) if isinstance(source, dict) else {}
    rc = roundtrip.get('counters', {}) if isinstance(roundtrip, dict) else {}
    ec = export.get('counters', {}) if isinstance(export, dict) else {}

    runtime_total = int(ec.get('runtimeNodes', 0) or rc.get('runtime_nodes', 0) or sc.get('exportable_nodes', 0) or 0)
    runtime_valid = int(runtime_total - int(ec.get('nodesMissingInExport', 0) or 0) - int(ec.get('nodesMissingData', 0) or 0) - int(ec.get('nodesWrongTypeFamily', 0) or 0)) if runtime_total else int(rc.get('runtime_nodes_schema_known', 0) or 0)
    runtime_valid = max(0, min(runtime_valid, runtime_total)) if runtime_total else runtime_valid

    prop_total = int(ec.get('propertiesTotal', 0) or rc.get('properties_total', 0) or 0)
    prop_valid = int(ec.get('propertiesRoundtripped', 0) or rc.get('properties_encodable', 0) or 0)

    socket_total = int(ec.get('socketsTotal', 0) or rc.get('exportable_input_sockets', 0) or sc.get('exportable_input_sockets', 0) or 0)
    socket_valid = int(ec.get('socketsRoundtripped', 0) or rc.get('exportable_input_sockets_bound', 0) or sc.get('bound_exportable_input_sockets', 0) or 0)

    links_total = int(rc.get('dataflow_links', 0) or sc.get('dataflow_links', 0) or 0)
    links_valid = int(rc.get('dataflow_links_encodable', 0) or sc.get('roundtrip_ready_links', 0) or 0)

    vars_total = int(ec.get('variables', 0) or rc.get('variables_total', 0) or 0)
    vars_valid = int(rc.get('variables_encodable', 0) or vars_total)

    duplicate_ids = int(ec.get('duplicateHandleIds', 0) or sc.get('duplicate_handles', 0) or 0)
    missing_refs = int(ec.get('missingHandleRefs', 0) or 0)

    return {
        'runtime_nodes_total': runtime_total,
        'runtime_nodes_valid': runtime_valid,
        'properties_total': prop_total,
        'properties_valid': min(prop_valid, prop_total) if prop_total else prop_valid,
        'input_sockets_total': socket_total,
        'input_sockets_valid': min(socket_valid, socket_total) if socket_total else socket_valid,
        'links_total': links_total,
        'links_valid': min(links_valid, links_total) if links_total else links_valid,
        'variables_total': vars_total,
        'variables_valid': min(vars_valid, vars_total) if vars_total else vars_valid,
        'missing_handle_refs': missing_refs,
        'duplicate_handle_ids': duplicate_ids,
        'source_alignment_ready': int(bool(source.get('ready', False))),
        'roundtrip_ready': int(bool(roundtrip.get('ready', False))),
        'export_projection_ready': int(bool(export.get('ready', False))),
    }


def _artist_summary(counters: Dict[str, int], ready: bool) -> str:
    if ready:
        return (
            f"Ready: {counters.get('runtime_nodes_valid', 0)}/{counters.get('runtime_nodes_total', 0)} nodes, "
            f"{counters.get('properties_valid', 0)}/{counters.get('properties_total', 0)} properties, "
            f"{counters.get('input_sockets_valid', 0)}/{counters.get('input_sockets_total', 0)} sockets."
        )
    return (
        f"Not ready: {counters.get('blocking_issues', 0)} blocking issue(s), "
        f"{counters.get('warnings', 0)} warning(s)."
    )


def report_for_tree(tree: Any, *, payload: Optional[Dict[str, Any]] = None) -> dict:
    root = reporting.root_tree(tree)
    source = _source_alignment_stage(root)
    roundtrip = _roundtrip_stage(root)
    export = _export_stage(root, payload=payload)

    blocking: List[str] = []
    warnings: List[str] = []
    _unique_extend(blocking, source.get('blocking', []), limit=BLOCKER_LIMIT)
    _unique_extend(blocking, roundtrip.get('blocking', []), limit=BLOCKER_LIMIT)
    _unique_extend(blocking, export.get('blocking', []), limit=BLOCKER_LIMIT)
    _unique_extend(warnings, source.get('warnings', []), limit=WARNING_LIMIT)
    _unique_extend(warnings, roundtrip.get('warnings', []), limit=WARNING_LIMIT)
    _unique_extend(warnings, export.get('warnings', []), limit=WARNING_LIMIT)

    counters = _combined_counters(source, roundtrip, export)
    counters['blocking_issues'] = len(blocking)
    counters['warnings'] = len(warnings)
    ready = bool(source.get('ready') and roundtrip.get('ready') and export.get('ready') and not blocking)
    counters['ready'] = int(ready)

    artist_summary = _artist_summary(counters, ready)
    technical_summary = (
        f"ready={ready} "
        f"nodes={counters.get('runtime_nodes_valid', 0)}/{counters.get('runtime_nodes_total', 0)} "
        f"properties={counters.get('properties_valid', 0)}/{counters.get('properties_total', 0)} "
        f"sockets={counters.get('input_sockets_valid', 0)}/{counters.get('input_sockets_total', 0)} "
        f"links={counters.get('links_valid', 0)}/{counters.get('links_total', 0)} "
        f"variables={counters.get('variables_valid', 0)}/{counters.get('variables_total', 0)} "
        f"refsMissing={counters.get('missing_handle_refs', 0)} "
        f"duplicates={counters.get('duplicate_handle_ids', 0)} "
        f"blockers={len(blocking)} warnings={len(warnings)}"
    )

    return {
        'version': 1,
        'scope': 'production-graph-validator',
        'ready': ready,
        'artist_summary': artist_summary,
        'summary': technical_summary,
        'counters': counters,
        'blocking': blocking,
        'warnings': warnings,
        'stages': {
            'sourceAlignment': source,
            'roundTrip': roundtrip,
            'exportProjection': export,
        },
    }


def run_and_store(tree: Any, *, payload: Optional[Dict[str, Any]] = None) -> dict:
    report = report_for_tree(tree, payload=payload)
    reporting.write_report(tree, report, report_key=REPORT_KEY, summary_key=SUMMARY_KEY, ready_key=READY_KEY, summary_field='artist_summary')
    return report
