from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

import bpy

from ....animation.domain.animgraph.policy import attach_runtime_context
from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....animation.services.animgraph.repository import AnimGraphRepository
from ....blender.animgraph.preview_settings import copy_graph_settings
from ....blender.animgraph.validation import roundtrip as roundtrip_audit
from ....blender.transactions import track_created_datablock
from ....core.log import debug_exception, get_logger
from ....exporters.animgraph.dangle_patch import (
    AnimGraphPatchError,
    dumps_pretty,
    patch_wolvenkit_payload,
    strip_private_export_metadata,
    validate_payload,
    write_json,
)
from ....exporters.animgraph.root import encode_wolvenkit_json
from ....importers.animgraph.graph_import import build_graph_tree
from ...blender.dangle_source import decode_graph_json, load_source_payload, source_text
from ...runtime.dangle.editor_state import import_chains_data

_LOG = get_logger(__name__)


_SOURCE_TEXT_PREFIX = ".CP77_AnimGraph_Source_"
_AUTO_SYNC_DEPTH = 0
_PENDING_GRAPH_SYNCS = {}
_TOPOLOGY_SIGNATURE_KEY = "cp77_dangle_topology_signature"


@contextmanager
def _suspend_auto_sync():
    global _AUTO_SYNC_DEPTH
    _AUTO_SYNC_DEPTH += 1
    try:
        yield
    finally:
        _AUTO_SYNC_DEPTH = max(0, _AUTO_SYNC_DEPTH - 1)


def _node_identity(node):
    return (
        str(getattr(node, "red_handle_id", "") or node.name),
        str(getattr(node, "red_type", "") or getattr(node, "bl_idname", "")),
    )


def _socket_identity(socket):
    return str(getattr(socket, "identifier", "") or getattr(socket, "name", ""))


def graph_topology_signature(tree) -> str:
    nodes = sorted(_node_identity(node) for node in tree.nodes)
    links = sorted(
        (
            *_node_identity(link.from_node),
            _socket_identity(link.from_socket),
            *_node_identity(link.to_node),
            _socket_identity(link.to_socket),
        )
        for link in tree.links
    )
    return repr((tuple(nodes), tuple(links)))


def _root_tree_for(tree):
    if tree is None:
        return None
    parent_name = str(tree.get("red_parent_graph", "") or "")
    if parent_name:
        parent = bpy.data.node_groups.get(parent_name)
        if parent is not None:
            return parent
    return tree


def _record_topology_snapshot(root_tree):
    if root_tree is None:
        return
    root_name = root_tree.name
    for tree in _related_animgraph_trees(root_name):
        try:
            tree[_TOPOLOGY_SIGNATURE_KEY] = graph_topology_signature(tree)
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            continue


def cancel_pending_graph_syncs():
    for callback in tuple(_PENDING_GRAPH_SYNCS.values()):
        try:
            if bpy.app.timers.is_registered(callback):
                bpy.app.timers.unregister(callback)
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            pass
    _PENDING_GRAPH_SYNCS.clear()


def notify_graph_tree_changed(tree):
    if _AUTO_SYNC_DEPTH or tree is None:
        return
    root = _root_tree_for(tree)
    if root is None:
        return
    rig_name = str(root.get("cp77_dangle_rig", "") or "")
    if not rig_name:
        return
    try:
        signature = graph_topology_signature(tree)
    except (ReferenceError, RuntimeError, TypeError, ValueError):
        return
    if str(tree.get(_TOPOLOGY_SIGNATURE_KEY, "")) == signature:
        return
    tree[_TOPOLOGY_SIGNATURE_KEY] = signature
    root_name = root.name
    if root_name in _PENDING_GRAPH_SYNCS:
        return

    def _sync_pending():
        current_root = bpy.data.node_groups.get(root_name)
        if current_root is None:
            _PENDING_GRAPH_SYNCS.pop(root_name, None)
            return None
        current_rig_name = str(current_root.get("cp77_dangle_rig", "") or "")
        rig = bpy.data.objects.get(current_rig_name) if current_rig_name else None
        if rig is None:
            _PENDING_GRAPH_SYNCS.pop(root_name, None)
            return None
        if getattr(rig.dangle_state, "is_playing", False):
            return 0.1
        try:
            with _suspend_auto_sync():
                sync_graph_to_editor(rig)
        except Exception as exc:
            _LOG.warning(
                "Automatic Graph View -> Dangle Editor sync failed: %s",
                exc,
                exc_info=True,
            )
        finally:
            _PENDING_GRAPH_SYNCS.pop(root_name, None)
        return None

    _PENDING_GRAPH_SYNCS[root_name] = _sync_pending
    try:
        bpy.app.timers.register(_sync_pending, first_interval=0.05)
    except Exception:
        _PENDING_GRAPH_SYNCS.pop(root_name, None)
        raise


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(value or ""))


def _source_text_name(rig: bpy.types.Object) -> str:
    return f"{_SOURCE_TEXT_PREFIX}{_safe_name(rig.name)}"


def _related_animgraph_trees(root_name: str) -> list[bpy.types.NodeTree]:
    related = []
    for tree in bpy.data.node_groups:
        if getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
            continue
        if tree.name == root_name or str(tree.get("red_parent_graph", "")) == root_name:
            related.append(tree)
    return related


def _remove_animgraph_tree(root_name: str) -> None:
    if not root_name:
        return
    related = _related_animgraph_trees(root_name)
    # Remove child graphs before the root.
    related.sort(key=lambda tree: tree.name == root_name)
    for tree in related:
        try:
            bpy.data.node_groups.remove(tree, do_unlink=True)
        except Exception:
            debug_exception(_LOG, "Could not remove the AnimGraph tree")


def store_source_text(
    rig: bpy.types.Object, raw_text: str, filepath: str
) -> bpy.types.Text:
    name = str(getattr(rig.dangle_state, "animgraph_source_text", "") or "")
    text = bpy.data.texts.get(name) if name else None
    if text is None:
        base = _source_text_name(rig)
        text = bpy.data.texts.get(base) or track_created_datablock(
            "texts", bpy.data.texts.new(base)
        )
    text.clear()
    text.write(str(raw_text or ""))
    rig.dangle_state.animgraph_source_text = text.name
    rig.dangle_state.animgraph_source_path = str(filepath or "")
    return text


def _exception_summary(exc: BaseException) -> str:
    message = str(exc).strip()
    if not message or message == "None":
        message = repr(exc)
    return f"{type(exc).__name__}: {message}"


def create_graph_tree(
    payload: dict,
    filepath: str,
    rig: bpy.types.Object,
    context: bpy.types.Context | None = None,
) -> bpy.types.NodeTree:
    old_name = str(getattr(rig.dangle_state, "animgraph_tree_name", "") or "")
    with _suspend_auto_sync():
        tree = build_graph_tree(payload, filepath, rig, context)
        tree["cp77_dangle_rig"] = rig.name
    # The graph names the rig's source text too, so the graph tools read the same document the dangle editor patches.
    text = source_text(rig)
    if text is not None:
        tree.red_source_text = text.name
        tree.red_source_path = str(rig.dangle_state.animgraph_source_path or "")

    if old_name and old_name != tree.name:
        old = bpy.data.node_groups.get(old_name)
        if getattr(old, "bl_idname", "") == ANIMGRAPH_TREE_ID:
            # The new tree is the same graph: its preview settings and rig part carry over.
            copy_graph_settings(old, tree)
            tree.red_rig_part = old.red_rig_part
        _remove_animgraph_tree(old_name)
    rig.dangle_state.animgraph_tree_name = tree.name
    _record_topology_snapshot(tree)
    return tree


def import_into_both_editors(
    filepath: str,
    rig: bpy.types.Object,
    context: bpy.types.Context | None = None,
) -> tuple[int, bpy.types.NodeTree | None, str]:
    document = AnimGraphRepository().load(filepath)
    payload, raw_text = document.payload, document.source_text
    count = import_chains_data(payload, rig.dangle_state)
    store_source_text(rig, raw_text, filepath)
    try:
        tree = create_graph_tree(payload, filepath, rig, context)
        return count, tree, ""
    except Exception as exc:
        rig.dangle_state.animgraph_tree_name = ""
        _LOG.warning(
            "AnimGraph view construction failed; dangle chains were imported without Graph View",
            exc_info=True,
        )
        return count, None, _exception_summary(exc)


def _state_bone_names(state: Any) -> Iterable[str]:
    for dnode in getattr(state, "dangle_nodes", ()):
        for shape in getattr(dnode, "collision_shapes", ()):
            if shape.bone_name:
                yield shape.bone_name
        for chain in getattr(dnode, "chains", ()):
            for particle in getattr(chain, "particles", ()):
                if particle.bone_name:
                    yield particle.bone_name
                if particle.direction_reference_bone:
                    yield particle.direction_reference_bone
                for link in particle.link_constraints:
                    if link.target_bone:
                        yield link.target_bone
                for ellipsoid in particle.ellipsoid_constraints:
                    if ellipsoid.target_bone:
                        yield ellipsoid.target_bone
                for cone in particle.pendulum_constraints:
                    if cone.target_bone:
                        yield cone.target_bone
    for drag in getattr(state, "drag_nodes", ()):
        if drag.source_bone_name:
            yield drag.source_bone_name
        if drag.bone_name:
            yield drag.bone_name


def validate_state_against_rig(rig: bpy.types.Object) -> list[str]:
    bones = getattr(getattr(rig, "data", None), "bones", None)
    if bones is None:
        return ["Active Dangle target is not an armature"]
    missing = []
    seen = set()
    for name in _state_bone_names(rig.dangle_state):
        if name in seen:
            continue
        seen.add(name)
        if bones.get(name) is None:
            missing.append(name)
    return missing


def validate_imported_document(rig: bpy.types.Object) -> dict:
    payload = load_source_payload(rig)
    report = validate_payload(payload)
    missing = validate_state_against_rig(rig)
    editor_audit = None
    editor_audit_error = ""
    tree = bpy.data.node_groups.get(str(rig.dangle_state.animgraph_tree_name or ""))
    if tree is not None and getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID:
        try:
            editor_audit = roundtrip_audit.report_for_tree(tree)
        except Exception as exc:
            debug_exception(
                _LOG, "The editor round-trip audit of the imported AnimGraph failed"
            )
            editor_audit_error = str(exc)
    return attach_runtime_context(
        report,
        missing_bones=missing,
        editor_audit=editor_audit,
        editor_audit_error=editor_audit_error,
    )


def export_from_specialist_editor(
    filepath: str,
    rig: bpy.types.Object,
    context: bpy.types.Context | None = None,
) -> dict:
    missing = validate_state_against_rig(rig)
    payload = load_source_payload(rig)
    patch_wolvenkit_payload(
        payload,
        rig.dangle_state,
        export_path=filepath,
    )
    report = validate_payload(payload)
    if not report.get("ready"):
        raise AnimGraphPatchError("; ".join(report.get("errors", ())))
    attach_runtime_context(report, missing_bones=missing)

    raw_text = write_json(filepath, payload)
    clean_payload = decode_graph_json(raw_text)
    import_chains_data(clean_payload, rig.dangle_state)
    store_source_text(rig, raw_text, filepath)
    rig.dangle_state.animgraph_last_export_path = filepath
    # Specialist export replaces pending graph edits.
    try:
        create_graph_tree(clean_payload, filepath, rig, context)
    except Exception as exc:
        debug_exception(_LOG, "Could not refresh the AnimGraph editor after the export")
        report["editorRefreshError"] = str(exc)
    return report


def sync_editor_to_graph(
    rig: bpy.types.Object,
    context: bpy.types.Context | None = None,
    *,
    removed_handles: Iterable[str] = (),
) -> bpy.types.NodeTree:
    payload = load_source_payload(rig)
    patch_wolvenkit_payload(
        payload,
        rig.dangle_state,
        update_header=False,
        removed_handles=removed_handles,
    )
    report = validate_payload(payload)
    if not report.get("ready"):
        raise AnimGraphPatchError("; ".join(report.get("errors", ())))
    clean = strip_private_export_metadata(payload)
    raw_text = dumps_pretty(clean)
    store_source_text(rig, raw_text, rig.dangle_state.animgraph_source_path)
    with _suspend_auto_sync():
        import_chains_data(clean, rig.dangle_state)
        tree = create_graph_tree(
            clean,
            rig.dangle_state.animgraph_source_path,
            rig,
            context,
        )
    area = getattr(context, "area", None) if context is not None else None
    space = getattr(area, "spaces", None) if area is not None else None
    active_space = getattr(space, "active", None) if space is not None else None
    if area is not None and area.type == "NODE_EDITOR" and active_space is not None:
        try:
            active_space.tree_type = ANIMGRAPH_TREE_ID
            active_space.pin = True
            active_space.node_tree = tree
        except Exception:
            debug_exception(_LOG, "Could not show the AnimGraph in the node editor")
    return tree


def sync_graph_to_editor(
    rig: bpy.types.Object,
) -> tuple[int, dict]:
    tree = bpy.data.node_groups.get(str(rig.dangle_state.animgraph_tree_name or ""))
    if tree is None or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        raise AnimGraphPatchError("No synchronized AnimGraph tree exists for this rig")
    payload = encode_wolvenkit_json(tree)
    report = validate_payload(payload)
    if not report.get("ready"):
        raise AnimGraphPatchError("; ".join(report.get("errors", ())))
    with _suspend_auto_sync():
        count = import_chains_data(payload, rig.dangle_state)
        raw_text = dumps_pretty(payload)
        store_source_text(rig, raw_text, rig.dangle_state.animgraph_source_path)
        _record_topology_snapshot(tree)
    return count, report
