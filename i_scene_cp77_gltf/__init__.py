<<<<<<< Updated upstream
print('-------------------- Cyberpunk IO Suite Starting--------------------')
print('')
import bpy
from bpy.types import Panel

from .addon_identity import get_addon_version
from .animtools import register_animtools, unregister_animtools
from .collisiontools import register_collisiontools, unregister_collisiontools
from .cyber_prefs import register_prefs, unregister_prefs
from .cyber_props import register_props, unregister_props
from .exporters import register_exporters, unregister_exporters
from .icons.cp77_icons import load_icons, unload_icons
from .importers import register_importers, unregister_importers
from .notifications import register_notifications, unregister_notifications
from .materialtools import register_materialtools, unregister_materialtools
from .meshtools import register_meshtools, unregister_meshtools
from .scriptman import register_scriptman, unregister_scriptman
from .registration import register_owned_classes, unregister_owned_classes
=======
import bpy

from .animtools.registration import register_animtools, unregister_animtools
from .collisiontools.registration import (
    register_collisiontools,
    unregister_collisiontools,
)
from .core.addon_identity import RUNTIME_BUILD, get_addon_version, runtime_build_string
from .core.log import (
    configure_from_preferences,
    configure_logging,
    current_log_path,
    get_logger,
    shutdown_logging,
)
from .core.notifications import register_notifications, unregister_notifications
from .core.preferences import register_prefs, unregister_prefs
from .core.registration import rollback_teardown_steps
from .cyber_props import register_props, unregister_props
from .enttools.registration import register_enttools, unregister_enttools
from .exporters.operators import register_exporters, unregister_exporters
from .icons.cp77_icons import load_icons, unload_icons
from .importers.operators import register_importers, unregister_importers
from .inktools.registration import register_inktools, unregister_inktools
from .materialtools.registration import register_materialtools, unregister_materialtools
from .meshtools.registration import register_meshtools, unregister_meshtools
from .scenetools.registration import register_scenetools, unregister_scenetools
from .scriptman import register_scriptman, unregister_scriptman

_manifest_version = get_addon_version()
if _manifest_version != RUNTIME_BUILD:
    raise RuntimeError(
        f"Cyberpunk IO Suite runtime build {runtime_build_string()} does not match manifest "
        f"{'.'.join(map(str, _manifest_version))}"
    )
>>>>>>> Stashed changes

bl_info = {
    "name": "Cyberpunk 2077 IO Suite",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwekmaster, glitchered, Simarilius, Doctor Presto, shotlastc, Rudolph2109, Holopointz, Peatral, John CO., Chase_81, akikoe,  sprt_, Jazza, 86maylin",
    "version": get_addon_version(),
    "blender": (5, 0, 0),
    "location": "File > Import-Export",
    "description": "Import and Export WolvenKit Cyberpunk2077 gLTF models with materials, Import .streamingsector and .ent from .json",
    "warning": "",
    "category": "Import-Export",
    "doc_url": "https://github.com/WolvenKit/Cyberpunk-Blender-add-on#readme",
    "tracker_url": "https://github.com/WolvenKit/Cyberpunk-Blender-add-on/issues/new/choose",
    }

<<<<<<< Updated upstream
plugin_version = ".".join(map(str, bl_info["version"]))
blender_version = ".".join(map(str, bpy.app.version))
print()
print(f"Blender Version:{blender_version}")
print(f"Cyberpunk IO Suite version: {plugin_version}")
print()


class CollectionAppearancePanel(Panel):
    bl_label = "Ent Appearances"
    bl_idname = "PANEL_PT_appearance_variants"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    # only draw the if the collector has an appearanceName property
    @classmethod
    def poll(cls, context):
        collection = context.collection
        return (
            collection is not None
            and "appearanceName" in collection.keys()
        )

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        layout.prop(
            collection,
            '["appearanceName"]',
            text="Appearance",
        )


classes = [CollectionAppearancePanel]


_registered_root_classes = []


def _register_root_classes():
    _registered_root_classes[:] = register_owned_classes(classes)


def _unregister_root_classes():
    failures = unregister_owned_classes(reversed(_registered_root_classes))
    if not failures:
        _registered_root_classes.clear()
    if failures:
        raise RuntimeError("; ".join(
            f"{cls.__name__}: {error}" for cls, error in failures
        ))


=======
_LOG = get_logger(__name__)


>>>>>>> Stashed changes
_REGISTRATION_STEPS = (
    (register_prefs, unregister_prefs),
    (register_notifications, unregister_notifications),
    (register_props, unregister_props),
    (register_animtools, unregister_animtools),
    (register_collisiontools, unregister_collisiontools),
    (register_importers, unregister_importers),
<<<<<<< Updated upstream
=======
    (register_inktools, unregister_inktools),
>>>>>>> Stashed changes
    (register_exporters, unregister_exporters),
    (register_scriptman, unregister_scriptman),
    (register_meshtools, unregister_meshtools),
    (register_materialtools, unregister_materialtools),
<<<<<<< Updated upstream
    (_register_root_classes, _unregister_root_classes),
=======
    (register_enttools, unregister_enttools),
    (register_scenetools, unregister_scenetools),
>>>>>>> Stashed changes
    (load_icons, unload_icons),
)

_registered_teardowns = []


def register():
    if _registered_teardowns:
        raise RuntimeError("Addon has pending registration teardown state")
<<<<<<< Updated upstream
    completed = []
    try:
        for register_step, unregister_step in _REGISTRATION_STEPS:
            register_step()
            completed.append(unregister_step)
    except Exception:
        pending = []
        for unregister_step in reversed((*completed, unregister_step)):
            try:
                unregister_step()
            except Exception:
                pending.append(unregister_step)
        _registered_teardowns[:] = reversed(pending)
        raise
    _registered_teardowns[:] = completed
    print('')
    print('-------------------- Cyberpunk IO Suite Has Started--------------------')
    print('')


def unregister():
    teardowns = tuple(_registered_teardowns)
    if not teardowns:
        return
    failed = []
    for unregister_step in reversed(teardowns):
        try:
            unregister_step()
        except Exception as error:
            failed.append(unregister_step)
            print(
                f"[CP77] Teardown warning in "
                f"{getattr(unregister_step, '__name__', unregister_step)}: "
                f"{error}"
            )
    _registered_teardowns[:] = reversed(failed)
    if failed:
        raise RuntimeError(
            f"Addon teardown incomplete: {len(failed)} step(s) remain"
        )


=======
    configure_logging()
    completed = []
    current_teardown = None
    try:
        for register_func, teardown_func in _REGISTRATION_STEPS:
            current_teardown = teardown_func
            register_func()
            completed.append(teardown_func)
            if register_func is register_prefs:
                configure_from_preferences()
    except Exception:
        _LOG.exception("Cyberpunk IO Suite registration failed")
        pending = []
        rollback_steps = rollback_teardown_steps(completed, current_teardown)
        for teardown_step in reversed(rollback_steps):
            try:
                teardown_step()
            except Exception:
                pending.append(teardown_step)
                _LOG.exception(
                    "Registration rollback teardown failed: %s",
                    getattr(teardown_step, "__name__", teardown_step),
                )
        _registered_teardowns[:] = reversed(pending)
        shutdown_logging()
        raise
    _registered_teardowns[:] = completed
    _LOG.info(
        "Cyberpunk IO Suite %s registered for Blender %s runtime_build=%s",
        ".".join(map(str, get_addon_version())),
        ".".join(map(str, bpy.app.version)),
        runtime_build_string(),
    )
    if path := current_log_path():
        _LOG.debug("Detailed log file: %s", path)


def unregister():
    teardowns = tuple(_registered_teardowns)
    if not teardowns:
        shutdown_logging()
        return
    failed = []
    try:
        for unregister_step in reversed(teardowns):
            try:
                unregister_step()
            except Exception:
                failed.append(unregister_step)
                _LOG.exception(
                    "Teardown step failed: %s",
                    getattr(unregister_step, "__name__", unregister_step),
                )
        _registered_teardowns[:] = reversed(failed)
        if failed:
            raise RuntimeError(
                f"Addon teardown incomplete: {len(failed)} step(s) remain"
            )
        _LOG.info("Cyberpunk IO Suite unregistered")
    finally:
        shutdown_logging()


>>>>>>> Stashed changes
if __name__ == "__main__":
    register()
