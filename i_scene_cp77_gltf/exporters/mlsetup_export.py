##################################################################################################################
# Initial attempt at getting MLSetup info back out of blender.
# Simarilius, July 2023
##################################################################################################################

import bpy
import json
import os
import numpy as np
import copy
from ..main.common import openJSON, createOverrideTable


##################################################################################################################
# When saving a local copy of a mltemplate the prefix below will be used, use '' to get original names.
prefix = 'mod_'

# When saving the mlSetup if out_prefix is defined it will be used, set to '' to save over original

out_prefix = 'mod_'

##################################################################################################################

def make_rel(filepath):
    before,mid,after=filepath.partition('base\\')
    return mid+after

def prefix_mat(material):
    b,m,a=material.partition(os.path.basename(material))
    return b+prefix+m

##################################################################################################################
def cp77_mlsetup_export(self, context):
    try: 
        obj=bpy.context.active_object
        mat=obj.material_slots[0].material
        nodes=mat.node_tree.nodes
        prefixxed=[]
        if not mat.get('MLSetup'):
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No ML Material Selected")
            return {'CANCELLED'}
        else:

            MLSetup = mat.get('MLSetup')
            ProjPath=mat.get('ProjPath')
            DepotPath=mat.get('DepotPath')
            file = openJSON( MLSetup+".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
            mlsetup = json.loads(file.read())
            file.close()
            
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

                # Layer Values
                ColorScale = LayerGroup.inputs['ColorScale']
                MatTile = LayerGroup.inputs['MatTile'].default_value
                json_layer['matTile']=MatTile
                MbTile = LayerGroup.inputs['MbTile'].default_value
                json_layer['mbTile']=MbTile
                MicroblendNormalStrength = LayerGroup.inputs['MicroblendNormalStrength'].default_value
                json_layer['microblendNormalStrength']=MicroblendNormalStrength
                MicroblendContrast = LayerGroup.inputs['MicroblendContrast'].default_value
                json_layer['microblendContrast']=MicroblendContrast
                NormalStrength = LayerGroup.inputs['NormalStrength'].default_value
        # needs to be converted to bytes
        #        json_layer['normalStrength']['$value'=NormalStrength
                Opacity = LayerGroup.inputs['Opacity'].default_value
                json_layer['opacity']=Opacity
                
                #print(ColorScale)
                print('MatTile: '+str(MatTile))
                print('MbTile: '+str(MbTile))
                print('MicroblendNormalStrength: '+str(MicroblendNormalStrength))
                print('MicroblendContrast: '+str(MicroblendContrast))
                print('NormalStrength: '+str(NormalStrength))
                print('Opacity: '+str(Opacity))
                
                # Microblend
                NG=LayerGroup.node_tree.nodes
                Microblend = bpy.path.abspath(NG['Image Texture'].image.filepath)[:-3]+'xbm'
                print('Microblend: '+Microblend)
                # Need to take the filesystem out of this
                rel_mb=make_rel(Microblend)
                json_layer['microblend']['DepotPath']['$value']=rel_mb
                
                # Tile bitmaps
                tileNG=NG['Group'].node_tree.nodes
                tile_diff = bpy.path.abspath(tileNG['Image Texture'].image.filepath)[:-3]+'xbm'
                tile_metal = bpy.path.abspath(tileNG['Image Texture.001'].image.filepath)[:-3]+'xbm'
                tile_rough = bpy.path.abspath(tileNG['Image Texture.002'].image.filepath)[:-3]+'xbm'
                tile_normal = bpy.path.abspath(tileNG['Image Texture.003'].image.filepath)[:-3]+'xbm'
                
                # Need to see if this is in the overrides in the mltemplate, if not, add it and reference the new one. and save a local copy of the mltemplate if its not already local
                cs=ColorScale.default_value[::]
                material=LayerGroup['mlTemplate']
                print('mlTemplate = ',material)
                if material in prefixxed:
                    material=prefix_mat(material)
                    print('Material already modified, loading ',material)
                mltfile = openJSON( material + ".json",mode='r',DepotPath=DepotPath, ProjPath=ProjPath)
                mltemp = json.loads(mltfile.read())
                mltfile.close()
                mltemplate =mltemp["Data"]["RootChunk"]
                OverrideTable = createOverrideTable(mltemplate)
                match=None
                for og in OverrideTable['ColorScale']:            
                    err=np.sum(np.subtract(OverrideTable['ColorScale'][og],cs))
                    #print(err)
                    if abs(err)<0.000001:
                        match = og
                if match:
                    json_layer['colorScale']['$value']= match
                    print('ColScale = ',match)
                else:
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
                    

                print('tile_diff: '+str(tile_diff))
                print('tile_metal: '+str(tile_metal))
                print('tile_rough: '+str(tile_rough))
                print('tile_normal: '+str(tile_normal))
                    
                layer+=1

        if os.path.basename(MLSetup)[:len(out_prefix)]==out_prefix:
            outpath= os.path.join(ProjPath,MLSetup)+".json"    
        else:
            b,m,a=MLSetup.partition(os.path.basename(MLSetup))
            newmlsetup=b+out_prefix+m
            outpath= os.path.join(ProjPath,newmlsetup)+".json"    

        if not os.path.exists(os.path.dirname(outpath)):
            os.makedirs(os.path.dirname(outpath))
                
        with open(outpath, 'w') as outfile:
                json.dump(mlsetup, outfile,indent=2)  
                print('Saved to ',outpath)
        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="MLSetup Succesfully")
    except IndexError as e:
        print(e)