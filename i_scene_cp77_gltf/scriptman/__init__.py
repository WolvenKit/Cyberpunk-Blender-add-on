import os

from bpy.types import Panel

from .scriptman_ops import registration_classes
from ..paths import ensure_user_script_dir
from ..registration import register_owned_classes, unregister_owned_classes


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
        script_dir = ensure_user_script_dir()
        script_files = sorted(
            f for f in os.listdir(script_dir) if f.endswith(".py")
        )

        for script_file in script_files:
            row = col.row(align=True)
            row.operator("script_manager.save_script", text="", icon="APPEND_BLEND").script_file = script_file
            row.operator("script_manager.load_script", text=script_file).script_file = script_file
            row.operator("script_manager.delete_script", text="", icon="X").script_file = script_file

        row = box.row(align=True)
        row.operator("script_manager.create_script")


_registered_classes = []


def register_scriptman():
    if _registered_classes:
        return
    ensure_user_script_dir()
    _registered_classes[:] = register_owned_classes((*registration_classes, CP77ScriptManager))


def unregister_scriptman():
    failures = unregister_owned_classes(reversed(_registered_classes))
    if not failures:
        _registered_classes.clear()
    if failures:
        raise RuntimeError("; ".join(f"{cls.__name__}: {error}" for cls, error in failures))
