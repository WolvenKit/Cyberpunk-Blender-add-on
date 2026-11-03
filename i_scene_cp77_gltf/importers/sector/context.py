from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .model import PlannedSector, SectorNodePlan


class SectorPlacementError(RuntimeError):
    pass


class SectorContentError(SectorPlacementError):
    pass


class FoliageResourceError(SectorPlacementError):
    pass


class DeformationDataError(SectorPlacementError):
    pass


@dataclass(slots=True, frozen=True)
class SectorPlacementOperations:
    """What one import's placements share"""

    place_copied_mesh_instances: Callable[..., list]
    copy_collection_tree_with_placement_root: Callable[..., tuple]
    assign_custom_properties: Callable[..., None]
    instance_matrix: Callable[..., Any]
    warning: Callable[[str], None]


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

    @property
    def sector_name(self):
        return self.planned_sector.parsed.sector_name

    @property
    def scale_factor(self):
        return self.session.options.scale_factor

    def record(self, plan, expected, actual=0, error=""):
        self.placement_records[(plan.node.index, plan.node.inner_index)] = (
            SectorPlacementRecord(
                handler_name=plan.handler_name,
                expected=int(expected),
                actual=int(actual),
                error=str(error or ""),
            )
        )

    def track_matrix_object(self, obj):
        if obj is not None:
            self.matrix_objects.append(obj)

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
                    f"{record.handler_name} failed: {record.error}"
                )
            elif record.actual != record.expected:
                issues.append(
                    f"{self.sector_name}: {node} "
                    f"{record.handler_name} placed {record.actual} of "
                    f"{record.expected} expected instances"
                )
        return tuple(issues)


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
        return self.node.instances

    @property
    def sector_name(self):
        return self.execution.sector_name

    @property
    def sector_collection(self):
        return self.execution.sector_collection

    @property
    def masters(self):
        return self.execution.masters_collection

    def collection_for_node_data(self, node_data_index=None):
        return self.execution.source_collection(self.plan, node_data_index)

    def node_owned_collection(self, node_data_index=None):
        """Collection dedicated to this node, for handlers that store node metadata on it"""
        return self.execution.node_owned_collection(self.plan, node_data_index)

    def collection_for_instance(self, instance=None):
        return self.collection_for_node_data(
            None if instance is None else instance.index
        )

    @property
    def operations(self):
        return self.execution.operations

    @property
    def blender_context(self):
        return self.execution.blender_context

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
    def physx_collision_assets(self):
        return self.session.physx_collision_assets

    def record_placements(self, actual, expected=None):
        if expected is None:
            expected = len(self.node.instances)
        self.execution.record(
            self.plan,
            expected=expected,
            actual=actual,
        )

    def record_error(self, error, expected=None):
        if expected is None:
            expected = len(self.node.instances)
        self.execution.record(
            self.plan,
            expected=expected,
            actual=0,
            error=str(error),
        )
