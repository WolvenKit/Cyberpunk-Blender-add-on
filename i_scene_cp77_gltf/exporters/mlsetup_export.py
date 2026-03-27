import bpy
import json
import os
import numpy as np
import copy
import colorsys
import math
import copy
from ..jsontool import JSONTool
from ..main.common import createOverrideTable

# JATO: prefix is never exposed in the UI but it's an interesting idea - keeping for now
# When saving a local copy of a mltemplate the prefix below will be used, use '' to get original names.
prefix = ''

def prefix_mat(MLTemplate):
    b,m,a=MLTemplate.partition(os.path.basename(MLTemplate))
    return b+prefix+m

# JATO: this function is used to get the microblend path. but it's possible to not have textures in the base folders
# TODO see if we can reliably get the relative path if it doesn't include "base\\"
def make_rel(filepath):
    before,mid,after=filepath.partition('base\\')
    return mid+after

def matchOverride(self,OverrideTable, key, layer, json_layer, jsonkey, nodevalue, matchTolerance):
    match = None
    matcherr=1e6
    for og in OverrideTable[key]:
        # print('  Overrides: ',key, og, (OverrideTable[key][og]))
        err=np.sum(np.abs(np.subtract(OverrideTable[key][og],nodevalue)))
        #print(err)
        if abs(err)<matchTolerance and not match:
            match = og
            matcherr=err
        elif abs(err)<matchTolerance and match and err<matcherr:
            match = og
            matcherr=err
    if match:
        json_layer[jsonkey]['$value']= match
        print(key,' = ',match)
    else:
        self.report({'ERROR'}, (key + ' in Layer ' + str(layer) + ' was not exported because a matching Override was not found.'))

def cp77_step_sort(r,g,b, repetitions=1):
    lum = math.sqrt( .241 * r + .691 * g + .068 * b )
    h, s, v = colorsys.rgb_to_hsv(r,g,b)
    if s<.01:
        h2=-1
    else:
        h2 = int(h * repetitions)
    lum2 = int(lum * repetitions)
    v2 = int(v * repetitions)
    if h2 % 2 == 1:
        v2 = repetitions - v2
        lum = repetitions - lum
    return (h2, lum, v2)

def cp77_create_palette(MLTemplate, OverrideTable):
    mltemplate_name = (((str(MLTemplate)).split('\\'))[-1])[:-11]

    # JATO: TODO we should do a safer check here using the mltemplate path prop
    if mltemplate_name in bpy.data.palettes:
        return

    new_palette = bpy.data.palettes.new(name=mltemplate_name)
    new_palette['MLTemplatePath'] = MLTemplate

    ListNormalStrength = []
    ListMetalLevelsIn = []
    ListMetalLevelsOut = []
    ListRoughLevelsIn = []
    ListRoughLevelsOut = []

    for og in OverrideTable['NormalStrength']:
        ListNormalStrength.append(str(OverrideTable['NormalStrength'][og]))
    for og in OverrideTable['MetalLevelsIn']:
        ListMetalLevelsIn.append(str(OverrideTable['MetalLevelsIn'][og]))
    for og in OverrideTable['MetalLevelsOut']:
        ListMetalLevelsOut.append(str(OverrideTable['MetalLevelsOut'][og]))
    for og in OverrideTable['RoughLevelsIn']:
        ListRoughLevelsIn.append(str(OverrideTable['RoughLevelsIn'][og]))
    for og in OverrideTable['RoughLevelsOut']:
        ListRoughLevelsOut.append(str(OverrideTable['RoughLevelsOut'][og]))

    # JATO: We could sort the override values but it might make sense to keep the first override in place because it's the default
    # ListNormalStrength.sort()

    new_palette['NormalStrengthList'] = ListNormalStrength
    new_palette['MetalLevelsInList'] = ListMetalLevelsIn
    new_palette['MetalLevelsOutList'] = ListMetalLevelsOut
    new_palette['RoughLevelsInList'] = ListRoughLevelsIn
    new_palette['RoughLevelsOutList'] = ListRoughLevelsOut

    # JATO: try sorting blocks
    # Get length of color blocks dynamically
    block_len = 1
    for colorscale in OverrideTable['ColorScale']:
        if not colorscale.endswith('_null'):
            block_len += 1
        else:
            break

    print(block_len," : ",mltemplate_name)

    # Sort color _nulls by Hue
    color_nulls = []
    for colorscale in OverrideTable['ColorScale']:
        if colorscale.endswith('_null'):
            repetitions = 8 #magic number bad
            red, green, blue = (OverrideTable['ColorScale'][colorscale])[:-1]
            key = cp77_step_sort(red, green, blue, repetitions)
            color_nulls.append((colorscale,key))
    color_nulls.sort(key=lambda x: x[1])

    # Add all colors to master list by _nulls Hue order
    col_by_hue_list = []
    for k in color_nulls:
        color_split = (k[0]).split('_')[0]
        for colorscale in OverrideTable['ColorScale']:
            colorscale_split = colorscale.split('_')[0]
            if colorscale_split == color_split:
                col_by_hue_list.append(OverrideTable['ColorScale'][colorscale])

    # Re-order colors by Saturation
    block_idx = 0
    color_sorted_list = []
    for colorvalue in col_by_hue_list:
        block_loop_idx = 0
        block_pos = block_loop_idx * block_len

        alt_sort_substrings = {
            "annodised",
            "cliff_",
            "dust_",
            "dirt_",
            "ebony_",
            "factory_floor_old",
            "factory_floor_rough",
            "factory_floor_cracked",
            "grass_",
            "gravel",
            "grime_",
            "mirror",
            "mud_",
            "patina",
            "pebbles",
            "plaster_exterior_01_300",
            "plaster_exterior_damp_01_300",
            "plaster_exterior_neutral_01_300",
            "plaster_exterior_damp_neutral_01_300",
            "plaster_exterior_patched_neutral_01_300",
            "plaster_exterior_rough_neutral_01_300_copy",
            "rock_"
            "sand_",
            "soil_",
            "trash_"
            "terrain",
            "water",
            "windows"
        }

        steel_sort_substrings = {
            "steel_dented_01_100",
            "steel_dented_coroded_01_100",
            "steel_dented_rusty_01_100",
            "steel_galvanized_corrugated_01_300",
            "steel_galvanized_corrugated_02_300",
            "steel_galvanized_corrugated_rust_01_300",
            "steel_galvanized_corrugated_rust_02_300",
            "iron_old"
        }

        # JATO: used LLM to refactor my insane list appending, dictionary works much better
        # This maps: material_type -> { block_idx: offset }
        OFFSET_MAPS = {
            "alt":           {0: 0, 1: 0, 2: 2, 3: 1, 4: 2},
            "concrete":      {0: 0, 1: 0, 2: 2, 3: 1, 4: 2},
            "steel":         {0: 0, 1: 1, 2: 1, 3: 0, 4: 2},
            "asphalt_paint": {0: 0, 1: 1, 2: 0, 3: 2},
            # Default is nested by block_len: { block_len: { block_idx: offset } }
            "default": {
                5: {0: 0, 1: 1, 2: 1, 3: 1},
                6: {0: 0, 1: 1, 2: 2, 3: 2, 4: 4},
                8: {0: 0, 1: 1, 2: 2, 3: 3, 4: 3, 5: 2, 6: 4},
                9: {0: 0, 1: 1, 2: 1, 3: 1, 4: 0, 5: 0, 6: 3, 7: 0},
            }
        }

        category = None
        if any(s in mltemplate_name for s in alt_sort_substrings):
            category = "alt"
        elif any(s in mltemplate_name for s in steel_sort_substrings):
            category = "steel"
        elif "asphalt_paint_01_300" in mltemplate_name:
            category = "asphalt_paint"
        elif "concrete" in mltemplate_name and not any(x in mltemplate_name for x in ["dyed", "painted"]):
            category = "concrete"

        offset = 0
        if category:
            offset = OFFSET_MAPS[category].get(block_idx, 0)
            color_sorted_list.insert(block_pos + offset, colorvalue)
        else:
            len_map = OFFSET_MAPS["default"].get(block_len)
            if len_map:
                offset = len_map.get(block_idx, 0)
                color_sorted_list.insert(block_pos + offset, colorvalue)
            else:
                color_sorted_list.append(colorvalue)

        block_idx += 1
        if block_idx > (block_len - 1):
            block_idx = 0
            block_loop_idx += 1

    for val in color_sorted_list:
        color = new_palette.colors.new()
        coloroverride = val[:-1]
        color.color = coloroverride
        #print('  Overrides: ColorScale', colorscale, (OverrideTable['ColorScale'][colorscale]))


def cp77_mlsetup_export(self, context, mlsetuppath, write_mltemplate):
    active_object = bpy.context.active_object
    active_material = active_object.active_material
    nodes = active_material.node_tree.nodes
    prefixxed=[]

    jsonDefaultMLData = {
        "$type": "Multilayer_Layer",
        "colorScale": {
            "$type": "CName",
            "$storage": "string",
            "$value": "null_null"
        },
        "material": {
            "DepotPath": {
                "$type": "ResourcePath",
                "$storage": "string",
                "$value": "engine\\materials\\defaults\\multilayer_default.mltemplate"
            },
            "Flags": "Default"
        },
        "matTile": 10.1,
        "mbTile": 6.0,
        "metalLevelsIn": {
            "$type": "CName",
            "$storage": "string",
            "$value": "null"
        },
        "metalLevelsOut": {
            "$type": "CName",
            "$storage": "string",
            "$value": "null"
        },
        "microblend": {
            "DepotPath": {
                "$type": "ResourcePath",
                "$storage": "string",
                "$value": "base\\surfaces\\microblends\\default.xbm"
            },
            "Flags": "Default"
        },
        "microblendContrast": 0.5,
        "microblendNormalStrength": 1.0,
        "microblendOffsetU": 0.0,
        "microblendOffsetV": 0.0,
        "normalStrength": {
            "$type": "CName",
            "$storage": "string",
            "$value": "null"
        },
        "offsetU": 0.0,
        "offsetV": 0.0,
        "opacity": 0.0,
        "overrides": {
            "$type": "CName",
            "$storage": "string",
            "$value": "None"
        },
        "roughLevelsIn": {
            "$type": "CName",
            "$storage": "string",
            "$value": "null"
        },
        "roughLevelsOut": {
            "$type": "CName",
            "$storage": "string",
            "$value": "null"
        }
    }

    print("Exporting MLSETUP from " + active_material.name + " on " + active_object.name)

    if not active_material.get('MLSetup'):
        self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
        return {'CANCELLED'}

    MLSetup=active_material.get('MLSetup')
    ProjPath=active_material.get('ProjPath')
    DepotPath=active_material.get('DepotPath')

    mlsetup = JSONTool.openJSON( MLSetup+".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
    #mlsetup = json.loads(file.read())
    #file.close()
    xllay = mlsetup["Data"]["RootChunk"]["layers"]
    jsonLayerCount = len(xllay)
    numLayers = 20
    layerBSDF = 1

    mlBSDFGroup = nodes.get("Multilayered 1.8.0")
    if mlBSDFGroup:
        while numLayers<=20:
            if not mlBSDFGroup.inputs.get('Layer ' + str(numLayers)).is_linked:
                numLayers -=1
            else:
                break
    else:
        self.report({'ERROR'}, 'Multilayered shader node not found within selected material.')
        return {'CANCELLED'}

    # JATO: append extra layers to json when linked socket count is greater than json-layer count
    if numLayers>jsonLayerCount:
        addJsonLayerCount = numLayers - jsonLayerCount
        while addJsonLayerCount > 0:
            xllay.append(copy.deepcopy(jsonDefaultMLData))
            addJsonLayerCount -= 1
    # JATO: remove extra layers to json when linked socket count is less than json-layer count
    if numLayers<jsonLayerCount:
        removeJsonLayerCount = jsonLayerCount - numLayers
        layerRemovedIdx = jsonLayerCount
        while removeJsonLayerCount > 0:
            del xllay[layerRemovedIdx-1]
            layerRemovedIdx -= 1
            removeJsonLayerCount -= 1

    while layerBSDF<=numLayers:
        print('')

        socket_name = ("Layer "+str(layerBSDF))
        socket = mlBSDFGroup.inputs.get(socket_name)
        if socket.is_linked:
            layerGroupLink = socket.links[0]
        else:
            xllay[layerBSDF-1] = jsonDefaultMLData
            print("# ", socket.name, "not linked to Node Group, writing default layer. ")
            layerBSDF += 1
            continue

        linkedLayerGroupName = layerGroupLink.from_node.name
        LayerGroup= nodes[linkedLayerGroupName]
        print("# ", socket.name, " linked to Node Group: ", LayerGroup.name)
        NG = LayerGroup.node_tree.nodes
        mlTemplateGroup = LayerGroup.node_tree.nodes['Group'].node_tree.nodes['Group Input']

        # Set Layer Values
        ColorScale = LayerGroup.inputs['ColorScale']
        NormalStrength = LayerGroup.inputs['NormalStrength']
        MetalLevelsIn = LayerGroup.inputs['MetalLevelsIn']
        MetalLevelsOut = LayerGroup.inputs['MetalLevelsOut']
        RoughLevelsIn = LayerGroup.inputs['RoughLevelsIn']
        RoughLevelsOut = LayerGroup.inputs['RoughLevelsOut']
        MatTile = LayerGroup.inputs['MatTile'].default_value
        MbTile = LayerGroup.inputs['MbTile'].default_value
        MicroblendNormalStrength = LayerGroup.inputs['MicroblendNormalStrength'].default_value
        MicroblendContrast = LayerGroup.inputs['MicroblendContrast'].default_value
        OffsetU = LayerGroup.inputs['OffsetU'].default_value
        OffsetV = LayerGroup.inputs['OffsetV'].default_value
        MicroblendOffsetU = LayerGroup.inputs['MicroblendOffsetU'].default_value
        MicroblendOffsetV = LayerGroup.inputs['MicroblendOffsetV'].default_value
        Opacity = LayerGroup.inputs['Opacity'].default_value
        Microblend = bpy.path.abspath(NG['Image Texture'].image.filepath)[:-3]+'xbm'
        MLTemplate=mlTemplateGroup['mlTemplate']

        if MLTemplate in prefixxed:
            MLTemplate=prefix_mat(MLTemplate)
            print('Material already modified, loading ',MLTemplate)

        # Write Layer Values
        json_layer=xllay[layerBSDF - 1]
        json_layer['matTile']=MatTile
        json_layer['mbTile']=MbTile
        json_layer['microblendNormalStrength']=MicroblendNormalStrength
        json_layer['microblendContrast']=MicroblendContrast
        json_layer['offsetU']=OffsetU
        json_layer['offsetV']=OffsetV
        json_layer['microblendOffsetU']=MicroblendOffsetU
        json_layer['microblendOffsetV']=MicroblendOffsetV
        json_layer['opacity']=Opacity
        rel_mb=make_rel(Microblend)
        json_layer['microblend']['DepotPath']['$value']=rel_mb
        json_layer['material']['DepotPath']['$value']=MLTemplate

        # Print Layer Values
        print('MatTile: '+str(MatTile))
        print('OffsetU: '+str(OffsetU))
        print('OffsetV: '+str(OffsetV))
        print('MbTile: '+str(MbTile))
        print('MicroblendOffsetU: '+str(MicroblendOffsetU))
        print('MicroblendOffsetV: '+str(MicroblendOffsetV))
        print('MicroblendNormalStrength: '+str(MicroblendNormalStrength))
        print('MicroblendContrast: '+str(MicroblendContrast))
        print('Opacity: '+str(Opacity))
        print('Microblend: '+Microblend)
        print('MLTemplate : ',MLTemplate)
        # print('Color Texture: '+str(tile_color))
        # print('Metalness Texture: '+str(tile_metal))
        # print('Roughness Texture: '+str(tile_rough))
        # print('Normal Texture: '+str(tile_normal))

        # Tile bitmaps
        # tileNG=NG['Group'].node_tree.nodes
        # tile_color = bpy.path.abspath(tileNG['Image Texture'].image.filepath)[:-3]+'xbm'
        # tile_metal = bpy.path.abspath(tileNG['Image Texture.001'].image.filepath)[:-3]+'xbm'
        # tile_rough = bpy.path.abspath(tileNG['Image Texture.002'].image.filepath)[:-3]+'xbm'
        # tile_normal = bpy.path.abspath(tileNG['Image Texture.003'].image.filepath)[:-3]+'xbm'

        # Need to see if this is in the overrides in the mltemplate, if not, add it and reference the new one. and save a local copy of the mltemplate if its not already local
        cs=ColorScale.default_value[::]
        nstr=NormalStrength.default_value
        mIn=MetalLevelsIn.default_value[::]
        mOut=MetalLevelsOut.default_value[::]
        rIn=RoughLevelsIn.default_value[::]
        rOut=RoughLevelsOut.default_value[::]

        mltempjson = JSONTool.openJSON( MLTemplate + ".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
        #mltempjson = json.loads(mltfile.read())
        #mltfile.close()
        mltemplatedata =mltempjson["Data"]["RootChunk"]
        OverrideTable = createOverrideTable(mltemplatedata)
        matchTolerance = 0.00001
        matchcol=None

        for og in OverrideTable['ColorScale']:
            #print('  Overrides: ColorScale', og, (OverrideTable['ColorScale'][og]))
            err=np.sum(np.subtract(OverrideTable['ColorScale'][og],cs))
            #print(err)
            if abs(err)<matchTolerance:
                matchcol = og
        if matchcol:
            json_layer['colorScale']['$value']= matchcol
            print('ColScale = ',matchcol)
        else:
            if write_mltemplate:
                #this is linking it so when you edit 0 later both get edited.
                mltemplatedata['overrides']['colorScale'].insert(0,copy.deepcopy(mltemplatedata['overrides']['colorScale'][0]))
                index=0
                name='000000_'+str(index).zfill(6)
                while name in OverrideTable['ColorScale']:
                    index+=1
                    name='000000_'+str(index).zfill(6)
                mltemplatedata['overrides']['colorScale'][0]['n']['$value']=name
                mltemplatedata['overrides']['colorScale'][0]['v']['Elements'][0]=cs[0]
                mltemplatedata['overrides']['colorScale'][0]['v']['Elements'][1]=cs[1]
                mltemplatedata['overrides']['colorScale'][0]['v']['Elements'][2]=cs[2]
                print('ColScale - ',name)
                json_layer['colorScale']['$value']= name
                print(cs[::])

                if os.path.basename(MLTemplate)[:len(prefix)]==prefix:
                    outpath= os.path.join(ProjPath,MLTemplate)+".json"
                else:
                    newmaterial=prefix_mat(MLTemplate)
                    outpath= os.path.join(ProjPath,newmaterial)+".json"
                    json_layer['material']['DepotPath']['$value']=newmaterial
                    prefixxed.append(MLTemplate)

                if not os.path.exists(os.path.dirname(outpath)):
                    os.makedirs(os.path.dirname(outpath))

                with open(outpath, 'w') as outfile:
                    json.dump(mltempjson, outfile,indent=2)

        matchOverride(self,OverrideTable, 'NormalStrength', (layerBSDF - 1), json_layer, 'normalStrength', nstr, matchTolerance)
        matchOverride(self,OverrideTable, 'MetalLevelsIn', (layerBSDF - 1), json_layer, 'metalLevelsIn', mIn, matchTolerance)
        matchOverride(self,OverrideTable, 'MetalLevelsOut', (layerBSDF - 1), json_layer, 'metalLevelsOut', mOut, matchTolerance)
        matchOverride(self,OverrideTable, 'RoughLevelsIn', (layerBSDF - 1), json_layer, 'roughLevelsIn', rIn, matchTolerance)
        matchOverride(self,OverrideTable, 'RoughLevelsOut', (layerBSDF - 1), json_layer, 'roughLevelsOut', rOut, matchTolerance)

        layerBSDF += 1

    outpath = mlsetuppath
    with open(outpath, 'w') as outfile:
            json.dump(mlsetup, outfile,indent=2)
            print('')
            print('Saved to ',outpath)
    success_message = "Exported MLSETUP from " + active_material.name + " on " + active_object.name
    self.report({'INFO'}, success_message)

def cp77_mlsetup_generateoverrides(self, context, objs=None, include_disconnected=False):
    if not objs:
        objs=bpy.context.selected_objects
    if not objs or len(objs)==0:
        return {'CANCELLED'}
    for obj in objs:
        if obj.material_slots is None or len(obj.material_slots)==0:
            continue
        active_material = obj.active_material
        nodes=active_material.node_tree.nodes

        print('Generating Override Data from ' + active_material.name + " on " + obj.name)

        if not active_material.get('MLSetup'):
            if self:
                self.report({'WARNING'}, 'Multilayered setup not found within selected material.')
            else:
                print('Multilayered setup not found within selected material.')
            continue

        MLSetup = active_material.get('MLSetup')
        ProjPath=active_material.get('ProjPath')
        DepotPath=active_material.get('DepotPath')

        mlsetup = JSONTool.openJSON( MLSetup+".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
        xllay = mlsetup["Data"]["RootChunk"]["layers"]
        layer = 1
        numLayers = 20

        mlBSDFGroup = nodes.get("Multilayered 1.8.0")
        if mlBSDFGroup:
            while numLayers<=20:
                if not mlBSDFGroup.inputs.get('Layer ' + str(numLayers)).is_linked:
                    numLayers -=1
                else:
                    break
        else:
            self.report({'ERROR'}, 'Multilayered shader node not found within selected material.')
            return {'CANCELLED'}

        if include_disconnected:
            numLayers = len([x for x in nodes if 'Mat_Mod_Layer_' in x.name])

        while layer<=numLayers:
            json_layer=xllay[layer - 1]

            socket_name = ("Layer "+str(layer))
            socket = mlBSDFGroup.inputs.get(socket_name)
            if socket:
                if socket.is_linked:
                    layerGroupLink = socket.links[0]
                else:
                    layer += 1
                    continue

            linkedLayerGroupName = layerGroupLink.from_node.name
            LayerGroup=nodes[linkedLayerGroupName]
            # print("# ", socket.name, " linked to Node Group: ", LayerGroup.name)
            if include_disconnected:
                LayerGroup=nodes['Mat_Mod_Layer_'+str(layer - 1)]
            mlTemplateGroup = LayerGroup.node_tree.nodes['Group'].node_tree.nodes['Group Input']

            MLTemplate = mlTemplateGroup['mlTemplate']
            # print(" ",MLTemplate)

            json_layer['material']['DepotPath']['$value']=MLTemplate

            mltempjson = JSONTool.openJSON( MLTemplate + ".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
            mltemplatedata =mltempjson['Data']['RootChunk']
            OverrideTable = createOverrideTable(mltemplatedata)

            cp77_create_palette(MLTemplate,OverrideTable)

            layer += 1

        success_message = "Generated overrides for " + active_material.name + " on " + obj.name

        if self:
            self.report({'INFO'}, success_message)
        else:
            print(success_message)
