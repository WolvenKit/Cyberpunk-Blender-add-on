import re

import bpy

from ...addon_identity import get_addon_preferences
from ...blender.context import safe_mode_switch
from ..model import MeshToolResult


def delete_unused_bones(context):
    """
    Deletes bones from the selected armature that do not have corresponding vertex groups
    in any of its child mesh objects.
    """
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        return MeshToolResult.failure("Active object must be an armature.")

    # Collect all vertex group names from all child meshes
    all_vertex_groups = set()
    for child in obj.children:
        if child.type == 'MESH':
            all_vertex_groups.update(vg.name for vg in child.vertex_groups)

    if not all_vertex_groups:
        return MeshToolResult.failure("No vertex groups found in mesh children.")

    original_mode = obj.mode

    # Safely switch to edit mode
    try:
        if obj and obj.name in bpy.data.objects and original_mode != 'EDIT':
            safe_mode_switch('EDIT')
    except Exception as e:
        return MeshToolResult.failure(f"Failed to switch to edit mode: {e}")

    try:
        edit_bones = obj.data.edit_bones

        # Build a list of bones to remove
        bones_to_remove = []
        for bone in edit_bones:
            # Strip Blender's automatic .001, .002 suffixes
            base_name = re.sub(r'\.\d+$', '', bone.name)

            # Keep bone if either its name or base name has a vertex group
            if bone.name not in all_vertex_groups and base_name not in all_vertex_groups:
                bones_to_remove.append(bone)

        # Remove bones
        try:
            cp77_addon_prefs = get_addon_preferences(context)
            verbose = not cp77_addon_prefs.non_verbose
        except (KeyError, AttributeError):
            verbose = True

        for bone in bones_to_remove:
            if verbose:
                print(f"Deleting unused bone: {bone.name}")
            edit_bones.remove(bone)

    except Exception as e:
        return MeshToolResult.failure(f"Error during bone deletion: {e}")

    finally:
        # Always restore the original mode
        try:
            if obj and obj.name in bpy.data.objects and obj.mode != original_mode:
                safe_mode_switch(original_mode)
        except Exception as e:
            print(f"Warning: Could not restore original mode: {e}")

    return MeshToolResult.success(f"Removed {len(bones_to_remove)} unused bones.")
