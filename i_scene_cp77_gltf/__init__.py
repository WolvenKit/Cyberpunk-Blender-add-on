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


_REGISTRATION_STEPS = (
    (register_prefs, unregister_prefs),
    (register_notifications, unregister_notifications),
    (register_props, unregister_props),
    (register_animtools, unregister_animtools),
    (register_collisiontools, unregister_collisiontools),
    (register_importers, unregister_importers),
    (register_exporters, unregister_exporters),
    (register_scriptman, unregister_scriptman),
    (register_meshtools, unregister_meshtools),
    (register_materialtools, unregister_materialtools),
    (_register_root_classes, _unregister_root_classes),
    (load_icons, unload_icons),
)

_registered_teardowns = []


def register():
    if _registered_teardowns:
        raise RuntimeError("Addon has pending registration teardown state")
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


if __name__ == "__main__":
    register()
