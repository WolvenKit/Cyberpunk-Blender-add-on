import bpy
from bpy.app.handlers import persistent
import bpy.utils.previews
import sys
import shutil
import numpy as np
import ast
from pathlib import Path
from ..main.bartmoss_functions import *
from ..main.common import get_classes
from .. exporters import CP77HairProfileExport, mi_export, mlsetup_export, mlmask_export
from .. importers.import_with_materials import CP77GLBimport, reload_mats
from bpy.props import (StringProperty, EnumProperty, PointerProperty, CollectionProperty)
from bpy.types import (Scene, Operator, Panel)


# JATO: LLM suggestion because the subscribe functions unregister when loading a new blender file
@persistent
def load_post_handler(dummy):
    """This runs every time a new Blend file is loaded"""
    subscribe_to_object()
    subscribe_to_color()
    subscribe_to_material()

# JATO: TODO figure out how irresponsible this is and add check to prevent from always setting this prop on undo/redo
@persistent
def trigger_update_on_undo(scene):
    bpy.context.scene.cp77_ml_props.multilayer_index_int = bpy.context.scene.cp77_ml_props.multilayer_index_int

def subscribe_to_color():
    subscribe_to = bpy.types.PaletteColor, "color"
    bpy.msgbus.subscribe_rna(key=subscribe_to,owner=bpy.types.PaletteColor,args=(),notify=color_changed_callback)

def color_changed_callback():
    ts = bpy.context.tool_settings
    palette = ts.gpencil_paint.palette
    props = bpy.context.scene.cp77_ml_props

    if palette:
        new_palette_color = palette.colors.active.color
        if new_palette_color != props.last_palette_color:
            # JATO: I think this should work but blender doesnt like?
            #bpy.app.timers.register(lambda: bpy.ops.apply_color_override.mlsetup(), first_interval=0.01)

            # LLM: We use a try/except because the context might be 'restricted' during callbacks
            try:
                send_color_to_shader()
            except Exception as e:
                print(f"Callback failed: {e}")

        props.last_palette_color = palette.colors.active.color

def send_color_to_shader():
    ts = bpy.context.tool_settings
    if 'MLTemplatePath' not in ts.gpencil_paint.palette:
        return
    palette = ts.gpencil_paint.palette
    if ts.gpencil_paint.palette:
        colR, colG, colB = palette.colors.active.color
        active_color = (colR, colG, colB, 1)

    LayerGroup = get_layernode_by_socket()

    LayerGroup.inputs['ColorScale'].default_value = active_color


def subscribe_to_object():
    subscribe_to = bpy.types.LayerObjects, "active"
    bpy.msgbus.subscribe_rna(key=subscribe_to,owner=bpy.types.LayerObjects,args=(),notify=object_changed_callback)

def object_changed_callback():
    props = bpy.context.scene.cp77_ml_props
    obj = bpy.context.active_object
    if not obj:
        return

    if bpy.context.active_object != props.last_active_object:
        if bpy.context.active_object.active_material != props.last_active_material:
            mat = bpy.context.object.active_material
            props.multilayer_object_bool = False
            if mat and 'MLSetup' in mat:
                props.multilayer_object_bool = True
            props.multilayer_index_int = 1

    # JATO: We have to update the "last" props when we change active mat
    # otherwise when making the first change panel will desync by not sending data to shader
    # TODO: do we need last_palette here and in the mat_change callback?
    props.last_active_object = bpy.context.active_object
    props.last_active_material = bpy.context.active_object.active_material
    props.last_palette = bpy.context.tool_settings.gpencil_paint.palette
    if bpy.context.tool_settings.gpencil_paint.palette != None:
        props.last_palette_color = bpy.context.tool_settings.gpencil_paint.palette.colors.active.color
    else:
        props.last_palette_color = (0.0, 0.0, 0.0)

def subscribe_to_material():
    owner = bpy.types.WindowManager
    bpy.msgbus.clear_by_owner(owner)
    bpy.msgbus.subscribe_rna(key=(bpy.types.Object, "active_material"),owner=owner,args=(),notify=material_changed_callback)
    bpy.msgbus.subscribe_rna(key=(bpy.types.Object, "active_material_index"),owner=owner,args=(),notify=material_changed_callback)

def material_changed_callback():
    props = bpy.context.scene.cp77_ml_props
    obj = bpy.context.active_object
    if not obj:
        return

    if bpy.context.active_object.active_material != props.last_active_material:
        #print("cur mat: ",bpy.context.active_object.active_material, "  |  last mat: ", props.last_active_material)
        mat = bpy.context.object.active_material
        props.multilayer_object_bool = False
        if mat and 'MLSetup' in mat:
            props.multilayer_object_bool = True
        props.multilayer_index_int = 1

    # JATO: We have to update the "last" props when we change active mat
    # otherwise when making the first change panel will desync by not sending data to shader
    props.last_active_material = bpy.context.active_object.active_material
    props.last_palette = bpy.context.tool_settings.gpencil_paint.palette
    if bpy.context.tool_settings.gpencil_paint.palette != None:
        props.last_palette_color = bpy.context.tool_settings.gpencil_paint.palette.colors.active.color
    else:
        props.last_palette_color = (0.0, 0.0, 0.0)


def get_layernode_by_socket():
    if bpy.context.object is None:
        return
    if bpy.context.object.active_material is None:
        return
    if bpy.context.object.active_material.get('MLSetup') is None:
        return

    active_object=bpy.context.active_object
    active_material = active_object.active_material
    props = bpy.context.scene.cp77_ml_props
    LayerGroup = None

    nodes = active_material.node_tree.nodes
    layer_index = props.multilayer_index_int

    mlBSDFGroup = nodes.get("Multilayered 1.8.0")
    if mlBSDFGroup:
        socket_name = ("Layer "+str(layer_index))
        socket = mlBSDFGroup.inputs.get(socket_name)
        if socket.is_linked:
            layerGroupLink = socket.links[0]
            linkedLayerGroupName = layerGroupLink.from_node.name
            LayerGroup=nodes[linkedLayerGroupName]
            # print(layer_index, " | ", LayerGroup.name)
        else:
            return None

    return LayerGroup


def generate_multilayer_material(self,context):
    active_object = context.active_object
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    script_directory = os.path.dirname(os.path.abspath(__file__))
    relative_filepath = os.path.join('..', 'resources', 'all_multilayered_resources.glb')
    filepath = os.path.normpath(os.path.join(script_directory, relative_filepath))
    active_material_index = None
    mlsetup_default_filepath = Path(os.path.normpath(os.path.join(script_directory, os.path.join('..', 'resources', 'default.mlsetup.json'))))
    mlsetup_default_depot_filepath = Path(os.path.normpath(os.path.join(cp77_addon_prefs.depotfolder_path, 'default.mlsetup.json')))
    # original_material = None

    if not mlsetup_default_depot_filepath.exists():
        mlsetup_default_depot_filepath.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mlsetup_default_filepath, mlsetup_default_depot_filepath)

    dummy_material = bpy.data.materials.new(name="Multilayer Default")
    dummy_material['MeshPath'] = filepath[:-4]
    # JATO: we have to set 'm' here to get the original mat-name, otherwise name-incrementing will break reload
    dummy_material['m'] = {'Name': 'Multilayer Default', 'BaseMaterial': 'engine\\materials\\multilayered.mt', 'GlobalNormal': 'engine\\textures\\editor\\normal.xbm', 'MultilayerMask': 'default.mlmask', 'DiffuseMap': 'None'}

    if os.path.exists(cp77_addon_prefs.depotfolder_path):
        DepotPath = cp77_addon_prefs.depotfolder_path
    dummy_material['DepotPath'] = DepotPath

    # assign the dummy mat to active obj
    if active_object:
        if active_object.data.materials:
            # original_material = active_object.active_material
            active_material_index = bpy.context.active_object.active_material_index
            bpy.context.active_object.data.materials[active_material_index] = dummy_material
        else:
            bpy.context.active_object.data.materials.append(dummy_material)

    new_material = reload_mats(self, context)
    new_material['BaseMaterial'] = "engine\materials\multilayered.mt"
    new_material['DiffuseMap'] = "None"
    new_material['GlobalNormal'] = "engine\\textures\editor\\normal.xbm"
    new_material['MultilayerMask'] = "default.mlmask"
    new_material['m'] = {'Name': 'Multilayer Default', 'BaseMaterial': 'engine\\materials\\multilayered.mt', 'GlobalNormal': 'engine\\textures\\editor\\normal.xbm', 'MultilayerMask': 'default.mlmask', 'DiffuseMap': 'None'}

    # JATO: clear these so user doesnt try exporting to appdata...
    new_material['MeshPath'] = ""
    new_material['ProjPath'] = ""

    dummy_material.user_remap(new_material)

    # JATO: not necessary but maybe nice to keep the orig material so it doesnt get orphaned
    # if original_material != None:
    #     bpy.context.active_object.data.materials.append(original_material)

    bpy.context.object.active_material = new_material
    if active_material_index:
        bpy.context.active_object.active_material_index = active_material_index

def generate_mlmask_images(self,context,dimensions=1024):
    if isinstance(dimensions, str):
        dimensions = int(dimensions)
    active_object = context.active_object
    active_material = active_object.active_material
    nodes = active_material.node_tree.nodes
    links = active_material.node_tree.links

    mlBSDFGroup = nodes.get("Multilayered 1.8.0")
    if not mlBSDFGroup:
        self.report({'ERROR'}, 'Multilayered shader node not found within selected material.')
        return {'CANCELLED'}

    numLayers = 20
    layerBSDF = 1
    while layerBSDF<=numLayers:
        if layerBSDF == 1:
            layerBSDF += 1
            continue
        socket_name = ("Layer "+str(layerBSDF))
        socket = mlBSDFGroup.inputs.get(socket_name)
        if not socket.is_linked:
            layerBSDF += 1
            continue

        layerGroupLink = socket.links[0]
        linkedLayerGroupName = layerGroupLink.from_node.name
        LayerGroup= nodes[linkedLayerGroupName]
        # print("# ", socket.name, " linked to Node Group: ", LayerGroup.name)

        MaskNode = None
        socket_name = "Mask"
        socket = LayerGroup.inputs.get(socket_name)

        image_name = "ml_default_masksset_" + str(layerBSDF)
        new_img = bpy.data.images.new(name=image_name,width=dimensions,height=dimensions,alpha=False)
        new_img.source = 'GENERATED'
        new_img.generated_type = 'BLANK'
        new_img.colorspace_settings.name = 'Non-Color'

        img_node= nodes.new(type='ShaderNodeTexImage')
        img_node.location = (-1250,800-(400*layerBSDF))
        img_node.width = 300
        img_node.image = new_img

        links.new(img_node.outputs[0], LayerGroup.inputs['Mask'])

        layerBSDF += 1


def switch_brush_44(brush_name):
    brush = bpy.data.brushes.get(brush_name)
    if not brush:
        # print(f"Brush '{brush_name}' not found in bpy.data.brushes.")
        return False
    try:
        identifier = "brushes\\essentials_brushes-mesh_texture.blend\\Brush\\" + brush.name
        bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS',asset_library_identifier="",relative_asset_identifier=identifier)
        # print(f"Successfully activated: {brush.name}")
        return True
    except Exception as e:
        # print(f"Failed to switch brush: {e}")
        return False

def apply_view_mask(self, context):
    if bpy.context.object is None:
        return
    if bpy.context.object.active_material is None:
        return
    if bpy.context.object.active_material.get('MLSetup') is None:
        return
    nt = bpy.context.object.active_material.node_tree
    nodes = nt.nodes

    LayerGroup = get_layernode_by_socket()

    if context.scene.cp77_ml_props.multilayer_view_mask_bool == True:
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

def apply_paint_mask(self, context):
    props = bpy.context.scene.cp77_ml_props
    if props.multilayer_index_int == 1:
        return
    if context.scene.cp77_ml_props.multilayer_paint_mask_bool == True:
        bpy.ops.enter_texture_paint.mlsetup()
        switch_brush_44(props.last_paint_brush)
    else:
        props.last_paint_brush = bpy.context.tool_settings.image_paint.brush.name

        switch_brush_44("Blur")
        bpy.ops.object.mode_set(mode='OBJECT')


def load_panel_data(self, context):
    if bpy.app.version[0]<5:
        return
    if bpy.context.active_object is None:
        return
    if bpy.context.active_object.active_material is None:
        return
    if bpy.context.active_object.active_material.get('MLSetup') is None:
        return
    props = bpy.context.scene.cp77_ml_props

    LayerGroup = get_layernode_by_socket()
    if LayerGroup == None:
        props.multilayer_has_linked_layer = False
        # self.report({'ERROR'}, 'A valid Multilayered node group was not found.')
        return
    props.multilayer_has_linked_layer = True
    props.multilayer_layergroup_string = LayerGroup.name

    # JATO: try setting mask as active then update any image editor windows to show active mask
    nodes = bpy.context.active_object.active_material.node_tree.nodes
    MaskNode = None
    socket_name = "Mask"
    socket = LayerGroup.inputs.get(socket_name)
    if socket.is_linked:
        props.multilayer_paint_mask_enable_bool = True
        maskNodeLink = socket.links[0]
        linkedMaskNodeName = maskNodeLink.from_node.name
        MaskNode=nodes[linkedMaskNodeName]
        nodes.active = MaskNode
        for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        space = area.spaces.active
                        space.image = MaskNode.image
    else:
        props.multilayer_paint_mask_enable_bool = False

    # JATO: TODO test error tolerance numbers
    # JATO: 0.00005 causes color mismatch on panam pants group #3 / layer 4, narrowed to 0.00001
    matchTolerance = 0.00001

    if context.scene.cp77_ml_props.multilayer_view_mask_bool == True:
        apply_view_mask(self, context)
    if context.scene.cp77_ml_props.multilayer_paint_mask_bool == True:
        apply_paint_mask(self, context)

    colorscale = (LayerGroup.inputs['ColorScale'].default_value[::])[:-1]
    normstr = (LayerGroup.inputs['NormalStrength'].default_value)
    metin = (LayerGroup.inputs['MetalLevelsIn'].default_value[::])
    metout = (LayerGroup.inputs['MetalLevelsOut'].default_value[::])
    rouin = (LayerGroup.inputs['RoughLevelsIn'].default_value[::])
    rouout = (LayerGroup.inputs['RoughLevelsOut'].default_value[::])

    props.multilayer_has_generated_overrides = False
    # JATO: We get overrides after selecting the right layer and before matching palette color
    load_mltemplate_and_microblend(self,context,node_group_name=LayerGroup.name)

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
        props.multilayer_normalstr_enum = elem_nrmstr
        props.multilayer_metalin_enum = elem_metin
        props.multilayer_metalout_enum = elem_metout
        props.multilayer_roughin_enum = elem_rouin
        props.multilayer_roughout_enum = elem_rouout

def load_mltemplate_and_microblend(self,context,node_group_name):
    active_object=bpy.context.active_object
    active_material = active_object.active_material
    props = bpy.context.scene.cp77_ml_props
    ts = context.tool_settings

    LayerGroup = active_material.node_tree.nodes.get(node_group_name)

    microblendtexnode = LayerGroup.node_tree.nodes['Image Texture']
    props.multilayer_microblend_pointer = microblendtexnode.image

    mlTemplateGroupInputNode = LayerGroup.node_tree.nodes['Group'].node_tree.nodes['Group Input']
    mlTemplatePath = str(mlTemplateGroupInputNode['mlTemplate'])
    mlTemplatePathStripped = ((mlTemplatePath.split('\\'))[-1])[:-11]

    # JATO: for performance, first we try getting palette by direct name-match and ensure the mlTemplate path matches
    # If mlTemplate paths don't match try searching all palettes which can be slow
    match_palette = None
    palette_byname = bpy.data.palettes.get(mlTemplatePathStripped)
    if palette_byname and palette_byname['MLTemplatePath'] == mlTemplateGroupInputNode['mlTemplate']:
        match_palette = palette_byname
    else:
        for palette in bpy.data.palettes:
            if 'MLTemplatePath' not in palette:
                if not props.multilayer_has_generated_overrides:
                    props.multilayer_has_generated_overrides = True
                    bpy.ops.generate_layer_overrides.mlsetup()
                return
            if palette['MLTemplatePath'] == mlTemplateGroupInputNode['mlTemplate']:
                match_palette = palette
    if match_palette == None:
        if not props.multilayer_has_generated_overrides:
            props.multilayer_has_generated_overrides = True
            bpy.ops.generate_layer_overrides.mlsetup()
        return

    ts.gpencil_paint.palette = match_palette
    props.multilayer_palette_string = match_palette.name
    props.multilayer_has_generated_overrides = False


def apply_mltemplate(self,context):
    ts = context.tool_settings
    props = bpy.context.scene.cp77_ml_props

    # JATO: set of early-returns when set_mltemplate operator should NOT be fired because data hasn't changed even tho prop was updated
    if props.last_multilayer_index != props.multilayer_index_int:
        props.last_palette = ts.gpencil_paint.palette
        return
    if bpy.context.active_object != props.last_active_object:
        return
    if bpy.context.active_object.active_material != props.last_active_material:
        return

    # JATO: update gpencil palette to the new mltemplate
    bpy.context.tool_settings.gpencil_paint.palette = bpy.data.palettes.get(props.multilayer_palette_string)

    active_palette = ts.gpencil_paint.palette
    if active_palette != props.last_palette:
        send_mltemplate_to_shader(self,context)

        # JATO: after we change mltemplate, get the new overrides and set idx-0 enum which is null/default
        normalstr_enums = get_normalstr_ovrd(None, context)
        if normalstr_enums:
            first_enum_id = normalstr_enums[0][0]
            props.multilayer_normalstr_enum = first_enum_id
        metalin_enums = get_metalin_ovrd(None, context)
        if metalin_enums:
            first_enum_id = metalin_enums[0][0]
            props.multilayer_metalin_enum = first_enum_id
        metalout_enums = get_metalout_ovrd(None, context)
        if metalout_enums:
            first_enum_id = metalout_enums[0][0]
            props.multilayer_metalout_enum = first_enum_id
        roughin_enums = get_roughin_ovrd(None, context)
        if roughin_enums:
            first_enum_id = roughin_enums[0][0]
            props.multilayer_roughin_enum = first_enum_id
        roughout_enums = get_roughout_ovrd(None, context)
        if roughout_enums:
            first_enum_id = roughout_enums[0][0]
            props.multilayer_roughout_enum = first_enum_id

    props.last_palette = ts.gpencil_paint.palette

def send_mltemplate_to_shader(self,context):
        ts = context.tool_settings
        if not ts.gpencil_paint.palette:
            # self.report({'WARNING'}, 'No active palette to match with MLTEMPLATE.')
            return {'CANCELLED'}
        if 'MLTemplatePath' not in ts.gpencil_paint.palette:
            # self.report({'WARNING'}, 'MLTEMPLATE path not found on active palette.')
            return {'CANCELLED'}
        palette_name = ts.gpencil_paint.palette.name

        LayerGroup = get_layernode_by_socket()
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

        palette = ts.gpencil_paint.palette
        if ts.gpencil_paint.palette:
            colR, colG, colB = palette.colors.active.color
            active_color = (colR, colG, colB, 1)

        LayerGroup.inputs['ColorScale'].default_value = active_color


def microblend_filter(self,object):
    props = bpy.context.scene.cp77_ml_props
    if props.multilayer_microblend_filter_bool == False:
        return True
    abs_path = bpy.path.abspath(object.filepath)
    return "microblend" in abs_path.lower()

def apply_microblend_mlsetup(self,context):
    props = bpy.context.scene.cp77_ml_props
    if props.last_multilayer_index != props.multilayer_index_int:
        return
    LayerGroup = get_layernode_by_socket()
    microblendtexnode = LayerGroup.node_tree.nodes['Image Texture']
    microblendtexnode.image = props.multilayer_microblend_pointer


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
    props = bpy.context.scene.cp77_ml_props
    if props.last_multilayer_index != props.multilayer_index_int:
        return
    LayerGroup = get_layernode_by_socket()
    LayerGroup.inputs['NormalStrength'].default_value = float(props.multilayer_normalstr_enum)
def apply_metalin_ovrd(self, context):
    props = bpy.context.scene.cp77_ml_props
    if props.last_multilayer_index != props.multilayer_index_int:
        return
    LayerGroup = get_layernode_by_socket()
    LayerGroup.inputs['MetalLevelsIn'].default_value = ast.literal_eval(props.multilayer_metalin_enum)
def apply_metalout_ovrd(self, context):
    props = bpy.context.scene.cp77_ml_props
    if props.last_multilayer_index != props.multilayer_index_int:
        return
    LayerGroup = get_layernode_by_socket()
    LayerGroup.inputs['MetalLevelsOut'].default_value = ast.literal_eval(props.multilayer_metalout_enum)
def apply_roughin_ovrd(self, context):
    props = bpy.context.scene.cp77_ml_props
    if props.last_multilayer_index != props.multilayer_index_int:
        return
    LayerGroup = get_layernode_by_socket()
    LayerGroup.inputs['RoughLevelsIn'].default_value = ast.literal_eval(props.multilayer_roughin_enum)
def apply_roughout_ovrd(self, context):
    props = bpy.context.scene.cp77_ml_props
    if props.last_multilayer_index != props.multilayer_index_int:
        props.last_multilayer_index = props.multilayer_index_int
        return
    LayerGroup = get_layernode_by_socket()
    LayerGroup.inputs['RoughLevelsOut'].default_value = ast.literal_eval(props.multilayer_roughout_enum)

    #JATO: important we do this here because this is the last "update" func to trigger
    props.last_multilayer_index = props.multilayer_index_int


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
        my_props = scene.cp77_ml_props
        props = context.scene.cp77_panel_props
        vers=bpy.app.version
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

        if not cp77_addon_prefs.show_modtools:
            return
        if not cp77_addon_prefs.show_meshtools:
            return

        ts = context.tool_settings
        active_palette = bpy.context.tool_settings.gpencil_paint.palette

        box1 = layout.box()
        active_object = context.active_object
        if active_object and active_object.active_material:
            box1.label(text=f"{active_object.active_material.name}", icon='MATERIAL')
        else:
            box1.label(text="No active material", icon="MATERIAL")

        col = box1.column()
        if vers[0]<5:
            row_error = col.row()
            row_error.alert = True
            row_error.label(text='Upgrade to Blender 5 for Multilayer features', icon='ERROR')
            return

        row_re = col.row()
        row_re.operator("reload_material.cp77", icon="FILE_REFRESH")
        row_re.operator("relocate_mesh.mlsetup", icon="ZOOM_ALL")
        col.operator("export_scene.mi", icon="EXPORT")
        col.operator("export_scene.hp", icon="STRANDS")
        col.operator("create_multilayer_material.mlsetup", icon="NODE_COMPOSITING")

        box2 = layout.box()
        col = box2.column()
        rowTitle = col.row()
        rowTitle.label(text="MULTILAYERED")

        row_overrides = col.row()
        row_overrides.enabled = my_props.multilayer_object_bool
        if my_props.multilayer_overrides_disconnected_bool == False:
            row_overrides.operator("generate_layer_overrides.mlsetup")
        else:
            row_overrides.operator("generate_layer_overrides_disconnected.mlsetup")
        row_overrides.prop(my_props, "multilayer_overrides_disconnected_bool", text="", icon="MESH_MONKEY", toggle=True)

        row_export = col.row()
        row_export.enabled = my_props.multilayer_object_bool
        row_export.operator("export_scene.mlsetup")
        row_export.operator("export_scene.mlmask")

        box3 = layout.box()
        col = box3.column()

        if (my_props.multilayer_object_bool == False) or (not active_object):
            row_error = col.row()
            row_error.alignment = 'CENTER'
            row_error.scale_y= 3
            row_error.label(text='Select a Multilayer object to access Multilayer Editing')
            return
        if not active_palette:
            row_error = col.row()
            row_error.alignment = 'CENTER'
            row_error.scale_y= 3
            row_error.label(text='Generate Overrides to access Multilayer Editing')
            return
        if 'MLTemplatePath' not in active_palette:
            row_error = col.row()
            row_error.alignment = 'CENTER'
            row_error.scale_y= 3
            row_error.alert = True
            row_error.label(text='Active Palette does not have MLTemplate Data', icon='ERROR')
            return

        row_mltemplate = col.row()
        row_mltemplate.scale_x = 1.75
        row_mltemplate.scale_y = 1.75
        row_mltemplate_split = row_mltemplate.split(factor=0.75)
        if my_props.multilayer_has_generated_overrides:
            row_mltemplate_split.label(text=f"Palette could not be generated", icon='ERROR')
            row_mltemplate_split.prop(my_props, "multilayer_index_int", text="")
            return
        elif my_props.multilayer_has_linked_layer:
            row_mltemplate_split.prop_search(my_props, "multilayer_palette_string", bpy.data, "palettes", text="", icon="NODE_MATERIAL")
            row_mltemplate_split.prop(my_props, "multilayer_index_int", text="")
        else:
            row_mltemplate_split.label(text=f"Empty Layer - No link detected", icon='ERROR')
            row_mltemplate_split.prop(my_props, "multilayer_index_int", text="")
            return

        # JATO: button to manually refresh the active layer. useful if im bad at fixing panel-desync
        # row_layer = col.row()
        # row_layer.scale_x = 1.25
        # row_layer.scale_y = 1.25
        # row_layer.prop(my_props, "multilayer_index_int", text="")
        # row_layer.operator("refresh_layer.mlsetup", text="", icon="FILE_REFRESH")

        row_mb = col.row()
        row_mb.scale_x = 1.25
        row_mb.scale_y = 1.25
        row_mb.prop(my_props, "multilayer_microblend_pointer", text="", icon="NODE_TEXTURE")
        row_mb.prop(my_props, "multilayer_microblend_filter_bool", text="", icon="VIEWZOOM",toggle=True)

        row = col.row()
        row.scale_y = 1.5
        col_paint = row.column()
        col_paint.prop(my_props, "multilayer_paint_mask_bool", toggle=True)
        col_paint.enabled = my_props.multilayer_paint_mask_enable_bool
        row.prop(my_props, "multilayer_view_mask_bool", toggle=True)

        col.separator()

        # JATO: displays active color values. not that useful but was annoying to figure out so its commented...
        # rowColor = box3.row(align=True)
        # if ts.gpencil_paint.palette:
        #     colR, colG, colB = palette.colors.active.color
        #     rowColor.label(text="Color  {:.4f}  {:.4f}  {:.4f}".format(colR, colG, colB))

        row_levels = col.row()
        metal_col = row_levels.box()
        metal_col.label(text="Metal Levels")
        metal_col.prop(my_props, "multilayer_metalin_enum", text="")
        metal_col.prop(my_props, "multilayer_metalout_enum", text="")
        rough_col = row_levels.box()
        rough_col.label(text="Rough Levels")
        rough_col.prop(my_props, "multilayer_roughin_enum", text="")
        rough_col.prop(my_props, "multilayer_roughout_enum", text="")

        row_normalstr = col.row()
        row_normalstr.scale_x = 1.25
        row_normalstr.scale_y = 1.25
        row_normalstr_split = row_normalstr.split(factor=0.5)
        row_normalstr_split.alignment = 'RIGHT'
        row_normalstr_split.label(text="NormalStrength:")
        row_normalstr_split.prop(my_props, "multilayer_normalstr_enum", text="")

        node = active_object.active_material.node_tree.nodes.get(my_props.multilayer_layergroup_string)
        col.prop(node.inputs['MatTile'],"default_value",text="MatTile")
        col.prop(node.inputs['OffsetU'],"default_value",text="OffsetU")
        col.prop(node.inputs['OffsetV'],"default_value",text="OffsetV")
        col.prop(node.inputs['MicroblendNormalStrength'],"default_value",text="MicroblendNormalStrength")
        col.prop(node.inputs['MicroblendContrast'],"default_value",text="MicroblendContrast")
        col.prop(node.inputs['MbTile'],"default_value",text="MbTile")
        col.prop(node.inputs['MicroblendOffsetU'],"default_value",text="MicroblendOffsetU")
        col.prop(node.inputs['MicroblendOffsetV'],"default_value",text="MicroblendOffsetV")
        col.prop(node.inputs['Opacity'],"default_value",text="Opacity")

        row_mltemp = col.row()
        row_mltemp.label(text=(str(active_palette['MLTemplatePath'])).split(".")[0])
        row_mltemp.active=False

        if my_props.multilayer_paint_mask_bool == False:
            palette_box = box3.column()
            palette_box.template_palette(ts.gpencil_paint,"palette",color=True)

class CP77MlSetupGenerateOverrides(Operator):
    bl_idname = "generate_layer_overrides.mlsetup"
    bl_label = "Generate Overrides"
    bl_description = "Create Override data for Layers connected to the Multilayered shader node."

    def execute(self, context):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}

        props = bpy.context.scene.cp77_ml_props
        mlsetup_export.cp77_mlsetup_generateoverrides(self, context)

        LayerGroup = get_layernode_by_socket()
        if LayerGroup == None:
            props.multilayer_has_linked_layer = False
            self.report({'WARNING'}, f'A valid Multilayered node group was not found on Layer {props.multilayer_index_int}.')
            return {'FINISHED'}
        props.multilayer_has_linked_layer = True

        load_mltemplate_and_microblend(self,context,node_group_name=LayerGroup.name)

        return {'FINISHED'}

class CP77MlSetupGenerateOverridesDisconnected(Operator):
    bl_idname = "generate_layer_overrides_disconnected.mlsetup"
    bl_label = "Generate Overrides for All Nodes"
    bl_description = "Create Override data for Layers using the mat_mod_layer naming scheme found within the selected material. Useful for generating extra multilayer-resources with a modified MLSETUP json."

    def execute(self, context):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}

        props = bpy.context.scene.cp77_ml_props
        mlsetup_export.cp77_mlsetup_generateoverrides(self, context, include_disconnected=True)

        props.multilayer_index_int = 1

        LayerGroup = get_layernode_by_socket()
        if LayerGroup == None:
            props.multilayer_has_linked_layer = False
            self.report({'WARNING'}, f'A valid Multilayered node group was not found on Layer {props.multilayer_index_int}.')
            return {'FINISHED'}
        props.multilayer_has_linked_layer = True

        load_mltemplate_and_microblend(self,context,node_group_name=LayerGroup.name)

        return {'FINISHED'}

class CP77MlSetupRefreshOverrides(Operator):
    bl_idname = "refresh_layer.mlsetup"
    bl_label = "Refresh Layer"
    bl_description = "Refreshes the active Multilayered Layer data"

    def execute(self, context):
        props = bpy.context.scene.cp77_ml_props
        props.multilayer_index_int = props.multilayer_index_int

        return {'FINISHED'}

class CP77MlSetupEnterTexturePaint(Operator):
    bl_idname = "enter_texture_paint.mlsetup"
    bl_label = "Paint Mask"

    def execute(self, context):
        LayerGroup = get_layernode_by_socket()
        if LayerGroup == None:
            return

        active_object=bpy.context.active_object
        active_material = active_object.active_material
        nodes = active_material.node_tree.nodes
        MaskNode = None

        socket_name = "Mask"
        socket = LayerGroup.inputs.get(socket_name)
        if not socket.is_linked:
            self.report({'ERROR'}, "No Image Texture Node linked to Selected Layer")
            return {'CANCELLED'}
        maskNodeLink = socket.links[0]
        linkedMaskNodeName = maskNodeLink.from_node.name
        MaskNode=nodes[linkedMaskNodeName]
        # print(layer_index, " | ", MaskNode.name)

        nodes.active = MaskNode

        bpy.ops.object.mode_set(mode='TEXTURE_PAINT')

        return {'FINISHED'}

# JATO: unused operator - is there any situation where user would want to import suzanne?
class CP77MlSetupCreateMultilayerObject(Operator):
    bl_idname = "create_multilayer_object.mlsetup"
    bl_label = "Create Multilayer Object"
    bl_description = "Create an object with a material ready for Multilayer Editing"
    bl_options = {'REGISTER', 'UNDO'}

    dimensions: bpy.props.EnumProperty(
        name="Mask Resolution",
        description="Sets the dimensions of the generated mask images in width and height",
        items=[('128', "128", "128 x 128"),
               ('256', "256", "256 x 256"),
               ('512', "512", "512 x 512"),
               ('1024', "1024", "1024 x 1024"),
               ('2048', "2048", "2048 x 2048"),
               ('4096', "4096 (recommended to downscale before export)", "4096 x 4096 (recommended to downscale before export)")
        ],
        default='1024'
        )

    def execute(self, context):
        script_directory = os.path.dirname(os.path.abspath(__file__))
        relative_filepath = os.path.join('..', 'resources', 'all_multilayered_resources.glb')
        filepath = os.path.normpath(os.path.join(script_directory, relative_filepath))

        CP77GLBimport(with_materials=True, remap_depot=True, scripting=True, filepath=filepath)

        generate_mlmask_images(self,context,self.dimensions)

        active_object = context.active_object
        active_material = active_object.active_material

        #JATO: clear these so user doesnt try exporting to appdata...
        active_material['MeshPath'] = ""
        active_material['ProjPath'] = ""

        return {'FINISHED'}

class CP77MlSetupCreateMultilayerMaterial(Operator):
    bl_idname = "create_multilayer_material.mlsetup"
    bl_label = "Create Multilayer Material"
    bl_description = "Create a material ready for Multilayer Editing on the active object"
    bl_options = {'REGISTER', 'UNDO'}

    dimensions: bpy.props.EnumProperty(
        name="Mask Resolution",
        description="Sets the dimensions of the generated mask images in width and height",
        items=[('128', "128", "128 x 128"),
               ('256', "256", "256 x 256"),
               ('512', "512", "512 x 512"),
               ('1024', "1024", "1024 x 1024"),
               ('2048', "2048", "2048 x 2048"),
               ('4096', "4096 (recommended to downscale before export)", "4096 x 4096 (recommended to downscale before export)")
        ],
        default='1024'
        )

    def execute(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.depotfolder_path == "//MaterialDepot" or cp77_addon_prefs.depotfolder_path == "":
            self.report({'ERROR'}, "This functionality requires you to set your Depot Path within add-on Preferences")
            return {'CANCELLED'}

        generate_multilayer_material(self,context)

        generate_mlmask_images(self,context,self.dimensions)

        bpy.ops.refresh_layer.mlsetup()

        return {'FINISHED'}

class CP77MlSetupRelocateMesh(Operator):
    bl_idname = "relocate_mesh.mlsetup"
    bl_label = "Relocate Mesh"
    bl_description = "Relocate the .glb to update paths used for Materials functionality"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="File Path",
        description="Path to the file",
        subtype='FILE_PATH'
    )

    filter_glob: StringProperty(
        default="*.glb",
        options={'HIDDEN'}
    )

    def execute(self, context):
        active_object = context.active_object
        active_material = active_object.active_material

        MeshPath= self.filepath[:-4]
        before,mid,after=MeshPath.partition('source\\raw\\'.replace('\\',os.sep))
        ProjPath=before+mid

        active_material['MeshPath'] = MeshPath
        active_material['ProjPath'] = ProjPath

        self.report({'INFO'}, f"Source file relocated to: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material")
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class CP77MlPropertyGroup(bpy.types.PropertyGroup):
    multilayer_index_int: bpy.props.IntProperty(name="Layer",default=1,min=1,max=20,update=load_panel_data)
    multilayer_object_bool: bpy.props.BoolProperty(name="",default=False)
    multilayer_overrides_disconnected_bool: bpy.props.BoolProperty(name="Toggle Override Method",default=False)
    multilayer_view_mask_bool: bpy.props.BoolProperty(name="View Mask",default=False,update=apply_view_mask)
    multilayer_paint_mask_bool: bpy.props.BoolProperty(name="Paint Mask",default=False,update=apply_paint_mask)
    multilayer_paint_mask_enable_bool: bpy.props.BoolProperty(name="",default=False)
    multilayer_has_linked_layer: bpy.props.BoolProperty(name="",default=True)
    multilayer_has_generated_overrides: bpy.props.BoolProperty(name="",default=False)

    multilayer_palette_string: bpy.props.StringProperty(name="MLTEMPLATE",update=apply_mltemplate)
    multilayer_normalstr_enum: bpy.props.EnumProperty(name="NormalStrength",description="NormalStrength",items=get_normalstr_ovrd,update=apply_normalstr_ovrd,default=0)
    multilayer_metalin_enum: bpy.props.EnumProperty(name="MetalLevelsIn",description="MetalLevelsIn",items=get_metalin_ovrd,update=apply_metalin_ovrd,default=0)
    multilayer_metalout_enum: bpy.props.EnumProperty(name="MetalLevelsOut",description="MetalLevelsOut",items=get_metalout_ovrd,update=apply_metalout_ovrd,default=0)
    multilayer_roughin_enum: bpy.props.EnumProperty(name="RoughLevelsIn",description="RoughLevelsIn",items=get_roughin_ovrd,update=apply_roughin_ovrd,default=0)
    multilayer_roughout_enum: bpy.props.EnumProperty(name="RoughLevelsOut",description="RoughLevelsOut",items=get_roughout_ovrd,update=apply_roughout_ovrd,default=0)

    multilayer_microblend_pointer: bpy.props.PointerProperty(type=bpy.types.Image,name="Microblend",update=apply_microblend_mlsetup,poll=microblend_filter)
    multilayer_microblend_filter_bool: bpy.props.BoolProperty(name="Microblend Filter",description="Filters available images for filepaths containing 'microblend'",default=True,)

    multilayer_layergroup_string: bpy.props.StringProperty(name="",default="")

    last_palette: bpy.props.PointerProperty(type=bpy.types.Palette)
    last_palette_color: bpy.props.FloatVectorProperty(name="r",subtype='COLOR',default=(1.0, 1.0, 1.0),min=0.0, max=1.0)
    last_paint_brush: bpy.props.StringProperty(name="")
    last_active_object: bpy.props.PointerProperty(type=bpy.types.Object)
    last_active_material: bpy.props.PointerProperty(type=bpy.types.Material)
    last_multilayer_index: bpy.props.IntProperty(name="",default=0)


operators, other_classes = get_classes(sys.modules[__name__])

def register_materialtools():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    subscribe_to_object()
    subscribe_to_color()
    subscribe_to_material()
    bpy.app.handlers.load_post.append(load_post_handler)
    bpy.app.handlers.undo_post.append(trigger_update_on_undo)
    bpy.app.handlers.redo_post.append(trigger_update_on_undo)
    bpy.types.Scene.cp77_ml_props = bpy.props.PointerProperty(type=CP77MlPropertyGroup)

def unregister_materialtools():
    for cls in reversed(other_classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)
    subscribe_to_object()
    subscribe_to_color()
    subscribe_to_material()
    if load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post_handler)
    bpy.app.handlers.undo_post.append(trigger_update_on_undo)
    bpy.app.handlers.redo_post.append(trigger_update_on_undo)
    del bpy.types.Scene.cp77_ml_props
