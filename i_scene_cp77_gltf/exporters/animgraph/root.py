import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import bpy

from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID, ANIM_NODE_PREFIX
from ...blender.animgraph.access import get_attr, get_idprop
from .defaults import _schema_resource_path
from .nodes import _encode_tree_runtime_entries, _json_idprop
from .references import normalize_inline_first_references
from .tree_state import root_tree
from .values import cname, clone_json, decode_optional
from .variables import encode_root_variables

def _feature_entry(feature: Any) -> Dict[str, Any]:
    name = str(get_attr(feature, 'name', '') or 'None')
    class_name = str(get_attr(feature, 'class_name', '') or name or 'None')
    return {
        '$type': 'animAnimFeatureEntry',
        'className': cname(class_name or 'None'),
        'debugEnabled': int(bool(get_attr(feature, 'debug_enabled', False))),
        'forceAllocate': int(bool(get_attr(feature, 'force_allocate', False))),
        'name': cname(name or 'None'),
    }

def encode_anim_features(tree: bpy.types.NodeTree) -> List[Dict[str, Any]]:
    root = root_tree(tree) or tree
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
            out.append(clone_json(source))
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
        out.append(clone_json(by_handle[handle]))

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
    handle = str(get_idprop(root, 'red_root_handle', '') or '')
    if not handle:
        handle = str(get_idprop(root, 'red_nodes_to_init_root_handle', '') or '')
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
        'sourceCount': int(get_idprop(root, 'red_nodes_to_init_count', 0) or 0),
        'refCount': len(result),
        'duplicateRefs': duplicates,
        'rootRefDuplicates': root_duplicates,
        'inlineAfterRoot': int(get_idprop(root, 'red_nodes_to_init_inline_after_root', 0) or 0),
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
    root = root_tree(tree) or tree
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
    root = root_tree(tree) or tree
    root_chunk = encode_rootchunk_payload(root)
    archive_name = str(getattr(root, 'name', '') or 'animgraph')
    if not archive_name.endswith('.animgraph') and not archive_name.endswith('.animgraph.json'):
        archive_name = f'{archive_name}.animgraph'

    source_header = decode_optional(get_idprop(root, 'red_source_header_json', ''), {})
    header = dict(source_header) if isinstance(source_header, dict) else {}
    header.setdefault('WolvenKitVersion', '8.18.2')
    header.setdefault('WKitJsonVersion', '0.0.9')
    header.setdefault('GameVersion', 2310)
    header['ExportedDateTime'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    header['DataType'] = 'CR2W'
    header.setdefault('ArchiveFileName', archive_name)

    source_data = decode_optional(get_idprop(root, 'red_source_data_meta_json', ''), {})
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
