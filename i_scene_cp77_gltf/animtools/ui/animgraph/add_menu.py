from functools import cache

import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....animation.model.animgraph.schema import registry
from ....blender.animgraph.categories import ADD_MENU_GROUPS, add_menu_types


@cache
def _menu_types() -> dict:
    return add_menu_types(registry.all_node_short_names(), registry.output_kind)


def _draw_type_list(layout, types):
    for short in types:
        op = layout.operator("redengine.add_node", text=short)
        op.node_type = short


def _make_submenu(group_name):
    idname = "REDENGINE_MT_add_" + group_name.lower().replace(" ", "_").replace(
        "&", "and"
    )

    class _Sub(bpy.types.Menu):
        bl_idname = idname
        bl_label = group_name

        def draw(self, context):
            _draw_type_list(self.layout, _menu_types()[group_name])

    _Sub.__name__ = idname
    return _Sub


_SUBMENUS = tuple(_make_submenu(name) for name, _category in ADD_MENU_GROUPS)


class REDENGINE_MT_add_root(bpy.types.Menu):
    bl_idname = "REDENGINE_MT_add_root"
    bl_label = "REDengine AnimGraph"

    def draw(self, context):
        for sub in _SUBMENUS:
            self.layout.menu(sub.bl_idname)


def menu_func_add(self, context):
    space = context.space_data
    if (
        space is not None
        and space.type == "NODE_EDITOR"
        and space.edit_tree is not None
        and space.edit_tree.bl_idname == ANIMGRAPH_TREE_ID
    ):
        self.layout.menu(REDENGINE_MT_add_root.bl_idname)


ADD_MENU_CLASSES = (*_SUBMENUS, REDENGINE_MT_add_root)
