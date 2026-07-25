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
from ..common.resources import MESH_GLB_EXTENSIONS, indexed_files

_UNSET = object()

_SOURCE_RAW_PATTERN = re.compile(r"(?:^|/)source/raw(?=$|/)", re.IGNORECASE)


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
        json_tool: Any,
        errors: list[str],
        component_depot_path: Callable[[dict], str],
        component_mesh_appearance: Callable[[dict], str],
        component_enabled: Callable[[dict], bool],
    ) -> None:
        self.asset_index = asset_index
        self.source_root = source_root
        self.json_tool = json_tool
        self.errors = errors
        self._component_depot_path = component_depot_path
        self._component_mesh_appearance = component_mesh_appearance
        self._component_enabled = component_enabled

        self._indexed_files: dict[str, tuple[str, ...]] = {}
        self._resolved_exports: dict[tuple[str, Any], str] = {}
        self._parsed_entities: dict[str, Any] = {}
        self._parsed_apps: dict[str, Any] = {}
        self._json_documents: dict[str, Any] = {}
        self._root_chunks: dict[str, Any] = {}
        self._rig_json_paths: dict[str, str] = {}
        self._rig_json_roots: dict[str, Any] = {}
        self._rig_data_by_path: dict[str, Any] = {}
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

    def load_entity(self, filepath: str) -> Any:
        if not filepath:
            return None
        key = absolute_path_key(filepath)
        return self._load_once(
            self._parsed_entities,
            key,
            lambda: self.json_tool.load_entity(filepath, self.errors),
        )

    def load_app(self, filepath: str) -> Any:
        if not filepath:
            return None
        key = absolute_path_key(filepath)
        return self._load_once(
            self._parsed_apps,
            key,
            lambda: self.json_tool.load_app(filepath, self.errors),
        )

    def load_json(self, filepath: str) -> Any:
        if not filepath:
            return None
        key = absolute_path_key(filepath)
        return self._load_once(
            self._json_documents,
            key,
            lambda: self.json_tool.jsonload(filepath, self.errors),
        )

    def load_root_chunk(self, filepath: str) -> Any:
        if not filepath:
            return None
        key = absolute_path_key(filepath)
        return self._load_once(
            self._root_chunks,
            key,
            lambda: (
                loaded.get("Data", {}).get("RootChunk")
                if (loaded := self.load_json(filepath)) is not None
                else None
            ),
        )

    def rig_json_path_for_depot(self, rig_depot: str) -> str:
        if not rig_depot:
            return ""
        key = depot_path_key(rig_depot)
        cached = self._rig_json_paths.get(key)
        if cached is None:
            cached = self.resolve_export(rig_depot, ".rig.json")
            self._rig_json_paths[key] = cached
        return cached

    def rig_json_for_depot(self, rig_depot: str) -> Any:
        if not rig_depot:
            return None
        key = depot_path_key(rig_depot)
        cached = self._rig_json_roots.get(key, _UNSET)
        if cached is _UNSET:
            rig_path = self.rig_json_path_for_depot(rig_depot)
            cached = self.load_root_chunk(rig_path) if rig_path else None
            self._rig_json_roots[key] = cached
        return cached

    def rig_data_for_path(self, filepath: str, loader: Callable[[str], Any]) -> Any:
        """Load one parsed RigData object per normalized rig path."""
        if not filepath:
            return None
        normalized = absolute_path_key(filepath)
        cached = self._rig_data_by_path.get(normalized, _UNSET)
        if cached is _UNSET:
            cached = loader(filepath)
            self._rig_data_by_path[normalized] = cached
        return cached

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
            mesh_path = self.resolve_export(
                depot_path,
                MESH_GLB_EXTENSIONS,
            )
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
            json_path = self.resolve_export(depot_path, ".mesh.json")
            cached = self.load_root_chunk(json_path) if json_path else None
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
        self._parsed_entities.clear()
        self._parsed_apps.clear()
        self._json_documents.clear()
        self._root_chunks.clear()
        self._rig_json_paths.clear()
        self._rig_json_roots.clear()
        self._rig_data_by_path.clear()
        self._component_mesh_info.clear()
        self._component_mesh_json.clear()
        self._master_group_objects.clear()
