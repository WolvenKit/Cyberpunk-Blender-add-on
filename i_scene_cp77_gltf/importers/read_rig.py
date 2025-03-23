# Read rig from json 
# This script reads a rig from a JSON file and creates an armature in Blender.
# Simarilius 22-3-2025


import bpy
import json
from mathutils import Quaternion, Vector

def create_custom_bone_shape():
    if "CustomBoneShape" in bpy.data.objects:
        return bpy.data.objects["CustomBoneShape"]
    # Create a new mesh object for the custom bone shape
    mesh = bpy.data.meshes.new("CustomBoneShape")
    obj = bpy.data.objects.new("CustomBoneShape", mesh)
    bpy.context.collection.objects.link(obj)

    mesh.from_pydata(
        [(-0.014190172776579857, -0.014190172776579857, 0.010027172975242138), (0.0, 0.0, 0.10000000149011612), (-0.014190172776579857, 0.014190172776579857, 0.010027172975242138), (0.014190172776579857, -0.014190172776579857, 0.010027172975242138), (0.014190172776579857, 0.014190172776579857, 0.010027172975242138), (3.3832008305978434e-09, -3.3832008305978434e-09, -0.0010654638754203916)], 
        [], 
        [(0, 1, 2), (2, 1, 4), (4, 1, 3), (3, 1, 0), (2, 4, 5), (3, 0, 5), (5, 0, 2), (5, 4, 3)])
    return obj

# Helper function to compute global transform
def compute_global_transform(index, transforms, parents, global_transforms):
    if index in global_transforms:
        return global_transforms[index]

    local_translation = Vector((
        transforms[index]["Translation"]["X"],
        transforms[index]["Translation"]["Y"],
        transforms[index]["Translation"]["Z"]
    ))
    local_rotation = Quaternion((
        transforms[index]["Rotation"]["r"],
        transforms[index]["Rotation"]["i"],
        transforms[index]["Rotation"]["j"],
        transforms[index]["Rotation"]["k"]
    ))

    if parents[index] == -1:  # Root bone
        global_transforms[index] = (local_translation, local_rotation)
    else:
        parent_translation, parent_rotation = compute_global_transform(parents[index], transforms, parents, global_transforms)
        global_translation = parent_translation + parent_rotation @ local_translation
        global_rotation = parent_rotation @ local_rotation
        global_transforms[index] = (global_translation, global_rotation)

    return global_transforms[index]

def create_rig_from_json(json_filepath):
    # Load the JSON data
    with open(json_filepath, 'r') as file:
        rig_data = json.load(file)

    # Extract relevant data
    bone_names = rig_data["Data"]["RootChunk"]["boneNames"]
    bone_parents = rig_data["Data"]["RootChunk"]["boneParentIndexes"]
    bone_transforms = rig_data["Data"]["RootChunk"]["boneTransforms"]

    # Create a new armature and object
    armature = bpy.data.armatures.new("Rig")
    armature["source"] = json_filepath
    armature_object = bpy.data.objects.new("Rig", armature)
    bpy.context.collection.objects.link(armature_object)

    # Enable bone axis display
    armature_object.data.show_axes = True

    # Enter edit mode to add bones
    bpy.context.view_layer.objects.active = armature_object
    bpy.ops.object.mode_set(mode='EDIT')    

    # Compute global transforms for all bones
    global_transforms = {}
    for i in range(len(bone_names)):
        compute_global_transform(i, bone_transforms, bone_parents, global_transforms)

    # Create bones
    bones = {}
    for i, bone_name in enumerate(bone_names):
        bone_name = bone_name["$value"]
        parent_index = bone_parents[i]

        # Get global transform
        global_translation, global_rotation = global_transforms[i]
        
        # Calculate the tail position based on the rotation and a fixed length
        tail_offset = global_rotation @ Vector((0, 0.1, 0))  # Rotate a vector of length 0.1
        global_tail = global_translation + tail_offset

         # Calculate the bone length based on the distance to the first child
        child_head_positions = [
        global_transforms[j][0]  # Get the global translation of the child
        for j, child_parent_index in enumerate(bone_parents)
        if child_parent_index == i  # Check if this bone is a parent of the child
        ]

        if child_head_positions:
            # Calculate the length as the distance to the first child's head
            bone_length = (child_head_positions[0] - global_translation).length
        else:
            # If no children, use the default length (e.g., 0.1)
            bone_length = 0.1

        # Create a new bone
        bone = armature.edit_bones.new(bone_name)
        bone.head = global_translation
        bone.tail = global_tail
        bone.length = bone_length

        # Set parent if applicable
        if parent_index != -1:
            parent_bone_name = bone_names[parent_index]["$value"]
            bone.parent = bones[parent_bone_name]

        # Store the bone for reference
        bones[bone_name] = bone

    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')

    # Create or retrieve the custom bone shape
    custom_shape = create_custom_bone_shape()

    bpy.ops.object.mode_set(mode='POSE')
    # Assign the custom shape to each bone
    for bone_name, bone in bones.items():
        pose_bone = armature_object.pose.bones[bone_name]
        pose_bone.custom_shape = custom_shape
        scale=pose_bone.length/0.1
        pose_bone.custom_shape_scale_xyz[0] = scale
        pose_bone.custom_shape_scale_xyz[1] = scale
        if bone_name != "Root":
            pose_bone.custom_shape_scale_xyz[2] = -scale
        else:
            pose_bone.custom_shape_scale_xyz[2] = scale
        pose_bone.use_custom_shape_bone_size = False
    print("Rig created successfully!")


    # Exit pose mode
    bpy.ops.object.mode_set(mode='OBJECT')


# Example usage:
# create_rig_from_json(r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton.rig.json")
if __name__ == "__main__":

    filepath = r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton.rig.json"
    create_rig_from_json(filepath)