import bpy

from ..blender.import_hooks import register_import_hook, unregister_import_hook
from ..core.registration import RegistrationLedger
from .application.lights import (
    clear_light_sources,
    lights_before_import,
    preview_imported_lights,
)
from .blender.images import clear_resource_image_cache
from .operators import SCENE_TOOL_OPERATOR_CLASSES
from .runtime.callbacks import clear_loaded_file_caches
from .runtime.lights import clear_light_index
from .runtime.ownership import clear_runtime_cache
from .runtime.sectors import clear_sector_cache
from .runtime.vehicle_lights import clear_vehicle_light_cache
from .ui import SCENE_TOOL_UI_CLASSES
from .ui.properties import SCENE_TOOL_PROPERTY_CLASSES, CP77SceneToolsSettings

_CLASSES = (
    *SCENE_TOOL_PROPERTY_CLASSES,
    *SCENE_TOOL_OPERATOR_CLASSES,
    *SCENE_TOOL_UI_CLASSES,
)
_LEDGER = RegistrationLedger("scenetools")


def register_scenetools():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(_CLASSES)
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_scene_tools",
            bpy.props.PointerProperty(type=CP77SceneToolsSettings),
        )
        _LEDGER.add_handler(bpy.app.handlers.load_post, clear_loaded_file_caches)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, clear_vehicle_light_cache)
        _LEDGER.add_cleanup("vehicle light cache", clear_vehicle_light_cache)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, clear_light_index)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, clear_light_sources)
        _LEDGER.add_handler(bpy.app.handlers.undo_post, clear_light_index)
        _LEDGER.add_handler(bpy.app.handlers.redo_post, clear_light_index)
        _LEDGER.add_cleanup("light index", clear_light_index)
        _LEDGER.add_cleanup("light sources", clear_light_sources)
        for handlers in (
            bpy.app.handlers.load_pre,
            bpy.app.handlers.undo_post,
            bpy.app.handlers.redo_post,
        ):
            _LEDGER.add_handler(handlers, clear_sector_cache)
        _LEDGER.add_cleanup("sector cache", clear_sector_cache)
        register_import_hook(lights_before_import, preview_imported_lights)
        _LEDGER.add_cleanup("import Lights preview", unregister_import_hook)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_scenetools():
    clear_runtime_cache()
    clear_resource_image_cache()
    _LEDGER.cleanup_or_raise()
