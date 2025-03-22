# Read rig from json 
# This script reads a rig from a JSON file and creates an armature in Blender.
# Simarilius 22-3-2025


import bpy
import json
from mathutils import Quaternion, Vector

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

        # Create a new bone
        bone = armature.edit_bones.new(bone_name)
        bone.head = global_translation
        bone.tail = global_translation + Vector((0, 0.1, 0))  # Temporary tail position
        bone.align_roll(global_rotation.to_euler())

        # Set parent if applicable
        if parent_index != -1:
            parent_bone_name = bone_names[parent_index]["$value"]
            bone.parent = bones[parent_bone_name]

        # Store the bone for reference
        bones[bone_name] = bone

    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')

    print("Rig created successfully!")




# Example usage:
# create_rig_from_json(r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton.rig.json")
if __name__ == "__main__":

    filepath = r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton.rig.json"
    create_rig_from_json(filepath)