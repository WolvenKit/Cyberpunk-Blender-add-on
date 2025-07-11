import bpy
import bpy.utils.previews
import sys
from .. exporters import CP77HairProfileExport, mlsetup_export
from .meshtools import *
from .verttools import *
from ..main.bartmoss_functions import *
from ..main.common import get_classes, get_color_presets, save_presets
from bpy.props import (StringProperty, EnumProperty)
from bpy.types import (Scene, Operator, Panel)
from ..cyber_props import CP77RefitList
from ..icons.cp77_icons import get_icon

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
        box.operator("cp77.rotate_obj", text="Rotate Selected Objects")
        box = layout.box()
        props = context.scene.cp77_panel_props

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_meshtools:
                box.label(icon_value=get_icon("SCULPT"), text="Modelling:")
                col = box.column()
                col.operator("cp77.set_armature", text="Change Armature Target")
                if context.active_object and context.active_object.type == 'MESH' and context.object.active_material and context.object.active_material.name == 'UV_Checker':
                    col.operator("cp77.uv_unchecker",  text="Remove UV Checker")
                else:
                    col.operator("cp77.uv_checker", text="Apply UV Checker")
                col.operator("cp77.trans_weights", text="Weight Transfer Tool")

                box = layout.box()
                box.label(text="Mesh Cleanup", icon_value=get_icon("TRAUMA"))
                col = box.column()
                col.operator("cp77.submesh_prep")
                col.operator("cp77.group_verts", text="Group Ungrouped Verts")
                col.operator("cp77.del_empty_vgroup", text="Delete Unused Vert Groups")

                box = layout.box()
                box.label(text="AKL Autofitter", icon_value=get_icon("REFIT"))
                col = box.column()
                col.operator("cp77.auto_fitter", text="Refit Selected Meshes")

                box = layout.box()
                box.label(text="Vertex Colours", icon="BRUSH_DATA")
                col = box.column()
                col.operator("cp77.apply_vertex_color_preset")
                col.operator("cp77.add_vertex_color_preset")
                col.operator("cp77.delete_vertex_color_preset")

                box = layout.box()
                box.label(text="Material Export", icon="MATERIAL")
                col = box.column()
                col.operator("export_scene.hp")
                col.operator("export_scene.mlsetup")

class CP77DeleteVertexcolorPreset(Operator):
    bl_idname = "cp77.delete_vertex_color_preset"
    bl_label = "Delete Vertex Colour Preset"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        preset_name = props.vertex_color_presets
        presets = get_color_presets()
        if preset_name in presets:
            del presets[preset_name]
            save_presets(presets)
            self.report({'INFO'}, f"Preset '{preset_name}' deleted.")
        else:
            self.report({'ERROR'}, f"Preset '{preset_name}' not found.")
            return {'CANCELLED'}

        return {'FINISHED'}

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.275,align=True)
        split.label(text="Preset:")
        split.prop(props, "vertex_color_presets", text="")

class CP77AddVertexcolorPreset(Operator):
    bl_idname = "cp77.add_vertex_color_preset"
    bl_label = "Save Vertex Colour Preset"
    bl_parent_id = "CP77_PT_MeshTools"

    preset_name: StringProperty(name="Preset Name")
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        min=0.0, max=1.0,
        size=4,
        default=(1, 1, 1, 1)  # Include alpha in default
    )

    def execute(self, context):
        presets = get_color_presets()
        presets[self.preset_name] = list(self.color)
        save_presets(presets)
        self.report({'INFO'}, f"Preset '{self.preset_name}' added.")
        return {'FINISHED'}

    def invoke(self, context, event):
        tool_settings = context.tool_settings.vertex_paint
        color = tool_settings.brush.color
        alpha = tool_settings.brush.strength  # Assuming alpha can be taken from brush strength
        self.color = (*color[:3], alpha)  # Combine color and alpha
        print(self.color)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "color", text="")
        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Preset Name:")
        split.prop(self, "preset_name", text="")

class CP77WeightTransfer(Operator):
    bl_idname = 'cp77.trans_weights'
    bl_label = "Cyberpunk 2077 Weight Transfer Tool"
    bl_description = "Transfer weights from source mesh to target mesh"
    vertInterop: BoolProperty(
        name="Use Nearest Vert Interpolated",
        description="Sometimes gives better results when the default mode fails",
        default=False)
    bySubmesh: BoolProperty(
        name="Transfer by Submesh Order",
        description="Because Mana Gets what Mana Wants :D",
        default=False)
    bl_options = {'REGISTER', 'UNDO'}


    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # Call the trans_weights function with the provided arguments
        result = trans_weights(self, context, self.properties.vertInterop ) #, self.properties.bySubmesh)
        return {"FINISHED"}

    def draw(self,context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Source Mesh:")
        split.prop(props, "mesh_source", text="")
        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Target Mesh:")
        split.prop(props, "mesh_target", text="")
        row = layout.row(align=True)
        row.prop(self, 'vertInterop', text="Use Nearest Vert Interpolation")
        row = layout.row(align=True)
        row.prop(self, 'bySubmesh')

# Operator to apply a preset
class CP77ApplyVertexcolorPreset(Operator):
    bl_idname = "cp77.apply_vertex_color_preset"
    bl_label = "Apply Vertex Colour Preset"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        preset_name = props.vertex_color_presets
        obj = context.object
        if not obj:
            show_message("No active object. Please Select a Mesh and try again")
            return {'CANCELLED'}
        if obj.type != 'MESH':
            show_message("The active object is not a mesh.")
            return {'CANCELLED'}
        if not preset_name:
            self.report({'ERROR'}, "No preset selected.")
            return {'CANCELLED'}

        presets = get_color_presets()
        preset_color = presets.get(preset_name)
        if not preset_color:
            self.report({'ERROR'}, f"Preset '{preset_name}' not found.")
            return {'CANCELLED'}

        initial_mode = context.mode
        if initial_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            mesh = obj.data
            if not mesh.vertex_colors:
                mesh.vertex_colors.new()

            color_layer = mesh.vertex_colors.active.data

            if initial_mode == 'EDIT_MESH':
                selected_verts = {v.index for v in mesh.vertices if v.select}

                for poly in mesh.polygons:
                    for loop_index in poly.loop_indices:
                        loop_vert_index = mesh.loops[loop_index].vertex_index
                        if loop_vert_index in selected_verts:
                            color_layer[loop_index].color = preset_color
                bpy.ops.object.mode_set(mode='EDIT')
              #  bpy.ops.object.mode_set(mode='OBJECT')
            else:
                for poly in mesh.polygons:
                    for loop_index in poly.loop_indices:
                        loop_vert_index = mesh.loops[loop_index].vertex_index
                        if mesh.vertices[loop_vert_index].select:
                            color_layer[loop_index].color = preset_color
                bpy.ops.object.mode_set(mode=initial_mode)
            mesh.update()


        self.report({'INFO'}, f"Preset '{preset_name}' applied.")
        return {'FINISHED'}

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.275,align=True)
        split.label(text="Preset:")
        split.prop(props, "vertex_color_presets", text="")


class CP77GroupVerts(Operator):
    bl_idname = "cp77.group_verts"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Assign to Nearest Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Assign ungrouped vertices to their nearest group"

    def execute(self, context):
        CP77GroupUngroupedVerts(self, context)
        return {'FINISHED'}

class CP77DeleteVertGroups(Operator):
    bl_idname = "cp77.del_empty_vgroup"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Delete Unused Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Delete empty vertex groups"

    def execute(self, context):
        del_empty_vgroup(self, context)
        return {'FINISHED'}

class CP77Autofitter(Operator):
    bl_idname = "cp77.auto_fitter"
    bl_label = "AKL Autofitter"
    bl_description = "Use to automatically fit your mesh to a selection of modified bodies"
    bl_options = {'REGISTER', 'UNDO'}

    useAddon: BoolProperty(
        name="Use an Addon",
        description="If enabled, a base refitter will be applied, followed by an addon",
        default=False
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        target_body_name = props.refit_json
        addon_target_body_name = props.refit_addon_json
        target_body_paths, target_body_names = CP77RefitList(context)
        addon_target_body_paths, addon_target_body_names = CP77RefitAddonList(context)
        refitter, addon = CP77RefitChecker(self, context)

        if target_body_name in target_body_names:
            target_body_path = target_body_paths[target_body_names.index(target_body_name)]
            if self.useAddon:
                if addon_target_body_name in addon_target_body_names:
                    addon_target_body_path = addon_target_body_paths[addon_target_body_names.index(addon_target_body_name)]
            else:
                addon_target_body_path = None
                addon_target_body_name = None

            CP77Refit(
                context=context,
                refitter=refitter,
                addon=addon,
                target_body_path=target_body_path,
                target_body_name=target_body_name,
                useAddon=self.useAddon,
                addon_target_body_path=addon_target_body_path,
                addon_target_body_name=addon_target_body_name,
                fbx_rot=props.fbx_rot
            )

            return {'FINISHED'}

    def draw(self,context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.2,align=True)
        split.label(text="Shape:")
        split.prop(props, 'refit_json', text="")
        if self.useAddon:
            row = layout.row(align=True)
            split = row.split(factor=0.2,align=True)
            split.label(text="Addon:")
            split.prop(props, 'refit_addon_json', text="")
        col = layout.column()
        col.prop(props, 'fbx_rot', text="Refit a mesh in FBX orientation")
        col.prop(self, 'useAddon', text="Use a Refitter Addon")


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

    reparent: BoolProperty(
        name= "Also Reparent Selected Meshes to the Armature",
        default= True
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        CP77ArmatureSet(self,context, self.reparent)
        return {'FINISHED'}

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.35,align=True)
        split.label(text="Armature Target:")
        split.prop(props, "selected_armature", text="")
        col = layout.column()
        col.prop(self, 'reparent')

class CP77_OT_submesh_prep(Operator):
# based on Rudolph2109's function
    bl_label = "Prep. It!"
    bl_idname = "cp77.submesh_prep"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "Mark seams based on edges boundary loops, merge vertices, correct and smooth normals based on the direction of the faces"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props= context.scene.cp77_panel_props
        CP77SubPrep(self, context, props.smooth_factor, props.merge_distance)
        return {'FINISHED'}

    def draw(self, context):
        props= context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.7,align=True)
        split.label(text="Merge Distance:")
        split.prop(props,"merge_distance", text="", slider=True)
        row = layout.row(align=True)
        split = row.split(factor=0.7,align=True)
        split.label(text="Smooth Factor:")
        split.prop(props,"smooth_factor", text="", slider=True)

class CP77RotateObj(Operator):
    bl_label = "Change Orientation"
    bl_idname = "cp77.rotate_obj"
    bl_description = "Rotate the selected object 180 degrees"

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

def unregister_meshtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
def unregister_meshtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)