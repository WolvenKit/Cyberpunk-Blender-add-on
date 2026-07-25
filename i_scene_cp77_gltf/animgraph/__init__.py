bl_info = {
    "name": "REDengine AnimGraph Editor",
    "author": "The Magnificent Doctor Presto!",
    "version": (0, 1, 0),
    "blender": (5, 0, 0),
    "location": "Node Editor sidebar",
    "description": "Edit REDengine AnimGraphs synchronized through the Dangle editor.",
    "category": "Import-Export",
}

import bpy

from .properties import (
    REDengine_AnimCurvePoint,
    REDengine_AnimArrayField,
    REDengine_AnimArrayElement,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
    REDengine_AnimFeature,
)
from .sockets import (
    REDengine_AnimGraphSocket_Pose,
    REDengine_AnimGraphSocket_Float,
    REDengine_AnimGraphSocket_Vector,
    REDengine_AnimGraphSocket_Int,
    REDengine_AnimGraphSocket_Bool,
    REDengine_AnimGraphSocket_Quaternion,
    REDengine_AnimGraphSocket_Transform,
    REDengine_AnimGraphSocket_Transition,
    REDengine_AnimGraphSocket_Editor,
)
from .tree import REDengine_AnimGraphTree
from .nodes import (
    REDengine_AnimGraphNode_Generic,
    REDengine_AnimGraphContainer,
    curve_editor_classes,
)
from .navigation import REDENGINE_OT_enter_group, REDENGINE_OT_exit_group
from .panels import (
    REDENGINE_PT_inputs,
    REDENGINE_PT_subgraph_nav,
    REDENGINE_PT_graph_validator,
    REDENGINE_PT_dangle_bridge,
)
from .add_node import add_classes, menu_func_add, REDENGINE_MT_add_root
from .parser import AnimGraphParser
from .graph_validator import REDENGINE_OT_validate_graph
from .json_encoder import (
    REDENGINE_OT_encode_selected_node,
    REDENGINE_OT_encode_root_variables,
    REDENGINE_OT_encode_active_tree,
    REDENGINE_OT_encode_rootchunk_json,
)

classes = (
    REDengine_AnimCurvePoint,
    REDengine_AnimArrayField,
    REDengine_AnimArrayElement,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
    REDengine_AnimFeature,
    REDengine_AnimGraphSocket_Pose,
    REDengine_AnimGraphSocket_Float,
    REDengine_AnimGraphSocket_Vector,
    REDengine_AnimGraphSocket_Int,
    REDengine_AnimGraphSocket_Bool,
    REDengine_AnimGraphSocket_Quaternion,
    REDengine_AnimGraphSocket_Transform,
    REDengine_AnimGraphSocket_Transition,
    REDengine_AnimGraphSocket_Editor,
    REDengine_AnimGraphTree,
    REDengine_AnimGraphNode_Generic,
    REDengine_AnimGraphContainer,
    REDENGINE_OT_enter_group,
    REDENGINE_OT_exit_group,
    REDENGINE_PT_inputs,
    REDENGINE_PT_subgraph_nav,
    REDENGINE_PT_graph_validator,
    REDENGINE_PT_dangle_bridge,
    REDENGINE_OT_validate_graph,
    REDENGINE_OT_encode_selected_node,
    REDENGINE_OT_encode_root_variables,
    REDENGINE_OT_encode_active_tree,
    REDENGINE_OT_encode_rootchunk_json,
    *curve_editor_classes,
) + add_classes

addon_keymaps = []
_registered_classes = []
_registered_menus = False



def _register_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    enter = km.keymap_items.new(REDENGINE_OT_enter_group.bl_idname, 'TAB', 'PRESS')
    exit_ = km.keymap_items.new(REDENGINE_OT_exit_group.bl_idname, 'TAB', 'PRESS', ctrl=True)
    addon_keymaps.append((km, enter))
    addon_keymaps.append((km, exit_))


def _unregister_keymaps():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


def register():
    global _registered_menus
    _registered_classes.clear()
    external_core = hasattr(bpy.types, REDengine_AnimGraphTree.__name__)
    for cls in classes:
        if hasattr(bpy.types, cls.__name__):
            continue
        bpy.utils.register_class(cls)
        _registered_classes.append(cls)
    if not external_core:
        bpy.types.NODE_MT_add.append(menu_func_add)
        _registered_menus = True
        _register_keymaps()


def unregister():
    global _registered_menus
    _unregister_keymaps()
    if _registered_menus:
        for menu, func in (
            (bpy.types.NODE_MT_add, menu_func_add),
        ):
            try:
                menu.remove(func)
            except Exception:
                pass
        _registered_menus = False
    for cls in reversed(_registered_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _registered_classes.clear()


if __name__ == "__main__":
    register()
