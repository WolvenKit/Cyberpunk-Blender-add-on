# Write rig back to json
# This script reads a rig from a JSON file and updates the bone transforms with the current pose data from Blender.
# Doesnt handle additions or removals of bones yet, only updates the transforms of existing bones.
# Simarilius 22-3-2025


import bpy
import os
import json
from mathutils import Quaternion, Vector

def save_rig_to_json(output_filepath):
    # Get the armature object
    armature_object = bpy.context.view_layer.objects.active
    if armature_object is None or armature_object.type != 'ARMATURE':
        raise ValueError("No active armature object found in the scene.")

    json_filepath = armature_object.data['source']
    if not os.path.exists(json_filepath):
        raise ValueError(f"Source JSON file '{json_filepath}' not found.")
    
    # Load the original JSON data
    with open(json_filepath, 'r') as file:
        rig_data = json.load(file)

    # Prepare updated lists
    updated_bones = []

    # Helper function to calculate the depth of a bone in the hierarchy
    def get_bone_depth(bone):
        depth = 0
        while bone.parent is not None:
            depth += 1
            bone = bone.parent
        return depth

    # Iterate over Blender bones and collect data
    for bone in armature_object.pose.bones:
        bone_name = bone.name
        parent_bone = bone.parent

        # Get the global transform of the bone
        global_translation = bone.head
        global_rotation = bone.matrix.to_quaternion()

        # Calculate relative transform
        if parent_bone is None:  # Root bone
            local_translation = global_translation
            local_rotation = global_rotation
            parent_name = None
        else:
            parent_translation = parent_bone.head
            parent_rotation = parent_bone.matrix.to_quaternion()

            # Calculate relative translation and rotation
            local_translation = parent_rotation.inverted() @ (global_translation - parent_translation)
            local_rotation = parent_rotation.inverted() @ global_rotation
            parent_name = parent_bone.name

        # Add the bone data to the updated list
        updated_bones.append({
            "name": {
                "$type": "CName",
                "$storage": "string",
                "$value": bone_name
            },
            "parent_name": parent_name,  # Temporarily store the parent name
            "depth": get_bone_depth(bone),  # Store the depth of the bone
            "transform": {
                "$type": "QsTransform",
                "Translation": {
                    "$type": "Vector4",
                    "X": local_translation.x,
                    "Y": local_translation.y,
                    "Z": local_translation.z
                },
                "Rotation": {
                    "$type": "Quaternion",
                    "r": local_rotation.w,
                    "i": local_rotation.x,
                    "j": local_rotation.y,
                    "k": local_rotation.z
                },
                "Scale": {
                    "$type": "Vector4",
                    "W": 1,
                    "X": 1,
                    "Y": 1,
                    "Z": 1
                }
            }
        })

    # Sort the bones by depth (lowest to highest)
    updated_bones.sort(key=lambda b: b["depth"])

    # Update parent indices based on the sorted order
    bone_name_to_index = {bone["name"]["$value"]: i for i, bone in enumerate(updated_bones)}
    for bone in updated_bones:
        parent_name = bone.pop("parent_name")  # Remove the temporary parent_name field
        bone["parent_index"] = bone_name_to_index[parent_name] if parent_name else -1

    # Remove the depth field as it's no longer needed
    for bone in updated_bones:
        bone.pop("depth")

    # Update the JSON data
    rig_data["Data"]["RootChunk"]["boneNames"] = [bone["name"] for bone in updated_bones]
    rig_data["Data"]["RootChunk"]["boneParentIndexes"] = [bone["parent_index"] for bone in updated_bones]
    rig_data["Data"]["RootChunk"]["boneTransforms"] = [bone["transform"] for bone in updated_bones]

    # Save the updated JSON data to the output file
    with open(output_filepath, 'w') as file:
        json.dump(rig_data, file, indent=4)

    print(f"Rig saved successfully to {output_filepath}!")

# Example usage:
# save_rig_to_json(r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton.rig.json")
if __name__ == "__main__":

    outpath = r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton_mod.rig.json"   
    save_rig_to_json(outpath)