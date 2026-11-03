from __future__ import annotations

<<<<<<< Updated upstream
=======
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)
>>>>>>> Stashed changes


def link_collection_once(parent, child):
    if parent.children.get(child.name) is not child:
        parent.children.link(child)


<<<<<<< Updated upstream
_link_collection_once = link_collection_once


def unlink_collection_once(parent, child):
    if parent.children.get(child.name) is child:
        parent.children.unlink(child)


_unlink_collection_once = unlink_collection_once


=======
>>>>>>> Stashed changes
def preserve_world_parent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    try:
        obj.matrix_parent_inverse = parent.matrix_world.inverted_safe()
<<<<<<< Updated upstream
    except AttributeError:
=======
    except AttributeError as error:
        log_once(
            _LOG,
            "DEBUG",
            ("preserve_world_parent", type(error).__name__),
            "preserve world parent: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world


<<<<<<< Updated upstream
_preserve_world_parent = preserve_world_parent


def remap_copied_object_references(copied_objects, object_map):
    """Remap common Blender object references after copying an object graph."""
=======
def remap_copied_object_references(copied_objects, object_map):
    """Remap common Blender object references after copying an object graph"""
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream


_remap_copied_object_references = remap_copied_object_references
=======
>>>>>>> Stashed changes
