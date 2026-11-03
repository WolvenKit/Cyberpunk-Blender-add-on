import os

from bpy.types import Panel

from ..core.registration import RegistrationLedger
from .scriptman_ops import registration_classes
from .user_scripts import ensure_user_script_dir, is_managed_text, user_script_names


class CP77ScriptManager(Panel):
    bl_label = "Script Manager"
    bl_idname = "CP77_PT_ScriptManagerPanel"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()

        script_dir, script_files = user_script_names()

        active_text = getattr(context.space_data, "text", None)
        for script_file in script_files:
            row = col.row(align=True)
            save = row.row(align=True)
            save.enabled = is_managed_text(
                active_text, os.path.join(script_dir, script_file)
            )
            save.operator(
                "script_manager.save_script", text="", icon="APPEND_BLEND"
            ).script_file = script_file
            row.operator(
                "script_manager.load_script", text=script_file
            ).script_file = script_file
            row.operator(
                "script_manager.delete_script", text="", icon="X"
            ).script_file = script_file

        row = box.row(align=True)
        row.operator("script_manager.create_script")


_LEDGER = RegistrationLedger("script manager")


def register_scriptman():
    if _LEDGER.active:
        return
    ensure_user_script_dir()
    _LEDGER.register_classes((*registration_classes, CP77ScriptManager))


def unregister_scriptman():
    _LEDGER.cleanup_or_raise()
