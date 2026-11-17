from __future__ import annotations

import json

from ..assetio.values import json_object

_STASH = "cp77_stashed_appearances"
# An import that brings several appearances as collections, an entity's say, tags each with its group and name.
APPEARANCE_GROUP_KEY = "cp77_appearance_group"
APPEARANCE_NAME_KEY = "cp77_display_appearance_name"
APPEARANCE_DEFAULT_KEY = "cp77_appearance_default"
_STASH_MATERIAL = "cp77_stashed_appearance_material_"
_STASH_ORIGINAL = "cp77_stashed_appearance_original_"


def appearance_index(scene, name, *, create=True):
    """The index of the scene's appearance called name, added at the end when create allows, or -1"""
    for index, appearance in enumerate(scene.cp77_mesh_appearances):
        if appearance.name == name:
            return index
    if not create:
        return -1
    scene.cp77_mesh_appearances.add().name = name
    return len(scene.cp77_mesh_appearances) - 1


def add_appearance(scene, base="appearance"):
    """The index of a new appearance named base, numbered when the name is taken"""
    names = {appearance.name for appearance in scene.cp77_mesh_appearances}
    name, number = base, 1
    while name in names:
        name = f"{base}_{number}"
        number += 1
    return appearance_index(scene, name)


def _uses(item, index):
    return any(entry.index == index for entry in item.appearances)


def _drop(item, index):
    for position, entry in enumerate(item.appearances):
        if entry.index == index:
            item.appearances.remove(position)
            return


def _drop_from_slot(mesh, slot_index, index, keep):
    for item in mesh.cp77_appearance_materials:
        if item.slot_index == slot_index and item.as_pointer() != keep.as_pointer():
            _drop(item, index)


def add_row_appearance(mesh, row, index):
    """Make row of mesh's appearance materials the material its slot shows in appearance index"""
    item = mesh.cp77_appearance_materials[row]
    _drop_from_slot(mesh, item.slot_index, index, item)
    if not _uses(item, index):
        item.appearances.add().index = index


def set_use_appearance(use, index):
    """Point an appearance entry at appearance index, taking that appearance from the slot's other materials"""
    mesh = use.id_data
    for item in mesh.cp77_appearance_materials:
        if any(entry.as_pointer() == use.as_pointer() for entry in item.appearances):
            _drop_from_slot(mesh, item.slot_index, index, item)
            break
    use.index = index


def slot_material_for(mesh, slot_index, index):
    """The material mesh's slot slot_index shows in appearance index, or None when it has none there"""
    for item in mesh.cp77_appearance_materials:
        if item.slot_index == slot_index and _uses(item, index):
            return item.material
    return None


def record_slot_material(mesh, slot_index, material, index):
    """Make material the one mesh's slot slot_index shows in appearance index"""
    entries = mesh.cp77_appearance_materials
    for item in entries:
        if item.slot_index == slot_index and item.material != material:
            _drop(item, index)
    for position in reversed(range(len(entries))):
        if not entries[position].appearances:
            entries.remove(position)
    item = next(
        (
            item
            for item in entries
            if item.slot_index == slot_index and item.material == material
        ),
        None,
    )
    if item is None:
        item = entries.add()
        item.slot_index = slot_index
        item.material = material
    if not _uses(item, index):
        item.appearances.add().index = index


def store_original_materials(obj):
    """Remember the object's slot materials as its originals, the first time only"""
    mesh = obj.data
    if len(mesh.cp77_appearance_defaults):
        return
    for slot_index, slot in enumerate(obj.material_slots):
        default = mesh.cp77_appearance_defaults.add()
        default.slot_index = slot_index
        default.material = slot.material


def _original_material(mesh, slot_index):
    for default in mesh.cp77_appearance_defaults:
        if default.slot_index == slot_index:
            return default.material, True
    return None, False


def _appearance_objects(scene):
    return [
        obj
        for obj in scene.objects
        if obj.type == "MESH"
        and obj.data is not None
        and (
            len(obj.data.cp77_appearance_materials)
            or len(obj.data.cp77_appearance_defaults)
        )
    ]


def _show_collection(collection, shown):
    if collection.hide_viewport == shown:
        collection.hide_viewport = not shown
    if collection.hide_render == shown:
        collection.hide_render = not shown


def _appearance_collection_groups(scene):
    groups = {}
    for collection in scene.collection.children_recursive:
        group = collection.get(APPEARANCE_GROUP_KEY)
        if group:
            groups.setdefault(str(group), []).append(collection)
    return groups.values()


def record_collection_appearances(scene, group, collections, default):
    """List each of an import's appearance collections among the scene's appearances by its name, showing only default"""
    for collection in collections:
        appearance_index(scene, str(collection.get(APPEARANCE_NAME_KEY, "")))
        collection[APPEARANCE_GROUP_KEY] = str(group)
        collection[APPEARANCE_DEFAULT_KEY] = collection == default
        _show_collection(collection, collection == default)


def display_appearance(scene, index):
    """Show appearance index on every mesh and appearance collection in the scene, leaving ones without it as they are"""
    name = scene.cp77_mesh_appearances[index].name
    for collections in _appearance_collection_groups(scene):
        if any(
            collection.get(APPEARANCE_NAME_KEY) == name for collection in collections
        ):
            for collection in collections:
                _show_collection(
                    collection, collection.get(APPEARANCE_NAME_KEY) == name
                )
    for obj in _appearance_objects(scene):
        mesh = obj.data
        for slot_index, slot in enumerate(obj.material_slots):
            material = slot_material_for(mesh, slot_index, index)
            if material is None:
                material, known = _original_material(mesh, slot_index)
                if not known:
                    continue
            if slot.material != material:
                slot.material = material


def assign_to_appearance(objects, index):
    """Record the mesh objects' current slot materials as appearance index"""
    for obj in objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        store_original_materials(obj)
        for slot_index, slot in enumerate(obj.material_slots):
            if slot.material is not None:
                record_slot_material(obj.data, slot_index, slot.material, index)


def reset_to_original(scene):
    """Give every mesh in the scene back the materials it had before any appearance was shown, and every import its default appearance"""
    for collections in _appearance_collection_groups(scene):
        for collection in collections:
            _show_collection(collection, bool(collection.get(APPEARANCE_DEFAULT_KEY)))
    for obj in _appearance_objects(scene):
        mesh = obj.data
        for slot_index, slot in enumerate(obj.material_slots):
            material, known = _original_material(mesh, slot_index)
            if known and slot.material != material:
                slot.material = material


def remove_appearance(scene, meshes, index):
    """Remove appearance index from the scene and from meshes, renumbering the ones after it"""
    scene.cp77_mesh_appearances.remove(index)
    for mesh in meshes:
        entries = mesh.cp77_appearance_materials
        for position in reversed(range(len(entries))):
            item = entries[position]
            _drop(item, index)
            for entry in item.appearances:
                if entry.index > index:
                    entry.index -= 1
            if not item.appearances:
                entries.remove(position)


def stash_appearance_materials(mesh, holder):
    """Move mesh's appearance materials and originals onto the custom properties of the data-block holder"""
    rows = mesh.cp77_appearance_materials
    defaults = mesh.cp77_appearance_defaults
    holder[_STASH] = json.dumps(
        {
            "materials": [
                [item.slot_index, [use.index for use in item.appearances]]
                for item in rows
            ],
            "originals": [default.slot_index for default in defaults],
        },
        separators=(",", ":"),
    )
    for position, item in enumerate(rows):
        if item.material is not None:
            holder[f"{_STASH_MATERIAL}{position}"] = item.material
    for position, default in enumerate(defaults):
        if default.material is not None:
            holder[f"{_STASH_ORIGINAL}{position}"] = default.material
    rows.clear()
    defaults.clear()


def restore_appearance_materials(mesh, holder):
    """Give mesh the appearance materials and originals stash_appearance_materials put on holder, and no others"""
    rows = mesh.cp77_appearance_materials
    defaults = mesh.cp77_appearance_defaults
    rows.clear()
    defaults.clear()
    stash = json_object(holder.get(_STASH))
    for position, (slot_index, indices) in enumerate(stash.get("materials", ())):
        item = rows.add()
        item.slot_index = slot_index
        item.material = holder.get(f"{_STASH_MATERIAL}{position}")
        for index in indices:
            item.appearances.add().index = index
    for position, slot_index in enumerate(stash.get("originals", ())):
        default = defaults.add()
        default.slot_index = slot_index
        default.material = holder.get(f"{_STASH_ORIGINAL}{position}")
