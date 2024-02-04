import bpy
from mathutils import Vector
import re

# Set the names of the armatures that you're trying to retarget
current_armature_name = "Armature.002"  # the armature you want to import, with TOO MANY DAMN BONES
target_armature_name = "Armature.003"  # the target armature (e.g. body__t_bug our lord and saviour)

# Get references to the current and target armatures
current_armature = bpy.data.objects.get(current_armature_name)
target_armature = bpy.data.objects.get(target_armature_name)


def check_prerequisites():
    # Check if both armatures exist
    if not current_armature:
        print("Set line 4 to the name of your current armature (the one you want to import)")
        return False

    if not target_armature:
        print("Set line 5 to the name of your target armature (the one you want to import into, e.g. body__t_bug)")
        return False

    current_armature.select_set(True)

    # Deselect all bones first
    bpy.ops.object.mode_set(mode="EDIT")
    return True


matching_bones = {}


def find_closest_bone(bone_name):
    activeBone = bpy.data.objects[current_armature_name].data.bones[bone_name]
    activeBone.select = True

    # Get the location of the selected bone
    selected_bone_location = activeBone.head

    # Initialize variables for closest bone and its distance
    closest_bone = None
    closest_distance = float("inf")

    # Iterate through bones in the target armature
    for bone in target_armature.data.bones:
        # Check if the bone is not in the current armature
        if bone.name not in current_armature.data.bones:
            # Calculate the distance to the selected bone
            distance = (Vector(bone.head) - selected_bone_location).length

            # Update closest bone if the distance is smaller
            if distance < closest_distance:
                closest_distance = distance
                closest_bone = bone.name

    matching_bones[bone_name] = closest_bone

    # Print the name of the closest bone to the console
    # print(f"\"{bone_name}\" : \"{closest_bone}\",")


def rename_vertex_groups(mesh_name):
    num_renamed_groups = 0
    for original_name, target_name in matching_bones.items():
        # Check if the vertex group exists and rename it
        matching_group = bpy.data.objects[mesh_name].vertex_groups.get(original_name)

        if matching_group is None:
            continue

        num_renamed_groups = num_renamed_groups + 1
        matching_group.name = target_name
    if num_renamed_groups > 0:
        print(f"\trenamed {num_renamed_groups} vertex groups in {mesh_name}")


def merge_similar_vertex_groups(mesh_name):
    obj = bpy.data.objects.get(mesh_name)

    pattern = re.compile(r"\.\d+$")

    # Iterate over existing vertex groups
    existing_groups = bpy.data.objects[mesh_name].vertex_groups.keys()
    needs_merging = [key for key in existing_groups if pattern.search(key)]
    original_names = [string[: pattern.search(string).start()] for string in needs_merging if pattern.search(string)]

    for root_group_name in original_names:
        groupNamePattern = re.compile(root_group_name + r"\.\d+$")
        groups_to_merge = [group for group in existing_groups if groupNamePattern.search(group)]

        # Check if there are groups to merge
        if not groups_to_merge or len(groups_to_merge) == 0:
            return

        # Create a new vertex group to store the merged weights
        merged_group = bpy.data.objects[mesh_name].vertex_groups.get(root_group_name)

        # Iterate over the groups to merge
        for group_name in groups_to_merge:
            source_group = bpy.data.objects[mesh_name].vertex_groups.get(group_name)

            if source_group is None:
                print(f"No group {group_name} found")
                continue

            # Iterate over the vertices and transfer weights to the merged group
            for vertex in obj.data.vertices:
                if not group_name in vertex.groups.keys():
                    continue
                vertex_index = vertex.index
                weight = source_group.weight(vertex_index)
                weight = weight if weight else 1
                # Add or update the weight in the merged group
                merged_group.add([vertex_index], weight, "REPLACE")

            # Remove the source group after merging
            bpy.data.objects[mesh_name].vertex_groups.remove(source_group)

            print(f"Vertex groups {groups_to_merge} merged into '{root_group_name}'.")


if check_prerequisites():
    target_bone_names = {bone.name for bone in target_armature.data.bones}
    # Get the names of bones in the mesh armature that are not in the target armature
    different_bones = [bone.name for bone in current_armature.data.bones if bone.name not in target_bone_names]

    for bone in different_bones:
        find_closest_bone(bone)

    print(f'Found {len(matching_bones)} bones that are not in "{target_armature_name}"')

    parented_meshes = [
        obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.parent == current_armature
    ]

    # find target armature collection so that we can parent our meshes to it
    for collection in bpy.data.collections:
        if target_armature_name in collection.objects:
            target_armature_collection = collection
            break  # Break the loop after finding the first collection

    for mesh in parented_meshes:
        print(f"\n processing {mesh.name}")
        rename_vertex_groups(mesh.name)
        merge_similar_vertex_groups(mesh.name)

        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == current_armature:
                modifier.object = target_armature

        # Change the parent to target_armature
        mesh.parent = target_armature

        # Remove the mesh from its current collections
        for collection in mesh.users_collection:
            collection.objects.unlink(mesh)

        if target_armature_collection:
            target_armature_collection.objects.link(mesh)

    bpy.ops.object.mode_set(mode="OBJECT")
    print("Done! You can import now")
