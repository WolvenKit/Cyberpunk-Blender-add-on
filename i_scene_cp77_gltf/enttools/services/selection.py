from __future__ import annotations

import bpy

from ...blender.selection import select_objects
from ...core.log import get_logger
from ...core.notifications import show_message
from ...entity.domain.document import attach_targets, rig_targets
from ..blender.scene import appearance_record, component_for_object, component_objects
from ..blender.state import ensure_appearance_state, load_documents
from ..runtime.scene_cache import entity_index
from ..runtime.updates import suspended

_LOG = get_logger(__name__)
NOT_IMPORTED = "+"


def appearance_choices(import_id: str):
    """(value, label, description) for each appearance"""
    index = entity_index()
    collections = [
        collection
        for collection in index.collections(import_id)
        if not collection.cp77_entity_state.removed
    ]
    items = []
    names = set()
    for collection in collections:
        state = collection.cp77_entity_state
        name = state.name or index.record(collection).appearance
        names.add(name)
        items.append((collection.name, name, ""))
    if collections:
        try:
            _app, ent = load_documents(collections[0])
        except (FileNotFoundError, ValueError):
            return items
        for entry in ent.entries():
            name = str((entry.get("appearanceName") or {}).get("$value", ""))
            if name and name not in names:
                names.add(name)
                items.append((NOT_IMPORTED + name, name, "Imports this appearance"))
    return items


def current_collection(context):
    appearance = context.scene.cp77_entity_tools.appearance
    collection = (
        bpy.data.collections.get(appearance)
        if not appearance.startswith(NOT_IMPORTED)
        else None
    )
    return (
        collection
        if collection is not None and entity_index().record(collection) is not None
        else None
    )


def selected_component(collection, index: int):
    """The live component at index of an appearance collection, or None"""
    state = collection.cp77_entity_state if collection is not None else None
    if state is None or not state.initialized or not 0 <= index < len(state.components):
        return None
    item = state.components[index]
    return None if item.removed else item


def current_component(context):
    """The selected appearance collection, component and index"""
    collection = current_collection(context)
    index = context.scene.cp77_entity_tools.component_index
    item = selected_component(collection, index)
    return (collection, item, index) if item is not None else (collection, None, -1)


def _fill(collection_property, names) -> None:
    collection_property.clear()
    for name in names:
        collection_property.add().name = name


def refresh_choices(context) -> None:
    """The Attach To, Slot and Deform With choices for the selected component"""
    tools = context.scene.cp77_entity_tools
    collection, item, _index = current_component(context)
    targets, rigs, slots = (), (), ()
    if collection is not None:
        state = collection.cp77_entity_state
        app, ent = load_documents(collection)
        found = dict(attach_targets(app, ent, state.source_name))
        for other in state.components:
            if not other.removed and other.name not in found:
                found[other.name] = ()
        if item is not None:
            found.pop(item.name, None)
            slots = found.get(item.attach_target, ())
        targets = tuple(found)
        rigs = rig_targets(app, ent, state.source_name)
    with suspended():
        _fill(tools.attach_choices, targets)
        _fill(tools.slot_choices, slots)
        _fill(tools.rig_choices, rigs)


def select_component_objects(context) -> None:
    collection, item, _index = current_component(context)
    if item is None:
        return
    objects = component_objects(collection, item.name)
    if objects:
        from ..runtime.selection_sync import syncing

        with syncing():
            select_objects(list(objects), context=context)


def tools_changed(context, field: str) -> None:
    tools = context.scene.cp77_entity_tools
    if field == "entity":
        choices = appearance_choices(tools.entity)
        with suspended():
            if choices:
                tools.appearance = choices[0][0]
            tools.component_index = 0
        refresh_choices(context)
    elif field == "appearance":
        if tools.appearance.startswith(NOT_IMPORTED):
            from .appearances import switch_appearance

            result = switch_appearance(
                context, tools.entity, tools.appearance[len(NOT_IMPORTED) :]
            )
        else:
            collection = current_collection(context)
            from .appearances import switch_appearance

            result = (
                switch_appearance(
                    context, tools.entity, ensure_appearance_state(collection).name
                )
                if collection
                else None
            )
        if result is not None and not result.ok:
            show_message(result.message, severity="ERROR", logger=_LOG)
        with suspended():
            tools.component_index = 0
        refresh_choices(context)
    elif field == "component_index":
        refresh_choices(context)
        select_component_objects(context)
    elif field == "issue_index":
        if not 0 <= tools.issue_index < len(tools.issues):
            return
        issue = tools.issues[tools.issue_index]
        for collection in entity_index().collections(tools.entity):
            state = ensure_appearance_state(collection)
            if state.name != issue.appearance:
                continue
            index = next(
                (
                    i
                    for i, item in enumerate(state.components)
                    if item.name == issue.component
                ),
                None,
            )
            with suspended():
                tools.appearance = collection.name
                if index is not None:
                    tools.component_index = index
            refresh_choices(context)
            select_component_objects(context)
            return


def follow_active_object(context) -> bool:
    """Point the panel at the component of the active object"""
    obj = getattr(context.view_layer.objects, "active", None)
    found = component_for_object(obj) if obj is not None else None
    if found is None:
        return False
    collection, name = found
    record = appearance_record(collection)
    state = ensure_appearance_state(collection)
    index = next(
        (
            i
            for i, item in enumerate(state.components)
            if item.name == name and not item.removed
        ),
        None,
    )
    if index is None:
        return False
    tools = context.scene.cp77_entity_tools
    if (
        tools.entity == record.import_id
        and tools.appearance == collection.name
        and tools.component_index == index
    ):
        return False
    with suspended():
        tools.entity = record.import_id
        tools.appearance = collection.name
        tools.component_index = index
    refresh_choices(context)
    return True
