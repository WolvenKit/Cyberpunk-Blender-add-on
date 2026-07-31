from __future__ import annotations
from ...blender.transactions import track_created_datablock

import os
from typing import Any, Iterable, Optional

import bpy

from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID
from ...importers.animgraph import AnimGraphParser
from ...exporters.animgraph import encode_wolvenkit_json
from ...blender.animgraph.validation import roundtrip as roundtrip_audit
from ...assetio import animgraph_json as json_io
from .animgraph_codec import (
    AnimGraphPatchError,
    dumps_pretty,
    patch_wolvenkit_payload,
    strip_private_export_metadata,
    validate_payload,
    write_json,
)
from .io import import_chains_data


_SOURCE_TEXT_PREFIX = ".CP77_AnimGraph_Source_"

# Return state is keyed by Blender area pointer.
_VIEW_RETURN_STATE: dict[int, dict[str, Any]] = {}


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
            pass


def store_source_text(rig: bpy.types.Object, raw_text: str, filepath: str) -> bpy.types.Text:
    name = str(getattr(rig.dangle_state, "animgraph_source_text", "") or "")
    text = bpy.data.texts.get(name) if name else None
    if text is None:
        base = _source_text_name(rig)
        text = bpy.data.texts.get(base) or track_created_datablock("texts", bpy.data.texts.new(base))
    text.clear()
    text.write(str(raw_text or ""))
    rig.dangle_state.animgraph_source_text = text.name
    rig.dangle_state.animgraph_source_path = str(filepath or "")
    return text


def source_text(rig: bpy.types.Object) -> Optional[bpy.types.Text]:
    name = str(getattr(rig.dangle_state, "animgraph_source_text", "") or "")
    return bpy.data.texts.get(name) if name else None


def _decode_json_text(raw: str) -> dict:
    value = json_io.loads(raw)
    if not isinstance(value, dict):
        raise AnimGraphPatchError("AnimGraph JSON root must be an object")
    return value

def load_source_payload(rig: bpy.types.Object) -> dict:
    text = source_text(rig)
    if text is None:
        raise AnimGraphPatchError(
            "This Dangle rig has no imported AnimGraph source document. Import a .animgraph.json first."
        )
    raw = text.as_string()
    try:
        return _decode_json_text(raw)
    except Exception as exc:
        raise AnimGraphPatchError(f"Stored AnimGraph source JSON is invalid: {exc}") from exc


def _tree_name_for_path(filepath: str, rig: bpy.types.Object) -> str:
    filename = os.path.basename(filepath or "")
    if filename.lower().endswith(".json"):
        filename = filename[:-5]
    return filename or f"{rig.name}_animgraph"


def create_graph_tree(
    payload: dict,
    filepath: str,
    rig: bpy.types.Object,
    context: Optional[bpy.types.Context] = None,
) -> bpy.types.NodeTree:
    old_name = str(getattr(rig.dangle_state, "animgraph_tree_name", "") or "")
    tree = track_created_datablock("node_groups", bpy.data.node_groups.new(
        name=_tree_name_for_path(filepath, rig),
        type=ANIMGRAPH_TREE_ID,
    ))
    try:
        parser = AnimGraphParser(tree)
        parser.execute(payload, context)
        tree["cp77_dangle_rig"] = rig.name
        tree["cp77_source_filepath"] = str(filepath or "")
    except Exception:
        try:
            bpy.data.node_groups.remove(tree, do_unlink=True)
        except Exception:
            pass
        raise

    if old_name and old_name != tree.name:
        _remove_animgraph_tree(old_name)
    rig.dangle_state.animgraph_tree_name = tree.name
    return tree


def import_into_both_editors(
    filepath: str,
    rig: bpy.types.Object,
    context: Optional[bpy.types.Context] = None,
) -> tuple[int, Optional[bpy.types.NodeTree], str]:
    with open(filepath, "r", encoding="utf-8-sig") as stream:
        raw_text = stream.read()
    payload = _decode_json_text(raw_text)
    count = import_chains_data(payload, rig.dangle_state)
    store_source_text(rig, raw_text, filepath)
    try:
        tree = create_graph_tree(payload, filepath, rig, context)
        return count, tree, ""
    except Exception as exc:
        rig.dangle_state.animgraph_tree_name = ""
        return count, None, str(exc)


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
    report["missingBones"] = missing
    if missing:
        report["ready"] = False
        report["errors"] = list(report.get("errors", ())) + [
            f"Rig is missing {len(missing)} referenced bone(s): {', '.join(missing[:12])}"
        ]
    tree = bpy.data.node_groups.get(str(rig.dangle_state.animgraph_tree_name or ""))
    if tree is not None and getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID:
        try:
            report["fullEditorAudit"] = roundtrip_audit.report_for_tree(tree)
        except Exception as exc:
            report["fullEditorAuditError"] = str(exc)
    return report


def export_from_specialist_editor(
    filepath: str,
    rig: bpy.types.Object,
    context: Optional[bpy.types.Context] = None,
) -> dict:
    missing = validate_state_against_rig(rig)
    if missing:
        raise AnimGraphPatchError(
            f"Rig is missing {len(missing)} referenced bone(s): {', '.join(missing[:12])}"
        )

    payload = load_source_payload(rig)
    patch_wolvenkit_payload(
        payload,
        rig.dangle_state,
        export_path=filepath,
    )
    report = validate_payload(payload)
    if not report.get("ready"):
        raise AnimGraphPatchError("; ".join(report.get("errors", ())))

    write_json(filepath, payload)
    with open(filepath, "r", encoding="utf-8") as stream:
        raw_text = stream.read()
    clean_payload = _decode_json_text(raw_text)
    store_source_text(rig, raw_text, filepath)
    rig.dangle_state.animgraph_last_export_path = filepath
    # Specialist export replaces pending graph edits.
    try:
        create_graph_tree(clean_payload, filepath, rig, context)
    except Exception as exc:
        report["editorRefreshError"] = str(exc)
    return report


def sync_editor_to_graph(
    rig: bpy.types.Object,
    context: Optional[bpy.types.Context] = None,
) -> bpy.types.NodeTree:
    payload = load_source_payload(rig)
    patch_wolvenkit_payload(
        payload,
        rig.dangle_state,
        update_header=False,
    )
    report = validate_payload(payload)
    if not report.get("ready"):
        raise AnimGraphPatchError("; ".join(report.get("errors", ())))
    clean = strip_private_export_metadata(payload)
    raw_text = dumps_pretty(clean)
    store_source_text(rig, raw_text, rig.dangle_state.animgraph_source_path)
    tree = create_graph_tree(
        clean,
        rig.dangle_state.animgraph_source_path,
        rig,
        context,
    )
    area = getattr(context, "area", None) if context is not None else None
    space = getattr(area, "spaces", None) if area is not None else None
    active_space = getattr(space, "active", None) if space is not None else None
    if area is not None and area.type == 'NODE_EDITOR' and active_space is not None:
        try:
            active_space.tree_type = ANIMGRAPH_TREE_ID
            active_space.pin = True
            active_space.node_tree = tree
        except Exception:
            pass
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
    count = import_chains_data(payload, rig.dangle_state)
    raw_text = dumps_pretty(payload)
    store_source_text(rig, raw_text, rig.dangle_state.animgraph_source_path)
    return count, report


def root_graph_tree(tree: Optional[bpy.types.NodeTree]) -> Optional[bpy.types.NodeTree]:
    current = tree
    visited: set[int] = set()
    while current is not None:
        try:
            pointer = int(current.as_pointer())
        except Exception:
            pointer = id(current)
        if pointer in visited:
            break
        visited.add(pointer)
        parent_name = str(current.get("red_parent_graph", "") or "")
        if not parent_name:
            break
        parent = bpy.data.node_groups.get(parent_name)
        if parent is None:
            break
        current = parent
    return current


def rig_for_graph_tree(tree: Optional[bpy.types.NodeTree]) -> Optional[bpy.types.Object]:
    root = root_graph_tree(tree)
    if root is None or getattr(root, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        return None
    rig_name = str(root.get("cp77_dangle_rig", "") or "")
    rig = bpy.data.objects.get(rig_name) if rig_name else None
    if rig is None or getattr(rig, "type", "") != 'ARMATURE':
        return None
    return rig


def rig_for_context(context: bpy.types.Context) -> Optional[bpy.types.Object]:
    space = getattr(context, "space_data", None)
    tree = getattr(space, "node_tree", None) if space is not None else None
    return rig_for_graph_tree(tree)


def _area_key(area: Optional[bpy.types.Area]) -> Optional[int]:
    if area is None:
        return None
    try:
        return int(area.as_pointer())
    except Exception:
        return None


def can_return_to_editor(context: bpy.types.Context) -> bool:
    key = _area_key(getattr(context, "area", None))
    return key is not None and key in _VIEW_RETURN_STATE


def clear_view_return_states() -> None:
    _VIEW_RETURN_STATE.clear()


def _activate_dangle_rig(context: bpy.types.Context, rig: bpy.types.Object) -> None:
    scene = context.scene
    for index, obj in enumerate(scene.objects):
        if obj == rig:
            scene.dangle_active_rig_index = index
            break
    try:
        scene.physx.ui_tab = 'DANGLES'
    except Exception:
        pass
    try:
        for obj in context.selected_objects:
            obj.select_set(False)
        rig.select_set(True)
        context.view_layer.objects.active = rig
    except Exception:
        pass


def switch_to_graph_view(context: bpy.types.Context, rig: bpy.types.Object) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.get(str(rig.dangle_state.animgraph_tree_name or ""))
    if tree is None or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        payload = load_source_payload(rig)
        tree = create_graph_tree(
            payload,
            rig.dangle_state.animgraph_source_path,
            rig,
            context,
        )

    area = getattr(context, "area", None)
    key = _area_key(area)
    if area is not None and key is not None and key not in _VIEW_RETURN_STATE:
        _VIEW_RETURN_STATE[key] = {
            "area_type": str(area.type),
            "ui_type": str(getattr(area, "ui_type", "") or ""),
            "rig_name": rig.name,
        }

    if area is not None:
        area.type = "NODE_EDITOR"
        space = area.spaces.active
        try:
            space.tree_type = ANIMGRAPH_TREE_ID
        except Exception:
            pass
        try:
            space.pin = True
            space.node_tree = tree
        except Exception:
            pass
    return tree


def switch_to_editor_view(
    context: bpy.types.Context,
    rig: Optional[bpy.types.Object] = None,
) -> bpy.types.Object:
    area = getattr(context, "area", None)
    key = _area_key(area)
    state = _VIEW_RETURN_STATE.pop(key, None) if key is not None else None
    if state is None:
        raise AnimGraphPatchError(
            "This Graph View was not opened from the Dangle editor."
        )

    if rig is None:
        rig = rig_for_context(context)
    if rig is None:
        rig_name = str(state.get("rig_name", "") or "")
        rig = bpy.data.objects.get(rig_name) if rig_name else None
    if rig is None or getattr(rig, "type", "") != 'ARMATURE':
        raise AnimGraphPatchError(
            "The Dangle rig associated with this graph is no longer available."
        )

    if area is not None:
        area.type = str(state.get("area_type", "VIEW_3D") or "VIEW_3D")
        previous_ui_type = str(state.get("ui_type", "") or "")
        if previous_ui_type:
            try:
                area.ui_type = previous_ui_type
            except Exception:
                pass
        space = area.spaces.active
        try:
            space.show_region_ui = True
        except Exception:
            pass

    _activate_dangle_rig(context, rig)
    return rig
