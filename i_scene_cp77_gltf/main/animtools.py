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


def play_anim(self, context, anim_name):
    obj = bpy.context.active_object

    if not obj or obj.type != 'ARMATURE':
        return {'CANCELLED'}

    if not obj.animation_data:
        return {'CANCELLED'}

    # Retrieve the action by name
    active_action = bpy.data.actions.get(anim_name)

    if active_action:
        # Stop the currently playing animation
        bpy.ops.screen.animation_cancel(restore_frame=False)

        # Set the active action
        obj.animation_data.action = active_action

        # Start playing the animation
        context.scene.frame_current = int(active_action.frame_range[0])
        bpy.ops.screen.animation_play()

    return {'FINISHED'}

def rename_anim(self, context, event):
    if event.ctrl:
    # Rename
        self.new_name = self.name
        return context.window_manager.invoke_props_dialog(self)
    else:
        self.new_name = ""
        return self.execute(context)

        


