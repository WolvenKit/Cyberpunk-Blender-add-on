from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ...assetio.diagnostics import IssueSeverity
from ...assetio.documents import DocumentSession
from ...assetio.index import IndexPolicy, build_asset_index
from ...assetio.paths import LocalPath
from ...materials import MaterialResourceRepository
from ...materials.repository import MATERIAL_IMAGE_EXTENSIONS
from ...materials.resources import material_resource_scope

from .execution_cache import EntityExecutionCache
from .resources import ENTITY_INDEX_EXTENSIONS, EntityResourceService


@dataclass(slots=True)
class EntityImportSession:
    """Own cache lifecycle, resource services, and Blender import outputs."""

    filepath: str
    split_source_root: Callable[[str], tuple[str, str]]
    provided_asset_index: Any
    index_policy: IndexPolicy
    documents: Any
    provided_material_resources: Any
    clear_transient_caches: Callable[[], None]
    component_depot_path: Callable[[dict], str]
    component_mesh_appearance: Callable[[dict], str]
    component_enabled: Callable[[dict], bool]
    manage_master_visibility: bool = True
    imported_collections_out: Any = None
    with_materials: bool = False

    source_root: str = field(init=False, default="")
    source_relative_path: str = field(init=False, default="")
    asset_index: Any = field(init=False, default=None)
    resources: EntityResourceService | None = field(init=False, default=None)
    material_resources: MaterialResourceRepository | None = field(init=False, default=None)
    execution_cache: EntityExecutionCache = field(init=False, default_factory=EntityExecutionCache)
    warnings: list[str] = field(init=False, default_factory=list)
    imported_collections: list[Any] = field(init=False, default_factory=list)
    masters: Any = field(init=False, default=None)
    rig: Any = field(init=False, default=None)
    _owns_documents: bool = field(init=False, default=False)
    _owns_material_resources: bool = field(init=False, default=False)
    _material_scope: Any = field(init=False, default=None)
    _issue_start: int = field(init=False, default=0)
    _started: bool = field(init=False, default=False)
    _closed: bool = field(init=False, default=False)

    def start(self) -> "EntityImportSession":
        if self._started:
            return self

        self.clear_transient_caches()
        if self.documents is None:
            self.documents = DocumentSession()
            self._owns_documents = True
        self._issue_start = len(self.documents.issues)
        self.source_root, self.source_relative_path = self.split_source_root(self.filepath)
        required_extensions = tuple(dict.fromkeys((
            *ENTITY_INDEX_EXTENSIONS,
            *(MATERIAL_IMAGE_EXTENSIONS if self.with_materials else ()),
        )))
        if self.provided_asset_index is not None:
            if self.provided_asset_index.root.key != LocalPath.from_value(
                self.source_root
            ).key:
                raise ValueError("Provided asset index root does not match entity source root")
            missing = set(required_extensions).difference(
                self.provided_asset_index.extensions
            )
            if missing:
                raise ValueError(
                    "Provided asset index is missing entity suffixes: "
                    + ", ".join(sorted(missing))
                )
            self.asset_index = self.provided_asset_index
        else:
            self.asset_index = build_asset_index(
                self.source_root,
                required_extensions,
                policy=self.index_policy,
            )

        self.execution_cache.clear()
        if self.provided_material_resources is not None:
            provided_index = getattr(
                self.provided_material_resources,
                "asset_index",
                None,
            )
            if provided_index is not self.asset_index:
                raise ValueError(
                    "Provided material resources do not use the entity asset index"
                )
            self.material_resources = self.provided_material_resources
        else:
            self.material_resources = MaterialResourceRepository(
                self.documents,
                asset_index=self.asset_index,
            )
            self._owns_material_resources = True
        self._material_scope = material_resource_scope(self.material_resources)
        self._material_scope.__enter__()
        self.resources = EntityResourceService(
            asset_index=self.asset_index,
            source_root=self.source_root,
            documents=self.documents,
            warnings=self.warnings,
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
        if self.manage_master_visibility:
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

    def collect_document_issues(self) -> None:
        for issue in self.documents.issues[self._issue_start:]:
            if issue.severity not in {IssueSeverity.WARNING, IssueSeverity.ERROR}:
                continue
            if issue.message not in self.warnings:
                self.warnings.append(issue.message)
        self._issue_start = len(self.documents.issues)

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

        if self.masters is not None and self.manage_master_visibility:
            self.masters.hide_viewport = True
        self.execution_cache.clear()
        if self.resources is not None:
            self.resources.clear()
        if self._material_scope is not None:
            self._material_scope.__exit__(None, None, None)
            self._material_scope = None
        if self.material_resources is not None and self._owns_material_resources:
            self.material_resources.clear()
        self.material_resources = None
        self._owns_material_resources = False
        if self.documents is not None:
            self.collect_document_issues()
            if self._owns_documents:
                self.documents.close()
        self.clear_transient_caches()
        self._closed = True

    def __enter__(self) -> "EntityImportSession":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False
