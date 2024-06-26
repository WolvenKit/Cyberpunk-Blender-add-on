import bpy
import bpy.utils.previews
import sys
from bpy.props import (StringProperty, BoolProperty)
from bpy.types import (Operator, Panel, TOPBAR_MT_file_export)
from bpy_extras.io_utils import ExportHelper
from .collision_export import *
from .glb_export import *
from .hp_export import *
from .phys_export import *
from .sectors_export import *
from .mlsetup_export import *
from ..main.bartmoss_functions import *
from ..main.common import get_classes, show_message
from ..cyber_props import *
from ..cyber_prefs import *
from ..icons.cp77_icons import *


class CP77StreamingSectorExport(Operator,ExportHelper):
    bl_idname = "export_scene.cp77_sector"
    bl_label = "Export Sector Updates for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export changes to Sectors back to project" 
    filename_ext = ".cpmodproj"
    filter_glob: StringProperty(default="*.cpmodproj", options={'HIDDEN'})

    def execute(self, context):
        exportSectors(self.filepath)
        return {'FINISHED'}


class CP77GLBExport(Operator,ExportHelper):
  ### cleaned this up and moved most code to exporters.py
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077" 
    filename_ext = ".glb"
   ### adds a checkbox for anim export settings
    
    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})
   
    
    limit_selected: BoolProperty(
        name="Limit to Selected Meshes",
        default=True,
        description="Only Export the Selected Meshes. This is probably the setting you want to use"
    )
    
    static_prop: BoolProperty(
        name="Export as Static Prop",
        default=False,
        description="No armature export, only use this for exporting props and objects which do not need to move"
    )

    export_poses: BoolProperty(
        name="Animations",
        default=False,
        description="Use this option if you are exporting anims to be imported into wkit as .anim"
    )

    export_visible: BoolProperty(
        name="Export Visible Meshes",
        default=False,
        description="Use this option to export all visible objects. Only use this if you know why you're using this"
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True) 
        row.prop(self, "export_poses")
        if not self.export_poses:
            row = layout.row(align=True)
            row.prop(self, "limit_selected")
            if not self.limit_selected:
                row = layout.row(align=True)
                row.prop(self, "export_visible")
            else: 
                row = layout.row(align=True)
                row.prop(self, "static_prop")
        
    def execute(self, context):
        export_cyberpunk_glb(context, self.filepath, self.export_poses, self.export_visible, self.limit_selected, self.static_prop)
        return {'FINISHED'}


class CP77HairProfileExport(Operator):
    bl_idname = "export_scene.hp"
    bl_label = "Export Hair Profile"
    bl_description ="Generates a new .hp.json in your mod project folder which can be imported in Wolvenkit"
    bl_parent_id = "CP77_PT_MeshTools"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        cp77_hp_export(self.filepath)
        return {"FINISHED"}


class CP77MlSetupExport(Operator):
    bl_idname = "export_scene.mlsetup"
    bl_label = "Export MLSetup"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "EXPERIMENTAL: Export material changes to mlsetup files" 

    filepath: StringProperty(subtype="FILE_PATH")
  
    def execute(self, context):
        cp77_mlsetup_export(self, context)
        return {"FINISHED"}

class CP77CollisionExport(Operator):
    bl_idname = "export_scene.collisions"
    bl_label = "Export Collisions to .JSON"
    bl_parent_id = "CP77_PT_collisions"
    bl_description = "Export project collisions to .phys.json"

    filepath: StringProperty(subtype="FILE_PATH")

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "collision_type")

    def execute(self, context):
        collision_type = context.scene.cp77_panel_props.collision_type
        cp77_collision_export(self.filepath, collision_type)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

def menu_func_export(self, context):
    self.layout.operator(CP77GLBExport.bl_idname, text="Cyberpunk GLB", icon_value=get_icon("WKIT"))
    self.layout.operator(CP77StreamingSectorExport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon("WKIT"))

operators, other_classes = get_classes(sys.modules[__name__])

def register_exporters():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)   
    TOPBAR_MT_file_export.append(menu_func_export)

def unregister_exporters():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    TOPBAR_MT_file_export.remove(menu_func_export)