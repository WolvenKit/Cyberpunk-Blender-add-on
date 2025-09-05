from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class MaterialOverride:
    material_path: str
    override_data: Dict = field(default_factory=dict)


@dataclass
class MeshReference:
    mesh_path: str
    mesh_appearance: Optional[str] = None
    material_overrides: List[MaterialOverride] = field(default_factory=list)


@dataclass
class AppearanceComponent:
    name: str
    type: str
    mesh: Optional[MeshReference] = None
    transform: Optional[Dict[str, List[float]]] = None  # {'position': [...], 'orientation': [...], 'scale': [...]}
    parent_transform_ref_id: Optional[int] = None
    parent_transform_data: Optional[Dict] = None
    extra_data: Dict = field(default_factory=dict)


@dataclass
class AppearanceData:
    name: str
    components: List[AppearanceComponent]


@dataclass
class EntityComponent:
    name: str
    type: str
    mesh_path: Optional[str] = None
    graphics_mesh_path: Optional[str] = None
    mesh_appearance: Optional[str] = None
    transform: Optional[Dict[str, List[float]]] = None
    parent_transform_ref_id: Optional[int] = None
    parent_transform_data: Optional[Dict] = None
    extra_data: Dict = field(default_factory=dict)


@dataclass
class ResolvedDependency:
    path: str


@dataclass
class EntityData:
    name: str
    default_appearance: Optional[str]
    global_components: List[EntityComponent] = field(default_factory=list)
    appearances: List[AppearanceData] = field(default_factory=list)
    resolved_dependencies: List[ResolvedDependency] = field(default_factory=list)

@dataclass
class RigData:
    rig_name: str
    disable_connect: bool
    apose_ms: List[Any]
    apose_ls: List[Any]
    bone_transforms: List[Any]
    bone_parents: List[int]
    bone_names: List[str]
    parts: List[Any]
    track_names: List[Any]
    reference_tracks: List[Any]
    cooking_platform: str
    distance_category_to_lod_map: List[Any]
    ik_setups: List[Any]
    level_of_detail_start_indices: List[Any]
    ragdoll_desc: List[Any]
    ragdoll_names: List[Any]