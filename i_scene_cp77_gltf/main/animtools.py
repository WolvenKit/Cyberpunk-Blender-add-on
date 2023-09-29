import bpy
from mathutils import Vector, Euler, Quaternion

### function to reset the armature to its neutral position

def reset_armature(self, context):
    obj = context.active_object
    current_context = bpy.context.mode

    # Store the original object mode
    original_object_mode = obj.mode

    try:
        if current_context != 'POSE':
            # Switch to pose mode
            bpy.ops.object.mode_set(mode='POSE')
        
        # Deselect all bones first
        for pose_bone in obj.pose.bones:
            pose_bone.bone.select = False
        
        # Select all bones in pose mode
        for pose_bone in obj.pose.bones:
            pose_bone.bone.select = True
        
        # Clear transforms for all selected bones
        bpy.ops.pose.transforms_clear()
    finally:
        # Restore the original object mode
        bpy.ops.object.mode_set(mode=original_object_mode)

    return {'FINISHED'}

    return {'FINISHED'}

def cp77_keyframe(self, context, frameall):

    ##Check the current context of the scene
    current_context = bpy.context.mode
    armature = context.active_object

    ## switch to pose mode if it's not already
    if current_context != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    if not frameall:
        # Select all bones in the armature
        for bone in armature.pose_bones:
            bone.bone_select = True
            
        # Insert a keyframe for the selected bones
        bpy.ops.anim.keyframe_insert(type='BUILTIN_KSI_LocRot', confirm_success=True)
        return {'FINISHED'}
    
    else:
        action = armature.animation_data.action
        if action:
            # Make sure the armature is in pose mode
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='POSE')

            # Select all bones in the armature
            for bone in armature.pose.bones:
                bone.bone_select = True

            # Insert a keyframe for each frame in the action
            for frame in range(int(action.frame_range[0]), int(action.frame_range[1]) + 1):
                bpy.context.scene.frame_set(frame)
                bpy.ops.anim.keyframe_insert(type='BUILTIN_KSI_LocRot', confirm_success=True)
            bpy.ops.object.mode_set(current_context)

        return {'FINISHED'}


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

def delete_anim(self, context):
    if obj.type == 'ARMATURE':
        obj = context.active_object 
    else:
        obj = None
    action = bpy.data.actions.get(self.name, None)

    for obj in obj:
        if not action:
            return {'CANCELLED'}
        else:
            bpy.data.actions.remove(action)

        return {'FINISHED'}
