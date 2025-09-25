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
from ..main.common import *
from ..jsontool import JSONTool
import glob
import os
import bpy
import math
import traceback
from mathutils import Vector, Matrix , Quaternion
from pathlib import Path
import time
import traceback
from pprint import pprint
from ..main.setup import MaterialBuilder, bcolors
from ..collisiontools.collisions import set_collider_props
from .collision_mesh_import import CP77CollisionTriangleMeshJSONimport_by_hashes
from operator import add
import bmesh
from .entity_import import *
from .import_with_materials import *
VERBOSE=True
scale_factor=1

def assign_custom_properties(obj, data, sectorName, i, **kwargs ):
    ntype=data['$type']
    obj['nodeType']=ntype
    obj['nodeIndex']=i
    if 'debugName' in data.keys():
        obj['debugName']=data['debugName']['$value']
    obj['sectorName']=sectorName
    if 'sourcePrefabHash' in data.keys():
        obj['sourcePrefabHash']=data['sourcePrefabHash']
    if ntype=='worldAISpotNode':
        if data['spot']:
            obj['workspot']=data['spot']['Data']['resource']['DepotPath']['$value']
        else: 
            obj['workspot']='None'
        if data['markings']:
            obj['markings']=data['markings'][0]['$value']
    if 'entityTemplate' in data.keys():
        obj['entityTemplate']=data['entityTemplate']['DepotPath']['$value']
    
    if 'appearanceName' in data.keys():
        obj['appearanceName']=data['appearanceName']['$value']
    elif 'meshAppearance'in data.keys():
        obj['appearanceName']=data['meshAppearance']['$value']
    else: 
        obj['appearanceName']=''
    
    # Assign any additional properties passed as kwargs
    for key, value in kwargs.items():
        obj[key] = value

def get_groupname(meshname, meshAppearance):
    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
    if 'intersection' in meshname:
        groupname = os.path.dirname(meshname).split(os.sep)[-1] + '_' + groupname
    if len(meshAppearance)>0:
        groupname += '@' + meshAppearance
    while len(groupname) > 63:
        groupname = groupname[:-1]
    return groupname

# Get the group name for the mesh based on its name and appearance
# group, groupname = get_group(meshname,meshAppearance)
def get_group(meshname,meshAppearance,Masters):
    groups= [g for g in Masters.children if 'meshpath' in g.keys() and g['meshpath']==meshname and 'appearance' in g.keys() and g['appearance']==meshAppearance]
    if len(groups)>0:
        group=groups[0]
        groupname = group.name
    else:
        groupname = get_groupname(meshname, meshAppearance)
        group = Masters.children.get(groupname)
        
    return group, groupname 

def find_debugName(obj):
    debugName=None
    if 'debugName' in obj.users_collection[0].keys():
        debugName=obj.users_collection[0]['debugName']
    else:
        if 'debugName' in D.collections[coll_parents.get(obj.users_collection[0].name)]:
            debugName=D.collections[coll_parents.get(obj.users_collection[0].name)]['debugName']
        else:
            if 'debugName' in D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]:
                debugName=D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]['debugName']
    return debugName

def points_within_tol(point1, point2, tolerance=0.01):
    """
    Check if two points are within a specified tolerance.

    :param point1: The first point as a tuple or list of (x, y, z) coordinates.
    :param point2: The second point as a tuple or list of (x, y, z) coordinates.
    :param tolerance: The tolerance within which the points should be to be considered close.
    :return: True if the points are within the tolerance, False otherwise.
    """
    # Calculate the Euclidean distance between the points
    distance = math.sqrt((point1[0] - point2[0]) ** 2 +
                         (point1[1] - point2[1]) ** 2 +
                         (point1[2] - point2[2]) ** 2)

    # Check if the distance is within the tolerance
    return distance <= tolerance

def average_vectors(vector1, vector2):
    """
    Calculate the average of two vectors.

    :param vector1: The first vector as a tuple or list of (x, y, z) coordinates.
    :param vector2: The second vector as a tuple or list of (x, y, z) coordinates.
    :return: The average vector as a tuple of (x, y, z) coordinates.
    """
    average = [(vector1[0] + vector2[0]) / 2,
                (vector1[1] + vector2[1]) / 2,
                (vector1[2] + vector2[2]) / 2]
    return Vector(average)

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

# add_to_list(m , meshes_w_apps)
def add_to_list(basename, meshes, dict):
     mesh = meshes[basename]
     if basename in dict:
        for app in mesh['appearances']:
            if app not in dict[basename]['apps']:
                dict[basename]['apps'].append(mesh['appearance'])
        if mesh['sector'] not in dict[basename]['sectors']:
            dict[basename]['sectors'].append(mesh['sector'])
     else:
        dict[basename]={'apps':[mesh['appearances']],'sectors':[mesh['sector']]}




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

def get_meshappearance(data):
    if 'meshAppearance' in data.keys():
        meshAppearance = data['meshAppearance']
    else:
        meshAppearance = {'$type': 'CName', '$storage': 'string', '$value': 'default'}
    return meshAppearance

def get_meshname(data):
    meshname=''
    if 'mesh' in data.keys() and isinstance(data['mesh'], dict) and'DepotPath' in data['mesh'].keys():
        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
    elif 'meshRef' in data.keys():
        meshname = data['meshRef']['DepotPath']['$value'].replace('\\', os.sep)
    elif 'entityTemplate' in data.keys() and isinstance(data['entityTemplate'], dict) and'DepotPath' in data['entityTemplate'].keys():
        meshname = data['entityTemplate']['DepotPath']['$value'].replace('\\', os.sep)
    return meshname

def importSectors( filepath, with_mats, remap_depot, want_collisions, am_modding, with_lights):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    if not cp77_addon_prefs.non_verbose:
        print('')
        print('-------------------- Importing Cyberpunk 2077 Streaming Sectors --------------------')
        print('')
    start_time = time.time()
    # Set this to true to limit import to the types listed in the import_types list.
    limittypes=False
    import_types=None
    import_types=['worldEntityNode'
    ]
    wkit_proj_name=os.path.basename(filepath)
    # Enter the path to your projects source\raw\base folder below, needs double slashes between folder names.
    path = os.path.join( os.path.dirname(filepath),'source','raw')
    print('path is ',path)
    sectorFiles = dataKrash(path, ('.glb', '.mesh.json', '.app.json', '.anims.json','.ent.json', '.anims.glb', '.streamingsector.json','.rig.json', '.phys.json'))
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
    props = bpy.context.scene.cp77_panel_props 
    escaped_path = glob.escape(path)    
    jsonpath = sectorFiles.get('.streamingsector.json', []) 
    mesh_jsons = sectorFiles.get('.mesh.json', [])
    anim_files = sectorFiles.get('.anims.glb', [])
    app_path = sectorFiles.get('.app.json', [])
    rigjsons = sectorFiles.get('.rig.json', [])
    glbs =  sectorFiles.get('.glb', [])
    path = os.path.join( os.path.dirname(filepath),'source','raw','base')
    meshes={}
    C = bpy.context
    I_want_to_break_free=False
    # Use object wireframe colors not theme - doesnt work need to find hte viewport as the context doesnt return that for this call
    # bpy.context.space_data.shading.wireframe_color_type = 'OBJECT'
    for filepath in jsonpath:
        if filepath==os.path.join(path,os.path.basename(project)+'.streamingsector.json'):
            continue
        if VERBOSE:
            print(os.path.join(path,os.path.basename(project)+'.streamingsector.json'))
        t, nodes = JSONTool.jsonload(filepath)
        sectorName=os.path.basename(filepath)[:-5]
        #print(len(nodes))
        #nodes=[]

        for i,e in enumerate(nodes):
            #print(i)
            data = e['Data']
            ntype = data['$type']
            if I_want_to_break_free:
                break
            if (limittypes and ntype in import_types) or limittypes==False :#or type=='worldCableMeshNode': # can add a filter for dev here
                meshname = get_meshname(data)
                meshAppearance= get_meshappearance(data)
                match ntype:
                    case 'worldEntityNode'|'worldDeviceNode':
                        #print('worldEntityNode',i)                        
                        if(meshname != 0):
                            if meshname not in meshes:
                                meshes[meshname] = {'appearances':[meshAppearance],'sector':sectorName}                        
                            else:
                                meshes[meshname]['appearances'].append(meshAppearance)
                    
                    case 'worldInstancedMeshNode':
                        if(meshname != 0):
                            if meshname not in meshes:
                                meshes[meshname] = {'appearances':[meshAppearance],'sector':sectorName}
                            else:
                                meshes[meshname]['appearances'].append(meshAppearance)
                    
                    case 'worldStaticMeshNode' |'worldRotatingMeshNode'|'worldAdvertisingNode'| 'worldAdvertisementNode' | 'worldPhysicalDestructionNode' | 'worldBakedDestructionNode'  \
                        |  'worldTerrainMeshNode' | 'worldBendedMeshNode'| 'worldCableMeshNode' | 'worldClothMeshNode'| 'worldDynamicMeshNode'\
                   | 'worldMeshNode' | 'worldStaticOccluderMeshNode' |'worldDecorationMeshNode' | 'worldFoliageNode':
                        if isinstance(e, dict) and 'mesh' in data.keys() and isinstance(data['mesh'], dict) and'DepotPath' in data['mesh'].keys():
                            #if ntype=='worldBendedMeshNode':
                            #    print('worldBendedMeshNode',i)
                            #print('Mesh name is - ',meshname, e['HandleId'])
                            if(meshname != 0):
                                #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                if meshname not in meshes:
                                    meshes[meshname] = {'appearances':[meshAppearance],'sector':sectorName}
                                else:
                                    meshes[meshname]['appearances'].append(meshAppearance)
                            
                        elif isinstance(e, dict) and 'meshRef' in data.keys() :
                            if(meshname != 0):
                                #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                if meshname not in meshes:
                                    meshes[meshname] = {'appearances':[{'$type': 'CName', '$storage': 'string', '$value': 'default'}],'sector':sectorName}
                                else:
                                    meshes[meshname]['appearances'].append({'$type': 'CName', '$storage': 'string', '$value': 'default'})
                    
                    case 'worldInstancedDestructibleMeshNode':
                        #print('worldInstancedDestructibleMeshNode',i)
                        if isinstance(e, dict) and 'mesh' in data.keys():                            
                            #print('Mesh name is - ',meshname, e['HandleId'])
                            if(meshname != 0):
                                if meshname not in meshes:
                                    meshes[meshname] = {'appearances':[meshAppearance],'sector':sectorName}
                                else:
                                    meshes[meshname]['appearances'].append(meshAppearance)

        # Do the proxy nodes after all the others, that way none proxies will be imported first and wont be hidden by the proxy ones
        for i,e in enumerate(nodes):
            data = e['Data']
            ntype = data['$type']
            if I_want_to_break_free:
                break
            if (limittypes and ntype in import_types) or limittypes==False :#or type=='worldCableMeshNode': # can add a filter for dev here
                match ntype:
                    case 'worldGenericProxyMeshNode'| 'worldTerrainProxyMeshNode' | 'worldDestructibleEntityProxyMeshNode' | 'worldBuildingProxyMeshNode':
                        if isinstance(e, dict) and 'mesh' in data.keys() and isinstance(data['mesh'], dict) and'DepotPath' in data['mesh'].keys():
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                            if(meshname != 0):
                                if 'meshAppearance' in e['Data'].keys():
                                    if meshname not in meshes:
                                        meshes[data['mesh']['DepotPath']['$value']] = {'appearances':[e['Data']['meshAppearance']],'sector':sectorName}
                                    else:
                                        meshes[data['mesh']['DepotPath']['$value']]['appearances'].append(e['Data']['meshAppearance'])
                                else:
                                    if meshname not in meshes:
                                        meshes[data['mesh']['DepotPath']['$value']] = {'appearances':[{'$type': 'CName', '$storage': 'string', '$value': 'default'}],'sector':sectorName}
                                    else:
                                        meshes[data['mesh']['DepotPath']['$value']]['appearances'].append({'$type': 'CName', '$storage': 'string', '$value': 'default'})
                        elif isinstance(e, dict) and 'meshRef' in data.keys() :
                            meshname = data['meshRef']['DepotPath']['$value'].replace('\\', os.sep)
                            if(meshname != 0):
                                if meshname not in meshes:
                                    meshes[data['meshRef']['DepotPath']['$value']]={'appearances':[{'$type': 'CName', '$storage': 'string', '$value': 'default'}],'sector':sectorName}
                                else:
                                    meshes[data['meshRef']['DepotPath']['$value']]['appearances'].append({'$type': 'CName', '$storage': 'string', '$value': 'default'})
                    


    basenames={}
    for m in meshes:
         if m not in basenames:
             basenames[m]=True

    meshes_w_apps={}

    for m in meshes:
       if len(m)>0:
            add_to_list(m , meshes, meshes_w_apps)

    path = path[:-5]

    coll_scene = C.scene.collection
    mis={}
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
        if i>=from_mesh_no and i<=to_mesh_no and (m[-4:]=='mesh' or m[-13:]=='physicalscene' or m[-6:]=='w2mesh'):
            apps=[]
            for meshApp in meshes_w_apps[m]['apps'][0]:
                if meshApp['$value'] not in apps and meshApp['$value']!='':                   
                    apps.append(meshApp['$value'])
            #if len(apps)>1:
            #    print(len(apps))
            #impapps=','.join(apps)
            #print(os.path.join(path, m[:-4]+'glb'),impapps)
            if m[-13:]=='physicalscene' or m[-6:]=='w2mesh':
                meshpath=os.path.join(path, m+'.glb').replace('\\', os.sep)
                print('not a standard mesh')
            else:
                meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb').replace('\\', os.sep)
            print(meshpath)
            groupname = get_groupname(meshpath, '')
            
            if groupname not in Masters.children.keys() and os.path.exists(meshpath):
                try:
                    JSONTool.start_caching()
                    CP77GLBimport( with_materials=with_mats,remap_depot= props.remap_depot, filepath=meshpath, appearances=apps,scripting=True)
                    JSONTool.stop_caching()
                    #bpy.ops.io_scene_gltf.cp77(with_mats, filepath=meshpath, appearances=impapps,scripting=True)
                    objs = C.selected_objects
                    if objs[0].users_collection[0].name!= groupname:
                        objs[0].users_collection[0].name= groupname
                    move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                    move_coll['meshpath']=m
                    move_coll['appearance']='default'
                    Masters.children.link(move_coll)
                    for app in apps:
                        # Create a completely new collection for this appearance
                        new_coll = bpy.data.collections.new(groupname + '@' + app)
                        Masters.children.link(new_coll)
                        new_coll['meshpath']=m
                        new_coll['appearance'] = app
                        # Set the appearance property
                        json_apps= None
                        if 'json_apps' in move_coll.keys():
                            json_apps =  json.loads(move_coll['json_apps'])
                        else:
                            print(f'{bcolors.FAIL}No material json found for - {m}{bcolors.ENDC}')
                        for idx,obj in enumerate(move_coll.objects):
                            obj_copy=obj.copy()
                            obj_copy.data = obj.data.copy()
                            if obj_copy.type == 'MESH':
                                if json_apps and app in json_apps and idx < len(json_apps[app]):
                                    # Assign the material from the json_apps if it exists
                                    mat_name = json_apps.get(app)[idx]
                                    if 'sidewalk' in m:
                                        mat_name = 'sidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalk'
                                        #print('Its too damn long', mat_name)
                                        #print(obj_copy.data.materials.keys())
                                    #if 'station' in groupname or 'fluorescent_light_b' in groupname:
                                    #    print('Pause here')
                                    #    print(mat_name, list(obj_copy.data.materials.keys()), mat_name in obj_copy.data.materials.keys())
                                    #if mat_name and mat_name in bpy.data.materials:
                                    if len(mat_name)<63 and len(obj_copy.data.materials)>1 and mat_name in obj_copy.data.materials.keys():
                                        for ii in range(len(obj_copy.data.materials)-1,-1,-1):
                                            mat=obj_copy.data.materials.keys()[ii]
                                            if mat.split('.')[0]!=mat_name:
                                                obj_copy.data.materials.pop(index=ii)
                            new_coll.objects.link(obj_copy)                    
                    coll_scene.children.unlink(move_coll)
                except:
                    print('failed on ',os.path.basename(meshpath))                    
                    print(traceback.print_exc())
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
    roads=[]
    no_sectors=len(jsonpath)
    for fpn,filepath in enumerate(jsonpath):
        projectjson=os.path.join(path,os.path.basename(project)+'.streamingsector.json')
        if filepath==projectjson:
            continue

        if 'sim_' in filepath:
            continue
        if VERBOSE:
            print(projectjson)
            print(filepath)
        # add nodeDataIndex props to all the nodes in t
        t, nodes = JSONTool.jsonload(filepath)
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

        print(fpn, ' Processing ',len(nodes),' nodes for sector', sectorName, '(no ', fpn+1, ' of ', no_sectors,')')
        group=''
        for i,e in enumerate(nodes):

            #if i % 20==0:
            #   continue
            data = e['Data']
            ntype = data['$type']
            meshAppearance='default'
            if 'meshAppearance' in data.keys():
                meshAppearance = data['meshAppearance']['$value'] # Need to actually use this
            if  (limittypes and ntype in import_types) or limittypes==False: #or type=='worldCableMeshNode': # can add a filter for dev here
                match ntype:
                    case 'worldAISpotNode':
                        instances = [x for x in t if x['NodeIndex'] == i]

                        print('worldAISpotNode',i)
                        if instances:
                            inst=instances[0]
                            o = bpy.data.objects.new( "empty", None )
                            assign_custom_properties(o, data,sectorName,i)
                            o.empty_display_size = 0.2
                            o.empty_display_type = 'CONE'
                            Sector_coll.objects.link(o) 
                            o.name= ntype+'_'+data['debugName']['$value']
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)

                    case 'worldEntityNode' | 'worldDeviceNode':
                        #print('worldEntityNode',i)
                        
                        app=data['appearanceName']["$value"]
                        entpath=os.path.join(path,data['entityTemplate']['DepotPath']['$value']).replace('\\', os.sep)+'.json'
                        ent_groupname=os.path.basename(entpath).split('.')[0]+'_'+app
                        if 'door' in ent_groupname:
                            print('Door entity found, pausing')
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
                                importEnt(with_mats, filepath=entpath, appearances=[app], inColl=incoll,meshes=glbs,mesh_jsons=mesh_jsons, escaped_path=escaped_path, app_path=app_path,
                                 anim_files=anim_files, rigjsons=rigjsons)
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
                                    move_coll['meshpath']='fake'
                                    move_coll['appearance']='fake'
                                    #print('Group found for ',groupname)
                                    new=bpy.data.collections.new(groupname)
                                    Sector_coll.children.link(new)
                                    assign_custom_properties(new, data,sectorName,i,ndi=inst['nodeDataIndex'],idx=idx,HandleId=e['HandleId'],pivot=inst['Pivot'])                                    
                                    pos = Vector(get_pos(inst))
                                    rot=[0,0,0,0]
                                    scale =Vector((1/scale_factor,1/scale_factor,1/scale_factor))
                                    rot =Quaternion(get_rot(inst))
                                    new['ent_rot']=rot.to_euler('XYZ')
                                    new['ent_pos']=pos
                                    inst_trans_mat=Matrix.LocRotScale(pos,rot,scale)
                                    #print('Entity transform matrix:', inst_trans_mat)
                                    for child in group.children:
                                        newchild=bpy.data.collections.new(child.name)
                                        new.children.link(newchild)
                                        for old_obj in child.objects:
                                            obj=old_obj.copy()
                                            obj.color = (0.567942, 0.0247339, 0.600028, 1)
                                            newchild.objects.link(obj)
                                            #print(obj.name, 'applying transform')
                                            #print("Before:", obj.matrix_local)
                                            if obj.parent:
                                                # Apply in local space relative to parent
                                                obj.matrix_local = inst_trans_mat @ obj.matrix_local
                                            else:
                                                # No parent, apply in world space
                                                obj.matrix_world = inst_trans_mat @ obj.matrix_world
                                            #print("After:", obj.matrix_local)
                                            if 'Armature' in obj.name:
                                                obj.hide_set(True)
                                        bpy.context.view_layer.update()
                                    for old_obj in group.objects:
                                        obj=old_obj.copy()
                                        obj.color = (0.567942, 0.0247339, 0.600028, 1)
                                        new.objects.link(obj)
                                        obj.matrix_local=  inst_trans_mat @ obj.matrix_local
                                        if 'Armature' in obj.name:
                                            obj.hide_set(True)
                                    if len(group.all_objects)>0:
                                        new['matrix']=group.all_objects[0].matrix_world

                    case 'worldBendedMeshNode' | 'worldCableMeshNode' :
                        #print(ntype)
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
                            curve.dimensions = '3D'
                            curve.twist_mode = 'Z_UP'
                            curve.resolution_u = 64
                            bzps=curve.splines[0].bezier_points
                            bzps.add(len(mesh_obj.data.vertices)-1)
                            for p_no,v in enumerate(mesh_obj.data.vertices):
                                bzps[p_no].co=v.co
                                bzps[p_no].handle_left_type='AUTO'
                                bzps[p_no].handle_right_type='AUTO'


                            curve_obj = bpy.data.objects.new('worldSplineNode_', curve)

                            coll_scene.objects.link(curve_obj)
                            curvelength=get_curve_length(curve_obj)

                            group, groupname = get_group(meshname,meshAppearance,Masters)
                            if (group):
                                new=bpy.data.collections.new(groupname)
                                Sector_coll.children.link(new)
                                assign_custom_properties(new, data,sectorName,i,
                                nodeDataIndex=inst['nodeDataIndex'],mesh=meshname)    
                                
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
                                    obj.color = (0.0380098, 0.595213, 0.600022, 1)
                                    new.objects.link(obj)
                                    if obj.type=='MESH':
                                        curveMod=obj.modifiers.new('Curve','CURVE')
                                        if curveMod:
                                            curveMod.object=curve_obj
                                            if ntype=='worldCableMeshNode':
                                                curveMod.deform_axis='NEG_X'
                                                obj.scale.x=abs(meshXScale)
                                            if ntype=='worldBendedMeshNode':
                                                curveMod.deform_axis='POS_Y'
                                                obj.scale.y=abs(meshYScale)
                                                obj.rotation_mode='QUATERNION'
                                                obj.rotation_quaternion = Quaternion((0.707,0,0.707,0))
                                                roads.append({'Mesh':obj, 'Curve':curve_obj,'Name':new['debugName'],'Startpos':bzps[0].co,'Endpos':bzps[-1].co})

                    case 'worldInstancedMeshNode' :
                        #print('worldInstancedMeshNode')
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for idx,inst in enumerate(instances):
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                            num=data['worldTransformsBuffer']['numElements']
                            start=data['worldTransformsBuffer']['startIndex']
                            if(meshname != 0):
                                #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                group, groupname = get_group(meshname,meshAppearance,Masters)
                                if (group):
                                    #print('Group found for ',groupname)
                                    NDI_Coll_name = 'NDI'+str(inst['nodeDataIndex'])+'_'+groupname
                                    while len(NDI_Coll_name) > 63:
                                            NDI_Coll_name = NDI_Coll_name[:-1]
                                    NDI_Coll = bpy.data.collections.new(NDI_Coll_name)
                                    Sector_coll.children.link(NDI_Coll)
                                    assign_custom_properties(NDI_Coll, data,sectorName,i,
                                    nodeDataIndex=inst['nodeDataIndex'],mesh=meshname,numElements=num)   
                                    
                                    for El_idx in range(start, start+num):
                                        #create the linked copy of the group of mesh
                                        new_groupname = 'NDI'+str(inst['nodeDataIndex'])+'_'+str(El_idx)+'_'+groupname
                                        while len(new_groupname) > 63:
                                            new_groupname = new_groupname[:-1]
                                        new = bpy.data.collections.new(new_groupname)
                                        NDI_Coll.children.link(new)
                                        assign_custom_properties(new, data,sectorName,i,
                                        nodeDataIndex=inst['nodeDataIndex'],mesh=meshname,Element_idx=El_idx) 
                                        
                                        for old_obj in group.all_objects:                            
                                            obj=old_obj.copy()  
                                            new.objects.link(obj)                                    
                                            if 'Data' in data['worldTransformsBuffer']['sharedDataBuffer'].keys():
                                                inst_trans=data['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']['Transforms'][El_idx]

                                            elif 'HandleRefId' in data['worldTransformsBuffer']['sharedDataBuffer'].keys():
                                                bufferID = int(data['worldTransformsBuffer']['sharedDataBuffer']['HandleRefId'])
                                                new['bufferID']=bufferID
                                                ref=e
                                                for n in nodes:
                                                    if n['HandleId']==str(bufferID-1):
                                                        ref=n
                                                inst_trans = ref['Data']['worldTransformsBuffer']['sharedDataBuffer']['Data']['buffer']['Data']['Transforms'][El_idx]
                                            else :
                                                print(e)
                                            obj.location = get_pos(inst_trans)
                                            obj.rotation_quaternion=get_rot(inst_trans)
                                            obj.scale = get_scale(inst_trans)
                                            obj['matrix']=obj.matrix_world
                                            obj.color = (0.785188, 0.409408, 0.0430124, 1)

                                            #if obj.location.x == 0:
                                            #    print('Location @ 0 for Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])

                            else:
                                print('Mesh not found in masters - ',meshname, ' - ',i, e['HandleId'])

                    case 'worldFoliageNode' :
                        #print('worldFoliageNode')
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for idx,inst in enumerate(instances):
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                            foliageResource=data['foliageResource']['DepotPath']['$value'].replace('\\', os.sep)+'.json'
                            if os.path.exists(os.path.join(path,foliageResource)):
                                frjson=JSONTool.jsonload(os.path.join(path,foliageResource))
                                inst_pos=get_pos(inst)
                                Bucketnum=data['populationSpanInfo']['cketCount']
                                Bucketstart=data['populationSpanInfo']['cketBegin']
                                InstBegin=data['populationSpanInfo']['stancesBegin']
                                InstCount=data['populationSpanInfo']['stancesCount']
                                if(meshname != 0):
                                    #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                    group, groupname = get_group(meshname,meshAppearance,Masters)
                                    if (group):
                                        #print('Group found for ',groupname)
                                        WFI_Coll_name = 'WFI_'+str(inst['nodeDataIndex'])+'_'+groupname
                                        while len(WFI_Coll_name) > 63:
                                                WFI_Coll_name = NDI_Coll_name[:-1]
                                        WFI_Coll = bpy.data.collections.new(WFI_Coll_name)
                                        Sector_coll.children.link(WFI_Coll)
                                        assign_custom_properties(WFI_Coll, data,sectorName,i,
                                        nodeDataIndex=inst['nodeDataIndex'],mesh=meshname,                                   
                                        Bucketnum=Bucketnum, Bucketstart=Bucketstart, InstBegin=InstBegin, InstCount=InstCount)
    
                                        PopSubIndex=frjson['Data']['RootChunk']['dataBuffer']['Data']['Buckets'][Bucketstart]['PopulationSubIndex']
                                        PopSubCount=frjson['Data']['RootChunk']['dataBuffer']['Data']['Buckets'][Bucketstart]['PopulationCount']
                                        inst_pos =Vector(get_pos_whole(inst))
                                        intr=get_rot(inst)
                                        inst_rot =Quaternion((intr[0],intr[1],intr[2],intr[3]))
                                        inst_scale =Vector((1,1,1))
                                        inst_m=Matrix.LocRotScale(inst_pos,inst_rot,inst_scale)

                                        for El_idx in range(InstBegin+PopSubIndex, InstBegin+InstCount):
                                            #create the linked copy of the group of mesh
                                            new_groupname = 'WFI'+str(inst['nodeDataIndex'])+'_'+str(El_idx)+'_'+groupname
                                            while len(new_groupname) > 63:
                                                new_groupname = new_groupname[:-1]
                                            new = bpy.data.collections.new(new_groupname)
                                            WFI_Coll.children.link(new)
                                            assign_custom_properties(new, data,sectorName,i,
                                            nodeDataIndex=inst['nodeDataIndex'],mesh=meshname,Element_idx=El_idx) 
                                        
                                            popInfo=frjson['Data']['RootChunk']['dataBuffer']['Data']['Populations'][El_idx]
                                            inst_trans_rot=Quaternion((popInfo['Rotation']['W'],popInfo['Rotation']['X'], popInfo['Rotation']['Y'],popInfo['Rotation']['Z']))
                                            inst_trans_pos=Vector(get_pos(popInfo))
                                            inst_trans_scale=Vector((popInfo['Scale'],popInfo['Scale'],popInfo['Scale']))
                                            inst_trans_m=Matrix.LocRotScale(inst_trans_pos,inst_trans_rot,inst_trans_scale)

                                            tm= inst_m @ inst_trans_m

                                            for old_obj in group.all_objects:
                                                obj=old_obj.copy()
                                                new.objects.link(obj)

                                                obj.matrix_local = tm
                                                obj['matrix']=obj.matrix_world
                                                obj.color = (0.0, 1.0, 0.0, 1)

                                                #if obj.location.x == 0:
                                                #    print('Location @ 0 for Mesh - ',meshname, ' - ',i,'HandleId - ', e['HandleId'])

                                else:
                                    print('Mesh not found in masters - ',meshname, ' - ',i, e['HandleId'])

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
                            pl_data.uv_layers.new(name="UVMap")

                            o = bpy.data.objects.new("Decal_Plane", pl_data)
                            assign_custom_properties(o, data,sectorName,i,
                            instance_idx=idx,mesh=meshname,
                            decal=data['material']['DepotPath']['$value'],
                            horizontalFlip=data['horizontalFlip'],
                            verticalFlip=data['verticalFlip'],
                            alpha=data['alpha'])
                            
                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)

                            #o.empty_display_size = 0.002
                            #o.empty_display_type = 'IMAGE'
                            if with_mats:
                                mipath = o['decal']
                                jsonpath = os.path.join(path,mipath)+".json"
                                #print(jsonpath)
                                try:
                                    obj=JSONTool.jsonload(jsonpath)
                                    index = 0
                                    obj["Data"]["RootChunk"]['alpha'] = data['alpha']
                                    #FIXME: image_format
                                    if mipath in mis.keys():
                                        bpymat = mis[mipath]
                                    else:
                                        builder = MaterialBuilder(obj,path,'png',path)
                                        bpymat = builder.createdecal(index)
                                        mis[mipath] = bpymat
                                    if bpymat:
                                        o.data.materials.append(bpymat)
                                    else:
                                        o.display_type = 'WIRE'
                                        o.color = (1.0, 0.905, .062, 1)
                                        o.show_wire = True
                                        o.display.show_shadows = False
                                except FileNotFoundError:
                                    name = os.path.basename(jsonpath)
                                    print(f'File not found {name} ({jsonpath}), you need to export .mi files')
                                    o.display_type = 'WIRE'
                                    o.color = (1.0, 0.905, .062, 1)
                                    o.show_wire = True
                                    o.display.show_shadows = False
                            else:
                                o.display_type = 'WIRE'
                                o.color = (1.0, 0.905, .062, 1)
                                o.show_wire = True
                                o.display.show_shadows = False

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
                            #meshpath=os.path.join(path, meshname[:-4]+'glb')
                            meshpath=os.path.join(path, meshname[:-1*len(os.path.splitext(meshname)[1])]+'.glb').replace('\\', os.sep)
                            print(os.path.exists(meshpath))
                            #print('Mesh path is - ',meshpath, e['HandleId'])
                            if(meshname != 0):
                                        #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                        # Roads all have stupid prx0 names so instancing by name wont work.
                                        imported=False
                                        try:
                                            bpy.ops.io_scene_gltf.cp77(with_mats, filepath=meshpath,scripting=True)
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
                                                assign_custom_properties(new, data,sectorName,i,
                                                nodeDataIndex=inst['nodeDataIndex'], instance_idx=idx,
                                                mesh=meshname, pivot=inst['Pivot'])                                               
                                            
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
                                            print('Mesh not found in masters - ',meshname, ' - ',i, e['HandleId'])

                    case 'worldStaticMeshNode' |'worldRotatingMeshNode'| 'worldPhysicalDestructionNode' | 'worldBakedDestructionNode' | 'worldBuildingProxyMeshNode' |'worldAdvertisingNode'|  'worldAdvertisementNode' | \
                    'worldGenericProxyMeshNode'|'worldDestructibleEntityProxyMeshNode'| 'worldTerrainProxyMeshNode' | 'worldStaticOccluderMeshNode'| 'worldTerrainMeshNode' | 'worldClothMeshNode' |\
                    'worldDecorationMeshNode' | 'worldDynamicMeshNode' | 'worldMeshNode':
                        meshname=None
                        if isinstance(e, dict) and 'mesh' in data.keys() and isinstance(data['mesh'], dict) and'DepotPath' in data['mesh'].keys():
                            meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        elif isinstance(e, dict) and 'meshRef' in data.keys():
                            meshname = data['meshRef']['DepotPath']['$value'].replace('\\', os.sep)
                        if meshname:
                            #print('Mesh name is - ',meshname, e['HandleId'])
                            
                            
                            if(meshname != 0):
                                        #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                        group, groupname = get_group(meshname,meshAppearance,Masters)
                                        if (group):
                                            #print('Group found for ',groupname)
                                            if ntype=='worldRotatingMeshNode':
                                                rot_axis=data['rotationAxis']
                                                axis_no=0
                                                if rot_axis=='Y':
                                                    axis_no=1
                                                elif rot_axis=='Z': #y & z are swapped sometimes, need to work out why
                                                    axis_no=2

                                                rot_time=data['fullRotationTime']
                                                reverse=data['reverseDirection']

                                            instances = [x for x in t if x['NodeIndex'] == i]
                                            for idx,inst in enumerate(instances):
                                                new=bpy.data.collections.new(groupname)
                                                Sector_coll.children.link(new)
                                                assign_custom_properties(new, data,sectorName,i,
                                                nodeDataIndex=inst['nodeDataIndex'], instance_idx=idx,
                                                mesh=meshname, pivot=inst['Pivot'],
                                                meshAppearance=meshAppearance,
                                                appearanceName=meshAppearance)
                                                if ntype=='worldClothMeshNode':
                                                    if 'windImpulseEnabled' in inst.keys():
                                                        new['windImpulseEnabled']= inst['windImpulseEnabled']
                                                if ntype=='worldRotatingMeshNode':
                                                    if 'rotationAxis' in data.keys():
                                                        new['rot_axis']=data['rotationAxis']
                                                    if 'reverseDirection' in data.keys():
                                                        new['reverseDirection']=data['reverseDirection']
                                                    if 'fullRotationTime' in data.keys():
                                                        new['fullRotationTime']=data['fullRotationTime']

                                                #print(new['nodeDataIndex'])
                                                # Should do something with the Advertisements lightData  bits here
                                                if ntype=='worldAdvertisingNode' or ntype=='worldAdvertisementNode':
                                                    if 'lightData' in data.keys():
                                                        new['lightData']=data['lightData']

                                                for old_obj in group.all_objects:
                                                    obj=old_obj.copy()
                                                    new.objects.link(obj)

                                                    obj.location = get_pos(inst)
                                                    obj.rotation_quaternion = get_rot(inst)
                                                    obj.scale = get_scale(inst)
                                                    obj.color = (0.3, 0.3, 0.3, 1)

                                                    if 'Armature' in obj.name:
                                                        obj.hide_set(True)
                                                    if ntype=='worldRotatingMeshNode':
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
                                            print('Mesh not found in masters - ',meshname, ' - ',i, e['HandleId'])

                    case 'worldInstancedDestructibleMeshNode':
                        #print('worldInstancedDestructibleMeshNode',i)
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for instidx,inst in enumerate(instances):
                            if isinstance(e, dict) and 'mesh' in data.keys():
                                meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                                num=data['cookedInstanceTransforms']['numElements']
                                start=data['cookedInstanceTransforms']['startIndex']
                                #print('Mesh name is - ',meshname, e['HandleId'])
                                if(meshname != 0):
                                            #print('Mesh - ',meshname, ' - ',i, e['HandleId'])
                                            groupname = os.path.splitext(os.path.split(meshname)[-1])[0]+'@'+meshAppearance
                                            group=Masters.children.get(groupname)
                                            if (group):
                                                NDI_Coll_name = 'wIDMn'+str(inst['nodeDataIndex'])+'_'+groupname
                                                while len(NDI_Coll_name) > 63:
                                                        NDI_Coll_name = NDI_Coll_name[:-1]
                                                NDI_Coll = bpy.data.collections.new(NDI_Coll_name)
                                                Sector_coll.children.link(NDI_Coll)
                                                assign_custom_properties(NDI_Coll, data,sectorName,i,
                                                nodeDataIndex=inst['nodeDataIndex'], 
                                                mesh=meshname, pivot=inst['Pivot'])
                                                if 'appearanceName' in e['Data'].keys():
                                                    NDI_Coll['appearanceName']=e['Data']['appearanceName']['$value']
                                                #print('Glb found - ',glbfoundname)
                                                #print('Glb found, looking for instances of ',i)
                                                #print('Node - ',i, ' - ',meshname)
                                                for idx in range(start, start+num):
                                                    new=bpy.data.collections.new(groupname)
                                                    NDI_Coll.children.link(new)
                                                    new['nodeType']=ntype
                                                    new['nodeIndex']=i
                                                    new['nodeDataIndex']=inst['nodeDataIndex']
                                                    new['tl_instance_idx']=instidx
                                                    new['sub_instance_idx']=idx
                                                    new['mesh']=meshname
                                                    new['debugName']=e['Data']['debugName']['$value']
                                                    new['sectorName']=sectorName
                                                    new['pivot']=inst['Pivot']
                                                    new['appearanceName']=NDI_Coll['appearanceName']

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
                                                print('Mesh not found in masters - ',meshname, ' - ',i, e['HandleId'])

                    case 'worldStaticLightNode':
                        #print('worldStaticLightNode',i)
                        if with_lights:
                            instances = [x for x in t if x['NodeIndex'] == i]
                            for inst in instances:
                                light_node=e['Data']
                                light_name=e['Data']['debugName']['$value']
                                light_ndata=inst
                                color= light_node['color']
                                intensity=light_node['intensity']
                                flicker=light_node['flicker']
                                area_shape=light_node['areaShape']
                                pos=get_pos(light_ndata)
                                rot=get_rot(light_ndata)

                                A_Light=bpy.data.lights.new(str(i)+'_'+light_name,'AREA')
                                light_obj=bpy.data.objects.new(str(i)+'_'+light_name, A_Light)
                                Sector_coll.objects.link(light_obj)
                                light_obj.location=pos
                                light_obj.rotation_mode='QUATERNION'
                                light_obj.rotation_quaternion=rot
                                original_rot = Quaternion(rot)
                                rotation_90_x_local = Quaternion((math.cos(math.radians(45)), math.sin(math.radians(45)), 0, 0))
                                light_obj.rotation_quaternion = original_rot @ rotation_90_x_local
                                light_obj['flicker']=light_node['flicker']
                                light_obj['nodeType']=ntype
                                A_Light.energy = intensity / 10
                                A_Light.color = get_col(color)
                                A_Light.cycles.use_multiple_importance_sampling = False
                                A_Light.cycles.max_bounces = 6
                                light_obj.visible_transmission = False

                                if area_shape=='ALS_Capsule':
                                    A_Light.shape='RECTANGLE'
                                    A_Light.size= 1
                                    light_obj['capsuleLength']=light_node['capsuleLength']
                                    A_Light.size_y= 1
                                    light_obj['radius']=light_node['radius']
                                elif area_shape=='ALS_Sphere':
                                    A_Light.shape='DISK'
                                    A_Light.size= 1
                                    light_obj['radius']=light_node['radius']

                        pass

                    case 'worldStaticParticleNode'|'worldEffectNode'|'worldPopulationSpawnerNode':
                        #print('worldStaticParticleNode',i)
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for idx,inst in enumerate(instances):
                            o = bpy.data.objects.new( "empty", None )
                            o.name=ntype+'_'+e['Data']['debugName']['$value']
                            o['nodeType']=ntype
                            o['nodeIndex']=i
                            o['instance_idx']=idx
                            o['debugName']=e['Data']['debugName']['$value']
                            o['sectorName']=sectorName
                            if ntype=='worldStaticParticleNode':
                                o['particleSystem']=e['Data']['particleSystem']['DepotPath']['$value']
                            if ntype=='worldEffectNode':
                                o['effect']=e['Data']['effect']['DepotPath']['$value']

                            if ntype=='worldPopulationSpawnerNode':
                                o['appearanceName']=e['Data']['appearanceName']['$value']
                                o['objectRecordId']=e['Data']['objectRecordId']['$value']
                                o['spawnonstart']=e['Data']['spawnOnStart']
                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)
                            o.scale = get_scale(inst)
                            o.display_type = 'WIRE'
                            o.color = (1.0, 0.005, .062, 1)
                            o.show_wire = True
                            o.display.show_shadows = False

                        pass

                    case 'worldStaticSoundEmitterNode':
                        #print(ntype)
                        instances = [x for x in t if x['NodeIndex'] == i]
                        for idx,inst in enumerate(instances):
                            o = bpy.data.objects.new( "empty", None )
                            o.empty_display_type = 'SPHERE'
                            o.name=ntype+'_'+e['Data']['debugName']['$value']
                            o['nodeType']=ntype
                            o['nodeIndex']=i
                            o['instance_idx']=idx
                            o['debugName']=e['Data']['debugName']['$value']
                            o['sectorName']=sectorName
                            o['Settings']=e['Data']['Settings']
                            if e['Data']['Settings']['Data']['EventsOnActive']:
                                o['eventName']=e['Data']['Settings']['Data']['EventsOnActive'][0]['event']['$value']
                            Sector_coll.objects.link(o)
                            o.location = get_pos(inst)
                            o.rotation_mode = "QUATERNION"
                            o.rotation_quaternion = get_rot(inst)

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
                                [x,y,z] =get_pos(act)
                                #x=act['Position']['x']['Bits']/131072*scale_factor
                                #y=act['Position']['y']['Bits']/131072*scale_factor
                                #z=act['Position']['z']['Bits']/131072*scale_factor
                                sector_Hash=e['Data']['sectorHash']
                                arot=get_rot(act)
                                for s,shape in enumerate(act['Shapes']):
                                    if 'Size' in shape.keys():
                                        ssize=(2*shape['Size']['X']*act['Scale']['X'],2*shape['Size']['Y']*act['Scale']['Y'],2*shape['Size']['Z']*act['Scale']['Z'])
                                    else:
                                        ssize=None
                                    spos=get_pos(shape)
                                    srot=get_rot(shape)
                                    arot_q = Quaternion((arot[0],arot[1],arot[2],arot[3]))
                                    srot_q = Quaternion((srot[0],srot[1],srot[2],srot[3]))
                                    rot= arot_q @ srot_q
                                    loc=(spos[0]+x,spos[1]+y,spos[2]+z)
                                    if shape['ShapeType']=='Box' or shape['ShapeType']=='Capsule' or shape['ShapeType']=='Sphere':
                                        #print('Box Collision Node')
                                        #pprint(act['Shapes'])

                                        if shape['ShapeType']=='Box':
                                            bpy.ops.mesh.primitive_cube_add(size=1/scale_factor, scale=(ssize[0],ssize[1],ssize[2]),location=(loc[0],loc[1],loc[2]))
                                        elif shape['ShapeType']=='Capsule':
                                            bpy.ops.mesh.primitive_cylinder_add(radius=5/scale_factor, depth=1/scale_factor, scale=(ssize[0],ssize[1],ssize[2]),location=loc)
                                        elif shape['ShapeType']=='Sphere':
                                            bpy.ops.mesh.primitive_uv_sphere_add(radius=5/scale_factor, scale=(ssize[0],ssize[1],ssize[2]),location=loc)
                                        crash=C.selected_objects[0]
                                        crash.name='NodeDataIndex_'+str(inst['nodeDataIndex'])+'_Actor_'+str(idx)+'_Shape_'+str(s)
                                        par_coll=crash.users_collection[0]
                                        par_coll.objects.unlink(crash)
                                        sector_Collisions_coll.objects.link(crash)
                                        crash['nodeIndex']=i
                                        crash['nodeDataIndex']=inst['nodeDataIndex']
                                        crash['ShapeType']=shape['ShapeType']
                                        crash['ShapeNo']=s
                                        crash['ActorIdx']=idx
                                        crash['sectorName']=sectorName
                                        crash['matrix']=crash.matrix_world
                                        crash.rotation_mode='QUATERNION'
                                        crash.rotation_quaternion=rot
                                        set_collider_props(crash, shape['ShapeType'], shape['Materials'][0]['$value'], 'WORLD')

                                    else:
                                        #print(f"unsupported shape {shape['ShapeType']}")
                                        meshname=sector_Hash+'_'+shape['Hash']
                                        if meshname not in Masters.objects.keys():
                                            o=CP77CollisionTriangleMeshJSONimport_by_hashes(sectorHashStr=sector_Hash,entryHashStr=shape['Hash'],project_raw_dir=path)
                                            if not o:
                                                o = bpy.data.objects.new('NDI_'+str(inst['nodeDataIndex'])+'_Actor_'+str(idx)+'_Shape_'+str(s), None)
                                            Masters.objects.link(o)
                                        if meshname not in Masters.objects.keys():
                                            print(f"Mesh {meshname} not found in Masters, skipping collision import for this shape")
                                            continue
                                        o=Masters.objects[meshname].copy()
                                        o['nodeType']='worldCollisionNode'
                                        o['nodeIndex']=i
                                        o['nodeDataIndex']=inst['nodeDataIndex']
                                        o['ShapeType']=shape['ShapeType']
                                        o['ShapeNo']=s
                                        o['ActorIdx']=idx
                                        o['sectorName']=sectorName
                                        sector_Collisions_coll.objects.link(o)
                                        o.location = (loc[0],loc[1],loc[2])
                                        o.rotation_mode = "QUATERNION"
                                        o.rotation_quaternion = rot
                                        if ssize:
                                            o.scale = (ssize[0],ssize[1],ssize[2])


                    case _:
                        #print('None of the above',i)
                        pass
        print('Nodes complete, updating view layer and saving world matrices')
        # Have to do a view_layer update or the matrices are all blank
        bpy.context.view_layer.update()
        for col in Sector_coll.children:
            if len(col.all_objects)>0:
                col['matrix']= col.all_objects[0].matrix_world



        print('Finished with ',filepath,' (no ', fpn+1, ' of ', no_sectors,')')
    # doing this earlier in the file was breaking the entity postitioning. NO idea how that works, but be warned.
    Masters.hide_viewport=True
    for obj in bpy.data.objects:
        if 'Decal' in obj.name:
            obj['matrix']=obj.matrix_world
    if len(roads)>0:
        for road in roads:
            curve=road['Curve']
            endpoint=curve.data.splines[0].bezier_points[-1]
            nextroad=[r for r in roads if (points_within_tol(r['Endpos'],road['Endpos']) or points_within_tol(r['Startpos'],road['Endpos'])) and r['Name']!=road['Name']]
            if len(nextroad)==1:
                nextroad=nextroad[0]
                nextcurve=nextroad['Curve']
                if points_within_tol(nextroad['Endpos'],road['Endpos']):
                    nextpoint=nextcurve.data.splines[0].bezier_points[-1]
                else:
                    nextpoint=nextcurve.data.splines[0].bezier_points[0]


                if points_within_tol(endpoint.handle_left, nextpoint.handle_left,0.5):
                    lefthandlepos=average_vectors( endpoint.handle_left, nextpoint.handle_left)
                else:
                    lefthandlepos=average_vectors( endpoint.handle_left, nextpoint.handle_right)
                lh = bpy.data.objects.new( "empty", None )
                lh.location = lefthandlepos
                Sector_coll.objects.link(lh)
                if points_within_tol(endpoint.handle_right, nextpoint.handle_right,0.5):
                    righthandlepos=average_vectors( endpoint.handle_right, nextpoint.handle_right)
                else:
                    righthandlepos=average_vectors( endpoint.handle_right, nextpoint.handle_left)
                lh = bpy.data.objects.new( "empty", None )
                lh.location = righthandlepos
                Sector_coll.objects.link(lh)
                # Set the handle types to vector ('FREE', 'VECTOR', 'ALIGNED', 'AUTO')
                nextpoint.handle_left_type='ALIGNED'
                nextpoint.handle_right_type='ALIGNED'
                endpoint.handle_left_type='ALIGNED'
                endpoint.handle_right_type='ALIGNED'
                # Set the handles to the average of the two roads
                endpoint.handle_left = lefthandlepos
                nextpoint.handle_left = lefthandlepos
                endpoint.handle_right = righthandlepos
                nextpoint.handle_right = righthandlepos
                # Set the points to be the same
                nextpoint.co=endpoint.co
    print(f"Imported Sectors from : {wkit_proj_name} in {time.time() - start_time}")
    print('')
    print('-------------------- Finished Importing Cyberpunk 2077 Streaming Sectors --------------------')
    print('')


# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    filepath = 'F:\\CPMod\\judysApt\\judysApt.cpmodproj'

    importSectors( filepath, with_mats=True, want_collisions=False, am_modding=False )