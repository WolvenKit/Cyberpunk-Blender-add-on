import bpy
import json
import os

def CP77CollisionTriangleMeshJSONimport( sectorHashStr='', entryHashStr='', project_raw_dir=''):
    D=bpy.data
    C=bpy.context
    coll_scene = C.scene.collection

    jsonpath=os.path.join(project_raw_dir,sectorHashStr+'_'+entryHashStr+'.pjson')

    with open(jsonpath,'r') as f: 
        j=json.load(f) 

    Verts=j['Vertices']
    verts=[]
    for v in Verts:
        verts.append((v['X'],v['Y'],v['Z']))
    edges=[]    

    mesh_name = "Test"
    mesh_data = D.meshes.new(mesh_name)
    Faces=  j['Triangles']

    mesh_data.from_pydata(verts, edges,Faces)
    mesh_obj = D.objects.new(mesh_data.name, mesh_data)
    mesh_obj.display_type = 'WIRE'
    mesh_obj.color = (0.005, 0.79105, 1, 1)
    mesh_obj.show_wire = True
    mesh_obj.show_in_front = True
    mesh_obj.display.show_shadows = False
    mesh_obj['fromCache'] = True
    mesh_obj['collisionType'] = 'WORLD'
    mesh_obj['collisionShape'] = 'TriangleMesh'
    mesh_obj['physics_material'] = 'plastic.physmat' # NOT in the json from the geom cache, need to pull it from the sector
    mesh_obj.rotation_mode = 'QUATERNION' 
    coll_scene.objects.link(mesh_obj)    

# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    project_raw_path = 'D:\\cpmod\\hanako\\source\\raw'
    sectorHashStrVal ='4468232872543907146' # from exterior_-15_-6_0_1
    entryHashStrVal = '10291560655135112123' # from a colllision node in that sector
    CP77CollisionTriangleMeshJSONimport(sectorHashStr=sectorHashStrVal,entryHashStr=entryHashStrVal,project_raw_dir=project_raw_path)

