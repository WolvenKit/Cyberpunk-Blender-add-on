from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from ...blender.operator_results import execute_operation
from ..blender.scene import appearance_record
from ..model.requests import EntityExportRequest
from ..runtime.scene_cache import entity_index
from ..services.export import export_entity


class CP77_OT_EntityExport(Operator, ExportHelper):
    bl_idname = "cp77.entity_export"
    bl_label = "Export Entity"
    bl_description = "Write the entity's .ent.json and .app.json and the edited meshes"
    bl_options = {"REGISTER"}

    filename_ext = ".ent.json"
    filter_glob: StringProperty(default="*.ent.json", options={"HIDDEN"})
    overwrite_imported: BoolProperty(
        name="Overwrite Imported",
        description="Write over the .ent.json and .app.json the entity was imported from",
        default=False,
    )
    edited_meshes: BoolProperty(
        name="Edited Meshes",
        description="Write meshes changed since import over the .glb they came from",
        default=True,
    )
    all_appearances: BoolProperty(
        name="All Appearances",
        description="Also copy the original's appearances that weren't imported",
        default=False,
    )
    appearances_folder: StringProperty(
        name="Appearances Folder",
        description="Where the .app.json goes; it takes the name of the .ent.json",
        subtype="DIR_PATH",
    )

    @classmethod
    def poll(cls, context):
        tools = getattr(context.scene, "cp77_entity_tools", None)
        return tools is not None and bool(entity_index().collections(tools.entity))

    def invoke(self, context, event):
        record = appearance_record(
            entity_index().collections(context.scene.cp77_entity_tools.entity)[0]
        )
        name = os.path.basename(record.ent_path)
        stem = (
            name[: -len(".ent.json")]
            if name.casefold().endswith(".ent.json")
            else os.path.splitext(name)[0]
        )
        self.filepath = os.path.join(
            os.path.dirname(record.ent_path), f"{stem}_edit.ent.json"
        )
        if not self.appearances_folder:
            self.appearances_folder = os.path.dirname(record.app_path)
        return super().invoke(context, event)

    def execute(self, context):
        request = EntityExportRequest(
            filepath=self.filepath,
            overwrite=self.overwrite_imported,
            edited_meshes=self.edited_meshes,
            all_appearances=self.all_appearances,
            appearances_folder=bpy.path.abspath(self.appearances_folder)
            if self.appearances_folder
            else "",
        )
        return execute_operation(
            self,
            "Entity export",
            export_entity,
            context,
            context.scene.cp77_entity_tools.entity,
            request,
        )


EXPORT_OPERATOR_CLASSES = (CP77_OT_EntityExport,)
