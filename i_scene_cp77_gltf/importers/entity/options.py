from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityImportRequest:
    """Canonical input for one entity import."""

    with_materials: bool
    filepath: str
    appearances: tuple[str, ...] = ("",)
    excluded_meshes: frozenset[str] = frozenset()
    include_collisions: bool = False
    include_phys: bool = False
    include_entity_colliders: bool = False
    include_occluders: bool = False
    include_proxies: bool = False
    include_lights: bool = False
    parent_collection_name: str = ""
    mesh_files: Any = None
    mesh_json_files: Any = None
    app_files: Any = None
    animation_files: Any = None
    rig_json_files: Any = None
    generate_overrides: bool = False
    parsed_entity: Any = None
    imported_collections_out: Any = None

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
            os.path.normcase(os.path.normpath(str(mesh)))
            for mesh in (exclusions or ())
            if mesh
        )

        include_collisions = bool(self.include_collisions)
        include_phys = bool(self.include_phys)
        include_entity_colliders = bool(self.include_entity_colliders)
        if include_collisions and not include_phys and not include_entity_colliders:
            include_entity_colliders = True

        object.__setattr__(self, "with_materials", bool(self.with_materials))
        object.__setattr__(self, "filepath", os.path.normpath(str(self.filepath)))
        object.__setattr__(self, "appearances", normalized_appearances)
        object.__setattr__(self, "excluded_meshes", normalized_exclusions)
        object.__setattr__(self, "include_collisions", include_collisions)
        object.__setattr__(self, "include_phys", include_phys)
        object.__setattr__(self, "include_entity_colliders", include_entity_colliders)
        object.__setattr__(self, "include_occluders", bool(self.include_occluders))
        object.__setattr__(self, "include_proxies", bool(self.include_proxies))
        object.__setattr__(self, "include_lights", bool(self.include_lights))
        object.__setattr__(self, "parent_collection_name", str(self.parent_collection_name or ""))
        object.__setattr__(self, "generate_overrides", bool(self.generate_overrides))
