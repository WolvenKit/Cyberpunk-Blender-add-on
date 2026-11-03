from __future__ import annotations

import bpy

from ...blender.collections import collection_parent_map
from ...blender.identity import rna_identity
from ...blender.import_hooks import after_import, before_import
from ...blender.operator_results import OperationResult
from ...blender.transactions import (
    track_collection_state,
    track_created_datablock,
    track_mutation,
    transactional,
)
from ...entity.model.import_record import IMPORT_RECORD_KEY
from ...importers.common.collections import remap_copied_object_references
from ..blender import mesh_appearance
from ..blender.rigs import reconcile_appearance_rig
from ..blender.scene import appearance_record, component_objects, holds_imported_lights
from ..blender.state import (
    component_mesh_path,
    ensure_appearance_state,
    load_documents,
    remember_applied,
)
from ..runtime.scene_cache import clear_entity_caches, entity_index
from ..runtime.updates import suspended
from .components import entity_armature, shared_mesh_objects, track_item, write_values

_STATE_FIELDS = (
    "key_name",
    "key_cruid",
    "template_name",
    "template_cruid",
    "name",
    "enabled",
    "type_key",
    "mesh",
    "base_mesh",
    "mesh_appearance",
    "chunk_mask",
    "attach_target",
    "attach_slot",
    "skin_target",
    "removed",
    "applied",
)


def _entity_collections(collection):
    index = entity_index()
    record = index.record(collection)
    return index.collections(record.import_id) if record is not None else (collection,)


def _states(collection):
    return [
        (other, ensure_appearance_state(other))
        for other in _entity_collections(collection)
    ]


def _name_taken(collection, name: str) -> bool:
    """Whether another appearance of the entity, in the scene or in its .app, already has name"""
    if any(
        state.name == name and not state.removed
        for _other, state in _states(collection)
    ):
        return True
    app, _ent = load_documents(collection)
    origins = {
        state.origin
        for _other, state in _states(collection)
        if state.origin and state.name != state.origin
    }
    return name in app.appearance_names() and name not in origins


def copied_entry_name(state, name: str) -> str:
    """The entry name of a copy named name of the appearance state"""
    prefix = (
        state.entry_name[: -len(state.name)]
        if state.entry_name.endswith(state.name)
        else ""
    )
    return f"{prefix}{name}"


def _track_state(collection, keys) -> None:
    state = collection.cp77_entity_state
    previous = {key: getattr(state, key) for key in keys}

    def restore():
        with suspended():
            for key, value in previous.items():
                setattr(collection.cp77_entity_state, key, value)

    track_mutation(
        ("enttools-appearance", rna_identity(collection), tuple(keys)),
        restore,
        label="Entity appearance",
    )


def select_appearance(context, collection) -> None:
    """Point the panel at collection's entity and appearance"""
    tools = context.scene.cp77_entity_tools
    with suspended():
        tools.entity = appearance_record(collection).import_id
        tools.appearance = collection.name


def _show_only(target, collections) -> None:
    for collection in collections:
        track_collection_state(collection, label="Entity appearance visibility")
        visible = collection == target
        collection.hide_viewport = not visible
        collection.hide_render = not visible


@transactional("Switch entity appearance")
def switch_appearance(context, import_id: str, appearance: str) -> OperationResult:
    collections = entity_index().collections(import_id)
    if not collections:
        return OperationResult.cancelled(
            "The entity's appearances are no longer in the scene"
        )
    target = next(
        (
            collection
            for collection in collections
            if ensure_appearance_state(collection).name == appearance
            and not collection.cp77_entity_state.removed
        ),
        None,
    )
    if target is None:
        from ...importers.entity.execution import import_entity
        from ...importers.entity.options import EntityImportRequest

        record = appearance_record(collections[0])
        parents = collection_parent_map().get(collections[0].as_pointer(), ())
        imported = []
        before = before_import(context.scene)
        result = import_entity(
            EntityImportRequest(
                with_materials=True,
                filepath=record.ent_path,
                appearances=(appearance,),
                include_animations=False,
                # An entity imported with its lights switches to an appearance with its lights; channels follow them.
                include_lights=holds_imported_lights(collections),
                existing_rig=entity_armature(collections[0]),
                parent_collection_name=parents[0].name if parents else "",
                imported_collections_out=imported,
                import_id=import_id,
                transactional=False,
            )
        )
        if not result.ok or not imported:
            return OperationResult.cancelled(
                "Appearance import failed: "
                + "; ".join(result.failures or result.warnings)
            )
        after_import(context.scene, before)
        target = imported[-1]
        clear_entity_caches()
        collections = entity_index().collections(import_id)
    try:
        reconcile_appearance_rig(target, entity_armature(target))
    except Exception as error:
        return OperationResult.cancelled(
            f"Appearance rig update failed: {error}", error=error
        )
    _show_only(target, collections)
    select_appearance(context, target)
    return OperationResult.finished(f"Showing {appearance}.")


def _copy_tree(source, parent, object_map, copied_collections):
    copy = track_created_datablock("collections", bpy.data.collections.new(source.name))
    for key in source.keys():
        if key != "cp77_entity_state":
            copy[key] = source[key]
    track_collection_state(parent, label="Entity appearance")
    parent.children.link(copy)
    copied_collections[source.as_pointer()] = copy
    for obj in source.objects:
        duplicate = object_map.get(obj)
        if duplicate is None:
            duplicate = track_created_datablock("objects", obj.copy())
            object_map[obj] = duplicate
        copy.objects.link(duplicate)
    for child in source.children:
        _copy_tree(child, copy, object_map, copied_collections)
    return copy


@transactional("Duplicate entity appearance")
def duplicate_appearance(
    context, collection, new_name: str, entry_name: str
) -> OperationResult:
    state = ensure_appearance_state(collection)
    new_name = new_name.strip()
    if not new_name:
        return OperationResult.cancelled("An appearance needs a name")
    if _name_taken(collection, new_name):
        return OperationResult.cancelled(
            f'An appearance named "{new_name}" already exists'
        )
    parents = collection_parent_map().get(collection.as_pointer(), ())
    parent = parents[0] if parents else context.scene.collection
    object_map = {}
    copied_collections = {}
    copy = _copy_tree(collection, parent, object_map, copied_collections)
    copy.name = (
        f"{collection.name.rsplit(state.name, 1)[0]}{new_name}"
        if state.name in collection.name
        else new_name
    )
    remap_copied_object_references(list(object_map.values()), object_map)
    copy[IMPORT_RECORD_KEY] = collection[IMPORT_RECORD_KEY]
    clear_entity_caches()
    with suspended():
        target = copy.cp77_entity_state
        target.components.clear()
        for item in state.components:
            duplicate = target.components.add()
            for field in _STATE_FIELDS:
                setattr(duplicate, field, getattr(item, field))
            holder = (
                copied_collections.get(item.mesh_collection.as_pointer())
                if item.mesh_collection
                else None
            )
            duplicate.mesh_collection = holder
            duplicate.mesh_collection_name = holder.name if holder is not None else ""
            # A mesh renamed before the copy keeps its new file in the copy, with the original as its base.
            mesh = component_mesh_path(item)
            if mesh != item.mesh:
                duplicate.mesh = mesh
                duplicate.base_mesh = item.base_mesh or item.mesh
        target.name = new_name
        target.entry_name = entry_name.strip() or copied_entry_name(state, new_name)
        target.source_name = state.source_name
        target.origin = ""
        target.is_default = False
        target.initialized = True
    _show_only(copy, _entity_collections(collection))
    select_appearance(context, copy)
    return OperationResult.finished(f"Duplicated {state.name} as {new_name}.")


@transactional("Rename entity appearance")
def rename_appearance(
    collection, new_name: str, entry_name: str = ""
) -> OperationResult:
    state = ensure_appearance_state(collection)
    new_name = new_name.strip()
    if not new_name:
        return OperationResult.cancelled("An appearance needs a name")
    if new_name != state.name and _name_taken(collection, new_name):
        return OperationResult.cancelled(
            f'An appearance named "{new_name}" already exists'
        )
    _track_state(collection, ("name", "entry_name"))
    with suspended():
        state.name = new_name
        if entry_name.strip():
            state.entry_name = entry_name.strip()
    return OperationResult.finished(f"Renamed the appearance to {new_name}.")


@transactional("Remove entity appearance")
def remove_appearance(collection) -> OperationResult:
    state = ensure_appearance_state(collection)
    if state.is_default:
        return OperationResult.cancelled("Make another appearance the default first")
    _track_state(collection, ("removed",))
    with suspended():
        state.removed = True
    track_collection_state(collection, label="Entity appearance visibility")
    collection.hide_viewport = True
    collection.hide_render = True
    return OperationResult.finished(f"Removed the appearance {state.name}.")


@transactional("Make entity appearance default")
def make_default(collection) -> OperationResult:
    for other, state in _states(collection):
        _track_state(other, ("is_default",))
        with suspended():
            state.is_default = other == collection
    return OperationResult.finished(
        f"{collection.cp77_entity_state.name} is the default appearance."
    )


@transactional("New mesh appearance")
def new_mesh_appearance(collection, index: int, name: str) -> OperationResult:
    item = ensure_appearance_state(collection).components[index]
    objects = component_objects(collection, item.name)
    name = name.strip()
    names = mesh_appearance.mesh_appearance_names(objects)
    if not name:
        return OperationResult.cancelled("A mesh appearance needs a name")
    if name in names:
        return OperationResult.cancelled(
            f'The mesh already has an appearance named "{name}"'
        )
    mesh_appearance.add_mesh_appearance(
        shared_mesh_objects(objects), name, item.mesh_appearance
    )
    track_item(collection, index)
    write_values(item, {"mesh_appearance": name})
    mesh_appearance.apply_mesh_appearance(objects, name)
    remember_applied(item)
    clear_entity_caches()
    return OperationResult.finished(f"Added the mesh appearance {name}.")


@transactional("Remove mesh appearance")
def remove_mesh_appearance(collection, index: int, name: str) -> OperationResult:
    item = ensure_appearance_state(collection).components[index]
    if name == item.mesh_appearance:
        return OperationResult.cancelled("Choose another mesh appearance first")
    objects = component_objects(collection, item.name)
    mesh_appearance.remove_mesh_appearance(shared_mesh_objects(objects), name)
    clear_entity_caches()
    return OperationResult.finished(f"Removed the mesh appearance {name}.")
