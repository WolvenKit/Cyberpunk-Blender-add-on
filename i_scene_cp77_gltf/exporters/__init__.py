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

class CP77CollectionExport(Operator, ExportHelper):
    bl_idname = "export_scene.cp77_collection_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"

    # For folder export
    directory: StringProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Export Folder",
        description="Folder where GLB files will be saved",
        subtype='DIR_PATH',
        default="",
    )

    only_visible: BoolProperty(  # pyright: ignore[reportInvalidTypeForm]
        name="Only Visible",
        default=False,
        description="Check this to export only collections that are currently visible in view port"
    )

    is_skinned: BoolProperty( # pyright: ignore[reportInvalidTypeForm]
        name="Skinned Mesh",
        default=True,
        description="Ensure armatures and vert groups are exported."
    )
    try_fix: BoolProperty( # pyright: ignore[reportInvalidTypeForm]
        name="Fix Meshes",
        default=False,
        description="Try to fix any issues "
    )

    export_poses: BoolProperty( # pyright: ignore[reportInvalidTypeForm]
        name="Animations",
        default=False,
        description="Use this option if you are exporting anims to be imported into wkit as .anim"
    )

    apply_transform: BoolProperty( # pyright: ignore[reportInvalidTypeForm]
        name="Apply Transform",
        default=True,
        description="Applies the transform of the objects. Disable this if you don't care about the location/rotation/scale of the objects"
    )

    apply_modifiers: BoolProperty( # pyright: ignore[reportInvalidTypeForm]
        name="Apply Modifiers",
        default=True,
        description="Applies the modifiers of the objects. Disable this if you have shapekeys."
    )
    export_tracks: BoolProperty( # pyright: ignore[reportInvalidTypeForm]
        name="Export Float Tracks",
        default=True,
        description="Transfer Float F-Curves Back to Custom Props for Wolvenkit Import"
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Export Options')
        row = box.row(align=True)
        row.prop(self, "only_visible")
        row = box.row(align=True)
        row.prop(self, "export_poses")
        if  self.export_poses:
            row.prop(self, "export_tracks")
            return

        row = box.row(align=True)
        row.prop(self, "is_skinned")
        row.prop(self, "try_fix")
        row = layout.row(align=True)
        row.prop(self, "apply_transform")
        row.prop(self, "apply_modifiers")


    def format_export_results_detailed(self, export_status, directory):
        exported = []
        export_skipped = []

        for name, error in export_status:
            if error:
                export_skipped.append((name, error))
            else:
                exported.append(name)

        # Build parts
        parts = []

        # Success section
        parts.append(f"exported to {directory}:")
        if exported:
            parts.append("  " + "\n  ".join([f"✓ {name}" for name in exported]))
        else:
            parts.append("  (no successful exports)")

        # Failed/skipped section (only if needed)
        if export_skipped:
            parts.append("export skipped or failed:")
            parts.append("  " + "\n  ".join([f"✗ {name}: {error}" for name, error in export_skipped]))

        return "\n".join(parts)


    def execute(self, context):
        export_status = export_cyberpunk_collections_glb(
            context=context,
            filepath=self.directory,
            export_poses=self.export_poses,
            is_skinned=self.is_skinned,
            try_fix=self.try_fix,
            apply_transform=self.apply_transform,
            apply_modifiers=self.apply_transform,
            export_tracks=self.export_tracks,
            only_visible=self.only_visible,
        )

        self.report({'INFO'}, self.format_export_results_detailed(export_status, self.filepath))
        return {'FINISHED'}

class CP77GLBExport(Operator,ExportHelper):
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"

    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})

    filepath: StringProperty(subtype="FILE_PATH")

    limit_selected: BoolProperty(
        name="Limit to Selected Meshes",
        default=True,
        description="Only Export the Selected Meshes. This is probably the setting you want to use"
    )

    is_skinned: BoolProperty(
        name="Skinned Mesh",
        default=True,
        description="Ensure armatures and vert groups are exported."
    )
    try_fix: BoolProperty(
        name="Fix Meshes",
        default=False,
        description="Try to fix any issues "
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

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        default=True,
        description="Applies the modifiers of the objects. Disable this if you have shapekeys."
    )
    export_tracks: BoolProperty(
        name="Export Float Tracks",
        default=True,
        description="Transfer Float F-Curves Back to Custom Props for Wolvenkit Import"
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Export Options')
        row = box.row(align=True)
        row.prop(self, "export_poses")
        if not self.export_poses:
            row = box.row(align=True)
            row.prop(self, "is_skinned")
            row.prop(self, "try_fix")
            row = box.row(align=True)
            row.prop(self, "limit_selected")
            if not self.limit_selected:
                row = box.row(align=True)
                row.prop(self, "export_visible")
            row = layout.row(align=True)
            row.prop(self, "apply_transform")
            row.prop(self, "apply_modifiers")
        else:
            row.prop(self, "export_tracks")


    def execute(self, context):
        export_cyberpunk_glb(
            context=context,
            filepath=self.filepath,
            export_poses=self.export_poses,
            export_visible=self.export_visible,
            limit_selected=self.limit_selected,
            is_skinned=self.is_skinned,
            try_fix=self.try_fix,
            apply_transform=self.apply_transform,
            apply_modifiers=self.apply_transform,
            export_tracks=self.export_tracks,
        )
        return {'FINISHED'}

class CP77HairProfileExport(Operator):
    bl_idname = "export_scene.hp"
    bl_label = "Export Hair Profile"
    bl_description ="Generates a new .hp.json in your mod project folder which can be imported in Wolvenkit"
    bl_parent_id = "CP77_PT_MaterialTools"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        cp77_hp_export(self.filepath)
        return {"FINISHED"}

class CP77MlSetupExport(Operator):
    bl_idname = "export_scene.mlsetup"
    bl_label = "Export MLSetup"
    bl_parent_id = "CP77_PT_MaterialTools"
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
    self.layout.operator(CP77CollectionExport.bl_idname, text="Cyberpunk Collections", icon_value=get_icon("WKIT"))
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
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)
    TOPBAR_MT_file_export.remove(menu_func_export)
