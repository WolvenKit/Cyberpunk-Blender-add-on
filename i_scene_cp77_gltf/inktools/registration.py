import bpy
from bpy.props import PointerProperty

from ..blender.ink import screens
from ..blender.ink.images import clear_decoded_images
from ..core.registration import RegistrationLedger
from .operators import INK_OPERATOR_CLASSES
from .properties import CP77InkToolsSettings, CP77InkWidgetControls
from .runtime.widgets import clear_screen_roots
from .ui import INK_UI_CLASSES

_CLASSES = (
    CP77InkWidgetControls,
    CP77InkToolsSettings,
    *INK_OPERATOR_CLASSES,
    *INK_UI_CLASSES,
)
_LEDGER = RegistrationLedger("inktools")


@bpy.app.handlers.persistent
def _frame_changed(scene, depsgraph):
    screens.frame_changed(scene, depsgraph)


@bpy.app.handlers.persistent
def _file_loading(*_args):
    screens.clear()
    clear_decoded_images()
    clear_screen_roots()


@bpy.app.handlers.persistent
def _file_loaded(*_args):
    screens.resume_playing()


@bpy.app.handlers.persistent
def _file_saving(*_args):
    screens.keep_rasters()


def register_inktools():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(_CLASSES)
        _LEDGER.add_property(
            bpy.types.Object, "cp77_ink", PointerProperty(type=CP77InkWidgetControls)
        )
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_ink_tools",
            PointerProperty(type=CP77InkToolsSettings),
        )
        _LEDGER.add_handler(bpy.app.handlers.frame_change_post, _frame_changed)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, _file_loading)
        _LEDGER.add_handler(bpy.app.handlers.load_post, _file_loaded)
        _LEDGER.add_handler(bpy.app.handlers.save_pre, _file_saving)
        _LEDGER.add_handler(bpy.app.handlers.undo_post, clear_screen_roots)
        _LEDGER.add_handler(bpy.app.handlers.redo_post, clear_screen_roots)
        _LEDGER.add_cleanup("ink screen roots", clear_screen_roots)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_inktools():
    screens.clear()
    _LEDGER.cleanup_or_raise()
