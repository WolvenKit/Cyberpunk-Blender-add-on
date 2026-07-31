import sys

import bpy

from ..registration import RegistrationLedger, get_classes
from .callbacks import (
    clear_msgbus,
    load_post_handler,
    load_pre_handler,
    stop_timers,
    subscribe_all,
    trigger_update_on_undo,
)
from .operators import (
    CP77MlSetupCreateMultilayerMaterial,
    CP77MlSetupCreateMultilayerObject,
    CP77MlSetupEnterTexturePaint,
    CP77MlSetupGenerateMasks,
    CP77MlSetupGenerateOverrides,
    CP77MlSetupGenerateOverridesDisconnected,
    CP77MlSetupRefreshOverrides,
    CP77MlSetupRelocateMesh,
)
from .properties import CP77MlPropertyGroup
from .editor import reset_runtime_state
from .ui import CP77_PT_MaterialTools

_CLASSES = get_classes(
    sys.modules[__name__],
    extra_classes=(
        CP77MlPropertyGroup,
        CP77MlSetupGenerateOverrides,
        CP77MlSetupGenerateOverridesDisconnected,
        CP77MlSetupRefreshOverrides,
        CP77MlSetupEnterTexturePaint,
        CP77MlSetupGenerateMasks,
        CP77MlSetupCreateMultilayerObject,
        CP77MlSetupCreateMultilayerMaterial,
        CP77MlSetupRelocateMesh,
        CP77_PT_MaterialTools,
    ),
)
_LEDGER = RegistrationLedger("materialtools")


def _reset_runtime():
    stop_timers()
    clear_msgbus()
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
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError(
            "; ".join(f"{label}: {error}" for label, error in failures)
        )
