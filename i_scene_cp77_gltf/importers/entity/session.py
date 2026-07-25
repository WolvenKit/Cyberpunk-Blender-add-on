from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..common.cache import acquire_json_cache, release_json_cache

from .execution_cache import EntityExecutionCache
from .resources import EntityResourceService


@dataclass(slots=True)
class EntityImportSession:
    """Own cache lifecycle, resource services, and Blender import outputs."""

    filepath: str
    split_source_root: Callable[[str], tuple[str, str]]
    asset_index_type: Any
    default_asset_extensions: Any
    json_tool: Any
    clear_transient_caches: Callable[[], None]
    component_depot_path: Callable[[dict], str]
    component_mesh_appearance: Callable[[dict], str]
    component_enabled: Callable[[dict], bool]
    imported_collections_out: Any = None

    source_root: str = field(init=False, default="")
    source_relative_path: str = field(init=False, default="")
    asset_index: Any = field(init=False, default=None)
    resources: EntityResourceService | None = field(init=False, default=None)
    execution_cache: EntityExecutionCache = field(init=False, default_factory=EntityExecutionCache)
    errors: list[str] = field(init=False, default_factory=list)
    warnings: list[str] = field(init=False, default_factory=list)
    imported_collections: list[Any] = field(init=False, default_factory=list)
    masters: Any = field(init=False, default=None)
    rig: Any = field(init=False, default=None)
    _owns_json_cache: bool = field(init=False, default=False)
    _started: bool = field(init=False, default=False)
    _closed: bool = field(init=False, default=False)

    def start(self) -> "EntityImportSession":
        if self._started:
            return self

        self.clear_transient_caches()
        self.source_root, self.source_relative_path = self.split_source_root(self.filepath)
        self.asset_index = self.asset_index_type.cached(
            self.source_root,
            self.default_asset_extensions,
            force_refresh=not self.json_tool._use_cache,
        )

        self._owns_json_cache = acquire_json_cache(self.json_tool)

        self.execution_cache.clear()
        self.resources = EntityResourceService(
            asset_index=self.asset_index,
            source_root=self.source_root,
            json_tool=self.json_tool,
            errors=self.errors,
            component_depot_path=self.component_depot_path,
            component_mesh_appearance=self.component_mesh_appearance,
            component_enabled=self.component_enabled,
        )
        self._started = True
        return self

    def ensure_masters(self, bpy_module: Any, scene_collection: Any) -> Any:
        masters = scene_collection.children.get("MasterInstances")
        if masters is None:
            masters = bpy_module.data.collections.new("MasterInstances")
            scene_collection.children.link(masters)
        masters.hide_viewport = False
        self.masters = masters
        return masters

    def register_collection(self, collection: Any) -> None:
        self.imported_collections.append(collection)
        if self.imported_collections_out is not None:
            self.imported_collections_out.append(collection)

    def register_rig(self, rig: Any) -> Any:
        self.rig = rig
        return rig

    def close(self, rig: Any = None) -> None:
        if self._closed:
            return
        if rig is not None:
            self.rig = rig

        if (
            self.rig is not None
            and getattr(self.rig, "type", None) == "ARMATURE"
            and getattr(self.rig, "data", None)
        ):
            self.rig.data.pose_position = "POSE"

        release_json_cache(self.json_tool, self._owns_json_cache)
        self._owns_json_cache = False
        if self.masters is not None:
            self.masters.hide_viewport = True
        self.execution_cache.clear()
        if self.resources is not None:
            self.resources.clear()
        self.clear_transient_caches()
        self._closed = True

    def __enter__(self) -> "EntityImportSession":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False
