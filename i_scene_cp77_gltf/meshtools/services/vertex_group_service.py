from collections import defaultdict
from contextlib import contextmanager

import numpy as np
from mathutils.kdtree import KDTree

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh import is_mesh
from ...blender.operator_results import OperationResult
from ...core.log import get_logger

_LOG = get_logger(__name__)

WEIGHT_EPSILON = 1e-5


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


class VertexGroupManager:
    """Efficient vertex group operations"""

    def __init__(self, obj):
        self.obj = obj
        self.mesh = obj.data
        self._weights = None
        self._grouped_verts = None
        self._tree = None

    @property
    def vertex_weights(self):
        """Each vertex's (group index, weight) pairs with weight above WEIGHT_EPSILON"""
        if self._weights is None:
            # Weights are read only when groups exist: Blender 5.0.0 corrupts a mesh without any when they are read.
            if not self.obj.vertex_groups:
                self._weights = [()] * len(self.mesh.vertices)
            else:
                self._weights = [
                    tuple(
                        (element.group, element.weight)
                        for element in vertex.groups
                        if element.weight > WEIGHT_EPSILON
                    )
                    for vertex in self.mesh.vertices
                ]
        return self._weights

    @property
    def grouped_vertices(self):
        """Cache vertices that have at least one nontrivial weight"""
        if self._grouped_verts is None:
            self._grouped_verts = {
                index for index, weights in enumerate(self.vertex_weights) if weights
            }
        return self._grouped_verts

    def get_empty_groups(self) -> list[int]:
        """The indices of groups that no vertex carries weight in, highest first"""
        if not self.obj.vertex_groups:
            return []
        used_groups = {
            element.group
            for vertex in self.mesh.vertices
            for element in vertex.groups
            if element.weight > WEIGHT_EPSILON
        }
        all_groups = set(range(len(self.obj.vertex_groups)))
        return sorted(all_groups - used_groups, reverse=True)

    def remove_empty_groups(self) -> int:
        """Remove empty vertex groups and return count"""
        empty_groups = self.get_empty_groups()
        count = len(empty_groups)

        # Remove in reverse order to maintain indices
        for idx in empty_groups:
            self.obj.vertex_groups.remove(self.obj.vertex_groups[idx])

        return count

    def find_nearest_grouped_vertex(self, vertex_idx: int) -> int | None:
        """The grouped vertex nearest to the given vertex"""
        return self.nearest_search(self.mesh.vertices[vertex_idx].co)

    def build_spatial_index(self):
        """A KD-tree over the grouped vertices"""
        positions = np.empty(len(self.mesh.vertices) * 3, dtype=np.float64)
        self.mesh.vertices.foreach_get("co", positions)
        positions = positions.reshape(-1, 3)
        self._tree = KDTree(len(self.grouped_vertices))
        for index in self.grouped_vertices:
            self._tree.insert(positions[index], index)
        self._tree.balance()

    def nearest_search(self, target_co):
        """The grouped vertex nearest to a position, or None when no vertex is grouped"""
        if not self.grouped_vertices:
            return None
        if self._tree is None:
            self.build_spatial_index()
        return self._tree.find(target_co)[1]


def delete_empty_vertex_groups(context):
    """Delete empty vertex groups from selected objects"""
    obj = context.object

    if not obj:
        return OperationResult.cancelled(
            "No active object. Please select a mesh and try again."
        )

    if not is_mesh(obj):
        return OperationResult.cancelled("The active object is not a mesh.")

    selected_meshes = [o for o in context.selected_objects if is_mesh(o)]

    if not selected_meshes:
        return OperationResult.cancelled("No mesh objects selected.")

    total_removed = 0

    with temporary_mode("OBJECT"):
        for obj in selected_meshes:
            manager = VertexGroupManager(obj)
            removed = manager.remove_empty_groups()
            total_removed += removed

            if removed > 0:
                _LOG.info("Removed %s empty groups from %s", removed, obj.name)

    return OperationResult.finished(
        f"Removed {total_removed} empty vertex groups total.", payload=total_removed
    )


def group_ungrouped_vertices(context):
    """Assign ungrouped vertices to nearest grouped vertices"""
    obj = context.object

    if not obj or not is_mesh(obj):
        return OperationResult.cancelled("No active mesh object selected.")

    with temporary_mode("OBJECT"):
        manager = VertexGroupManager(obj)
        weights = manager.vertex_weights
        ungrouped = [index for index, entries in enumerate(weights) if not entries]

        if not ungrouped:
            return OperationResult.finished("No ungrouped vertices found.", payload=0)

        # Return early if there are no weighted verts to copy from
        if not manager.grouped_vertices:
            return OperationResult.cancelled("No vertices with weights to copy from.")

        # Each vertex copies the weights of its nearest grouped vertex; one add call per group and weight.
        copies = defaultdict(list)
        for index in ungrouped:
            for group, weight in weights[manager.find_nearest_grouped_vertex(index)]:
                copies[group, weight].append(index)
        for (group, weight), indices in copies.items():
            obj.vertex_groups[group].add(indices, weight, "REPLACE")

    return OperationResult.finished(
        f"Assigned {len(ungrouped)} ungrouped vertices to nearest groups.",
        payload=len(ungrouped),
    )
