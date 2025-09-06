from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

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

@dataclass(slots=True)
class RigData:
    num_bones: int
    parent_indices: np.ndarray # shape [N], dtype np.int16 canonical
    bone_names: List[str]
    track_names: List[str]
    ls_q: np.ndarray # [N,4]
    ls_t: np.ndarray # [N,3]
    ls_s: np.ndarray # [N,3]
    rig_name: str = ""
    disable_connect: bool = False
    apose_ms: List[Any] = field(default_factory=list)
    apose_ls: List[Any] = field(default_factory=list)
    bone_transforms: List[Any] = field(default_factory=list)
    parts: List[Any] = field(default_factory=list)
    track_names_extra: List[Any] = field(default_factory=list)
    rig_extra_tracks: List[Any] = field(default_factory=list) 
    reference_tracks: List[Any] = field(default_factory=list)
    cooking_platform: str = ""
    distance_category_to_lod_map: List[Any] = field(default_factory=list)
    ik_setups: List[Any] = field(default_factory=list)
    level_of_detail_start_indices: List[Any] = field(default_factory=list)
    ragdoll_desc: List[Any] = field(default_factory=list)
    ragdoll_names: List[Any] = field(default_factory=list)


def __post_init__(self) -> None:
    # Normalize array dtypes/shapes
    self.parent_indices = np.asarray(self.parent_indices, dtype=np.int16).reshape(-1)
    self.ls_q = np.asarray(self.ls_q, dtype=np.float32).reshape((-1, 4))
    self.ls_t = np.asarray(self.ls_t, dtype=np.float32).reshape((-1, 3))
    self.ls_s = np.asarray(self.ls_s, dtype=np.float32).reshape((-1, 3))


    # Ensure num_bones agrees with arrays
    n = len(self.bone_names) if self.bone_names else int(self.parent_indices.shape[0])
    self.num_bones = int(n)