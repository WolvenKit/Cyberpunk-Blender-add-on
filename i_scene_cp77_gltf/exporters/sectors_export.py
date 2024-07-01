# Script to export CP2077 streaming sectors from Blender
# Just does changes to existing bits so far
# By Simarilius Jan 2023
# last updated 17/4/24
# latest version in the plugin from https://github.com/WolvenKit/Cyberpunk-Blender-add-on
#
#  __       __   ___  __   __  .  . .  . .   .       __   ___  __  ___  __   __      ___  __  . ___ . .  .  __
# /  ` \ / |__) |__  |__) |__) |  | |\ | |__/       /__` |__  /  `  |  /  \ |__)    |__  |  \ |  |  | |\ | / _`
# \__,  |  |__) |___ |  \ |    \__/ | \| |  \       .__/ |___ \__,  |  \__/ |  \    |___ |__/ |  |  | | \| \__/
#
# Havent written a tutorial for this yet so thought I should add some instructions
# 1) Import the sector you want to edit using the Cyberpunk blender plugin (link above).
# 2) You can move the existing objects around and this will be exported
# 3) If you delete the mesh from a collector but leave the collector, the script will delete it with archivexl the file to do this is written to \source\resources
# 4) to add new stuff create a new collector with the sector name with _new on the end ie interior_1_1_0_1.streamingsector_new and then copy any objects you want into it.
#    You need to copy the collector and the meshes for the nodes you want to copy, not just the meshes, the tags that make it work are on the collectors.
# 5) If its stuff already in the sector it will create nodeData nodes to instance it, if its from another imported sector it will copy the main node too
#    Its assuming it can find the json for the sector its copying from in the project, dont be clever merging blends or whatever.
# 6) not all nodetypes are supported yet, have a look at the case statements to see which are
#
# Ask in world-editing on the discord (https://discord.gg/redmodding) if you have any trouble

# TODO
# - Fix the entities - done
# - Add collisions - can delete
# - sort out instanced bits

import json
import glob
import os
import bpy
import copy
from ..main.common import *
from mathutils import Vector, Matrix, Quaternion
from os.path import join

def are_matrices_equal(mat1, mat2, tolerance=0.01):
    if len(mat1) != len(mat2):
        return False
    
    for i in range(len(mat1)):
        for j in range(len(mat1[i])):
            if abs(mat1[i][j] - mat2[i][j]) > tolerance:
                return False
    
    return True

#
# If you want your deletions archive.xl to be yaml not json, you need to install pyyaml
# Following worked for me
# import pip
# pip.main(['install', 'pyyaml'])
#
yamlavail=False
try:
    import yaml
    yamlavail=True
except:
    messages = [
        "pyyaml not available. Please start Blender as administrator."
        "If that doesn't help, switch to Blender's scripting perspective, create a new file, and put the following code in it (no indentation):",
        "\timport pip",
        "\tpip.main(['install', 'pyyaml'])",
    ]

    blender_install_path = next(iter(bpy.utils.script_paths()), None)

    if blender_install_path is not None:
        blender_install_path = join(blender_install_path, "..")
        blender_python_path =  join(blender_install_path, "python", "bin", "python.exe")
        blender_module_path =  join(blender_install_path, "python", "lib", "site-packages")

        messages.append("If that doesn't help either, run the following command from an administrator command prompt:")
        messages.append(f"\t\"{blender_python_path}\" -m pip install pyyaml -t \"{blender_module_path}\"")

    messages.apppend("You can learn more about running Blender scripts under https://tinyurl.com/cp2077blenderpython")
    for message in messages:
        print(message)

C = bpy.context

# function to recursively count nested collections
def countChildNodes(collection):
    if 'expectedNodes' in collection:
        numChildNodes = collection['expectedNodes']
        return numChildNodes

def to_archive_xl(xlfilename, deletions, expectedNodes):
    projectsector=os.path.splitext(os.path.basename(xlfilename))[0]+'.streamingsector'
    xlfile={}
    xlfile['streaming']={'sectors':[]}
    sectors=xlfile['streaming']['sectors']
    for sectorPath in deletions:
        if sectorPath =='Decals' or sectorPath=='Collisions':
            continue

        if sectorPath == projectsector:
            continue
        new_sector={}
        new_sector['path']=sectorPath
        if sectorPath in expectedNodes.keys():
            new_sector['expectedNodes']=expectedNodes[sectorPath]
        else:
            continue
        new_sector['nodeDeletions']=[]
        sectorData = deletions[sectorPath]
        currentNodeIndex = -1
        currentNodeComment = ''
        currentNodeType = ''
        for empty_collection in sectorData:
            currentNodeIndex = empty_collection['nodeDataIndex']
            currentNodeComment = empty_collection.name
            currentNodeType = empty_collection['nodeType']
            if currentNodeIndex>-1:
                new_sector['nodeDeletions'].append({'index':currentNodeIndex,'type':currentNodeType,'debugName':currentNodeComment})
            # set instance variables
        for decal in deletions['Decals'][sectorPath]:
            print('Deleting ', decal)
            new_sector['nodeDeletions'].append({'index':decal['nodeIndex'],'type':decal['NodeType'],'debugName':decal['NodeComment']})
        for collision in deletions['Collisions'][sectorPath].keys():
            print('Deleting ',collision,' Actors ',deletions['Collisions'][sectorPath][collision])
            new_sector['nodeDeletions'].append({'index':collision,"actorDeletions":deletions['Collisions'][sectorPath][collision] ,'type':'worldCollisionNode','debugName':collision,'expectedActors':expectedNodes[sectorPath+'_NI_'+str(collision)]})
        sectors.append(new_sector)
    with open(xlfilename, "w") as filestream:
        if yamlavail:
            yaml.dump(xlfile, filestream, indent=4, sort_keys=False)
        else:
            json.dump(xlfile, filestream, indent=4)

def checkexists(meshname, Masters):
    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
    if groupname in Masters.children.keys() and len(Masters.children[groupname].objects)>0:
        return True
    else:
        return False

def get_pos(inst):
    pos=[0,0,0]
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            pos[0] = inst['Position']['Properties']['X']
            pos[1] = inst['Position']['Properties']['Y']
            pos[2] = inst['Position']['Properties']['Z']
        else:
            if 'X' in inst['Position'].keys():
                pos[0] = inst['Position']['X']
                pos[1] = inst['Position']['Y']
                pos[2] = inst['Position']['Z']
            else:
                pos[0] = inst['Position']['x']
                pos[1] = inst['Position']['y']
                pos[2] = inst['Position']['z']
    elif 'position' in inst.keys():
        if 'X' in inst['position'].keys():
                pos[0] = inst['position']['X']
                pos[1] = inst['position']['Y']
                pos[2] = inst['position']['Z']
    elif 'translation' in inst.keys():
        pos[0] = inst['translation']['X']
        pos[1] = inst['translation']['Y']
        pos[2] = inst['translation']['Z']
    return pos

def get_rot(inst):
    rot=[0,0,0,0]
    if 'Orientation' in inst.keys():
        if 'Properties' in inst['Orientation'].keys():
            rot[0] = inst['Orientation']['Properties']['r']
            rot[1] = inst['Orientation']['Properties']['i']
            rot[2] = inst['Orientation']['Properties']['j']
            rot[3] = inst['Orientation']['Properties']['k']
        else:
            rot[0] = inst['Orientation']['r']
            rot[1] = inst['Orientation']['i']
            rot[2] = inst['Orientation']['j']
            rot[3] = inst['Orientation']['k']
    elif 'orientation' in inst.keys():
            rot[0] = inst['orientation']['r']
            rot[1] = inst['orientation']['i']
            rot[2] = inst['orientation']['j']
            rot[3] = inst['orientation']['k']
    elif 'Rotation' in inst.keys():
            rot[0] = inst['Rotation']['r']
            rot[1] = inst['Rotation']['i']
            rot[2] = inst['Rotation']['j']
            rot[3] = inst['Rotation']['k']
    elif 'rotation' in inst.keys():
            rot[0] = inst['rotation']['r']
            rot[1] = inst['rotation']['i']
            rot[2] = inst['rotation']['j']
            rot[3] = inst['rotation']['k']
    return rot

def set_pos(inst,obj):
    #print(inst)
    if 'Position'in inst.keys():
        if 'Properties' in inst['Position'].keys():
            inst['Position']['Properties']['X']= float("{:.9g}".format(obj.location[0]))
            inst['Position']['Properties']['Y'] = float("{:.9g}".format(obj.location[1]))
            inst['Position']['Properties']['Z'] = float("{:.9g}".format(obj.location[2]))
        else:
            if 'X' in inst['Position'].keys():
                inst['Position']['X'] = float("{:.9g}".format(obj.location[0]))
                inst['Position']['Y'] = float("{:.9g}".format(obj.location[1]))
                inst['Position']['Z'] = float("{:.9g}".format(obj.location[2]))
            else:
                inst['Position']['x'] = float("{:.9g}".format(obj.location[0]))
                inst['Position']['y'] = float("{:.9g}".format(obj.location[1]))
                inst['Position']['z'] = float("{:.9g}".format(obj.location[2]))
    elif 'position' in inst.keys():
        inst['position']['X'] = float("{:.9g}".format(obj.location[0]))
        inst['position']['Y'] = float("{:.9g}".format(obj.location[1]))
        inst['position']['Z'] = float("{:.9g}".format(obj.location[2]))
    elif 'translation' in inst.keys():
        inst['translation']['X'] = float("{:.9g}".format(obj.location[0]))
        inst['translation']['Y'] = float("{:.9g}".format(obj.location[1]))
        inst['translation']['Z'] = float("{:.9g}".format(obj.location[2]))

def set_z_pos(inst,obj):
    #print(inst)
    if 'Position'in inst.keys():
        if 'Properties' in inst['Position'].keys():
            inst['Position']['Properties']['Z'] = float("{:.9g}".format(obj.location[2]))
        else:
            if 'X' in inst['Position'].keys():
                inst['Position']['Z'] = float("{:.9g}".format(obj.location[2]))
            else:
                inst['Position']['z'] = float("{:.9g}".format(obj.location[2]))
    elif 'position' in inst.keys():
        inst['position']['Z'] = float("{:.9g}".format(obj.location[2]))
    elif 'translation' in inst.keys():
        inst['translation']['Z'] = float("{:.9g}".format(obj.location[2]))

def set_rot(inst,obj):
    if 'Orientation' in inst.keys():
        if 'Properties' in inst['Orientation'].keys():
            inst['Orientation']['Properties']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0] ))
            inst['Orientation']['Properties']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1] ))
            inst['Orientation']['Properties']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2] ))
            inst['Orientation']['Properties']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3] ))
        else:
            inst['Orientation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0] ))
            inst['Orientation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1] ))
            inst['Orientation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2] ))
            inst['Orientation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3] ))
    elif 'Rotation' in inst.keys():
            inst['Rotation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0] ))
            inst['Rotation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1] ))
            inst['Rotation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2] ))
            inst['Rotation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3] ))
    elif 'rotation' in inst.keys():
            inst['rotation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0] ))
            inst['rotation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1] ))
            inst['rotation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2] ))
            inst['rotation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3] ))
    elif 'orientation' in inst.keys():
            inst['orientation']['r'] = float("{:.9g}".format(obj.rotation_quaternion[0] ))
            inst['orientation']['i'] = float("{:.9g}".format(obj.rotation_quaternion[1] ))
            inst['orientation']['j'] = float("{:.9g}".format(obj.rotation_quaternion[2] ))
            inst['orientation']['k'] = float("{:.9g}".format(obj.rotation_quaternion[3] ))

def set_scale(inst,obj):
    if 'Scale' in inst.keys():
        if 'Properties' in inst['Scale'].keys():
            inst['Scale']['Properties']['X'] = float("{:.9g}".format(obj.scale[0]))
            inst['Scale']['Properties']['Y'] = float("{:.9g}".format(obj.scale[1]))
            inst['Scale']['Properties']['Z']= float("{:.9g}".format(obj.scale[2]))
        else:
            inst['Scale']['X']  = float("{:.9g}".format(obj.scale[0]))
            inst['Scale']['Y']  = float("{:.9g}".format(obj.scale[1]))
            inst['Scale']['Z']  = float("{:.9g}".format(obj.scale[2]))
    elif 'scale' in inst.keys():
            inst['scale']['X']  = float("{:.9g}".format(obj.scale[0]))
            inst['scale']['Y']  = float("{:.9g}".format(obj.scale[1]))
            inst['scale']['Z']  = float("{:.9g}".format(obj.scale[2]))

def set_bounds(node, obj):
        node["Bounds"]['Max']["X"]= float("{:.9g}".format(obj.location[0]))
        node["Bounds"]['Max']["Y"]= float("{:.9g}".format(obj.location[1]))
        node["Bounds"]['Max']["Z"]= float("{:.9g}".format(obj.location[2]))
        node["Bounds"]['Min']["X"]= float("{:.9g}".format(obj.location[0]))
        node["Bounds"]['Min']["Y"]= float("{:.9g}".format(obj.location[1]))
        node["Bounds"]['Min']["Z"]= float("{:.9g}".format(obj.location[2]))

def find_col(NodeIndex,Inst_idx,Sector_coll):
    #print('Looking for NodeIndex ',NodeIndex,' Inst_idx ',Inst_idx, ' in ',Sector_coll)
    col=[x for x in Sector_coll.children if x['nodeIndex']==NodeIndex]
    if len(col)==0:
        return None
    elif len(col)==1:
        return col[0]
    else:
        inst=[x for x in col if x['instance_idx']==Inst_idx]
        if len(inst)>0:
            return inst[0]
    return None

def find_wIDMN_col(NodeIndex,tl_inst_idx, sub_inst_idx,Sector_coll):
    #print('Looking for NodeIndex ',NodeIndex,' Inst_idx ',Inst_idx, ' in ',Sector_coll)
    col=[x for x in Sector_coll.children if x['nodeIndex']==NodeIndex]
    if len(col)==0:
        return None
    elif len(col)==1:
        return col[0]
    else:
        inst=[x for x in col if x['tl_instance_idx']==tl_inst_idx and x['sub_instance_idx']==sub_inst_idx]
        if len(inst)>0:
            return inst[0]
    return None

def find_decal(NodeIndex,Inst_idx,Sector_coll):
    #print('Looking for NodeIndex ',NodeIndex,' Inst_idx ',Inst_idx, ' in ',Sector_coll)
    col=[x for x in Sector_coll.objects if 'nodeIndex' in x.keys() and x['nodeIndex']==NodeIndex]
    if len(col)==0:
        return None
    elif len(col)==1:
        return col[0]
    else:
        inst=[x for x in col if x['instance_idx']==Inst_idx]
        if len(inst)>0:
            return inst[0]
    return None

def createNodeData(t, col, nodeIndex, obj, ID):
    print(ID)
    t.append({'Id':ID,'Uk10':1088,'Uk11':256,'Uk12':0,'UkFloat1':60.47757,'UkHash1':{"$type": "NodeRef", "$storage": "uint64",  "$value": "0" },'QuestPrefabRefHash': {"$type": "NodeRef", "$storage": "uint64","$value": "0"},'MaxStreamingDistance': 3.4028235e+38})
    new = t[len(t)-1]
    new['NodeIndex']=nodeIndex
    new['Position']={'$type': 'Vector4','W':0,'X':float("{:.9g}".format(obj.location[0])),'Y':float("{:.9g}".format(obj.location[1])),'Z':float("{:.9g}".format(obj.location[2]))}
    new['Orientation']={'$type': 'Quaternion','r':float("{:.9g}".format(obj.rotation_quaternion[0])),'i':float("{:.9g}".format(obj.rotation_quaternion[1])),'j':float("{:.9g}".format(obj.rotation_quaternion[2])),'k':float("{:.9g}".format(obj.rotation_quaternion[3]))}
    new['Scale']= {'$type': 'Vector3', 'X':  float("{:.9g}".format(obj.scale[0])), 'Y':  float("{:.9g}".format(obj.scale[1])), 'Z':  float("{:.9g}".format(obj.scale[2]))}
    new['Pivot']= {'$type': 'Vector3', 'X': 0, 'Y': 0, 'Z': 0}
    new['Bounds']= {'$type': 'Box'}
    new['Bounds']['Max']={'$type': 'Vector4','X':float("{:.9g}".format(obj.location[0])),'Y':float("{:.9g}".format(obj.location[1])),'Z':float("{:.9g}".format(obj.location[2]))}
    new['Bounds']['Min']={'$type': 'Vector4','X':float("{:.9g}".format(obj.location[0])),'Y':float("{:.9g}".format(obj.location[1])),'Z':float("{:.9g}".format(obj.location[2]))}
    
def create_static_from_WIMN(node, template_nodes,  newHID):
    new_ni=len(template_nodes)
    WSMN={
          "Data": {
            "$type": "worldStaticMeshNode",
            "castLocalShadows": "Always",
            "castRayTracedGlobalShadows": "Always",
            "castRayTracedLocalShadows": "Always",
            "castShadows": "Always",
            "debugName": {
              "$type": "CName",
              "$storage": "string",
              "$value": node['Data']['debugName']['$value']
            },
            "isHostOnly": node['Data']['isHostOnly'],
            "isVisibleInGame": node['Data']['isVisibleInGame'],
            "mesh": {
              "DepotPath": {
                "$type": "ResourcePath",
                "$storage": "string",
                "$value": node['Data']['mesh']['DepotPath']['$value']
              },              
              "Flags": "Soft"
            },
            "meshAppearance": {
              "$type": "CName",
              "$storage": "string",
              "$value": node['Data']['meshAppearance']['$value']
            },
            "occluderAutohideDistanceScale": node['Data']['occluderAutohideDistanceScale'],
            "occluderType": node['Data']['occluderType'],
            "proxyScale": node['Data']['proxyScale'],            
            
            "sourcePrefabHash": node['Data']['sourcePrefabHash'],
            "tag": node['Data']['tag'],
            "tagExt":node['Data']['tagExt'],
            "version": node['Data']['version'],
            
          }
        }
    template_nodes.append(WSMN)
    newHID+=1


def exportSectors( filename):
    #Set this to your project directory
    #filename= '/Volumes/Ruby/archivexlconvert/archivexlconvert.cdproj'
    #project = '/Volumes/Ruby/archivexlconvert/'
    project=os.path.dirname(filename)
    if not os.path.exists(project):
        print('project path doesnt exist')
    projpath = os.path.join(project,'source','raw','base')
    print('exporting sectors from ',projpath)
    #its currently set to output the modified jsons to an output folder in the project dir (create one before running)
    #you can change this to a path if you prefer
    xloutpath = os.path.join(project,'source','resources')
    jsons = glob.glob(os.path.join(projpath, "**", "*.streamingsector.json"), recursive = True)

    if len(jsons)<1:
        print('ERROR - No source streaming sector jsons found')

    Masters=bpy.data.collections.get("MasterInstances")

    # Open the blank template streaming sector
    resourcepath=get_resources_dir()

    with open(os.path.join(resourcepath,'empty.streamingsector.json'),'r') as f:
        template_json=json.load(f)
    template_nodes = template_json["Data"]["RootChunk"]["nodes"]
    template_nodeData = template_json['Data']['RootChunk']['nodeData']['Data']
    ID=0

    # If anythings tagged from last time you exported, clear it
    for col in bpy.data.collections:
        col['exported']=False

    for obj in bpy.data.objects:
        if 'exported' in obj.keys():
            obj['exported']=False
    coll_scene = bpy.context.scene.collection
    impacts=None
    impact_mats=[]
    Inst_bufferIDs={}
    new_HID=10000
    # .  .  __ .    .. .  .  __      __  ___ .  .  ___  ___ 
    # |\/| /  \ \  / | |\ | / _`    /__`  |  |  | |__  |__  
    # |  | \__/  \/  | | \| \__/    .__/  |  \__/ |    |    
    #
    deletions = {}
    deletions['Decals']={}
    deletions['Collisions']={}
    expectedNodes = {}
    for filepath in jsons:
        projectjson = os.path.join( projpath , os.path.splitext(os.path.basename(filename))[0]+'.streamingsector.json')
        print(projectjson)
        print(filepath)
        if filepath==os.path.join(projpath,projectjson):
            continue
        with open(filepath,'r') as f:
            j=json.load(f)
        nodes = j["Data"]["RootChunk"]["nodes"]
        t=j['Data']['RootChunk']['nodeData']['Data']
        # add nodeDataIndex props to all the nodes in t
        for index, obj in enumerate(t):
            obj['nodeDataIndex']=index

        sectorName=os.path.basename(filepath)[:-5]
        deletions[sectorName]=[]
        deletions['Decals'][sectorName]=[]
        deletions['Collisions'][sectorName]={}
        if sectorName not in bpy.data.collections.keys():
            continue
        print('Updating sector ',sectorName)
        Sector_coll=bpy.data.collections.get(sectorName)
        expectedNodes[sectorName] = countChildNodes(Sector_coll)
        if 'filepath' not in Sector_coll.keys():
            Sector_coll['filepath']=filepath
        #print(filepath)
        #print(len(nodes))
        Sector_additions_coll=bpy.data.collections.get(sectorName+'_new')
        sector_Collisions=sectorName+'_colls'
        wIMNs=0
        for i,e in enumerate(nodes):
            data = e['Data']
            type = data['$type']
            match type:
                case 'worldInstancedMeshNode' :
                    wIMNs+=1
                    #print(wIMNs)
                    meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                    #if 'chopstick' in meshname:
                    #    print('worldInstancedMeshNode - ',meshname)
                    if not checkexists(meshname, Masters):
                        print(meshname, ' not found in masters')
                        continue
                   
                    instances = [(NodeData,nodeDataIndex) for nodeDataIndex,NodeData in enumerate(t) if NodeData['NodeIndex'] == i]
                    for Nidx,(inst,instNDidx) in enumerate(instances):
                        num=data['worldTransformsBuffer']['numElements']
                        start=data['worldTransformsBuffer']['startIndex']
                        if(meshname != 0):
                            for idx in range(start, start+num):
                                 # find the top level instance collector
                                obj_col=find_col(i,idx,Sector_coll)    
                                if obj_col :
                                    # elements are in collectors inside the top one, not just objects
                                    if len(obj_col.children)>0 and len(obj_col.children[0].objects)>0:
                                        obj=obj_col.children[0].objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world!=Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            # working with instancedmesh nodes is a pain in the ass, so convert to static
                                            
                                            create_static_from_WIMN(e,  template_nodes,  new_HID)                                            
                                            new_ni=len(template_nodes)-1
                                            for child in obj_col.children:
                                                if len(child.objects)>0:
                                                    # might need to convert instanced to static here, not sure what the best approach is.
                                                    createNodeData(template_nodeData, child, new_ni, child.objects[0], ID)
                                                    ID+=1
                                    else:
                                        # empty collector, so just delete
                                        if obj_col:
                                            deletions[sectorName].append(obj_col)
                                    

                case 'worldStaticDecalNode':
                    #print('worldStaticDecalNode')
                    instances = [(x,y) for y,x in enumerate(t) if x['NodeIndex'] == i]
                    for idx,(inst,instNid) in enumerate(instances):
                        obj=find_decal(i,idx,Sector_coll)
                        if obj:
                            # Check for Position and if changed delete the original and add to the new sector
                            if obj.matrix_world!=Matrix(obj['matrix']):
                                deletions['Decals'][sectorName].append({'nodeIndex':instNid,'NodeComment' :obj.name, 'NodeType' : obj['nodeType']})
                                new_ni=len(template_nodes)
                                template_nodes.append(copy.deepcopy(nodes[obj['nodeIndex']]))
                                createNodeData(template_nodeData, Sector_coll, new_ni, obj,ID)
                                ID+=1
                        else:
                            deletions['Decals'][sectorName].append({'nodeIndex':instNid,'NodeComment' :'DELETED Decal nid:'+str(inst['NodeIndex'])+' ndid:'+str(instNid), 'NodeType' : 'worldStaticDecalNode'})


                case   'worldStaticMeshNode' | 'worldBuildingProxyMeshNode' | 'worldGenericProxyMeshNode'| 'worldTerrainProxyMeshNode':
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                            instances = [x for x in t if x['NodeIndex'] == i]
                            for idx,inst in enumerate(instances):
                                obj_col=find_col(i,idx,Sector_coll)
                                #print(obj_col)
                                if obj_col:
                                    if len(obj_col.objects)>0:
                                        obj=obj_col.objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world!=Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            new_ni=len(template_nodes)
                                            template_nodes.append(copy.deepcopy(nodes[obj_col['nodeIndex']]))

                                            createNodeData(template_nodeData, obj_col, new_ni, obj,ID)
                                            ID+=1
                                    else:
                                        if obj_col:
                                            deletions[sectorName].append(obj_col)

                case  'worldEntityNode':
                    if isinstance(e, dict) and 'entityTemplate' in data.keys():
                        entname = data['entityTemplate']['DepotPath']['$value'].replace('\\', os.sep)

                        if(entname != 0):
                            instances = [x for x in t if x['NodeIndex'] == i]
                            for idx,inst in enumerate(instances):
                                obj_col=find_col(i,idx,Sector_coll)
                                #print(obj_col)
                                # THIS WAS WRONG, the entity meshes are in child collectors not objects so children>0 and children.objects>0
                                if obj_col and len(obj_col.children)>0:
                                    if len(obj_col.children[0].objects)>0:
                                        obj=obj_col.children[0].objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world!=Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            new_ni=len(template_nodes)
                                            template_nodes.append(copy.deepcopy(nodes[obj_col['nodeIndex']]))

                                            createNodeData(template_nodeData, obj_col, new_ni, obj,ID)
                                            ID+=1

                                else:
                                    if obj_col:
                                        deletions[sectorName].append(obj_col)



                case 'worldInstancedDestructibleMeshNode':
                    #print('worldInstancedDestructibleMeshNode',i)
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        num=data['cookedInstanceTransforms']['numElements']
                        start=data['cookedInstanceTransforms']['startIndex']
                        instances = [x for x in t if x['NodeIndex'] == i]
                        # need to go through the instances (tlidx - top level index) and then the elements (just idx)
                        new_WIDM_static=None
                        for tlidx,inst in enumerate(instances):
                            for idx in range(start, start+num):

                                obj_col=find_wIDMN_col(i,tlidx,idx,Sector_coll)

                                if obj_col :
                                    # elements are in collectors inside the top one, not just objects
                                    if len(obj_col.children)>0 and len(obj_col.children[0].objects)>0:
                                        obj=obj_col.children[0].objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world!=Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            # working with instancedmesh nodes is a pain in the ass, so convert to static
                                            if new_WIDM_static==None:
                                                create_static_from_WIMN(e,  template_nodes,  new_HID)                                            
                                                new_ni=len(template_nodes)-1
                                                new_WIDM_static=new_ni


                                            for child in obj_col.children:
                                                if len(child.objects)>0:
                                                    # might need to convert instanced to static here, not sure what the best approach is.
                                                    createNodeData(template_nodeData, child, new_WIDM_static, child.objects[0],ID)
                                                    ID+=1
                                    else:
                                        # empty collector, so just delete
                                        if obj_col:
                                            deletions[sectorName].append(obj_col)


                case 'worldCollisionNode':
                    # need to process the sector_coll sectors and look for deleted collision bodies - this is almost identical to import, refactor them to have it in one place
                    if sector_Collisions in coll_scene.children.keys():
                        
                        sector_Collisions_coll=bpy.data.collections.get(sector_Collisions)
                        inst = [x for x in t if x['NodeIndex'] == i][0]
                        print('collisions Node ',inst['nodeDataIndex'])
                        Actors=e['Data']['compiledData']['Data']['Actors']
                        expectedNodes[sectorName+'_NI_'+str(inst['nodeDataIndex'])] = len(Actors)
                        for idx,act in enumerate(Actors):
                            x=act['Position']['x']['Bits']/131072
                            y=act['Position']['y']['Bits']/131072
                            z=act['Position']['z']['Bits']/131072
                            arot=get_rot(act)
                            for s,shape in enumerate(act['Shapes']):
                                collname='NodeDataIndex_'+str(inst['nodeDataIndex'])+'_Actor_'+str(idx)+'_Shape_'+str(s)
                                if collname in sector_Collisions_coll.objects:
                                    print('found ',collname)
                                    crash= sector_Collisions_coll.objects[collname]
                                    if Matrix(crash['matrix']).to_translation()!=crash.matrix_world.to_translation():
                                        # how the f do we deal with this???
                                        # delete the actor with archivexl, then recreate it with the new position
                                        # so we need a collisions node, then we need to add the actor
                                        # if we already added one to the export sector it should be ref'd by impacts, if not copy this one and ref it from impacts
                                        # Code below is working, but the collisions arent, I'm clearly missing something.
                                        if impacts==None:
                                            # add the actor to the archivexl deletion list 
                                            if inst['nodeDataIndex'] in deletions['Collisions'][sectorName].keys():
                                                deletions['Collisions'][sectorName][inst['nodeDataIndex']].append(str(idx))
                                            else:
                                                deletions['Collisions'][sectorName][inst['nodeDataIndex']]=[str(idx)]

                                            # nodeindex is the len of template nodes
                                            new_ni=len(template_nodes)
                                            #copy the collision node
                                            template_nodes.append(copy.deepcopy(nodes[i]))
                                            createNodeData(template_nodeData, nodes[i], new_ni, obj,ID)
                                            ID+=1
                                            impacts = template_nodes[len(template_nodes)-1]
                                            impacts['Data']['compiledData']['Data']['Actors']=[]
                                            #need to update the position data
                                      
                                        # Add the current actor to the actors
                                        impacts['Data']['compiledData']['Data']['Actors'].append(copy.deepcopy(Actors[idx]))
                                        #update its position                                        
                                        ddyer=impacts['Data']['compiledData']['Data']['Actors'][len(impacts['Data']['compiledData']['Data']['Actors'])-1]
                                        actloc = ((crash.location[0]-ddyer['Shapes'][s]['Position']['X'])*131072,(crash.location[1]-ddyer['Shapes'][s]['Position']['Y'])*131072,(crash.location[2]-ddyer['Shapes'][s]['Position']['Z'])*131072)
                                        ddyer['Shapes'][s]['Position']={"$type": "Vector3", "X": { "$type": "FixedPoint", "Bits": int(actloc[0])  },"y": {"$type": "FixedPoint","Bits": int(actloc[1]) },
                                                           "z": { "$type": "FixedPoint", "Bits": int(actloc[2]) }}
                                        ddyer['Orientation']={'$type': 'Quaternion','r':float("{:.9g}".format(crash.rotation_quaternion[0])),'i':float("{:.9g}".format(crash.rotation_quaternion[1])),'j':float("{:.9g}".format(crash.rotation_quaternion[2])),'k':float("{:.9g}".format(crash.rotation_quaternion[3]))}
                                        ddyer['Scale']= {'$type': 'Vector3', 'X':  float("{:.9g}".format(crash.scale[0])), 'Y':  float("{:.9g}".format(crash.scale[1])), 'Z':  float("{:.9g}".format(crash.scale[2]))}
                                        if 'Size' in ddyer['Shapes'][s].keys():
                                            ddyer['Shapes'][s]['Size']= { "$type": "Vector3", "X": crash.dimensions[0]/2, "Y": crash.dimensions[1]/2, "Z": crash.dimensions[2]/2  }
                                        #update the numActors property
                                        impacts['Data']['numActors']=len(impacts['Data']['compiledData']['Data']['Actors'])
                                        
                                        for mat in shape['Materials']:
                                            if mat['$value'] not in impact_mats:
                                                impact_mats.append(mat['$value'])
                                        impacts['Data']['numMaterials']=len(impact_mats)
                                            
                                        
                                else:
                                    if shape['ShapeType']=='Box' or shape['ShapeType']=='Capsule':
                                        if inst['nodeDataIndex'] in deletions['Collisions'][sectorName].keys():
                                            deletions['Collisions'][sectorName][inst['nodeDataIndex']].append(str(idx))
                                        else:
                                            deletions['Collisions'][sectorName][inst['nodeDataIndex']]=[str(idx)]






        print(wIMNs)

    #       __   __          __      __  ___       ___  ___
    #  /\  |  \ |  \ | |\ | / _`    /__`  |  |  | |__  |__
    # /~~\ |__/ |__/ | | \| \__>    .__/  |  \__/ |    |
    #
        instances_to_copy=[]
        destructibles_to_copy=[]
        ID=666
        for node in t:
            if int(node['Id'])>ID:
                ID=int(node['Id'])+1
        if Sector_additions_coll:
            for col in Sector_additions_coll.children:
                if 'nodeIndex' in col.keys() and col['sectorName']==sectorName and len(col.objects)>0:
                    match col['nodeType']:
                        case 'worldStaticMeshNode' | 'worldStaticDecalNode' | 'worldBuildingProxyMeshNode' | 'worldGenericProxyMeshNode' | 'worldTerrainProxyMeshNode':
                            obj=col.objects[0]
                            createNodeData(t, col, col['nodeIndex'], obj,ID)
                            ID+=1
                        case 'worldEntityNode':
                            new_ni=len(nodes)
                            nodes.append(copy.deepcopy(nodes[col['nodeIndex']]))
                            obj=col.objects[0]
                            createNodeData(t, col, new_ni, obj,ID)
                            ID+=1

                        case 'worldInstancedMeshNode':
                            obj=col.objects[0]
                            nodeIndex=col['nodeIndex']
                            base=nodes[nodeIndex]['Data']
                            meshname = col['mesh'].replace('\\', os.sep)
                            #print(base)
                            num=base['worldTransformsBuffer']['numElements']
                            start=base['worldTransformsBuffer']['startIndex']
                            base['worldTransformsBuffer']['numElements']=num+1
                            print('start ',start,' num ',num)
                            #Need to build the transform to go in the sharedDataBuffer
                            trans= {"$type": "worldNodeTransform","rotation": {"$type": "Quaternion","i": 0.0, "j": 0.0,"k": 0.0, "r": 1.0 },
                            "translation": {"$type": "Vector3",  "X": 0.0,"Y": 0.0, "Z": 0.0 },'scale': {'$type': 'Vector3', 'X': 1.0, 'Y': 1.0, 'Z': 1.0} }
                            set_pos(trans,obj)
                            set_rot(trans,obj)
                            set_scale(trans,obj)
                            print(trans)

                            if(meshname != 0):
                                idx =start+num
                                if 'Data' in base['worldTransformsBuffer']['sharedDataBuffer'].keys():
                                    #if the transforms are in the nodeData itself we can just add to the end of it - WRONG. it may be the shared one everything else is pointing to.
                                    base['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']
                                    bufferID = nodeIndex

                                elif 'HandleRefId' in base['worldTransformsBuffer']['sharedDataBuffer'].keys():
                                    # transforms are in a shared buffer in another nodeData need to insert then update all the references to the shared buffer
                                    bufferID = int(base['worldTransformsBuffer']['sharedDataBuffer']['HandleRefId'])
                                    ref=base
                                    for n in nodes:
                                        if n['HandleId']==str(bufferID-1):
                                            ref=n
                                    wtbbuffer=ref['Data']['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']
                                print('Before = ',len(wtbbuffer['Transforms']))
                                print('inserting at ',idx)
                                wtbbuffer['Transforms'].insert(idx,trans)
                                print('After = ',len(wtbbuffer['Transforms']))
                                #Need to fix all the start pos for any instances after the node we're processing. What a ballache
                                for i,e in enumerate(nodes):
                                    data = e['Data']
                                    type = data['$type']
                                    if type=='worldInstancedMeshNode':
                                        wtb=data['worldTransformsBuffer']
                                        if 'HandleRefId' in wtb['sharedDataBuffer'].keys()==bufferID:
                                            if wtb['startIndex']>start:
                                                wtb['startIndex']=wtb['startIndex']+1

                        case 'worldInstancedDestructibleMeshNode':
                            obj=col.objects[0]
                            nodeIndex=col['nodeIndex']
                            base=nodes[nodeIndex]['Data']
                            meshname = col['mesh'].replace('\\', os.sep)
                            #print(base)
                            num=base['cookedInstanceTransforms']['numElements']
                            start=base['cookedInstanceTransforms']['startIndex']
                            base['cookedInstanceTransforms']['numElements']=num+1
                            print('start ',start,' num ',num)
                            #Need to build the transform to go in the sharedDataBuffer
                            trans= {"$type": "Transform","orientation": {"$type": "Quaternion","i": 0.0, "j": 0.0,"k": 0.0, "r": 1.0 },
                            "position": {"$type": "Vector4","W": 0,  "X": 0.0,"Y": 0.0, "Z": 0.0 }}


                            instances = [x for x in t if x['NodeIndex'] == nodeIndex]
                            inst=instances[0]

                            inst_pos =Vector(get_pos(inst))
                            inst_rot =Quaternion(get_rot(inst))
                            inst_scale =Vector((1,1,1))
                            inst_m=Matrix.LocRotScale(inst_pos,inst_rot,inst_scale)
                            inst_m_inv=inst_m.inverted()
                            inst_trans_m = inst_m_inv @ obj.matrix_local
                            pos=inst_trans_m.translation
                            trans['position']['X']=pos[0]
                            trans['position']['Y']=pos[1]
                            trans['position']['Z']=pos[2]
                            quat=inst_trans_m.to_quaternion()
                            trans['orientation']['r']=-quat[0]
                            trans['orientation']['i']=-quat[1]
                            trans['orientation']['j']=-quat[2]
                            trans['orientation']['k']=-quat[3]
                            print(trans)

                            if(meshname != 0):
                                idx =start+num
                                if 'Data' in base['cookedInstanceTransforms']['sharedDataBuffer'].keys():
                                    #if the transforms are in the nodeData itself we can just add to the end of it - WRONG
                                    wtbbuffer=base['cookedInstanceTransforms']['sharedDataBuffer']['Data']['buffer']['Data']
                                    bufferID = nodeIndex

                                elif 'HandleRefId' in base['cookedInstanceTransforms']['sharedDataBuffer'].keys():
                                    # transforms are in a shared buffer in another nodeData need to insert then update all the references to the shared buffer
                                    bufferID = int(base['cookedInstanceTransforms']['sharedDataBuffer']['HandleRefId'])
                                    ref=base
                                    for n in nodes:
                                        if n['HandleId']==str(bufferID-1):
                                            ref=n
                                    wtbbuffer=ref['Data']['cookedInstanceTransforms']['sharedDataBuffer']['Data']['buffer']['Data']
                                print('Before = ',len(wtbbuffer['Transforms']))
                                print('inserting at ',idx)
                                wtbbuffer['Transforms'].insert(idx,trans)
                                print('After = ',len(wtbbuffer['Transforms']))
                                #Need to fix all the start pos for any instances after the node we're processing. What a ballache
                                for i,e in enumerate(nodes):
                                    data = e['Data']
                                    type = data['$type']
                                    if type=='worldInstancedDestructibleMeshNode':
                                        citb=data['cookedInstanceTransforms']
                                        if 'HandleRefId' in citb['sharedDataBuffer'].keys()==bufferID:
                                            if citb['startIndex']>start:
                                                citb['startIndex']=citb['startIndex']+1

    #
    #     ___       __    ___ __  _                     ____                              __  __                 _____           __
    #    /   | ____/ /___/ (_) /_(_)___  ____  _____   / __/________  ____ ___     ____  / /_/ /_  ___  _____   / ___/___  _____/ /_____  __________
    #   / /| |/ __  / __  / / __/ / __ \/ __ \/ ___/  / /_/ ___/ __ \/ __ `__ \   / __ \/ __/ __ \/ _ \/ ___/   \__ \/ _ \/ ___/ __/ __ \/ ___/ ___/
    #  / ___ / /_/ / /_/ / / /_/ / /_/ / / / (__  )  / __/ /  / /_/ / / / / / /  / /_/ / /_/ / / /  __/ /      ___/ /  __/ /__/ /_/ /_/ / /  (__  )
    # /_/  |_\__,_/\__,_/_/\__/_/\____/_/ /_/____/  /_/ /_/   \____/_/ /_/ /_/   \____/\__/_/ /_/\___/_/      /____/\___/\___/\__/\____/_/  /____/
    #
    #  Nodes from other sectors that have been imported

                elif 'nodeIndex' in col.keys() and col['sectorName'] in bpy.data.collections.keys() and len(col.objects)>0:
                    match col['nodeType']:
                        case 'worldStaticMeshNode' | 'worldBuildingProxyMeshNode' | 'worldGenericProxyMeshNode' | 'worldTerrainProxyMeshNode':
                            source_sector=col['sectorName']
                            print(source_sector)
                            source_sect_coll=bpy.data.collections.get(source_sector)
                            source_sect_json_path=source_sect_coll['filepath']
                            print(source_sect_json_path)
                            with open(source_sect_json_path,'r') as f:
                                source_sect_json=json.load(f)
                            source_nodes = source_sect_json["Data"]["RootChunk"]["nodes"]
                            print(len(source_nodes),col['nodeIndex'])
                            print(source_nodes[col['nodeIndex']])
                            nodes.append(copy.deepcopy(source_nodes[col['nodeIndex']]))
                            new_Index=len(nodes)-1
                            nodes[new_Index]['HandleId']=str(int(nodes[new_Index-1]['HandleId'])+1)
                            obj=col.objects[0]
                            createNodeData(t, col, new_Index, obj,ID)
                            ID+=1

                        # make a list of all the instances, we'll copy the main node once and instance them
                        case 'worldInstancedMeshNode':
                            if [col['nodeIndex'],col['sectorName']] not in instances_to_copy:
                                instances_to_copy.append([col['nodeIndex'],col['sectorName']])

                        case 'worldInstancedDestructibleMeshNode':
                            if [col['nodeIndex'],col['sectorName']] not in destructibles_to_copy:
                                destructibles_to_copy.append([col['nodeIndex'],col['sectorName']])

        print(instances_to_copy)
        print(destructibles_to_copy)

        for node in instances_to_copy:
            ni=node[0]
            source_sector=node[1]
            source_sect_coll=bpy.data.collections.get(source_sector)
            source_sect_json_path=source_sect_coll['filepath']
            print(source_sect_json_path)
            with open(source_sect_json_path,'r') as f:
                source_sect_json=json.load(f)
            source_nodes = source_sect_json["Data"]["RootChunk"]["nodes"]
            nodes.append(copy.deepcopy(source_nodes[ni]))
            new_Index=len(nodes)-1
            new_node=nodes[new_Index]
            prev_node=nodes[new_Index-1]
            if 'cookedInstanceTransforms' in prev_node.keys() or 'worldTransformsBuffer' in prev_node.keys():
                if 'cookedInstanceTransforms' in prev_node.keys() and 'HandleId' in prev_node['cookedInstanceTransforms']:
                    new_node['HandleId']=str(int(nodes[new_Index-1]['cookedInstanceTransforms']['HandleId'])+1)
                if 'worldTransformsBuffer' in prev_node.keys() and 'HandleId' in prev_node['worldTransformsBuffer']:
                    new_node['HandleId']=str(int(nodes[new_Index-1]['worldTransformsBuffer']['HandleId'])+1)
            else:
                new_node['HandleId']=str(int(nodes[new_Index-1]['HandleId'])+1)
            print("New Node: ")
            print(new_node)
            #need the new nodeData node pointing to it.
            instances = [x for x in source_sect_json['Data']['RootChunk']['nodeData']['Data'] if x['NodeIndex'] == ni]
            inst=instances[0]
            t.append(copy.deepcopy(inst))
            new_nd_node=t[len(t)-1]
            new_nd_node['NodeIndex']=new_Index
            print("New nodeData Node: ")
            print(new_nd_node)
            bufferID=0
            new_node['Data']['worldTransformsBuffer']['numElements']=0
            # Hopefully we can add the instances to the end of the buffer we saved earlier.
            print("Sector_additions_coll['Inst_bufferID'] = ",Sector_additions_coll['Inst_bufferID'])
            if Sector_additions_coll['Inst_bufferID']>0:
                new_node['Data']['worldTransformsBuffer']['sharedDataBuffer']['HandleRefId']=str(Sector_additions_coll['Inst_bufferID'])
                bufferID = Sector_additions_coll['Inst_bufferID']
                if 'Data' in new_node['Data']['worldTransformsBuffer']['sharedDataBuffer'].keys():
                    new_node['Data']['worldTransformsBuffer']['sharedDataBuffer'].pop('Data')
            else:
                # the sector has no other instanced meshes already in it, so no wtb to point to. Need to create one in the wtb data
                # have absolutely no idea what the flags is here.
                newbuf={ "BufferId": str(new_Index+1), "Flags": 4063232,"Type": "WolvenKit.RED4.Archive.Buffer.WorldTransformsBuffer, WolvenKit.RED4.Archive, Version=1.61.0.0, Culture=neutral, PublicKeyToken=null", "Data": { "Transforms": []} }
                new_node['Data']['worldTransformsBuffer']['sharedDataBuffer']['Data']={ "Data": {"$type": "worldSharedDataBuffer", "buffer": newbuf}}

                bufferID = new_node['Data']['worldTransformsBuffer']['sharedDataBuffer']['Data']['Data']['BufferID']
                Sector_additions_coll['Inst_bufferID']=bufferID

            print('bufferID - ',bufferID)
            ref=new_nd_node
            for n in nodes:
                if n['HandleId']==str(bufferID-1):
                    ref=n
            wtbbuffer=ref['Data']['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']
            new_node['Data']['worldTransformsBuffer']['startIndex']=len(wtbbuffer['Transforms'])

            new_node['HandleId']=str(int(nodes[new_Index-1]['HandleId'])+1)
            inst_col=[]
            for col in Sector_additions_coll.children:
                if col['nodeIndex']==ni and col['sectorName']==source_sector:
                    inst_col.append(col.name)
            for colname in inst_col:
                col=Sector_additions_coll.children.get(colname)
                obj=col.objects[0]
                new_node['Data']['worldTransformsBuffer']['numElements']+=1
                trans= {"$type": "worldNodeTransform","rotation": {"$type": "Quaternion","i": 0.0, "j": 0.0,"k": 0.0, "r": 1.0 },
                            "translation": {"$type": "Vector3",  "X": 0.0,"Y": 0.0, "Z": 0.0 },'scale': {'$type': 'Vector3', 'X': 1.0, 'Y': 1.0, 'Z': 1.0} }
                set_pos(trans,obj)
                set_rot(trans,obj)
                set_scale(trans,obj)
                idx=len(wtbbuffer['Transforms'])
                print(trans)
                print('Before = ',len(wtbbuffer['Transforms']))
                print('inserting at ',idx)
                wtbbuffer['Transforms'].insert(idx,trans)
                print('After = ',len(wtbbuffer['Transforms']))

        for node in destructibles_to_copy:
            ni=node[0]
            source_sector=node[1]
            source_sect_coll=bpy.data.collections.get(source_sector)
            source_sect_json_path=source_sect_coll['filepath']
            print(source_sect_json_path)
            with open(source_sect_json_path,'r') as f:
                source_sect_json=json.load(f)
            source_nodes = source_sect_json["Data"]["RootChunk"]["nodes"]
            nodes.append(copy.deepcopy(source_nodes[ni]))
            new_Index=len(nodes)-1
            new_node=nodes[new_Index]
            prev_node=nodes[new_Index-1]
            if 'cookedInstanceTransforms' in prev_node.keys() or 'worldTransformsBuffer' in prev_node.keys():
                if 'cookedInstanceTransforms' in prev_node.keys() and 'HandleId' in prev_node['cookedInstanceTransforms']:
                    new_node['HandleId']=str(int(nodes[new_Index-1]['cookedInstanceTransforms']['HandleId'])+1)
                if 'worldTransformsBuffer' in prev_node.keys() and 'HandleId' in prev_node['worldTransformsBuffer']:
                    new_node['HandleId']=str(int(nodes[new_Index-1]['worldTransformsBuffer']['HandleId'])+1)
            else:
                new_node['HandleId']=str(int(nodes[new_Index-1]['HandleId'])+1)
            print("New Node: ")
            print(new_node)
            #need the new nodeData node pointing to it.
            instances = [x for x in source_sect_json['Data']['RootChunk']['nodeData']['Data'] if x['NodeIndex'] == ni]
            inst=instances[0]
            t.append(copy.deepcopy(inst))
            new_nd_node=t[len(t)-1]
            new_nd_node['NodeIndex']=new_Index
            new_nd_node['Position']['X']=0
            new_nd_node['Position']['Y']=0
            new_nd_node['Position']['Z']=0
            new_nd_node['Orientation']['r']=0
            new_nd_node['Orientation']['i']=0
            new_nd_node['Orientation']['j']=0
            new_nd_node['Orientation']['k']=0
            new_nd_node['Scale']['X']=1
            new_nd_node['Scale']['Y']=1
            new_nd_node['Scale']['Z']=1

            maxHid=new_node['HandleId']
            print("New nodeData Node: ")
            print(new_nd_node)
            bufferID=-99
            new_node['Data']['cookedInstanceTransforms']['numElements']=0
            # Hopefully we can add the instances to the end of the buffer we saved earlier.
            #print("Sector_additions_coll['Dest_bufferID'] = ",Sector_additions_coll['Dest_bufferID'])
            if 'Dest_bufferID' in Sector_additions_coll.keys() and int(Sector_additions_coll['Dest_bufferID'])>-1:

                print('  Found a shared buffer ',Sector_additions_coll['Dest_bufferID'])
                new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer']['HandleRefId']=str(Sector_additions_coll['Dest_bufferID'])
                bufferID = Sector_additions_coll['Dest_bufferID']
                if 'Data' in new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer'].keys():
                    new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer'].pop('Data')
                if 'HandleId' in new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer'].keys():
                    new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer'].pop('HandleId')
            else:
                # the sector has no other instanced meshes already in it, so no wtb to point to. Need to create one in the wtb data
                # have absolutely no idea what the flags is here.
                print('No shared buffer found.')
                newbuf={ "BufferId": str(new_Index+1), "Flags": 4063232,"Type": "WolvenKit.RED4.Archive.Buffer.WorldTransformsBuffer, WolvenKit.RED4.Archive, Version=1.61.0.0, Culture=neutral, PublicKeyToken=null", "Data": { "Transforms": []} }
                new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer']['Data']= { "Data": {"$type": "worldSharedDataBuffer", "buffer": newbuf}}
                print(new_node)
                new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer']['HandleId']=maxHid+1
                maxHid+=1
                new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer'].pop('HandleRefId')
                bufferID = new_node['Data']['cookedInstanceTransforms']['sharedDataBuffer']['HandleId']
                print(new_node['Data']['cookedInstanceTransforms'])
                Sector_additions_coll['Dest_bufferID']=bufferID

            print('bufferID - ',bufferID)
            ref=new_node
            for n in nodes:
                if int(n['HandleId'])==int(bufferID)-1:
                    ref=n
            print(ref['Data']['cookedInstanceTransforms']['sharedDataBuffer'])
            wtbbuffer=ref['Data']['cookedInstanceTransforms']['sharedDataBuffer']['Data']['buffer']['Data']
            new_node['Data']['cookedInstanceTransforms']['startIndex']=len(wtbbuffer['Transforms'])
            if 'HandleId' in new_node['Data']['filterData'].keys():
                    new_node['Data']['filterData']['HandleId']=str(int(maxHid)+1)

            inst_col=[]
            for col in Sector_additions_coll.children:
                if col['nodeIndex']==ni and col['sectorName']==source_sector:
                    inst_col.append(col.name)
            for colname in inst_col:
                col=Sector_additions_coll.children.get(colname)
                obj=col.objects[0]
                new_node['Data']['cookedInstanceTransforms']['numElements']+=1
                trans= {"$type": "Transform","orientation": {"$type": "Quaternion","i": 0.0, "j": 0.0,"k": 0.0, "r": 1.0 },
                            "position": {"$type": "Vector4","W": 0,  "X": 0.0,"Y": 0.0, "Z": 0.0 }}
                set_pos(trans,obj)
                set_rot(trans,obj)
                set_scale(trans,obj)
                idx=len(wtbbuffer['Transforms'])
                print(trans)
                print('Before = ',len(wtbbuffer['Transforms']))
                print('inserting at ',idx)
                wtbbuffer['Transforms'].insert(idx,trans)
                print('After = ',len(wtbbuffer['Transforms']))


    # Export the modified json
    sectpathout=os.path.join(projpath,os.path.splitext(os.path.basename(filename))[0]+'.streamingsector.json')
    with open(sectpathout, 'w') as outfile:
        json.dump(template_json, outfile,indent=2)

    xlpathout=os.path.join(xloutpath,os.path.splitext(os.path.basename(filename))[0]+'.archive.xl')
    to_archive_xl(xlpathout, deletions, expectedNodes)
    print('Finished exporting sectors from ',os.path.splitext(os.path.basename(filename))[0], ' to ',sectpathout )
