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
    J!ELd1!@#    
    