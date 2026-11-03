from __future__ import annotations

import json

import bpy

from ...entity.domain.chunks import FULL_MASK, mask_text, parse_mask
from ...entity.domain.components import component_edit_from
from ...entity.domain.document import AppearanceDocument, EntityDocument
from ...entity.model.edits import (
    AppearanceEdit,
    Binding,
    ComponentEdit,
    ComponentKey,
    EntityEdit,
    ValidationIssue,
)
from ...importers.entity.records import COMPONENT_TAG_KEY
from ..runtime.documents import source_documents
from ..runtime.scene_cache import entity_index
from ..runtime.updates import suspended
from .scene import appearance_record, component_objects


def applied_values(item) -> dict:
    """The values last shown on the component's objects"""
    return {
        "name": item.name,
        "enabled": item.enabled,
        "type_key": item.type_key,
        "mesh_appearance": item.mesh_appearance,
        "attach_target": item.attach_target,
        "attach_slot": item.attach_slot,
        "skin_target": item.skin_target,
    }


def remember_applied(item) -> None:
    item.applied = json.dumps(applied_values(item))


def _write_component(item, edit: ComponentEdit, collection_name: str) -> None:
    item.key_name = edit.key.name if edit.key else ""
    item.key_cruid = edit.key.cruid if edit.key else ""
    item.name = edit.name
    item.enabled = edit.enabled
    item.type_key = edit.type_key
    item.mesh = edit.mesh
    item.mesh_appearance = edit.mesh_appearance
    item.chunk_mask = mask_text(edit.chunk_mask)
    item.attach_target = edit.attach.target if edit.attach else ""
    item.attach_slot = edit.attach.slot if edit.attach else ""
    item.skin_target = edit.skin
    item.mesh_collection_name = collection_name
    remember_applied(item)


def load_documents(collection) -> tuple[AppearanceDocument, EntityDocument]:
    """The appearance's source documents (read-only)"""
    record = appearance_record(collection)
    if record is None:
        raise ValueError(
            f"'{collection.name}' was not imported by the entity importer; re-import the entity"
        )
    return source_documents(record.app_path, record.ent_path)


def _component_collection(collection, component: str):
    """The component's mesh collection inside the appearance, found by the tag the import gave it"""
    return next(
        (
            child
            for child in collection.children_recursive
            if child.get(COMPONENT_TAG_KEY) == component
        ),
        None,
    )


def ensure_appearance_state(collection):
    """The appearance's stored state, built from its import on first use"""
    state = collection.cp77_entity_state
    if state.initialized:
        return state
    record = appearance_record(collection)
    app, ent = load_documents(collection)
    collection_names = dict(record.collection_names)
    with suspended():
        state.components.clear()
        for pair in app.components(record.appearance):
            edit = component_edit_from(pair, app.handles)
            if edit is None or edit.name not in collection_names:
                continue
            item = state.components.add()
            _write_component(item, edit, collection_names[edit.name])
            item.mesh_collection = _component_collection(
                collection, edit.name
            ) or bpy.data.collections.get(collection_names[edit.name])
        state.name = record.appearance
        state.entry_name = record.entry_name
        state.source_name = record.appearance
        state.origin = record.appearance
        state.is_default = (
            bool(record.entry_name) and record.entry_name == ent.default_appearance()
        )
        state.initialized = True
    return state


def component_mesh_path(item) -> str:
    """The mesh path the component exports with"""
    collection = item.mesh_collection
    if (
        collection is None
        or not item.mesh_collection_name
        or collection.name == item.mesh_collection_name
    ):
        return item.mesh
    folder = item.mesh.rsplit("\\", 1)[0] if "\\" in item.mesh else ""
    return f"{folder}\\{collection.name}.mesh" if folder else f"{collection.name}.mesh"


def component_edit(item) -> ComponentEdit:
    return ComponentEdit(
        key=ComponentKey(item.key_name, item.key_cruid) if item.key_name else None,
        template=ComponentKey(item.template_name, item.template_cruid)
        if item.template_name
        else None,
        name=item.name,
        enabled=item.enabled,
        type_key=item.type_key,
        mesh=component_mesh_path(item),
        mesh_appearance=item.mesh_appearance,
        chunk_mask=parse_mask(item.chunk_mask) if item.chunk_mask else FULL_MASK,
        attach=Binding(item.attach_target, item.attach_slot)
        if item.attach_target
        else None,
        skin=item.skin_target,
    )


def appearance_edit(collection) -> tuple[AppearanceEdit, tuple[ValidationIssue, ...]]:
    state = ensure_appearance_state(collection)
    edits = []
    removed = set()
    issues = []
    for item in state.components:
        if item.removed:
            if item.key_name:
                removed.add(ComponentKey(item.key_name, item.key_cruid))
            continue
        if not component_objects(collection, item.name):
            issues.append(
                ValidationIssue(state.name, item.name, f"{item.name} has no objects")
            )
            continue
        edits.append(component_edit(item))
    return (
        AppearanceEdit(
            state.name,
            state.source_name,
            state.entry_name,
            tuple(edits),
            frozenset(removed),
        ),
        tuple(issues),
    )


def entity_edit(import_id: str) -> tuple[EntityEdit, tuple[ValidationIssue, ...]]:
    collections = entity_index().collections(import_id)
    if not collections:
        raise ValueError("The entity's appearances are no longer in the scene")
    record = appearance_record(collections[0])
    if (
        len(
            {
                appearance_record(collection).app_path.casefold()
                for collection in collections
            }
        )
        > 1
    ):
        raise ValueError(
            "This entity's appearances come from more than one .app file; exporting it isn't supported yet"
        )
    appearances = []
    issues = []
    default = ""
    states = [
        (collection, ensure_appearance_state(collection)) for collection in collections
    ]
    live_names = {state.name for _collection, state in states if not state.removed}
    # An imported appearance that was removed or renamed leaves the export, unless another appearance now has
    # its name (it was imported again); duplicates were never in the source and need no removal.
    removed = {
        state.origin
        for _collection, state in states
        if state.origin
        and (state.removed or state.name != state.origin)
        and state.origin not in live_names
    }
    for collection, state in states:
        if state.removed:
            continue
        edit, found = appearance_edit(collection)
        appearances.append(edit)
        issues.extend(found)
        if state.is_default:
            default = state.entry_name
    if not default:
        default = source_documents(record.app_path, record.ent_path)[
            1
        ].default_appearance()
    return (
        EntityEdit(
            ent_path=record.ent_path,
            app_path=record.app_path,
            appearances=tuple(appearances),
            removed_appearances=frozenset(removed),
            default_appearance=default,
        ),
        tuple(issues),
    )
