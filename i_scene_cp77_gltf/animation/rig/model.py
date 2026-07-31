from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class RigData:
    num_bones: int
    parent_indices: np.ndarray
    bone_names: list[str]
    track_names: list[str]
    ls_q: np.ndarray
    ls_t: np.ndarray
    ls_s: np.ndarray
    rig_name: str = ""
    disable_connect: bool = False
    apose_ms: list[Any] = field(default_factory=list)
    apose_ls: list[Any] = field(default_factory=list)
    bone_transforms: list[Any] = field(default_factory=list)
    parts: list[Any] = field(default_factory=list)
    track_names_extra: list[Any] = field(default_factory=list)
    rig_extra_tracks: list[Any] = field(default_factory=list)
    reference_tracks: list[Any] = field(default_factory=list)
    cooking_platform: str = ""
    distance_category_to_lod_map: list[Any] = field(default_factory=list)
    ik_setups: list[Any] = field(default_factory=list)
    level_of_detail_start_indices: list[Any] = field(default_factory=list)
    ragdoll_desc: list[Any] = field(default_factory=list)
    ragdoll_names: list[Any] = field(default_factory=list)
    source_path: str = ""
    source_document: dict | None = None
    _bone_index_map: dict[str, int] | None = field(default=None, init=False, repr=False)
    _track_index_map: dict[str, int] | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.parent_indices = np.asarray(self.parent_indices, dtype=np.int16).reshape(-1)
        self.ls_q = np.asarray(self.ls_q, dtype=np.float32).reshape((-1, 4))
        self.ls_t = np.asarray(self.ls_t, dtype=np.float32).reshape((-1, 3))
        self.ls_s = np.asarray(self.ls_s, dtype=np.float32).reshape((-1, 3))
        self.num_bones = len(self.bone_names) if self.bone_names else int(self.parent_indices.shape[0])

    @property
    def bone_parents(self):
        return self.parent_indices

    @property
    def ref_quats(self):
        return self.ls_q

    @property
    def ref_trans(self):
        return self.ls_t

    @property
    def ref_scales(self):
        return self.ls_s

    @property
    def num_tracks(self):
        return len(self.track_names)

    @property
    def lod_start_indices(self):
        return np.asarray(self.level_of_detail_start_indices, dtype=np.int32)

    @property
    def bone_index_map(self):
        cache = self._bone_index_map
        if cache is None:
            cache = {name: index for index, name in enumerate(self.bone_names)}
            self._bone_index_map = cache
        return cache

    @property
    def track_index_map(self):
        cache = self._track_index_map
        if cache is None:
            cache = {name: index for index, name in enumerate(self.track_names)}
            self._track_index_map = cache
        return cache

    def bone_index(self, name):
        return self.bone_index_map[name]

    def track_index(self, name):
        return self.track_index_map[name]
