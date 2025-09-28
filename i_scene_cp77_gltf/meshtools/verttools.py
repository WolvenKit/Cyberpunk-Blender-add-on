import bpy
import math
import re
from typing import List, Tuple, Optional, Dict
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
    """Manages weight transfer operations between meshes."""
    
    def __init__(self, context):
        self.context = context
        self.submesh_pattern = re.compile(r'^submesh_(\d+)(?:_LOD_(\d+))?$', re.IGNORECASE)
    
    def parse_submesh_name(self, name: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse submesh name for index and LOD."""
        match = self.submesh_pattern.match(name)
        if not match:
            return None, None
        
        idx = int(match.group(1))
        lod = int(match.group(2)) if match.group(2) else None
        return idx, lod
    
    def build_transfer_pairs(self, sources: List, targets: List) -> List[Tuple]:
        """Build source-target pairs for weight transfer."""
        pairs = []
        
        # Special case: single source to many targets
        if len(sources) == 1 and len(targets) >= 1:
            return [(sources[0], targets)]
        
        # Special case: many sources to single target
        if len(targets) == 1 and len(sources) >= 1:
            return [(s, [targets[0]]) for s in sources]
        
        # Check if all are submeshes
        src_all_submesh = all(self.parse_submesh_name(o.name)[0] is not None for o in sources)
        tgt_all_submesh = all(self.parse_submesh_name(o.name)[0] is not None for o in targets)
        
        if src_all_submesh and tgt_all_submesh:
            # Pair by submesh index
            pairs = self.pair_by_submesh_index(sources, targets)
        else:
            # Simple ordered pairing
            pairs = [(s, [t]) for s, t in zip(sources, targets)]
        
        return pairs
    
    def pair_by_submesh_index(self, sources: List, targets: List) -> List[Tuple]:
        """Pair meshes by submesh index."""
        # Build index maps
        src_by_idx = {}
        for s in sources:
            idx, _ = self.parse_submesh_name(s.name)
            if idx is not None and idx not in src_by_idx:
                src_by_idx[idx] = s
        
        tgt_by_idx = {}
        for t in targets:
            idx, _ = self.parse_submesh_name(t.name)
            if idx is not None:
                tgt_by_idx.setdefault(idx, []).append(t)
        
        # Create pairs
        pairs = []
        for idx in sorted(tgt_by_idx.keys()):
            if idx in src_by_idx:
                pairs.append((src_by_idx[idx], tgt_by_idx[idx]))
        
        return pairs
    
    def transfer_weights(self, source, targets, vert_mapping='NEAREST'):
        """Execute weight transfer"""
        # Deselect all first
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select targets and clear existing weights
        for t in targets:
            t.select_set(True)
            t.vertex_groups.clear()
        
        # Set source as active and select it
        select_object(source)
        source.select_set(True)  # Also add to selection for the transfer
        
        # Transfer weights
        bpy.ops.object.data_transfer(
            use_reverse_transfer=False,
            use_object_transform=True,
            vert_mapping=vert_mapping,
            data_type='VGROUP_WEIGHTS',
            layers_select_src='ALL',
            layers_select_dst='NAME',
            mix_mode='REPLACE',
            mix_factor=1.0
        )

def trans_weights(self, context, vertInterop):
    """Transfer vertex weights between collections"""
    props = context.scene.cp77_panel_props
    
    # Get collections
    src_col = bpy.data.collections.get(props.mesh_source)
    tgt_col = bpy.data.collections.get(props.mesh_target)
    
    if not src_col or not tgt_col:
        show_message("Source and target collections must be specified")
        return {'CANCELLED'}
    
    # Get meshes
    sources = [o for o in src_col.objects if is_mesh(o)]
    targets = [o for o in tgt_col.objects if is_mesh(o)]
    
    if not sources or not targets:
        show_message("Both collections must contain at least one mesh")
        return {'CANCELLED'}
    
    # Store current context
    store_current_context()
    
    try:
        # Switch to object mode for transfer
        safe_mode_switch('OBJECT')
        
        # Setup transfer
        manager = WeightTransferManager(context)
        vert_mapping = 'POLYINTERP_NEAREST' if vertInterop else 'NEAREST'
        
        # Build pairs
        pairs = manager.build_transfer_pairs(sources, targets)
        
        # Execute transfers
        passes = 0
        errors = []
        
        for source, target_list in pairs:
            try:
                manager.transfer_weights(source, target_list, vert_mapping)
                passes += 1
            except Exception as e:
                errors.append(f"{source.name}: {str(e)}")
        
        # Report results
        if errors:
            show_message(f"Transferred weights ({passes} passes). Errors: {'; '.join(errors[:3])}")
        else:
            msg = f"Successfully transferred weights across {passes} pass(es)"
            if len(pairs) > 1:
                msg += f" using {'submesh pairing' if any('submesh' in p[0].name for p in pairs) else 'ordered pairing'}"
            show_message(msg)
    
    finally:
        # Restore context
        restore_previous_context()
    
    return {'FINISHED'}