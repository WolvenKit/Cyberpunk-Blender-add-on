from __future__ import annotations

from uuid import uuid4

import bpy

from ...blender.identity import rna_identity, rna_is_live
from ...blender.transactions import (
    current_import_transaction,
    restore_id_property,
    snapshot_id_property,
    track_created_datablock,
    track_mutation,
)
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

SCENE_OWNER_KEY = "cp77_scenetools_id"
OWNER_KEY = "cp77_scenetools_owner"
ROLE_KEY = "cp77_scenetools_role"
# The world a scene had before Scene Tools gave it its own; the reference keeps it in the file.
KEPT_WORLD_KEY = "cp77_scenetools_kept_world"
BASE_NAME_KEY = "cp77_scenetools_base_name"
ROOT_COLLECTION_NAME = "CP77 SceneTools"
ROOT_COLLECTION_ROLE = "ROOT_COLLECTION"

_ROLE_CACHE: dict[tuple[str, str, str], object] = {}


def _track_property_mutation(owner, key, label):
    snapshot = snapshot_id_property(owner, key)
    identity = rna_identity(owner)
    track_mutation(
        ("scenetools_property", identity, str(key)),
        lambda owner=owner, key=key, snapshot=snapshot: restore_id_property(
            owner, key, snapshot
        ),
        label=label,
    )


def keep_scene_world(scene, world):
    """Keep world, which the scene is about to give up for Scene Tools' own, so a saved file still holds it"""
    if world is None or world.get(OWNER_KEY):
        return
    _track_property_mutation(scene, KEPT_WORLD_KEY, "SceneTools kept world")
    scene[KEPT_WORLD_KEY] = world


def clear_runtime_cache():
    _ROLE_CACHE.clear()


def existing_scene_owner_id(scene):
    if scene is None:
        return ""
    try:
        return str(scene.get(SCENE_OWNER_KEY, "") or "")
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("existing_scene_owner_id", type(error).__name__),
            "existing scene owner id: fell back after %s",
            error,
            exc_info=True,
        )
        return ""


def ensure_scene_owner_id(scene):
    owner_id = existing_scene_owner_id(scene)
    if owner_id:
        duplicated = any(
            other is not scene and existing_scene_owner_id(other) == owner_id
            for other in tuple(bpy.data.scenes)
        )
        if not duplicated:
            return owner_id
    owner_id = uuid4().hex
    _track_property_mutation(scene, SCENE_OWNER_KEY, "SceneTools scene ownership")
    scene[SCENE_OWNER_KEY] = owner_id
    return owner_id


def managed_name(scene, base_name):
    return f"{base_name} [{ensure_scene_owner_id(scene)[:8]}]"


def _collection(collection_name):
    collection = getattr(bpy.data, str(collection_name), None)
    if collection is None:
        raise AttributeError(f"bpy.data has no collection {collection_name!r}")
    return collection


def _is_registered(collection, value):
    if not rna_is_live(value):
        return False
    try:
        return collection.get(value.name) is value
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_is_registered", type(error).__name__),
            "is registered: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def is_owned(value, scene, role=None):
    owner_id = existing_scene_owner_id(scene)
    if not owner_id or value is None:
        return False
    try:
        if str(value.get(OWNER_KEY, "")) != owner_id:
            return False
        return role is None or str(value.get(ROLE_KEY, "")) == str(role)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("is_owned", type(error).__name__),
            "is owned: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def tag_owned(value, scene, role, *, base_name=None):
    owner_id = ensure_scene_owner_id(scene)
    _track_property_mutation(value, OWNER_KEY, "SceneTools datablock ownership")
    _track_property_mutation(value, ROLE_KEY, "SceneTools datablock role")
    value[OWNER_KEY] = owner_id
    value[ROLE_KEY] = str(role)
    if base_name:
        _track_property_mutation(value, BASE_NAME_KEY, "SceneTools datablock base name")
        value[BASE_NAME_KEY] = str(base_name)
    return value


def cache_owned(collection_name, scene, role, value):
    owner_id = ensure_scene_owner_id(scene)
    _ROLE_CACHE[(owner_id, str(collection_name), str(role))] = value
    return value


def find_owned(collection_name, scene, role):
    owner_id = existing_scene_owner_id(scene)
    if not owner_id:
        return None
    role = str(role)
    cache_key = (owner_id, str(collection_name), role)
    collection = _collection(collection_name)
    cached = _ROLE_CACHE.get(cache_key)
    if _is_registered(collection, cached) and is_owned(cached, scene, role):
        return cached
    _ROLE_CACHE.pop(cache_key, None)
    for value in tuple(collection):
        if is_owned(value, scene, role):
            _ROLE_CACHE[cache_key] = value
            return value
    return None


def retire_datablock(
    collection_name,
    value,
    *,
    scene=None,
    role=None,
    replacement=None,
    replacement_name=None,
):
    if value is None:
        return
    if scene is not None and role is not None:
        tag_owned(
            value,
            scene,
            f"{role}:RETIRED",
            base_name=value.get(BASE_NAME_KEY),
        )

    def cleanup():
        collection = _collection(collection_name)
        try:
            if collection.get(value.name) is not value:
                return
            if getattr(value, "users", 0) != 0:
                return
            collection.remove(value)
        except (ReferenceError, RuntimeError, TypeError):
            return
        if replacement is not None and replacement_name:
            try:
                replacement.name = str(replacement_name)
            except (ReferenceError, RuntimeError, TypeError):
                pass

    transaction = current_import_transaction()
    if transaction is None:
        cleanup()
    else:
        transaction.defer_commit_cleanup(cleanup)


_DATA_COLLECTIONS = {
    "MESH": "meshes",
    "CURVES": "hair_curves",
    "CURVE": "curves",
    "POINTCLOUD": "pointclouds",
}


def _object_datablocks(obj):
    """(collection name, datablock) for an object's data and its geometry node groups"""
    found = []
    data = getattr(obj, "data", None)
    collection_name = _DATA_COLLECTIONS.get(getattr(obj, "type", ""))
    if data is not None and collection_name:
        found.append((collection_name, data))
    for modifier in getattr(obj, "modifiers", ()):
        group = (
            getattr(modifier, "node_group", None) if modifier.type == "NODES" else None
        )
        if group is not None:
            found.append(("node_groups", group))
    return found


def _free_unused(datablocks):
    """Remove the datablocks nothing uses any more"""
    freed = []
    for collection_name, datablock in datablocks:
        collection = getattr(bpy.data, collection_name)
        try:
            name = datablock.name
            if datablock.users == 0 and collection.get(name) is datablock:
                collection.remove(datablock)
                freed.append((collection_name, name))
        except (ReferenceError, RuntimeError, TypeError):
            continue
    return freed


def _take_names(obj, freed):
    """Give obj's own datablocks the names the freed ones of its kinds left"""
    names = {}
    for collection_name, name in freed:
        names.setdefault(collection_name, []).append(name)
    for collection_name, datablock in _object_datablocks(obj):
        pending = names.get(collection_name)
        if not pending:
            continue
        name = pending.pop(0)
        try:
            if getattr(bpy.data, collection_name).get(name) is None:
                datablock.name = name
        except (ReferenceError, RuntimeError, TypeError):
            continue


def retire_object(
    value,
    *,
    scene=None,
    role=None,
    replacement=None,
    replacement_name=None,
):
    if value is None:
        return
    if scene is not None and role is not None:
        tag_owned(
            value,
            scene,
            f"{role}:RETIRED",
            base_name=value.get(BASE_NAME_KEY),
        )
    # The object's own data and geometry node groups go with it once nothing else uses them, and the replacement's
    # take their names.
    owned = _object_datablocks(value)

    def cleanup():
        try:
            if bpy.data.objects.get(value.name) is value:
                bpy.data.objects.remove(value, do_unlink=True)
        except (ReferenceError, RuntimeError, TypeError):
            return
        freed = _free_unused(owned)
        if replacement is not None and replacement_name:
            try:
                if bpy.data.objects.get(replacement.name) is replacement:
                    replacement.name = str(replacement_name)
            except (ReferenceError, RuntimeError, TypeError):
                pass
        if replacement is not None:
            _take_names(replacement, freed)

    transaction = current_import_transaction()
    if transaction is None:
        cleanup()
    else:
        transaction.defer_commit_cleanup(cleanup)


def root_collection(scene, *, create=False):
    owner_id = (
        ensure_scene_owner_id(scene) if create else existing_scene_owner_id(scene)
    )
    if not owner_id:
        return None
    if create:
        for child in tuple(scene.collection.children):
            try:
                if (
                    child.get(ROLE_KEY) == ROOT_COLLECTION_ROLE
                    and child.get(OWNER_KEY)
                    and not is_owned(child, scene, ROOT_COLLECTION_ROLE)
                ):
                    scene.collection.children.unlink(child)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("root_collection", type(error).__name__),
                    "root collection: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue
    collection = find_owned("collections", scene, ROOT_COLLECTION_ROLE)
    if collection is None and create:
        collection = track_created_datablock(
            "collections",
            bpy.data.collections.new(managed_name(scene, ROOT_COLLECTION_NAME)),
        )
        tag_owned(
            collection,
            scene,
            ROOT_COLLECTION_ROLE,
            base_name=ROOT_COLLECTION_NAME,
        )
        cache_owned("collections", scene, ROOT_COLLECTION_ROLE, collection)
    if (
        collection is not None
        and scene.collection.children.get(collection.name) is None
    ):
        scene.collection.children.link(collection)
    return collection


def scene_has_owned_runtime(scene):
    owner_id = existing_scene_owner_id(scene)
    if not owner_id:
        return False
    if any(
        other is not scene and existing_scene_owner_id(other) == owner_id
        for other in tuple(bpy.data.scenes)
    ):
        return False
    world = getattr(scene, "world", None)
    if is_owned(world, scene, "WORLD"):
        return True
    root = root_collection(scene, create=False)
    if root is not None:
        return True
    try:
        return any(
            str(obj.get(OWNER_KEY, "")) == owner_id for obj in tuple(scene.objects)
        )
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("scene_has_owned_runtime", type(error).__name__),
            "scene has owned runtime: fell back after %s",
            error,
            exc_info=True,
        )
        return False
