from typing import Literal, get_args

import bpy


_TARGET_TYPES = Literal["MESH", "ARMATURE", "ALL"]


def get_selected_collection(context=None):
    context = context or bpy.context
    active = getattr(context, "active_object", None)
    selected = [obj for obj in getattr(context, "selected_objects", ()) if obj != active]
    if not selected and active is not None:
        selected.append(active)
    collections = {collection for obj in selected for collection in obj.users_collection}
    return next(iter(collections)) if len(collections) == 1 else None


def get_active_collection(context=None):
    context = context or bpy.context
    active = getattr(context, "active_object", None)
    if active is None:
        return None
    collections = tuple(active.users_collection)
    return collections[0] if len(collections) == 1 else None


def get_collection_children(target_collection_name, target_type: _TARGET_TYPES = "MESH"):
    options = get_args(_TARGET_TYPES)
    if target_type not in options:
        raise ValueError(f"{target_type!r} is not one of {options}")
    collection = bpy.data.collections.get(target_collection_name)
    if collection is None:
        return None
    return [obj for obj in collection.objects if target_type == "ALL" or obj.type == target_type]


def newly_linked_collection_object(collection, existing_objects, expected_name):
    for obj in collection.objects:
        if obj not in existing_objects:
            return obj
    return collection.objects.get(expected_name)
