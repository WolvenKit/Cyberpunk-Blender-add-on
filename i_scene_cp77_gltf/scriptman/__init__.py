import bpy
import os
from bpy.types import Panel
from .scriptman_ops import operators, other_classes
from ..main.common import get_script_dir 


script_dir = get_script_dir()


class CP77ScriptManager(Panel):
    bl_label = "Script Manager"
    bl_idname = "CP77_PT_ScriptManagerPanel"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        # List available scripts
        script_files = [f for f in os.listdir(script_dir) if f.endswith(".py")]

        
        for script_file in script_files:
            row = col.row(align=True)
            row.operator("script_manager.save_script", text="", icon="APPEND_BLEND").script_file = script_file
            row.operator("script_manager.load_script", text=script_file).script_file = script_file
            row.operator("script_manager.delete_script", text="", icon="X").script_file = script_file

        row = box.row(align=True)
        row.operator("script_manager.create_script")


def register_scriptman():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    bpy.utils.register_class(CP77ScriptManager)

def unregister_scriptman():
    bpy.utils.unregister_class(CP77ScriptManager)
    for cls in reversed(other_classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)