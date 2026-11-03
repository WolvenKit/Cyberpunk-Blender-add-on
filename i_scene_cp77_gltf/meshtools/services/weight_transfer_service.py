import re
<<<<<<< Updated upstream
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
=======

import bpy

from ...blender.context import (
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh_source import mesh_source, set_base_mesh
from ...blender.operator_results import OperationResult, require_finished
from ...blender.selection import select_objects
from ...blender.vertex_groups import capture_vertex_groups, restore_vertex_groups
from ...core.log import get_logger

_LOG = get_logger(__name__)


class WeightTransferManager:
    """Manages weight transfer"""

    def __init__(self, context):
        self.context = context
        self.submesh_pattern = re.compile(
            r".*submesh_(\d+)(?:_LOD_(\d+))?(?:\.\d+)?$", re.IGNORECASE
        )

    def parse_submesh_index(self, name: str) -> int | None:
        """Extracts the submesh index from a name"""
>>>>>>> Stashed changes
        match = self.submesh_pattern.match(name)
        if match:
            return int(match.group(1))
        return None

    def build_transfer_pairs(
<<<<<<< Updated upstream
            self, sources: List[bpy.types.Object], targets: List[bpy.types.Object], by_submesh: bool,
            ) -> List[Tuple[List[bpy.types.Object], List[bpy.types.Object]]]:
        """Build source-target pairs for weight transfer."""
=======
        self,
        sources: list[bpy.types.Object],
        targets: list[bpy.types.Object],
        by_submesh: bool,
    ) -> list[tuple[list[bpy.types.Object], list[bpy.types.Object]]]:
        """Build source-target pairs for weight transfer"""
>>>>>>> Stashed changes

        if by_submesh:
            return self.pair_by_submesh_index(sources, targets)
        return [(sources, targets)]

<<<<<<< Updated upstream
    def pair_by_submesh_index(self, sources: List[bpy.types.Object], targets: List[bpy.types.Object]) -> List[
        Tuple[List[bpy.types.Object], List[bpy.types.Object]]]:
=======
    def pair_by_submesh_index(
        self, sources: list[bpy.types.Object], targets: list[bpy.types.Object]
    ) -> list[tuple[list[bpy.types.Object], list[bpy.types.Object]]]:
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
                _LOG.warning(
                    "No weight-transfer source found for target submesh %s", idx
                )
        return pairs

    @staticmethod
    def _record_base_mesh(target, sources):
        """A mesh with no game source takes the mesh its weights came from as its base for export"""
        if mesh_source(target) is not None:
            return
        source = next(
            (found for found in map(mesh_source, sources) if found is not None), None
        )
        if source is not None:
            set_base_mesh(target, source.depot_path)

    def _joined_source(self, sources: list[bpy.types.Object]) -> bpy.types.Object:
        """A temporary object joining the sources as evaluated, vertex groups merged by name"""
        depsgraph = self.context.evaluated_depsgraph_get()
        parts, meshes = [], []
        joined = None
        try:
            for source in sources:
                mesh = bpy.data.meshes.new_from_object(
                    source.evaluated_get(depsgraph),
                    preserve_all_data_layers=True,
                    depsgraph=depsgraph,
                )
                meshes.append(mesh)
                part = bpy.data.objects.new(f"CP77_WeightSource_{source.name}", mesh)
                part.matrix_world = source.matrix_world
                self.context.scene.collection.objects.link(part)
                parts.append(part)
            select_objects(parts, context=self.context)
            require_finished(bpy.ops.object.join(), "Joining the weight sources")
            joined = self.context.view_layer.objects.active
            return joined
        except Exception:
            for part in parts:
                _remove_temporary(part)
            raise
        finally:
            # The join removes the other parts and leaves their meshes without users.
            for mesh in meshes:
                try:
                    if (joined is None or mesh != joined.data) and mesh.users == 0:
                        bpy.data.meshes.remove(mesh)
                except ReferenceError:
                    pass

    def transfer_weights(
        self,
        sources: list[bpy.types.Object],
        targets: list[bpy.types.Object],
        vert_mapping: str,
    ):
        transferred = 0
        failures = []
        joined = {}
        try:
            for target in targets:
                valid_sources = [s for s in sources if s != target]
                if not valid_sources:
                    continue
                # A source that shares the target's mesh holds the weights the target is cleared of.
                sharing = [s.name for s in valid_sources if s.data == target.data]
                if sharing:
                    failures.append(
                        f"{target.name}: shares its mesh with source {', '.join(sharing)}; make it "
                        "single user (Object > Relations > Make Single User > Object & Data) first"
                    )
                    continue
                source = valid_sources[0]
                if len(valid_sources) > 1:
                    key = tuple(item.as_pointer() for item in valid_sources)
                    if key not in joined:
                        joined[key] = self._joined_source(valid_sources)
                    source = joined[key]

                refusal = _source_refusal(source, vert_mapping)
                if refusal:
                    failures.append(f"{target.name}: {refusal}")
                    continue

                select_objects(
                    [target, source],
                    context=self.context,
                    reveal=True,
                )

                # The target gets its own weights back when the transfer fails.
                snapshot = capture_vertex_groups(target)
                target.vertex_groups.clear()

                try:
                    result = bpy.ops.object.data_transfer(
                        use_reverse_transfer=True,
                        use_object_transform=True,
                        vert_mapping=vert_mapping,
                        data_type="VGROUP_WEIGHTS",
                        layers_select_src="NAME",
                        layers_select_dst="ALL",
                        mix_mode="REPLACE",
                        mix_factor=1.0,
                    )
                    if "FINISHED" not in result:
                        restore_vertex_groups(target, snapshot)
                        failures.append(
                            f"{target.name}: Blender cancelled the weight transfer"
                        )
                        continue
                    transferred += 1
                    self._record_base_mesh(target, valid_sources)
                except RuntimeError as error:
                    restore_vertex_groups(target, snapshot)
                    _LOG.warning(
                        "Weight transfer failed for target: object=%s error=%s",
                        target.name,
                        error,
                        exc_info=True,
                    )
                    failures.append(f"{target.name}: {error}")
        finally:
            for source in joined.values():
                _remove_temporary(source)
        return transferred, failures


def _source_refusal(source, vert_mapping: str) -> str:
    """Why source cannot give weights with vert_mapping, or empty when it can"""
    if not source.vertex_groups:
        return f"{source.name} has no vertex groups to transfer"
    if vert_mapping.startswith("POLY") and not source.data.polygons:
        return f"{source.name} has no faces to interpolate weights from"
    return ""


def _remove_temporary(obj):
    try:
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
    except ReferenceError:
        return
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
>>>>>>> Stashed changes


def transfer_weights(context, vert_interop: bool, by_submesh: bool):
    """
<<<<<<< Updated upstream
    Does the transfer of weights between meshes.
=======
    Does the transfer of weights between meshes
>>>>>>> Stashed changes
    """
    props = context.scene.cp77_panel_props

    src_col = bpy.data.collections.get(props.mesh_source)
    tgt_col = bpy.data.collections.get(props.mesh_target)

    if not src_col or not tgt_col:
<<<<<<< Updated upstream
        return MeshToolResult.failure("Source or target collection not found.")

    sources = [o for o in src_col.objects if o.type == 'MESH']
    targets = [o for o in tgt_col.objects if o.type == 'MESH']

    if not sources or not targets:
        return MeshToolResult.failure("Collections must contain meshes.")

    if props.mesh_source == props.mesh_target:
        return MeshToolResult.failure("Source and target collections cannot be the same.")
=======
        return OperationResult.cancelled("Source or target collection not found.")

    sources = [o for o in src_col.objects if o.type == "MESH"]
    targets = [o for o in tgt_col.objects if o.type == "MESH"]

    if not sources or not targets:
        return OperationResult.cancelled("Collections must contain meshes.")

    if props.mesh_source == props.mesh_target:
        return OperationResult.cancelled(
            "Source and target collections cannot be the same."
        )
>>>>>>> Stashed changes

    store_current_context()

    try:
<<<<<<< Updated upstream
        safe_mode_switch('OBJECT')

        manager = WeightTransferManager(context)
        mapping_mode = 'NEAREST' if vert_interop else 'POLYINTERP_NEAREST'
=======
        safe_mode_switch("OBJECT")

        manager = WeightTransferManager(context)
        mapping_mode = "NEAREST" if vert_interop else "POLYINTERP_NEAREST"
>>>>>>> Stashed changes

        pairs = manager.build_transfer_pairs(sources, targets, by_submesh=by_submesh)

        if not pairs:
<<<<<<< Updated upstream
            return MeshToolResult.failure("No matching source/target pairs found.")

        count = 0
        for src_list, tgt_list in pairs:
            manager.transfer_weights(src_list, tgt_list, mapping_mode)
            count += len(tgt_list)

        return MeshToolResult.success(f"Transferred weights to {count} meshes.", payload=count)

    except Exception as e:
        return MeshToolResult.failure(f"Weight transfer failed: {e}")
=======
            return OperationResult.cancelled("No matching source/target pairs found.")

        count = 0
        failures = []
        for src_list, tgt_list in pairs:
            transferred, pair_failures = manager.transfer_weights(
                src_list, tgt_list, mapping_mode
            )
            count += transferred
            failures.extend(pair_failures)

        if count == 0:
            return OperationResult.cancelled(
                "Weight transfer failed: " + "; ".join(failures)
            )
        result = OperationResult.finished(
            f"Transferred weights to {count} meshes.", payload=count
        )
        if failures:
            return OperationResult.finished(
                result.message, level="WARNING", warnings=failures, payload=count
            )
        return result

    except Exception as e:
        return OperationResult.cancelled(f"Weight transfer failed: {e}", error=e)
>>>>>>> Stashed changes

    finally:
        restore_previous_context()
