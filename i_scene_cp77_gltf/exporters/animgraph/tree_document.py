from typing import Any

import bpy

from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...blender.animgraph.access import get_attr, get_idprop
from ...core.log import debug_exception, get_logger
from .nodes import _runtime_node, encode_runtime_node_entry
from .tree_state import node_sort_key, root_tree, tree_nodes

_LOG = get_logger(__name__)


def _tree_bool(tree: Any, key: str) -> bool:
    return bool(get_idprop(tree, key, False))


def _is_editor_projection_node(node: Any) -> bool:
    if _runtime_node(node):
        return False
    red_type = str(get_attr(node, "red_type", "") or "")
    handle = str(get_attr(node, "red_handle_id", "") or "")
    if red_type or handle:
        return True
    if bool(get_attr(node, "red_pseudo", False)):
        return True

    return True


def _collect_tree_link_references(
    entries: list[dict[str, Any]], local_handles: set
) -> tuple[list[dict[str, str]], int]:
    refs: list[dict[str, str]] = []
    local_count = 0
    for entry in entries:
        owner_handle = str(entry.get("HandleId", "") or "")
        stack = [(entry.get("Data"), "Data")]
        while stack:
            value, path = stack.pop()
            if isinstance(value, dict):
                node_ref = value.get("node")
                if isinstance(node_ref, dict):
                    ref = str(
                        node_ref.get("HandleRefId", "")
                        or node_ref.get("HandleId", "")
                        or ""
                    )
                    if ref:
                        if ref in local_handles:
                            local_count += 1
                        else:
                            refs.append(
                                {"owner": owner_handle, "path": path, "target": ref}
                            )
                items = tuple(value.items())
                for key, child in reversed(items):
                    child_path = f"{path}.{key}" if path else str(key)
                    stack.append((child, child_path))
            elif isinstance(value, list):
                for index in range(len(value) - 1, -1, -1):
                    stack.append((value[index], f"{path}[{index}]"))
    return refs, local_count


def encode_active_tree(tree: bpy.types.NodeTree) -> dict[str, Any]:
    if tree is None or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        raise ValueError("active editor tree is not a REDengine animGraph tree")

    all_nodes = tree_nodes(tree)
    runtime_nodes = [node for node in all_nodes if _runtime_node(node)]
    skipped_nodes = [
        node
        for node in all_nodes
        if node not in runtime_nodes and _is_editor_projection_node(node)
    ]
    runtime_nodes.sort(key=node_sort_key)

    entries: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}

    for node in runtime_nodes:
        handle = str(get_attr(node, "red_handle_id", "") or "")
        if not handle:
            blockers.append(f"{getattr(node, 'name', '<node>')}: missing red_handle_id")
            continue
        if handle in seen:
            blockers.append(
                f"duplicate HandleId {handle}: {seen[handle]} and {getattr(node, 'name', '<node>')}"
            )
            continue
        seen[handle] = str(getattr(node, "name", "<node>"))
        try:
            entries.append(encode_runtime_node_entry(node, embed_containers=False))
        except Exception as exc:
            debug_exception(_LOG, "Could not encode node %s of the active tree", handle)
            blockers.append(f"{handle} {getattr(node, 'name', '<node>')}: {exc}")

    local_handles = {
        str(entry.get("HandleId", "")) for entry in entries if entry.get("HandleId")
    }
    external_refs, local_ref_count = _collect_tree_link_references(
        entries, local_handles
    )
    if external_refs:
        warnings.append(
            f"{len(external_refs)} encoded HandleRefId reference(s) target nodes outside the active tree"
        )

    root = root_tree(tree) or tree
    summary = {
        "runtimeNodes": len(runtime_nodes),
        "encodedNodes": len(entries),
        "editorSkipped": len(skipped_nodes),
        "localHandleRefs": local_ref_count,
        "externalHandleRefs": len(external_refs),
        "blockers": len(blockers),
        "warnings": len(warnings),
        "ready": len(blockers) == 0,
    }
    return {
        "tree": str(getattr(tree, "name", "<tree>")),
        "rootTree": str(getattr(root, "name", "<root>")),
        "internalSubgraph": _tree_bool(tree, "red_internal_subgraph"),
        "editorSubgraph": _tree_bool(tree, "red_editor_subgraph"),
        "ordering": "diagnostic numeric HandleId order; not final RootChunk/nodesToInit order",
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "externalReferences": external_refs,
        "nodes": entries,
    }
