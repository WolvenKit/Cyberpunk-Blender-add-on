from __future__ import annotations

import hashlib
import logging
import os
import random
from dataclasses import astuple, dataclass, fields

import bpy

from ....assetio.paths import (
    absolute_local_path_key,
    depot_path_key,
    depot_to_local_fragment,
    local_path_key,
)
from ....assetio.values import cname_text
from ....blender.naming import fit_id_name
from ....blender.physics.actors import unregister_actors
from ....blender.transactions import child_import_savepoint, rollback_import_child
from ....core.log import LogLimiter, debug_exception, get_logger, log_once
from ...common.entity_data import (
    resolve_ent_appearance_alias,
    resolve_requested_appearance_name,
)
from ...common.mesh_assets import get_group, get_groupname, meshes_from_mesheswapps
from ...common.progress import NO_PROGRESS
from ...entity.execution import import_entity
from ...entity.options import EntityImportRequest
from ..context import SectorContentError
from ..model import PROXY_PHASE

_LOG = get_logger(__name__)


_ENTITY_MASTER_CACHE_VERSION = 10
_UNSET = object()


def _external_armature_references(collection):
    try:
        objects = tuple(collection.all_objects)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_external_armature_references 1", type(error).__name__),
            "external armature references: fell back after %s",
            error,
            exc_info=True,
        )
        return ()
    object_set = set(objects)
    external = []
    seen = set()

    def add(target):
        if target is None:
            return
        try:
            pointer = int(target.as_pointer())
            live = bool(pointer)
            target_type = target.type
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_external_armature_references.add", type(error).__name__),
                "add: fell back after %s",
                error,
                exc_info=True,
            )
            return
        if (
            not live
            or target in object_set
            or target_type != "ARMATURE"
            or pointer in seen
        ):
            return
        seen.add(pointer)
        external.append(target)

    for obj in objects:
        try:
            add(obj.parent)
            modifiers = tuple(obj.modifiers)
            constraints = tuple(obj.constraints)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_external_armature_references 2", type(error).__name__),
                "external armature references: fell back after %s",
                error,
                exc_info=True,
            )
            continue
        for modifier in modifiers:
            if getattr(modifier, "type", None) == "ARMATURE":
                add(getattr(modifier, "object", None))
        for constraint in constraints:
            add(getattr(constraint, "target", None))
    return tuple(external)


def _adopt_entity_rigs(collection, rigs):
    """Move sector-imported rigs inside the entity master collection"""
    adopted = []
    for rig in rigs or ():
        try:
            if getattr(rig, "type", None) != "ARMATURE":
                continue
            if collection.objects.get(rig.name) is not rig:
                collection.objects.link(rig)
            source_collections = tuple(rig.users_collection)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_adopt_entity_rigs 1", type(error).__name__),
                "adopt entity rigs: fell back after %s",
                error,
                exc_info=True,
            )
            continue

        for source_collection in source_collections:
            if source_collection is collection:
                continue
            try:
                if source_collection.objects.get(rig.name) is rig:
                    source_collection.objects.unlink(rig)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_adopt_entity_rigs 2", type(error).__name__),
                    "adopt entity rigs: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
            try:
                if not source_collection.objects and not source_collection.children:
                    bpy.data.collections.remove(source_collection)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_adopt_entity_rigs 3", type(error).__name__),
                    "adopt entity rigs: fell back after %s",
                    error,
                    exc_info=True,
                )
        adopted.append(rig)

    return tuple(adopted)


def _adopt_entity_rigs_for_collections(collections, rigs):
    """Link shared imported rigs into every appearance master"""
    targets = tuple(collection for collection in collections if collection is not None)
    target_ids = {id(collection) for collection in targets}
    adopted = []
    for rig in rigs or ():
        try:
            if getattr(rig, "type", None) != "ARMATURE":
                continue
            for collection in targets:
                if collection.objects.get(rig.name) is not rig:
                    collection.objects.link(rig)
            source_collections = tuple(rig.users_collection)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_adopt_entity_rigs_for_collections 1", type(error).__name__),
                "adopt entity rigs for collections: fell back after %s",
                error,
                exc_info=True,
            )
            continue

        for source_collection in source_collections:
            if id(source_collection) in target_ids:
                continue
            try:
                if source_collection.objects.get(rig.name) is rig:
                    source_collection.objects.unlink(rig)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_adopt_entity_rigs_for_collections 2", type(error).__name__),
                    "adopt entity rigs for collections: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
            try:
                if not source_collection.objects and not source_collection.children:
                    bpy.data.collections.remove(source_collection)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_adopt_entity_rigs_for_collections 3", type(error).__name__),
                    "adopt entity rigs for collections: fell back after %s",
                    error,
                    exc_info=True,
                )
        adopted.append(rig)

    return tuple(adopted)


def _embed_external_armatures(collection, armatures):
    """Link shared GLB armatures into an entity master without stealing ownership"""
    embedded = []
    for armature in armatures or ():
        try:
            if getattr(armature, "type", None) != "ARMATURE":
                continue
            if collection.objects.get(armature.name) is not armature:
                collection.objects.link(armature)
            embedded.append(armature)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_embed_external_armatures", type(error).__name__),
                "embed external armatures: fell back after %s",
                error,
                exc_info=True,
            )
            continue
    return tuple(embedded)


def _select_entity_appearance(
    parsed_entity,
    requested,
    resolved,
    chooser,
):
    requested = str(requested or "default")
    resolved = str(resolved or requested or "default")
    requested_key = requested.strip().lower()
    resolved_key = resolved.strip().lower()
    appearance_names = tuple(getattr(parsed_entity, "appearance_names", ()) or ())

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
    return fit_id_name(
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
    path = depot_to_local_fragment(ent_depot)
    return path if path.lower().endswith(".json") else f"{path}.json"


@dataclass(frozen=True, slots=True)
class MasterOptions:
    """What the entity masters of a sector import bring, from the sector's choices"""

    with_materials: bool
    lights: bool
    light_channels: bool
    link_lights: bool
    occluders: bool
    proxies: bool
    inkwidgets: bool
    colliders: bool

    @classmethod
    def from_sector(cls, options):
        chosen = options.chosen
        return cls(
            with_materials=bool(options.with_materials),
            lights=chosen("entity_lights"),
            light_channels=chosen("light_linking") or chosen("light_channel_volumes"),
            link_lights=chosen("light_linking"),
            occluders=chosen("entity_occluders"),
            proxies=bool(options.import_proxies),
            inkwidgets=chosen("screens"),
            colliders=chosen("entity_colliders"),
        )

    def request_fields(self):
        """The EntityImportRequest fields of a master import"""
        return {
            "with_materials": self.with_materials,
            "include_lights": self.lights,
            "include_light_channels": self.light_channels,
            "link_lights": self.link_lights,
            "keep_light_channel_volumes": True,
            "include_occluders": self.occluders,
            "include_proxies": self.proxies,
            "include_inkwidgets": self.inkwidgets,
            "include_collisions": self.colliders,
            "include_entity_colliders": self.colliders,
            "include_phys": False,
            "include_shadow_meshes": False,
        }

    def tag(self, collection):
        collection["cp77_sector_entity_with_materials"] = self.with_materials


def _entity_master_signature(entpath, appearance, master_options):
    payload = "|".join(
        (
            str(_ENTITY_MASTER_CACHE_VERSION),
            absolute_local_path_key(entpath),
            str(appearance),
            *(
                f"{field.name}={int(getattr(master_options, field.name))}"
                for field in fields(master_options)
            ),
        )
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _collection_has_materials(collection):
    try:
        objects = collection.all_objects
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_collection_has_materials", type(error).__name__),
            "collection has materials: fell back after %s",
            error,
            exc_info=True,
        )
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
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_collection_is_linked_master", type(error).__name__),
            "collection is linked master: fell back after %s",
            error,
            exc_info=True,
        )
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
        stored_path = local_path_key(collection.get("depotPath", ""))
        stored_app = str(collection.get("appearanceName", ""))
        stored_signature = str(
            collection.get("cp77_sector_entity_master_signature", "")
        )
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_collection_matches_entity_master 1", type(error).__name__),
            "collection matches entity master: fell back after %s",
            error,
            exc_info=True,
        )
        return False

    if stored_path and stored_path != expected_path:
        return False
    if valid_apps and stored_app not in valid_apps:
        return False
    if not stored_signature or stored_signature != signature:
        return False
    if require_materials:
        try:
            tagged_with_materials = bool(
                collection.get("cp77_sector_entity_with_materials", False)
            )
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_collection_matches_entity_master 2", type(error).__name__),
                "collection matches entity master: fell back after %s",
                error,
                exc_info=True,
            )
            tagged_with_materials = False
        if not tagged_with_materials and not _collection_has_materials(collection):
            return False
    return True


class MasterAssetError(SectorContentError):
    pass


@dataclass(slots=True, frozen=True)
class MeshMasterPreparation:
    meshes: dict
    meshes_with_appearances: dict
    source_paths: dict[str, str]
    source_paths_by_key: dict[str, str]
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
            session.caches.proxy_masters if self.proxy else session.caches.mesh_masters
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
        self._random_draws = {}
        self._scene_index_count = -1
        self._scene_by_signature = {}
        self._failed_requests = {}
        self.stats = {
            "document_hits": 0,
            "document_misses": 0,
            "resolution_hits": 0,
            "resolution_misses": 0,
            "master_hits": 0,
            "master_builds": 0,
            "scene_reuses": 0,
            "batch_groups": 0,
            "batch_appearances": 0,
            "scene_index_builds": 0,
            "scene_index_collections": 0,
        }

    def _resolve_entpath(self, ent_depot):
        reference = depot_to_local_fragment(ent_depot)
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

    def _seeded_choice(self, entpath, request_key):
        """A chooser for "random" appearances that a re-import repeats"""
        key = (os.path.basename(str(entpath)).casefold(), request_key)
        draw = self._random_draws.get(key, 0)
        self._random_draws[key] = draw + 1
        return random.Random(f"{key[0]}|{key[1]}|{draw}").choice

    def _selected_appearance(
        self,
        entpath,
        parsed_entity,
        requested,
    ):
        path_id = absolute_local_path_key(entpath)
        request_key = str(requested or "default")
        cache_key = (path_id, request_key)
        cached = self.resolutions.get(cache_key)
        if cached is not None:
            self.stats["resolution_hits"] += 1
            return cached

        self.stats["resolution_misses"] += 1
        resolved = (
            resolve_requested_appearance_name(
                request_key,
                parsed_entity.default_appearance,
                parsed_entity.appearances,
                parsed_entity.appearances_by_appearance,
                parsed_entity.appearances_by_name,
            )
            or request_key
        )
        selected = _select_entity_appearance(
            parsed_entity,
            request_key,
            resolved,
            self._seeded_choice(entpath, request_key),
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
                names = {
                    str(collection.get("appearanceName", "")),
                    str(collection.get("cp77_requested_appearance_name", "")),
                    str(collection.get("cp77_display_appearance_name", "")),
                }
                if selected_appearance in names:
                    return collection
            except (AttributeError, ReferenceError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    (
                        "EntityMasterService._collection_from_import_output",
                        type(error).__name__,
                    ),
                    "collection from import output: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
        return imported_collections[0] if len(imported_collections) == 1 else None

    def _rebuild_scene_index(self, masters):
        by_signature = {}
        for collection in masters.children:
            try:
                signature = str(
                    collection.get("cp77_sector_entity_master_signature", "")
                )
            except (AttributeError, ReferenceError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("EntityMasterService._rebuild_scene_index", type(error).__name__),
                    "rebuild scene index: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
            if signature:
                by_signature.setdefault(signature, []).append(collection)
        self._scene_by_signature = by_signature
        self._scene_index_count = len(masters.children)
        self.stats["scene_index_builds"] += 1
        self.stats["scene_index_collections"] += self._scene_index_count

    def _find_scene_master(
        self,
        masters,
        ent_depot,
        requested_app,
        resolved_app,
        candidates,
        *,
        signature,
        require_materials,
    ):
        expected_path = local_path_key(_relative_entity_json_path(ent_depot))
        valid_apps = {str(value) for value in (requested_app, resolved_app) if value}
        checked = set()
        for candidate in candidates:
            collection = masters.children.get(candidate)
            if collection is None:
                continue
            checked.add(id(collection))
            if _collection_matches_entity_master(
                collection,
                expected_path=expected_path,
                valid_apps=valid_apps,
                signature=signature,
                require_materials=require_materials,
            ):
                return collection

        if self._scene_index_count != len(masters.children):
            self._rebuild_scene_index(masters)

        for collection in self._scene_by_signature.get(signature, ()):
            if id(collection) in checked:
                continue
            if _collection_matches_entity_master(
                collection,
                expected_path=expected_path,
                valid_apps=valid_apps,
                signature=signature,
                require_materials=require_materials,
            ):
                return collection
        return None

    def _invalidate_scene_index(self):
        self._scene_index_count = -1
        self._scene_by_signature.clear()

    def _identity(self, entpath, selected_appearance):
        master_options = MasterOptions.from_sector(self.session.options)
        signature = _entity_master_signature(
            entpath, selected_appearance, master_options
        )
        cache_key = (
            absolute_local_path_key(entpath),
            selected_appearance,
            *astuple(master_options),
        )
        return signature, cache_key

    def _cached_or_scene_master(
        self,
        masters,
        ent_depot,
        entpath,
        selected_appearance,
        *,
        signature,
        cache_key,
    ):
        with_materials = bool(self.session.options.with_materials)
        collection = self.cache.get(cache_key)
        if not _collection_is_linked_master(masters, collection) or (
            str(collection.get("cp77_sector_entity_master_signature", "")) != signature
        ):
            self.cache.pop(cache_key, None)
            collection = None
        if collection is not None:
            self.stats["master_hits"] += 1
            return collection

        candidates = _entity_collection_candidates(
            entpath,
            selected_appearance,
            selected_appearance,
        )
        collection = self._find_scene_master(
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
            self.cache[cache_key] = collection
        return collection

    def _tag_collection(
        self,
        collection,
        *,
        signature,
        cache_key,
    ):
        self.cache[cache_key] = collection
        master_options = MasterOptions.from_sector(self.session.options)
        master_options.tag(collection)
        if master_options.colliders:
            # Masters are only copied: the PhysX tools work on the placed copies.
            unregister_actors(tuple(collection.all_objects), bpy.context)
        collection["cp77_sector_entity_master_signature"] = signature
        self._invalidate_scene_index()
        return collection

    def prepare(self, masters, dependencies, *, progress=NO_PROGRESS):
        """Batch missing appearances of each entity into one importer session"""
        pending_by_path = {}
        seen = set()
        for dependency in dependencies:
            ent_depot = str(getattr(dependency, "depot_path", "") or "")
            requested = str(getattr(dependency, "appearance", "default") or "default")
            if not ent_depot or requested.strip().lower() == "random":
                continue
            request_key = (depot_path_key(ent_depot), requested)
            if request_key in seen:
                continue
            seen.add(request_key)

            entpath = self._resolve_entpath(ent_depot)
            if not entpath:
                self._failed_requests[request_key] = (
                    f"Entity template not indexed: {ent_depot}"
                )
                continue
            parsed_entity = self._parsed_entity(entpath)
            if parsed_entity is None:
                self._failed_requests[request_key] = (
                    f"Entity template could not be parsed: {entpath}"
                )
                continue
            selected = self._selected_appearance(
                entpath,
                parsed_entity,
                requested,
            )
            signature, cache_key = self._identity(entpath, selected)
            collection = self._cached_or_scene_master(
                masters,
                ent_depot,
                entpath,
                selected,
                signature=signature,
                cache_key=cache_key,
            )
            if collection is not None:
                self._tag_collection(
                    collection,
                    signature=signature,
                    cache_key=cache_key,
                )
                continue

            path_key_value = absolute_local_path_key(entpath)
            group = pending_by_path.setdefault(
                path_key_value,
                {
                    "entpath": entpath,
                    "parsed": parsed_entity,
                    "requests": [],
                },
            )
            group["requests"].append(
                {
                    "ent_depot": ent_depot,
                    "selected": selected,
                    "signature": signature,
                    "cache_key": cache_key,
                    "request_key": request_key,
                }
            )

        failures = []
        request_fields = MasterOptions.from_sector(
            self.session.options
        ).request_fields()
        pending_groups = tuple(pending_by_path.values())
        group_count = len(pending_groups)
        for group_index, group in enumerate(pending_groups):
            requests = group["requests"]
            group_progress = progress.span(
                100.0 * group_index / max(1, group_count),
                100.0 * (group_index + 1) / max(1, group_count),
                label=os.path.basename(group["entpath"])[:-9],
            )
            appearances = tuple(
                dict.fromkeys(request["selected"] for request in requests)
            )
            imported_collections = []
            imported_rigs = []
            self.stats["batch_groups"] += 1
            self.stats["batch_appearances"] += len(appearances)
            child_state = child_import_savepoint()
            try:
                import_result = import_entity(
                    EntityImportRequest(
                        **request_fields,
                        filepath=group["entpath"],
                        appearances=appearances,
                        parent_collection_name="MasterInstances",
                        animation_files=(),
                        parsed_entity=group["parsed"],
                        include_animations=False,
                        imported_collections_out=imported_collections,
                        imported_rigs_out=imported_rigs,
                        asset_index=self.session.asset_index,
                        depot_root=self.session.depot_root,
                        documents=self.session.documents,
                        material_resources=self.session.material_resources,
                        manage_master_visibility=False,
                        transactional=False,
                        defer_child_of_inverse=True,
                    ),
                    progress=group_progress,
                )
                if not import_result.ok:
                    raise MasterAssetError(
                        "Entity import reported required-content failures: "
                        + "; ".join(import_result.failures)
                    )
            except Exception as error:
                debug_exception(
                    _LOG, "Batched entity import failed for %s", group["entpath"]
                )
                message = f"Failed during batched entity import on {group['entpath']}: {error}"
                try:
                    rollback_import_child(
                        child_state,
                        f"entity master {os.path.basename(group['entpath'])}",
                    )
                except RuntimeError as rollback_error:
                    message += f"; {rollback_error}"
                imported_collections.clear()
                imported_rigs.clear()
                failures.append(message)
                for request in requests:
                    self._failed_requests[request["request_key"]] = message
                continue

            by_appearance = {}
            for collection in imported_collections:
                try:
                    for key in (
                        "appearanceName",
                        "cp77_requested_appearance_name",
                        "cp77_display_appearance_name",
                    ):
                        name = str(collection.get(key, ""))
                        if name:
                            by_appearance.setdefault(name, collection)
                except (AttributeError, ReferenceError, TypeError) as exc:
                    log_once(
                        _LOG,
                        "DEBUG",
                        ("EntityMasterService.prepare", type(exc).__name__),
                        "prepare: fell back after %s",
                        exc,
                        exc_info=True,
                    )
                    continue
            _adopt_entity_rigs_for_collections(imported_collections, imported_rigs)

            for request in requests:
                collection = by_appearance.get(request["selected"])
                if collection is None:
                    collection = self._collection_from_import_output(
                        imported_collections,
                        request["selected"],
                    )
                if collection is None:
                    message = (
                        "Batched entity import produced no collection for "
                        f"{request['ent_depot']}@{request['selected']}"
                    )
                    failures.append(message)
                    self._failed_requests[request["request_key"]] = message
                    continue

                remaining_external = _external_armature_references(collection)
                if remaining_external:
                    _embed_external_armatures(collection, remaining_external)
                    remaining_external = _external_armature_references(collection)
                if remaining_external:
                    names = ", ".join(
                        str(getattr(armature, "name", "<unnamed>"))
                        for armature in remaining_external
                    )
                    message = (
                        "Entity master retains external armature references: " + names
                    )
                    failures.append(message)
                    self._failed_requests[request["request_key"]] = message
                    continue

                self._tag_collection(
                    collection,
                    signature=request["signature"],
                    cache_key=request["cache_key"],
                )
                self.stats["master_builds"] += 1

        _LOG.debug(
            "Entity master preparation: %d batch group(s), %d appearance(s), "
            "%d scene index rebuild(s), %d collection(s) indexed; service totals",
            self.stats["batch_groups"],
            self.stats["batch_appearances"],
            self.stats["scene_index_builds"],
            self.stats["scene_index_collections"],
        )
        return tuple(dict.fromkeys(failures))

    def require(self, masters, ent_depot, requested_appearance):
        requested = str(requested_appearance or "default")
        failed = self._failed_requests.get((depot_path_key(ent_depot), requested))
        if failed:
            raise MasterAssetError(failed)
        entpath = self._resolve_entpath(ent_depot)
        if not entpath:
            raise MasterAssetError(f"Entity template not indexed: {ent_depot}")

        parsed_entity = self._parsed_entity(entpath)
        if parsed_entity is None:
            raise MasterAssetError(f"Entity template could not be parsed: {entpath}")

        selected_appearance = self._selected_appearance(
            entpath,
            parsed_entity,
            requested,
        )
        master_options = MasterOptions.from_sector(self.session.options)
        with_materials = master_options.with_materials
        signature, cache_key = self._identity(entpath, selected_appearance)

        collection = self.cache.get(cache_key)
        if not _collection_is_linked_master(masters, collection):
            self.cache.pop(cache_key, None)
            collection = None
        else:
            stored_signature = str(
                collection.get("cp77_sector_entity_master_signature", "")
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
            collection = self._find_scene_master(
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
            imported_rigs = []
            try:
                request = EntityImportRequest(
                    **master_options.request_fields(),
                    filepath=entpath,
                    appearances=(selected_appearance,),
                    parent_collection_name="MasterInstances",
                    animation_files=(),
                    parsed_entity=parsed_entity,
                    include_animations=False,
                    imported_collections_out=imported_collections,
                    imported_rigs_out=imported_rigs,
                    asset_index=self.session.asset_index,
                    depot_root=self.session.depot_root,
                    documents=self.session.documents,
                    material_resources=self.session.material_resources,
                    manage_master_visibility=False,
                    transactional=False,
                    defer_child_of_inverse=True,
                )
                import_result = import_entity(request, progress=NO_PROGRESS)
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
                    self._invalidate_scene_index()
                    collection = self._find_scene_master(
                        masters,
                        ent_depot,
                        selected_appearance,
                        selected_appearance,
                        candidates,
                        signature=signature,
                        require_materials=with_materials,
                    )
                if collection is not None:
                    _adopt_entity_rigs(collection, imported_rigs)
                    remaining_external = _external_armature_references(collection)
                    if remaining_external:
                        _embed_external_armatures(collection, remaining_external)
                        remaining_external = _external_armature_references(collection)
                    if remaining_external:
                        names = ", ".join(
                            str(getattr(armature, "name", "<unnamed>"))
                            for armature in remaining_external
                        )
                        raise MasterAssetError(
                            "Entity master retains external armature references: "
                            + names
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

        self._tag_collection(
            collection,
            signature=signature,
            cache_key=cache_key,
        )
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
        self._mesh_index_count = -1
        self._mesh_by_source = {}
        self._mesh_by_depot = {}

    @staticmethod
    def _appearance_lookup_keys(appearance):
        key = cname_text(appearance)
        return ("default", "") if key in {"", "default"} else (key,)

    def _rebuild_mesh_index(self, masters):
        by_source = {}
        by_depot = {}
        for collection in masters.children:
            try:
                appearance = cname_text(collection.get("appearance", ""))
                source_key = absolute_local_path_key(collection.get("sourcePath", ""))
                depot_key = depot_path_key(collection.get("meshPath", ""))
            except (AttributeError, ReferenceError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("MasterAssetServices._rebuild_mesh_index", type(error).__name__),
                    "rebuild mesh index: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
            if source_key:
                by_source.setdefault((source_key, appearance), collection)
            if depot_key:
                by_depot.setdefault((depot_key, appearance), collection)
        self._mesh_by_source = by_source
        self._mesh_by_depot = by_depot
        self._mesh_index_count = len(masters.children)

    def _ensure_mesh_index(self, masters):
        if self._mesh_index_count != len(masters.children):
            self._rebuild_mesh_index(masters)
            self._mesh_lookup.clear()

    def _indexed_mesh_master(self, meshname, appearance, resolved):
        appearance_keys = self._appearance_lookup_keys(appearance)
        source_key = absolute_local_path_key(resolved)
        if source_key:
            for appearance_key in appearance_keys:
                collection = self._mesh_by_source.get((source_key, appearance_key))
                if collection is not None:
                    return collection
        depot_key = depot_path_key(meshname)
        if depot_key:
            for appearance_key in appearance_keys:
                collection = self._mesh_by_depot.get((depot_key, appearance_key))
                if collection is not None:
                    return collection
        return None

    def prepare_meshes(self, planned_sectors, masters, *, progress=NO_PROGRESS):
        standard_count = 0
        proxy_count = 0
        entries_by_key = {}

        for planned in planned_sectors:
            for dependency in planned.mesh_dependencies:
                is_proxy = dependency.placement_phase >= PROXY_PHASE
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
                        "alias_keys": set(),
                        "appearances": [],
                        "appearance_keys": set(),
                        "sector": dependency.source_sector,
                        "standard": not is_proxy,
                    }
                    entries_by_key[canonical_key] = entry
                elif not is_proxy:
                    entry["standard"] = True

                alias_key = depot_path_key(dependency.depot_path)
                if alias_key not in entry["alias_keys"]:
                    entry["alias_keys"].add(alias_key)
                    entry["aliases"].append(dependency.depot_path)
                appearance_key = cname_text(dependency.appearance)
                if appearance_key not in entry["appearance_keys"]:
                    entry["appearance_keys"].add(appearance_key)
                    entry["appearances"].append(dependency.appearance)

        meshes = {}
        source_paths = {}
        source_paths_by_key = {}
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
                    source_paths_by_key[depot_path_key(alias)] = meshpath
            request = {
                "apps": [list(entry["appearances"])],
                "sectors": [entry["sector"]] if entry["sector"] else [],
            }
            if meshpath:
                request["meshpath"] = meshpath
            meshes[meshname] = mesh_data
            meshes_with_appearances[meshname] = request

        if not meshes_with_appearances:
            result = MeshMasterPreparation(
                meshes=meshes,
                meshes_with_appearances=meshes_with_appearances,
                source_paths=source_paths,
                source_paths_by_key=source_paths_by_key,
                standard_dependency_count=standard_count,
                proxy_dependency_count=proxy_count,
            )
            self.last_mesh_preparation = result
            self._mesh_lookup.clear()
            self._rebuild_mesh_index(masters)
            return result

        existing_master_children = {id(child) for child in masters.children}
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
            progress=progress,
        )
        missing_exports = [
            message
            for message in mesh_failures
            if message.startswith("Mesh export not indexed:")
        ]
        other_failures = [
            message
            for message in mesh_failures
            if not message.startswith("Mesh export not indexed:")
        ]
        unindexed = LogLimiter(
            _LOG,
            logging.WARNING,
            20,
            "%d more unindexed mesh exports, logged at DEBUG; first: %s",
        )
        for message in missing_exports:
            unindexed.log("unindexed", "%s", message)
        unindexed.flush()
        for message in other_failures:
            _LOG.warning("%s", message)

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
            source_paths_by_key=source_paths_by_key,
            standard_dependency_count=standard_count,
            proxy_dependency_count=proxy_count,
        )
        self.last_mesh_preparation = result
        self._mesh_lookup.clear()
        self._rebuild_mesh_index(masters)
        return result

    def get_mesh_master(self, masters, meshname, appearance):
        self._ensure_mesh_index(masters)
        lookup_key = (
            depot_path_key(meshname),
            cname_text(appearance),
        )
        cached = self._mesh_lookup.get(lookup_key, _UNSET)
        if cached is not _UNSET:
            collection, groupname, generation = cached
            if generation == self._mesh_index_count:
                if collection is None:
                    return None, groupname
                if masters.children.get(collection.name) is collection:
                    return collection, groupname
            self._mesh_lookup.pop(lookup_key, None)

        preparation = self.last_mesh_preparation
        resolved = ""
        if preparation is not None:
            resolved = preparation.source_paths_by_key.get(
                lookup_key[0],
                "",
            )

        collection = self._indexed_mesh_master(
            meshname,
            appearance,
            resolved,
        )
        groupname = get_groupname(meshname, appearance)
        if collection is None:
            collection, groupname = get_group(
                meshname,
                appearance,
                masters,
                resolved,
            )
            if collection is not None:
                self._rebuild_mesh_index(masters)

        if collection is not None:
            groupname = collection.name
        self._mesh_lookup[lookup_key] = (
            collection,
            groupname,
            self._mesh_index_count,
        )
        return collection, groupname
