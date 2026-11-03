import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....core.log import debug_exception, get_logger
from ....exporters.animgraph.dangle_patch import AnimGraphPatchError
from ...blender.dangle_context import rig_for_context
from ...blender.dangle_source import load_source_payload
from .sync import create_graph_tree

_LOG = get_logger(__name__)

_VIEW_RETURN_STATE: dict[int, dict] = {}


def _area_key(area: bpy.types.Area | None) -> int | None:
    if area is None:
        return None
    try:
        return int(area.as_pointer())
    except ReferenceError:
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
        scene.physx.ui_tab = "DANGLES"
    except Exception:
        debug_exception(_LOG, "Could not switch Physics Tools to the Dangles tab")
    try:
        for obj in context.selected_objects:
            obj.select_set(False)
        rig.select_set(True)
        context.view_layer.objects.active = rig
    except Exception:
        debug_exception(
            _LOG, "Could not make the Dangle rig the only selected, active object"
        )


def rig_graph_tree(
    context: bpy.types.Context, rig: bpy.types.Object
) -> bpy.types.NodeTree:
    """The Dangle rig's graph tree, built again from its source document when it is missing"""
    tree = bpy.data.node_groups.get(str(rig.dangle_state.animgraph_tree_name or ""))
    if tree is None or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        payload = load_source_payload(rig)
        tree = create_graph_tree(
            payload,
            rig.dangle_state.animgraph_source_path,
            rig,
            context,
        )
    return tree


def switch_to_graph_view(
    context: bpy.types.Context, rig: bpy.types.Object
) -> bpy.types.NodeTree:
    tree = rig_graph_tree(context, rig)

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
            debug_exception(_LOG, "Could not set the node editor to AnimGraph trees")
        try:
            space.pin = True
            space.node_tree = tree
        except Exception:
            debug_exception(_LOG, "Could not pin the AnimGraph tree in the node editor")
    return tree


def switch_to_editor_view(
    context: bpy.types.Context,
    rig: bpy.types.Object | None = None,
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
    if rig is None or getattr(rig, "type", "") != "ARMATURE":
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
                debug_exception(
                    _LOG,
                    "Could not restore the area's previous editor type %s",
                    previous_ui_type,
                )
        space = area.spaces.active
        try:
            space.show_region_ui = True
        except Exception:
            debug_exception(_LOG, "Could not show the editor's sidebar")

    _activate_dangle_rig(context, rig)
    return rig
