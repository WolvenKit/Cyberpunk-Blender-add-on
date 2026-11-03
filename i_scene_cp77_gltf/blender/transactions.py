from __future__ import annotations

import copy
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

try:
    import bpy
except ImportError:
    bpy = None


_ACTIVE_IMPORT_TRANSACTION = ContextVar("cp77_active_import_transaction", default=None)


_TRANSACTION_DATABLOCKS = (
    "objects",
    "scenes",
    "collections",
    "meshes",
    "curves",
    "armatures",
    "lattices",
    "lights",
    "cameras",
    "materials",
    "images",
    "actions",
    "node_groups",
    "shape_keys",
    "particle_settings",
    "palettes",
    "worlds",
    "texts",
)


def _datablock_identity(value):
    try:
        return int(value.as_pointer())
    except (AttributeError, ReferenceError):
        return id(value)


def snapshot_datablocks():
    if bpy is None:
        return {}
    return {
        name: frozenset(
            _datablock_identity(value)
            for value in getattr(bpy.data, name, ())
        )
        for name in _TRANSACTION_DATABLOCKS
        if hasattr(bpy.data, name)
    }


def rollback_datablocks(snapshot):
    if bpy is None:
        return
    for name in _TRANSACTION_DATABLOCKS:
        collection = getattr(bpy.data, name, None)
        if collection is None:
            continue
        previous = snapshot.get(name, frozenset())
        created = [
            value
            for value in tuple(collection)
            if _datablock_identity(value) not in previous
        ]
        for value in reversed(created):
            try:
                collection.remove(value, do_unlink=True)
            except TypeError:
                try:
                    collection.remove(value)
                except (ReferenceError, RuntimeError, TypeError, ValueError):
                    pass
            except (ReferenceError, RuntimeError, ValueError):
                pass


def snapshot_id_properties(owner):
    if owner is None:
        return None
    try:
        keys = tuple(owner.keys())
    except (AttributeError, ReferenceError, TypeError):
        return None
    snapshot = {}
    for key in keys:
        try:
            snapshot[key] = copy.deepcopy(owner[key])
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            try:
                snapshot[key] = owner[key]
            except (AttributeError, KeyError, ReferenceError, TypeError):
                pass
    return snapshot


def restore_id_properties(owner, snapshot):
    if owner is None or snapshot is None:
        return
    try:
        for key in tuple(owner.keys()):
            del owner[key]
        for key, value in snapshot.items():
            owner[key] = value
    except (AttributeError, ReferenceError, TypeError):
        pass


@dataclass(slots=True)
class _CollectionState:
    owner: object
    properties: object
    children: tuple
    objects: tuple
    hide_viewport: object
    hide_render: object


@dataclass(slots=True)
class _ObjectState:
    owner: object
    properties: object
    parent: object
    data: object
    matrix_world: object
    hide_viewport: object
    hide_select: object
    hide_render: object
    hide_get: object


@dataclass(slots=True)
class _MeshState:
    owner: object
    properties: object
    materials: tuple


@dataclass(slots=True)
class _ArmatureState:
    owner: object
    properties: object
    pose_position: object


@dataclass(slots=True)
class _PhysxSceneState:
    owner: object
    actor_refs: tuple
    actor_list_index: object
    active_actor_count: object


def _safe_tuple(value):
    try:
        return tuple(value)
    except (ReferenceError, TypeError):
        return ()


def _copy_matrix(value):
    try:
        return value.copy()
    except (AttributeError, ReferenceError):
        return None


def _collection_state(collection):
    return _CollectionState(
        collection,
        snapshot_id_properties(collection),
        _safe_tuple(getattr(collection, "children", ())),
        _safe_tuple(getattr(collection, "objects", ())),
        getattr(collection, "hide_viewport", None),
        getattr(collection, "hide_render", None),
    )


def _object_state(obj):
    try:
        hidden = obj.hide_get()
    except (AttributeError, ReferenceError, TypeError):
        hidden = None
    return _ObjectState(
        obj,
        snapshot_id_properties(obj),
        getattr(obj, "parent", None),
        getattr(obj, "data", None),
        _copy_matrix(getattr(obj, "matrix_world", None)),
        getattr(obj, "hide_viewport", None),
        getattr(obj, "hide_select", None),
        getattr(obj, "hide_render", None),
        hidden,
    )


def _mesh_state(mesh):
    return _MeshState(
        mesh,
        snapshot_id_properties(mesh),
        _safe_tuple(getattr(mesh, "materials", ())),
    )


def _armature_state(armature):
    return _ArmatureState(
        armature,
        snapshot_id_properties(armature),
        getattr(armature, "pose_position", None),
    )


def _physx_scene_state(scene):
    physx = getattr(scene, "physx", None)
    if physx is None:
        return None
    actors = getattr(physx, "actors", None)
    if actors is None:
        return None
    return _PhysxSceneState(
        scene,
        tuple(getattr(item, "obj_ref", None) for item in _safe_tuple(actors)),
        getattr(physx, "actor_list_index", None),
        getattr(physx, "active_actor_count", None),
    )


def _force_object_mode():
    if bpy is None:
        return
    context = getattr(bpy, "context", None)
    if context is None or getattr(context, "mode", "OBJECT") == "OBJECT":
        return
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except (AttributeError, RuntimeError, TypeError):
        pass


def _owner_exists(owner, collection_name):
    if bpy is None or owner is None:
        return False
    collection = getattr(bpy.data, collection_name, None)
    if collection is None:
        return False
    try:
        return collection.get(owner.name) is owner
    except (AttributeError, ReferenceError, TypeError):
        try:
            return owner in collection
        except (ReferenceError, TypeError):
            return False


def _restore_links(link_collection, expected):
    expected_ids = {_datablock_identity(value) for value in expected}
    for value in _safe_tuple(link_collection):
        if _datablock_identity(value) not in expected_ids:
            try:
                link_collection.unlink(value)
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass
    current_ids = {
        _datablock_identity(value)
        for value in _safe_tuple(link_collection)
    }
    for value in expected:
        identity = _datablock_identity(value)
        if identity in current_ids:
            continue
        try:
            link_collection.link(value)
            current_ids.add(identity)
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass


@dataclass(frozen=True, slots=True)
class ImportSavepoint:
    created_count: int
    mutation_count: int


@dataclass(frozen=True, slots=True)
class RollbackReport:
    removed: int = 0
    restored: int = 0
    failures: tuple = ()
    leaked: tuple = ()

    @property
    def ok(self):
        return not self.failures and not self.leaked


class RollbackIncompleteError(RuntimeError):
    pass


def child_import_savepoint():
    transaction = current_import_transaction()
    return (transaction, transaction.savepoint()) if transaction is not None else (None, None)


def rollback_import_child(state, label):
    transaction, savepoint = state
    if transaction is None:
        return
    report = transaction.rollback_to(savepoint)
    rollback_error = rollback_report_message(report)
    if rollback_error:
        raise RuntimeError(f"{label} rollback incomplete: {rollback_error}")


def rollback_report_message(report):
    if report is None or report.ok:
        return ""
    details = [
        f"{label}: {detail}"
        for label, detail in report.failures
    ]
    details.extend(f"leaked {value}" for value in report.leaked)
    return "; ".join(details) or "rollback verification failed"


def require_complete_rollback(report):
    message = rollback_report_message(report)
    if message:
        raise RollbackIncompleteError(message)
    return report


@dataclass(slots=True)
class _MutationEntry:
    key: object
    label: str
    restore: object
    verify: object


def current_import_transaction():
    return _ACTIVE_IMPORT_TRANSACTION.get()


@contextmanager
def import_transaction_scope(transaction):
    current = current_import_transaction()
    if current is transaction:
        yield transaction
        return
    if current is not None:
        raise RuntimeError("A different import transaction is already active")
    token = _ACTIVE_IMPORT_TRANSACTION.set(transaction)
    try:
        yield transaction
    finally:
        _ACTIVE_IMPORT_TRANSACTION.reset(token)


def track_created_datablock(collection_name, value):
    transaction = current_import_transaction()
    if transaction is not None:
        transaction.track_created(collection_name, value)
    return value


def new_tracked_datablock(collection_name, *args, **kwargs):
    if bpy is None:
        raise RuntimeError("Tracked Blender datablock creation requires bpy")
    collection = getattr(bpy.data, str(collection_name), None)
    if collection is None or not hasattr(collection, "new"):
        raise AttributeError(f"bpy.data has no creatable collection {collection_name!r}")
    return track_created_datablock(
        collection_name,
        collection.new(*args, **kwargs),
    )


def track_mutation(key, restore, *, verify=None, label="mutation"):
    transaction = current_import_transaction()
    if transaction is not None:
        transaction.track_mutation(key, restore, verify=verify, label=label)
    return transaction


def _remove_datablock(collection_name, value):
    if bpy is None or value is None:
        return
    collection = getattr(bpy.data, collection_name, None)
    if collection is None:
        return
    try:
        collection.remove(value, do_unlink=True)
    except TypeError:
        try:
            collection.remove(value)
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            pass
    except (ReferenceError, RuntimeError, ValueError):
        pass


def _datablock_has_live_users(collection_name, value):
    try:
        return int(value.users) > 0
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False


def _invalidate_material_caches_after_rollback():
    try:
        from ..materials.blender.cache import clear_material_cache

        clear_material_cache(
            clear_persistent=False,
            reset_stats=False,
            clear_helpers=True,
        )
    except (ImportError, RuntimeError):
        pass


class DatablockImportTransaction:
    def __init__(self):
        self._snapshot = snapshot_datablocks()
        self._created = []
        self._created_keys = set()
        self._mutations = []
        self._mutation_keys = set()
        self._closed = False

    def scope(self):
        return import_transaction_scope(self)

    def savepoint(self):
        return ImportSavepoint(len(self._created), len(self._mutations))

    def track_created(self, collection_name, value):
        if self._closed or value is None:
            return value
        key = (str(collection_name), _datablock_identity(value))
        if key in self._created_keys:
            return value
        self._created_keys.add(key)
        self._created.append((str(collection_name), value, key))
        return value

    def track_mutation(self, key, restore, *, verify=None, label="mutation"):
        if self._closed or key in self._mutation_keys:
            return
        self._mutation_keys.add(key)
        self._mutations.append(_MutationEntry(key, str(label), restore, verify))

    def _accepted_created_identities(self, target):
        accepted = {}
        for collection_name, value, _key in self._created[:target]:
            accepted.setdefault(collection_name, set()).add(_datablock_identity(value))
        return accepted

    def _untracked_since_snapshot(self, target):
        if bpy is None:
            return []
        accepted = self._accepted_created_identities(target)
        discovered = []
        for name in _TRANSACTION_DATABLOCKS:
            collection = getattr(bpy.data, name, None)
            if collection is None:
                continue
            baseline = self._snapshot.get(name, frozenset())
            keep = accepted.get(name, set())
            for value in tuple(collection):
                identity = _datablock_identity(value)
                if identity not in baseline and identity not in keep:
                    discovered.append((name, value))
        return discovered

    def rollback_to(self, savepoint):
        if self._closed:
            return RollbackReport(failures=(("transaction", "closed"),))
        target_created = savepoint.created_count if isinstance(savepoint, ImportSavepoint) else int(savepoint)
        target_mutations = savepoint.mutation_count if isinstance(savepoint, ImportSavepoint) else 0
        target_created = max(0, min(target_created, len(self._created)))
        target_mutations = max(0, min(target_mutations, len(self._mutations)))
        failures = []
        restored = 0
        removed = 0
        leaked = []

        pending_mutations = self._mutations[target_mutations:]
        for entry in reversed(pending_mutations):
            try:
                entry.restore()
                if entry.verify is not None and not entry.verify():
                    raise RuntimeError("verification failed")
                restored += 1
            except Exception as error:
                failures.append((entry.label, str(error)))
        for entry in pending_mutations:
            self._mutation_keys.discard(entry.key)
        del self._mutations[target_mutations:]

        pending = self._created[target_created:]
        for collection_name, value, _key in reversed(pending):
            identity = _datablock_identity(value)
            label = f"{collection_name}:{getattr(value, 'name', identity)}"
            try:
                _remove_datablock(collection_name, value)
                collection = getattr(bpy.data, collection_name, ()) if bpy is not None else ()
                if any(
                    _datablock_identity(item) == identity
                    for item in tuple(collection)
                ):
                    leaked.append(label)
                    raise RuntimeError("datablock remains registered")
                removed += 1
            except Exception as error:
                failures.append((label, str(error)))
        for _collection_name, _value, key in pending:
            self._created_keys.discard(key)
        del self._created[target_created:]

        # Reconcile only after tracked child creations have been removed.  This
        # catches legacy/untracked leftovers from the failed child without
        # deleting shared material dependencies created by earlier successful
        # children in the same bulk import.
        for collection_name, value in reversed(
            self._untracked_since_snapshot(target_created)
        ):
            if _datablock_has_live_users(collection_name, value):
                continue
            identity = _datablock_identity(value)
            label = f"{collection_name}:{getattr(value, 'name', identity)}"
            try:
                _remove_datablock(collection_name, value)
                collection = getattr(bpy.data, collection_name, ()) if bpy is not None else ()
                if any(
                    _datablock_identity(item) == identity
                    for item in tuple(collection)
                ):
                    leaked.append(label)
                    raise RuntimeError("datablock remains registered")
                removed += 1
            except Exception as error:
                failures.append((label, str(error)))

        if pending or restored or removed:
            _invalidate_material_caches_after_rollback()

        return RollbackReport(
            removed,
            restored,
            tuple(failures),
            tuple(leaked),
        )

    def rollback(self):
        if self._closed:
            return RollbackReport()
        report = self.rollback_to(ImportSavepoint(0, 0))
        self._created.clear()
        self._created_keys.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
        self._closed = True
        return report

    def commit(self):
        self._created.clear()
        self._created_keys.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
        self._closed = True


class BlenderImportTransaction(DatablockImportTransaction):
    def __init__(self, *, capture_existing_state=True, restore_context=True):
        if bpy is None:
            raise RuntimeError("Blender import transactions require bpy")
        super().__init__()
        self._context_snapshot = None
        if restore_context:
            from .context import BlenderContextSnapshot
            self._context_snapshot = BlenderContextSnapshot().store()
        if capture_existing_state:
            self._collections = tuple(
                _collection_state(value)
                for value in getattr(bpy.data, "collections", ())
            )
            self._scene_roots = tuple(
                _collection_state(scene.collection)
                for scene in getattr(bpy.data, "scenes", ())
                if getattr(scene, "collection", None) is not None
            )
            self._objects = tuple(
                _object_state(value)
                for value in getattr(bpy.data, "objects", ())
            )
            self._meshes = tuple(
                _mesh_state(value)
                for value in getattr(bpy.data, "meshes", ())
            )
            self._armatures = tuple(
                _armature_state(value)
                for value in getattr(bpy.data, "armatures", ())
            )
            self._physx_scenes = tuple(
                state
                for state in (
                    _physx_scene_state(scene)
                    for scene in getattr(bpy.data, "scenes", ())
                )
                if state is not None
            )
        else:
            self._collections = ()
            self._scene_roots = ()
            self._objects = ()
            self._meshes = ()
            self._armatures = ()
            self._physx_scenes = ()

    def rollback(self):
        if self._closed:
            return RollbackReport()
        _force_object_mode()
        report = super().rollback_to(ImportSavepoint(0, 0))
        self._restore_existing_state()
        if self._context_snapshot is not None:
            self._context_snapshot.restore()
        self._created.clear()
        self._created_keys.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
        self._closed = True
        return report

    def _restore_existing_state(self):
        for state in (*self._collections, *self._scene_roots):
            owner = state.owner
            try:
                _restore_links(owner.children, state.children)
                _restore_links(owner.objects, state.objects)
                restore_id_properties(owner, state.properties)
                if state.hide_viewport is not None:
                    owner.hide_viewport = state.hide_viewport
                if state.hide_render is not None:
                    owner.hide_render = state.hide_render
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass

        for state in self._objects:
            owner = state.owner
            if not _owner_exists(owner, "objects"):
                continue
            try:
                owner.data = state.data
                owner.parent = state.parent
                if state.matrix_world is not None:
                    owner.matrix_world = state.matrix_world
                restore_id_properties(owner, state.properties)
                if state.hide_viewport is not None:
                    owner.hide_viewport = state.hide_viewport
                if state.hide_select is not None:
                    owner.hide_select = state.hide_select
                if state.hide_render is not None:
                    owner.hide_render = state.hide_render
                if state.hide_get is not None:
                    owner.hide_set(state.hide_get)
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass

        for state in self._meshes:
            owner = state.owner
            if not _owner_exists(owner, "meshes"):
                continue
            try:
                owner.materials.clear()
                for material in state.materials:
                    owner.materials.append(material)
                restore_id_properties(owner, state.properties)
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass

        for state in self._physx_scenes:
            physx = getattr(state.owner, "physx", None)
            actors = getattr(physx, "actors", None) if physx is not None else None
            if actors is None:
                continue
            expected = {
                _datablock_identity(obj)
                for obj in state.actor_refs
                if obj is not None
            }
            for index in range(len(actors) - 1, -1, -1):
                obj = getattr(actors[index], "obj_ref", None)
                if obj is None or _datablock_identity(obj) not in expected:
                    try:
                        actors.remove(index)
                    except (AttributeError, IndexError, RuntimeError, TypeError):
                        pass
            try:
                if state.actor_list_index is not None:
                    physx.actor_list_index = state.actor_list_index
                if state.active_actor_count is not None:
                    physx.active_actor_count = state.active_actor_count
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass

        for state in self._armatures:
            owner = state.owner
            if not _owner_exists(owner, "armatures"):
                continue
            try:
                restore_id_properties(owner, state.properties)
                if state.pose_position is not None:
                    owner.pose_position = state.pose_position
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass
