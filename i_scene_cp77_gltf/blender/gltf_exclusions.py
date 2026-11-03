from __future__ import annotations

import bpy

from ..core.log import get_logger, log_once

_LOG = get_logger(__name__)

EXCLUSION_COLLECTION_NAME = "glTF_not_exported"


def collect_excluded_objects():
    """Scan the optional export-exclusion collection once"""

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
        except (AttributeError, ReferenceError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("collect_excluded_objects", type(error).__name__),
                "collect excluded objects: fell back after %s",
                error,
                exc_info=True,
            )
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
