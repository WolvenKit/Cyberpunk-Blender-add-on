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
from .write_rig import *
from ..main.bartmoss_functions import *
from ..main.common import get_classes, show_message
from ..cyber_props import *
from ..cyber_prefs import *
from ..icons.cp77_icons import *

class CP77RigJSONExport(Operator,ExportHelper):
    bl_idname = "export_scene.cp77_rig_export"
    bl_label = "Export Rig Updates to JSON for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export changes to Rigs exported from JSON back to JSON"
    filename_ext = ".rig.json"
    filter_glob: StringProperty(default="*.rig.json", options={'HIDDEN'})

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout

    def execute(self, context):
        save_rig_to_json(self.filepath)
        return {'FINISHED'}

    def check(self, context):
        # Ensure the file path ends with the correct extension
        if not self.filepath.endswith(self.filename_ext):
            self.filepath += self.filename_ext
        return True

class CP77StreamingSectorExport(Operator,ExportHelper):
    bl_idname = "export_scene.cp77_sector"
    bl_label = "Export Sector Updates for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export changes to Sectors back to project"
    filename_ext = ".cpmodproj"
    filter_glob: StringProperty(default="*.cpmodproj", options={'HIDDEN'})

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "axl_yaml")

    def execute(self, context):
        use_yaml = context.scene.cp77_panel_props.axl_yaml
        exportSectors(self.filepath, use_yaml)
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

    filepath: StringProperty(subtype="FILE_PATH")

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

    apply_transform: BoolProperty(
        name="Apply Transform",
        default=True,
        description="Applies the transform of the objects. Disable this if you don't care about the location/rotation/scale of the objects"
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
            row = layout.row(align=True)
            row.prop(self, "apply_transform")


    def execute(self, context):
        export_cyberpunk_glb(
            context=context,
            filepath=self.filepath,
            export_poses=self.export_poses,
            export_visible=self.export_visible,
            limit_selected=self.limit_selected,
            static_prop=self.static_prop,
            apply_transform=self.apply_transform,
        )
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
    bl_description = "Export selected material to a mlsetup json file which can be imported in WolvenKit"

    filepath: StringProperty(subtype="FILE_PATH")

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        layout.prop(props, "write_mltemplate")

    def invoke(self, context, event):
        try:
            self.filepath = cp77_mlsetup_getpath(self, context)
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        except TypeError as e:
            show_message(e.args[0])
            return {'CANCELLED'}
        except ValueError as e:
            show_message(e.args[0])
            return {'CANCELLED'}


    def execute(self, context):
        write_mltemplate = context.scene.cp77_panel_props.write_mltemplate
        cp77_mlsetup_export(self, context, self.filepath, write_mltemplate)
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
    self.layout.operator(CP77RigJSONExport.bl_idname, text="Cyberpunk Rig to JSON", icon_value=get_icon("WKIT"))

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