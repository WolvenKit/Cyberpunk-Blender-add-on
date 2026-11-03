from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from ...animation.services.rig.repository import RigRepository
from ...assetio.index import indexed_files
from ...assetio.paths import (
    absolute_local_path_key,
    depot_path_key,
    depot_to_local_fragment,
    local_path_key,
)
from ...assetio.resolver import resolve_mirrored_export
from ...blender.identity import rna_identity, rna_is_live
from ...core.log import get_logger, log_once
from ...meshes.repository import MeshRepository
from ...physics.services.repository import PhysicsRepository
from ..appearance.repository import AppearanceRepository
from .repository import EntityRepository

_LOG = get_logger(__name__)

_UNSET = object()


@dataclass(frozen=True, slots=True)
class MasterGroupPlan:
    objects: tuple[Any, ...]
    root_flags: tuple[bool, ...]
    resource_matrices: tuple[Any, ...]
    non_armature_objects: tuple[Any, ...]
    non_armature_root_flags: tuple[bool, ...]
    non_armature_resource_matrices: tuple[Any, ...]


ENTITY_CORE_INDEX_EXTENSIONS = (
    ".ent.json",
    ".app.json",
    ".mesh.json",
    ".glb",
    ".physicalscene.glb",
    ".physicalscene.json",
    ".w2mesh.glb",
    ".w2mesh.json",
    ".rig.json",
)
ENTITY_ANIMATION_INDEX_EXTENSIONS = (".anims.glb", ".anims.json")
ENTITY_PHYSICS_INDEX_EXTENSIONS = (".phys.json",)
ENTITY_LIGHT_INDEX_EXTENSIONS = (".ies", ".ies.json")
ENTITY_INK_INDEX_EXTENSIONS = (
    ".inkwidget.json",
    ".inkatlas.json",
    ".inkstyle.json",
    ".inkanim.json",
)
ENTITY_INDEX_EXTENSIONS = (
    *ENTITY_CORE_INDEX_EXTENSIONS,
    *ENTITY_ANIMATION_INDEX_EXTENSIONS,
    *ENTITY_PHYSICS_INDEX_EXTENSIONS,
    *ENTITY_LIGHT_INDEX_EXTENSIONS,
)


def entity_index_extensions(
    *,
    include_animations: bool = False,
    include_physics: bool = False,
    include_inkwidgets: bool = False,
    include_facial_setup: bool = False,
    include_lights: bool = False,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *ENTITY_CORE_INDEX_EXTENSIONS,
                *(ENTITY_ANIMATION_INDEX_EXTENSIONS if include_animations else ()),
                *(ENTITY_PHYSICS_INDEX_EXTENSIONS if include_physics else ()),
                *(ENTITY_INK_INDEX_EXTENSIONS if include_inkwidgets else ()),
                *((".facialsetup.json",) if include_facial_setup else ()),
                *(ENTITY_LIGHT_INDEX_EXTENSIONS if include_lights else ()),
            )
        )
    )


class EntityResourceService:
    """Resolve and cache resources required by one entity import session"""

    def __init__(
        self,
        *,
        asset_index: Any,
        source_root: str,
        depot_root: str,
        documents: Any,
        warnings: list[str],
        component_depot_path: Callable[[dict], str],
        component_mesh_appearance: Callable[[dict], str],
        component_enabled: Callable[[dict], bool],
    ) -> None:
        self.asset_index = asset_index
        self.source_root = source_root
        self.depot_root = str(depot_root or "")
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
        self._master_group_objects: dict[int, tuple[Any, tuple[Any, ...]]] = {}
        self._master_group_resolutions: dict[tuple[int, str, str], tuple[Any, str]] = {}
        self._master_group_plans: dict[int, tuple[Any, MasterGroupPlan]] = {}
        self._master_group_submesh_indexes: dict[
            int,
            tuple[Any, tuple, tuple],
        ] = {}

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

    def files(
        self, extension: str, provided: Iterable[str] | None = None
    ) -> tuple[str, ...]:
        """Return normalized supplied files or one cached index query"""
        if provided is not None:
            if isinstance(provided, tuple):
                return provided
            return tuple(
                dict.fromkeys(sorted(os.path.normpath(path) for path in provided))
            )
        cached = self._indexed_files.get(extension)
        if cached is None:
            cached = indexed_files(self.asset_index, extension)
            self._indexed_files[extension] = cached
        return cached

    def resolve_export(self, depot_path: str, extension: Any) -> str:
        if not depot_path:
            return ""
        extension_key = self._extension_key(extension)
        cache_key = (local_path_key(depot_to_local_fragment(depot_path)), extension_key)
        cached = self._resolved_exports.get(cache_key)
        if cached is None:
            cached = self.asset_index.resolve_export(depot_path, extension) or ""
            if not cached and self.source_root:
                cached = (
                    resolve_mirrored_export(
                        depot_path,
                        self.source_root,
                        extension
                        if isinstance(extension, (tuple, list))
                        else (extension,),
                    )
                    or ""
                )
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
        key = absolute_local_path_key(filepath)
        return self._load_once(
            self._json_documents,
            key,
            lambda: self.documents.payload(filepath),
        )

    def resolve_rig(self, rig_depot: str) -> str:
        if not rig_depot:
            return ""
        resolved = self.rigs.resolve(rig_depot)
        if resolved or not self.depot_root:
            return resolved or ""
        return resolve_mirrored_export(
            rig_depot,
            self.depot_root,
            (".rig.json",),
        )

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
        """Return the mesh descriptor tuple for one component identity"""
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
        depot_path = (
            cached_info[0]
            if cached_info is not None
            else self._component_depot_path(component)
        )
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
        cache_key = rna_identity(group)
        cached = self._master_group_objects.get(cache_key)
        if cached is not None and cached[0] is group:
            return cached[1]
        try:
            objects = tuple(obj for obj in group.all_objects if rna_is_live(obj))
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("EntityResourceService.master_group_objects", type(error).__name__),
                "master group objects: fell back after %s",
                error,
                exc_info=True,
            )
            objects = ()
        self._master_group_objects[cache_key] = (group, objects)
        return objects

    def resolve_master_group(
        self,
        mesh_path: str,
        mesh_appearance: str,
        masters: Any,
        resolver: Callable[..., tuple[Any, str]],
    ) -> tuple[Any, str]:
        key = (
            id(masters),
            absolute_local_path_key(mesh_path),
            str(mesh_appearance or ""),
        )
        cached = self._master_group_resolutions.get(key)
        if cached is not None:
            group, group_name = cached
            try:
                if group is None or masters.children.get(group.name) is group:
                    return group, group_name
            except (AttributeError, ReferenceError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    (
                        "EntityResourceService.resolve_master_group",
                        type(error).__name__,
                    ),
                    "resolve master group: fell back after %s",
                    error,
                    exc_info=True,
                )
        value = resolver(
            mesh_path,
            mesh_appearance,
            masters,
            source_glb=mesh_path,
        )
        self._master_group_resolutions[key] = value
        return value

    def master_group_plan(self, group: Any) -> MasterGroupPlan:
        cache_key = rna_identity(group)
        cached = self._master_group_plans.get(cache_key)
        if cached is not None and cached[0] is group:
            return cached[1]

        objects = self.master_group_objects(group)
        object_set = set(objects)

        def is_root(obj, candidates):
            try:
                parent = obj.parent
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    (
                        "EntityResourceService.master_group_plan.is_root",
                        type(error).__name__,
                    ),
                    "is root: fell back after %s",
                    error,
                    exc_info=True,
                )
                return True
            return not rna_is_live(parent) or parent not in candidates

        root_flags = tuple(is_root(obj, object_set) for obj in objects)
        resource_matrices = tuple(obj.matrix_world.copy() for obj in objects)
        non_armature_pairs = tuple(
            (obj, matrix)
            for obj, matrix in zip(objects, resource_matrices)
            if getattr(obj, "type", None) != "ARMATURE"
        )
        non_armature_objects = tuple(obj for obj, _matrix in non_armature_pairs)
        non_armature_resource_matrices = tuple(
            matrix for _obj, matrix in non_armature_pairs
        )
        non_armature_set = set(non_armature_objects)
        non_armature_root_flags = tuple(
            is_root(obj, non_armature_set) for obj in non_armature_objects
        )
        plan = MasterGroupPlan(
            objects=objects,
            root_flags=root_flags,
            resource_matrices=resource_matrices,
            non_armature_objects=non_armature_objects,
            non_armature_root_flags=non_armature_root_flags,
            non_armature_resource_matrices=non_armature_resource_matrices,
        )
        self._master_group_plans[cache_key] = (group, plan)
        return plan

    def master_group_submesh_indexes(
        self,
        group: Any,
        submesh_index_for_object: Callable[[Any], int | None],
        *,
        exclude_armatures: bool = False,
    ) -> tuple[int | None, ...]:
        cache_key = rna_identity(group)
        cached = self._master_group_submesh_indexes.get(cache_key)
        if cached is None or cached[0] is not group:
            objects = self.master_group_objects(group)
            all_indexes = tuple(submesh_index_for_object(obj) for obj in objects)
            non_armature_indexes = tuple(
                index
                for obj, index in zip(objects, all_indexes)
                if getattr(obj, "type", None) != "ARMATURE"
            )
            cached = (group, all_indexes, non_armature_indexes)
            self._master_group_submesh_indexes[cache_key] = cached
        return cached[2] if exclude_armatures else cached[1]

    def clear(self) -> None:
        """Release import-scoped references after execution"""
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
        self._master_group_resolutions.clear()
        self._master_group_plans.clear()
        self._master_group_submesh_indexes.clear()
