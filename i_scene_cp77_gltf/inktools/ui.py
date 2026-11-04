from __future__ import annotations

import bpy

from ..assetio.values import json_object
from ..core.addon_identity import get_addon_preferences
from .blender import hierarchy
from .runtime.widgets import screen_roots


def _draw_sequences(layout, root) -> None:
    sequences = [
        str(name) for name in json_object(root.get("cp77_ink_animation_durations"))
    ]
    if not sequences:
        return
    column = layout.column(align=True)
    playing = (
        str(root.get("cp77_ink_active_sequence", ""))
        if root.get("cp77_ink_animation_enabled")
        else ""
    )
    for name in sequences:
        column.operator(
            "cp77.ink_activate_sequence", text=name, depress=name == playing
        ).sequence_name = name
    column.operator("cp77.ink_stop_sequence", icon="PAUSE")


def _draw_controls(layout, handle) -> None:
    controls = handle.cp77_ink
    bound = set(str(handle.get("inkBoundProperties", "") or "").split(","))
    column = layout.column()
    if handle.get("cp77_type") == "inkTextWidget":
        column.prop(controls, "text")
        if "fontSize" not in bound:
            column.prop(controls, "font_size")
    if not handle.get("inkFitToContent"):
        column.prop(controls, "size")
    if "opacity" not in bound:
        column.prop(controls, "opacity")
    if "tintColor" not in bound:
        column.prop(controls, "tint")
    if "visible" not in bound:
        column.prop(controls, "visible")


class CP77_UL_InkWidgets(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        layout.label(text=item.name, icon="IMAGE_DATA")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        named = bpy.types.UI_UL_list.filter_items_by_name(
            self.filter_name,
            self.bitflag_filter_item,
            items,
            "name",
            reverse=self.use_filter_invert,
        )
        flags = [0] * len(items)
        for root in screen_roots():
            index = items.find(root.name)
            if index >= 0 and items[index] == root and (not named or named[index]):
                flags[index] = self.bitflag_filter_item
        return flags, []


def draw_ink_widgets(layout, context):
    """The ink Widgets section"""
    if not getattr(get_addon_preferences(context), "show_modtools", True):
        return
    header, body = layout.panel("cp77_scene_ink_widgets", default_closed=True)
    header.label(text="ink Widgets")
    if not body:
        return
    body.operator("cp77.import_inkwidget", icon="IMPORT")
    tools = context.scene.cp77_ink_tools
    body.template_list(
        "CP77_UL_InkWidgets",
        "",
        context.scene,
        "objects",
        tools,
        "widget_index",
        rows=3,
    )
    root = hierarchy.screen_root(hierarchy.picked_widget(context.scene))
    if root is not None:
        _draw_sequences(body, root)
        if hierarchy.standalone_root(root) is not None:
            row = body.row(align=True)
            row.operator("cp77.ink_refresh", icon="FILE_REFRESH")
            row.operator("cp77.ink_export", icon="EXPORT")
    part = context.active_object
    if (
        hierarchy.widget_path(part) is not None
        and hierarchy.standalone_root(part) is not None
    ):
        _draw_controls(body, part)


INK_UI_CLASSES = (CP77_UL_InkWidgets,)
