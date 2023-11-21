import bpy
from mathutils import Vector, Quaternion, Euler, Matrix
from math import radians

def rotate_quat_180(self,context):
    if context.active_object and context.active_object.rotation_quaternion:
        active_obj =  context.active_object

        rotation_quat = Quaternion((0, 0, 1), radians(180))
        active_obj.rotation_quaternion = rotation_quat @ active_obj.rotation_quaternion
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        # Update the object to reflect the changes
        active_obj.update_tag()
        active_obj.update_from_editmode()

        # Update the scene to see the changes
        bpy.context.view_layer.update()

    else:
        return{'FINISHED'}
 
    
def calculate_mesh_volume(self, context):
    # Calculate the volume of the mesh using the bounding box approach
    selected_object = context.object
    mesh = selected_object.data
    min_vertex = Vector((float('inf'), float('inf'), float('inf')))
    max_vertex = Vector((float('-inf'), float('-inf'), float('-inf')))
    if selected_object.type == 'MESH':
        matrix = selected_object.matrix_world
        for vertex in mesh.vertices:
            vertex_world = matrix @ vertex.co
            min_vertex = Vector(min(min_vertex[i], vertex_world[i]) for i in range(3))
            max_vertex = Vector(max(max_vertex[i], vertex_world[i]) for i in range(3))
        volume = (max_vertex.x - min_vertex.x) * (max_vertex.y - min_vertex.y) * (max_vertex.z - min_vertex.z)

        return volume