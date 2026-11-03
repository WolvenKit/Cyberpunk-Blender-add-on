from __future__ import annotations

import bpy
from bpy.types import UIList

from ..operators.sectors import CP77_OT_SceneAddNewSector, CP77_OT_SceneRemoveNewSector
from ..runtime.sectors import scene_sectors


class CP77_UL_NewSectors(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="OUTLINER_COLLECTION")
        remove = row.operator(
            CP77_OT_SceneRemoveNewSector.bl_idname, text="", icon="X", emboss=False
        )
        remove.collection_name = item.name

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
        for collection in scene_sectors(context.scene).new:
            index = items.find(collection.name)
            if (
                index >= 0
                and items[index] == collection
                and (not named or named[index])
            ):
                flags[index] = self.bitflag_filter_item
        return flags, []


def draw_sectors(layout, context):
    """The Sectors section"""
    scene = context.scene
    sectors = scene_sectors(scene)
    if not sectors.imported:
        return
    header, body = layout.panel("cp77_scene_sectors", default_closed=True)
    header.label(text="Sectors")
    if not body:
        return
    body.operator(CP77_OT_SceneAddNewSector.bl_idname, icon="ADD")
    if sectors.new:
        body.template_list(
            "CP77_UL_NewSectors",
            "",
            bpy.data,
            "collections",
            scene.cp77_scene_tools,
            "new_sector_index",
            rows=3,
        )


SECTOR_UI_CLASSES = (CP77_UL_NewSectors,)
