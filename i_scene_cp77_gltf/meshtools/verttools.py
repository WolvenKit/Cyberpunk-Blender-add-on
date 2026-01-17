import bpy
import re
from typing import List, Tuple, Optional
from contextlib import contextmanager
from ..main.common import show_message
from ..main.bartmoss_functions import (
    get_safe_mode,
    safe_mode_switch,
    store_current_context,
    restore_previous_context,
    select_object,
    is_mesh
)
WEIGHT_EPSILON = 1e-5
@contextmanager
def temporary_mode(context, target_mode='OBJECT'):
    """Context manager for temporary mode switches using bartmoss helpers."""
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

def del_empty_vgroup(self, context):
    """Delete empty vertex groups from selected objects."""
    obj = context.object

    if not obj:
        show_message("No active object. Please select a mesh and try again")
        return {'CANCELLED'}

    if not is_mesh(obj):
        show_message("The active object is not a mesh")
        return {'CANCELLED'}

    selected_meshes = [o for o in context.selected_objects if is_mesh(o)]

    if not selected_meshes:
        show_message("No mesh objects selected")
        return {'CANCELLED'}

    total_removed = 0

    with temporary_mode(context, 'OBJECT'):
        for obj in selected_meshes:
            manager = VertexGroupManager(obj)
            removed = manager.remove_empty_groups()
            total_removed += removed

            if removed > 0:
                print(f"Removed {removed} empty groups from {obj.name}")

    show_message(f"Removed {total_removed} empty vertex groups total")
    return {'FINISHED'}

def CP77GroupUngroupedVerts(self, context):
    """Assign ungrouped vertices to nearest grouped vertices."""
    obj = context.object

    if not obj or not is_mesh(obj):
        show_message("No active mesh object selected")
        return {'CANCELLED'}

    with temporary_mode(context, 'OBJECT'):
        manager = VertexGroupManager(obj)

        # Find ungrouped vertices
        ungrouped = [v.index for v in obj.data.vertices
                     if not any(ge.weight > WEIGHT_EPSILON for ge in v.groups)]

        if not ungrouped:
            show_message("No ungrouped vertices found")
            return {'FINISHED'}

        # Return early if there are no weighted verts to copy from
        if not manager.grouped_vertices:
            show_message("No vertices with weights to copy from")
            return {'CANCELLED'}

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

        show_message(f"Assigned {assigned_count} ungrouped vertices to nearest groups")

    return {'FINISHED'}

class WeightTransferManager:
    """Manages weight transfer """

    def __init__(self, context):
        self.context = context
        self.submesh_pattern = re.compile(r'.*submesh_(\d+)(?:_LOD_(\d+))?(?:\.\d+)?$', re.IGNORECASE)

    def parse_submesh_index(self, name: str) -> Optional[int]:
        """Extracts the submesh index from a name."""
        match = self.submesh_pattern.match(name)
        if match:
            return int(match.group(1))
        return None

    def build_transfer_pairs(self, sources: List[bpy.types.Object], targets: List[bpy.types.Object], by_submesh: bool) -> List[Tuple[List[bpy.types.Object], List[bpy.types.Object]]]:
        """Build source-target pairs for weight transfer."""
       
        if by_submesh:
            return self.pair_by_submesh_index(sources, targets)
        return [(sources, targets)]

    def pair_by_submesh_index(self, sources: List[bpy.types.Object], targets: List[bpy.types.Object]) -> List[Tuple[List[bpy.types.Object], List[bpy.types.Object]]]:
        src_map = {}
        for s in sources:
            idx = self.parse_submesh_index(s.name)
            if idx is not None:
                src_map.setdefault(idx, []).append(s)

        tgt_map = {}
        for t in targets:
            idx = self.parse_submesh_index(t.name)
            if idx is not None:
                tgt_map.setdefault(idx, []).append(t)

        pairs = []
        for idx, target_list in tgt_map.items():
            if idx in src_map:
                pairs.append((src_map[idx], target_list))
            else:
                print(f"Warning: No source found for Target Submesh {idx}")
        return pairs

    def transfer_weights(self, sources: List[bpy.types.Object], targets: List[bpy.types.Object], vert_mapping: str):
        for target in targets:
            valid_sources = [s for s in sources if s != target]
            if not valid_sources:
                continue

            bpy.ops.object.select_all(action='DESELECT')

            target.hide_viewport = False
            target.select_set(True)
            self.context.view_layer.objects.active = target

            for source in valid_sources:
                source.hide_viewport = False
                source.select_set(True)

            target.vertex_groups.clear()

            try:
                bpy.ops.object.data_transfer(
                        use_reverse_transfer=True,
                        use_object_transform=True,
                        vert_mapping=vert_mapping,
                        data_type='VGROUP_WEIGHTS',
                        layers_select_src='NAME',
                        layers_select_dst='ALL',
                        mix_mode='REPLACE',
                        mix_factor=1.0
                        )
            except RuntimeError as e:
                print(f"Transfer failed for {target.name}: {e}")

def trans_weights(operator, context, vertInterop: bool, bySubmesh: bool):
    """
    Does the transfer of weights between meshes.
    """
    props = context.scene.cp77_panel_props

    src_col = bpy.data.collections.get(props.mesh_source)
    tgt_col = bpy.data.collections.get(props.mesh_target)

    if not src_col or not tgt_col:
        operator.report({'ERROR'}, "Source or Target collection not found!")
        return {'CANCELLED'}

    sources = [o for o in src_col.objects if o.type == 'MESH']
    targets = [o for o in tgt_col.objects if o.type == 'MESH']

    if not sources or not targets:
        operator.report({'ERROR'}, "Collections must contain meshes.")
        return {'CANCELLED'}

    if props.mesh_source == props.mesh_target:
        operator.report({'ERROR'}, "Source and Target collections cannot be the same!")
        return {'CANCELLED'}

    store_current_context()

    try:
        safe_mode_switch('OBJECT')

        manager = WeightTransferManager(context)
        mapping_mode = 'NEAREST' if vertInterop else 'POLYINTERP_NEAREST'

        pairs = manager.build_transfer_pairs(sources, targets, by_submesh=bySubmesh)

        if not pairs:
            operator.report({'WARNING'}, "No matching pairs found.")
            return {'CANCELLED'}

        count = 0
        for src_list, tgt_list in pairs:
            manager.transfer_weights(src_list, tgt_list, mapping_mode)
            count += len(tgt_list)

        operator.report({'INFO'}, f"Transferred weights to {count} meshes.")
        return {'FINISHED'}

    except Exception as e:
        operator.report({'ERROR'}, f"Transfer Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'CANCELLED'}

    finally:
        restore_previous_context()
