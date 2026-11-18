from typing import Literal, get_args

import bpy

from ..core.log import get_logger, log_once
from .identity import rna_identity

_LOG = get_logger(__name__)

_TARGET_TYPES = Literal["MESH", "ARMATURE", "ALL"]


def collection_parent_map():
    """The parent collections of every child collection, keyed by the child's RNA pointer"""
    parents = {}
    for collection in bpy.data.collections:
        for child in collection.children:
            parents.setdefault(child.as_pointer(), []).append(collection)
    return parents


def object_owners():
    """The collections holding each object, scene master collections included, by the object's identity

    Built from one pass over every collection: Object.users_collection scans all collections on
    each call, which takes minutes across a sector scene's thousands of objects.
    """
    owners = {}
    for owner in (
        *bpy.data.collections,
        *(scene.collection for scene in bpy.data.scenes),
    ):
        for obj in owner.objects:
            owners.setdefault(rna_identity(obj), []).append(owner)
    return owners


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
    return next(iter(collections)) if len(collections) == 1 else None


def get_active_collection(context=None):
    context = context or bpy.context
    active = getattr(context, "active_object", None)
    if active is None:
        return None
    collections = tuple(active.users_collection)
    return collections[0] if len(collections) == 1 else None


def get_collection_children(
    target_collection_name, target_type: _TARGET_TYPES = "MESH"
):
    options = get_args(_TARGET_TYPES)
    if target_type not in options:
        raise ValueError(f"{target_type!r} is not one of {options}")
    collection = bpy.data.collections.get(target_collection_name)
    if collection is None:
        return None
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


def preserve_world_parent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    try:
        obj.matrix_parent_inverse = parent.matrix_world.inverted_safe()
    except AttributeError as error:
        log_once(
            _LOG,
            "DEBUG",
            ("preserve_world_parent", type(error).__name__),
            "preserve world parent: fell back after %s",
            error,
            exc_info=True,
        )
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world


def remap_copied_object_references(copied_objects, object_map):
    """Remap common Blender object references after copying an object graph"""
    for obj in copied_objects:
        parent = obj.parent
        if parent in object_map:
            world = obj.matrix_world.copy()
            obj.parent = object_map[parent]
            obj.matrix_world = world

        for modifier in obj.modifiers:
            target = getattr(modifier, "object", None)
            if target in object_map:
                modifier.object = object_map[target]

        for constraint in obj.constraints:
            target = getattr(constraint, "target", None)
            if target in object_map:
                constraint.target = object_map[target]
