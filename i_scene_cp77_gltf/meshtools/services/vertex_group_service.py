from contextlib import contextmanager
from typing import List, Optional

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh import is_mesh
from ..model import MeshToolResult

WEIGHT_EPSILON = 1e-5


@contextmanager
def temporary_mode(context, target_mode='OBJECT'):
    """Context manager for temporary mode switches while preserving the Blender context."""
    # Store complete context
    store_current_context()
    try:
        # Switch to target mode
        safe_mode_switch(target_mode)
        yield get_safe_mode()
    finally:
        # Restore complete context (mode, selection, visibility, etc.)
        restore_previous_context()


class VertexGroupManager:
    """Efficient vertex group operations."""

    def __init__(self, obj):
        self.obj = obj
        self.mesh = obj.data
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
        all_groups = set(range(len(self.obj.vertex_groups)))
        return sorted(all_groups - used_groups, reverse=True)

    def remove_empty_groups(self) -> int:
        """Remove empty vertex groups and return count."""
        empty_groups = self.get_empty_groups()
        count = len(empty_groups)

        # Remove in reverse order to maintain indices
        for idx in empty_groups:
            self.obj.vertex_groups.remove(self.obj.vertex_groups[idx])

        return count

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

    selected_meshes = [o for o in context.selected_objects if is_mesh(o)]

    if not selected_meshes:
        return MeshToolResult.failure("No mesh objects selected.")

    total_removed = 0

    with temporary_mode(context, 'OBJECT'):
        for obj in selected_meshes:
            manager = VertexGroupManager(obj)
            removed = manager.remove_empty_groups()
            total_removed += removed

            if removed > 0:
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
    )
