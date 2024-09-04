import json
import glob
import os
import bpy
import math
from mathutils import Vector, Matrix , Quaternion
import bmesh
import time

def CP77CollisionTriangleMeshJSONimport_by_hashes( sectorHashStr='', entryHashStr='', project_raw_dir=''):
    jsonpath=os.path.join(project_raw_dir,'collision_meshes',sectorHashStr+'_'+entryHashStr+'.json')
    if os.path.exists(jsonpath):
        return CP77CollisionTriangleMeshJSONimport( jsonpath )
    else:
        print('ERROR: file not found: ',jsonpath)
        return None


def CP77CollisionTriangleMeshJSONimport( jsonpath ):
    start_time = time.time()
    D=bpy.data
    C=bpy.context
    coll_scene = C.scene.collection  
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    with open(jsonpath,'r') as f: 
        j=json.load(f) 
    mesh_name = os.path.basename(jsonpath).split('.')[0]

    if not cp77_addon_prefs.non_verbose:
        print('-------------------- Beginning Cyberpunk Collision Mesh Import --------------------')
        print('')
        print(f"Importing Collision Mesh from: {mesh_name}")
        print('')
    mesh_data = D.meshes.new(mesh_name)
    mesh_obj = D.objects.new(mesh_data.name, mesh_data)    
    mesh_obj.display_type = 'WIRE'
    mesh_obj.color = (0.005, 0.79105, 1, 1)
    mesh_obj.show_wire = True
    mesh_obj.show_in_front = True
    mesh_obj.display.show_shadows = False
    mesh_obj['fromCache'] = True
    mesh_obj['collisionType'] = 'WORLD'
    mesh_obj['physics_material'] = 'plastic.physmat' # NOT in the json from the geom cache, need to pull it from the sector
    mesh_obj.rotation_mode = 'QUATERNION' 
    verts=[]
    if 'Vertices' in j.keys():
        Verts=j['Vertices']
        for v in Verts:
            verts.append((v['X'],v['Y'],v['Z']))
        edges=[]    
        Faces=  j['Triangles']

        mesh_data.from_pydata(verts, edges,Faces)
        mesh_obj['collisionShape'] = 'TriangleMesh'
        
    elif 'HullData' in j.keys():        
        Verts=j['HullData']['HullVertices']
        for v in Verts:
            verts.append((v['X'],v['Y'],v['Z']))       
        bm = bmesh.new()     
        for v in verts:
            bm.verts.new(v)
        ch = bmesh.ops.convex_hull(bm, input=bm.verts)
        bmesh.ops.delete(
        bm,
        geom=ch["geom_unused"] + ch["geom_interior"],
        context='VERTS',
        )        
        bm.to_mesh(mesh_data)
        bm.free()
        mesh_obj['collisionShape'] = 'ConvexHull'
        if not cp77_addon_prefs.non_verbose:
            print(f"Collision Mesh Import Time: {(time.time() - start_time)} Seconds")
            print('')
            print('-------------------- Finished importing Cyberpunk 2077 Collision Mesh --------------------')
    return mesh_obj   


scale_factor=1.0

def get_pos(inst):
    pos=[0,0,0]
    if 'Position' in inst.keys():
        if '$type' in inst['Position'].keys() and inst['Position']['$type']=='WorldPosition':
            pos[0]=inst['Position']['x']['Bits']/131072*scale_factor  
            pos[1]=inst['Position']['y']['Bits']/131072*scale_factor
            pos[2]=inst['Position']['z']['Bits']/131072*scale_factor
        else:
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
    elif 'Rotation' in inst.keys() and 'r' in inst['Rotation'].keys():
            rot[0] = inst['Rotation']['r'] 
            rot[1] = inst['Rotation']['i'] 
            rot[2] = inst['Rotation']['j'] 
            rot[3] = inst['Rotation']['k'] 
    elif 'Rotation' in inst.keys() and 'X' in inst['Rotation'].keys():
            rot[0] = inst['Rotation']['W'] 
            rot[1] = inst['Rotation']['X'] 
            rot[2] = inst['Rotation']['Y'] 
            rot[3] = inst['Rotation']['Z'] 
    elif 'rotation' in inst.keys():
            rot[0] = inst['rotation']['r'] 
            rot[1] = inst['rotation']['i'] 
            rot[2] = inst['rotation']['j'] 
            rot[3] = inst['rotation']['k'] 
    return rot

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

# Create a new text data block
mesh_text_data = bpy.data.texts.new("MeshObjects")
col_text_data = bpy.data.texts.new("CollisionMeshes")
match_text_data = bpy.data.texts.new("Matches")

VERBOSE=True
start_time = time.time()

filepath='C:\\CPMod\\notell\\'

path = os.path.join( os.path.dirname(filepath),'source','raw')
print('path is ',path)
project=os.path.dirname(filepath)

# Set the content of the text file
mesh_text_data.from_string("Meshes and Locations for nodes in "+project+'\n')
col_text_data.from_string("Collision meshes and Locations for nodes in "+project+'\n')
col_text_data.from_string("Matches between meshes and collision meshes by location for nodes in "+project+'\n')

jsonpath = glob.glob(os.path.join(path, "**", "*.streamingsector.json"), recursive = True)
ColInfo=[]
MeshInfo=[]
Matches={}
for filepath in jsonpath:
    if VERBOSE:
        print(os.path.join(path,os.path.basename(project)+'.streamingsector.json'))
        print(filepath)
    with open(filepath,'r') as f: 
            j=json.load(f) 
    sectorName=os.path.basename(filepath)[:-5]
    t=j['Data']['RootChunk']['nodeData']['Data']
    nodes = j["Data"]["RootChunk"]["nodes"]
    for i,e in enumerate(nodes):
        try:
            print(i)
            data = e['Data']
            type = data['$type']
            meshname=None
            if 'mesh' in data:
                meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
            elif 'meshRef' in data:
                meshname = data['meshRef']['DepotPath']['$value'].replace('\\', os.sep)
            if meshname:
                instances = [x for x in t if x['NodeIndex'] == i]
                for inst in instances:
                    pos=get_pos(inst)
                    rot=get_rot(inst)
                    MeshInfo.append([meshname,pos,rot])
                    mesh_text_data.write(meshname+','+str(pos)+','+str(rot)+'\n')
            if type=='worldCollisionNode':
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
                        if shape['ShapeType']=='ConvexMesh' or shape['ShapeType']=='TriangleMesh' :
                            spos=get_pos(shape)
                            srot=get_rot(shape)
                            arot_q = Quaternion((arot[0],arot[1],arot[2],arot[3]))
                            srot_q = Quaternion((srot[0],srot[1],srot[2],srot[3]))
                            rot= arot_q @ srot_q
                            loc=(spos[0]+x,spos[1]+y,spos[2]+z)
                            meshname=sector_Hash+'_'+shape['Hash']
                            col_text_data.write(meshname+','+str(loc)+','+str(rot)+'\n')
                            ColInfo.append([meshname,loc,rot])
        except:
            print('bob')

for col in ColInfo:
    colname=col[0]
    colloc=col[1]
    match=None
    matches=[x for x in MeshInfo if points_within_tol(colloc,x[1],tolerance=0.1)]
    for match in matches:
        combo=colname+'_'+match[0]
        if combo in Matches :
            Matches[combo]['count']=Matches[combo]['count']+1
        else:
            Matches[combo]={'meshname':match[0],'colname':colname, 'count':1,'loc':colloc}
x=-5 
C=bpy.context
coll_scene=C.scene.collection
props = C.scene.cp77_panel_props
props.with_materials=False
currentcol=None
currentcolmesh=None
imported=False
mdim=Vector((0,0,0))
coldim=Vector((0,0,0))
y=0
for key, match in Matches.items():
    colname=match['colname']
    if colname==currentcol:
        y+=5
    else:
        y=0
        x+=5
        currentcol=colname
    match_text_data.write(colname+','+match['meshname']+','+str(match['count'])+'\n')
    meshpath=os.path.join(path, match['meshname'][:-1*len(os.path.splitext(match['meshname'])[1])]+'.glb').replace('\\', os.sep)
    print(meshpath)
    groupname = os.path.splitext(os.path.split(meshpath)[-1])[0]
    while len(groupname) > 63:
        groupname = groupname[:-1]
    if groupname not in coll_scene and os.path.exists(meshpath):
        try:
            bpy.ops.io_scene_gltf.cp77( filepath=meshpath, appearances='default')
            objs = C.selected_objects
            for o in objs: 
                if sum(o.dimensions)>sum(mdim):
                    mdim=o.dimensions
                o.location = (x,y,0)
                imported=True
        except:
            print('failed on ',os.path.basename(meshpath))
    elif groupname in coll_scene:
        #instance it and position it           
        imported=True 
        group= coll_scene.children.get( groupname )
        new=bpy.data.collections.new(groupname)
        coll_scene.children.link(new)
        for old_obj in group.all_objects:                            
            o=old_obj.copy()  
            new.objects.link(o)      
            o.location =    (x,y,0)        
            if sum(o.dimensions)>sum(mdim):
                    mdim=o.dimensions    


    elif not os.path.exists(meshpath):
        print('Mesh ', meshpath, ' does not exist')

    if imported:
        sectorHashStr=colname.split('_')[0]
        entryHashStr=colname.split('_')[1]
        if y==0:
            currentcolmesh=CP77CollisionTriangleMeshJSONimport_by_hashes(sectorHashStr=sectorHashStr,entryHashStr=entryHashStr,project_raw_dir=path)
            o=currentcolmesh
            coldim=o.dimensions
        else:
            old_obj=coll_scene.objects[colname]
            o=old_obj.copy()                  
        o.location=(x,y,0)
        coll_scene.objects.link(o)
        if sum(mdim-coldim)<0.25:
            o.color = (0.0, 0.3, 0.0, 1)
        else:                
            o.color = (0.5, 0.0, 0.0, 1)

print(f"Collision analysis Time: {(time.time() - start_time)} Seconds")
                