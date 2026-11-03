from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParsedEntity:
    appearances: tuple
    appearance_names: tuple
    appearances_by_appearance: object
    appearances_by_name: object
    default_appearance: str
    component_dicts: tuple
    component_data: tuple
    all_components: tuple
    components_by_name: object
    all_components_by_name: object
    components_by_id: object
    slot_components: tuple
    component_ids: frozenset
    component_data_ids: frozenset
    parent_transform_lookup: object
    skinning_lookup: object
    shape_lookup: object
    slot_component_lookups: object
    collider_components: tuple
    simple_collider_components: tuple
    light_channel_components: tuple
    resolved_dependencies: tuple
    vehicle_slot_component: dict | None


@dataclass(frozen=True, slots=True)
class AppearanceRequestResolution:
    appearances: tuple[str, ...]
    default_appearance: str
    appearance_indices: tuple[int | None, ...]
    messages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EntityMeshRequirement:
    key: str
    depot_path: str
    mesh_name: str
    mesh_path: str
    appearances: tuple[str, ...]
    sector: str = "ALL"


@dataclass(frozen=True, slots=True)
class EntityAppearancePlan:
    requested_name: str
    display_name: str
    resolved_name: str
    entity_appearance_index: int | None
    app_resource_depot: str
    app_resource_path: str
    parsed_app: Any | None
    parsed_app_name: str
    root_components: tuple[dict, ...]
    appearance_components: tuple[dict, ...]
    merged_components: tuple[dict, ...]
    component_index: Any
    chunks: tuple[dict, ...]
    used_root_fallback: bool


@dataclass(frozen=True, slots=True)
class EntityRigComponentPlan:
    component: dict
    component_name: str
    rig_depot_path: str
    control_target: str
    is_deformation_rig: bool


@dataclass(frozen=True, slots=True)
class EntityRigPlan:
    components: tuple[EntityRigComponentPlan, ...]
    deformation_authorities: tuple[str, ...]
    base_components: tuple[EntityRigComponentPlan, ...] = ()
    overlay_components: tuple[EntityRigComponentPlan, ...] = ()

    @property
    def ordered_components(self) -> tuple[dict, ...]:
        return tuple(item.component for item in self.components)

    @property
    def ordered_base_components(self) -> tuple[dict, ...]:
        return tuple(item.component for item in self.base_components)

    @property
    def ordered_overlay_components(self) -> tuple[dict, ...]:
        return tuple(item.component for item in self.overlay_components)


@dataclass(frozen=True, slots=True)
class EntityImportPlan:
    appearances: tuple[str, ...]
    default_appearance: str
    appearance_plans: tuple[EntityAppearancePlan, ...]
    mesh_requirements: tuple[EntityMeshRequirement, ...]
    rig: EntityRigPlan
    warnings: tuple[str, ...]
    messages: tuple[str, ...] = field(default_factory=tuple)
