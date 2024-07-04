import bpy
import bpy.utils.previews
import sys
from .. exporters import CP77HairProfileExport, mlsetup_export
from .meshtools import *
from .verttools import *
from ..main.bartmoss_functions import *
from ..main.common import get_classes
from bpy.props import (StringProperty, EnumProperty)
from bpy.types import (Scene, Operator, Panel)
from ..cyber_props import CP77RefitList
from ..icons.cp77_icons import get_icon
import mathutils

class CP77_PT_MeshTools(Panel):
    bl_label = "Mesh Tools"
    bl_idname = "CP77_PT_MeshTools"
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
                box.label(text="Mesh Cleanup", icon_value=get_icon("TRAUMA"))
                row = box.row(align=True)
                split = row.split(factor=0.7,align=True)
                split.label(text="Merge Distance:")
                split.prop(props,"merge_distance", text="", slider=True)
                row = box.row(align=True)
                split = row.split(factor=0.7,align=True)
                split.label(text="Smooth Factor:")
                split.prop(props,"smooth_factor", text="", slider=True)
                row = box.row(align=True)
                row.operator("cp77.submesh_prep")
                row = box.row(align=True)
                row.operator("cp77.group_verts", text="Group Ungrouped Verts")
                row = box.row(align=True)
                row.operator('object.delete_unused_vgroups', text="Delete Unused Vert Groups")
                row = box.row(align=True)
                row.operator("cp77.rotate_obj")
                box = layout.box()
                box.label(icon_value=get_icon("SCULPT"), text="Modelling:")
                row = box.row(align=True)
                if context.active_object and context.active_object.type == 'MESH' and context.object.active_material and context.object.active_material.name == 'UV_Checker':
                    row.operator("cp77.uv_unchecker",  text="Remove UV Checker")
                else:
                    row.operator("cp77.uv_checker", text="UV Checker")
                row = box.row(align=True)
                split = row.split(factor=0.5,align=True)
                split.label(text="Source Mesh:")
                split.prop(props, "mesh_source", text="")
                row = box.row(align=True)
                split = row.split(factor=0.5,align=True)
                split.label(text="Target Mesh:")
                split.prop(props, "mesh_target", text="")
                row = box.row(align=True)
                box.operator("cp77.trans_weights", text="Transfer Vertex Weights")
                box = layout.box()
                box.label(icon_value=get_icon("REFIT"), text="AKL Autofitter:")
                row = box.row(align=True)
                split = row.split(factor=0.29,align=True)
                split.label(text="Shape:")
                split.prop(props, 'refit_json', text="")
                row = box.row(align=True)
                row.operator("cp77.auto_fitter", text="Refit Selected Mesh")
                row.prop(props, 'fbx_rot', text="", icon='LOOP_BACK', toggle=1)
                box = layout.box()
                box.label(icon_value=get_icon("TECH"), text="Modifiers:")
                row = box.row(align=True)
                split = row.split(factor=0.35,align=True)
                split.label(text="Target:")
                split.prop(props, "selected_armature", text="")
                row = box.row(align=True)
                row.operator("cp77.set_armature", text="Change Armature Target")
                box = layout.box()
                box.label(text="Vertex Colours", icon="MATERIAL")
                box.operator("cp77.add_vertex_color_preset")
                box.operator("cp77.apply_vertex_color_preset")   
                box.prop(context.scene, "cp77_vertex_color_preset", text="Select Preset")              
                box = layout.box()
                box.label(text="Material Export", icon="MATERIAL")
                box.operator("export_scene.hp")
                box.operator("export_scene.mlsetup")


class CP77AddVertexColorPreset(Operator):
    bl_idname = "cp77.add_vertex_color_preset"
    bl_label = "Save Vertex Color Preset"
    bl_parent_id = "CP77_PT_MeshTools"

    preset_name: StringProperty(name="Preset Name")
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        min=0.0, max=1.0,
        size=3,
        default=(1, 1, 1)
    )

    def execute(self, context):
        presets = get_colour_presets()
        presets[self.preset_name] = list(self.color)
        save_presets(presets)
        self.report({'INFO'}, f"Preset '{self.preset_name}' added.")
        return {'FINISHED'}

    def invoke(self, context, event):
        tool_settings = context.tool_settings.vertex_paint
        self.color = mathutils.Color.from_scene_linear_to_srgb(tool_settings.brush.color)
        print(self.color)
        return context.window_manager.invoke_props_dialog(self)


class CP77WeightTransfer(Operator):
    bl_idname = 'cp77.trans_weights'
    bl_label = "Transfer weights from one mesh to another"
    bl_description = "Transfer weights from source mesh to target mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Call the trans_weights function with the provided arguments
        result = trans_weights(self, context)
        return {"FINISHED"}
        
# Operator to apply a preset
class CP77ApplyVertexColorPreset(Operator):
    bl_idname = "cp77.apply_vertex_color_preset"
    bl_label = "Apply Vertex Color Preset"

    def execute(self, context):
        preset = Scene.cp77_vertex_color_preset
        if not preset:
            self.report({'ERROR'}, f"Preset '{self.preset_name}' not found.")
            return {'CANCELLED'}

        preset_color = preset.append(1.0)  # Adding alpha value
        initial_mode = context.mode

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            mesh = obj.data
            if not mesh.vertex_colors:
                mesh.vertex_colors.new()

            color_layer = mesh.vertex_colors.active.data

            if initial_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')
                selected_verts = {v.index for v in mesh.vertices if v.select}
                bpy.ops.object.mode_set(mode='EDIT')

                for poly in mesh.polygons:
                    for loop_index in poly.loop_indices:
                        loop_vert_index = mesh.loops[loop_index].vertex_index
                        if loop_vert_index in selected_verts:
                            color_layer[loop_index].color = preset_color
                bpy.ops.object.mode_set(mode='OBJECT')
            else:
                for poly in mesh.polygons:
                    for loop_index in poly.loop_indices:
                        loop_vert_index = mesh.loops[loop_index].vertex_index
                        if mesh.vertices[loop_vert_index].select:
                            color_layer[loop_index].color = preset_color

            mesh.update()

        bpy.ops.object.mode_set(mode=initial_mode)
        self.report({'INFO'}, f"Preset '{self.preset_name}' applied.")
        return {'FINISHED'}


class CP77GroupVerts(Operator):
    bl_idname = "cp77.group_verts"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Assign to Nearest Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Assign ungrouped vertices to their nearest group" 

    def execute(self, context):
        CP77GroupUngroupedVerts(self, context)
        return {'FINISHED'}


class CP77Autofitter(Operator):
    bl_idname = "cp77.auto_fitter"
    bl_label = "Auto Fit"
    bl_description = "Use to automatically fit your mesh to a selection of modified bodies" 
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.cp77_panel_props
        target_body_name = props.refit_json
        target_body_paths, target_body_names = CP77RefitList(context)
        refitter = CP77RefitChecker(self, context)  

        if target_body_name in target_body_names:          
            target_body_path = target_body_paths[target_body_names.index(target_body_name)]
            CP77Refit(context, refitter, target_body_path, target_body_name, props.fbx_rot)

            return {'FINISHED'}


class CP77UVTool(Operator):
    bl_idname = 'cp77.uv_checker'
    bl_label = "UV Checker"
    bl_description = "Apply a texture to assist with UV coordinate mapping"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        CP77UvChecker(self, context)
        return {"FINISHED"}


class CP77UVCheckRemover(Operator):
    bl_idname = 'cp77.uv_unchecker'
    bl_label = "UV Checker"
    bl_description = "revert back to original material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.active_material.name and context.object.active_material.name == 'UV_Checker'
        
    def execute(self, context):
        CP77UvUnChecker(self, context)
        return {"FINISHED"}


class CP77SetArmature(Operator):
    bl_idname = "cp77.set_armature"
    bl_label = "Change Armature Target"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "Change the armature modifier on selected meshes to the target" 
    
    def execute(self, context):
        CP77ArmatureSet(self,context)
        return {'FINISHED'}


class CP77_OT_submesh_prep(Operator):
# based on Rudolph2109's function
    bl_label = "Prep. It!"
    bl_idname = "cp77.submesh_prep"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "Marking seams based on edges boundary loops, merging vertices, correcting and smoothening the normals based on the direction of the faces" 

    def execute(self, context):
        props= context.scene.cp77_panel_props
        CP77SubPrep(self, context, props.smooth_factor, props.merge_distance)
        return {'FINISHED'}


class CP77RotateObj(Operator):
    bl_label = "Change Orientation"
    bl_idname = "cp77.rotate_obj"
    bl_description = "rotate the selected object"
    
    def execute(self, context):
        rotate_quat_180(self, context)
        return {'FINISHED'}

operators, other_classes = get_classes(sys.modules[__name__])

def register_meshtools():
    
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    Scene.cp77_vertex_color_preset = EnumProperty(name="Vertex Color Preset", items=update_presets_items())

def unregister_meshtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    del Scene.cp77_vertex_color_preset