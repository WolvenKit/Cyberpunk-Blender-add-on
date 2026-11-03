from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ...assetio.index import IndexPolicy
<<<<<<< Updated upstream
=======
from ...assetio.paths import local_path_key
>>>>>>> Stashed changes


@dataclass(frozen=True, slots=True)
class EntityImportRequest:
<<<<<<< Updated upstream
    """Canonical input for one entity import."""
=======
    """Canonical input for one entity import"""
>>>>>>> Stashed changes

    with_materials: bool
    filepath: str
    appearances: tuple[str, ...] = ("",)
    excluded_meshes: frozenset[str] = frozenset()
    include_collisions: bool = False
    include_phys: bool = False
    include_entity_colliders: bool = False
<<<<<<< Updated upstream
    include_occluders: bool = False
    include_proxies: bool = False
    include_lights: bool = False
    parent_collection_name: str = ""
    mesh_files: Any = None
    app_files: Any = None
=======
    # The colliders built into the entity's meshes; include_phys is the chassis .phys only.
    include_mesh_colliders: bool = False
    include_occluders: bool = False
    include_proxies: bool = False
    include_lights: bool = False
    # None follows include_lights.
    include_light_channels: bool | None = None
    link_lights: bool | None = None
    # None keeps the volumes.
    keep_light_channel_volumes: bool | None = None
    include_shadow_meshes: bool = True
    include_inkwidgets: bool = False
    include_facial_setup: bool = False
    include_facial_animations: bool = False
    parent_collection_name: str = ""
>>>>>>> Stashed changes
    animation_files: Any = None
    include_animations: bool = True
    generate_overrides: bool = False
    parsed_entity: Any = None
    imported_collections_out: Any = None
<<<<<<< Updated upstream
    asset_index: Any = None
    documents: Any = None
    material_resources: Any = None
    manage_master_visibility: bool = True
    transactional: bool = True
    index_policy: IndexPolicy = IndexPolicy.REFRESH
=======
    imported_rigs_out: Any = None
    existing_rig: Any = None
    asset_index: Any = None
    depot_root: str = ""
    documents: Any = None
    material_resources: Any = None
    report_owner: Any = None
    manage_master_visibility: bool = True
    transactional: bool = True
    defer_child_of_inverse: bool = False
    index_policy: IndexPolicy = IndexPolicy.REUSE
    import_id: str = ""
>>>>>>> Stashed changes

    def __post_init__(self) -> None:
        appearances = self.appearances
        if appearances is None:
            normalized_appearances = ("",)
        elif isinstance(appearances, str):
            normalized_appearances = (appearances,)
        else:
            normalized_appearances = tuple(str(value) for value in appearances)
        if not normalized_appearances:
            normalized_appearances = ("",)

        exclusions = self.excluded_meshes
        if isinstance(exclusions, str):
            exclusions = (exclusions,) if exclusions else ()
        normalized_exclusions = frozenset(
<<<<<<< Updated upstream
            os.path.normcase(os.path.normpath(str(mesh)))
            for mesh in (exclusions or ())
            if mesh
=======
            local_path_key(str(mesh)) for mesh in (exclusions or ()) if mesh
>>>>>>> Stashed changes
        )

        include_collisions = bool(self.include_collisions)
        include_phys = bool(self.include_phys)
        include_entity_colliders = bool(self.include_entity_colliders)
<<<<<<< Updated upstream
        if include_collisions and not include_phys and not include_entity_colliders:
=======
        include_mesh_colliders = bool(self.include_mesh_colliders)
        if include_collisions and not (
            include_phys or include_entity_colliders or include_mesh_colliders
        ):
>>>>>>> Stashed changes
            include_entity_colliders = True

        object.__setattr__(self, "with_materials", bool(self.with_materials))
        object.__setattr__(self, "filepath", os.path.normpath(str(self.filepath)))
<<<<<<< Updated upstream
=======
        object.__setattr__(
            self,
            "depot_root",
            os.path.normpath(str(self.depot_root)) if self.depot_root else "",
        )
>>>>>>> Stashed changes
        object.__setattr__(self, "appearances", normalized_appearances)
        object.__setattr__(self, "excluded_meshes", normalized_exclusions)
        object.__setattr__(self, "include_collisions", include_collisions)
        object.__setattr__(self, "include_phys", include_phys)
        object.__setattr__(self, "include_entity_colliders", include_entity_colliders)
<<<<<<< Updated upstream
        object.__setattr__(self, "include_occluders", bool(self.include_occluders))
        object.__setattr__(self, "include_proxies", bool(self.include_proxies))
        object.__setattr__(self, "include_lights", bool(self.include_lights))
=======
        object.__setattr__(self, "include_mesh_colliders", include_mesh_colliders)
        object.__setattr__(self, "include_occluders", bool(self.include_occluders))
        object.__setattr__(self, "include_proxies", bool(self.include_proxies))
        object.__setattr__(self, "include_lights", bool(self.include_lights))
        for name in (
            "include_light_channels",
            "link_lights",
            "keep_light_channel_volumes",
        ):
            value = getattr(self, name)
            object.__setattr__(self, name, None if value is None else bool(value))
        object.__setattr__(
            self, "include_shadow_meshes", bool(self.include_shadow_meshes)
        )
        object.__setattr__(self, "include_inkwidgets", bool(self.include_inkwidgets))
        object.__setattr__(
            self, "include_facial_setup", bool(self.include_facial_setup)
        )
        object.__setattr__(
            self,
            "include_facial_animations",
            bool(self.include_facial_animations) and bool(self.include_facial_setup),
        )
>>>>>>> Stashed changes
        object.__setattr__(
            self,
            "include_animations",
            bool(self.include_animations),
        )
<<<<<<< Updated upstream
        object.__setattr__(self, "parent_collection_name", str(self.parent_collection_name or ""))
=======
        object.__setattr__(
            self, "parent_collection_name", str(self.parent_collection_name or "")
        )
>>>>>>> Stashed changes
        object.__setattr__(self, "generate_overrides", bool(self.generate_overrides))
        object.__setattr__(
            self,
            "manage_master_visibility",
            bool(self.manage_master_visibility),
        )
        object.__setattr__(self, "transactional", bool(self.transactional))
<<<<<<< Updated upstream
        object.__setattr__(self, "index_policy", IndexPolicy(self.index_policy))
=======
        object.__setattr__(
            self,
            "defer_child_of_inverse",
            bool(self.defer_child_of_inverse),
        )
        object.__setattr__(self, "index_policy", IndexPolicy(self.index_policy))

    @property
    def light_channels_included(self) -> bool:
        return (
            self.include_lights
            if self.include_light_channels is None
            else self.include_light_channels
        )

    @property
    def lights_linked(self) -> bool:
        return self.include_lights if self.link_lights is None else self.link_lights

    @property
    def light_channel_volumes_kept(self) -> bool:
        return (
            True
            if self.keep_light_channel_volumes is None
            else self.keep_light_channel_volumes
        )
>>>>>>> Stashed changes
