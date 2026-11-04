import bpy

from ..core.registration import RegistrationLedger
from .operators import ENTITY_OPERATOR_CLASSES
from .properties import (
    ENTITY_PROPERTY_CLASSES,
    CP77EntityAppearanceState,
    CP77EntityToolsState,
)
from .runtime.documents import clear_source_documents
from .runtime.scene_cache import clear_entity_caches
from .runtime.selection_sync import on_depsgraph_update, reset_selection_sync
from .runtime.ui_refresh import cancel_refresh
from .ui import ENTITY_UI_CLASSES

_CLASSES = (*ENTITY_PROPERTY_CLASSES, *ENTITY_OPERATOR_CLASSES, *ENTITY_UI_CLASSES)
_LEDGER = RegistrationLedger("enttools")


def register_enttools():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(_CLASSES)
        _LEDGER.add_property(
            bpy.types.Collection,
            "cp77_entity_state",
            bpy.props.PointerProperty(type=CP77EntityAppearanceState),
        )
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_entity_tools",
            bpy.props.PointerProperty(type=CP77EntityToolsState),
        )
        _LEDGER.add_handler(bpy.app.handlers.depsgraph_update_post, on_depsgraph_update)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, reset_selection_sync)
        for handlers in (
            bpy.app.handlers.load_pre,
            bpy.app.handlers.undo_post,
            bpy.app.handlers.redo_post,
        ):
            _LEDGER.add_handler(handlers, clear_entity_caches)
        _LEDGER.add_cleanup("entity scene caches", clear_entity_caches)
        _LEDGER.add_cleanup("entity documents", clear_source_documents)
        _LEDGER.add_cleanup("entity panel refresh", cancel_refresh)
        _LEDGER.add_cleanup("entity selection sync", reset_selection_sync)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_enttools():
    _LEDGER.cleanup_or_raise()
