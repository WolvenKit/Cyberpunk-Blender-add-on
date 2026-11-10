from typing import Any

import bpy

from ...animation.domain.animgraph.topology import (
    handle_index,
    initialization_handles,
    nested_values,
)
from ...animation.model.animgraph.constants import ANIM_NODE_PREFIX, ANIMGRAPH_TREE_ID
from ...animation.model.animgraph.indices import cname
from ...assetio.headers import (
    SUPPORTED_GAME_VERSION,
    SUPPORTED_WKIT_JSON_VERSION,
    SUPPORTED_WOLVENKIT_VERSION,
    utc_timestamp,
)
from ...blender.animgraph.access import get_attr, get_idprop
from ...core.log import get_logger
from .dangle_patch import validate_payload, write_json
from .defaults import _schema_resource_path, unresolved_default_collector
from .handles import finalize_new_handles
from .nodes import _encode_tree_runtime_entries, _json_idprop, take_unlisted_entries
from .paths import indexed_socket_links
from .references import normalize_inline_first_references
from .tree_state import root_tree
from .values import clone_json, decode_optional
from .variables import encode_root_variables

_LOG = get_logger(__name__)


def _feature_entry(feature: Any) -> dict[str, Any]:
    name = str(get_attr(feature, "name", "") or "None")
    class_name = str(get_attr(feature, "class_name", "") or name or "None")
    return {
        "$type": "animAnimFeatureEntry",
        "className": cname(class_name or "None"),
        "debugEnabled": int(bool(get_attr(feature, "debug_enabled", False))),
        "forceAllocate": int(bool(get_attr(feature, "force_allocate", False))),
        "name": cname(name or "None"),
    }


def encode_anim_features(tree: bpy.types.NodeTree) -> list[dict[str, Any]]:
    root = root_tree(tree) or tree
    features = list(getattr(root, "features", []) or [])
    if not features:
        return []
    return [_feature_entry(feature) for feature in features]


def _require_source_metadata(root: bpy.types.NodeTree, key: str) -> Any:
    """Return required import metadata or fail before export"""
    try:
        if key in root:
            return root[key]
    except (AttributeError, ReferenceError, TypeError) as error:
        _LOG.debug("Source metadata %s unreadable: %s", key, error)
    raise ValueError(f"missing required source metadata: {key}; reimport the animgraph")


def _source_root_output_spec(root: bpy.types.NodeTree) -> dict[str, Any]:
    _require_source_metadata(root, "red_root_output_json")
    spec = _json_idprop(root, "red_root_output_json", None)
    if not isinstance(spec, dict):
        raise ValueError("invalid required source metadata: red_root_output_json")
    return spec


def _root_output_link(root: bpy.types.NodeTree) -> dict[str, Any]:
    """Encode Root.outputNode from stored source metadata"""
    spec = _source_root_output_spec(root)
    link_type = str(spec.get("link_type") or "animPoseLink")
    if not spec.get("present"):
        return {"$type": link_type, "node": None}

    handle = str(spec.get("handle") or "")
    wrapper = {"$type": link_type}
    wrapper["node"] = {"HandleRefId": handle} if handle else None
    return wrapper


def _source_ordered_root_entries(
    root: bpy.types.NodeTree, entries: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return root.Data.nodes in imported membership order"""
    available_handles = {
        str(value["HandleId"])
        for value in nested_values(entries)
        if isinstance(value, dict) and "HandleId" in value
    }
    by_handle: dict[str, dict[str, Any]] = {}
    encoded_order: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        handle = str(entry.get("HandleId", "") or "")
        if not handle:
            continue
        by_handle[handle] = entry
        encoded_order.append(handle)

    _require_source_metadata(root, "red_root_nodes_order_json")
    specs_raw = _json_idprop(root, "red_root_nodes_order_json", None)
    if not isinstance(specs_raw, list):
        raise ValueError("invalid required source metadata: red_root_nodes_order_json")
    specs = specs_raw
    out: list[dict[str, Any]] = []
    used: set = set()
    missing: list[str] = []
    malformed = 0

    for spec in specs:
        if isinstance(spec, dict):
            handle = str(
                spec.get("handle", "")
                or spec.get("HandleId", "")
                or spec.get("HandleRefId", "")
                or ""
            )
            inline = bool(spec.get("inline", False))
        else:
            handle = str(spec or "")
            inline = False
        if not handle:
            malformed += 1
            continue
        if handle not in available_handles:
            missing.append(handle)
            continue
        if handle in used:
            out.append({"HandleRefId": handle})
            continue
        used.add(handle)
        source = by_handle.get(handle)
        if inline and source is not None:
            out.append(clone_json(source))
        else:
            if source is None:
                missing.append(handle)
            out.append({"HandleRefId": handle})

    source_known_handles: set = set()
    if specs:
        for spec in specs:
            if isinstance(spec, dict):
                h = str(
                    spec.get("handle", "")
                    or spec.get("HandleId", "")
                    or spec.get("HandleRefId", "")
                    or ""
                )
            else:
                h = str(spec or "")
            if h:
                source_known_handles.add(h)
        refs_raw = _json_idprop(root, "red_nodes_to_init_refs_json", [])
        if isinstance(refs_raw, list):
            source_known_handles.update(str(value) for value in refs_raw if value)
        source_known_handles.add(_root_handle(root))

    appended: list[str] = []
    for handle in encoded_order:
        if handle in used:
            continue

        if specs and handle in source_known_handles:
            continue
        appended.append(handle)
        used.add(handle)
        out.append(clone_json(by_handle[handle]))

    meta = {
        "sourceOrderEntries": len(specs),
        "emittedEntries": len(out),
        "fullEntries": sum(
            1 for item in out if isinstance(item, dict) and item.get("HandleId")
        ),
        "refEntries": sum(
            1 for item in out if isinstance(item, dict) and item.get("HandleRefId")
        ),
        "missingSourceHandles": missing,
        "appendedNewHandles": appended,
        "malformedSourceOrderSpecs": malformed,
        "usedSourceOrder": bool(specs),
    }
    return out, meta


def _default_root_chunk_scalars(
    entries: list[dict[str, Any]], root: bpy.types.NodeTree
) -> dict[str, Any]:
    has_mixer_slot = any(
        isinstance(entry.get("Data"), dict)
        and entry["Data"].get("$type") == f"{ANIM_NODE_PREFIX}MixerSlot"
        for entry in entries
    )
    data = {
        "$type": "animAnimGraph",
        "additionalAnimDatabases": [],
        "animFeatures": [],
        "cookingPlatform": "PLATFORM_None",
        "hackAlwaysSample": 0,
        "hasMixerSlot": int(has_mixer_slot),
        "isPaused": 0,
        "jsonFilesDirectory": "",
        "nodesToInit": [],
        "oneFrameToggle": 0,
        "staticCommandsRig": {"DepotPath": _schema_resource_path(), "Flags": "Default"},
        "timeDeltaMultiplier": 1,
        "useAnimCommands": 0,
        "useAnimCommandsForCrowd": 0,
        "useAnimStaticCommands": 0,
        "useLunaticMode": 0,
    }
    _require_source_metadata(root, "red_rootchunk_scalars_json")
    scalars = _json_idprop(root, "red_rootchunk_scalars_json", None)
    if not isinstance(scalars, dict):
        raise ValueError("invalid required source metadata: red_rootchunk_scalars_json")
    for key, value in scalars.items():
        if (
            key == "$type"
            or key == "nodesToInit"
            or key == "rootNode"
            or key == "variables"
        ):
            continue
        data[key] = value
    data["$type"] = "animAnimGraph"
    return data


def _root_handle(root: bpy.types.NodeTree) -> str:
    handle = str(get_idprop(root, "red_root_handle", "") or "")
    if not handle:
        handle = str(get_idprop(root, "red_nodes_to_init_root_handle", "") or "")
    return handle or "0"


def encode_root_node(
    root: bpy.types.NodeTree, entries: list[dict[str, Any]]
) -> dict[str, Any]:
    root_handle = _root_handle(root)
    _require_source_metadata(root, "red_root_data_fields_json")
    root_fields = _json_idprop(root, "red_root_data_fields_json", None)
    if not isinstance(root_fields, dict):
        raise ValueError("invalid required source metadata: red_root_data_fields_json")
    root_data = dict(root_fields)
    root_data["$type"] = f"{ANIM_NODE_PREFIX}Root"
    ordered_entries, _ = _source_ordered_root_entries(root, entries)
    root_data["nodes"] = ordered_entries
    root_data["outputNode"] = _root_output_link(root)
    return {"HandleId": root_handle, "Data": root_data}


def encode_nodes_to_init(
    root_entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index = handle_index(root_entry)
    handles = initialization_handles(root_entry, index)
    root_handle = str(root_entry["HandleId"])
    nodes = [
        root_entry if handle == root_handle else {"HandleRefId": handle}
        for handle in handles
    ]
    return nodes, {"totalEntries": len(nodes), "fullRootEntries": 1}


def encode_rootchunk_payload(tree: bpy.types.NodeTree) -> dict[str, Any]:
    """Encode the public root node tree as a WolvenKit RootChunk"""
    root = root_tree(tree) or tree
    if root is None or getattr(root, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        raise ValueError("active editor tree is not a REDengine animGraph tree")

    take_unlisted_entries()
    with indexed_socket_links():
        entries = _encode_tree_runtime_entries(
            root, embed_containers=True, _stack=set()
        )
        root_entry = encode_root_node(root, entries)
    ref_style = normalize_inline_first_references(
        root_entry, entries + take_unlisted_entries()
    )
    root_entry = ref_style.get("root") or root_entry

    root_chunk = _default_root_chunk_scalars(entries, root)
    root_chunk["animFeatures"] = encode_anim_features(root)
    if "red_nodes_to_init_count" in root and not int(
        get_idprop(root, "red_nodes_to_init_count", 0) or 0
    ):
        # A source graph without nodesToInit writes its root node in place.
        root_chunk["nodesToInit"] = []
        root_chunk["rootNode"] = root_entry
    else:
        root_chunk["nodesToInit"], _ = encode_nodes_to_init(root_entry)
        root_chunk["rootNode"] = {
            "HandleRefId": str(root_entry.get("HandleId", "") or _root_handle(root))
        }
    root_chunk["variables"] = encode_root_variables(root)
    return root_chunk


def _bools_as_ints(root: Any) -> Any:
    """WolvenKit writes and reads CBool as 0 or 1"""
    stack = [root]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if value is True or value is False:
                    current[key] = int(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            for index, value in enumerate(current):
                if value is True or value is False:
                    current[index] = int(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
    return root


def encode_wolvenkit_json(tree: bpy.types.NodeTree) -> dict[str, Any]:
    root = root_tree(tree) or tree
    with unresolved_default_collector() as unresolved:
        root_chunk = encode_rootchunk_payload(root)
    if unresolved:
        _LOG.warning(
            "AnimGraph export wrote null for %d field(s) whose schema default could not be resolved; first: %s",
            len(unresolved),
            "; ".join(unresolved[:3]),
        )
    finalize_new_handles(root_chunk)
    archive_name = str(getattr(root, "name", "") or "animgraph")
    if not archive_name.endswith(".animgraph") and not archive_name.endswith(
        ".animgraph.json"
    ):
        archive_name = f"{archive_name}.animgraph"

    source_header = decode_optional(get_idprop(root, "red_source_header_json", ""), {})
    header = dict(source_header) if isinstance(source_header, dict) else {}
    header.setdefault("WolvenKitVersion", SUPPORTED_WOLVENKIT_VERSION)
    header.setdefault("WKitJsonVersion", SUPPORTED_WKIT_JSON_VERSION)
    header.setdefault("GameVersion", SUPPORTED_GAME_VERSION)
    header["ExportedDateTime"] = utc_timestamp()
    header["DataType"] = "CR2W"
    header.setdefault("ArchiveFileName", archive_name)

    source_data = decode_optional(get_idprop(root, "red_source_data_meta_json", ""), {})
    data = dict(source_data) if isinstance(source_data, dict) else {}
    data.setdefault("Version", 195)
    data.setdefault("BuildVersion", 0)
    data.setdefault("EmbeddedFiles", [])
    data["RootChunk"] = _bools_as_ints(root_chunk)
    payload = {"Header": header, "Data": data}
    validation = validate_payload(payload)
    if validation["errors"]:
        raise ValueError("; ".join(validation["errors"]))
    return payload


def encode_rootchunk_summary(payload: dict[str, Any]) -> dict[str, Any]:
    root_chunk = (
        (((payload or {}).get("Data") or {}).get("RootChunk") or {})
        if isinstance(payload, dict)
        else {}
    )
    nodes_to_init = (
        root_chunk.get("nodesToInit") if isinstance(root_chunk, dict) else []
    )
    nodes_to_init = nodes_to_init if isinstance(nodes_to_init, list) else []
    root_ref = root_chunk.get("rootNode") if isinstance(root_chunk, dict) else {}
    root_handle = ""
    if isinstance(root_ref, dict):
        root_handle = str(
            root_ref.get("HandleRefId", "") or root_ref.get("HandleId", "") or ""
        )
    root_entry = (
        nodes_to_init[0] if nodes_to_init and isinstance(nodes_to_init[0], dict) else {}
    )
    root_data = (
        root_entry.get("Data")
        if isinstance(root_entry, dict) and isinstance(root_entry.get("Data"), dict)
        else {}
    )
    nodes = root_data.get("nodes") if isinstance(root_data, dict) else []
    variables = root_chunk.get("variables") if isinstance(root_chunk, dict) else {}
    variable_data = variables.get("Data") if isinstance(variables, dict) else {}
    variable_count = 0
    if isinstance(variable_data, dict):
        for key in (
            "boolVariables",
            "floatVariables",
            "intVariables",
            "quaternionVariables",
            "transformVariables",
            "vectorVariables",
        ):
            values = variable_data.get(key)
            if isinstance(values, list):
                variable_count += len(values)
    root_output = (
        (root_data.get("outputNode") or {}) if isinstance(root_data, dict) else {}
    )
    output_ref = ""
    if isinstance(root_output, dict) and isinstance(root_output.get("node"), dict):
        output_ref = str(
            root_output["node"].get("HandleRefId", "")
            or root_output["node"].get("HandleId", "")
            or ""
        )
    root_node_full = (
        sum(1 for item in nodes if isinstance(item, dict) and item.get("HandleId"))
        if isinstance(nodes, list)
        else 0
    )
    root_node_refs = (
        sum(1 for item in nodes if isinstance(item, dict) and item.get("HandleRefId"))
        if isinstance(nodes, list)
        else 0
    )
    return {
        "rootHandle": root_handle or str(root_entry.get("HandleId", "") or "")
        if isinstance(root_entry, dict)
        else root_handle,
        "rootOutputRef": output_ref,
        "rootNodes": len(nodes) if isinstance(nodes, list) else 0,
        "rootNodeFullEntries": root_node_full,
        "rootNodeRefEntries": root_node_refs,
        "variables": variable_count,
        "animFeatures": len(root_chunk.get("animFeatures") or [])
        if isinstance(root_chunk, dict)
        else 0,
        "nodesToInit": len(nodes_to_init),
        "nodesToInitRefs": max(0, len(nodes_to_init) - 1),
    }


def write_graph_document(path: str, tree: bpy.types.NodeTree) -> str:
    """Write the graph tree belongs to as a WolvenKit AnimGraph document at path, returning the text written"""
    from ...blender.animgraph.rig_binding import binding_tree

    return write_json(path, encode_wolvenkit_json(binding_tree(tree)))
