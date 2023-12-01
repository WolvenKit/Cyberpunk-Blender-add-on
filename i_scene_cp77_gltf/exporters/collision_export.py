import json
import os 
import bpy
from mathutils import Vector, Euler, Quaternion

def cp77_collision_export(filepath):
    selected_collection = bpy.context.collection
    with open(filepath, 'r') as phys:
        data = json.load(phys)
        physJsonPath = filepath

        dir_name, file_name = os.path.split(filepath)
        new_file_name = 'new_' + file_name
        output = os.path.join(dir_name, new_file_name)

        collection = selected_collection

        if collection is not None:
            for index, obj in enumerate(collection.objects):
                colliderType = obj.name.split('_')[1]
                i = data['Data']['RootChunk']['bodies'][0]['Data']['collisionShapes'][index]

                i['Data']['localToBody']['position']['X'] = obj.location.x
                i['Data']['localToBody']['position']['Y'] = obj.location.y
                i['Data']['localToBody']['position']['Z'] = obj.location.z
                i['Data']['localToBody']['orientation']['i'] = obj.rotation_quaternion.z
                i['Data']['localToBody']['orientation']['j'] = obj.rotation_quaternion.x
                i['Data']['localToBody']['orientation']['k'] = obj.rotation_quaternion.y
                i['Data']['localToBody']['orientation']['r'] = obj.rotation_quaternion.w

                if colliderType == "physicsColliderConvex" or colliderType == "physicsColliderConcave":
                    mesh = obj.data
                    if 'vertices' in i['Data']:
                        for j, vert in enumerate(mesh.vertices):
                            i['Data']['vertices'][j]['X'] = vert.co.x
                            i['Data']['vertices'][j]['Y'] = vert.co.y
                            i['Data']['vertices'][j]['Z'] = vert.co.z

                elif colliderType == "physicsColliderBox":
                    # Calculate world-space bounding box vertices
                    world_bounds = [obj.matrix_world @ Vector(coord) for coord in obj.bound_box]

                    # Get center of the box in world space
                    center = sum(world_bounds, Vector()) / 8

                    # Update position in the json based on the center of the cube in world space
                    i['Data']['localToBody']['position']['X'] = center.x
                    i['Data']['localToBody']['position']['Y'] = center.y
                    i['Data']['localToBody']['position']['Z'] = center.z
                    # Update halfExtents
                    i['Data']['halfExtents']['X'] = obj.dimensions.x / 2
                    i['Data']['halfExtents']['Y'] = obj.dimensions.y / 2
                    i['Data']['halfExtents']['Z'] = obj.dimensions.z / 2

                elif colliderType == "physicsColliderCapsule":
                    i['Data']['radius'] = obj.dimensions.x / 2  # Divided by 2 because blender dimensions are diameter
                    i['Data']['height'] = obj.dimensions.z 
                
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Succesfully Exported Collisions")
        with open(output, 'w') as f:
            json.dump(data, f, indent=2)

    print(f'Finished exporting {new_file_name}')
