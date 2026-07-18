from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import mathutils
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


@dataclass(slots=True)
class RigData:
    num_bones: int
    parent_indices: np.ndarray  # shape [N], dtype np.int16 canonical
    bone_names: List[str]
    track_names: List[str]
    ls_q: np.ndarray  # [N,4]
    ls_t: np.ndarray  # [N,3]
    ls_s: np.ndarray  # [N,3]
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

    @property
    def bone_parents(self) -> np.ndarray:
        return self.parent_indices

    @property
    def ref_quats(self) -> np.ndarray:
        return self.ls_q

    @property
    def ref_trans(self) -> np.ndarray:
        return self.ls_t

    @property
    def ref_scales(self) -> np.ndarray:
        return self.ls_s

    @property
    def num_tracks(self) -> int:
        return len(self.track_names)

    @property
    def lod_start_indices(self) -> np.ndarray:
        return np.asarray(self.level_of_detail_start_indices, dtype=np.int32)

    @property
    def bone_index_map(self) -> dict[str, int]:
        cache = getattr(self, "_bone_index_map", None)
        if cache is None:
            cache = {name: index for index, name in enumerate(self.bone_names)}
            self._bone_index_map = cache
        return cache

    @property
    def track_index_map(self) -> dict[str, int]:
        cache = getattr(self, "_track_index_map", None)
        if cache is None:
            cache = {name: index for index, name in enumerate(self.track_names)}
            self._track_index_map = cache
        return cache

    def bone_index(self, name: str) -> int:
        return self.bone_index_map[name]

    def track_index(self, name: str) -> int:
        return self.track_index_map[name]

# Backward-compatible name for callers that still use the old facial type.
RigSkeleton = RigData
