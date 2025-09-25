from bpy_extras.io_utils import ImportHelper
import bpy
import bpy.utils.previews
import sys
import os
from .meshtools import *
from .verttools import *
from ..main.bartmoss_functions import *
from ..main.common import get_active_collection, get_classes, get_color_presets, get_selected_collection, save_presets
from bpy.props import (StringProperty, FloatVectorProperty, FloatProperty, BoolProperty, EnumProperty)
from bpy.types import (Operator, Panel)
from ..cyber_props import CP77RefitList, refit_dir
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
        if not cp77_addon_prefs.show_modtools or not cp77_addon_prefs.show_meshtools:
            return

        box.label(icon_value=get_icon("SCULPT"), text="Modelling:")
        col = box.column()
        col.operator("cp77.set_armature", text="Change Armature Target")
        if context.active_object and context.active_object.type == 'MESH' and context.object.active_material and context.object.active_material.name == 'UV_Checker':
            col.operator("cp77.uv_unchecker",  text="Remove UV Checker")
        else:
            col.operator("cp77.uv_checker", text="Apply UV Checker")
        col.operator("cp77.trans_weights", text="Weight Transfer Tool")
        col.operator("cp77.shrinkwrap", text="GarmentSupport/Decal")

        if context.active_object and len([obj for obj in bpy.context.selected_objects if obj.type == 'MESH']) > 1:
            col.operator("cp77.safe_join", text="Join Meshes")
        elif context.active_object and context.active_object.type == 'MESH' and context.active_object.data.materials and any(mat.name.startswith('submesh_') for mat in context.active_object.data.materials if mat):
            col.operator("cp77.safe_split", text="Split into submeshes")

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

# region active vertex group property
def get_vertex_groups(context):
    """Dynamic callback function to get vertex groups from selected objects"""
    items = [('', 'None', 'No vertex group')]
    groups_set = set()

    # Collect vertex groups from all selected objects
    for obj in context.selected_objects:
        if obj.type == 'MESH' and obj.vertex_groups:
            for vg in obj.vertex_groups:
                groups_set.add(vg.name)

    if "Group" in groups_set:
        items.append(("Group", "Group", f"Use 'Group' vertex group"))
        groups_set.remove("Group")
    # Add sorted vertex groups to items
    for vg_name in sorted(groups_set):
        items.append((vg_name, vg_name, f"Use '{vg_name}' vertex group"))

    return items

class Vertex_Group_Properties(bpy.types.PropertyGroup):
    presets: bpy.props.EnumProperty(
        items=lambda self, context: get_vertex_groups(context),
        name='Vertex Group'
    ) # pyright: ignore[reportInvalidTypeForm]

#endregion

class CP77GarmentSupport(Operator):
    bl_idname = 'cp77.shrinkwrap'
    bl_label = "Cyberpunk 2077 Shrinkwrap Tool"
    bl_description = "Shrinkwrap selection on top of another mesh"
    bl_options = {'REGISTER', 'UNDO'}

    mesh_target: StringProperty(name="Mesh Target")  # pyright: ignore[reportInvalidTypeForm]

    as_garment_support: BoolProperty(
        name="As Garment Support",
        description="Modifier is GarmentSupport",
        default=True
    ) # pyright: ignore[reportInvalidTypeForm]

    apply_immediately: BoolProperty(
        name="Apply immediately",
        description="Unchecking this box will preserve the modifier",
        default=True
    ) # pyright: ignore[reportInvalidTypeForm]

    offset: FloatProperty(
        name="Offset",
        description="Offset distance for shrinkwrap",
        default=0.0002,
        step=0.0001,
        precision=5,
    ) # pyright: ignore[reportInvalidTypeForm]

    wrap_method: EnumProperty(

        description="How to wrap your mesh?",
        items=[
            ('NEAREST_SURFACEPOINT', "Nearest Surface Point", "Shrink the mesh to the nearest target surface."),
            ('PROJECT', "Project", "Shrink the mesh to the nearest target surface along a given axis."),
            ('NEAREST_VERTEX', "Nearest Vertex", "Shrink the mesh to the nearest target vertex."),
            ('TARGET_PROJECT', "Target Normal Project", "Shrink the mesh to the nearest target surface along the interpolated vertex normals of the target.")
        ],
        default='NEAREST_SURFACEPOINT'
    ) # pyright: ignore[reportInvalidTypeForm]

    def invoke(self, context, event):
        try:
            context.scene.vertex_group_props.presets = ''  # Reset to trigger refresh
        except Exception as e:
            pass

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        vertex_group = context.scene.vertex_group_props.presets if context.scene.vertex_group_props.presets else None

        return add_shrinkwrap(
            context=context,
            target_collection_name=context.scene.cp77_panel_props.mesh_target,
            offset=self.offset,
            wrap_method=self.wrap_method,
            as_garment_support=self.as_garment_support,
            apply_immediately=self.apply_immediately,
            vertex_group=vertex_group
        )

    def draw(self,context):
        props = context.scene.cp77_panel_props
        vg_props = context.scene.vertex_group_props
        layout = self.layout

        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Target Mesh:")
        split.prop(props, "mesh_target", text="")

        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="As Garment Support:")
        split.prop(self, "as_garment_support")

        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Apply immediately:")
        split.prop(self, "apply_immediately")

        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Offset:")
        split.prop(self, "offset")

        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Wrap Method:")
        split.prop(self, "wrap_method", text="")

        row = layout.row(align=True)
        split = row.split(factor=0.3,align=True)
        split.label(text="Vertex Group:")
        split.prop(vg_props, "presets", text="")

class CP77SafeJoin(Operator):
    bl_idname = "cp77.safe_join"
    bl_label = "Join Selected Meshes"
    bl_description = "Join selected meshes while preserving submesh information"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


    def execute(self, context):
        result = safe_join(self, context)
        return result

class CP77SafeSplit(Operator):
    bl_idname = "cp77.safe_split"
    bl_label = "Split Selected Meshes"
    bl_description = "Split selected mesh back into submeshes"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        result = safe_split(self, context)
        return result

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
        selected_collection = get_selected_collection()
        active_collection = get_active_collection()

        if active_collection and selected_collection and active_collection.name == selected_collection.name:
            active_collection = None

        props = context.scene.cp77_panel_props

        if selected_collection and active_collection:
            props.mesh_source = selected_collection.name
            props.mesh_target = active_collection.name
        elif selected_collection:
            props.mesh_target = selected_collection.name

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
    try_auto_apply: BoolProperty(
        name="Auto Apply",
        description="Attempt to apply the refit geometry as the mesh's new basis upon creation",
        default=False
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props

        # Build selectable lists
        base_paths,  base_names  = CP77RefitList(context)
        addon_paths, addon_names = CP77RefitAddonList(context)

        # Gather the user’s chosen refitters (paths + names in order)
        refitter_paths = []
        names = []

        # Base (required)
        base_choice = props.refit_json
        if base_choice in base_names:
            target_body_path = base_paths[base_names.index(base_choice)]
            refitter_paths.append(target_body_path)
            names.append(base_choice)
        else:
            self.report({'ERROR'}, f"Base refitter '{base_choice}' not found.")
            return {'CANCELLED'}

        # Optional addon
        addon_target_body_path = None
        addon_choice = None
        if self.useAddon:
            addon_choice = props.refit_addon_json
            if addon_choice in addon_names:
                addon_target_body_path = addon_paths[addon_names.index(addon_choice)]
                refitter_paths.append(addon_target_body_path)
                names.append(addon_choice)
            else:
                self.report({'ERROR'}, f"Addon refitter '{addon_choice}' not found.")
                return {'CANCELLED'}
        refitter, addon = CP77RefitChecker(self, context)
        CP77Refit(
            context=context,
            refitter=refitter,
            addon=addon,
            target_body_path=target_body_path,
            target_body_name=base_choice,
            useAddon=self.useAddon,
            addon_target_body_path=addon_target_body_path,
            addon_target_body_name=addon_choice,
            fbx_rot=props.fbx_rot,
            try_auto_apply=self.try_auto_apply
            )

        return {'FINISHED'}

    def draw(self,context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        col = layout.column_flow(columns=2)
        col.prop(props, 'fbx_rot', text="Refit a mesh in FBX orientation")
        col.prop(self, 'useAddon', text="Use a Refitter Addon")
        col = layout.column()
        col.prop(self, 'try_auto_apply', text="Apply to Mesh")
        row = layout.row(align=True)
        split = row.split(factor=0.2,align=True)
        split.label(text="Shape:")
        split.prop(props, 'refit_json', text="")
        if self.useAddon:
            row = layout.row(align=True)
            split = row.split(factor=0.2,align=True)
            split.label(text="Addon:")
            split.prop(props, 'refit_addon_json', text="")

class CP77RefitConvert(Operator,ImportHelper):
    bl_idname = 'cp77.refit_convert'
    bl_label = "Convert Old Refit"
    bl_description = "Convert old .zip refit to new format"
    bl_options = {'REGISTER'}

    filter_glob: StringProperty(
        default="*.refitter.zip",
        options={'HIDDEN'},
        )

    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH')

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        filepath = self.filepath if self.filepath != "" else refit_dir
        if os.path.isdir(filepath):
            for filename in os.listdir(filepath):
                if filename.endswith('.refitter.zip'):
                    full_path = os.path.join(filepath, filename)
                    convert_legacy_lattice(full_path)
        else:
            convert_legacy_lattice(filepath)
        return {"FINISHED"}

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
    bl_options = {'REGISTER', "UNDO"}
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

    bpy.types.Scene.vertex_group_props = bpy.props.PointerProperty(type=Vertex_Group_Properties)

def unregister_meshtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)

    del bpy.types.Scene.vertex_group_props
