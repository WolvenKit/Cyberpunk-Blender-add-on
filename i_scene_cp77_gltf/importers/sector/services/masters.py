from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import random
from ...entity import EntityImportRequest, import_entity
from ...common.mesh_assets import get_group, meshes_from_mesheswapps
from ...common.entity_data import (
    resolve_ent_appearance_alias,
    resolve_requested_appearance_name,
)
from ..context import SectorContentError
from ...common.paths import (
    absolute_path_key,
    depot_path_key,
    normalize_depot_path,
    path_key,
    trim_name as _trim_name,
)
from ....assetio.values import appearance_name as _appearance_name


_ENTITY_MASTER_CACHE_VERSION = 4
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

    index, appearance_name = resolve_ent_appearance_alias(
        requested,
        parsed_entity.appearances,
        parsed_entity.appearances_by_appearance,
        parsed_entity.appearances_by_name,
    )
    if index >= 0:
        return appearance_name or resolved or requested

    default_name = resolve_requested_appearance_name(
        "default",
        parsed_entity.default_appearance,
        parsed_entity.appearances,
        parsed_entity.appearances_by_appearance,
        parsed_entity.appearances_by_name,
    )
    default_index, default_resolved = resolve_ent_appearance_alias(
        default_name,
        parsed_entity.appearances,
        parsed_entity.appearances_by_appearance,
        parsed_entity.appearances_by_name,
    )
    if default_index >= 0:
        return default_resolved or default_name
    return appearance_names[0] if appearance_names else "default"


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
    include_occluders,
    include_proxies,
):
    payload = (
        f"{_ENTITY_MASTER_CACHE_VERSION}|"
        f"{absolute_path_key(entpath)}|"
        f"{appearance}|"
        f"materials={int(bool(with_materials))}|"
        f"lights={int(bool(include_lights))}|"
        f"occluders={int(bool(include_occluders))}|"
        f"proxies={int(bool(include_proxies))}"
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
        asset = self.session.meshes.resolve(depot_path)
        resolved = asset.local_path if asset is not None else ""
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
        before = self.session.entities.stats
        parsed = self.session.entities.load(entpath)
        after = self.session.entities.stats
        self.stats["document_hits"] += after["hits"] - before["hits"]
        self.stats["document_misses"] += after["misses"] - before["misses"]
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
        include_occluders = bool(self.session.options.import_occluders)
        include_proxies = bool(self.session.options.import_proxies)
        signature = _entity_master_signature(
            entpath,
            selected_appearance,
            with_materials=with_materials,
            include_lights=include_lights,
            include_occluders=include_occluders,
            include_proxies=include_proxies,
        )
        path_id = absolute_path_key(entpath)
        cache_key = (
            path_id,
            selected_appearance,
            with_materials,
            include_lights,
            include_occluders,
            include_proxies,
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
                    app_files=files.appearance_jsons,
                    animation_files=(),
                    parsed_entity=parsed_entity,
                    include_lights=include_lights,
                    include_occluders=include_occluders,
                    include_proxies=include_proxies,
                    include_animations=False,
                    imported_collections_out=imported_collections,
                    asset_index=self.session.asset_index,
                    documents=self.session.documents,
                    material_resources=self.session.material_resources,
                    manage_master_visibility=False,
                    transactional=False,
                )
                import_result = import_entity(request)
                if not import_result.ok:
                    raise MasterAssetError(
                        "Entity import reported required-content failures: "
                        + "; ".join(import_result.failures)
                    )
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
        collection["sectorEntityImportOccluders"] = include_occluders
        collection["sectorEntityImportProxies"] = include_proxies
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
        entries_by_key = {}

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

                    canonical_key = depot_path_key(dependency.depot_path)
                    entry = entries_by_key.get(canonical_key)
                    if entry is None:
                        entry = {
                            "depot_path": dependency.depot_path,
                            "aliases": [],
                            "appearances": [],
                            "appearance_keys": set(),
                            "sector": dependency.source_sector,
                            "standard": not is_proxy,
                        }
                        entries_by_key[canonical_key] = entry
                    elif not is_proxy:
                        entry["standard"] = True

                    if dependency.depot_path not in entry["aliases"]:
                        entry["aliases"].append(dependency.depot_path)
                    appearance_key = _appearance_name(dependency.appearance)
                    if appearance_key not in entry["appearance_keys"]:
                        entry["appearance_keys"].add(appearance_key)
                        entry["appearances"].append(dependency.appearance)

        meshes = {}
        source_paths = {}
        meshes_with_appearances = {}
        for entry in entries_by_key.values():
            meshname = entry["depot_path"]
            service = self.meshes if entry["standard"] else self.proxies
            meshpath = service.resolve(meshname)
            mesh_data = {
                "appearances": list(entry["appearances"]),
                "sector": entry["sector"],
            }
            if meshpath:
                mesh_data["meshpath"] = meshpath
                for alias in entry["aliases"]:
                    source_paths[alias] = meshpath
            else:
                print(f"Mesh export not indexed: {meshname}")

            request = {
                "apps": [list(entry["appearances"])],
                "sectors": [entry["sector"]] if entry["sector"] else [],
            }
            if meshpath:
                request["meshpath"] = meshpath
            meshes[meshname] = mesh_data
            meshes_with_appearances[meshname] = request

        existing_master_children = {
            id(child) for child in masters.children
        }
        mesh_failures = meshes_from_mesheswapps(
            meshes_with_appearances,
            asset_index=self.session.asset_index,
            from_mesh_no=0,
            to_mesh_no=100000,
            with_mats=self.session.options.with_materials,
            Masters=masters,
            mesh_repository=self.session.meshes,
            document_session=self.session.documents,
            material_resources=self.session.material_resources,
        )
        for message in mesh_failures:
            print(f"Sector import warning: {message}")

        empty = [
            child
            for child in masters.children
            if id(child) not in existing_master_children
            and len(child.objects) == 0
            and len(child.children) == 0
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
