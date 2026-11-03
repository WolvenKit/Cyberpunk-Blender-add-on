from __future__ import annotations

import itertools

import bpy

NEW_SECTOR_KEY = "cp77_new_sector"
_NEW_SECTOR_NAME = "new_sector"


def new_sector_collections(scene) -> tuple[bpy.types.Collection, ...]:
    """The scene's new-sector collections"""
    return tuple(
        collection
        for collection in scene.collection.children_recursive
        if collection.get(NEW_SECTOR_KEY)
    )


def add_new_sector(scene) -> bpy.types.Collection:
    """A new, empty new-sector collection under the scene's collection"""
    taken = {collection.name.casefold() for collection in bpy.data.collections}
    name = next(
        name
        for name in (f"{_NEW_SECTOR_NAME}_{number}" for number in itertools.count(1))
        if name.casefold() not in taken
    )
    collection = bpy.data.collections.new(name)
    collection[NEW_SECTOR_KEY] = True
    scene.collection.children.link(collection)
    return collection


def remove_new_sector(scene, collection) -> None:
    """Remove the new-sector collection, moving what it holds to its parent"""
    if not collection.get(NEW_SECTOR_KEY):
        raise ValueError(f"{collection.name} is not a new sector")
    owner = next(
        (
            candidate
            for candidate in scene.collection.children_recursive
            if candidate.children.get(collection.name) == collection
        ),
        scene.collection,
    )
    for obj in collection.objects:
        if owner.objects.get(obj.name) != obj:
            owner.objects.link(obj)
    for child in collection.children:
        if owner.children.get(child.name) != child:
            owner.children.link(child)
    bpy.data.collections.remove(collection)
