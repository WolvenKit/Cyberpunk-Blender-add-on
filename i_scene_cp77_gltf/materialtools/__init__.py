import bpy
import bpy.utils.previews
import sys
from .. exporters import CP77HairProfileExport, mlsetup_export
from ..main.bartmoss_functions import *
from ..main.common import get_classes, get_color_presets, save_presets
from bpy.props import (StringProperty, EnumProperty, PointerProperty)
from bpy.types import (Scene, Operator, Panel)
from ..cyber_props import CP77RefitList
from ..icons.cp77_icons import get_icon
import numpy as np
import ast


last_active_object = None

def active_object_listener(self,context):
    global last_active_object
    if bpy.context.active_object != last_active_object:
        bpy.app.timers.register(set_multilayer_index)
    last_active_object = bpy.context.active_object

def set_multilayer_index():
    # Remove palette first to prevent setting errant color
    bpy.context.tool_settings.gpencil_paint.palette = None
    bpy.context.scene.multilayer_index_prop = 1


last_palette = None

def apply_mltemplate_mlsetup():
    bpy.ops.set_layer_mltemplate.mlsetup()

def apply_microblend_mlsetup(self,context):
     bpy.ops.apply_microblend.mlsetup()

def check_palette_change(self,context):
    global last_palette

    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette

    if active_palette != last_palette:
        bpy.app.timers.register(apply_mltemplate_mlsetup)

    last_palette = ts.gpencil_paint.palette


last_palette_color = None

def apply_mlsetup_color_override():
    bpy.ops.apply_color_override.mlsetup()

def check_palette_col_change(self, context):
    global last_palette_color
    ts = context.tool_settings
    palette = ts.gpencil_paint.palette

    if palette:
        new_palette_color = palette.colors.active.color
        if new_palette_color != last_palette_color:
            bpy.app.timers.register(apply_mlsetup_color_override)

        last_palette_color = palette.colors.active.color


def bool_function(self, context):
    nt = bpy.context.object.active_material.node_tree
    nodes = nt.nodes

    if context.scene.multilayer_view_mask_prop == True:
        ml_nodename = 'Mat_Mod_Layer_'

        if not nodes.get('Multilayered Mask Output'):
            view_mask_output_node = nodes.new(type='ShaderNodeOutputMaterial')
            view_mask_output_node.name = "Multilayered Mask Output"
            view_mask_output_node.location = (-1000, 400)
            view_mask_output_node.is_active_output = True
        else:
            view_mask_output_node = nodes.get('Multilayered Mask Output')
            view_mask_output_node.is_active_output = True

        # JATO: TODO is else statement required?
        if self.multilayer_index_prop:
            ml_idx = (bpy.context.scene.multilayer_index_prop) - 1
        else:
            self.report({'ERROR'}, 'Multilayered index property not found.')
            return {'CANCELLED'}

        # JATO: TODO more effecient to deselect all then break when we match?
        ml_nodegroup = ml_nodename + str(ml_idx)
        for node in nt.nodes:
            if node.name == ml_nodegroup:
                node.select = True
                nt.links.new(node.outputs[5], view_mask_output_node.inputs[0])
                #print("matched: ", idx)
            else:
                node.select = False
    else:
        nodes.remove(nodes.get('Multilayered Mask Output'))

def setup_mldata(self, context):
    if bpy.context.object is None:
        return
    if bpy.context.object.active_material and not bpy.context.object.active_material.get('MLSetup'):
        return
    nt = bpy.context.object.active_material.node_tree
    
    ml_nodename = 'Mat_Mod_Layer_'

    # JATO: TODO test error tolerance numbers
    # JATO: 0.00005 causes color mismatch on panam pants group #3 / layer 4, narrowed to 0.00001
    matchTolerance = 0.00001

    # JATO: TODO is else statement required?
    if self.multilayer_index_prop:
        ml_idx = (bpy.context.scene.multilayer_index_prop) - 1
    else:
        self.report({'ERROR'}, 'Multilayered index property not found.')
        return {'CANCELLED'}

    if context.scene.multilayer_view_mask_prop == True:
        bool_function(self, context)

    # JATO: TODO more effecient to deselect all then break when we match?
    ml_nodegroup = ml_nodename + str(ml_idx)
    for node in nt.nodes:
        if node.name == ml_nodegroup:
            node.select = True
            colorscale = (node.inputs['ColorScale'].default_value[::])[:-1]
            normstr = (node.inputs['NormalStrength'].default_value)
            metin = (node.inputs['MetalLevelsIn'].default_value[::])
            metout = (node.inputs['MetalLevelsOut'].default_value[::])
            rouin = (node.inputs['RoughLevelsIn'].default_value[::])
            rouout = (node.inputs['RoughLevelsOut'].default_value[::])
            #print("matched: ", idx)
        else:
            node.select = False

    # JATO: We get overrides after selecting the right layer and before matching palette color
    bpy.ops.get_layer_overrides.mlsetup()

    active_palette = bpy.context.tool_settings.gpencil_paint.palette
    if active_palette:
        palette_colors = active_palette.colors

        for pal_col in palette_colors:
            col_tuple= pal_col.color[:]
            err=np.sum(np.abs(np.subtract(col_tuple,colorscale)))
            if abs(err)<matchTolerance:
                break

        for elem_nrmstr in active_palette['NormalStrengthList']:
            elem_nrmstr_float = float(elem_nrmstr)
            err=np.sum(np.subtract(elem_nrmstr_float,normstr))
            if abs(err)<matchTolerance:
                break

        for elem_metin in active_palette['MetalLevelsInList']:
            elem_metin_list = ast.literal_eval(elem_metin)
            err=np.sum(np.abs(np.subtract(elem_metin_list,metin)))
            if abs(err)<matchTolerance:
                break

        for elem_metout in active_palette['MetalLevelsOutList']:
            elem_metout_list = ast.literal_eval(elem_metout)
            err=np.sum(np.abs(np.subtract(elem_metout_list,metout)))
            if abs(err)<matchTolerance:
                break

        for elem_rouin in active_palette['RoughLevelsInList']:
            elem_rouin_list = ast.literal_eval(elem_rouin)
            err=np.sum(np.abs(np.subtract(elem_rouin_list,rouin)))
            if abs(err)<matchTolerance:
                break

        for elem_rouout in active_palette['RoughLevelsOutList']:
            elem_rouout_list = ast.literal_eval(elem_rouout)
            err=np.sum(np.abs(np.subtract(elem_rouout_list,rouout)))
            if abs(err)<matchTolerance:
                break

        bpy.context.tool_settings.gpencil_paint.palette.colors.active = pal_col
        bpy.context.scene.multilayer_normalstr_enum = elem_nrmstr
        bpy.context.scene.multilayer_metalin_enum = elem_metin
        bpy.context.scene.multilayer_metalout_enum = elem_metout
        bpy.context.scene.multilayer_roughin_enum = elem_rouin
        bpy.context.scene.multilayer_roughout_enum = elem_rouout


def get_normalstr_ovrd(self, context):
    normal_str_list = []
    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette
    if active_palette:
        for x in active_palette['NormalStrengthList']:
            normal_str_list.append((x, x, f"Select {x}"))
        return normal_str_list
def get_metalin_ovrd(self, context):
    metal_in_list = []
    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette
    if active_palette:
        for x in active_palette['MetalLevelsInList']:
            metal_in_list.append((x, x, f"Select {x}"))
        return metal_in_list
def get_metalout_ovrd(self, context):
    metal_out_list = []
    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette
    if active_palette:
        for x in active_palette['MetalLevelsOutList']:
            metal_out_list.append((x, x, f"Select {x}"))
        return metal_out_list
def get_roughin_ovrd(self, context):
    rough_in_list = []
    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette
    if active_palette:
        for x in active_palette['RoughLevelsInList']:
            rough_in_list.append((x, x, f"Select {x}"))
        return rough_in_list
def get_roughout_ovrd(self, context):
    rough_out_list = []
    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette
    if active_palette:
        for x in active_palette['RoughLevelsOutList']:
            rough_out_list.append((x, x, f"Select {x}"))
        return rough_out_list

def apply_normalstr_ovrd(self, context):
    bpy.ops.apply_normalstr_override.mlsetup()
def apply_metalin_ovrd(self, context):
    bpy.ops.apply_metalin_override.mlsetup()
def apply_metalout_ovrd(self, context):
    bpy.ops.apply_metalout_override.mlsetup()
def apply_roughin_ovrd(self, context):
    bpy.ops.apply_roughin_override.mlsetup()
def apply_roughout_ovrd(self, context):
    bpy.ops.apply_roughout_override.mlsetup()

# JATO: TODO idk where these props should go, probably somewhere else?
bpy.types.Scene.multilayer_index_prop = bpy.props.IntProperty(
    name="Layer",
    description="Multilayered layer-group index",
    default=1,
    min=1,
    max=20,
    update=setup_mldata
)
bpy.types.Scene.multilayer_view_mask_prop = bpy.props.BoolProperty(
    name="View Layer Mask",
    description="View Layer Mask desc",
    default=False,
    update=bool_function
)
bpy.types.Scene.multilayer_normalstr_enum = bpy.props.EnumProperty(
    name="NormalStrength",
    description="NormalStrength",
    items=get_normalstr_ovrd,
    update=apply_normalstr_ovrd,
    default=0
)
bpy.types.Scene.multilayer_metalin_enum = bpy.props.EnumProperty(
    name="MetalLevelsIn",
    description="MetalLevelsIn",
    items=get_metalin_ovrd,
    update=apply_metalin_ovrd,
    default=0
)
bpy.types.Scene.multilayer_metalout_enum = bpy.props.EnumProperty(
    name="MetalLevelsOut",
    description="MetalLevelsOut",
    items=get_metalout_ovrd,
    update=apply_metalout_ovrd,
    default=0
)
bpy.types.Scene.multilayer_roughin_enum = bpy.props.EnumProperty(
    name="RoughLevelsIn",
    description="RoughLevelsIn",
    items=get_roughin_ovrd,
    update=apply_roughin_ovrd,
    default=0
)
bpy.types.Scene.multilayer_roughout_enum = bpy.props.EnumProperty(
    name="RoughLevelsOut",
    description="RoughLevelsOut",
    items=get_roughout_ovrd,
    update=apply_roughout_ovrd,
    default=0
)

bpy.types.Scene.multilayer_microblend_pointer = bpy.props.PointerProperty(
    type=bpy.types.Image,
    name="Microblend",
    update=apply_microblend_mlsetup
)


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
        scene = context.scene
        box = layout.box()
        props = context.scene.cp77_panel_props

        # JATO: can be used to display selected node name
        # nt = bpy.context.object.active_material.node_tree
        # selected_nodes = [n for n in nt.nodes if n.select]

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_meshtools:
                ts = context.tool_settings
                palette = ts.gpencil_paint.palette

                active_palette = bpy.context.tool_settings.gpencil_paint.palette

                box.label(text="Materials", icon="MATERIAL")
                col = box.column()
                col.operator("reload_material.cp77")
                col.operator("export_scene.hp")

                box.label(text="MULTILAYERED")
                col = box.column()

                col.operator("generate_layer_overrides.mlsetup")
                col.operator("export_scene.mlsetup")

                if not active_palette:
                    col.label(text='Generate Overrides or select a multilayered object')
                    return
                if 'MLTemplatePath' not in active_palette:
                    col.label(text='Generate Overrides or select a multilayered object')
                    return

                col.prop(scene, "multilayer_index_prop")
                col.prop(scene, "multilayer_view_mask_prop")

                rowColor = box.row(align=True)

                # Row for showing currently selected node
                # rowMat = box.row(align=True)
                # if selected_nodes:
                #     rowMat.label(text=f"Selected: {selected_nodes[0].name}")
                # else:
                #     rowMat.label(text="No Node Selected")

                # JATO: we probably don't need a button because this op automatically fires now
                #col.operator("get_layer_overrides.mlsetup")

                col.template_ID(ts.gpencil_paint, "palette", new="palette.new")

                col.label(text=str(active_palette['MLTemplatePath']))
                col.prop(scene, "multilayer_microblend_pointer")
                col.prop(scene, "multilayer_normalstr_enum")
                col.prop(scene, "multilayer_metalin_enum")
                col.prop(scene, "multilayer_metalout_enum")
                col.prop(scene, "multilayer_roughin_enum")
                col.prop(scene, "multilayer_roughout_enum")

                # JATO: probably don't need this button for applying mltemplate since we are doing this automatically
                # if ts.gpencil_paint.palette:
                #     col.operator("set_layer_mltemplate.mlsetup")

                # JATO: shouldn't need this button since we can set color by selecting palette colors
                # col.operator("apply_all_overrides.mlsetup")

                palette_box = box.column()
                palette_box.template_palette(ts.gpencil_paint,"palette",color=True)

                # if ts.gpencil_paint.palette:
                #     colR, colG, colB = palette.colors.active.color
                #     rowColor.label(text="Color  {:.4f}  {:.4f}  {:.4f}".format(colR, colG, colB))




operators, other_classes = get_classes(sys.modules[__name__])

def register_materialtools():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    CP77_PT_MaterialTools.append(check_palette_change)
    CP77_PT_MaterialTools.append(check_palette_col_change)
    CP77_PT_MaterialTools.append(active_object_listener)

    # bpy.msgbus.subscribe_rna(
    #     key=(bpy.types.Context, "active_object"),
    #     owner=owner,
    #     args=(),
    #     notify=selection_changed_callback,
    # )

def unregister_materialtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)

    # bpy.msgbus.clear_by_owner(owner)