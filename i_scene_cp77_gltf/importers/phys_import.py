import json
import bpy
import os
import bmesh
import mathutils
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
 
def cp77_phys_import(filepath):
    
    physJsonPath = filepath
    
    phys = open(physJsonPath)
    data = json.load(phys)

    # create a new collector named after the file
    collection_name = os.path.splitext(os.path.basename(physJsonPath))[0]
    new_collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(new_collection)

    # create the new objects
    def create_new_object(name, transform):
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        new_collection.objects.link(obj)  
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # create dicts for position/orientation
        position = (transform['position']['X'], transform['position']['Y'], transform['position']['Z'])
        orientation = (transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i'])
        obj.location = position
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = orientation

        return obj

    # Iterate through the collisionShapes array, creatting submeshes in the collector named after the collider types
    for index, i in enumerate(data['Data']['RootChunk']['bodies'][0]['Data']['collisionShapes']):

        # create dicts for later
        colliderType = i['Data']['$type']
        submeshName = str(index) + '_' + colliderType
        transform = i['Data']['localToBody']

        # If the type is "physicsColliderConvex", or "physicsColliderConcave" create meshes with vertices everywhere specified in the vertices array
        if colliderType == "physicsColliderConvex" or colliderType == "physicsColliderConcave":
            obj = create_new_object(submeshName, transform)
            obj['collisionType'] = 'VEHICLE'
            obj['collisionShape'] = 'physicsColliderConvex'
            if 'vertices' in i['Data']:
                verts = [(j['X'], j['Y'], j['Z']) for j in i['Data']['vertices']]
                bm = bmesh.new()
                for v in verts:
                    bm.verts.new(v)
                bm.to_mesh(obj.data)
                bm.free()

        # If the type is "physicsColliderBox", create a box centered at the object's location
        elif colliderType == "physicsColliderBox":
            half_extents = i['Data']['halfExtents']
            dimensions = (2 * half_extents['X'], 2 * half_extents['Y'], 2 * half_extents['Z'])
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
            box = bpy.context.object
            box.scale = dimensions
            box.name = submeshName
            box['collisionType'] = 'VEHICLE'
            box['collisionShape'] = 'physicsColliderBox'
            box.display_type = 'WIRE'
            box.location = transform['position']['X'], transform['position']['Y'], transform['position']['Z']
            box.rotation_mode = 'QUATERNION'  # Set the rotation mode to QUATERNION first
            box.rotation_quaternion = transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i']

            new_collection.objects.link(box)
            bpy.context.collection.objects.unlink(box) # Unlink from the current collection

        # handle physicsColliderCapsule       
        elif colliderType == "physicsColliderCapsule":
            r = i['Data']['radius']
            h = i['Data']['height']
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=9, radius=r)
            delta_Z = float(h)
            bm.verts.ensure_lookup_table()
            for vert in bm.verts:
                if vert.co[2] < 0:
                    vert.co[2] -= delta_Z
                elif vert.co[2] > 0:
                    vert.co[2] += delta_Z

            name = 'physicsColliderCapsule'
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()

            capsule = bpy.data.objects.new(name, mesh)
            capsule.display_type = 'WIRE'
            capsule.location = center
            capsule.rotation_mode = 'QUATERNION'
            capsule['collisionType'] = 'VEHICLE'
            capsule['collisionShape'] = 'physicsColliderCapsule'
            if is_edit_mode:
                bpy.ops.object.mode_set(mode='OBJECT')
            capsule.dimensions.z = float(h)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            colliderCollection.objects.link(capsule)
            # Re-enter Edit mode
            if is_edit_mode:
                bpy.ops.object.mode_set(mode='EDIT')