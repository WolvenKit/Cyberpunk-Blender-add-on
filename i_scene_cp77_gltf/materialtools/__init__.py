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

def get_layernode_by_socket(self,context):
    if bpy.context.object is None:
        return
    if bpy.context.object.active_material is None:
        return
    if bpy.context.object.active_material.get('MLSetup') is None:
        return

    active_object=bpy.context.active_object
    active_material = active_object.active_material
    LayerGroup = None

    nodes = active_material.node_tree.nodes
    layer_index = bpy.context.scene.multilayer_index_prop

    mlBSDFGroup = nodes.get("Multilayered 1.8.0")
    if mlBSDFGroup:
        socket_name = ("Layer "+str(layer_index))
        socket = mlBSDFGroup.inputs.get(socket_name)
        layerGroupLink = socket.links[0]
        linkedLayerGroupName = layerGroupLink.from_node.name
        LayerGroup=nodes[linkedLayerGroupName]
        # print(layer_index, " | ", LayerGroup.name)

    return LayerGroup


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


def apply_view_mask(self, context):
    if bpy.context.object is None:
        return
    if bpy.context.object.active_material is None:
        return
    if bpy.context.object.active_material.get('MLSetup') is None:
        return
    nt = bpy.context.object.active_material.node_tree
    nodes = nt.nodes

    LayerGroup = get_layernode_by_socket(self,context)

    if context.scene.multilayer_view_mask_prop == True:
        if not nodes.get('Multilayered Mask Output'):
            view_mask_output_node = nodes.new(type='ShaderNodeOutputMaterial')
            view_mask_output_node.name = "Multilayered Mask Output"
            view_mask_output_node.location = (-200, 400)
            view_mask_output_node.is_active_output = True
        else:
            view_mask_output_node = nodes.get('Multilayered Mask Output')
            view_mask_output_node.is_active_output = True

        # LayerGroup.select = True
        nt.links.new(LayerGroup.outputs['Layer Mask'], view_mask_output_node.inputs[0])

    else:
        nodes.remove(nodes.get('Multilayered Mask Output'))

def setup_mldata(self, context):
    if bpy.app.version[0]<5:
        return
    if bpy.context.object is None:
        return
    if bpy.context.object.active_material is None:
        return
    if bpy.context.object.active_material.get('MLSetup') is None:
        return

    LayerGroup = get_layernode_by_socket(self,context)
    if LayerGroup == None:
        # self.report({'ERROR'}, 'A valid Multilayered node group was not found.')
        return

    # JATO: TODO test error tolerance numbers
    # JATO: 0.00005 causes color mismatch on panam pants group #3 / layer 4, narrowed to 0.00001
    matchTolerance = 0.00001

    if context.scene.multilayer_view_mask_prop == True:
        apply_view_mask(self, context)

    # LayerGroup.select = True
    colorscale = (LayerGroup.inputs['ColorScale'].default_value[::])[:-1]
    normstr = (LayerGroup.inputs['NormalStrength'].default_value)
    metin = (LayerGroup.inputs['MetalLevelsIn'].default_value[::])
    metout = (LayerGroup.inputs['MetalLevelsOut'].default_value[::])
    rouin = (LayerGroup.inputs['RoughLevelsIn'].default_value[::])
    rouout = (LayerGroup.inputs['RoughLevelsOut'].default_value[::])

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
    update=apply_view_mask
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
        vers=bpy.app.version

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
                if vers[0]<5:
                    col.label(text='Upgrade to Blender 5 for Multilayer features')
                    return

                col.operator("reload_material.cp77")
                col.operator("export_scene.hp")

                box.label(text="MULTILAYERED")
                col = box.column()

                col.operator("generate_layer_overrides.mlsetup")
                col.operator("generate_layer_overrides_disconnected.mlsetup")
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

class CP77MlSetupGenerateOverrides(Operator):
    bl_idname = "generate_layer_overrides.mlsetup"
    bl_label = "Generate Overrides"
    bl_description = "Create Override data for Layers connected to the Multilayered shader node."

    def execute(self, context):
        mlsetup_export.cp77_mlsetup_generateoverrides(self, context)

        bpy.ops.get_layer_overrides.mlsetup()

        # Do this to trigger update function so active color is set when we first generate overrides
        bpy.context.scene.multilayer_index_prop = 1

        return {'FINISHED'}

class CP77MlSetupGenerateOverridesDisconnected(Operator):
    bl_idname = "generate_layer_overrides_disconnected.mlsetup"
    bl_label = "Generate Overrides for All Nodes"
    bl_description = "Create Override data for Layers using the mat_mod_layer naming scheme found within the selected material. Useful for generating extra multilayer-resources with a modified MLSETUP json."

    def execute(self, context):
        mlsetup_export.cp77_mlsetup_generateoverrides(self, context, include_disconnected=True)

        bpy.ops.get_layer_overrides.mlsetup()

        # Do this to trigger update function so active color is set when we first generate overrides
        bpy.context.scene.multilayer_index_prop = 1

        return {'FINISHED'}

class CP77MlSetupGetOverrides(Operator):
    bl_idname = "get_layer_overrides.mlsetup"
    bl_label = "View Layer Overrides"
    bl_description = "View the Overrides for the MLTemplate within the selected Multilayered Layer Node Group"

    def execute(self, context):
        ts = context.tool_settings
        active_object=bpy.context.active_object
        if not active_object or active_object.material_slots is None or len(active_object.material_slots)==0:
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material.get('MLSetup'):
            self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
            return {'CANCELLED'}

        LayerGroup = get_layernode_by_socket(self,context)

        mlTemplateGroupInputNode = LayerGroup.node_tree.nodes['Group'].node_tree.nodes['Group Input']
        mlTemplatePath = str(mlTemplateGroupInputNode['mlTemplate'])
        mlTemplatePathStripped = ((mlTemplatePath.split('\\'))[-1])[:-11]

        microblendtexnode = LayerGroup.node_tree.nodes['Image Texture']
        bpy.context.scene.multilayer_microblend_pointer = microblendtexnode.image

        # JATO: for performance, first we try getting palette by direct name-match and ensure the mlTemplate path matches
        # If mlTemplate paths don't match try searching all palettes which can be slow
        match_palette = None
        palette_byname = bpy.data.palettes.get(mlTemplatePathStripped)
        if palette_byname:
            if palette_byname['MLTemplatePath'] == mlTemplateGroupInputNode['mlTemplate']:
                match_palette = palette_byname
        else:
            for palette in bpy.data.palettes:
                if palette['MLTemplatePath'] == mlTemplateGroupInputNode['mlTemplate']:
                    match_palette = palette
        if match_palette == None:
            self.report({'WARNING'}, 'A Palette and Node Group with corresponding MLTEMPLATE path were not found.')
            return {'CANCELLED'}

        ts.gpencil_paint.palette = match_palette

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

        LayerGroup = get_layernode_by_socket(self,context)

        LayerGroup.inputs['ColorScale'].default_value = active_color

        return {'FINISHED'}

class CP77MlSetupApplyNormalStrOverride(Operator):
    bl_idname = "apply_normalstr_override.mlsetup"
    bl_label = "Apply NormalStrength Override"
    bl_description = "Apply the NormalStrength override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket(self,context)

        LayerGroup.inputs['NormalStrength'].default_value = float(bpy.context.scene.multilayer_normalstr_enum)

        return {'FINISHED'}

class CP77MlSetupApplyMetalLevelsInOverride(Operator):
    bl_idname = "apply_metalin_override.mlsetup"
    bl_label = "Apply MetalLevelsIn Override"
    bl_description = "Apply the MetalLevelsIn override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket(self,context)

        LayerGroup.inputs['MetalLevelsIn'].default_value = ast.literal_eval(bpy.context.scene.multilayer_metalin_enum)

        return {'FINISHED'}

class CP77MlSetupApplyMetalLevelsOutOverride(Operator):
    bl_idname = "apply_metalout_override.mlsetup"
    bl_label = "Apply MetalLevelsOut Override"
    bl_description = "Apply the MetalLevelsOut override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket(self,context)

        LayerGroup.inputs['MetalLevelsOut'].default_value = ast.literal_eval(bpy.context.scene.multilayer_metalout_enum)

        return {'FINISHED'}

class CP77MlSetupApplyRoughLevelsInOverride(Operator):
    bl_idname = "apply_roughin_override.mlsetup"
    bl_label = "Apply RoughLevelsIn Override"
    bl_description = "Apply the RoughLevelsIn override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket(self,context)

        LayerGroup.inputs['RoughLevelsIn'].default_value = ast.literal_eval(bpy.context.scene.multilayer_roughin_enum)

        return {'FINISHED'}

class CP77MlSetupApplyRoughLevelsOutOverride(Operator):
    bl_idname = "apply_roughout_override.mlsetup"
    bl_label = "Apply RoughLevelsOut Override"
    bl_description = "Apply the RoughLevelsOut override to the selected Multilayered Layer Node Group"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket(self,context)

        LayerGroup.inputs['RoughLevelsOut'].default_value = ast.literal_eval(bpy.context.scene.multilayer_roughout_enum)

        return {'FINISHED'}

class CP77MlSetupApplyMLTemplate(Operator):
    bl_idname = "set_layer_mltemplate.mlsetup"
    bl_label = "Apply Selected MLTemplate"
    bl_description = "Apply the selected MLTemplate within the selected Multilayered Layer Node Group"

    # JATO: TODO Stop this operator from running when changing layer index in panel UI

    def execute(self, context):
        ts = context.tool_settings
        if not ts.gpencil_paint.palette:
            # self.report({'WARNING'}, 'No active palette to match with MLTEMPLATE.')
            return {'CANCELLED'}
        if 'MLTemplatePath' not in ts.gpencil_paint.palette:
            # self.report({'WARNING'}, 'MLTEMPLATE path not found on active palette.')
            return {'CANCELLED'}
        palette_name = ts.gpencil_paint.palette.name

        LayerGroup = get_layernode_by_socket(self,context)
        if LayerGroup == None:
            return

        # JATO: for performance, first we try getting node group by direct name-match and ensure the mlTemplate path matches
        # If mlTemplate paths don't match try searching all node-groups which can be slow
        ngmatch = None
        nodeGroup = bpy.data.node_groups.get(palette_name)
        if nodeGroup['mlTemplate'] == ts.gpencil_paint.palette['MLTemplatePath']:
            ngmatch = nodeGroup
        else:
            for ng in bpy.data.node_groups:
                if 'mlTemplate' in ng:
                    if ng['mlTemplate'] == ts.gpencil_paint.palette['MLTemplatePath']:
                        ngmatch = ng
        if ngmatch == None:
            self.report({'WARNING'}, 'A Palette and Node Group with corresponding MLTEMPLATE path were not found.')
            return {'CANCELLED'}

        LayerGroup.node_tree.nodes['Group'].node_tree = ngmatch

        return {'FINISHED'}

class CP77MlSetupApplyMicroblend(Operator):
    bl_idname = "apply_microblend.mlsetup"
    bl_label = "Apply Microblend"
    bl_description = "Apply the Microblend to the selected Multilayered Layer Node Group"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket(self,context)

        microblendtexnode = LayerGroup.node_tree.nodes['Image Texture']
        microblendtexnode.image = bpy.context.scene.multilayer_microblend_pointer

        return {'FINISHED'}


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

def unregister_materialtools():
    for cls in reversed(other_classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)
