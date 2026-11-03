from typing import Literal, get_args

import bpy

<<<<<<< Updated upstream

_TARGET_TYPES = Literal["MESH", "ARMATURE", "ALL"]


def get_selected_collection(context=None):
    context = context or bpy.context
    active = getattr(context, "active_object", None)
    selected = [obj for obj in getattr(context, "selected_objects", ()) if obj != active]
    if not selected and active is not None:
        selected.append(active)
    collections = {collection for obj in selected for collection in obj.users_collection}
=======
_TARGET_TYPES = Literal["MESH", "ARMATURE", "ALL"]


def collection_parent_map():
    """The parent collections of every child collection, keyed by the child's RNA pointer"""
    parents = {}
    for collection in bpy.data.collections:
        for child in collection.children:
            parents.setdefault(child.as_pointer(), []).append(collection)
    return parents


def get_selected_collection(context=None):
    context = context or bpy.context
    active = getattr(context, "active_object", None)
    selected = [
        obj for obj in getattr(context, "selected_objects", ()) if obj != active
    ]
    if not selected and active is not None:
        selected.append(active)
    collections = {
        collection for obj in selected for collection in obj.users_collection
    }
>>>>>>> Stashed changes
    return next(iter(collections)) if len(collections) == 1 else None


def get_active_collection(context=None):
    context = context or bpy.context
    active = getattr(context, "active_object", None)
    if active is None:
        return None
    collections = tuple(active.users_collection)
    return collections[0] if len(collections) == 1 else None


<<<<<<< Updated upstream
def get_collection_children(target_collection_name, target_type: _TARGET_TYPES = "MESH"):
=======
def get_collection_children(
    target_collection_name, target_type: _TARGET_TYPES = "MESH"
):
>>>>>>> Stashed changes
    options = get_args(_TARGET_TYPES)
    if target_type not in options:
        raise ValueError(f"{target_type!r} is not one of {options}")
    collection = bpy.data.collections.get(target_collection_name)
    if collection is None:
        return None
<<<<<<< Updated upstream
    return [obj for obj in collection.objects if target_type == "ALL" or obj.type == target_type]


def newly_linked_collection_object(collection, existing_objects, expected_name):
    for obj in collection.objects:
        if obj not in existing_objects:
            return obj
    return collection.objects.get(expected_name)
=======
    return [
        obj
        for obj in collection.objects
        if target_type == "ALL" or obj.type == target_type
    ]


def root_objects(objects):
    objects = tuple(objects)
    object_set = set(objects)
    return tuple(obj for obj in objects if obj.parent not in object_set)


def find_layer_collection(layer_collection, target_collection):
    if layer_collection.collection == target_collection:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, target_collection)
        if found is not None:
            return found
    return None
>>>>>>> Stashed changes
