from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ...assetio.streaming_sector import NodeInstance

# The order in which planned nodes are placed: proxies after the content they stand for.
STANDARD_PHASE = 20
PROXY_PHASE = 30


class NodeCategory(str, Enum):
    STANDARD = "standard"
    LIGHT = "lights"
    FOLIAGE = "foliage"
    EFFECT = "effects"
    COLLISION = "collisions"
    PROXY = "proxies"
    FOG = "fog"
    GAMEPLAY = "gameplay"
    AUDIO = "audio"


@dataclass(slots=True, frozen=True)
class SectorResourceRef:
    depot_path: str
    normalized_path: str
    resource_kind: str


@dataclass(slots=True, frozen=True)
class SectorNode:
    """One node to place"""

    index: int
    handle_id: str
    node_type: str
    source_node_type: str
    inner_index: int
    data: dict[str, Any]
    raw_entry: dict[str, Any]
    instances: tuple[NodeInstance, ...]
    category: NodeCategory
    mesh_path: str = ""
    mesh_appearance: str = "default"
    entity_template_path: str = ""
    entity_appearance: str = "default"
    foliage_resource_path: str = ""
    resource_refs: tuple[SectorResourceRef, ...] = ()


@dataclass(slots=True, frozen=True)
class ParsedSector:
    """A sector as the import reads it"""

    source_path: str
    sector_name: str
    node_data_count: int
    instances: tuple[NodeInstance, ...]
    nodes: tuple[SectorNode, ...]
    skipped_node_data: tuple[int, ...] = ()
    skipped_instances: tuple[tuple[int, int], ...] = ()
    category: Any = ""
    variant_indices: tuple[int, ...] = ()
    variant_nodes: tuple[Any, ...] = ()
    # The sector's ``externInplaceResource``, as the document holds it: the inplace resource that holds the resources
    # of the node data entries that name one in ``externalInplaceResourceHash``.
    extern_inplace_resource: Any = None
    # The resources the sector holds embedded (its ``localInplaceResource``), as local path fragments.
    local_inplace_paths: tuple[str, ...] = ()
    parent_sector: str = ""
    parent_sector_path: str = ""
    composition_parent_paths: tuple[str, ...] = ()
    composition_issues: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class PlacedContent:
    """What an earlier import left of a sector in the scene"""

    node_data: frozenset[int] = frozenset()
    recorded_nodes: frozenset[int] = frozenset()
    entryless_nodes: frozenset[int] = frozenset()


@dataclass(slots=True, frozen=True)
class ImportDependency:
    kind: str
    depot_path: str
    appearance: Any = "default"
    source_sector: str = ""
    source_node_index: int = -1
    placement_phase: int = STANDARD_PHASE


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
    mesh_dependencies: tuple[ImportDependency, ...] = ()
