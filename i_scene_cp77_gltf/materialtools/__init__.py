import bpy
import bpy.utils.previews
import sys
from .. exporters import CP77HairProfileExport, mlsetup_export
from ..main.bartmoss_functions import *
from ..main.common import get_classes, get_color_presets, save_presets
from bpy.props import (StringProperty, EnumProperty)
from bpy.types import (Scene, Operator, Panel)
from ..cyber_props import CP77RefitList
from ..icons.cp77_icons import get_icon

class CP77_PT_MaterialTools(Panel):
    bl_label = "Material Tools"
    bl_idname = "CP77_PT_MaterialTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'MESH'
        else:
            return context

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        props = context.scene.cp77_panel_props

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_meshtools:
                box.label(text="Materials", icon="MATERIAL")
                col = box.column()
                col.operator("export_scene.hp")
                col.operator("export_scene.mlsetup")
                col.operator("reload_material.cp77")

operators, other_classes = get_classes(sys.modules[__name__])

def register_materialtools():

    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)

def unregister_materialtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
def unregister_materialtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)