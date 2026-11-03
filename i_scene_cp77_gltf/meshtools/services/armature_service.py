import re

<<<<<<< Updated upstream
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
=======
from ...blender.context import preserved_context, safe_mode_switch
from ...blender.operator_results import OperationResult
from ...core.log import get_logger

_LOG = get_logger(__name__)


def delete_unused_bones(context):
    """Delete the selected armature's bones that none of its child meshes has a vertex group for"""
    obj = context.active_object
    if not obj or obj.type != "ARMATURE":
        return OperationResult.cancelled("Active object must be an armature.")
>>>>>>> Stashed changes

    # Collect all vertex group names from all child meshes
    all_vertex_groups = set()
    for child in obj.children:
<<<<<<< Updated upstream
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
=======
        if child.type == "MESH":
            all_vertex_groups.update(vg.name for vg in child.vertex_groups)

    if not all_vertex_groups:
        return OperationResult.cancelled("No vertex groups found in mesh children.")
    if (
        context.view_layer.objects.get(obj.name) is None
        or not obj.is_editable
        or not obj.data.is_editable
    ):
        return OperationResult.cancelled(
            "The armature is not editable in the current view layer."
        )

    bones_to_remove = []
    try:
        # Imported armatures come in hidden; the armature is shown for the edit and hidden again after.
        with preserved_context() as snapshot:
            safe_mode_switch("OBJECT")
            snapshot.object_visibility.setdefault(
                obj.name,
                {
                    "hide_viewport": obj.hide_viewport,
                    "hide_select": obj.hide_select,
                    "hide_get": obj.hide_get(),
                },
            )
            obj.hide_viewport = False
            obj.hide_select = False
            obj.hide_set(False)
            for selected in tuple(context.selected_objects):
                selected.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            safe_mode_switch("EDIT")
            edit_bones = obj.data.edit_bones
            # Keep a bone if its name, or its name without Blender's .001-style suffix, has a vertex group.
            bones_to_remove = [
                bone.name
                for bone in edit_bones
                if bone.name not in all_vertex_groups
                and re.sub(r"\.\d+$", "", bone.name) not in all_vertex_groups
            ]
            for name in bones_to_remove:
                _LOG.debug("Deleting unused bone: %s", name)
                edit_bones.remove(edit_bones[name])
    except Exception as e:
        return OperationResult.cancelled(f"Error during bone deletion: {e}", error=e)

    return OperationResult.finished(f"Removed {len(bones_to_remove)} unused bones.")


def _selected_mesh_armatures(meshes):
    targets = {}
    for mesh in meshes:
        candidates = [
            modifier.object
            for modifier in mesh.modifiers
            if modifier.type == "ARMATURE" and modifier.object is not None
        ]
        parent = mesh.parent
        while parent is not None:
            if parent.type == "ARMATURE":
                candidates.append(parent)
                break
            parent = parent.parent
        for armature in candidates:
            if armature.type == "ARMATURE":
                targets.setdefault(armature.as_pointer(), armature)
    return tuple(targets.values())


def delete_orphan_bones(context):
    meshes = tuple(obj for obj in context.selected_objects if obj.type == "MESH")
    if not meshes:
        return OperationResult.cancelled(
            "Select the meshes whose vertex groups should be kept."
        )
    armatures = _selected_mesh_armatures(meshes)
    if not armatures:
        return OperationResult.cancelled(
            "The selected meshes have no associated armature."
        )
    group_names = {group.name for mesh in meshes for group in mesh.vertex_groups}
    editable = []
    seen_data = set()
    skipped = 0
    for armature in armatures:
        if (
            context.view_layer.objects.get(armature.name) is None
            or not armature.is_editable
            or not armature.data.is_editable
        ):
            skipped += 1
            continue
        identity = armature.data.as_pointer()
        if identity not in seen_data:
            editable.append(armature)
            seen_data.add(identity)
    if not editable:
        return OperationResult.cancelled(
            "Associated armatures are not editable in the current view layer."
        )

    removed = 0
    processed = 0
    try:
        with preserved_context() as snapshot:
            safe_mode_switch("OBJECT")
            for obj in tuple(context.selected_objects):
                obj.select_set(False)
            for armature in editable:
                snapshot.object_visibility.setdefault(
                    armature.name,
                    {
                        "hide_viewport": armature.hide_viewport,
                        "hide_select": armature.hide_select,
                        "hide_get": armature.hide_get(),
                    },
                )
                armature.hide_viewport = False
                armature.hide_select = False
                armature.hide_set(False)
                armature.select_set(True)
            context.view_layer.objects.active = editable[0]
            safe_mode_switch("EDIT")
            for armature in editable:
                if armature.mode != "EDIT":
                    skipped += 1
                    continue
                bones = armature.data.edit_bones
                orphan_names = tuple(
                    bone.name for bone in bones if bone.name not in group_names
                )
                for name in orphan_names:
                    bones.remove(bones[name])
                    removed += 1
                processed += 1
    except Exception as error:
        message = f"Bone cleanup stopped: {error}"
        if removed:
            # The partial result reports no error, so its traceback is logged here.
            _LOG.warning(
                "Orphan-bone cleanup stopped after removing %d bone(s): %s",
                removed,
                error,
                exc_info=True,
            )
            return OperationResult.finished(
                f"Removed {removed} orphan bone(s). {message}", level="WARNING"
            )
        return OperationResult.cancelled(message, error=error)

    if not processed:
        return OperationResult.cancelled(
            "Associated armatures could not enter Edit Mode."
        )
    message = f"Removed {removed} orphan bone(s) from {processed} armature(s)."
    if skipped:
        return OperationResult.finished(
            f"{message} Skipped {skipped} unavailable armature(s).", level="WARNING"
        )
    return OperationResult.finished(message)
>>>>>>> Stashed changes
