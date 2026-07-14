from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import numpy as np
import mathutils 

@dataclass
class MaterialOverride:
    material_path: str
    override_data: Dict = field(default_factory=dict)


@dataclass
class MeshReference:
    mesh_path: str
    mesh_appearance: Optional[str] = None
    material_overrides: List[MaterialOverride] = field(default_factory=list)


@dataclass(slots=True)
class ParsedEntity:
    appearances: list
    appearance_names: list
    appearance_index_by_name: dict
    appearances_by_appearance: dict
    appearances_by_name: dict
    default_appearance: str
    component_dicts: list
    component_data: list
    components_by_name: dict
    components_by_id: dict
    component_ids: set
    component_data_ids: set
    parent_transform_lookup: dict
    skinning_lookup: dict
    shape_lookup: dict
    slot_component_lookups: dict
    collider_components: list
    simple_collider_components: list
    light_channel_components: list
    resolved_dependencies: list
    vehicle_slot_component: dict | None


@dataclass(slots=True)
class ParsedApp:
    appearances: list
    appearance_names: list
    appearances_by_name: dict
    components_by_appearance_name: dict
    chunks_by_appearance_name: dict
    parent_transform_lookup_by_appearance_name: dict
    skinning_lookup_by_appearance_name: dict
    shape_lookup_by_appearance_name: dict
    light_channels_by_appearance_name: dict
    
@dataclass(slots=True)
class BoneTransformCache:
    location: mathutils.Vector
    rotation: mathutils.Quaternion
    scale: mathutils.Vector
    matrix: mathutils.Matrix
    world_matrix: mathutils.Matrix

## TODO: merge RigSkeleton and RigData - this makes no sense to duplicate like this but I did it and someday I need to fix it
@dataclass
class RigSkeleton:
    """Minimal rig skeleton data for facial animation
    
    Attributes:
        num_bones: Total bone count
        parent_indices: Parent bone indices (-1 for root)
        bone_names: List of bone names
        track_names: List of animation track names
        reference_tracks: Default values for each track (from JSON)
        ls_q: Local-space reference quaternions (N, 4) [x, y, z, w]
        ls_t: Local-space reference translations (N, 3) [x, y, z]
        ls_s: Local-space reference scales (N, 3) [x, y, z]
    """
    num_bones: int
    parent_indices: np.ndarray  # (N,) int16
    bone_names: List[str]
    track_names: List[str]
    reference_tracks: np.ndarray  # (M,) float32 - default track values
    ls_q: np.ndarray  # (N, 4) float32 - quaternions
    ls_t: np.ndarray  # (N, 3) float32 - translations
    ls_s: np.ndarray  # (N, 3) float32 - scales

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
        # Normalize array dtypes/shapes and keep num_bones consistent with them.
        # Previously defined at module level by mistake, so it never ran.
        self.parent_indices = np.asarray(self.parent_indices, dtype=np.int16).reshape(-1)
        self.ls_q = np.asarray(self.ls_q, dtype=np.float32).reshape((-1, 4))
        self.ls_t = np.asarray(self.ls_t, dtype=np.float32).reshape((-1, 3))
        self.ls_s = np.asarray(self.ls_s, dtype=np.float32).reshape((-1, 3))
        n = len(self.bone_names) if self.bone_names else int(self.parent_indices.shape[0])
        self.num_bones = int(n)
