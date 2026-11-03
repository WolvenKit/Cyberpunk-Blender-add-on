from __future__ import annotations

from dataclasses import dataclass, field
<<<<<<< Updated upstream
from typing import Any, Mapping
=======
from typing import Any
>>>>>>> Stashed changes


@dataclass(frozen=True, slots=True)
class ParsedEntity:
    appearances: tuple
    appearance_names: tuple
<<<<<<< Updated upstream
    appearance_index_by_name: object
=======
>>>>>>> Stashed changes
    appearances_by_appearance: object
    appearances_by_name: object
    default_appearance: str
    component_dicts: tuple
    component_data: tuple
<<<<<<< Updated upstream
    components_by_name: object
    components_by_id: object
=======
    all_components: tuple
    components_by_name: object
    all_components_by_name: object
    components_by_id: object
    slot_components: tuple
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
    appearance_indices: tuple[int | None, ...]
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
    component_index: Any
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
    base_components: tuple[EntityRigComponentPlan, ...] = ()
    overlay_components: tuple[EntityRigComponentPlan, ...] = ()
>>>>>>> Stashed changes

    @property
    def ordered_components(self) -> tuple[dict, ...]:
        return tuple(item.component for item in self.components)

    @property
<<<<<<< Updated upstream
    def control_targets_by_identity(self) -> Mapping[int, str]:
        return {id(item.component): item.control_target for item in self.components}
=======
    def ordered_base_components(self) -> tuple[dict, ...]:
        return tuple(item.component for item in self.base_components)

    @property
    def ordered_overlay_components(self) -> tuple[dict, ...]:
        return tuple(item.component for item in self.overlay_components)
>>>>>>> Stashed changes


@dataclass(frozen=True, slots=True)
class EntityImportPlan:
    appearances: tuple[str, ...]
    default_appearance: str
    appearance_plans: tuple[EntityAppearancePlan, ...]
    mesh_requirements: tuple[EntityMeshRequirement, ...]
    rig: EntityRigPlan
<<<<<<< Updated upstream
=======
    warnings: tuple[str, ...]
>>>>>>> Stashed changes
    messages: tuple[str, ...] = field(default_factory=tuple)
