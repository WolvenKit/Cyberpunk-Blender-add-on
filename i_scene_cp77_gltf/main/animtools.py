import bpy
from mathutils import Vector, Euler, Quaternion

## function to reset the armature to its neutral position

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


## insert a keyframe at either the corrunt frame or for the entire specified frame length
def cp77_keyframe(self, context, frameall=False):

    ##Check the current context of the scene
    current_context = bpy.context.mode
    armature = context.active_object

    ## switch to pose mode if it's not already
    if current_context != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    if not frameall:
        bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacter")
        return {'FINISHED'}
    
    else:
        action = armature.animation_data.action
        if action:
            # Make sure the armature is in pose mode
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='POSE')

            # Insert a keyframe for each frame in the action
            for frame in range(int(action.frame_range[0]), int(action.frame_range[1]) + 1):
                bpy.context.scene.frame_set(frame)
                bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacter")
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
        bpy.ops.screen.animation_play()

    return {'FINISHED'}

def delete_anim(self, context):
    action = bpy.data.actions.get(self.name, None)
    if not action:
        return {'CANCELLED'}
    else:
        bpy.data.actions.remove(action)

def hide_extra_bones(self, context):
    # List of bone names that should not be hidden
    ## the regular animrig bones
    animBones = ["Hips", "Spine", "Spine1", "Spine2", "Spine3", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "WeaponLeft", "LeftInHandThumb", "LeftHandThumb1", "LeftHandThumb2", "LeftInHandIndex", "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3", "LeftInHandMiddle", "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3", "LeftInHandRing", "LeftHandRing1", "LeftHandRing2", "LeftHandRing3", "LeftInHandPinky", "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3", "RightShoulder", "RightArm", "RightForeArm", "RightHand", "WeaponRight", "RightInHandThumb", "RightHandThumb1", "RightHandThumb2", "RightInHandIndex", "RightHandIndex1", "RightHandIndex2", "RightHandIndex3", "RightInHandMiddle", "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3", "RightInHandRing", "RightHandRing1", "RightHandRing2", "RightHandRing3", "RightInHandPinky", "RightHandPinky1", "RightHandPinky2", "RightHandPinky3", "Neck", "Neck1", "Head", "LeftEye", "RightEye", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftHeel", "LeftToeBase", "RightUpLeg", "RightLeg", "RightFoot", "RightHeel", "RightToeBase"]

    if selected_object is not None and selected_object.type == 'ARMATURE':
        armature = selected_object.data
    else:
        print("Select an armature object.")
        armature = None

    if armature:
    #Iterate through all bones in the armature
        for bone in armature.bones:
            if bone.name not in animBones:
                bone.hide = True
    # Iterate through all edit bones in the armature
    for bone in armature.edit_bones:
        if bone.name not in animBones:
            bone.hide = True