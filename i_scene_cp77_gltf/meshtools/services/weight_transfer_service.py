import re
from typing import List, Optional, Tuple

import bpy

from ...blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ..model import MeshToolResult


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

    def build_transfer_pairs(
            self, sources: List[bpy.types.Object], targets: List[bpy.types.Object], by_submesh: bool,
            ) -> List[Tuple[List[bpy.types.Object], List[bpy.types.Object]]]:
        """Build source-target pairs for weight transfer."""

        if by_submesh:
            return self.pair_by_submesh_index(sources, targets)
        return [(sources, targets)]

    def pair_by_submesh_index(self, sources: List[bpy.types.Object], targets: List[bpy.types.Object]) -> List[
        Tuple[List[bpy.types.Object], List[bpy.types.Object]]]:
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


def transfer_weights(context, vert_interop: bool, by_submesh: bool):
    """
    Does the transfer of weights between meshes.
    """
    props = context.scene.cp77_panel_props

    src_col = bpy.data.collections.get(props.mesh_source)
    tgt_col = bpy.data.collections.get(props.mesh_target)

    if not src_col or not tgt_col:
        return MeshToolResult.failure("Source or target collection not found.")

    sources = [o for o in src_col.objects if o.type == 'MESH']
    targets = [o for o in tgt_col.objects if o.type == 'MESH']

    if not sources or not targets:
        return MeshToolResult.failure("Collections must contain meshes.")

    if props.mesh_source == props.mesh_target:
        return MeshToolResult.failure("Source and target collections cannot be the same.")

    store_current_context()

    try:
        safe_mode_switch('OBJECT')

        manager = WeightTransferManager(context)
        mapping_mode = 'NEAREST' if vert_interop else 'POLYINTERP_NEAREST'

        pairs = manager.build_transfer_pairs(sources, targets, by_submesh=by_submesh)

        if not pairs:
            return MeshToolResult.failure("No matching source/target pairs found.")

        count = 0
        for src_list, tgt_list in pairs:
            manager.transfer_weights(src_list, tgt_list, mapping_mode)
            count += len(tgt_list)

        return MeshToolResult.success(f"Transferred weights to {count} meshes.", payload=count)

    except Exception as e:
        return MeshToolResult.failure(f"Weight transfer failed: {e}")

    finally:
        restore_previous_context()
