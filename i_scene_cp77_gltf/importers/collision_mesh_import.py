import bpy
import json
import os
import bmesh

def CP77CollisionTriangleMeshJSONimport_by_hashes( sectorHashStr='', entryHashStr='', project_raw_dir=''):
    jsonpath=os.path.join(project_raw_dir,'collision_meshes',sectorHashStr+'_'+entryHashStr+'.json')
    if os.path.exists(jsonpath):
        return CP77CollisionTriangleMeshJSONimport( jsonpath )
    else:
        print('ERROR: file not found: ',jsonpath)
        return None


def CP77CollisionTriangleMeshJSONimport( jsonpath ):
    D=bpy.data
    C=bpy.context
    coll_scene = C.scene.collection  

    with open(jsonpath,'r') as f: 
        j=json.load(f) 
    mesh_name = os.path.basename(jsonpath).split('.')[0]
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
    coll_scene.objects.link(mesh_obj) 
    return mesh_obj   

# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":
    import glob
    test='filenames'
    if test=='HASHES':
        project_raw_path = 'C:\\cpmod\\hotel\\source\\raw'
        sectorHashStrVal ='4490140329313192080' # from exterior_-15_-6_0_1
        entryHashStrVals = ['16942165231745220599', '15592228418071567203','4736015122801775210','15495621493829931487'] # from a colllision node in that sector
        for hash in entryHashStrVals:
            CP77CollisionTriangleMeshJSONimport_by_hashes(sectorHashStr=sectorHashStrVal,entryHashStr=hash,project_raw_dir=project_raw_path)
    else:
        project_raw_path = 'C:\\cpmod\\notell\\source\\raw\\collision_meshes'
        jsonpaths = glob.glob(os.path.join(project_raw_path, "**", "*.json"), recursive = True)
        for jsonpath in jsonpaths:
            print(jsonpath)
            mesh_obj = CP77CollisionTriangleMeshJSONimport(jsonpath)
