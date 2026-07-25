from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class NodeCategory(str, Enum):
    STANDARD = "standard"
    LIGHT = "lights"
    FOLIAGE = "foliage"
    EFFECT = "effects"
    COLLISION = "collisions"
    PROXY = "proxies"
    ACOUSTIC = "acoustics"
    OCCLUDER = "occluders"
    MINIMAP = "minimap"
    ENVIRONMENT_PROBE = "environment_probes"
    WORLD_METADATA = "world_metadata"
    GI = "gi"


@dataclass(slots=True, frozen=True)
class SectorResourceRef:
    depot_path: str
    normalized_path: str
    resource_kind: str


@dataclass(slots=True, frozen=True)
class SectorInstance:
    node_data_index: int
    node_index: int | None
    raw: dict[str, Any]


@dataclass(slots=True, frozen=True)
class SectorNode:
    index: int
    handle_id: str
    node_type: str
    data: dict[str, Any]
    raw_entry: dict[str, Any]
    instances: tuple[SectorInstance, ...]
    raw_instances: tuple[dict[str, Any], ...]
    category: NodeCategory
    mesh_path: str = ""
    mesh_appearance: str = "default"
    entity_template_path: str = ""
    entity_appearance: str = "default"
    foliage_resource_path: str = ""
    resource_refs: tuple[SectorResourceRef, ...] = ()


@dataclass(slots=True, frozen=True)
class ParsedSector:
    source_path: str
    sector_name: str
    node_data: tuple[dict[str, Any], ...]
    indexed_node_data: tuple[dict[str, Any], ...]
    raw_nodes: tuple[dict[str, Any], ...]
    nodes: tuple[SectorNode, ...]
    instances_by_node: Mapping[int | None, tuple[dict[str, Any], ...]]
    nodes_by_handle: Mapping[str, dict[str, Any]]
    world_transform_buffers: Mapping[str, tuple[dict[str, Any], ...]]
    cooked_transform_buffers: Mapping[str, tuple[dict[str, Any], ...]]
    category: Any = ""
    level: int = 0
    variant_indices: tuple[int, ...] = ()
    variant_nodes: tuple[Any, ...] = ()
    inplace_depot_paths: tuple[str, ...] = ()
    parent_sector: str = ""
    parent_sector_path: str = ""
    composition_parents: tuple[str, ...] = ()
    composition_parent_paths: tuple[str, ...] = ()
    composition_depth: int = 0
    source_kind: str = "root"
    source_depot_path: str = ""
    composition_issues: tuple[str, ...] = ()
    resolved_inplace_paths: tuple[str, ...] = ()

    def legacy_jsonload(self):
        return list(self.node_data), list(self.raw_nodes)

    def legacy_entry(self):
        return {
            "filepath": self.source_path,
            "sectorName": self.sector_name,
            "nodeData": list(self.indexed_node_data),
            "nodes": list(self.raw_nodes),
            "instances_by_node": {
                key: list(value)
                for key, value in self.instances_by_node.items()
            },
            "nodes_by_handle": dict(self.nodes_by_handle),
            "world_transform_buffers": {
                key: list(value)
                for key, value in self.world_transform_buffers.items()
            },
            "cooked_transform_buffers": {
                key: list(value)
                for key, value in self.cooked_transform_buffers.items()
            },
            "category": self.category,
            "level": self.level,
            "variantIndices": list(self.variant_indices),
            "variantNodes": list(self.variant_nodes),
            "inplaceDepotPaths": list(self.inplace_depot_paths),
            "parentSector": self.parent_sector,
            "parentSectorPath": self.parent_sector_path,
            "compositionParents": list(self.composition_parents),
            "compositionParentPaths": list(self.composition_parent_paths),
            "compositionDepth": self.composition_depth,
            "sourceKind": self.source_kind,
            "sourceDepotPath": self.source_depot_path,
            "compositionIssues": list(self.composition_issues),
            "resolvedInplacePaths": list(self.resolved_inplace_paths),
        }


@dataclass(slots=True, frozen=True)
class ImportDependency:
    kind: str
    depot_path: str
    appearance: Any = "default"
    source_sector: str = ""
    source_node_index: int = -1
    placement_phase: int = 20


@dataclass(slots=True, frozen=True)
class SectorNodePlan:
    node: SectorNode
    enabled: bool
    skip_reason: str
    placement_phase: int
    handler_name: str
    dependencies: tuple[ImportDependency, ...] = ()


@dataclass(slots=True, frozen=True)
class PlannedSector:
    parsed: ParsedSector
    plans: tuple[SectorNodePlan, ...]
    ordered_placement_plans: tuple[SectorNodePlan, ...]
    active_node_indexes: frozenset[int]
    skipped_by_reason: Mapping[str, int] = field(default_factory=dict)

    def placement_plans(self):
        return self.ordered_placement_plans

    def legacy_entry(self):
        entry = self.parsed.legacy_entry()
        entry["activeNodeIndexes"] = self.active_node_indexes
        entry["nodePlans"] = self.plans
        entry["skippedNodeCounts"] = dict(self.skipped_by_reason)
        entry["parsedSector"] = self.parsed
        return entry
