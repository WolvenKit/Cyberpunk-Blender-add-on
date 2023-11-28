import json
import bpy
import os
import bmesh
import mathutils
from bpy.props import StringProperty
 
def cp77_phys_import(filepath, rig=None, chassis_z=None):
    physJsonPath = filepath
        # create the new objects
    for area in bpy.context.screen.areas: 
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            if space.type == 'VIEW_3D':
                space.shading.wireframe_color_type = 'OBJECT'
                
    def create_new_object(name, transform):
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        new_collection.objects.link(obj)  
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # if importing with an entity, apply constraints to the rig so that the colliders are positioned properly
                       

        # create dicts for position/orientation
        position = (transform['position']['X'], transform['position']['Y'], transform['position']['Z'])
        #orientation = (transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i'])
        obj.location = position

        return obj
 
    with open(physJsonPath, 'r') as phys:
        data = json.load(phys)

    #bodies = []
    #collision_shapes=[]
    for index, i in enumerate(data['Data']['RootChunk']['bodies']):
        bname = (i['Data']['name']['$value'])
        collection_name = bname
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection)
        
        for index, i in enumerate(data['Data']['RootChunk']['bodies'][0]['Data']['collisionShapes']):
            collision_shape = i['Data']['$type']
            physmat = i['Data']['material']['$value']
            submeshName = str(index) + '_' + collision_shape
            transform = i['Data']['localToBody']
            print(bname, collision_shape, physmat, submeshName, transform)

            
            if collision_shape == "physicsColliderConvex":
                obj = create_new_object(submeshName, transform)
                obj['collisionType'] = 'VEHICLE'
                obj['collisionShape'] = 'physicsColliderConvex'
                obj['physics_material'] = physmat
                obj.display_type = 'WIRE'
                obj.color = (0.005, 0.79105, 1, 1)
                obj.show_wire = True
                obj.show_in_front = True
                obj.display.show_shadows = False
                obj.rotation_mode = 'QUATERNION'
                if 'vertices' in i['Data']:
                    verts = [(j['X'], j['Y'], j['Z']) for j in i['Data']['vertices']]
                    bm = bmesh.new()
                    for v in verts:
                        bm.verts.new(v)
                    bm.to_mesh(obj.data)
                    bm.free()
                    if rig is not None: 
                        constraint = obj.constraints.new('CHILD_OF')
                        constraint.target = rig
                        constraint.subtarget = 'Base'
                        bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
                        if chassis_z is not None: 
                            obj.delta_location[2] = chassis_z 

            # If the type is "physicsColliderBox", create a box centered at the object's location
            elif collision_shape == "physicsColliderBox":
                half_extents = i['Data']['halfExtents']
                dimensions = (2 * half_extents['X'], 2 * half_extents['Y'], 2 * half_extents['Z'])
                bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
                box = bpy.context.object
                box.scale = dimensions
                box.name = submeshName
                box.display_type = 'WIRE'
                box.color = (0.005, 0.79105, 1, 1)
                box.show_wire = True
                box.show_in_front = True
                box.display.show_shadows = False
                box.rotation_mode = 'QUATERNION'
                box['collisionType'] = 'VEHICLE'
                box['collisionShape'] = 'physicsColliderBox'
                box['physics_material'] = physmat
                box.location = transform['position']['X'], transform['position']['Y'], transform['position']['Z']
                box.rotation_quaternion = transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i']
                if rig is not None: 
                    constraint = box.constraints.new('CHILD_OF')
                    constraint.target = rig
                    constraint.subtarget = 'Base'
                    bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
                    if chassis_z is not None: 
                        box.delta_location[2] = chassis_z 
                new_collection.objects.link(box)
                bpy.context.collection.objects.unlink(box) # Unlink from the current collection

            # handle physicsColliderCapsule       
            elif collision_shape == "physicsColliderCapsule":
                r = i['Data']['radius'] 
                h = i['Data']['height']    

                # create the capsule
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
                capsule.color = (0.005, 0.79105, 1, 1)
                capsule.show_wire = True
                capsule.show_in_front = True
                capsule.display.show_shadows = False
                capsule.rotation_mode = 'QUATERNION'
                capsule['collisionType'] = 'VEHICLE'
                capsule['collisionShape'] = collision_shape
                capsule['physics_material'] = physmat
                capsule.rotation_quaternion[1] = 1
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
                capsule.dimensions.z = float(h)
                capsule.location = transform['position']['X'], transform['position']['Y'], transform['position']['Z']
                capsule.rotation_mode = 'QUATERNION'  # Set the rotation mode to QUATERNION first
                capsule.rotation_quaternion = transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i']
                if rig is not None: 
                    constraint = capsule.constraints.new('CHILD_OF')
                    constraint.target = rig
                    constraint.subtarget = 'Base'
                    bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
                    if chassis_z is not None: 
                        capsule.delta_location[2] = chassis_z 
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                new_collection.objects.link(capsule)