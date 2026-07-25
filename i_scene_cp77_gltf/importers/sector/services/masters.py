from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import random
from ...entity_import import EntityImportRequest, import_entity
from ...common.mesh_assets import get_group, meshes_from_mesheswapps
from ....jsontool import JSONTool, resolve_requested_appearance_name
from ..context import SectorContentError
from ..options import MESH_GLB_EXTENSIONS
from ...common.resources import resolve_mesh_export
from ...common.paths import (
    absolute_path_key,
    depot_path_key,
    normalize_depot_path,
    path_key,
    trim_name as _trim_name,
)
from ...common.values import appearance_name as _appearance_name


_ENTITY_MASTER_CACHE_VERSION = 3
_UNSET = object()




def _select_entity_appearance(
    parsed_entity,
    requested,
    resolved,
    chooser=random.choice,
):
    requested = str(requested or "default")
    resolved = str(resolved or requested or "default")
    requested_key = requested.strip().lower()
    resolved_key = resolved.strip().lower()
    appearance_names = tuple(
        getattr(parsed_entity, "appearance_names", ()) or ()
    )

    if requested_key == "random" or resolved_key == "random":
        return chooser(appearance_names) if appearance_names else "default"

    if requested_key == "default":
        if resolved_key and resolved_key != "default":
            return resolved
        if appearance_names:
            default_appearance = str(
                getattr(parsed_entity, "default_appearance", "") or ""
            )
            if default_appearance and default_appearance.lower() != "random":
                return resolved or default_appearance
            return appearance_names[0]
        return "default"

    return resolved or requested




def _entity_collection_name(entpath, appearance_name):
    if not appearance_name:
        return ""
    return _trim_name(
        os.path.basename(entpath).split(".")[0] + "_" + str(appearance_name)
    )


def _entity_collection_candidates(entpath, requested_app, resolved_app):
    names = []
    for appearance_name in (resolved_app, requested_app):
        name = _entity_collection_name(entpath, appearance_name)
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _relative_entity_json_path(ent_depot):
    path = normalize_depot_path(ent_depot)
    return path if path.lower().endswith(".json") else f"{path}.json"


def _entity_master_signature(
    entpath,
    appearance,
    *,
    with_materials,
    include_lights,
):
    payload = (
        f"{_ENTITY_MASTER_CACHE_VERSION}|"
        f"{absolute_path_key(entpath)}|"
        f"{appearance}|"
        f"materials={int(bool(with_materials))}|"
        f"lights={int(bool(include_lights))}"
    )
    return hashlib.sha1(
        payload.encode("utf-8")
    ).hexdigest()


def _collection_has_materials(collection):
    try:
        objects = collection.all_objects
    except (AttributeError, ReferenceError):
        return False
    for obj in objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        data = getattr(obj, "data", None)
        materials = getattr(data, "materials", ()) if data else ()
        if any(material is not None for material in materials):
            return True
    return False


def _collection_is_linked_master(masters, collection):
    if collection is None:
        return False
    try:
        return masters.children.get(collection.name) is collection
    except (AttributeError, ReferenceError, TypeError):
        return False


def _collection_matches_entity_master(
    collection,
    *,
    expected_path,
    valid_apps,
    signature,
    require_materials,
):
    try:
        stored_path = path_key(collection.get("depotPath", ""))
        stored_app = str(collection.get("appearanceName", ""))
        stored_signature = str(
            collection.get("sectorEntityMasterSignature", "")
        )
    except (AttributeError, ReferenceError, TypeError):
        return False

    if stored_path and stored_path != expected_path:
        return False
    if valid_apps and stored_app not in valid_apps:
        return False
    if not stored_signature or stored_signature != signature:
        return False
    if require_materials and not _collection_has_materials(collection):
        return False
    return True


def _find_entity_master(
    masters,
    ent_depot,
    requested_app,
    resolved_app,
    candidates,
    *,
    signature,
    require_materials,
):
    expected_path = path_key(_relative_entity_json_path(ent_depot))
    valid_apps = {
        str(value)
        for value in (requested_app, resolved_app)
        if value
    }
    for candidate in candidates:
        collection = masters.children.get(candidate)
        if collection is not None and _collection_matches_entity_master(
            collection,
            expected_path=expected_path,
            valid_apps=valid_apps,
            signature=signature,
            require_materials=require_materials,
        ):
            return collection

    for collection in masters.children:
        if _collection_matches_entity_master(
            collection,
            expected_path=expected_path,
            valid_apps=valid_apps,
            signature=signature,
            require_materials=require_materials,
        ):
            return collection
    return None


class MasterAssetError(SectorContentError):
    pass


@dataclass(slots=True, frozen=True)
class MeshMasterPreparation:
    meshes: dict
    meshes_with_appearances: dict
    source_paths: dict[str, str]
    standard_dependency_count: int
    proxy_dependency_count: int


@dataclass(slots=True, frozen=True)
class EntityMasterResult:
    collection: object
    entpath: str
    depot_path: str
    requested_appearance: str
    resolved_appearance: str
    identity: str


class _MeshDependencyService:
    def __init__(self, session, *, proxy):
        self.session = session
        self.proxy = bool(proxy)
        self.cache = (
            session.caches.proxy_masters
            if self.proxy
            else session.caches.mesh_masters
        )

    def resolve(self, depot_path):
        key = depot_path_key(depot_path)
        if key in self.cache:
            return self.cache[key] or None
        resolved = resolve_mesh_export(
            self.session.asset_index,
            depot_path,
            warn=False,
        )
        self.cache[key] = resolved or ""
        return resolved


class MeshMasterService(_MeshDependencyService):
    def __init__(self, session):
        super().__init__(session, proxy=False)


class ProxyMasterService(_MeshDependencyService):
    def __init__(self, session):
        super().__init__(session, proxy=True)


class EntityMasterService:
    def __init__(self, session):
        self.session = session
        self.cache = session.caches.entity_masters
        self.documents = session.caches.entity_documents
        self.resolutions = session.caches.entity_resolutions
        self.stats = {
            "document_hits": 0,
            "document_misses": 0,
            "resolution_hits": 0,
            "resolution_misses": 0,
            "master_hits": 0,
            "master_builds": 0,
            "scene_reuses": 0,
        }

    def _resolve_entpath(self, ent_depot):
        reference = normalize_depot_path(ent_depot)
        if not reference:
            return None
        if not reference.lower().endswith(".json"):
            reference = f"{reference}.json"
        return self.session.asset_index.resolve_expected(
            reference,
            ".ent.json",
        )

    def _parsed_entity(self, entpath):
        path_id = absolute_path_key(entpath)
        parsed = self.documents.get(path_id)
        if parsed is not None:
            self.stats["document_hits"] += 1
            return parsed

        self.stats["document_misses"] += 1
        parsed = JSONTool.load_entity(entpath)
        if parsed is not None:
            self.documents[path_id] = parsed
        return parsed

    def _selected_appearance(
        self,
        entpath,
        parsed_entity,
        requested,
    ):
        path_id = absolute_path_key(entpath)
        request_key = str(requested or "default")
        cache_key = (path_id, request_key)
        cached = self.resolutions.get(cache_key)
        if cached is not None:
            self.stats["resolution_hits"] += 1
            return cached

        self.stats["resolution_misses"] += 1
        resolved = resolve_requested_appearance_name(
            request_key,
            parsed_entity.default_appearance,
            parsed_entity.appearances,
            parsed_entity.appearances_by_appearance,
            parsed_entity.appearances_by_name,
        ) or request_key
        selected = _select_entity_appearance(
            parsed_entity,
            request_key,
            resolved,
        )

        if (
            request_key.strip().lower() != "random"
            and str(resolved).strip().lower() != "random"
        ):
            self.resolutions[cache_key] = selected
        return selected

    @staticmethod
    def _collection_from_import_output(
        imported_collections,
        selected_appearance,
    ):
        for collection in imported_collections:
            try:
                if (
                    str(collection.get("appearanceName", ""))
                    == selected_appearance
                ):
                    return collection
            except (AttributeError, ReferenceError, TypeError):
                continue
        return (
            imported_collections[0]
            if len(imported_collections) == 1
            else None
        )

    def require(self, masters, ent_depot, requested_appearance):
        requested = str(requested_appearance or "default")
        entpath = self._resolve_entpath(ent_depot)
        if not entpath:
            raise MasterAssetError(
                f"Entity template not indexed: {ent_depot}"
            )

        parsed_entity = self._parsed_entity(entpath)
        if parsed_entity is None:
            raise MasterAssetError(
                f"Entity template could not be parsed: {entpath}"
            )

        selected_appearance = self._selected_appearance(
            entpath,
            parsed_entity,
            requested,
        )
        with_materials = bool(self.session.options.with_materials)
        include_lights = bool(self.session.options.with_lights)
        signature = _entity_master_signature(
            entpath,
            selected_appearance,
            with_materials=with_materials,
            include_lights=include_lights,
        )
        path_id = absolute_path_key(entpath)
        cache_key = (
            path_id,
            selected_appearance,
            with_materials,
            include_lights,
        )

        collection = self.cache.get(cache_key)
        if not _collection_is_linked_master(masters, collection):
            self.cache.pop(cache_key, None)
            collection = None
        else:
            stored_signature = str(
                collection.get("sectorEntityMasterSignature", "")
            )
            if stored_signature != signature:
                self.cache.pop(cache_key, None)
                collection = None
            elif (
                with_materials
                and not _collection_has_materials(collection)
            ):
                self.cache.pop(cache_key, None)
                collection = None

        if collection is not None:
            self.stats["master_hits"] += 1

        candidates = _entity_collection_candidates(
            entpath,
            selected_appearance,
            selected_appearance,
        )
        if collection is None:
            collection = _find_entity_master(
                masters,
                ent_depot,
                selected_appearance,
                selected_appearance,
                candidates,
                signature=signature,
                require_materials=with_materials,
            )
            if collection is not None:
                self.stats["scene_reuses"] += 1

        if collection is None:
            imported_collections = []
            try:
                files = self.session.files
                request = EntityImportRequest(
                    with_materials=with_materials,
                    filepath=entpath,
                    appearances=(selected_appearance,),
                    parent_collection_name="MasterInstances",
                    mesh_files=files.mesh_glbs,
                    mesh_json_files=files.mesh_jsons,
                    app_files=files.appearance_jsons,
                    animation_files=files.animation_glbs,
                    rig_json_files=files.rig_jsons,
                    parsed_entity=parsed_entity,
                    include_lights=include_lights,
                    imported_collections_out=imported_collections,
                )
                import_entity(request)
                collection = self._collection_from_import_output(
                    imported_collections,
                    selected_appearance,
                )
                if collection is None:
                    collection = _find_entity_master(
                        masters,
                        ent_depot,
                        selected_appearance,
                        selected_appearance,
                        candidates,
                        signature=signature,
                        require_materials=with_materials,
                    )
            except Exception as error:
                raise MasterAssetError(
                    f"Failed during entity import on {entpath} "
                    f"from appearance {selected_appearance}: {error}"
                ) from error

            if collection is not None:
                self.stats["master_builds"] += 1

        if collection is None:
            raise MasterAssetError(
                f"Imported entity collection not found for "
                f"{ent_depot}@{selected_appearance}; tried names: "
                f"{', '.join(candidates)}"
            )

        self.cache[cache_key] = collection
        collection["sectorEntityMaster"] = True
        collection["sectorEntityPath"] = ent_depot
        collection["sectorEntityAppearance"] = selected_appearance
        collection["sectorEntityRequestedAppearance"] = requested
        collection["sectorEntityImportLights"] = include_lights
        collection["sectorEntityWithMaterials"] = with_materials
        collection["sectorEntityMasterSignature"] = signature
        identity = signature[:8]
        return EntityMasterResult(
            collection=collection,
            entpath=entpath,
            depot_path=ent_depot,
            requested_appearance=requested,
            resolved_appearance=selected_appearance,
            identity=identity,
        )


class MasterAssetServices:
    def __init__(self, session):
        self.session = session
        self.meshes = MeshMasterService(session)
        self.proxies = ProxyMasterService(session)
        self.entities = EntityMasterService(session)
        self.last_mesh_preparation = None
        self._mesh_lookup = {}

    def prepare_meshes(self, planned_sectors, masters):
        standard_count = 0
        proxy_count = 0
        standard_paths = set()
        meshes = {}
        appearance_keys = {}
        for planned in planned_sectors:
            for plan in planned.plans:
                if not plan.enabled:
                    continue
                is_proxy = plan.placement_phase >= 30
                for dependency in plan.dependencies:
                    if dependency.kind != "mesh" or not dependency.depot_path:
                        continue
                    if is_proxy:
                        proxy_count += 1
                    else:
                        standard_count += 1
                        standard_paths.add(dependency.depot_path)
                    entry = meshes.setdefault(
                        dependency.depot_path,
                        {
                            "appearances": [],
                            "sector": dependency.source_sector,
                        },
                    )
                    appearance_key = _appearance_name(
                        dependency.appearance
                    )
                    seen = appearance_keys.setdefault(
                        dependency.depot_path,
                        set(),
                    )
                    if appearance_key not in seen:
                        seen.add(appearance_key)
                        entry["appearances"].append(
                            dependency.appearance
                        )

        source_paths = {}
        meshes_with_appearances = {}
        for meshname, mesh_data in meshes.items():
            service = (
                self.meshes
                if meshname in standard_paths
                else self.proxies
            )
            meshpath = service.resolve(meshname)
            if meshpath:
                mesh_data["meshpath"] = meshpath
                source_paths[meshname] = meshpath
            else:
                print(f"Mesh export not indexed: {meshname}")
            request = {
                "apps": [list(mesh_data["appearances"])],
                "sectors": (
                    [mesh_data["sector"]]
                    if mesh_data.get("sector")
                    else []
                ),
            }
            if mesh_data.get("meshpath"):
                request["meshpath"] = mesh_data["meshpath"]
            meshes_with_appearances[meshname] = request

        meshes_from_mesheswapps(
            meshes_with_appearances,
            asset_index=self.session.asset_index,
            from_mesh_no=0,
            to_mesh_no=100000,
            with_mats=self.session.options.with_materials,
            Masters=masters,
        )

        empty = [
            child for child in masters.children
            if len(child.objects) < 1
        ]
        for collection in empty:
            masters.children.unlink(collection)

        result = MeshMasterPreparation(
            meshes=meshes,
            meshes_with_appearances=meshes_with_appearances,
            source_paths=source_paths,
            standard_dependency_count=standard_count,
            proxy_dependency_count=proxy_count,
        )
        self.last_mesh_preparation = result
        self._mesh_lookup.clear()
        return result

    def get_mesh_master(self, masters, meshname, appearance):
        lookup_key = (
            depot_path_key(meshname),
            _appearance_name(appearance),
        )
        cached = self._mesh_lookup.get(lookup_key, _UNSET)
        if cached is not _UNSET:
            collection, groupname = cached
            if (
                collection is not None
                and masters.children.get(collection.name) is collection
            ):
                return collection, groupname
            self._mesh_lookup.pop(lookup_key, None)

        preparation = self.last_mesh_preparation
        resolved = (
            preparation.source_paths.get(meshname, "")
            if preparation is not None
            else ""
        )
        group, groupname = get_group(
            meshname,
            appearance,
            masters,
            resolved,
        )
        if group is not None:
            self._mesh_lookup[lookup_key] = (group, groupname)
            return group, groupname

        requested_appearance = _appearance_name(appearance)
        resolved_key = absolute_path_key(resolved)
        depot_key = depot_path_key(meshname)
        candidates = []
        for collection in masters.children:
            source_matches = (
                bool(resolved_key)
                and absolute_path_key(collection.get("source_glb", "")) == resolved_key
            )
            depot_matches = (
                bool(depot_key)
                and depot_path_key(collection.get("meshpath", "")) == depot_key
            )
            if not source_matches and not depot_matches:
                continue

            stored_appearance = _appearance_name(
                collection.get("appearance", "")
            )
            if requested_appearance:
                if stored_appearance != requested_appearance:
                    continue
            elif "@" in collection.name:
                continue
            candidates.append(collection)

        if requested_appearance and len(candidates) > 1:
            suffix = f"@{requested_appearance}"
            exact_variant = next(
                (
                    collection
                    for collection in candidates
                    if collection.name.endswith(suffix)
                ),
                None,
            )
            if exact_variant is not None:
                self._mesh_lookup[lookup_key] = (
                    exact_variant,
                    exact_variant.name,
                )
                return exact_variant, exact_variant.name

        if candidates:
            collection = candidates[0]
            self._mesh_lookup[lookup_key] = (
                collection,
                collection.name,
            )
            return collection, collection.name

        return None, groupname
