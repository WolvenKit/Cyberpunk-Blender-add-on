from __future__ import annotations

import re

SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)


def submesh_index_from_name(name, fallback=None):
    match = SUBMESH_PATTERN.search(str(name or ""))
    return int(match.group(1)) if match else fallback


def submesh_index_for_object(obj, fallback=None):
    try:
        explicit = int(obj.get("cp77_submesh_index", -1))
    except (AttributeError, ReferenceError, TypeError, ValueError):
        explicit = -1
    if explicit >= 0:
        return explicit
    try:
        name = getattr(obj, "name", "")
    except ReferenceError:
        name = ""
    return submesh_index_from_name(name, fallback)


def ordered_submesh_objects(objects):
    indexed = []
    for input_index, obj in enumerate(objects):
        authored_index = submesh_index_for_object(obj, None)
        indexed.append(
            (
                authored_index is None,
                authored_index if authored_index is not None else input_index,
                input_index,
                obj,
            )
        )
    indexed.sort(key=lambda item: item[:3])
    return [item[3] for item in indexed]
