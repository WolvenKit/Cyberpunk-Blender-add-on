import os

from bpy.types import Panel

<<<<<<< Updated upstream
from .scriptman_ops import registration_classes
from ..paths import ensure_user_script_dir
from ..registration import register_owned_classes, unregister_owned_classes
=======
from ..core.registration import RegistrationLedger
from .scriptman_ops import registration_classes
from .user_scripts import ensure_user_script_dir, is_managed_text, user_script_names
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
        # List available scripts
        script_dir = ensure_user_script_dir()
        script_files = sorted(
            f for f in os.listdir(script_dir) if f.endswith(".py")
        )

=======

        script_dir, script_files = user_script_names()

        active_text = getattr(context.space_data, "text", None)
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
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
=======
_LEDGER = RegistrationLedger("script manager")


def register_scriptman():
    if _LEDGER.active:
        return
    ensure_user_script_dir()
    _LEDGER.register_classes((*registration_classes, CP77ScriptManager))


def unregister_scriptman():
    _LEDGER.cleanup_or_raise()
>>>>>>> Stashed changes
