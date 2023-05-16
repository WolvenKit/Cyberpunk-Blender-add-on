# 
# Streaming Sector Blender import Script for Cyberpunk 2077 by Simarilius
# Jan 2023
# Latest Version available at https://github.com/Simarilius-uk/CP2077_BlenderScripts
# Assumes import plugin version >1.1
# 
#    ________  ______  __________  ____  __  ___   ____ __    _____ ______________________  ____     ______  _______  ____  ____  ______
#   / ____/\ \/ / __ )/ ____/ __ \/ __ \/ / / / | / / //_/   / ___// ____/ ____/_  __/ __ \/ __ \   /  _/  |/  / __ \/ __ \/ __ \/_  __/
#  / /      \  / __  / __/ / /_/ / /_/ / / / /  |/ / ,<      \__ \/ __/ / /     / / / / / / /_/ /   / // /|_/ / /_/ / / / / /_/ / / /   
# / /___    / / /_/ / /___/ _, _/ ____/ /_/ / /|  / /| |    ___/ / /___/ /___  / / / /_/ / _, _/  _/ // /  / / ____/ /_/ / _, _/ / /    
# \____/   /_/_____/_____/_/ |_/_/    \____/_/ |_/_/ |_|   /____/_____/\____/ /_/  \____/_/ |_|  /___/_/  /_/_/    \____/_/ |_| /_/     
#                                                                                                                                       
# 1) Change the project path defined below to the wkit project folder
# 2) If you want collision objects, change want_collisions to True
# 3) If you want it to generate the _new collections for you to add new stuff in set am_modding to True
# 4) Run it                                                                      

import json
import glob
import os
import bpy
from mathutils import Vector, Matrix , Quaternion
from pathlib import Path
import time
from pprint import pprint 




def get_pos_whole(inst):
    pos=[0,0,0]
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            pos[0] = inst['Position']['Properties']['X'] 
            pos[1] = inst['Position']['Properties']['Y'] 
            pos[2] = inst['Position']['Properties']['Z']           
        else:
            pos[0] = inst['Position']['X'] 
            pos[1] = inst['Position']['Y'] 
            pos[2] = inst['Position']['Z'] 
    elif 'position' in inst.keys():
        pos[0] = inst['position']['X'] 
        pos[1] = inst['position']['Y'] 
        pos[2] = inst['position']['Z'] 
    return pos

def add_to_list(mesh, dict):
     if mesh['basename'] in dict.keys():
         if mesh['appearance'] not in dict[mesh['basename']]['apps']:
             dict[mesh['basename']]['apps'].append(mesh['appearance'])
         if mesh['sector'] not in dict[mesh['basename']]['sectors']:
            dict[mesh['basename']]['sectors'].append(mesh['sector'])
     else:
         dict[mesh['basename']]={'apps':[mesh['appearance']],'sectors':[mesh['sector']]}


def get_pos(inst):
    pos=[0,0,0]
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            pos[0] = inst['Position']['Properties']['X'] /100
            pos[1] = inst['Position']['Properties']['Y'] /100
            pos[2] = inst['Position']['Properties']['Z'] /100          
        else:
            if 'X' in inst['Position'].keys():
                pos[0] = inst['Position']['X'] /100
                pos[1] = inst['Position']['Y'] /100
                pos[2] = inst['Position']['Z'] /100
            else:
                pos[0] = inst['Position']['x'] /100
                pos[1] = inst['Position']['y'] /100
                pos[2] = inst['Position']['z'] /100
    elif 'position' in inst.keys():
        if 'X' in inst['position'].keys():
                pos[0] = inst['position']['X'] /100
                pos[1] = inst['position']['Y'] /100
                pos[2] = inst['position']['Z'] /100
    elif 'translation' in inst.keys():
        pos[0] = inst['translation']['X'] /100
        pos[1] = inst['translation']['Y'] /100
        pos[2] = inst['translation']['Z'] /100
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

def get_scale(inst):
    scale=[0,0,0]
    if 'Scale' in inst.keys():
        if 'Properties' in inst['Scale'].keys():
            scale[0] = inst['Scale']['Properties']['X'] /100
            scale[1] = inst['Scale']['Properties']['Y'] /100
            scale[2] = inst['Scale']['Properties']['Z'] /100
        else:
            scale[0] = inst['Scale']['X'] /100
            scale[1] = inst['Scale']['Y'] /100
            scale[2] = inst['Scale']['Z'] /100
    elif 'scale' in inst.keys():
        scale[0] = inst['scale']['X'] /100
        scale[1] = inst['scale']['Y'] /100
        scale[2] = inst['scale']['Z'] /100
    return scale

def importSectors( filepath='', want_collisions=False, am_modding=False ):
    # Enter the path to your projects source\raw\base folder below, needs double slashes between folder names.
    path = os.path.join( os.path.dirname(filepath),'source\\raw\\base')
    print('path is ',path)
    # If your importing to edit the sectors and want to add stuff then set the am_modding to True and it will auto create the _new collectors
    # want_collisions when True will import/generate the box and capsule collisions
 
    jsonpath = glob.glob(path+"\**\*.streamingsector.json", recursive = True)

    meshes=[]
    C = bpy.context

    for filepath in jsonpath:    
        with open(filepath,'r') as f: 
              j=json.load(f) 
        sectorName=os.path.basename(filepath)[:-5]
        t=j['Data']['RootChunk']['nodeData']['Data']
        nodes = j["Data"]["RootChunk"]["nodes"]
        print(len(nodes))
        for i,e in enumerate(nodes):
            data = e['Data']
            type = data['$type']
            match type:
                case 'worldEntityNode': 
                    print('worldEntityNode',i)
                    meshes.append({'basename':e['Data']['entityTemplate']['DepotPath'],'appearance':e['Data']['appearanceName'],'sector':sectorName})
                case 'worldInstancedMeshNode':
                    meshname = data['mesh']['DepotPath'] 
                    if(meshname != 0):
                        meshes.append({'basename':data['mesh']['DepotPath'] ,'appearance':e['Data']['meshAppearance'],'sector':sectorName})
                case 'worldStaticMeshNode' | 'worldBuildingProxyMeshNode' | 'worldGenericProxyMeshNode'| 'worldTerrainProxyMeshNode': 
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                            #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                            meshes.append({'basename':data['mesh']['DepotPath'] ,'appearance':e['Data']['meshAppearance'],'sector':sectorName})
                case 'worldInstancedDestructibleMeshNode':
                    #print('worldInstancedDestructibleMeshNode',i)
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                            meshes.append({'basename':data['mesh']['DepotPath'] ,'appearance':e['Data']['meshAppearance'],'sector':sectorName})

    basenames=[]
    for m in meshes:
         if m['basename'] not in basenames:
             basenames.append(m['basename'])

    meshes_w_apps={}

    for m in meshes:
       if len(m)>0:
            add_to_list(m , meshes_w_apps)

    path = path[:-5]

    coll_scene = C.scene.collection
    if "MasterInstances" not in coll_scene.children.keys():
        coll_target=bpy.data.collections.new("MasterInstances")
        coll_scene.children.link(coll_target)
    else:
        coll_target=bpy.data.collections.get("MasterInstances")

    Masters=coll_target
    Masters.hide_viewport=True

    # could take this out but its useful in edge cases.
    from_mesh_no=0
    to_mesh_no=100000

    for i,m in enumerate(meshes_w_apps):
        if i>=from_mesh_no and i<=to_mesh_no:
            apps=[]
            for meshApp in meshes_w_apps[m]['apps']:
                apps.append(meshApp)
            impapps=','.join(apps)
            #print(os.path.join(path, m[:-4]+'glb'),impapps)
            meshpath=os.path.join(path, m[:-4]+'glb')
            groupname = os.path.splitext(os.path.split(meshpath)[-1])[0]
            if groupname not in Masters.children.keys():
                try:
                    bpy.ops.io_scene_gltf.cp77(filepath=meshpath, appearances=impapps, update_gi=False)
                    objs = C.selected_objects
                    move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                    coll_target.children.link(move_coll) 
                    coll_scene.children.unlink(move_coll)
                except:
                    print('failed on ',os.path.basename(meshpath))
    empty=[]
    for child in Masters.children:
        if len(child.objects)<1:
            empty.append(child)
    
    for failed in empty:
        Masters.children.unlink(failed)


    for filepath in jsonpath:    
        with open(filepath,'r') as f: 
              j=json.load(f) 
          
        t=j['Data']['RootChunk']['nodeData']['Data']
        sectorName=os.path.basename(filepath)[:-5]
    
        if sectorName in coll_scene.children.keys():
            Sector_coll=bpy.data.collections.get(sectorName)
        else:
            Sector_coll=bpy.data.collections.new(sectorName)
            coll_scene.children.link(Sector_coll)       
        Sector_coll['filepath']=filepath
    
        if am_modding==True:
            if sectorName+'_new' in coll_scene.children.keys():
                Sector_additions_coll=bpy.data.collections.get(sectorName+'_new')
            else:
                Sector_additions_coll=bpy.data.collections.new(sectorName+'_new')
                coll_scene.children.link(Sector_additions_coll)       

        meshes =  glob.glob(path+"\**\*.glb", recursive = True)

        glbnames = [ os.path.basename(x) for x in meshes]
        meshnames = [ os.path.splitext(x)[0]+".mesh" for x in glbnames]

        nodes = j["Data"]["RootChunk"]["nodes"]
        print('Processing ',len(nodes),' nodes for sector', sectorName)
        group=''
        for i,e in enumerate(nodes):
    
            #if i > 2: break
            data = e['Data']
            type = data['$type']

            match type:
                case 'worldEntityNode': 
                    #print('worldEntityNode',i)
                    app=data['appearanceName']
                    entpath=os.path.join(path,data['entityTemplate']['DepotPath'])+'.json'
                    ent_groupname=os.path.basename(entpath).split('.')[0]+'_'+app
                    imported=False
                    if ent_groupname in Masters.children.keys():
                        move_coll=Masters.children.get(ent_groupname)
                        imported=True
                    else:
                        try:
                            print('Importing ',entpath, ' using app ',app)
                            bpy.ops.io_scene_gltf.cp77entity(filepath=entpath, appearances=app)
                            objs = C.selected_objects
                            move_coll= coll_scene.children.get( ent_groupname )
                            Masters.children.link(move_coll) 
                            coll_scene.children.unlink(move_coll)
                            imported=True
                        except:
                            print('failed on ',os.path.basename(entpath))
                    if imported:
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for idx,inst in enumerate(instances):
                            #print(inst)
                            group=move_coll
                            groupname=move_coll.name
                            if (group):
                                #print('Group found for ',groupname)     
                                new=bpy.data.collections.new(groupname)
                                Sector_coll.children.link(new)
                                new['nodeType']=type
                                new['nodeIndex']=i
                                new['instance_idx']=idx
                                new['debugName']=e['Data']['debugName']
                                new['sectorName']=sectorName 
                                new['HandleId']=e['HandleId']
                                new['entityTemplate']=os.path.basename(data['entityTemplate']['DepotPath'])
                                new['appearanceName']=data['appearanceName']
                                new['pivot']=inst['Pivot']
                                for old_obj in group.all_objects:                            
                                    obj=old_obj.copy()  
                                    new.objects.link(obj)  
                                    curse=bpy.context.scene.cursor.location
                                    with bpy.context.temp_override(selected_editable_objects=obj):
                                        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                                    pos=get_pos(inst)
                                    # objects may already be offset by the entity import, need to preserve that.
                                    obj.location = (obj.location.x*.01+pos[0],obj.location.y*.01+pos[1],obj.location.z*.01+pos[2])
                                    obj.rotation_quaternion = get_rot(inst)
                                    obj.scale = get_scale(inst)
                                    bpy.context.scene.cursor.location=curse 

 
                case 'worldInstancedMeshNode' :
                    #print('worldInstancedMeshNode')
                    meshname = data['mesh']['DepotPath'] 
                    num=data['worldTransformsBuffer']['numElements']
                    start=data['worldTransformsBuffer']['startIndex']
                    if(meshname != 0):
                                    #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                                    group=Masters.children.get(groupname)
                                    if (group):
                                        #print('Group found for ',groupname)                               
                                        for idx in range(start, start+num):
                                            #create the linked copy of the group of mesh
                                        
                                            new=bpy.data.collections.new(groupname)
                                            Sector_coll.children.link(new)
                                            new['nodeType']=type
                                            new['nodeIndex']=i
                                            new['instance_idx']=idx
                                            new['mesh']=meshname
                                            new['debugName']=e['Data']['debugName']
                                            new['sectorName']=sectorName 
                                            for old_obj in group.all_objects:                            
                                                obj=old_obj.copy()  
                                                new.objects.link(obj)                                    
                                                if 'Data' in data['worldTransformsBuffer']['sharedDataBuffer'].keys():
                                                    inst_trans=data['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']['Transforms'][idx]
                                                       
                                                elif 'HandleRefId' in data['worldTransformsBuffer']['sharedDataBuffer'].keys():
                                                    bufferID = int(data['worldTransformsBuffer']['sharedDataBuffer']['HandleRefId'])
                                                    new['bufferID']=bufferID
                                                    ref=e
                                                    for n in nodes:
                                                        if n['HandleId']==str(bufferID-1):
                                                            ref=n
                                                    inst_trans = ref['Data']['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']['Transforms'][idx]       
                                                else :
                                                    print(e)
                                                obj.location = get_pos(inst_trans)                                         
                                                obj.rotation_quaternion=get_rot(inst_trans)
                                                obj.scale = get_scale(inst_trans)
                                                if obj.location.x == 0:
                                                    print('Location @ 0 for Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])      

                                    else:
                                        print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])
                                                
                case 'XworldDecorationMeshNode': 
                    #print('worldDecorationMeshNode',i)
                    pass
                case 'XworldInstancedOccluderNode':
                    #print('worldInstancedOccluderNode')
                    pass
                case 'worldStaticDecalNode':
                    print('worldStaticDecalNode')
                    # decals are imported as planes tagged with the material details so you can see what they are and move them.
                    instances = [x for x in t if x['NodeIndex'] == i]
                    for idx,inst in enumerate(instances):
                        #print( inst)
                        o = bpy.data.objects.new( "empty", None )
                        o['nodeType']='worldStaticDecalNode'
                        o['nodeIndex']=i
                        o['instance_idx']=idx
                        o['decal']=e['Data']['material']['DepotPath']
                        o['debugName']=e['Data']['debugName']
                        o['sectorName']=sectorName
                        Sector_coll.objects.link(o)
                        o.location = get_pos(inst)
                        o.rotation_quaternion = get_rot(inst)
                        o.scale = get_scale(inst)
                        o.empty_display_size = 0.002
                        o.empty_display_type = 'IMAGE'   

                case 'XworldStaticOccluderMeshNode':
                    #print('worldStaticOccluderMeshNode',i)
                    pass


                case 'worldRoadProxyMeshNode' : 
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']
                        meshpath=os.path.join(path, meshname[:-4]+'glb')
                        #print(os.path.exists(meshpath))
                        #print('Mesh path is - ',meshpath, e['HandleId'])
                        if(meshname != 0):
                                    #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    # Roads all have stupid prx0 names so instancing by name wont work.
                                    imported=False
                                    try:                                   
                                       bpy.ops.io_scene_gltf.cp77(filepath=meshpath, with_materials=True)
                                       objs = C.selected_objects     
                                       groupname = objs[0].users_collection[0].name
                                       group= coll_scene.children.get( groupname )
                                       coll_target.children.link(group) 
                                       coll_scene.children.unlink(group)
                                       coll_target['glb_file']=meshname
                                       imported=True
                                    except:
                                        print("Failed on ",meshpath)
                                
                                    if (imported):
                                        #print('Group found for ',groupname) 
                                        instances = [x for x in t if x['NodeIndex'] == i]
                                        for inst in instances:
                                            new=bpy.data.collections.new(groupname)
                                            Sector_coll.children.link(new)
                                            new['nodeType']=type
                                            new['nodeIndex']=i
                                            new['mesh']=meshname
                                            new['debugName']=e['Data']['debugName']
                                            new['sectorName']=sectorName
                                            new['pivot']=inst['Pivot']
                                        
                                            for old_obj in group.all_objects:                            
                                                obj=old_obj.copy()  
                                                new.objects.link(obj)                             

                                                obj.location = get_pos(inst)
                                            
                                                if obj.location.x == 0:
                                                    print('Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])      
                                                curse=bpy.context.scene.cursor.location
                                                bpy.context.scene.cursor.location=Vector((inst['Pivot']['X'] /100,inst['Pivot']['Y'] /100,inst['Pivot']['Z'] /100))
                                                with bpy.context.temp_override(selected_editable_objects=obj):
                                                    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                                            
                                                #print(i,obj.name,' x= ',obj.location.x, ' y= ', obj.location.y, ' z= ',obj.location.z)
                                                obj.rotation_quaternion = get_rot(inst)
                                                obj.scale = get_scale(inst)
                                                bpy.context.scene.cursor.location=curse  
                                    else:
                                        print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])

                case 'worldStaticMeshNode' | 'worldBuildingProxyMeshNode' | 'worldGenericProxyMeshNode'| 'worldTerrainProxyMeshNode': 
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                                    #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                                    group=Masters.children.get(groupname)
                                    if (group):
                                        #print('Group found for ',groupname) 
                                        instances = [x for x in t if x['NodeIndex'] == i]
                                        for idx,inst in enumerate(instances):
                                            new=bpy.data.collections.new(groupname)
                                            Sector_coll.children.link(new)
                                            new['nodeType']=type
                                            new['nodeIndex']=i
                                            new['instance_idx']=idx
                                            new['mesh']=meshname
                                            new['debugName']=e['Data']['debugName']
                                            new['sectorName']=sectorName
                                            new['pivot']=inst['Pivot']
                                        
                                            for old_obj in group.all_objects:                            
                                                obj=old_obj.copy()  
                                                new.objects.link(obj)                             
                                            
                                                obj.location = get_pos(inst)
                                                obj.rotation_quaternion = get_rot(inst)
                                                obj.scale = get_scale(inst)
                                    else:
                                        print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])
                                  
                case 'worldInstancedDestructibleMeshNode':
                    #print('worldInstancedDestructibleMeshNode',i)
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']
                        num=data['cookedInstanceTransforms']['numElements']
                        start=data['cookedInstanceTransforms']['startIndex']
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                                    #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                                    group=Masters.children.get(groupname)
                                    if (group):
                                        #print('Glb found - ',glbfoundname)     
                                        #print('Glb found, looking for instances of ',i)
                                        instances = [x for x in t if x['NodeIndex'] == i]
                                        for instidx, inst in enumerate(instances):
                                            #print('Node - ',i, ' - ',meshname)
                                            for idx in range(start, start+num):
                                                new=bpy.data.collections.new(groupname)
                                                Sector_coll.children.link(new)
                                                new['nodeType']=type
                                                new['nodeIndex']=i    
                                                new['tl_instance_idx']=instidx
                                                new['sub_instance_idx']=idx
                                                new['mesh']=meshname
                                                new['debugName']=e['Data']['debugName']
                                                new['sectorName']=sectorName  
                                                new['pivot']=inst['Pivot']                     
                                                
                                            
                                                if 'Data' in data['cookedInstanceTransforms']['sharedDataBuffer'].keys():
                                                    #print(data['cookedInstanceTransforms'])
                                                    cookednum=data['cookedInstanceTransforms']['numElements']
                                                
                                                    inst_trans=data['cookedInstanceTransforms']['sharedDataBuffer']['Data']['buffer']['Data']['Transforms'][idx]
                                                
                                                elif 'HandleRefId' in data['cookedInstanceTransforms']['sharedDataBuffer'].keys():
                                                    bufferID = int(data['cookedInstanceTransforms']['sharedDataBuffer']['HandleRefId'])
                                                    new['bufferID']=bufferID
                                                    ref=e
                                                    for n in nodes:
                                                        if n['HandleId']==str(bufferID-1):
                                                            ref=n
                                                    inst_trans = ref['Data']['cookedInstanceTransforms']['sharedDataBuffer']['Data']['buffer']['Data']['Transforms'][idx]   
                                                  
                                                else :
                                                    print(e)
                                            
                                                inst_trans_rot=Quaternion((inst_trans['orientation']['r'],inst_trans['orientation']['i'], -inst_trans['orientation']['j'],-inst_trans['orientation']['k']))  
                                                inst_trans_pos=Vector(get_pos_whole(inst_trans))
                                                inst_trans_scale=Vector((1,1,1))
                                                                                        
                                                inst_pos =Vector(get_pos_whole(inst))
                                                inst_rot =Quaternion(get_rot(inst))
                                                inst_scale =Vector((1,1,1))
                                                inst_trans_m=Matrix.LocRotScale(inst_trans_pos,inst_trans_rot,inst_trans_scale)
                                                inst_m=Matrix.LocRotScale(inst_pos,inst_rot,inst_scale)
                                                tm= inst_m @ inst_trans_m
                                                tm[0][3]=tm[0][3]*.01 
                                                tm[1][3]=tm[1][3]*.01
                                                tm[2][3]=tm[2][3]*.01

                                                for old_obj in group.all_objects:                            
                                                    obj=old_obj.copy()  
                                                    new.objects.link(obj)   
                                                    obj.matrix_local= tm   
                                                    obj.scale=get_scale(inst)
                                    else:
                                        print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])
                case 'worldCollisionNode':
                
    #   ______      _____      _                 
    #  / ____/___  / / (_)____(_)___  ____  _____
    # / /   / __ \/ / / / ___/ / __ \/ __ \/ ___/
    #/ /___/ /_/ / / / (__  ) / /_/ / / / (__  ) 
    #\____/\____/_/_/_/____/_/\____/_/ /_/____/  
    #                                            
    # Collisions are only partially supported, cant get the mesh object ones out of the geomCache from wkit enmasse currently so only box and capsule ones
                    if want_collisions:
                        print('worldCollisionNode',i)
                        sector_Collisions=sectorName+'_colls'
                        if sector_Collisions in coll_scene.children.keys():
                            sector_Collisions_coll=bpy.data.collections.get(sector_Collisions)
                        else:
                            sector_Collisions_coll=bpy.data.collections.new(sector_Collisions)
                            coll_scene.children.link(sector_Collisions_coll) 
                        Actors=e['Data']['compiledData']['Data']['Actors']
                        for idx,act in enumerate(Actors):
                            #print(len(act['Shapes']))
                            x=act['Position']['x']['Bits']/13107200  # this has /100 built in
                            y=act['Position']['y']['Bits']/13107200
                            z=act['Position']['z']['Bits']/13107200
                            arot=get_rot(act)
                            for s,shape in enumerate(act['Shapes']):
                                if shape['ShapeType']=='Box':
                                    print('Box Collision Node')
                                    #pprint(act['Shapes'])
                                    ssize=shape['Size']
                                    spos=get_pos(shape)
                                    srot=get_rot(shape)
                                    arot_q = Quaternion((arot[0],arot[1],arot[2],arot[3]))
                                    srot_q = Quaternion((srot[0],srot[1],srot[2],srot[3]))
                                    rot= arot_q @ srot_q
                                    loc=(spos[0]+x,spos[1]+y,spos[2]+z)
                                    bpy.ops.mesh.primitive_cube_add(size=.01, scale=(ssize['X'],ssize['Y'],ssize['Z']),location=loc)
                                    cube=C.selected_objects[0]
                                    sector_Collisions_coll.objects.link(cube)
                                    cube['nodeIndex']=i
                                    cube['ShapeType']=shape['ShapeType']
                                    cube['ShapeNo']=s
                                    cube['ActorIdx']=idx
                                    cube['sectorName']=sectorName
                            
                                elif shape['ShapeType']=='Capsule':
                                    print('Capsule Collision Node')
                                    ssize=shape['Size']
                                    spos=get_pos(shape)
                                    srot=get_rot(shape)
                                    arot_q = Quaternion((arot[0],arot[1],arot[2],arot[3]))
                                    srot_q = Quaternion((srot[0],srot[1],srot[2],srot[3]))
                                    rot= arot_q @ srot_q
                                    loc=(spos[0]+x,spos[1]+y,spos[2]+z)
                                    bpy.ops.mesh.primitive_cylinder_add(radius=.005, depth=0.01, scale=(ssize['X'],ssize['Y'],ssize['Z']),location=loc)
                                    capsule=C.selected_objects[0]
                                    sector_Collisions_coll.objects.link(capsule)
                                    capsule['nodeIndex']=i
                                    capsule['ShapeType']=shape['ShapeType']
                                    capsule['ShapeNo']=s
                                    capsule['ActorIdx']=idx
                                    capsule['sectorName']=sectorName
                                else: 
                                    print(shape['ShapeType'], ' not supported yet')
                        
            
                case _:
                    print('None of the above',i)
                    pass

        print('Finished with ',filepath)
    print('Finished Importing Sectors')