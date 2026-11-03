from __future__ import annotations

import copy
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
<<<<<<< Updated upstream

try:
    import bpy
except ImportError:
    bpy = None


_ACTIVE_IMPORT_TRANSACTION = ContextVar("cp77_active_import_transaction", default=None)
=======
from functools import wraps

import bpy

from ..core.log import debug_exception, get_logger, log_once
from .identity import rna_identity, rna_is_live

_ACTIVE_IMPORT_TRANSACTION = ContextVar("cp77_active_import_transaction", default=None)
_LOG = get_logger(__name__)
>>>>>>> Stashed changes


_TRANSACTION_DATABLOCKS = (
    "objects",
    "scenes",
    "collections",
    "meshes",
    "curves",
<<<<<<< Updated upstream
    "armatures",
    "lattices",
    "lights",
=======
    "hair_curves",
    "armatures",
    "lattices",
    "lights",
    "lightprobes",
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
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
=======
def _datablock_label(collection_name, value, identity=None):
    if identity is None:
        identity = rna_identity(value)
    try:
        name = value.name
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
            ("_datablock_label", type(error).__name__),
            "datablock label: fell back after %s",
            error,
            exc_info=True,
        )
        name = identity
    return f"{collection_name}:{name}"


# Run after a rollback with the bpy.data collection names it removed datablocks from, by the cache that registered them.
_ROLLBACK_HOOKS = {}
# Scenes need Blender's per-item guards; shape keys are freed with their owner.
_PER_ITEM_REMOVAL = frozenset({"scenes", "shape_keys"})


def snapshot_datablocks():
    return {
        name: frozenset(rna_identity(value) for value in getattr(bpy.data, name, ()))
>>>>>>> Stashed changes
        for name in _TRANSACTION_DATABLOCKS
        if hasattr(bpy.data, name)
    }


<<<<<<< Updated upstream
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
=======
def _snapshot_id_property_value(value):
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return {
            key: _snapshot_id_property_value(item) for key, item in to_dict().items()
        }
    to_list = getattr(value, "to_list", None)
    if callable(to_list):
        return [_snapshot_id_property_value(item) for item in to_list()]
    if isinstance(value, dict):
        return {key: _snapshot_id_property_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_snapshot_id_property_value(item) for item in value]
    try:
        return copy.deepcopy(value)
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
            ("_snapshot_id_property_value", type(error).__name__),
            "snapshot id property value: fell back after %s",
            error,
            exc_info=True,
        )
        return value


def _id_property_values_equal(current, expected):
    try:
        current = _snapshot_id_property_value(current)
        result = current == expected
        if isinstance(result, bool):
            return result
        return bool(result)
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
            ("_id_property_values_equal", type(error).__name__),
            "id property values equal: fell back after %s",
            error,
            exc_info=True,
        )
        return False
>>>>>>> Stashed changes


def snapshot_id_properties(owner):
    if owner is None:
        return None
    try:
        keys = tuple(owner.keys())
<<<<<<< Updated upstream
    except (AttributeError, ReferenceError, TypeError):
=======
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("snapshot_id_properties 1", type(error).__name__),
            "snapshot id properties: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return None
    snapshot = {}
    for key in keys:
        try:
<<<<<<< Updated upstream
            snapshot[key] = copy.deepcopy(owner[key])
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            try:
                snapshot[key] = owner[key]
            except (AttributeError, KeyError, ReferenceError, TypeError):
                pass
=======
            snapshot[key] = _snapshot_id_property_value(owner[key])
        except (
            AttributeError,
            KeyError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("snapshot_id_properties 2", type(error).__name__),
                "snapshot id properties: fell back after %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes
    return snapshot


def restore_id_properties(owner, snapshot):
    if owner is None or snapshot is None:
        return
    try:
<<<<<<< Updated upstream
        for key in tuple(owner.keys()):
            del owner[key]
        for key, value in snapshot.items():
            owner[key] = value
    except (AttributeError, ReferenceError, TypeError):
        pass
=======
        current_keys = tuple(owner.keys())
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("restore_id_properties 1", type(error).__name__),
            "restore id properties: fell back after %s",
            error,
            exc_info=True,
        )
        return

    expected_keys = set(snapshot)
    for key in current_keys:
        if key not in expected_keys:
            try:
                del owner[key]
            except (
                AttributeError,
                KeyError,
                ReferenceError,
                RuntimeError,
                TypeError,
            ) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("restore_id_properties 2", type(error).__name__),
                    "restore id properties: fell back after %s",
                    error,
                    exc_info=True,
                )

    for key, value in snapshot.items():
        try:
            current = owner[key]
        except (
            AttributeError,
            KeyError,
            ReferenceError,
            RuntimeError,
            TypeError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("restore_id_properties 3", type(error).__name__),
                "restore id properties: fell back after %s",
                error,
                exc_info=True,
            )
            current = None
            exists = False
        else:
            exists = True
        if exists and _id_property_values_equal(current, value):
            continue
        try:
            owner[key] = _snapshot_id_property_value(value)
        except (
            AttributeError,
            KeyError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("restore_id_properties 4", type(error).__name__),
                "restore id properties: fell back after %s",
                error,
                exc_info=True,
            )


def snapshot_id_property(owner, key):
    """(True, value) with a plain copy of owner's ID property key, or (False, None)"""
    try:
        if key not in owner:
            return False, None
        value = owner[key]
    except (AttributeError, KeyError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("snapshot_id_property", type(error).__name__),
            "snapshot id property: fell back after %s",
            error,
            exc_info=True,
        )
        return False, None
    plain = getattr(value, "to_dict", None) or getattr(value, "to_list", None)
    return True, plain() if callable(plain) else value


def restore_id_property(owner, key, snapshot) -> None:
    """Give owner its ID property key back as snapshot (snapshot_id_property) found it, or remove it"""
    existed, value = snapshot
    try:
        if existed:
            owner[key] = value
        elif key in owner:
            del owner[key]
    except (AttributeError, KeyError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("restore_id_property", type(error).__name__),
            "restore id property: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
    except (AttributeError, ReferenceError):
=======
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_copy_matrix", type(error).__name__),
            "copy matrix: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
def _object_state(obj):
    try:
        hidden = obj.hide_get()
    except (AttributeError, ReferenceError, TypeError):
=======
def _restore_collection_state(state):
    owner = state.owner
    try:
        _restore_links(owner.children, state.children)
        _restore_links(owner.objects, state.objects)
        restore_id_properties(owner, state.properties)
        if state.hide_viewport is not None:
            owner.hide_viewport = state.hide_viewport
        if state.hide_render is not None:
            owner.hide_render = state.hide_render
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_restore_collection_state", type(error).__name__),
            "restore collection state: fell back after %s",
            error,
            exc_info=True,
        )


def _collection_links_match(state):
    owner = state.owner
    try:
        return {rna_identity(value) for value in owner.children} == {
            rna_identity(value) for value in state.children
        } and {rna_identity(value) for value in owner.objects} == {
            rna_identity(value) for value in state.objects
        }
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_collection_links_match", type(error).__name__),
            "collection links match: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _object_state(obj):
    try:
        hidden = obj.hide_get()
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_object_state", type(error).__name__),
            "object state: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
=======
def _restore_object_state(state):
    owner = state.owner
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
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_restore_object_state", type(error).__name__),
            "restore object state: fell back after %s",
            error,
            exc_info=True,
        )


>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    if bpy is None:
        return
=======
>>>>>>> Stashed changes
    context = getattr(bpy, "context", None)
    if context is None or getattr(context, "mode", "OBJECT") == "OBJECT":
        return
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
<<<<<<< Updated upstream
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
=======
    except (AttributeError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_force_object_mode", type(error).__name__),
            "force object mode: fell back after %s",
            error,
            exc_info=True,
        )


def _restore_links(link_collection, expected):
    expected_ids = {rna_identity(value) for value in expected}
    for value in _safe_tuple(link_collection):
        if rna_identity(value) not in expected_ids:
            try:
                link_collection.unlink(value)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_restore_links 1", type(error).__name__),
                    "restore links: fell back after %s",
                    error,
                    exc_info=True,
                )
    current_ids = {rna_identity(value) for value in _safe_tuple(link_collection)}
    for value in expected:
        identity = rna_identity(value)
>>>>>>> Stashed changes
        if identity in current_ids:
            continue
        try:
            link_collection.link(value)
            current_ids.add(identity)
<<<<<<< Updated upstream
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass
=======
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_restore_links 2", type(error).__name__),
                "restore links: fell back after %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
class RollbackIncompleteError(RuntimeError):
    pass


def child_import_savepoint():
    transaction = current_import_transaction()
    return (transaction, transaction.savepoint()) if transaction is not None else (None, None)
=======
def child_import_savepoint():
    transaction = current_import_transaction()
    return (
        (transaction, transaction.savepoint())
        if transaction is not None
        else (None, None)
    )
>>>>>>> Stashed changes


def rollback_import_child(state, label):
    transaction, savepoint = state
    if transaction is None:
        return
<<<<<<< Updated upstream
    report = transaction.rollback_to(savepoint)
    rollback_error = rollback_report_message(report)
    if rollback_error:
        raise RuntimeError(f"{label} rollback incomplete: {rollback_error}")
=======
    raise_if_rollback_incomplete(transaction.rollback_to(savepoint), label=label)
>>>>>>> Stashed changes


def rollback_report_message(report):
    if report is None or report.ok:
        return ""
<<<<<<< Updated upstream
    details = [
        f"{label}: {detail}"
        for label, detail in report.failures
    ]
=======
    details = [f"{label}: {detail}" for label, detail in report.failures]
>>>>>>> Stashed changes
    details.extend(f"leaked {value}" for value in report.leaked)
    return "; ".join(details) or "rollback verification failed"


<<<<<<< Updated upstream
def require_complete_rollback(report):
    message = rollback_report_message(report)
    if message:
        raise RollbackIncompleteError(message)
    return report
=======
def raise_if_rollback_incomplete(
    report, error=None, *, label="", error_type=RuntimeError
) -> None:
    """Raise error_type when the rollback report left changes behind"""
    message = rollback_report_message(report)
    if not message:
        return
    text = (
        f"{label} rollback incomplete: {message}"
        if label
        else f"rollback incomplete: {message}"
    )
    if error is None:
        raise error_type(text)
    raise error_type(f"{error}; {text}") from error
>>>>>>> Stashed changes


@dataclass(slots=True)
class _MutationEntry:
    key: object
    label: str
    restore: object
    verify: object


def current_import_transaction():
    return _ACTIVE_IMPORT_TRANSACTION.get()


<<<<<<< Updated upstream
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


=======
>>>>>>> Stashed changes
def track_created_datablock(collection_name, value):
    transaction = current_import_transaction()
    if transaction is not None:
        transaction.track_created(collection_name, value)
    return value


def new_tracked_datablock(collection_name, *args, **kwargs):
<<<<<<< Updated upstream
    if bpy is None:
        raise RuntimeError("Tracked Blender datablock creation requires bpy")
    collection = getattr(bpy.data, str(collection_name), None)
    if collection is None or not hasattr(collection, "new"):
        raise AttributeError(f"bpy.data has no creatable collection {collection_name!r}")
=======
    collection = getattr(bpy.data, str(collection_name), None)
    if collection is None or not hasattr(collection, "new"):
        raise AttributeError(
            f"bpy.data has no creatable collection {collection_name!r}"
        )
>>>>>>> Stashed changes
    return track_created_datablock(
        collection_name,
        collection.new(*args, **kwargs),
    )


def track_mutation(key, restore, *, verify=None, label="mutation"):
    transaction = current_import_transaction()
    if transaction is not None:
        transaction.track_mutation(key, restore, verify=verify, label=label)
    return transaction


<<<<<<< Updated upstream
def _remove_datablock(collection_name, value):
    if bpy is None or value is None:
=======
def track_collection_state(collection, *, label="collection state"):
    """Restore links, ID properties and visibility of an existing collection on rollback"""
    transaction = current_import_transaction()
    if transaction is None or collection is None:
        return transaction
    state = _collection_state(collection)
    transaction.track_mutation(
        ("collection_state", rna_identity(collection)),
        lambda state=state: _restore_collection_state(state),
        verify=lambda state=state: _collection_links_match(state),
        label=label,
    )
    return transaction


def track_object_state(obj, *, label="object state"):
    """Restore data, parent, world matrix, ID properties and visibility of an existing object on rollback"""
    transaction = current_import_transaction()
    if transaction is None or obj is None:
        return transaction
    state = _object_state(obj)
    transaction.track_mutation(
        ("object_state", rna_identity(obj)),
        lambda state=state: (
            _restore_object_state(state) if rna_is_live(state.owner) else None
        ),
        label=label,
    )
    return transaction


def track_created_since(snapshot):
    """Track every datablock missing from a snapshot_datablocks() result as created"""
    transaction = current_import_transaction()
    if transaction is None:
        return ()
    created = []
    for name in _TRANSACTION_DATABLOCKS:
        collection = getattr(bpy.data, name, None)
        if collection is None:
            continue
        baseline = snapshot.get(name, frozenset())
        for value in tuple(collection):
            if rna_identity(value) not in baseline:
                transaction.track_created(name, value)
                created.append((name, value))
    return tuple(created)


def _remove_datablock(collection_name, value):
    if value is None:
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
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
=======
def _remove_datablocks(entries):
    """Remove (collection_name, value) entries and verify each is gone"""
    live = [(name, value) for name, value in entries if rna_is_live(value)]
    batched = [value for name, value in live if name not in _PER_ITEM_REMOVAL]
    if batched:
        try:
            bpy.data.batch_remove(batched)
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            pass
    errors = {}
    for name, value in live:
        if rna_is_live(value):
            try:
                _remove_datablock(name, value)
            except Exception as error:
                debug_exception(
                    _LOG,
                    "Could not remove %s %s during rollback",
                    name,
                    rna_identity(value),
                )
                errors[rna_identity(value)] = str(error)
    removed = 0
    removed_types = set()
    failures = []
    leaked = []
    for name, value in live:
        if rna_is_live(value):
            label = _datablock_label(name, value)
            leaked.append(label)
            failures.append(
                (
                    label,
                    errors.get(rna_identity(value), "datablock remains registered"),
                )
            )
        else:
            removed += 1
            removed_types.add(name)
    return removed, removed_types, failures, leaked


def _datablock_has_live_users(value):
    try:
        return int(value.users) > 0
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_datablock_has_live_users", type(error).__name__),
            "datablock has live users: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def register_rollback_hook(name, hook):
    """Have hook(removed_types) run after each rollback that removed datablocks"""
    _ROLLBACK_HOOKS[str(name)] = hook


def _run_rollback_hooks(removed_types):
    for name, hook in tuple(_ROLLBACK_HOOKS.items()):
        try:
            hook(frozenset(removed_types))
        except RuntimeError:
            debug_exception(_LOG, "Rollback hook %s failed", name)
>>>>>>> Stashed changes


class DatablockImportTransaction:
    def __init__(self):
        self._snapshot = snapshot_datablocks()
        self._created = []
<<<<<<< Updated upstream
        self._created_keys = set()
        self._mutations = []
        self._mutation_keys = set()
        self._closed = False

    def scope(self):
        return import_transaction_scope(self)
=======
        self._created_values = {}
        self._mutations = []
        self._mutation_keys = set()
        self._commit_cleanup = []
        self._finalizers = []
        self._closed = False

    @contextmanager
    def scope(self):
        current = current_import_transaction()
        if current is self:
            yield self
            return
        if current is not None:
            raise RuntimeError("A different import transaction is already active")
        token = _ACTIVE_IMPORT_TRANSACTION.set(self)
        try:
            yield self
        finally:
            _ACTIVE_IMPORT_TRANSACTION.reset(token)
>>>>>>> Stashed changes

    def savepoint(self):
        return ImportSavepoint(len(self._created), len(self._mutations))

    def track_created(self, collection_name, value):
        if self._closed or value is None:
            return value
<<<<<<< Updated upstream
        key = (str(collection_name), _datablock_identity(value))
        if key in self._created_keys:
            return value
        self._created_keys.add(key)
=======
        key = (str(collection_name), rna_identity(value))
        if self._created_values.get(key) is value:
            return value
        # Blender reuses a freed datablock's address for the next one it allocates, so a known key held by another
        # value means that datablock is gone and this one has not been tracked yet.
        self._created_values[key] = value
>>>>>>> Stashed changes
        self._created.append((str(collection_name), value, key))
        return value

    def track_mutation(self, key, restore, *, verify=None, label="mutation"):
        if self._closed or key in self._mutation_keys:
            return
        self._mutation_keys.add(key)
        self._mutations.append(_MutationEntry(key, str(label), restore, verify))

<<<<<<< Updated upstream
    def _accepted_created_identities(self, target):
        accepted = {}
        for collection_name, value, _key in self._created[:target]:
            accepted.setdefault(collection_name, set()).add(_datablock_identity(value))
        return accepted

    def _untracked_since_snapshot(self, target):
        if bpy is None:
            return []
=======
    def defer_commit_cleanup(self, callback):
        """Release superseded data only after rollback no longer needs it"""
        if not self._closed:
            self._commit_cleanup.append(callback)

    def defer_finalizer(self, callback):
        """Run callback once the import is complete, before commit"""
        if not self._closed:
            self._finalizers.append(callback)

    def _run_finalizers(self):
        while self._finalizers:
            finalizers, self._finalizers = self._finalizers, []
            with self.scope():
                for callback in finalizers:
                    try:
                        callback()
                    except Exception as error:
                        _LOG.exception("Import finalizer failed: %s", error)

    def _accepted_created_identities(self, target):
        accepted = {}
        for collection_name, value, _key in self._created[:target]:
            accepted.setdefault(collection_name, set()).add(rna_identity(value))
        return accepted

    def _untracked_since_snapshot(self, target):
>>>>>>> Stashed changes
        accepted = self._accepted_created_identities(target)
        discovered = []
        for name in _TRANSACTION_DATABLOCKS:
            collection = getattr(bpy.data, name, None)
            if collection is None:
                continue
            baseline = self._snapshot.get(name, frozenset())
            keep = accepted.get(name, set())
            for value in tuple(collection):
<<<<<<< Updated upstream
                identity = _datablock_identity(value)
=======
                identity = rna_identity(value)
>>>>>>> Stashed changes
                if identity not in baseline and identity not in keep:
                    discovered.append((name, value))
        return discovered

    def rollback_to(self, savepoint):
        if self._closed:
            return RollbackReport(failures=(("transaction", "closed"),))
<<<<<<< Updated upstream
        target_created = savepoint.created_count if isinstance(savepoint, ImportSavepoint) else int(savepoint)
        target_mutations = savepoint.mutation_count if isinstance(savepoint, ImportSavepoint) else 0
=======
        target_created = (
            savepoint.created_count
            if isinstance(savepoint, ImportSavepoint)
            else int(savepoint)
        )
        target_mutations = (
            savepoint.mutation_count if isinstance(savepoint, ImportSavepoint) else 0
        )
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
                debug_exception(_LOG, "Could not roll back %s", entry.label)
>>>>>>> Stashed changes
                failures.append((entry.label, str(error)))
        for entry in pending_mutations:
            self._mutation_keys.discard(entry.key)
        del self._mutations[target_mutations:]

        pending = self._created[target_created:]
<<<<<<< Updated upstream
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
=======
        removed += sum(1 for _name, value, _key in pending if not rna_is_live(value))
        count, removed_types, removal_failures, removal_leaks = _remove_datablocks(
            (collection_name, value)
            for collection_name, value, _key in reversed(pending)
        )
        removed += count
        failures.extend(removal_failures)
        leaked.extend(removal_leaks)
        for _collection_name, value, key in pending:
            if self._created_values.get(key) is value:
                del self._created_values[key]
        del self._created[target_created:]

        # Remove what the failed child left untracked, repeating until a pass removes nothing.
        untracked = list(reversed(self._untracked_since_snapshot(target_created)))
        while untracked:
            unused = [
                (collection_name, value)
                for collection_name, value in untracked
                if not _datablock_has_live_users(value)
            ]
            if not unused:
                break
            count, untracked_types, removal_failures, removal_leaks = (
                _remove_datablocks(unused)
            )
            removed += count
            removed_types |= untracked_types
            failures.extend(removal_failures)
            leaked.extend(removal_leaks)
            if removal_failures:
                break
            untracked = [
                (collection_name, value)
                for collection_name, value in untracked
                if rna_is_live(value)
            ]

        if removed_types:
            _run_rollback_hooks(removed_types)
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
        self._created_keys.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
=======
        self._created_values.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
        self._commit_cleanup.clear()
        self._finalizers.clear()
>>>>>>> Stashed changes
        self._closed = True
        return report

    def commit(self):
<<<<<<< Updated upstream
        self._created.clear()
        self._created_keys.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
=======
        self._run_finalizers()
        for callback in self._commit_cleanup:
            callback()
        self._commit_cleanup.clear()
        self._created.clear()
        self._created_values.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
        self._commit_cleanup.clear()
>>>>>>> Stashed changes
        self._closed = True


class BlenderImportTransaction(DatablockImportTransaction):
    def __init__(self, *, capture_existing_state=True, restore_context=True):
<<<<<<< Updated upstream
        if bpy is None:
            raise RuntimeError("Blender import transactions require bpy")
=======
>>>>>>> Stashed changes
        super().__init__()
        self._context_snapshot = None
        if restore_context:
            from .context import BlenderContextSnapshot
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
                _object_state(value) for value in getattr(bpy.data, "objects", ())
            )
            self._meshes = tuple(
                _mesh_state(value) for value in getattr(bpy.data, "meshes", ())
            )
            self._armatures = tuple(
                _armature_state(value) for value in getattr(bpy.data, "armatures", ())
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        self._created_keys.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
=======
        self._created_values.clear()
        self._mutations.clear()
        self._mutation_keys.clear()
        self._commit_cleanup.clear()
        self._finalizers.clear()
>>>>>>> Stashed changes
        self._closed = True
        return report

    def _restore_existing_state(self):
        for state in (*self._collections, *self._scene_roots):
<<<<<<< Updated upstream
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
=======
            _restore_collection_state(state)

        for state in self._objects:
            if rna_is_live(state.owner):
                _restore_object_state(state)

        for state in self._meshes:
            owner = state.owner
            if not rna_is_live(owner):
>>>>>>> Stashed changes
                continue
            try:
                owner.materials.clear()
                for material in state.materials:
                    owner.materials.append(material)
                restore_id_properties(owner, state.properties)
<<<<<<< Updated upstream
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass
=======
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    (
                        "BlenderImportTransaction._restore_existing_state 1",
                        type(error).__name__,
                    ),
                    "restore existing state: fell back after %s",
                    error,
                    exc_info=True,
                )
>>>>>>> Stashed changes

        for state in self._physx_scenes:
            physx = getattr(state.owner, "physx", None)
            actors = getattr(physx, "actors", None) if physx is not None else None
            if actors is None:
                continue
            expected = {
<<<<<<< Updated upstream
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
=======
                rna_identity(obj) for obj in state.actor_refs if obj is not None
            }
            for index in range(len(actors) - 1, -1, -1):
                obj = getattr(actors[index], "obj_ref", None)
                if obj is None or rna_identity(obj) not in expected:
                    try:
                        actors.remove(index)
                    except (
                        AttributeError,
                        IndexError,
                        RuntimeError,
                        TypeError,
                    ) as error:
                        log_once(
                            _LOG,
                            "DEBUG",
                            (
                                "BlenderImportTransaction._restore_existing_state 2",
                                type(error).__name__,
                            ),
                            "restore existing state: fell back after %s",
                            error,
                            exc_info=True,
                        )
>>>>>>> Stashed changes
            try:
                if state.actor_list_index is not None:
                    physx.actor_list_index = state.actor_list_index
                if state.active_actor_count is not None:
                    physx.active_actor_count = state.active_actor_count
<<<<<<< Updated upstream
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass

        for state in self._armatures:
            owner = state.owner
            if not _owner_exists(owner, "armatures"):
=======
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    (
                        "BlenderImportTransaction._restore_existing_state 3",
                        type(error).__name__,
                    ),
                    "restore existing state: fell back after %s",
                    error,
                    exc_info=True,
                )

        for state in self._armatures:
            owner = state.owner
            if not rna_is_live(owner):
>>>>>>> Stashed changes
                continue
            try:
                restore_id_properties(owner, state.properties)
                if state.pose_position is not None:
                    owner.pose_position = state.pose_position
<<<<<<< Updated upstream
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass
=======
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    (
                        "BlenderImportTransaction._restore_existing_state 4",
                        type(error).__name__,
                    ),
                    "restore existing state: fell back after %s",
                    error,
                    exc_info=True,
                )


def _failed(result) -> bool:
    from .operator_results import OperationResult

    return isinstance(result, OperationResult) and not result.ok


def _rollback_transaction(
    transaction, label: str, error: BaseException | None = None
) -> None:
    report = transaction.rollback()
    if not report.ok:
        _LOG.error("%s rollback incomplete: %s", label, rollback_report_message(report))
    raise_if_rollback_incomplete(report, error, label=label)


def transactional(label: str):
    """Run a tool use case so that a failure leaves the file unchanged"""

    def decorator(function):
        @wraps(function)
        def run(*args, **kwargs):
            if current_import_transaction() is not None:
                state = child_import_savepoint()
                try:
                    result = function(*args, **kwargs)
                except Exception:
                    rollback_import_child(state, label)
                    raise
                if _failed(result):
                    rollback_import_child(state, label)
                return result
            transaction = BlenderImportTransaction(capture_existing_state=False)
            try:
                with transaction.scope():
                    result = function(*args, **kwargs)
            except Exception as error:
                _rollback_transaction(transaction, label, error)
                raise
            if _failed(result):
                _rollback_transaction(transaction, label)
            else:
                transaction.commit()
            return result

        return run

    return decorator
>>>>>>> Stashed changes
