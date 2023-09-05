import bpy
from mathutils import Vector, Euler, Quaternion

### function to reset the armature to its neutral position

def reset_armature(self, context):

    if obj.type != 'ARMATURE':
        
        for pose_bone in obj.pose.bones:    
            pose_bone.location = Vector()
            pose_bone.rotation_quaternion = Quaternion()
            pose_bone.rotation_euler = Euler()
            pose_bone.rotation_axis_angle = [0.0, 0.0, 1.0, 0.0]
            pose_bone.scale = Vector((1.0, 1.0, 1.0))
    else:
        return
def play_anim(self, context):
    if not self.name:
        obj.animation_data.action = None
        return {'FINISHED'}

    action = bpy.data.actions.get(self.name, None)

    if not action:
        return {'CANCELLED'}
    
    else:
        action.use_fake_user = True

        context.scene.frame_current = int(action.curve_frame_range[0])
        bpy.ops.screen.animation_cancel(restore_frame=False)
        bpy.ops.screen.animation_play()

def rename_anim(self, context, event):
    if event.ctrl:
    # Rename
        self.new_name = self.name
        return context.window_manager.invoke_props_dialog(self)
    else:
        self.new_name = ""
        return self.execute(context)

        


