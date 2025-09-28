import bpy
import json
import re
from mathutils import Vector, Euler, Quaternion
from ..importers.read_rig import *
from ..main.bartmoss_functions import store_current_context, restore_previous_context, get_safe_mode, safe_mode_switch, is_armature


animBones = ["Hips", "Spine", "Spine1", "Spine2", "Spine3", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "WeaponLeft", "LeftInHandThumb", "LeftHandThumb1", "LeftHandThumb2", "LeftInHandIndex", "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3", "LeftInHandMiddle", "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3", "LeftInHandRing", "LeftHandRing1", "LeftHandRing2", "LeftHandRing3", "LeftInHandPinky", "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3", "RightShoulder", "RightArm", "RightForeArm", "RightHand", "WeaponRight", "RightInHandThumb", "RightHandThumb1", "RightHandThumb2", "RightInHandIndex", "RightHandIndex1", "RightHandIndex2", "RightHandIndex3", "RightInHandMiddle", "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3", "RightInHandRing", "RightHandRing1", "RightHandRing2", "RightHandRing3", "RightInHandPinky", "RightHandPinky1", "RightHandPinky2", "RightHandPinky3", "Neck", "Neck1", "Head", "LeftEye", "RightEye", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftHeel", "LeftToeBase", "RightUpLeg", "RightLeg", "RightFoot", "RightHeel", "RightToeBase"]


def delete_unused_bones(self, context):
    obj = context.active_object
    current_context = bpy.context.mode


    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences


    # get all vertex groups from all children
    all_vertex_groups = {vg.name for mesh in (child for child in obj.children if child.type == 'MESH') for vg in mesh.vertex_groups}

    # Delete bones that aren't in the list
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')

    b = obj.data.edit_bones[0]

    # for rigs, these are nested - otherwise, just iterate
    allBones = b.children_recursive
    if len(allBones) == 0:
        allBones = obj.data.edit_bones

    for bone in allBones:
        m = re.search(r'\.\d+$', bone.name) # drop numbers from bone names
        if m is not None:
            bone.name = bone.name.replace(m[0], "")
        if bone.name in all_vertex_groups:
           continue

        if not cp77_addon_prefs.non_verbose:
            print(f"Deleting bone {bone.name}")
        bpy.context.object.data.edit_bones.remove(bone)


    if current_context != bpy.context.mode:
        bpy.ops.object.mode_set(mode=current_context)

    return {'FINISHED'}

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

def load_apose(self, arm_obj):
    arm_data = arm_obj.data
    filepath = arm_data.get('source_rig_file', None)
    bone_names = arm_data.get('boneNames', [])
    bone_parents = arm_data.get('boneParentIndexes', [])
    store_current_context()
    safe_mode_switch('EDIT')
    edit_bones = arm_data.edit_bones
    if not os.path.exists(filepath):
        self.report({'ERROR'}, f"Invalid path to json source {filepath} not found")
        return
    rig_data = read_rig(filepath)
    apose_ms = rig_data.apose_ms
    apose_ls = rig_data.apose_ls
    
    if apose_ms is None and apose_ls is None:
        self.report({'ERROR'}, f"No A-Pose found in {rig_data.rig_name} json source")
        return
    
    bone_index_map = {}
    for i, name in enumerate(rig_data.bone_names):
        bone = edit_bones.get(name)
        bone_index_map[i] = bone
    pose_matrices = build_apose_matrices(apose_ms, apose_ls, bone_names, bone_parents)
    if not pose_matrices:
        self.report({'ERROR'}, f"Error building A-Pose matrices for {rig_data.rig_name}")
        print
        return
    for i, name in enumerate(rig_data.bone_names):
        mat = pose_matrices[i]
        apply_bone_from_matrix(i, mat, bone_index_map, rig_data.parent_indices, pose_matrices)
    restore_previous_context()
    self.report({'INFO'}, "A-Pose loaded")

def load_tpose(self, arm_obj):
    arm_data = arm_obj.data
    filepath = arm_data.get('source_rig_file', None)
    store_current_context()
    safe_mode_switch('EDIT')
    edit_bones = arm_data.edit_bones
    # Make sure the path exists
    if not os.path.exists(filepath):
        self.report({'ERROR'}, f"Invalid path to json source {filepath} not found")
        return
    #Load Fresh Data
    rig_data = read_rig(filepath)
    bone_index_map = {}
    for i, name in enumerate(rig_data.bone_names):
        bone = edit_bones.get(name)
        bone_index_map[i] = bone
        print(f'index{i} = {bone.name} = {bone}')
    
    global_transforms = {}
    for i in range(len(rig_data.bone_names)):
        mat_red = compute_global_transform(i, rig_data.bone_transforms, rig_data.parent_indices, global_transforms)
        global_transforms[i] = mat_red
    for i in range(len(rig_data.bone_transforms)):
        transform_data = rig_data.bone_transforms[i]
        if is_identity_transform(transform_data):
            continue  # leave stub alone
        apply_bone_from_matrix(i, global_transforms[i], bone_index_map, rig_data.parent_indices, global_transforms)
        arm_data['T-Pose'] = True
    restore_previous_context()
    
    self.report({'INFO'}, "A-Pose loaded")
    return

## insert a keyframe at either the corrunt frame or for the entire specified frame length
def cp77_keyframe(self, context, frameall=False):

    ##Check the current context of the scene
    current_context = bpy.context.mode
    armature = context.active_object

    ## switch to pose mode if it's not already
    if current_context != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    if not frameall:
        bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
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
                bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
            bpy.ops.object.mode_set(current_context)

        if current_context != bpy.context.mode:
            bpy.context.mode = current_context

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
    selected_object = context.active_object

    if selected_object is not None and selected_object.type == 'ARMATURE':
        armature = selected_object.data
    else:
        print("Select an armature object.")
        armature = None

    for bone in armature.bones:
        if bone.name not in animBones:
            if bone.hide is not True:
                bone.hide = True

    for bone in armature.edit_bones:
        if bone.name not in animBones:
            if bone.hide is not True:
                bone.hide = True

    selected_object['deformBonesHidden'] = True


def unhide_extra_bones(self, context):
    selected_object = context.active_object

    if selected_object is not None and selected_object.type == 'ARMATURE':
        armature = selected_object.data
    else:
        print("Select an armature object.")
        armature = None

    for bone in armature.bones:
        if bone.hide == True:
            bone.hide = False

    for bone in armature.edit_bones:
        if bone.hide == True:
            bone.hide = False

    bpy.ops.wm.properties_remove(data_path="object", property_name="deformBonesHidden")