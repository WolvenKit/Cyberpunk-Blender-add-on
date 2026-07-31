from __future__ import annotations

import bpy

EXCLUSION_COLLECTION_NAME = "glTF_not_exported"


def collect_excluded_objects():
    """Scan the optional export-exclusion collection once.

    The collection primarily stores custom bone-shape objects. Export callers own
    the returned immutable set for the duration of one export operation; no frame,
    depsgraph, or persistent cache state participates in exclusion decisions.
    """

    root = bpy.data.collections.get(EXCLUSION_COLLECTION_NAME)
    if root is None:
        return frozenset()

    excluded = set()
    pending = [root]
    visited = set()
    while pending:
        collection = pending.pop()
        try:
            identity = int(collection.as_pointer())
        except (AttributeError, ReferenceError, TypeError, ValueError):
            identity = id(collection)
        if identity in visited:
            continue
        visited.add(identity)
        try:
            excluded.update(collection.objects)
            pending.extend(collection.children)
        except ReferenceError:
            continue
    return frozenset(excluded)
