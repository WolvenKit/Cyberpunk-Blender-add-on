import bpy
from mathutils import Vector

# Set the names of the armatures that you're trying to retarget
current_armature_name = "your_mesh_armature"
target_armature_name = "Armature"

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
    bpy.ops.object.mode_set(mode='EDIT')
        
    # Check if the active object is an armature and in edit mode
    if not bpy.context.active_object and bpy.context.active_object.type == 'ARMATURE':
        print("Make sure you have an armature selected in edit mode.")
        return False 

    # Deselect all bones first
    bpy.ops.armature.select_all(action='DESELECT')
    return True

matching_bones = {}

def find_closest_bone(bone_name):        
    activeBone = bpy.data.objects[current_armature_name].data.bones[bone_name]    
    activeBone.select = True
        
    # Get the location of the selected bone
    selected_bone_location = activeBone.head

    # Initialize variables for closest bone and its distance
    closest_bone = None
    closest_distance = float('inf')

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
    print(f"\"{bone_name}\" : \"{closest_bone}\",")

def rename_vertex_groups(mesh_name):
    
    print(f"\nrenaming vertex groups in {mesh_name}...")
    for original_name, target_name in matching_bones.items():
        # Check if the vertex group exists and rename it        
        vertex_groups = bpy.data.objects[mesh_name].vertex_groups
        matching_group = next((group for group in vertex_groups if group.name == original_name), None)

        if matching_group is None:
            print(f"\tVertex group {original_name} not found")
            continue

        matching_group.name = target_name
        print(f"\t{original_name} -> {target_name}")

def reparent_meshes():
    # Find all meshes parented to target_armature and delete them
    parented_meshes_to_delete = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.parent == target_armature]
    for mesh_to_delete in parented_meshes_to_delete:
        bpy.data.objects.remove(mesh_to_delete, do_unlink=True)

    # Find all meshes parented to current_armature
    meshes_to_reparent = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.parent == current_armature]

    # Reparent the meshes to target_armature and update armature modifiers
    for mesh in meshes_to_reparent:
        mesh.parent = target_armature
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object == current_armature:
                modifier.object = target_armature

        print("Meshes reparented successfully.")
        
if check_prerequisites():
    target_bone_names = {bone.name for bone in target_armature.data.bones}
    # Get the names of bones in the mesh armature that are not in the target armature
    different_bones = [bone.name for bone in current_armature.data.bones if bone.name not in target_bone_names]

    for bone in different_bones:
        find_closest_bone(bone)

    print(f"Found {len(matching_bones)} bones that are not in \"{target_armature_name}\"")
    
    parented_meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.parent == current_armature]
    for mesh in parented_meshes: 
        rename_vertex_groups(mesh.name)
    
    reparent_meshes()
    print("Done! You can import now")