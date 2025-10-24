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
import ast

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

class CP77MlSetupGenerateOverrides(Operator):
    bl_idname = "generate_layer_overrides.mlsetup"
    bl_label = "Generate Overrides"
    bl_description = "Create Override data for MLTemplates found within the selected material."

    def execute(self, context):        
        cp77_mlsetup_generateoverrides(self, context)

        bpy.ops.get_layer_overrides.mlsetup()

        # Do this to trigger update function so active color is set when we first generate overrides
        bpy.context.scene.multilayer_index_prop = 1

        # success_message = "Generated overrides for " + mat.name

        # self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupGetOverrides(Operator):
    bl_idname = "get_layer_overrides.mlsetup"
    bl_label = "View Layer Overrides"
    bl_description = "View the Overrides for the MLTemplate within the selected Multilayered Layer Node Group"

    def execute(self, context):
        ts = context.tool_settings
        obj=bpy.context.active_object
        if not obj or obj.material_slots is None or len(obj.material_slots)==0:
            return {'CANCELLED'}
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break # Assuming only one group node can be actively selected at a time

        if selected_node_group == None:
            self.report({'ERROR'}, 'A valid Multilayered node group was not selected.')
            return {'CANCELLED'}

        BaseMat = selected_node_group.node_tree.nodes['Group'].node_tree.nodes['Group Input']
        material = str(BaseMat['mlTemplate'])
        smallmaterial = ((material.split('\\'))[-1])[:-11]

        microblendtexnode = selected_node_group.node_tree.nodes['Image Texture']
        bpy.context.scene.multilayer_microblend_pointer = microblendtexnode.image

        match_palette = None
        for palette in bpy.data.palettes:
            if palette.name == smallmaterial:
                match_palette = palette
        ts.gpencil_paint.palette = match_palette

        # success_message = "Overrides found for " + str(selected_node_group.name) + " (" +str(smallmaterial) + ")"

        # self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyColorOverride(Operator):
    bl_idname = "apply_color_override.mlsetup"
    bl_label = "Apply Color Override"
    bl_description = "Apply the current color override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        ts = context.tool_settings

        if 'MLTemplatePath' not in ts.gpencil_paint.palette:
            self.report({'ERROR'}, 'MLTEMPLATE path not found on active palette.')
            return {'CANCELLED'}

        palette = ts.gpencil_paint.palette
        if ts.gpencil_paint.palette:
            colR, colG, colB = palette.colors.active.color
            active_color = (colR, colG, colB, 1)

        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break # Assuming only one group node can be actively selected at a time
        selected_node_group.inputs['ColorScale'].default_value = active_color

        #success_message = "{:.4f}  {:.4f}  {:.4f}".format(colR, colG, colB) + " was set on " + str(selected_node_group.name)

        #self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyNormalStrOverride(Operator):
    bl_idname = "apply_normalstr_override.mlsetup"
    bl_label = "Apply NormalStrength Override"
    bl_description = "Apply the NormalStrength override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break
        selected_node_group.inputs['NormalStrength'].default_value = float(bpy.context.scene.multilayer_normalstr_enum)

        #success_message = """

        #self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyMetalLevelsInOverride(Operator):
    bl_idname = "apply_metalin_override.mlsetup"
    bl_label = "Apply MetalLevelsIn Override"
    bl_description = "Apply the MetalLevelsIn override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break
        selected_node_group.inputs['MetalLevelsIn'].default_value = ast.literal_eval(bpy.context.scene.multilayer_metalin_enum)

        #success_message = ""

        #self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyMetalLevelsOutOverride(Operator):
    bl_idname = "apply_metalout_override.mlsetup"
    bl_label = "Apply MetalLevelsOut Override"
    bl_description = "Apply the MetalLevelsOut override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break
        selected_node_group.inputs['MetalLevelsOut'].default_value = ast.literal_eval(bpy.context.scene.multilayer_metalout_enum)

        #success_message = ""

        #self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyRoughLevelsInOverride(Operator):
    bl_idname = "apply_roughin_override.mlsetup"
    bl_label = "Apply RoughLevelsIn Override"
    bl_description = "Apply the RoughLevelsIn override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break

        selected_node_group.inputs['RoughLevelsIn'].default_value = ast.literal_eval(bpy.context.scene.multilayer_roughin_enum)

        #success_message = ""

        #self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyRoughLevelsOutOverride(Operator):
    bl_idname = "apply_roughout_override.mlsetup"
    bl_label = "Apply RoughLevelsOut Override"
    bl_description = "Apply the RoughLevelsOut override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break

        selected_node_group.inputs['RoughLevelsOut'].default_value = ast.literal_eval(bpy.context.scene.multilayer_roughout_enum)

        #success_message = ""

        #self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyMLTemplate(Operator):
    bl_idname = "set_layer_mltemplate.mlsetup"
    bl_label = "Apply Selected MLTemplate"
    bl_description = "Apply the selected MLTemplate within the selected Multilayered Layer Node Group"

    # JATO: TODO Stop this operator from running when changing layer index in panel UI
    # JATO: TODO within big scenes (for ng in bpy.data.node_groups:) causes lag when changing layer index

    def execute(self, context):
        ts = context.tool_settings

        if not ts.gpencil_paint.palette:
            self.report({'WARNING'}, 'No active palette to match with MLTEMPLATE.')
            return {'CANCELLED'}

        if 'MLTemplatePath' not in ts.gpencil_paint.palette:
            self.report({'WARNING'}, 'MLTEMPLATE path not found on active palette.')
            return {'CANCELLED'}

        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        nodes=mat.node_tree.nodes
        if not mat.get('MLSetup'):
            self.report({'WARNING'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break # Assuming only one group node can be actively selected at a time

        if selected_node_group == None:
            self.report({'WARNING'}, 'A valid Multilayered node group was not selected.')
            return {'CANCELLED'}

        ngmatch = None
        for ng in bpy.data.node_groups:
            if 'mlTemplate' in ng:
                if ng['mlTemplate'] == ts.gpencil_paint.palette['MLTemplatePath']:
                    ngmatch = ng
        selected_node_group.node_tree.nodes['Group'].node_tree = ngmatch

        # success_message = ""

        # self.report({'INFO'}, success_message)
        return {'FINISHED'}

class CP77MlSetupApplyMicroblend(Operator):
    bl_idname = "apply_microblend.mlsetup"
    bl_label = "Apply Microblend"
    bl_description = "Apply the Microblend to the selected Multilayered Layer Node Group"

    def execute(self, context):
        ts = context.tool_settings
        obj=bpy.context.active_object
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        if not mat.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        node_tree = bpy.context.object.active_material.node_tree
        selected_node_group = None
        for node in node_tree.nodes:
            if node.select and node.type == 'GROUP':
                selected_node_group = node
                break # Assuming only one group node can be actively selected at a time

        if selected_node_group == None:
            self.report({'ERROR'}, 'A valid Multilayered node group was not selected.')
            return {'CANCELLED'}

        microblendtexnode = selected_node_group.node_tree.nodes['Image Texture']
        microblendtexnode.image = bpy.context.scene.multilayer_microblend_pointer

        # success_message = ""

        # self.report({'INFO'}, success_message)
        return {'FINISHED'}

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
