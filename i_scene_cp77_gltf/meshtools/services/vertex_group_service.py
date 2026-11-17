from contextlib import contextmanager

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh import is_mesh
from ...blender.mesh_repair import remove_unmatched_vertex_groups
from ...blender.mesh_validation import armature_modifier, bone_group_indices
from ...blender.operator_results import OperationResult
from ...blender.vertex_groups import give_nearest_weights, vertex_weights
from ...core.log import get_logger

_LOG = get_logger(__name__)


@contextmanager
def temporary_mode(target_mode="OBJECT"):
    """Context manager for temporary mode switches while preserving the Blender context"""

    store_current_context()
    try:
        safe_mode_switch(target_mode)
        yield get_safe_mode()
    finally:
        # Restore complete context (mode, selection, visibility, etc.)
        restore_previous_context()


def _selected_meshes(context):
    return [obj for obj in context.selected_objects if is_mesh(obj)]


def _deform_groups(obj):
    """The indices of the vertex groups that deform obj, its armature's bone groups, or None for every group"""
    modifier = armature_modifier(obj)
    return None if modifier is None else bone_group_indices(obj, modifier.object)


def delete_empty_vertex_groups(context):
    """Delete the selected meshes' vertex groups that carry no weight or that no bone of their armature uses"""
    meshes = _selected_meshes(context)
    if not meshes:
        return OperationResult.cancelled(
            "Select the meshes whose unused vertex groups to delete."
        )

    total_removed = 0
    with temporary_mode("OBJECT"):
        for obj in meshes:
            used = {group for entries in vertex_weights(obj) for group, _ in entries}
            empty = [
                group.name for group in obj.vertex_groups if group.index not in used
            ]
            for name in empty:
                obj.vertex_groups.remove(obj.vertex_groups[name])
            modifier = armature_modifier(obj)
            boneless = (
                []
                if modifier is None
                else [
                    group.name
                    for group in obj.vertex_groups
                    if modifier.object.data.bones.get(group.name) is None
                ]
            )
            if boneless:
                # Their vertices take the weights of the nearest weighted vertex, as Try Fix gives them.
                remove_unmatched_vertex_groups(obj, boneless, modifier.object)
            removed = len(empty) + len(boneless)
            total_removed += removed
            if removed:
                _LOG.info("Removed %s unused groups from %s", removed, obj.name)

    return OperationResult.finished(
        f"Removed {total_removed} unused vertex groups total.", payload=total_removed
    )


def group_ungrouped_vertices(context):
    """Give the selected meshes' vertices without weights the weights of their nearest weighted vertex"""
    meshes = _selected_meshes(context)
    if not meshes:
        return OperationResult.cancelled(
            "Select the meshes whose ungrouped vertices to group."
        )

    ungrouped = 0
    assigned = 0
    with temporary_mode("OBJECT"):
        for obj in meshes:
            groups = _deform_groups(obj)
            indices = [
                index
                for index, entries in enumerate(vertex_weights(obj, groups))
                if not entries
            ]
            ungrouped += len(indices)
            assigned += give_nearest_weights(obj, indices, groups)

    if not ungrouped:
        return OperationResult.finished("No ungrouped vertices found.", payload=0)
    if not assigned:
        return OperationResult.cancelled(
            "The selected meshes have no weighted vertices to copy from."
        )
    message = f"Assigned {assigned} ungrouped vertices to nearest groups."
    if assigned < ungrouped:
        return OperationResult.finished(
            f"{message} {ungrouped - assigned} on meshes without weights were left as they are.",
            level="WARNING",
            payload=assigned,
        )
    return OperationResult.finished(message, payload=assigned)
