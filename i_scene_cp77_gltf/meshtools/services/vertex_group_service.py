<<<<<<< Updated upstream
from contextlib import contextmanager
from typing import List, Optional
=======
from collections import defaultdict
from contextlib import contextmanager

import numpy as np
from mathutils.kdtree import KDTree
>>>>>>> Stashed changes

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh import is_mesh
<<<<<<< Updated upstream
from ..model import MeshToolResult
=======
from ...blender.operator_results import OperationResult
from ...core.log import get_logger

_LOG = get_logger(__name__)
>>>>>>> Stashed changes

WEIGHT_EPSILON = 1e-5


@contextmanager
<<<<<<< Updated upstream
def temporary_mode(context, target_mode='OBJECT'):
    """Context manager for temporary mode switches while preserving the Blender context."""
    # Store complete context
    store_current_context()
    try:
        # Switch to target mode
=======
def temporary_mode(target_mode="OBJECT"):
    """Context manager for temporary mode switches while preserving the Blender context"""

    store_current_context()
    try:
>>>>>>> Stashed changes
        safe_mode_switch(target_mode)
        yield get_safe_mode()
    finally:
        # Restore complete context (mode, selection, visibility, etc.)
        restore_previous_context()


class VertexGroupManager:
<<<<<<< Updated upstream
    """Efficient vertex group operations."""
=======
    """Efficient vertex group operations"""
>>>>>>> Stashed changes

    def __init__(self, obj):
        self.obj = obj
        self.mesh = obj.data
<<<<<<< Updated upstream
        self._group_cache = None
        self._grouped_verts = None

    @property
    def grouped_vertices(self):
        """Cache vertices that have at least one nontrivial weight."""
        if self._grouped_verts is None:
            self._grouped_verts = set()
            for v in self.mesh.vertices:
                # consider only weights > epsilon as grouped
                if any(ge.weight > WEIGHT_EPSILON for ge in v.groups):
                    self._grouped_verts.add(v.index)
        return self._grouped_verts

    def get_empty_groups(self) -> List[int]:
        """Find empty vertex groups efficiently."""
        # Track which groups have vertices
        used_groups = set()
        for vert in self.mesh.vertices:
            for vg in vert.groups:
                used_groups.add(vg.group)

        # Find empty groups
=======
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
>>>>>>> Stashed changes
        all_groups = set(range(len(self.obj.vertex_groups)))
        return sorted(all_groups - used_groups, reverse=True)

    def remove_empty_groups(self) -> int:
<<<<<<< Updated upstream
        """Remove empty vertex groups and return count."""
=======
        """Remove empty vertex groups and return count"""
>>>>>>> Stashed changes
        empty_groups = self.get_empty_groups()
        count = len(empty_groups)

        # Remove in reverse order to maintain indices
        for idx in empty_groups:
            self.obj.vertex_groups.remove(self.obj.vertex_groups[idx])

        return count

<<<<<<< Updated upstream
    def find_nearest_grouped_vertex(self, vertex_idx: int) -> Optional[int]:
        """Find nearest vertex with groups using spatial partitioning."""
        target_co = self.mesh.vertices[vertex_idx].co

        # Build spatial index if not cached
        if not hasattr(self, '_spatial_index'):
            self.build_spatial_index()

        # Search in expanding radius
        return self.nearest_search(target_co)

    def build_spatial_index(self):
        """Build spatial index for grouped vertices."""
        # Simple grid-based spatial index
        self._spatial_index = {}
        grid_size = 1.0

        for v_idx in self.grouped_vertices:
            vert = self.mesh.vertices[v_idx]
            grid_key = (
                int(vert.co.x / grid_size),
                int(vert.co.y / grid_size),
                int(vert.co.z / grid_size)
                )
            self._spatial_index.setdefault(grid_key, []).append(v_idx)

    def nearest_search(self, target_co):
        """Search for nearest vertex using spatial index."""
        grid_size = 1.0
        grid_x = int(target_co.x / grid_size)
        grid_y = int(target_co.y / grid_size)
        grid_z = int(target_co.z / grid_size)

        # Search in expanding shells
        min_dist = float('inf')
        nearest_idx = None

        for radius in range(5):  # Limit search radius
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for dz in range(-radius, radius + 1):
                        # Skip inner shells
                        if abs(dx) < radius and abs(dy) < radius and abs(dz) < radius:
                            continue

                        grid_key = (grid_x + dx, grid_y + dy, grid_z + dz)
                        if grid_key in self._spatial_index:
                            for v_idx in self._spatial_index[grid_key]:
                                v_co = self.mesh.vertices[v_idx].co
                                dist = (v_co - target_co).length
                                if dist < min_dist:
                                    min_dist = dist
                                    nearest_idx = v_idx

            # Early exit if found
            if nearest_idx is not None:
                return nearest_idx

        # Fallback to exhaustive search if needed
        if nearest_idx is None:
            for v_idx in self.grouped_vertices:
                v_co = self.mesh.vertices[v_idx].co
                dist = (v_co - target_co).length
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = v_idx

        return nearest_idx


def delete_empty_vertex_groups(context):
    """Delete empty vertex groups from selected objects."""
    obj = context.object

    if not obj:
        return MeshToolResult.failure("No active object. Please select a mesh and try again.")

    if not is_mesh(obj):
        return MeshToolResult.failure("The active object is not a mesh.")
=======
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
>>>>>>> Stashed changes

    selected_meshes = [o for o in context.selected_objects if is_mesh(o)]

    if not selected_meshes:
<<<<<<< Updated upstream
        return MeshToolResult.failure("No mesh objects selected.")

    total_removed = 0

    with temporary_mode(context, 'OBJECT'):
=======
        return OperationResult.cancelled("No mesh objects selected.")

    total_removed = 0

    with temporary_mode("OBJECT"):
>>>>>>> Stashed changes
        for obj in selected_meshes:
            manager = VertexGroupManager(obj)
            removed = manager.remove_empty_groups()
            total_removed += removed

            if removed > 0:
<<<<<<< Updated upstream
                print(f"Removed {removed} empty groups from {obj.name}")

    return MeshToolResult.success(f"Removed {total_removed} empty vertex groups total.", payload=total_removed)


def group_ungrouped_vertices(context):
    """Assign ungrouped vertices to nearest grouped vertices."""
    obj = context.object

    if not obj or not is_mesh(obj):
        return MeshToolResult.failure("No active mesh object selected.")

    with temporary_mode(context, 'OBJECT'):
        manager = VertexGroupManager(obj)

        # Find ungrouped vertices
        ungrouped = [v.index for v in obj.data.vertices
                     if not any(ge.weight > WEIGHT_EPSILON for ge in v.groups)]

        if not ungrouped:
            return MeshToolResult.success("No ungrouped vertices found.", payload=0)

        # Return early if there are no weighted verts to copy from
        if not manager.grouped_vertices:
            return MeshToolResult.failure("No vertices with weights to copy from.")

        # Process ungrouped vertices
        assigned_count = 0
        for v_idx in ungrouped:
            nearest_idx = manager.find_nearest_grouped_vertex(v_idx)
            if nearest_idx is None:
                continue

            nearest_vert = obj.data.vertices[nearest_idx]
            # copy only meaningful weights
            for ge in nearest_vert.groups:
                if ge.weight > WEIGHT_EPSILON:
                    group_name = obj.vertex_groups[ge.group].name
                    obj.vertex_groups[group_name].add([v_idx], ge.weight, 'ADD')

                assigned_count += 1

    return MeshToolResult.success(
        f"Assigned {assigned_count} ungrouped vertices to nearest groups.",
        payload=assigned_count,
=======
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
>>>>>>> Stashed changes
    )
