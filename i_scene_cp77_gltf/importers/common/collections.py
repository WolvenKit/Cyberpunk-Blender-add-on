from __future__ import annotations



def link_collection_once(parent, child):
    if parent.children.get(child.name) is not child:
        parent.children.link(child)


_link_collection_once = link_collection_once


def unlink_collection_once(parent, child):
    if parent.children.get(child.name) is child:
        parent.children.unlink(child)


_unlink_collection_once = unlink_collection_once


def preserve_world_parent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    try:
        obj.matrix_parent_inverse = parent.matrix_world.inverted_safe()
    except AttributeError:
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world


_preserve_world_parent = preserve_world_parent


def remap_copied_object_references(copied_objects, object_map):
    """Remap common Blender object references after copying an object graph."""
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


_remap_copied_object_references = remap_copied_object_references
