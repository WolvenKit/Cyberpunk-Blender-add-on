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
import math
from mathutils import Vector, Matrix , Quaternion
from pathlib import Path
import time
import traceback
from pprint import pprint 
from ..main.setup import MaterialBuilder
from ..main.collisions import set_collider_props
from operator import add
import bmesh
VERBOSE=True
scale_factor=1

def apply_transform(ob, use_location=True, use_rotation=True, use_scale=True):
    mb = ob.matrix_basis
    I = Matrix()
    loc, rot, scale = mb.decompose()

    # rotation
    T = Matrix.Translation(loc)
    #R = rot.to_matrix().to_4x4()
    R = mb.to_3x3().normalized().to_4x4()
    S = Matrix.Diagonal(scale).to_4x4()

    transform = [I, I, I]
    basis = [T, R, S]

    def swap(i):
        transform[i], basis[i] = basis[i], transform[i]

    if use_location:
        swap(0)
    if use_rotation:
        swap(1)
    if use_scale:
        swap(2)
        
    M = transform[0] @ transform[1] @ transform[2]
    if hasattr(ob.data, "transform"):
        ob.data.transform(M)
    for c in ob.children:
        c.matrix_local = M @ c.matrix_local
        
    ob.matrix_basis = basis[0] @ basis[1] @ basis[2]

def ext_row(rowdata):
    row=[0,0,0,0]
    row[0]=rowdata['X']
    row[1]=rowdata['Y']
    row[2]=rowdata['Z']
    row[3]=rowdata['W']
    return row

def get_curve_length(ob):
    total=0
    me = ob.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    for i in bm.edges:
        total+=i.calc_length()
    return total

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
     basename=mesh['basename']
     if basename in dict.keys():
         if mesh['appearance'] not in dict[basename]['apps']:
             dict[basename]['apps'].append(mesh['appearance'])
         if mesh['sector'] not in dict[basename]['sectors']:
            dict[basename]['sectors'].append(mesh['sector'])
     else:
         dict[basename]={'apps':[mesh['appearance']],'sectors':[mesh['sector']]}


def get_pos(inst):
    pos=[0,0,0]
    if 'Position' in inst.keys():
        if 'Properties' in inst['Position'].keys():
            pos[0] = inst['Position']['Properties']['X'] /scale_factor
            pos[1] = inst['Position']['Properties']['Y'] /scale_factor
            pos[2] = inst['Position']['Properties']['Z'] /scale_factor          
        else:
            if 'X' in inst['Position'].keys():
                pos[0] = inst['Position']['X'] /scale_factor
                pos[1] = inst['Position']['Y'] /scale_factor
                pos[2] = inst['Position']['Z'] /scale_factor
            else:
                pos[0] = inst['Position']['x'] /scale_factor
                pos[1] = inst['Position']['y'] /scale_factor
                pos[2] = inst['Position']['z'] /scale_factor
    elif 'position' in inst.keys():
        if 'X' in inst['position'].keys():
                pos[0] = inst['position']['X'] /scale_factor
                pos[1] = inst['position']['Y'] /scale_factor
                pos[2] = inst['position']['Z'] /scale_factor
    elif 'translation' in inst.keys():
        pos[0] = inst['translation']['X'] /scale_factor
        pos[1] = inst['translation']['Y'] /scale_factor
        pos[2] = inst['translation']['Z'] /scale_factor
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
            scale[0] = inst['Scale']['Properties']['X'] /scale_factor
            scale[1] = inst['Scale']['Properties']['Y'] /scale_factor
            scale[2] = inst['Scale']['Properties']['Z'] /scale_factor
        else:
            scale[0] = inst['Scale']['X'] /scale_factor
            scale[1] = inst['Scale']['Y'] /scale_factor
            scale[2] = inst['Scale']['Z'] /scale_factor
    elif 'scale' in inst.keys():
        scale[0] = inst['scale']['X'] /scale_factor
        scale[1] = inst['scale']['Y'] /scale_factor
        scale[2] = inst['scale']['Z'] /scale_factor
    return scale

def get_col(color):
    col=[0,0,0]
    col[0] = color['Red']/255
    col[1] = color['Green']/255
    col[2] = color['Blue']/255    
    return col


def get_tan_pos(inst):
    pos=[[0,0,0],[0,0,0]]
    if 'Elements' in inst.keys():
        pos[0][0] = inst['Elements'][0]['X'] 
        pos[0][1] = inst['Elements'][0]['Y'] 
        pos[0][2] = inst['Elements'][0]['Z'] 
        pos[1][0] = inst['Elements'][1]['X'] 
        pos[1][1] = inst['Elements'][1]['Y'] 
        pos[1][2] = inst['Elements'][1]['Z'] 
    return pos

def importSectors( filepath='', want_collisions=False, am_modding=False, with_materials=True, remap_depot=False ):
    # Enter the path to your projects source\raw\base folder below, needs double slashes between folder names.
    path = os.path.join( os.path.dirname(filepath),'source','raw','base')
    print('path is ',path)
    project=os.path.dirname(filepath)
    # If your importing to edit the sectors and want to add stuff then set the am_modding to True and it will auto create the _new collectors
    # want_collisions when True will import/generate the box and capsule collisions
    
    if scale_factor==1:
        # Set the view clip to 10000 so you can actually see the models were imported (used to scale down by 100)
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_end = 50000

    jsonpath = glob.glob(os.path.join(path, "**", "*.streamingsector.json"), recursive = True)
    print(jsonpath)
    meshes=[]
    C = bpy.context
    # Use object wireframe colors not theme - doesnt work need to find hte viewport as the context doesnt return that for this call 
   # bpy.context.space_data.shading.wireframe_color_type = 'OBJECT'
    for filepath in jsonpath:
        if filepath==os.path.join(path,os.path.basename(project)+'.streamingsector.json'):
            continue
        if VERBOSE:
            print(os.path.join(path,os.path.basename(project)+'.streamingsector.json'))
            print(filepath)
        with open(filepath,'r') as f: 
                j=json.load(f) 
        sectorName=os.path.basename(filepath)[:-5]
        t=j['Data']['RootChunk']['nodeData']['Data']
        nodes = j["Data"]["RootChunk"]["nodes"]
        #print(len(nodes))
        #nodes=[]
        for i,e in enumerate(nodes):
            data = e['Data']
            type = data['$type']
            match type:
                case 'worldEntityNode'|'worldDeviceNode': 
                    #print('worldEntityNode',i)
                    meshname = data['entityTemplate']['DepotPath']['$value'].replace('\\', os.sep)
                    if(meshname != 0):
                        meshes.append({'basename':e['Data']['entityTemplate']['DepotPath']['$value'],'appearance':e['Data']['appearanceName'],'sector':sectorName})
                case 'worldInstancedMeshNode':
                    meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                    if(meshname != 0):
                        meshes.append({'basename':data['mesh']['DepotPath']['$value'] ,'appearance':e['Data']['meshAppearance'],'sector':sectorName})
                case 'worldStaticMeshNode' |'worldRotatingMeshNode'|'worldAdvertisingNode'| 'worldPhysicalDestructionNode' | 'worldBakedDestructionNode' | 'worldBuildingProxyMeshNode' \
                    | 'worldGenericProxyMeshNode'| 'worldTerrainProxyMeshNode' | 'worldBendedMeshNode'| 'worldCableMeshNode' | 'worldClothMeshNode': 
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                            #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                            meshes.append({'basename':data['mesh']['DepotPath']['$value'] ,'appearance':e['Data']['meshAppearance'],'sector':sectorName})
                case 'worldInstancedDestructibleMeshNode':
                    #print('worldInstancedDestructibleMeshNode',i)
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        #print('Mesh name is - ',meshname, e['HandleId'])
                        if(meshname != 0):
                            meshes.append({'basename':data['mesh']['DepotPath']['$value'] ,'appearance':e['Data']['meshAppearance'],'sector':sectorName})
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
    Masters.hide_viewport=False #if its hidden it breaks entity positioning for some reason?!?

    # could take this out but its useful in edge cases.
    from_mesh_no=0
    to_mesh_no=100000

    for i,m in enumerate(meshes_w_apps):
        if i>=from_mesh_no and i<=to_mesh_no and m[-4:]=='mesh':
            apps=[]
            for meshApp in meshes_w_apps[m]['apps']:
                apps.append(meshApp['$value'])
            #if len(apps)>1:
            #    print(len(apps))
            impapps=','.join(apps)
            #print(os.path.join(path, m[:-4]+'glb'),impapps)

            meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb').replace('\\', os.sep)
            print(meshpath)
            groupname = os.path.splitext(os.path.split(meshpath)[-1])[0]
            while len(groupname) > 63:
                groupname = groupname[:-1]
            if groupname not in Masters.children.keys() and os.path.exists(meshpath):
                try:
                    bpy.ops.io_scene_gltf.cp77(filepath=meshpath, appearances=impapps, update_gi=False, with_materials=with_materials, remap_depot= remap_depot)
                    objs = C.selected_objects
                    move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                    coll_target.children.link(move_coll) 
                    coll_scene.children.unlink(move_coll)
                except:
                    print('failed on ',os.path.basename(meshpath))
            elif not os.path.exists(meshpath):
                print('Mesh ', meshpath, ' does not exist')
    empty=[]
    for child in Masters.children:
        if len(child.objects)<1:
            empty.append(child)
    
    for failed in empty:
        Masters.children.unlink(failed)
    inst_pos=(0,0,0)
    inst_rot =Quaternion((0.707,0,.707,0))
    inst_scale =Vector((1,1,1))
    inst_m=Matrix.LocRotScale(inst_pos,inst_rot,inst_scale)

    for fpn,filepath in enumerate(jsonpath):
        projectjson=os.path.join(path,'base',os.path.basename(project)+'.streamingsector.json')
        if filepath==projectjson:
            continue
        if VERBOSE:
            print(projectjson)
            print(filepath)
        with open(filepath,'r') as f: 
              j=json.load(f) 
          
        t=j['Data']['RootChunk']['nodeData']['Data']
        # add nodeDataIndex props to all the nodes in t
        for index, obj in enumerate(t):
            obj['nodeDataIndex']=index

        numExpectedNodes = len(t)
        sectorName=os.path.basename(filepath)[:-5]
    
        if sectorName in coll_scene.children.keys():
            Sector_coll=bpy.data.collections.get(sectorName)
        else:
            Sector_coll=bpy.data.collections.new(sectorName)
            coll_scene.children.link(Sector_coll)
        Sector_coll['filepath']=filepath
        Sector_coll['expectedNodes']=numExpectedNodes
    
        if am_modding==True:
            if sectorName+'_new' in coll_scene.children.keys():
                Sector_additions_coll=bpy.data.collections.get(sectorName+'_new')
            else:
                Sector_additions_coll=bpy.data.collections.new(sectorName+'_new')
                coll_scene.children.link(Sector_additions_coll)       

        meshes =  glob.glob(os.path.join(path, "**", "*.glb"), recursive = True)

        glbnames = [ os.path.basename(x) for x in meshes]
        meshnames = [ os.path.splitext(x)[0]+".mesh" for x in glbnames]

        nodes = j["Data"]["RootChunk"]["nodes"]
        print(fpn, ' Processing ',len(nodes),' nodes for sector', sectorName)
        group=''
        for i,e in enumerate(nodes):
    
            #if i % 20==0: 
            #   continue
            data = e['Data']
            type = data['$type']
            if True:# type=='worldBendedMeshNode' :#or type=='worldCableMeshNode': # can add a filter for dev here
                match type:
                    case 'worldEntityNode' | 'worldDeviceNode': 
                        #print('worldEntityNode',i)
                        app=data['appearanceName']["$value"]
                        entpath=os.path.join(path,data['entityTemplate']['DepotPath']['$value']).replace('\\', os.sep)+'.json'
                        ent_groupname=os.path.basename(entpath).split('.')[0]+'_'+app
                        while len(ent_groupname) > 63:
                            ent_groupname = ent_groupname[:-1]
                        imported=False
                        if ent_groupname in Masters.children.keys():
                            move_coll=Masters.children.get(ent_groupname)
                            imported=True
                        else:
                            try:
                                #print('Importing ',entpath, ' using app ',app)
                                incoll='MasterInstances'
                                bpy.ops.io_scene_gltf.cp77entity(filepath=entpath, appearances=app,with_materials=with_materials, inColl=incoll)
                                move_coll=Masters.children.get(ent_groupname)
                                imported=True
                            except:
                                print(traceback.print_exc())
                                print(f"Failed during Entity import on {entpath} from app {app}")
                        if imported:
                            instances = [x for x in t if x['NodeIndex'] == i]
                            for idx,inst in enumerate(instances):
                                #print(inst)
                                group=move_coll                            
                                if (group):
                                    groupname=move_coll.name
                                    #print('Group found for ',groupname)     
                                    new=bpy.data.collections.new(groupname)
                                    Sector_coll.children.link(new)
                                    new['nodeType']=type
                                    new['nodeIndex']=i
                                    new['nodeDataIndex']=inst['nodeDataIndex']
                                    new['instance_idx']=idx
                                    new['debugName']=e['Data']['debugName']
                                    new['sectorName']=sectorName 
                                    new['HandleId']=e['HandleId']
                                    new['entityTemplate']=os.path.basename(data['entityTemplate']['DepotPath']['$value'])
                                    new['appearanceName']=data['appearanceName']
                                    new['pivot']=inst['Pivot']

                                    if len(group.all_objects)>0:
                                        new['matrix']=group.all_objects[0].matrix_local
                                    pos = Vector(get_pos(inst))
                                    rot=[0,0,0,0]
                                    scale =Vector((1/scale_factor,1/scale_factor,1/scale_factor))
                                    rot =Quaternion(get_rot(inst))
                                    inst_trans_mat=Matrix.LocRotScale(pos,rot,scale)
                                    for child in group.children:
                                        newchild=bpy.data.collections.new(child.name)
                                        new.children.link(newchild)
                                        for old_obj in child.objects:                            
                                            obj=old_obj.copy()  
                                            newchild.objects.link(obj)                                     
                                            obj.matrix_local=  inst_trans_mat @ obj.matrix_local 
                                            if 'Armature' in obj.name:
                                                obj.hide_set(True)
                                    for old_obj in group.objects:                            
                                        obj=old_obj.copy()  
                                        new.objects.link(obj)                                     
                                        obj.matrix_local=  inst_trans_mat @ obj.matrix_local 
                                        if 'Armature' in obj.name:
                                            obj.hide_set(True)
                       
                    case 'worldBendedMeshNode' | 'worldCableMeshNode' :
                        #print(type)
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep) 
                        instances = [x for x in t if x['NodeIndex'] == i]
                        #if len(instances)>1:
                        #    print('Multiple Instances of node ',i)
                        if len(instances)>0 and (meshname != 0):
                            node=nodes[i]
                            defData=node['Data']['deformationData']
                            coll_scene = C.scene.collection

                            inst_pos=(0,0,0)
                            inst_rot =Quaternion((0.707,0,.707,0))
                            inst_scale =Vector((1,1,1))
                            inst_m=Matrix.LocRotScale(inst_pos,inst_rot,inst_scale)

                            joints=[]
                            mesh_name = "bendable_"+str(i)
                            mesh_data = bpy.data.meshes.new(mesh_name)

                            for idx,tt in enumerate(defData):   
                                M=Matrix((ext_row(defData[idx]['X']),ext_row(defData[idx]['Y']),ext_row(defData[idx]['Z']),ext_row(defData[idx]['W'])))
                                M=M.transposed()
                                joints.append(M.to_translation())
                            mesh_data.from_pydata(joints,[],[])
                            mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
                            #coll_scene.objects.link(mesh_obj)  

                            inst=[n for n in t if n['NodeIndex']==i][0]
                            
                            mesh_obj.rotation_mode='QUATERNION'
                            mesh_obj.rotation_quaternion=get_rot(inst)
                            pos=get_pos(inst)
                            mesh_obj.location=pos
                            apply_transform(mesh_obj)
                               
                            curve=bpy.data.curves.new('worldSplineNode_','CURVE')    
                            curve.splines.new('BEZIER')
                            bzps=curve.splines[0].bezier_points
                            bzps.add(len(mesh_obj.data.vertices)-1)
                            for p_no,v in enumerate(mesh_obj.data.vertices):    
                                bzps[p_no].co=v.co
                                bzps[p_no].handle_left_type='AUTO'
                                bzps[p_no].handle_right_type='AUTO'
                                
                            curve_obj = bpy.data.objects.new('worldSplineNode_', curve)
                            
                            coll_scene.objects.link(curve_obj)
                            curvelength=get_curve_length(curve_obj)

                            groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                            while len(groupname) > 63:
                                groupname = groupname[:-1]
                            group=Masters.children.get(groupname)
                            if (group):
                                new=bpy.data.collections.new(groupname)
                                Sector_coll.children.link(new)
                                new['nodeType']=type
                                new['nodeIndex']=i
                                new['nodeDataIndex']=inst['nodeDataIndex']
                                new['mesh']=meshname
                                new['debugName']=e['Data']['debugName']
                                new['sectorName']=sectorName 
                                

                                min_vertex = Vector((float('inf'), float('inf'), float('inf')))
                                max_vertex = Vector((float('-inf'), float('-inf'), float('-inf')))
                                for obj in group.all_objects:
                                    if obj.type == 'MESH':
                                        matrix = obj.matrix_world
                                        mesh = obj.data
                                        for vertex in mesh.vertices:
                                            vertex_world = matrix @ vertex.co
                                            min_vertex = Vector(min(min_vertex[i], vertex_world[i]) for i in range(3))
                                            max_vertex = Vector(max(max_vertex[i], vertex_world[i]) for i in range(3))
                                meshxLength=min_vertex[0]-max_vertex[0]
                                meshXScale=curvelength/meshxLength
                                meshyLength=min_vertex[1]-max_vertex[1]
                                meshYScale=curvelength/meshyLength
                                for old_obj in group.all_objects:                            
                                    obj=old_obj.copy()  
                                    new.objects.link(obj) 
                                    if obj.type=='MESH':
                                        curveMod=obj.modifiers.new('Curve','CURVE')
                                        if curveMod:
                                            curveMod.object=curve_obj
                                            if type=='worldCableMeshNode':
                                                curveMod.deform_axis='NEG_X'
                                                obj.scale.x=abs(meshXScale)
                                            if type=='worldBendedMeshNode':
                                                curveMod.deform_axis='POS_Y'
                                                obj.scale.y=abs(meshYScale)
                                                obj.rotation_mode='QUATERNION'
                                                obj.rotation_quaternion = Quaternion((0.707,0,0.707,0))
    
                    case 'worldInstancedMeshNode' :
                        #print('worldInstancedMeshNode')
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep) 
                        num=data['worldTransformsBuffer']['numElements']
                        start=data['worldTransformsBuffer']['startIndex']
                        if(meshname != 0):
                            #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                            groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                            while len(groupname) > 63:
                                groupname = groupname[:-1]
                            group=Masters.children.get(groupname)
                            if (group):
                                #print('Group found for ',groupname)                               
                                for idx in range(start, start+num):
                                    #create the linked copy of the group of mesh
                                
                                    new=bpy.data.collections.new(groupname)
                                    Sector_coll.children.link(new)
                                    new['nodeType']=type
                                    new['nodeIndex']=i
                                    new['nodeDataIndex']=inst['nodeDataIndex']
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
                                        obj['matrix']=obj.matrix_world
                                        #if obj.location.x == 0:
                                        #    print('Location @ 0 for Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])

                            else:
                                print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])
                                                    
                    case 'XworldDecorationMeshNode': 
                        #print('worldDecorationMeshNode',i)
                        pass
                    case 'XworldInstancedOccluderNode':
                        #print('worldInstancedOccluderNode')
                        pass
                    case 'worldStaticDecalNode':
                        #print('worldStaticDecalNode')
                        # decals are imported as planes tagged with the material details so you can see what they are and move them.
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for idx,inst in enumerate(instances):
                            #print( inst)
                            #o = bpy.data.objects.new( "empty", None )
                            vert = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (-0.5, 0.5, 0.0), (0.5,0.5, 0.0)]
                            fac = [(0, 1, 3, 2)]
                            pl_data = bpy.data.meshes.new("PL")
                            pl_data.from_pydata(vert, [], fac)
                            o = bpy.data.objects.new("Decal_Plane", pl_data)
                            o['nodeType']='worldStaticDecalNode'
                            o['nodeIndex']=i
                            o['instance_idx']=idx
                            o['decal']=e['Data']['material']['DepotPath']['$value']
                            o['debugName']=e['Data']['debugName']
                            o['sectorName']=sectorName
                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)
                            #o.empty_display_size = 0.002
                            #o.empty_display_type = 'IMAGE'
                            if with_materials:
                                mipath = o['decal']
                                jsonpath = os.path.join(path,mipath)+".json"
                                #print(jsonpath)
                                try:
                                    with open(jsonpath,'r') as jsonpath:
                                        obj=json.load(jsonpath)
                                    index = 0
                                    obj["Data"]["RootChunk"]['alpha'] = e['Data']['alpha']
                                    #FIXME: image_format
                                    builder = MaterialBuilder(obj,path,'png',path)
                                    bpymat = builder.create(index)
                                    o.data.materials.append(bpymat)
                                except FileNotFoundError:
                                    name = os.path.basename(jsonpath)
                                    print(f'File not found {name} ({jsonpath}), you need to export .mi files')
                            else:
                                o.display_type = 'WIRE'
                                o.color = (1.0, 0.905, .062, 1)
                                o.show_wire = True
                                o.display.show_shadows = False

                    case 'XworldStaticOccluderMeshNode':
                        #print('worldStaticOccluderMeshNode',i)
                        pass
                    
                    case 'worldSplineNode':
                        #print('worldSplineNode',i)
                        instances = [x for x in t if x['NodeIndex'] == i]
                        if len(instances)>0:
                            spline_node=e
                            spline_ndata=instances[0]
                            pos=get_pos(spline_ndata)
                            splineData=spline_node['Data']['splineData']
                            curve=bpy.data.curves.new('worldSplineNode_'+str(i),'CURVE')
                            curve_obj = bpy.data.objects.new('worldSplineNode_'+str(i), curve)
                            coll_scene.objects.link(curve_obj)
                            curve_obj['nodeType']='worldSplineNode'
                            curve_obj['nodeIndex']=i
                            curve_obj['sectorName']=sectorName
                            curve.splines.new('BEZIER')
                            bzps=curve.splines[0].bezier_points
                            bzps.add(len(splineData['Data']['points'])-1)
                            for p_no,point in enumerate(splineData['Data']['points']):
                                point_pos=list(map(add, pos, get_pos(point)))
                                bzps[p_no].co=point_pos
                                bzps[p_no].handle_left_type='AUTO'
                                bzps[p_no].handle_right_type='AUTO'
                                tans=get_tan_pos(point['tangents'])
                                bzps[p_no].handle_right=list(map(add, point_pos,tans[0]))
                                bzps[p_no].handle_left=list(map(add, point_pos,tans[1]))                     
                        pass

                    case 'worldRoadProxyMeshNode' : 
                        if isinstance(e, dict) and 'mesh' in data.keys():
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
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
                                                new['nodeDataIndex']=inst['nodeDataIndex']
                                                new['mesh']=meshname
                                                new['debugName']=e['Data']['debugName']
                                                new['sectorName']=sectorName
                                                new['pivot']=inst['Pivot']
                                            
                                                for old_obj in group.all_objects:                            
                                                    obj=old_obj.copy()  
                                                    new.objects.link(obj)                             

                                                    obj.location = get_pos(inst)
                                                
                                                    # if obj.location.x == 0:
                                                    #    print('Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])
                                                    curse=bpy.context.scene.cursor.location
                                                    bpy.context.scene.cursor.location=Vector((inst['Pivot']['X'] /scale_factor,inst['Pivot']['Y'] /scale_factor,inst['Pivot']['Z'] /scale_factor))
                                                    with bpy.context.temp_override(selected_editable_objects=obj):
                                                        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                                                
                                                    #print(i,obj.name,' x= ',obj.location.x, ' y= ', obj.location.y, ' z= ',obj.location.z)
                                                    obj.rotation_quaternion = get_rot(inst)
                                                    obj.scale = get_scale(inst)
                                                    bpy.context.scene.cursor.location=curse  
                                        else:
                                            print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])

                    case 'worldStaticMeshNode' |'worldRotatingMeshNode'| 'worldPhysicalDestructionNode' | 'worldBakedDestructionNode' | 'worldBuildingProxyMeshNode' | 'worldAdvertismentNode' | \
                'worldGenericProxyMeshNode'| 'worldTerrainProxyMeshNode' | 'worldClothMeshNode' | 'worldDecorationMeshNode': 
                        if isinstance(e, dict) and 'mesh' in data.keys():
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                            #print('Mesh name is - ',meshname, e['HandleId'])
                            meshAppearance = data['meshAppearance']['$value'] # Need to actually use this
                            if(meshname != 0):
                                        #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                        groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                                        while len(groupname) > 63:
                                            groupname = groupname[:-1]
                                        group=Masters.children.get(groupname)
                                        if (group):
                                            #print('Group found for ',groupname)
                                            if type=='worldRotatingMeshNode':
                                                rot_axis=data['rotationAxis']
                                                axis_no=0
                                                if rot_axis=='Z':
                                                    axis_no=1
                                                elif rot_axis=='Y': #y & z are swapped
                                                    axis_no=2
                                                
                                                rot_time=data['fullRotationTime']
                                                reverse=data['reverseDirection']

                                            instances = [x for x in t if x['NodeIndex'] == i]
                                            for idx,inst in enumerate(instances):
                                                new=bpy.data.collections.new(groupname)
                                                Sector_coll.children.link(new)
                                                new['nodeType']=type
                                                new['nodeIndex']=i
                                                new['nodeDataIndex']=inst['nodeDataIndex']
                                                new['instance_idx']=idx
                                                new['mesh']=meshname
                                                new['debugName']=e['Data']['debugName']
                                                new['sectorName']=sectorName
                                                new['pivot']=inst['Pivot']

                                                print(new['nodeDataIndex'])
                                            
                                                for old_obj in group.all_objects:                            
                                                    obj=old_obj.copy()  
                                                    new.objects.link(obj)                             
                                                    
                                                    obj.location = get_pos(inst)
                                                    obj.rotation_quaternion = get_rot(inst)
                                                    obj.scale = get_scale(inst)                                                                                                        
                                                    
                                                    if 'Armature' in obj.name:
                                                        obj.hide_set(True)
                                                    if type=='worldRotatingMeshNode':
                                                        orig_rot= obj.rotation_quaternion
                                                        obj.rotation_mode='XYZ'
                                                        obj.keyframe_insert('rotation_euler', index=axis_no ,frame=1)
                                                        obj.rotation_euler[axis_no] = obj.rotation_euler[axis_no] +math.radians(360)
                                                        obj.keyframe_insert('rotation_euler', index=axis_no ,frame=rot_time*24)
                                                        if obj.animation_data.action:
                                                            obj_action = bpy.data.actions.get(obj.animation_data.action.name)
                                                            obj_fcu = obj_action.fcurves[0]
                                                            for pt in obj_fcu.keyframe_points:
                                                                pt.interpolation = 'LINEAR'


                                                        
                                        else:
                                            print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])
                                    
                    case 'worldInstancedDestructibleMeshNode':
                        #print('worldInstancedDestructibleMeshNode',i)
                        if isinstance(e, dict) and 'mesh' in data.keys():
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                            num=data['cookedInstanceTransforms']['numElements']
                            start=data['cookedInstanceTransforms']['startIndex']
                            #print('Mesh name is - ',meshname, e['HandleId'])
                            if(meshname != 0):
                                        #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                        groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
                                        while len(groupname) > 63:
                                            groupname = groupname[:-1]
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
                                                    new['nodeDataIndex']=inst['nodeDataIndex']
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
                                                
                                                    inst_trans_rot=Quaternion((inst_trans['orientation']['r'],inst_trans['orientation']['i'], inst_trans['orientation']['j'],inst_trans['orientation']['k']))  
                                                    inst_trans_pos=Vector(get_pos_whole(inst_trans))
                                                    inst_trans_scale=Vector((1,1,1))
                                                                                            
                                                    inst_pos =Vector(get_pos_whole(inst))
                                                    intr=get_rot(inst)
                                                    inst_rot =Quaternion((intr[0],intr[1],intr[2],intr[3]))
                                                    inst_scale =Vector((1,1,1))
                                                    inst_trans_m=Matrix.LocRotScale(inst_trans_pos,inst_trans_rot,inst_trans_scale)
                                                    inst_m=Matrix.LocRotScale(inst_pos,inst_rot,inst_scale)
                                                    tm= inst_m @ inst_trans_m
                                                    tm[0][3]=tm[0][3]/scale_factor
                                                    tm[1][3]=tm[1][3]/scale_factor
                                                    tm[2][3]=tm[2][3]/scale_factor
                                                    new['inst_rot']=inst_rot
                                                    new['inst_pos']=inst_pos
                                                    new['inst_trans_rot']=inst_trans_rot
                                                    new['inst_trans_pos']=inst_trans_pos

                                                    for old_obj in group.all_objects:                            
                                                        obj=old_obj.copy()  
                                                        new.objects.link(obj)   
                                                        obj.matrix_local= tm   
                                                        obj.scale=get_scale(inst)
                                                        if 'Armature' in obj.name:
                                                            obj.hide_set(True)  
                                        else:
                                            print('Mesh not found - ',meshname, ' - ',i, e['HandleId'])

                    case 'worldStaticLightNode':
                        #print('worldStaticLightNode',i)
                        
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for inst in instances:
                            light_node=e['Data']
                            light_ndata=inst
                            color= light_node['color']  
                            intensity=light_node['intensity']        
                            flicker=light_node['flicker'] 
                            area_shape=light_node['areaShape']
                            pos=get_pos(light_ndata)
                            rot=get_rot(light_ndata)
                            
                            A_Light=bpy.data.lights.new('worldStaticLightNode_'+str(i),'AREA')
                            light_obj=bpy.data.objects.new('worldStaticLightNode_'+str(i), A_Light)
                            Sector_coll.objects.link(light_obj)
                            light_obj.location=pos
                            light_obj.rotation_mode='QUATERNION'
                            light_obj.rotation_quaternion=rot
                            A_Light.energy = intensity
                            A_Light.color = get_col(color)
                            
                            if area_shape=='ALS_Capsule':                        
                                A_Light.shape='ELLIPSE'
                                A_Light.size= light_node['capsuleLength']
                                A_Light.size_y= light_node['radius']*2
                            elif area_shape=='ALS_Sphere':                        
                                A_Light.shape='DISK'
                                A_Light.size= light_node['radius']*2

                        pass

                    case 'worldCollisionNode':
                    
        #   ______      _____      _                 
        #  / ____/___  / / (_)____(_)___  ____  _____
        # / /   / __ \/ / / / ___/ / __ \/ __ \/ ___/
        #/ /___/ /_/ / / / (__  ) / /_/ / / / (__  ) 
        #\____/\____/_/_/_/____/_/\____/_/ /_/____/  
        #                                            
        # Collisions are only partially supported, cant get the mesh object ones out of the geomCache from wkit enmasse currently so only box and capsule ones
                        if want_collisions:
                            #print('worldCollisionNode',i)
                            sector_Collisions=sectorName+'_colls'
                            if sector_Collisions in coll_scene.children.keys():
                                sector_Collisions_coll=bpy.data.collections.get(sector_Collisions)
                            else:
                                sector_Collisions_coll=bpy.data.collections.new(sector_Collisions)
                                coll_scene.children.link(sector_Collisions_coll) 
                            inst = [x for x in t if x['NodeIndex'] == i][0]
                            Actors=e['Data']['compiledData']['Data']['Actors']
                            for idx,act in enumerate(Actors):
                                #print(len(act['Shapes']))
                                x=act['Position']['x']['Bits']/131072*scale_factor  
                                y=act['Position']['y']['Bits']/131072*scale_factor
                                z=act['Position']['z']['Bits']/131072*scale_factor
                                arot=get_rot(act)
                                for s,shape in enumerate(act['Shapes']):
                                    if shape['ShapeType']=='Box':
                                        #print('Box Collision Node')
                                        #pprint(act['Shapes'])
                                        ssize=shape['Size']
                                        spos=get_pos(shape)
                                        srot=get_rot(shape)
                                        arot_q = Quaternion((arot[0],arot[1],arot[2],arot[3]))
                                        srot_q = Quaternion((srot[0],srot[1],srot[2],srot[3]))
                                        rot= arot_q @ srot_q
                                        loc=(spos[0]+x,spos[1]+y,spos[2]+z)
                                        bpy.ops.mesh.primitive_cube_add(size=1/scale_factor, scale=(ssize['X'],ssize['Y'],ssize['Z']),location=loc)
                                        cube=C.selected_objects[0]
                                        cube.name='NodeDataIndex_'+str(inst['nodeDataIndex'])+'_Actor_'+str(idx)+'_Shape_'+str(s)
                                        par_coll=cube.users_collection[0]
                                        par_coll.objects.unlink(cube)
                                        sector_Collisions_coll.objects.link(cube)
                                        cube['nodeIndex']=i
                                        cube['nodeDataIndex']=inst['nodeDataIndex']
                                        cube['ShapeType']=shape['ShapeType']
                                        cube['ShapeNo']=s
                                        cube['ActorIdx']=idx
                                        cube['sectorName']=sectorName
                                        cube.rotation_mode='QUATERNION'
                                        cube.rotation_quaternion=rot
                                        set_collider_props(cube, shape['ShapeType'], shape['Materials'][0]['$value'], 'WORLD')
                                
                                    elif shape['ShapeType']=='Capsule':
                                        #print('Capsule Collision Node')
                                        ssize=shape['Size']
                                        spos=get_pos(shape)
                                        srot=get_rot(shape)
                                        arot_q = Quaternion((arot[0],arot[1],arot[2],arot[3]))
                                        srot_q = Quaternion((srot[0],srot[1],srot[2],srot[3]))
                                        rot= arot_q @ srot_q
                                        loc=(spos[0]+x,spos[1]+y,spos[2]+z)
                                        bpy.ops.mesh.primitive_cylinder_add(radius=5/scale_factor, depth=1/scale_factor, scale=(ssize['X'],ssize['Y'],ssize['Z']),location=loc)
                                        capsule=C.selected_objects[0]
                                        capsule.name='NodeDataIndex_'+str(inst['nodeDataIndex'])+'_Actor_'+str(idx)+'_Shape_'+str(s)
                                        par_coll=capsule.users_collection[0]
                                        par_coll.objects.unlink(capsule)
                                        sector_Collisions_coll.objects.link(capsule)
                                        capsule['nodeIndex']=i
                                        capsule['nodeDataIndex']=inst['nodeDataIndex']
                                        capsule['ShapeType']=shape['ShapeType']
                                        capsule['ShapeNo']=s
                                        capsule['ActorIdx']=idx
                                        capsule['sectorName']=sectorName                                        
                                        capsule.rotation_mode='QUATERNION'
                                        capsule.rotation_quaternion=rot
                                        set_collider_props(cube, shape['ShapeType'], shape['Materials'][0]['$value'], 'WORLD')
                                    else: 
                                        print(f"skipping unsupported shape {shape['ShapeType']}")

                
                    case _:
                        #print('None of the above',i)
                        pass
                # Have to do a view_layer update or the matrices are all blank
                bpy.context.view_layer.update()                
                for col in Sector_coll.children:
                    if len(col.objects)>0:
                        col['matrix']= col.objects[0].matrix_world
                        
        

        print('Finished with ',filepath)
    # doing this earlier in the file was breaking the entity postitioning. NO idea how that works, but be warned.    
    Masters.hide_viewport=True
    for obj in bpy.data.objects:
        if 'Decal' in obj.name:
            obj['matrix']=obj.matrix_world
    print('Finished Importing Sectors')



# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    filepath = 'F:\\CPMod\\judysApt\\judysApt.cpmodproj'

    importSectors( filepath, want_collisions=False, am_modding=False, with_materials=True )        
