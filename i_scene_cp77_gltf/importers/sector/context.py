from __future__ import annotations

<<<<<<< Updated upstream
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
=======
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
>>>>>>> Stashed changes

from .model import PlannedSector, SectorNodePlan


class SectorPlacementError(RuntimeError):
    pass


class SectorContentError(SectorPlacementError):
    pass


<<<<<<< Updated upstream
class SectorInvariantError(SectorPlacementError):
    pass


=======
>>>>>>> Stashed changes
class FoliageResourceError(SectorPlacementError):
    pass


class DeformationDataError(SectorPlacementError):
    pass


@dataclass(slots=True, frozen=True)
class SectorPlacementOperations:
<<<<<<< Updated upstream
    place_copied_mesh_instances: Callable[..., list]
    copy_collection_tree_with_placement_root: Callable[..., tuple]
    assign_custom_properties: Callable[..., None]
    assign_id_properties: Callable[..., None]
    instance_matrix: Callable[..., Any]
    instance_scale: Callable[[Any], list]
    matrix_values: Callable[[Any], list]
    animate_rotation_root: Callable[..., None]
    warning: Callable[[str], None]
    safe_json: Callable[[Any], str]
    cname_value: Callable[..., str]
    nested_value: Callable[..., Any]
    depot_path: Callable[..., str]
    new_collection: Callable[[str], Any]
    collection_instance_object: Callable[..., Any]
    trim_name: Callable[..., str]
    copy_object: Callable[..., Any]
    remap_copied_object_references: Callable[..., None]
    new_empty: Callable[..., Any]
    place_world_collision_node: Callable[..., int]
=======
    """What one import's placements share"""

    place_copied_mesh_instances: Callable[..., list]
    copy_collection_tree_with_placement_root: Callable[..., tuple]
    assign_custom_properties: Callable[..., None]
    instance_matrix: Callable[..., Any]
    warning: Callable[[str], None]
>>>>>>> Stashed changes


@dataclass(slots=True)
class SectorPlacementRecord:
    handler_name: str
    expected: int
    actual: int = 0
    error: str = ""

    @property
    def valid(self):
        return not self.error and self.actual == self.expected


@dataclass(slots=True)
class SectorExecutionContext:
    session: Any
    planned_sector: PlannedSector
    sector_collection: Any
    masters_collection: Any
<<<<<<< Updated upstream
    world_transform_buffers: Mapping[str, tuple]
    cooked_transform_buffers: Mapping[str, tuple]
    operations: SectorPlacementOperations
    placement_records: dict[int, SectorPlacementRecord] = field(
        default_factory=dict
    )
    matrix_objects: list[Any] = field(default_factory=list)
    collision_actor_objects: dict[str, Any] = field(default_factory=dict)
=======
    operations: SectorPlacementOperations
    blender_context: Any
    placement_records: dict[tuple[int, int], SectorPlacementRecord] = field(
        default_factory=dict
    )
    matrix_objects: list[Any] = field(default_factory=list)
    source_collection_resolver: Callable[[SectorNodePlan, int | None], Any] | None = (
        None
    )
    generated_collection_resolver: Callable[[str], Any] | None = None
    node_owned_collection_resolver: (
        Callable[[SectorNodePlan, int | None], Any] | None
    ) = None
>>>>>>> Stashed changes

    @property
    def sector_name(self):
        return self.planned_sector.parsed.sector_name

    @property
    def scale_factor(self):
        return self.session.options.scale_factor

<<<<<<< Updated upstream
    def node_context(self, plan):
        return SectorNodeContext(execution=self, plan=plan)

    def record(self, plan, expected, actual=0, error=""):
        self.placement_records[plan.node.index] = SectorPlacementRecord(
            handler_name=plan.handler_name,
            expected=int(expected),
            actual=int(actual),
            error=str(error or ""),
=======
    def record(self, plan, expected, actual=0, error=""):
        self.placement_records[(plan.node.index, plan.node.inner_index)] = (
            SectorPlacementRecord(
                handler_name=plan.handler_name,
                expected=int(expected),
                actual=int(actual),
                error=str(error or ""),
            )
>>>>>>> Stashed changes
        )

    def track_matrix_object(self, obj):
        if obj is not None:
            self.matrix_objects.append(obj)

<<<<<<< Updated upstream
    def validation_issues(self):
        issues = []
        for node_index, record in sorted(self.placement_records.items()):
            if record.error:
                issues.append(
                    f"{self.sector_name}: node {node_index} "
=======
    def source_collection(self, plan, node_data_index=None):
        resolver = self.source_collection_resolver
        if resolver is None:
            return self.sector_collection
        return resolver(plan, node_data_index)

    def node_owned_collection(self, plan, node_data_index=None):
        resolver = self.node_owned_collection_resolver
        if resolver is None:
            return self.source_collection(plan, node_data_index)
        return resolver(plan, node_data_index)

    def generated_collection(self, name):
        resolver = self.generated_collection_resolver
        if resolver is None:
            return self.sector_collection
        return resolver(name)

    def validation_issues(self):
        issues = []
        for (node_index, inner_index), record in sorted(self.placement_records.items()):
            node = (
                f"node {node_index}"
                if inner_index < 0
                else f"node {node_index} inner node {inner_index}"
            )
            if record.error:
                issues.append(
                    f"{self.sector_name}: {node} "
>>>>>>> Stashed changes
                    f"{record.handler_name} failed: {record.error}"
                )
            elif record.actual != record.expected:
                issues.append(
<<<<<<< Updated upstream
                    f"{self.sector_name}: node {node_index} "
=======
                    f"{self.sector_name}: {node} "
>>>>>>> Stashed changes
                    f"{record.handler_name} placed {record.actual} of "
                    f"{record.expected} expected instances"
                )
        return tuple(issues)

<<<<<<< Updated upstream
    def summary(self):
        expected = 0
        actual = 0
        failed = 0
        mismatched = 0
        for record in self.placement_records.values():
            expected += record.expected
            actual += record.actual
            failed += int(bool(record.error))
            mismatched += int(not record.valid)
        return {
            "handlerNodes": len(self.placement_records),
            "expectedPlacements": expected,
            "actualPlacements": actual,
            "failedNodes": failed,
            "mismatchedNodes": mismatched,
        }

=======
>>>>>>> Stashed changes

@dataclass(slots=True, frozen=True)
class SectorNodeContext:
    execution: SectorExecutionContext
    plan: SectorNodePlan

    @property
    def session(self):
        return self.execution.session

    @property
    def node(self):
        return self.plan.node

    @property
    def data(self):
        return self.node.data

    @property
    def node_entry(self):
        return self.node.raw_entry

    @property
    def node_index(self):
        return self.node.index

    @property
    def node_type(self):
        return self.node.node_type

    @property
    def instances(self):
<<<<<<< Updated upstream
        return self.node.raw_instances
=======
        return self.node.instances
>>>>>>> Stashed changes

    @property
    def sector_name(self):
        return self.execution.sector_name

    @property
    def sector_collection(self):
        return self.execution.sector_collection

    @property
    def masters(self):
        return self.execution.masters_collection

<<<<<<< Updated upstream
=======
    def collection_for_node_data(self, node_data_index=None):
        return self.execution.source_collection(self.plan, node_data_index)

    def node_owned_collection(self, node_data_index=None):
        """Collection dedicated to this node, for handlers that store node metadata on it"""
        return self.execution.node_owned_collection(self.plan, node_data_index)

    def collection_for_instance(self, instance=None):
        return self.collection_for_node_data(
            None if instance is None else instance.index
        )

>>>>>>> Stashed changes
    @property
    def operations(self):
        return self.execution.operations

    @property
<<<<<<< Updated upstream
    def world_transform_buffers(self):
        return self.execution.world_transform_buffers

    @property
    def cooked_transform_buffers(self):
        return self.execution.cooked_transform_buffers
=======
    def blender_context(self):
        return self.execution.blender_context
>>>>>>> Stashed changes

    @property
    def transform_buffers(self):
        return self.session.transform_buffers

    @property
    def foliage_assets(self):
        return self.session.foliage_assets

    @property
    def deformation_assets(self):
        return self.session.deformation_assets

    @property
    def world_metadata_assets(self):
        return self.session.world_metadata_assets

    @property
    def decal_assets(self):
        return self.session.decal_assets

    @property
    def lighting_assets(self):
        return self.session.lighting_assets

    @property
    def probe_assets(self):
        return self.session.probe_assets

    @property
    def effect_assets(self):
        return self.session.effect_assets

    @property
    def acoustic_assets(self):
        return self.session.acoustic_assets

    @property
    def minimap_assets(self):
        return self.session.minimap_assets

    @property
    def semantic_assets(self):
        return self.session.semantic_assets

    @property
    def spline_assets(self):
        return self.session.spline_assets

    @property
    def gi_assets(self):
        return self.session.gi_assets

    @property
<<<<<<< Updated upstream
    def collision_metadata_assets(self):
        return self.session.collision_metadata_assets

    def record_placements(self, actual, expected=None):
        if expected is None:
            expected = len(self.node.raw_instances)
=======
    def physx_collision_assets(self):
        return self.session.physx_collision_assets

    def record_placements(self, actual, expected=None):
        if expected is None:
            expected = len(self.node.instances)
>>>>>>> Stashed changes
        self.execution.record(
            self.plan,
            expected=expected,
            actual=actual,
        )

    def record_error(self, error, expected=None):
        if expected is None:
<<<<<<< Updated upstream
            expected = len(self.node.raw_instances)
=======
            expected = len(self.node.instances)
>>>>>>> Stashed changes
        self.execution.record(
            self.plan,
            expected=expected,
            actual=0,
            error=str(error),
        )
