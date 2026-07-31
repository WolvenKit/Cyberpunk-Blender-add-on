from __future__ import annotations

from dataclasses import dataclass
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
class SectorNode:
    index: int
    handle_id: str
    node_type: str
    data: dict[str, Any]
    raw_entry: dict[str, Any]
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
    indexed_node_data: tuple[dict[str, Any], ...]
    nodes: tuple[SectorNode, ...]
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

    def placement_plans(self):
        return self.ordered_placement_plans
