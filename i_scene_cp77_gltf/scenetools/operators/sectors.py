from __future__ import annotations

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from ...core.log import get_logger
from ...core.notifications import report
from ...exporters.sector.new_sectors import (
    NEW_SECTOR_KEY,
    add_new_sector,
    remove_new_sector,
)

_LOG = get_logger(__name__)


class CP77_OT_SceneAddNewSector(Operator):
    bl_idname = "cp77.scene_add_new_sector"
    bl_label = "Add New Sector"
    bl_description = (
        "Add an empty new sector; placements moved into it are exported as copies in a sector of its own, "
        "named after the collection"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        add_new_sector(context.scene)
        return {"FINISHED"}


class CP77_OT_SceneRemoveNewSector(Operator):
    bl_idname = "cp77.scene_remove_new_sector"
    bl_label = "Remove New Sector"
    bl_description = (
        "Remove this new sector; what it holds moves to the collection above it"
    )
    bl_options = {"REGISTER", "UNDO"}

    collection_name: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection_name)
        if collection is None or not collection.get(NEW_SECTOR_KEY):
            report(
                self,
                "ERROR",
                f"{self.collection_name} is not a new sector",
                logger=_LOG,
            )
            return {"CANCELLED"}
        remove_new_sector(context.scene, collection)
        return {"FINISHED"}


SECTOR_OPERATOR_CLASSES = (
    CP77_OT_SceneAddNewSector,
    CP77_OT_SceneRemoveNewSector,
)
