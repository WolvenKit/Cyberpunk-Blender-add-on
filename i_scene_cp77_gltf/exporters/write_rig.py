# Write rig back to json
# This script reads a rig from a JSON file and updates the bone transforms with the current pose data from Blender.
# Doesnt handle additions or removals of bones yet, only updates the transforms of existing bones.
# Simarilius 22-3-2025


import bpy
import os
import json
from mathutils import Quaternion, Vector

def save_rig_to_json( output_filepath):
    

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
    # Extract relevant data
    bone_names = rig_data["Data"]["RootChunk"]["boneNames"]
    bone_parents = rig_data["Data"]["RootChunk"]["boneParentIndexes"]
    bone_transforms = rig_data["Data"]["RootChunk"]["boneTransforms"]

    # Update the JSON data with the current bone transforms
    for i, bone_name in enumerate(bone_names):
        bone_name = bone_name["$value"]
        bone = armature_object.pose.bones.get(bone_name)
        if bone is None:
            raise ValueError(f"Bone '{bone_name}' not found in the armature.")

        # Get the global transform of the bone
        global_translation = bone.head
        global_rotation = bone.matrix.to_quaternion()

        # Calculate relative transform
        if bone_parents[i] == -1:  # Root bone
            local_translation = global_translation
            local_rotation = global_rotation
        else:
            parent_bone_name = bone_names[bone_parents[i]]["$value"]
            parent_bone = armature_object.pose.bones.get(parent_bone_name)
            if parent_bone is None:
                raise ValueError(f"Parent bone '{parent_bone_name}' not found in the armature.")

            parent_translation = parent_bone.head
            parent_rotation = parent_bone.matrix.to_quaternion()

            # Calculate relative translation and rotation
            local_translation = parent_rotation.inverted() @ (global_translation - parent_translation)
            local_rotation = parent_rotation.inverted() @ global_rotation

        # Update the JSON data
        bone_transforms[i]["Translation"] = {
            "$type": "Vector4",
            "X": local_translation.x,
            "Y": local_translation.y,
            "Z": local_translation.z
        }
        bone_transforms[i]["Rotation"] = {
            "$type": "Quaternion",
            "r": local_rotation.w,
            "i": local_rotation.x,
            "j": local_rotation.y,
            "k": local_rotation.z
        }

    # Save the updated JSON data to the output file
    with open(output_filepath, 'w') as file:
        json.dump(rig_data, file, indent=4)

    print(f"Rig saved successfully to {output_filepath}!")

# Example usage:
# save_rig_to_json(r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton.rig.json")
if __name__ == "__main__":

    outpath = r"c:\CPMod\terrain_collision\source\raw\base\characters\common\hair\hh_040_wa__pixie_bob\hh_040_wa__pixie_bob_dangle_skeleton_mod.rig.json"   
    save_rig_to_json(outpath)