from __future__ import annotations

import os
import re
from typing import Any, Callable, Iterable

from ..common.paths import (
    absolute_path_key,
    depot_path_key,
    normalize_depot_path,
    path_key,
)
from ...assetio.index import indexed_files
from ...animation.rig import RigRepository
from ...meshes import MeshRepository
from ...physics import PhysicsRepository
from .repository import EntityRepository
from ..appearance.repository import AppearanceRepository

_UNSET = object()

_SOURCE_RAW_PATTERN = re.compile(r"(?:^|/)source/raw(?=$|/)", re.IGNORECASE)

ENTITY_INDEX_EXTENSIONS = (
    ".ent.json",
    ".app.json",
    ".mesh.json",
    ".glb",
    ".physicalscene.glb",
    ".physicalscene.json",
    ".w2mesh.glb",
    ".w2mesh.json",
    ".anims.glb",
    ".anims.json",
    ".rig.json",
    ".phys.json",
)


def split_source_raw_root(filepath: str) -> tuple[str, str]:
    if not filepath:
        return "", ""
    normalized = os.path.normpath(filepath)
    match = _SOURCE_RAW_PATTERN.search(normalized.replace("\\", "/"))
    if match is None:
        return os.path.dirname(normalized), os.path.basename(normalized)
    end = match.end()
    root = normalized[:end].replace("/", os.sep)
    remainder = normalized[end:].lstrip("/\\")
    return root, remainder.replace("/", os.sep)



class EntityResourceService:
    """Resolve and cache resources required by one entity import session."""

    def __init__(
        self,
        *,
        asset_index: Any,
        source_root: str,
        documents: Any,
        warnings: list[str],
        component_depot_path: Callable[[dict], str],
        component_mesh_appearance: Callable[[dict], str],
        component_enabled: Callable[[dict], bool],
    ) -> None:
        self.asset_index = asset_index
        self.source_root = source_root
        self.documents = documents
        self.warnings = warnings
        self._component_depot_path = component_depot_path
        self._component_mesh_appearance = component_mesh_appearance
        self._component_enabled = component_enabled

        self._indexed_files: dict[str, tuple[str, ...]] = {}
        self._resolved_exports: dict[tuple[str, Any], str] = {}
        self.entities = EntityRepository(documents, asset_index=asset_index)
        self.appearances = AppearanceRepository(documents, asset_index=asset_index)
        self.rigs = RigRepository(documents, asset_index=asset_index)
        self.meshes = MeshRepository(asset_index)
        self._physics = None
        self._json_documents: dict[str, Any] = {}
        self._component_mesh_info: dict[int, tuple[str, str, str, str, bool]] = {}
        self._component_mesh_json: dict[str, Any] = {}
        self._master_group_objects: dict[int, tuple[Any, ...]] = {}

    @staticmethod
    def _extension_key(extension: Any) -> Any:
        if isinstance(extension, list):
            return tuple(extension)
        return extension

    @staticmethod
    def _load_once(cache: dict, key: str, loader: Callable[[], Any]) -> Any:
        cached = cache.get(key, _UNSET)
        if cached is _UNSET:
            cached = loader()
            cache[key] = cached
        return cached

    def files(self, extension: str, provided: Iterable[str] | None = None) -> tuple[str, ...]:
        """Return normalized supplied files or one cached index query."""
        if isinstance(provided, tuple):
            return provided
        if provided:
            return tuple(dict.fromkeys(
                sorted(os.path.normpath(path) for path in provided)
            ))
        cached = self._indexed_files.get(extension)
        if cached is None:
            cached = indexed_files(self.asset_index, extension)
            self._indexed_files[extension] = cached
        return cached

    def resolve_export(self, depot_path: str, extension: Any) -> str:
        if not depot_path:
            return ""
        extension_key = self._extension_key(extension)
        cache_key = (path_key(normalize_depot_path(depot_path)), extension_key)
        cached = self._resolved_exports.get(cache_key)
        if cached is None:
            cached = self.asset_index.resolve_export(depot_path, extension) or ""
            self._resolved_exports[cache_key] = cached
        return cached

    def _load_repository(self, repository, filepath):
        issue_start = len(repository.issues)
        value = repository.load(filepath)
        for issue in repository.issues[issue_start:]:
            if issue.message not in self.warnings:
                self.warnings.append(issue.message)
        return value

    def load_entity(self, filepath: str) -> Any:
        if not filepath:
            return None
        return self._load_repository(self.entities, filepath)

    def load_app(self, filepath: str) -> Any:
        if not filepath:
            return None
        return self._load_repository(self.appearances, filepath)

    def load_json(self, filepath: str) -> Any:
        if not filepath:
            return None
        key = absolute_path_key(filepath)
        return self._load_once(
            self._json_documents,
            key,
            lambda: self.documents.payload(filepath),
        )

    def resolve_rig(self, rig_depot: str) -> str:
        return self.rigs.resolve(rig_depot) if rig_depot else ""

    def load_rig(self, reference: str) -> Any:
        if not reference:
            return None
        return self._load_repository(self.rigs, reference)

    def load_physics(self, reference: str) -> Any:
        if not reference:
            return None
        if self._physics is None:
            self._physics = PhysicsRepository(
                self.documents,
                asset_index=self.asset_index,
            )
        return self._load_repository(self._physics, reference)

    def component_mesh_info(self, component: dict) -> tuple[str, str, str, str, bool]:
        """Return the mesh descriptor tuple for one component identity."""
        cache_key = id(component)
        cached = self._component_mesh_info.get(cache_key)
        if cached is not None:
            return cached

        depot_path = self._component_depot_path(component)
        if not depot_path:
            cached = ("", "", "", "", True)
        else:
            mesh_asset = self.meshes.resolve(depot_path, include_sidecar=False)
            mesh_path = mesh_asset.local_path if mesh_asset is not None else ""
            mesh_name = os.path.basename(depot_path.replace("\\", os.sep))
            cached = (
                depot_path,
                mesh_name,
                mesh_path,
                self._component_mesh_appearance(component),
                self._component_enabled(component),
            )
        self._component_mesh_info[cache_key] = cached
        return cached

    def component_mesh_json(self, component: dict) -> Any:
        cached_info = self._component_mesh_info.get(id(component))
        depot_path = cached_info[0] if cached_info is not None else self._component_depot_path(component)
        if not depot_path:
            return None
        key = depot_path_key(depot_path)
        cached = self._component_mesh_json.get(key, _UNSET)
        if cached is _UNSET:
            json_path = self.meshes.resolve_sidecar(depot_path)
            loaded = self.load_json(json_path) if json_path else None
            cached = (
                loaded.get("Data", {}).get("RootChunk")
                if isinstance(loaded, dict)
                else None
            )
            self._component_mesh_json[key] = cached
        return cached

    def master_group_objects(self, group: Any) -> tuple[Any, ...]:
        cache_key = id(group)
        cached = self._master_group_objects.get(cache_key)
        if cached is None:
            cached = tuple(group.all_objects)
            self._master_group_objects[cache_key] = cached
        return cached

    def clear(self) -> None:
        """Release import-scoped references after execution."""
        self._indexed_files.clear()
        self._resolved_exports.clear()
        self.entities.clear()
        self.appearances.clear()
        self.rigs.clear()
        self.meshes.clear()
        if self._physics is not None:
            self._physics.clear()
            self._physics = None
        self._json_documents.clear()
        self._component_mesh_info.clear()
        self._component_mesh_json.clear()
        self._master_group_objects.clear()
