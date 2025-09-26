##################################################################################################################
# Initial attempt at getting MLSetup info back out of blender.
# Simarilius, July 2023
##################################################################################################################

import bpy
import json
import os
import numpy as np
import copy
import colorsys
import math
from ..jsontool import JSONTool
from ..main.common import createOverrideTable, show_message


##################################################################################################################
# When saving a local copy of a mltemplate the prefix below will be used, use '' to get original names.
prefix = ''

# When saving the mlSetup if out_prefix is defined it will be used, set to '' to save over original

out_prefix = ''

##################################################################################################################

def make_rel(filepath):
    before,mid,after=filepath.partition('base\\')
    return mid+after

def prefix_mat(material):
    b,m,a=material.partition(os.path.basename(material))
    return b+prefix+m

def matchOverride(self,OverrideTable, key, layer, json_layer, jsonkey, nodevalue, matchTolerance):
    match = None
    matcherr=1e6
    for og in OverrideTable[key]:
        print('  Overrides: ',key, og, (OverrideTable[key][og]))
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


##################################################################################################################
def cp77_mlsetup_export(self, context, mlsetuppath, write_mltemplate):
    obj=bpy.context.active_object
    mat_idx = obj.active_material_index
    mat=obj.material_slots[mat_idx].material
    nodes=mat.node_tree.nodes
    prefixxed=[]
    if not mat.get('MLSetup'):
        self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
        return {'CANCELLED'}
    else:

        MLSetup = mat.get('MLSetup')
        ProjPath=mat.get('ProjPath')
        DepotPath=mat.get('DepotPath')
        mlsetup = JSONTool.openJSON( MLSetup+".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
        #mlsetup = json.loads(file.read())
        #file.close()

        xllay = mlsetup["Data"]["RootChunk"]["layers"]

        LayerCount = len(xllay)

        print('Obj -'+ obj.name)
        print('Mat -'+ mat.name)

        layer=0
        layer_txt=''
        numLayers= len([x for x in nodes if 'Image Texture' in x.name])

        while layer<numLayers:
            layernodename=''
            if layer>1:
                layer_txt='.'+str(layer-1).zfill(3)
            if layer>0:
                layernodename='Image Texture'+layer_txt
            #
            print('#')
            print('# Layer '+str(layer))
            print('#')

            json_layer=xllay[layer]

            # Layer Mask
            if layernodename:
                LayerMask=nodes[layernodename].image.filepath
                print(LayerMask)
            LayerGroup=nodes['Mat_Mod_Layer_'+str(layer)]
            BaseMat = LayerGroup.node_tree.nodes['Group'].node_tree.nodes['Group Input']
            NG=LayerGroup.node_tree.nodes

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

            # Write Layer Values
            json_layer['matTile']=MatTile
            json_layer['mbTile']=MbTile
            json_layer['microblendNormalStrength']=MicroblendNormalStrength
            json_layer['microblendContrast']=MicroblendContrast
            json_layer['offsetU']=OffsetU
            json_layer['offsetV']=OffsetV
            json_layer['microblendOffsetU']=MicroblendOffsetU
            json_layer['microblendOffsetV']=MicroblendOffsetV
            json_layer['opacity']=Opacity
            # Need to take the filesystem out of this
            rel_mb=make_rel(Microblend)
            json_layer['microblend']['DepotPath']['$value']=rel_mb

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

            # Tile bitmaps
            tileNG=NG['Group'].node_tree.nodes
            tile_diff = bpy.path.abspath(tileNG['Image Texture'].image.filepath)[:-3]+'xbm'
            tile_metal = bpy.path.abspath(tileNG['Image Texture.001'].image.filepath)[:-3]+'xbm'
            tile_rough = bpy.path.abspath(tileNG['Image Texture.002'].image.filepath)[:-3]+'xbm'
            tile_normal = bpy.path.abspath(tileNG['Image Texture.003'].image.filepath)[:-3]+'xbm'

            # Need to see if this is in the overrides in the mltemplate, if not, add it and reference the new one. and save a local copy of the mltemplate if its not already local
            cs=ColorScale.default_value[::]
            nstr=NormalStrength.default_value
            mIn=MetalLevelsIn.default_value[::]
            mOut=MetalLevelsOut.default_value[::]
            rIn=RoughLevelsIn.default_value[::]
            rOut=RoughLevelsOut.default_value[::]

            material=BaseMat['mlTemplate']
            print('mlTemplate = ',material)
            json_layer['material']['DepotPath']['$value']=material
            if material in prefixxed:
                material=prefix_mat(material)
                print('Material already modified, loading ',material)

            mltemp = JSONTool.openJSON( material + ".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
            #mltemp = json.loads(mltfile.read())
            #mltfile.close()
            mltemplate =mltemp["Data"]["RootChunk"]
            OverrideTable = createOverrideTable(mltemplate)
            matchTolerance = 0.00001
            matchcol=None
            matchnstr=None
            matchMIN=None
            matchMOUT=None
            matchRIN=None
            matchROUT=None

            mltemplate_name = (((str(material)).split('\\'))[-1])[:-11]
            add_col_to_palette = False
            if mltemplate_name not in bpy.data.palettes:
                new_palette = bpy.data.palettes.new(name=mltemplate_name)
                add_col_to_palette = True
            else:
                new_palette = bpy.data.palettes[mltemplate_name]


            for og in OverrideTable['ColorScale']:
                if add_col_to_palette:
                    color = new_palette.colors.new()
                    coloroverride = (OverrideTable['ColorScale'][og])[:-1]
                    color.color = coloroverride

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
                    mltemplate['overrides']['colorScale'].insert(0,copy.deepcopy(mltemplate['overrides']['colorScale'][0]))
                    index=0
                    name='000000_'+str(index).zfill(6)
                    while name in OverrideTable['ColorScale']:
                        index+=1
                        name='000000_'+str(index).zfill(6)
                    mltemplate['overrides']['colorScale'][0]['n']['$value']=name
                    mltemplate['overrides']['colorScale'][0]['v']['Elements'][0]=cs[0]
                    mltemplate['overrides']['colorScale'][0]['v']['Elements'][1]=cs[1]
                    mltemplate['overrides']['colorScale'][0]['v']['Elements'][2]=cs[2]
                    print('ColScale - ',name)
                    json_layer['colorScale']['$value']= name
                    print(cs[::])

                    if  os.path.basename(material)[:len(prefix)]==prefix:
                        outpath= os.path.join(ProjPath,material)+".json"
                    else:
                        newmaterial=prefix_mat(material)
                        outpath= os.path.join(ProjPath,newmaterial)+".json"
                        json_layer['material']['DepotPath']['$value']=newmaterial
                        prefixxed.append(material)

                    if not os.path.exists(os.path.dirname(outpath)):
                        os.makedirs(os.path.dirname(outpath))

                    with open(outpath, 'w') as outfile:
                        json.dump(mltemp, outfile,indent=2)

            matchOverride(self,OverrideTable, 'NormalStrength', layer, json_layer, 'normalStrength', nstr, matchTolerance)
            matchOverride(self,OverrideTable, 'MetalLevelsIn', layer, json_layer, 'metalLevelsIn', mIn, matchTolerance)
            matchOverride(self,OverrideTable, 'MetalLevelsOut', layer, json_layer, 'metalLevelsOut', mOut, matchTolerance)
            matchOverride(self,OverrideTable, 'RoughLevelsIn', layer, json_layer, 'roughLevelsIn', rIn, matchTolerance)
            matchOverride(self,OverrideTable, 'RoughLevelsOut', layer, json_layer, 'roughLevelsOut', rOut, matchTolerance)

            print('tile_diff: '+str(tile_diff))
            print('tile_metal: '+str(tile_metal))
            print('tile_rough: '+str(tile_rough))
            print('tile_normal: '+str(tile_normal))

            layer+=1

    outpath = mlsetuppath

    with open(outpath, 'w') as outfile:
            json.dump(mlsetup, outfile,indent=2)
            print('Saved to ',outpath)
    self.report({'INFO'}, 'MLSETUP Successfully exported')

def cp77_mlsetup_getpath(self, context):
    obj=bpy.context.active_object
    if not obj or obj is None:
        raise ValueError("No object selected")
    if not obj.material_slots:
        raise ValueError('Selected object has no materials')

    mat_idx = obj.active_material_index
    mat=obj.material_slots[mat_idx].material

    if not mat.get('MLSetup'):
        self.report({'ERROR'}, 'Multilayered setup not found within selected material.')
        return {'CANCELLED'}
    else:
        MLSetup = mat.get('MLSetup')
        ProjPath=mat.get('ProjPath')

    if os.path.basename(MLSetup)[:len(out_prefix)]==out_prefix:
        outpath= os.path.join(ProjPath,MLSetup)+".json"
    else:
        b,m,a=MLSetup.partition(os.path.basename(MLSetup))
        newmlsetup=b+out_prefix+m
        outpath= os.path.join(ProjPath,newmlsetup)+".json"

    if not os.path.exists(os.path.dirname(outpath)):
        os.makedirs(os.path.dirname(outpath))

    return outpath

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

def cp77_mlsetup_generateoverrides(self, context,objs=None):
    if not objs:
        objs=bpy.context.selected_objects
    if not objs or len(objs)==0:
        return {'CANCELLED'}
    for obj in objs:
        if obj.material_slots is None or len(obj.material_slots)==0:
            continue
        mat_idx = obj.active_material_index
        mat=obj.material_slots[mat_idx].material
        nodes=mat.node_tree.nodes
        prefixxed=[]
        if not mat.get('MLSetup'):
            if self:
                self.report({'WARNING'}, 'Multilayered setup not found within selected material.')
            else:
                print('Multilayered setup not found within selected material.')
            continue

        MLSetup = mat.get('MLSetup')
        ProjPath=mat.get('ProjPath')
        DepotPath=mat.get('DepotPath')

        print('Generating Override Data')
        print('Object: '+ obj.name)
        print('Material: '+ mat.name)

        mlsetup = JSONTool.openJSON( MLSetup+".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)

        xllay = mlsetup["Data"]["RootChunk"]["layers"]

        layer=0
        numLayers= len([x for x in nodes if 'Mat_Mod_Layer_' in x.name])

        while layer<numLayers:

            #
            print('')
            print('Layer '+str(layer))

            json_layer=xllay[layer]

            LayerGroup=nodes['Mat_Mod_Layer_'+str(layer)]
            BaseMat = LayerGroup.node_tree.nodes['Group'].node_tree.nodes['Group Input']

            material=BaseMat['mlTemplate']
            print(" ",material)
            json_layer['material']['DepotPath']['$value']=material
            if material in prefixxed:
                material=prefix_mat(material)
                print('Material already modified, loading ',material)

            mltemp = JSONTool.openJSON( material + ".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
            mltemplate =mltemp['Data']['RootChunk']
            OverrideTable = createOverrideTable(mltemplate)

            mltemplate_name = (((str(material)).split('\\'))[-1])[:-11]
            add_col_to_palette = False
            if mltemplate_name not in bpy.data.palettes:
                new_palette = bpy.data.palettes.new(name=mltemplate_name)
                new_palette['MLTemplatePath'] = material

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

                # JATO: printing to check the props are on the palettes
                # for x in new_palette['NormalStrengthList']:
                #     print(x, 'this is x')
                # for x in new_palette['MetalLevelsInList']:
                #     print(x, 'this is x')
                # for y in new_palette['MetalLevelsOutList']:
                #     print(y, 'this is y')
                # for z in new_palette['RoughLevelsInList']:
                #     print(z, 'this is z')
                # for w in OverrideTable['RoughLevelsOut']:
                #     print(w, 'this is w')

                add_col_to_palette = True
            else:
                new_palette = bpy.data.palettes[mltemplate_name]

            # JATO: try sorting blocks
            # Get length of color blocks dynamically
            block_len = 1
            for colorscale in OverrideTable['ColorScale']:
                if not colorscale.endswith('_null'):
                    block_len += 1
                else:
                    break

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

                # These sort methods work for most 6/8 len color-blocks
                # TODO: Handle special templates with alternate palettes like dirt
                if block_len == 6:
                    if block_idx == 0:
                        color_sorted_list.insert((block_pos + 0), colorvalue)
                    elif block_idx == 1:
                        color_sorted_list.insert((block_pos + 1), colorvalue)
                    elif block_idx == 2:
                        color_sorted_list.insert((block_pos + 2), colorvalue)
                    elif block_idx == 3:
                        color_sorted_list.insert((block_pos + 2), colorvalue)
                    elif block_idx == 4:
                        color_sorted_list.insert((block_pos + 4), colorvalue)
                    else:
                        color_sorted_list.insert((block_pos + 0), colorvalue)
                elif block_len == 8:
                    if block_idx == 0:
                        color_sorted_list.insert((block_pos + 0), colorvalue)
                    elif block_idx == 1:
                        color_sorted_list.insert((block_pos + 1), colorvalue)
                    elif block_idx == 2:
                        color_sorted_list.insert((block_pos + 2), colorvalue)
                    elif block_idx == 3:
                        color_sorted_list.insert((block_pos + 3), colorvalue)
                    elif block_idx == 4:
                        color_sorted_list.insert((block_pos + 3), colorvalue)
                    elif block_idx == 5:
                        color_sorted_list.insert((block_pos + 2), colorvalue)
                    elif block_idx == 6:
                        color_sorted_list.insert((block_pos + 4), colorvalue)
                    else:
                        color_sorted_list.insert((block_pos + 0), colorvalue)
                else:
                    color_sorted_list.append(colorvalue)

                block_idx += 1
                if block_idx > (block_len - 1):
                    block_idx = 0
                    block_loop_idx += 1

            for val in color_sorted_list:
                if add_col_to_palette:
                    color = new_palette.colors.new()
                    coloroverride = val[:-1]
                    color.color = coloroverride
                #print('  Overrides: ColorScale', colorscale, (OverrideTable['ColorScale'][colorscale]))

            layer+=1

        success_message = "Generated overrides for " + mat.name + " on " + obj.name

        if self:
            self.report({'INFO'}, success_message)
        else:
            print(success_message)
