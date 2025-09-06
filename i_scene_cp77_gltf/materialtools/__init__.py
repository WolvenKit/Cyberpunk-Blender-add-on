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
import numpy as np


last_palette = None

def apply_mltemplate_mlsetup():
    bpy.ops.set_layer_mltemplate.mlsetup()

def check_palette_change(self,context):
    global last_palette
    ts = context.tool_settings
    active_palette = ts.gpencil_paint.palette

    if active_palette != last_palette:
        bpy.app.timers.register(apply_mltemplate_mlsetup)

    last_palette = ts.gpencil_paint.palette


last_palette_color = None

def apply_color_mlsetup():
    bpy.ops.set_layer_color.mlsetup()

def check_palette_col_change(self, context):
    global last_palette_color
    ts = context.tool_settings
    palette = ts.gpencil_paint.palette

    if palette:
        new_palette_color = palette.colors.active.color
        if new_palette_color != last_palette_color:
            bpy.app.timers.register(apply_color_mlsetup)

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
    nt = bpy.context.object.active_material.node_tree
    ml_nodename = 'Mat_Mod_Layer_'

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
            err=sum(np.subtract(col_tuple,colorscale))
            # JATO: TODO test error tolerance numbers, 0.00005 just a random guess
            # JATO: 0.00005 causes color mismatch on panam pants group #3 / layer 4, narrowed to 0.00001
            if abs(err)<0.00001:
                break
        bpy.context.tool_settings.gpencil_paint.palette.colors.active = pal_col


# JATO: TODO idk where this should go, probably somewhere else?
bpy.types.Scene.multilayer_index_prop = bpy.props.IntProperty(
    name="Layer",
    description="Multilayered layer-group index",
    default=1,
    min=1,
    max=20,
    update=setup_mldata
)

# JATO: TODO idk where this should go, probably somewhere else?
bpy.types.Scene.multilayer_view_mask_prop = bpy.props.BoolProperty(
    name="View Layer Mask",
    description="View Layer Mask desc",
    default=False,
    update=bool_function
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

                box.label(text="Materials", icon="MATERIAL")
                col = box.column()
                col.operator("reload_material.cp77")
                col.operator("export_scene.hp")

                box.label(text="MULTILAYERED")
                col = box.column()

                col.operator("generate_layer_overrides.mlsetup")
                col.operator("export_scene.mlsetup")
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
                # JATO: probably don't need this button for applying mltemplate since we are doing this automatically
                # if ts.gpencil_paint.palette:
                #     col.operator("set_layer_mltemplate.mlsetup")

                # JATO: shouldn't need this button since we can set color by selecting palette colors
                # col.operator("set_layer_color.mlsetup")

                palette_box = box.column()
                palette_box.template_palette(ts.gpencil_paint,"palette",color=True)


                if ts.gpencil_paint.palette:
                    colR, colG, colB = palette.colors.active.color
                    rowColor.label(text="Color  {:.4f}  {:.4f}  {:.4f}".format(colR, colG, colB))



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


def unregister_materialtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)