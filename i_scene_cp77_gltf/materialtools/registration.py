import bpy

from ..core.registration import RegistrationLedger
from .depot.state import clear_depot_state_cache
from .multilayer.editor import reset_runtime_state
from .operators.actions import MATERIAL_OPERATOR_CLASSES
from .runtime.callbacks import (
    clear_material_runtime_caches,
    clear_msgbus,
    load_post_handler,
    load_pre_handler,
    stop_timers,
    subscribe_all,
    trigger_update_on_undo,
)
from .ui.panels import MATERIAL_UI_CLASSES
from .ui.properties import CP77MlPropertyGroup

_CLASSES = (
    CP77MlPropertyGroup,
    *MATERIAL_OPERATOR_CLASSES,
    *MATERIAL_UI_CLASSES,
)
_LEDGER = RegistrationLedger("materialtools")


def _reset_runtime():
    stop_timers()
    clear_msgbus()
    clear_depot_state_cache()
    clear_material_runtime_caches()
    reset_runtime_state()


def register_materialtools():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(_CLASSES)
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_ml_props",
            bpy.props.PointerProperty(type=CP77MlPropertyGroup),
        )
        _LEDGER.add_cleanup("material runtime", _reset_runtime)
        clear_msgbus()
        subscribe_all()
        for handlers, callback in (
            (bpy.app.handlers.load_pre, load_pre_handler),
            (bpy.app.handlers.load_post, load_post_handler),
            (bpy.app.handlers.undo_post, trigger_update_on_undo),
            (bpy.app.handlers.redo_post, trigger_update_on_undo),
        ):
            _LEDGER.add_handler(handlers, callback)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_materialtools():
    _LEDGER.cleanup_or_raise()
