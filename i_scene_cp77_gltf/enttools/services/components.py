from __future__ import annotations

import json

import bpy

from ...blender.collections import root_objects
from ...blender.identity import rna_identity
from ...blender.mesh_source import base_mesh, mesh_source
from ...blender.operator_results import OperationResult
from ...blender.transactions import (
    track_collection_state,
    track_created_datablock,
    track_mutation,
    track_object_state,
    transactional,
)
from ...core.log import get_logger
from ...core.notifications import show_message
from ...entity.domain import chunks
from ...entity.domain.chunks import FULL_MASK, mask_text, parse_mask
from ...entity.domain.document import (
    attach_targets,
    find_component,
    rig_targets,
    slot_bone,
)
from ...entity.model.component_types import SKINNED_TYPES
from ...importers.common.collections import remap_copied_object_references
from ..blender import apply, mesh_appearance
from ..blender.scene import (
    COMPONENT_NAME_KEY,
    appearance_record,
    component_for_object,
    component_objects,
)
from ..blender.state import (
    component_mesh_path,
    ensure_appearance_state,
    load_documents,
    remember_applied,
)
from ..runtime.scene_cache import clear_entity_caches
from ..runtime.updates import suspended

_LOG = get_logger(__name__)
NEW_MATERIAL = "__NEW__"


class EditError(RuntimeError):
    """An edit that cannot be applied"""


def _live_items(state):
    return [item for item in state.components if not item.removed]


def entity_armature(collection):
    """The armature the appearance's skinned meshes deform with"""
    for obj in collection.all_objects:
        for modifier in getattr(obj, "modifiers", ()):
            if modifier.type == "ARMATURE" and modifier.object is not None:
                return modifier.object
    return next((obj for obj in collection.all_objects if obj.type == "ARMATURE"), None)


def _attach_target(collection, state, target: str, slot: str):
    """The object (and bone) a component attaching to target/slot is constrained to"""
    app, ent = load_documents(collection)
    targets = dict(attach_targets(app, ent, state.source_name))
    names = {item.name for item in _live_items(state)}
    if target not in targets and target not in names:
        raise EditError(f'Attach To "{target}" doesn\'t exist in this appearance')
    if slot and slot not in targets.get(target, ()):
        raise EditError(f'Slot "{slot}" doesn\'t exist on "{target}"')
    objects = component_objects(collection, target)
    if objects and not slot:
        roots = root_objects(objects) or objects[:1]
        return roots[0], ""
    armature = entity_armature(collection)
    if armature is None:
        raise EditError(
            f'"{target}" has no object or rig to attach to in this appearance'
        )
    if slot:
        component = find_component(app, ent, state.source_name, target)
        return armature, slot_bone(component or {}, slot)
    return armature, ""


def shared_mesh_objects(objects):
    """Every object in the file showing the same game mesh as objects"""
    meshes = [obj for obj in objects if obj.type == "MESH"]
    source = mesh_source(meshes[0]) if meshes else None
    if source is None:
        return tuple(meshes)
    key = source.depot_path.casefold()
    return tuple(
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH"
        and (other := mesh_source(obj)) is not None
        and other.depot_path.casefold() == key
    )


def write_values(item, values: dict) -> None:
    with suspended():
        for key, value in values.items():
            if getattr(item, key) != value:
                setattr(item, key, value)


def track_item(collection, index: int) -> None:
    item = collection.cp77_entity_state.components[index]
    previous = {
        key: getattr(item, key)
        for key in item.bl_rna.properties.keys()
        if key not in {"rna_type", "mesh_collection"}
    }
    # Fields an edit has stored but not yet shown come back as last shown.
    previous.update(json.loads(item.applied or "{}"))
    previous_collection = item.mesh_collection

    def restore():
        target = collection.cp77_entity_state.components[index]
        write_values(
            target,
            {key: value for key, value in previous.items() if key != "name" or value},
        )
        with suspended():
            target.mesh_collection = previous_collection

    track_mutation(
        ("enttools-component", rna_identity(collection), index),
        restore,
        label="Entity component",
    )


def _track_objects(objects) -> None:
    for obj in objects:
        track_object_state(obj, label="Entity component object")


def _apply_name(collection, state, item, applied, objects):
    new, old = item.name.strip(), applied.get("name", item.name)
    if not new:
        raise EditError("A component needs a name")
    if any(other.name == new for other in _live_items(state) if other != item):
        raise EditError(f'Two components are named "{new}"')
    for obj in objects:
        obj[COMPONENT_NAME_KEY] = new
    for index, other in enumerate(state.components):
        if other == item:
            continue
        changes = {}
        if other.attach_target == old:
            changes["attach_target"] = new
        if other.skin_target == old:
            changes["skin_target"] = new
        if changes:
            track_item(collection, index)
            write_values(other, changes)
            remember_applied(other)


def _apply_enabled(collection, state, item, applied, objects):
    apply.apply_enabled(
        objects,
        item.enabled,
        parse_mask(item.chunk_mask) if item.chunk_mask else FULL_MASK,
    )


def _apply_skin_for(collection, state, item, objects):
    if item.type_key not in SKINNED_TYPES or not item.skin_target:
        apply.apply_skin(objects, None)
        return
    app, ent = load_documents(collection)
    if item.skin_target not in rig_targets(app, ent, state.source_name):
        raise EditError(
            f'Deform With "{item.skin_target}" isn\'t a rig in this appearance'
        )
    apply.apply_skin(objects, entity_armature(collection))


def _apply_type(collection, state, item, applied, objects):
    if item.type_key not in SKINNED_TYPES and item.skin_target:
        write_values(item, {"skin_target": ""})
    _apply_skin_for(collection, state, item, objects)


def _apply_skin(collection, state, item, applied, objects):
    _apply_skin_for(collection, state, item, objects)


def _apply_mesh_appearance(collection, state, item, applied, objects):
    names = mesh_appearance.mesh_appearance_names(objects)
    if names and item.mesh_appearance not in names:
        raise EditError(f'"{item.mesh_appearance}" isn\'t an appearance of this mesh')
    mesh_appearance.apply_mesh_appearance(objects, item.mesh_appearance)


def _apply_attach(collection, state, item, applied, objects):
    if not item.attach_target:
        apply.apply_attach(objects, None)
        return
    target, bone = _attach_target(
        collection, state, item.attach_target, item.attach_slot
    )
    apply.apply_attach(objects, target, bone)


_HANDLERS = {
    "name": _apply_name,
    "enabled": _apply_enabled,
    "type_key": _apply_type,
    "mesh_appearance": _apply_mesh_appearance,
    "attach": _apply_attach,
    "skin": _apply_skin,
}

_FIELD_VALUES = {
    "name": lambda value: {"name": value},
    "enabled": lambda value: {"enabled": bool(value)},
    "type_key": lambda value: {"type_key": value},
    "mesh_appearance": lambda value: {"mesh_appearance": value},
    "attach": lambda value: {"attach_target": value[0], "attach_slot": value[1]},
    "skin": lambda value: {"skin_target": value},
}


@transactional("Entity component edit")
def apply_field(context, collection, index: int, field: str) -> OperationResult:
    """Show the component's stored field on its objects"""
    state = ensure_appearance_state(collection)
    item = state.components[index]
    applied = json.loads(item.applied or "{}")
    objects = component_objects(collection, applied.get("name", item.name))
    track_item(collection, index)
    _track_objects(objects)
    try:
        _HANDLERS[field](collection, state, item, applied, objects)
    except EditError as error:
        write_values(item, applied)
        return OperationResult.cancelled(str(error), error=error)
    remember_applied(item)
    return OperationResult.finished()


def set_field(context, collection, index: int, field: str, value) -> OperationResult:
    """Store and show a new value for a component field"""
    item = ensure_appearance_state(collection).components[index]
    write_values(item, _FIELD_VALUES[field](value))
    return apply_field(context, collection, index, field)


def field_changed(context, item, field: str) -> None:
    """A component field was edited in the panel"""
    collection = item.id_data
    index = next(
        i
        for i, candidate in enumerate(collection.cp77_entity_state.components)
        if candidate == item
    )
    result = apply_field(context, collection, index, field)
    if not result.ok:
        show_message(result.message, severity=result.level, logger=_LOG)
    elif field in {"attach", "name"}:
        from .selection import refresh_choices

        refresh_choices(context)


@transactional("Entity chunk visibility")
def set_part_visible(
    context, collection, index: int, part: int, visible: bool
) -> OperationResult:
    item = ensure_appearance_state(collection).components[index]
    track_item(collection, index)
    mask = chunks.set_part_visible(
        parse_mask(item.chunk_mask) if item.chunk_mask else FULL_MASK, part, visible
    )
    write_values(item, {"chunk_mask": mask_text(mask)})
    objects = component_objects(collection, item.name)
    _track_objects(objects)
    apply.apply_chunk_mask(objects, mask)
    return OperationResult.finished()


@transactional("Entity chunk visibility")
def show_all_parts(context, collection, index: int) -> OperationResult:
    item = ensure_appearance_state(collection).components[index]
    track_item(collection, index)
    write_values(item, {"chunk_mask": mask_text(FULL_MASK)})
    objects = component_objects(collection, item.name)
    _track_objects(objects)
    apply.apply_chunk_mask(objects, FULL_MASK)
    return OperationResult.finished()


@transactional("Entity part material")
def set_part_material(
    context, collection, index: int, part: int, material: str
) -> OperationResult:
    item = ensure_appearance_state(collection).components[index]
    objects = component_objects(collection, item.name)
    own = next((found for found in apply.parts(objects) if found.index == part), None)
    if own is None:
        return OperationResult.cancelled(f"The mesh has no part {part}")
    if material == NEW_MATERIAL:
        current = (
            own.objects[0].material_slots[0].material
            if own.objects[0].material_slots
            else None
        )
        if current is None:
            return OperationResult.cancelled("This part has no material to copy")
        copied = track_created_datablock("materials", current.copy())
        material = copied.name
    names = list(mesh_appearance.mesh_appearance_names(objects))
    appearance_index = (
        names.index(item.mesh_appearance) if item.mesh_appearance in names else 0
    )
    shared = tuple(
        obj
        for found in apply.parts(shared_mesh_objects(objects))
        if found.index == part
        for obj in found.objects
    )
    _track_objects(shared)
    mesh_appearance.set_part_material(
        apply.Part(part, shared, ()), appearance_index, material
    )
    for obj in own.objects:
        mesh_appearance.assign_material(obj, bpy.data.materials.get(material))
    clear_entity_caches()
    return OperationResult.finished()


def _mesh_for(objects, template_mesh: str, collection_name: str) -> tuple[str, str]:
    """The mesh path and base mesh for objects joining the entity"""
    source = mesh_source(objects[0])
    if source is not None:
        return source.depot_path, ""
    base = base_mesh(objects[0])
    folder_source = base or template_mesh
    folder = folder_source.rsplit("\\", 1)[0] if "\\" in folder_source else ""
    return (
        f"{folder}\\{collection_name}.mesh" if folder else f"{collection_name}.mesh"
    ), base


def _component_collection(collection, name: str, objects):
    holder = track_created_datablock("collections", bpy.data.collections.new(name))
    track_collection_state(collection, label="Entity appearance")
    collection.children.link(holder)
    for obj in objects:
        track_object_state(obj, label="Entity component object")
        for owner in tuple(obj.users_collection):
            track_collection_state(owner, label="Entity component collection")
            owner.objects.unlink(obj)
        holder.objects.link(obj)
    return holder


def _owned_elsewhere(objects) -> str:
    """A refusal message when any of the objects already belongs to an entity component, else ''"""
    for obj in objects:
        found = component_for_object(obj)
        if found is not None:
            return f'"{obj.name}" already belongs to the component "{found[1]}"; duplicate that component instead'
    return ""


def _delete_objects(objects) -> None:
    for obj in objects:
        if bpy.data.objects.get(obj.name) == obj:
            bpy.data.objects.remove(obj, do_unlink=True)


@transactional("Add entity component")
def add_component(collection, objects, *, name: str) -> OperationResult:
    state = ensure_appearance_state(collection)
    name = name.strip()
    meshes = [obj for obj in objects if obj.type == "MESH"]
    if not name:
        return OperationResult.cancelled("A component needs a name")
    if any(item.name == name for item in _live_items(state)):
        return OperationResult.cancelled(f'Two components are named "{name}"')
    if not meshes:
        return OperationResult.cancelled("Select the mesh objects to add")
    refusal = _owned_elsewhere(meshes)
    if refusal:
        return OperationResult.cancelled(refusal)
    skinned = any(
        modifier.type == "ARMATURE" for obj in meshes for modifier in obj.modifiers
    )
    candidates = _live_items(state)
    template = next(
        (item for item in candidates if (item.type_key in SKINNED_TYPES) == skinned),
        None,
    )
    template = template or (candidates[0] if candidates else None)
    if template is None:
        return OperationResult.cancelled(
            "The appearance has no component to copy settings from"
        )
    holder = _component_collection(collection, name, meshes)
    mesh, base = _mesh_for(meshes, template.mesh, holder.name)
    names = mesh_appearance.mesh_appearance_names(meshes)
    with suspended():
        item = state.components.add()
        item.template_name, item.template_cruid = template.key_name, template.key_cruid
        item.name = name
        item.enabled = True
        item.type_key = (
            template.type_key
            if (template.type_key in SKINNED_TYPES) == skinned
            else ("SKINNED" if skinned else "MESH")
        )
        item.mesh, item.base_mesh = mesh, base
        item.mesh_collection, item.mesh_collection_name = holder, holder.name
        item.mesh_appearance = names[0] if names else "default"
        item.chunk_mask = mask_text(FULL_MASK)
        item.attach_target, item.attach_slot = (
            template.attach_target,
            template.attach_slot,
        )
        item.skin_target = (
            template.skin_target if item.type_key in SKINNED_TYPES else ""
        )
    index = len(state.components) - 1

    def forget():
        components = collection.cp77_entity_state.components
        if len(components) > index and components[index].name == name:
            components.remove(index)

    track_mutation(
        ("enttools-added", rna_identity(collection), name),
        forget,
        label="Entity component",
    )
    for obj in meshes:
        obj[COMPONENT_NAME_KEY] = name
    try:
        _apply_attach(collection, state, item, {}, meshes)
        _apply_skin_for(collection, state, item, meshes)
    except EditError as error:
        return OperationResult.cancelled(str(error), error=error)
    remember_applied(item)
    return OperationResult.finished(f"Added {name}.")


@transactional("Replace entity component mesh")
def replace_mesh(context, collection, index: int, objects) -> OperationResult:
    state = ensure_appearance_state(collection)
    item = state.components[index]
    meshes = [obj for obj in objects if obj.type == "MESH"]
    if not meshes:
        return OperationResult.cancelled("Select the mesh objects to use")
    old_objects = component_objects(collection, item.name)
    if any(obj in old_objects for obj in meshes):
        return OperationResult.cancelled(
            "Select meshes that aren't already this component"
        )
    refusal = _owned_elsewhere(meshes)
    if refusal:
        return OperationResult.cancelled(refusal)
    source_holder = next(
        (
            owner
            for owner in meshes[0].users_collection
            if owner != context.scene.collection
        ),
        None,
    )
    holder = _component_collection(
        collection, source_holder.name if source_holder else meshes[0].name, meshes
    )
    self_modelled = mesh_source(meshes[0]) is None
    mesh, base = _mesh_for(meshes, item.mesh, holder.name)
    if self_modelled and not base:
        base = item.mesh
    track_item(collection, index)
    for obj in meshes:
        obj[COMPONENT_NAME_KEY] = item.name
    try:
        _apply_attach(collection, state, item, {}, meshes)
        _apply_skin_for(collection, state, item, meshes)
        for child_index, child in enumerate(state.components):
            if not child.removed and child.attach_target == item.name:
                child_objects = component_objects(collection, child.name)
                _track_objects(child_objects)
                apply.apply_attach(
                    child_objects, (root_objects(meshes) or meshes[:1])[0], ""
                )
    except EditError as error:
        return OperationResult.cancelled(str(error), error=error)
    old_holder = item.mesh_collection
    names = mesh_appearance.mesh_appearance_names(meshes)
    appearance = (
        item.mesh_appearance
        if item.mesh_appearance in names
        else (names[0] if names else "default")
    )
    # The new mesh shows every part; its chunks and appearances are its own, not the replaced mesh's.
    write_values(
        item,
        {
            "mesh": mesh,
            "base_mesh": base,
            "mesh_collection_name": holder.name,
            "chunk_mask": mask_text(FULL_MASK),
            "mesh_appearance": appearance,
        },
    )
    apply.apply_enabled(meshes, item.enabled, FULL_MASK)
    with suspended():
        item.mesh_collection = holder
    _delete_objects(old_objects)
    if (
        old_holder is not None
        and not old_holder.all_objects
        and not old_holder.children
    ):
        bpy.data.collections.remove(old_holder)
    remember_applied(item)
    return OperationResult.finished(f"Replaced the mesh of {item.name}.")


@transactional("Remove entity component")
def remove_component(context, collection, index: int) -> OperationResult:
    state = ensure_appearance_state(collection)
    item = state.components[index]
    child = next(
        (
            other.name
            for other in _live_items(state)
            if other.attach_target == item.name and other != item
        ),
        None,
    )
    if child is not None:
        return OperationResult.cancelled(
            f'"{item.name}" is attached to by "{child}"; reattach it first'
        )
    name = item.name
    _delete_objects(component_objects(collection, name))
    if item.key_name:
        write_values(item, {"removed": True})
    else:
        state.components.remove(index)
    return OperationResult.finished(f"Removed {name}.")


@transactional("Duplicate entity component")
def duplicate_component(collection, index: int, *, name: str) -> OperationResult:
    """A new component made from copies of this one's objects (sharing their meshes) and its settings"""
    state = ensure_appearance_state(collection)
    source = state.components[index]
    name = name.strip()
    if not name:
        return OperationResult.cancelled("A component needs a name")
    if any(item.name == name for item in _live_items(state)):
        return OperationResult.cancelled(f'Two components are named "{name}"')
    objects = component_objects(collection, source.name)
    if not objects:
        return OperationResult.cancelled(f"{source.name} has no objects")
    object_map = {
        obj: track_created_datablock("objects", obj.copy()) for obj in objects
    }
    holder = track_created_datablock("collections", bpy.data.collections.new(name))
    track_collection_state(collection, label="Entity appearance")
    collection.children.link(holder)
    for duplicate in object_map.values():
        holder.objects.link(duplicate)
        duplicate[COMPONENT_NAME_KEY] = name
    remap_copied_object_references(list(object_map.values()), object_map)
    mesh = component_mesh_path(source)
    with suspended():
        item = state.components.add()
        for field in (
            "enabled",
            "type_key",
            "mesh_appearance",
            "chunk_mask",
            "attach_target",
            "attach_slot",
            "skin_target",
        ):
            setattr(item, field, getattr(source, field))
        if source.key_name:
            item.template_name, item.template_cruid = source.key_name, source.key_cruid
        else:
            item.template_name, item.template_cruid = (
                source.template_name,
                source.template_cruid,
            )
        item.name = name
        item.mesh = mesh
        item.base_mesh = source.base_mesh or (
            source.mesh if mesh != source.mesh else ""
        )
        item.mesh_collection, item.mesh_collection_name = holder, holder.name
    added = len(state.components) - 1

    def forget():
        components = collection.cp77_entity_state.components
        if len(components) > added and components[added].name == name:
            components.remove(added)

    track_mutation(
        ("enttools-duplicated", rna_identity(collection), name),
        forget,
        label="Entity component",
    )
    remember_applied(item)
    return OperationResult.finished(f"Duplicated {source.name} as {name}.")


def separate_renamed_meshes() -> int:
    """Give each renamed mesh its own mesh data and return the number of objects separated"""
    separated = 0
    for collection in bpy.data.collections:
        state = getattr(collection, "cp77_entity_state", None)
        if (
            state is None
            or not state.initialized
            or appearance_record(collection) is None
        ):
            continue
        for item in state.components:
            holder = item.mesh_collection
            if (
                item.removed
                or holder is None
                or not item.mesh_collection_name
                or holder.name == item.mesh_collection_name
            ):
                continue
            for obj in component_objects(collection, item.name):
                if obj.type == "MESH" and obj.data.users > 1:
                    obj.data = obj.data.copy()
                    separated += 1
    return separated
