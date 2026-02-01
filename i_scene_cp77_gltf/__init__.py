print('-------------------- Cyberpunk IO Suite Starting--------------------')
print('')
from .cyber_prefs import *
from .cyber_props import *
import bpy
import textwrap
from bpy.props import (StringProperty)
from bpy.types import (Operator, Panel)
from . collisiontools import *
from . meshtools import *
from . animtools import *
from . importers import *
from . exporters import *
from . scriptman import *
from . materialtools import *

bl_info = {
    "name": "Cyberpunk 2077 IO Suite",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwekmaster, glitchered, Simarilius, Doctor Presto, shotlastc, Rudolph2109, Holopointz, Peatral, John CO., Chase_81, akikoe,  sprt_, Jazza",
    "version": (1, 8, 1),
    "blender": (4, 5, 0),
    "location": "File > Import-Export",
    "description": "Import and Export WolvenKit Cyberpunk2077 gLTF models with materials, Import .streamingsector and .ent from .json",
    "warning": "",
    "category": "Import-Export",
    "doc_url": "https://github.com/WolvenKit/Cyberpunk-Blender-add-on#readme",
    "tracker_url": "https://github.com/WolvenKit/Cyberpunk-Blender-add-on/issues/new/choose",
}

plugin_version = ".".join(map(str, bl_info["version"]))
blender_version = ".".join(map(str, bpy.app.version))
script_dir = get_script_dir()

print()
print(f"Blender Version:{blender_version}")
print(f"Cyberpunk IO Suite version: {plugin_version}")
print()

res_dir = get_resources_dir()

class ShowMessageBox(Operator):
    bl_idname = "cp77.message_box"
    bl_label = "Cyberpunk 2077 IO Suite"

    message: StringProperty(default="")

    def execute(self, context):
        self.report({'INFO'}, self.message)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw_header(self, context):
        layout = self.layout
        layout.label(text='Cyberpunk 2077 IO Suite')

    def draw(self, context):
        wrapp = textwrap.TextWrapper(width=70) #50 = maximum length
        wList = wrapp.wrap(text=self.message)
        for text in wList:
            row = self.layout.row(align = True)
            row.alignment = 'EXPAND'
            row.label(text=text)

class CollectionAppearancePanel(Panel):
    bl_label = "Ent Appearances"
    bl_idname = "PANEL_PT_appearance_variants"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    #only draw the if the collector has an appearanceName property
    @classmethod
    def poll(cls, context):
        collection = context.collection
        return hasattr(collection, "appearanceName")

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        layout.prop(collection, "appearanceName")

classes = [ShowMessageBox, CollectionAppearancePanel]

def register():
    register_prefs()
    register_props()
    register_animtools()
    register_collisiontools()
    register_importers()
    register_exporters()
    register_scriptman()
    register_meshtools()
    register_materialtools()

    for cls in classes:
        if cls.__name__ == "JSONTool": # this one is static
            continue
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    load_icons()
    print('')
    print('-------------------- Cyberpunk IO Suite Has Started--------------------')
    print('')

def unregister():
    unregister_materialtools()
    unregister_meshtools()
    unregister_scriptman()
    unregister_exporters()
    unregister_importers()
    unregister_collisiontools()
    unregister_animtools()
    unregister_props()
    unregister_prefs()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unload_icons()

if __name__ == "__main__":
    register()
