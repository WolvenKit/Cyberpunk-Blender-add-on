from __future__ import annotations

import re
from functools import lru_cache

SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)


def submesh_index_from_name(name, fallback=None):
    match = SUBMESH_PATTERN.search(str(name or ""))
    return int(match.group(1)) if match else fallback


@lru_cache(maxsize=4096)
def _submesh_index_from_names(object_name, material_names):
    index = submesh_index_from_name(object_name, None)
    if index is not None:
        return index
    for material_name in material_names:
        index = submesh_index_from_name(material_name, None)
        if index is not None:
            return index
    return None


def submesh_index_for_object(obj, fallback=None):
    try:
        explicit = int(obj.get("cp77_submesh_index", -1))
    except (AttributeError, ReferenceError, TypeError, ValueError):
        explicit = -1
    if explicit >= 0:
        return explicit
    try:
        name = str(getattr(obj, "name", "") or "")
        data = getattr(obj, "data", None)
        materials = getattr(data, "materials", ()) if data is not None else ()
        material_names = tuple(
            str(getattr(material, "name", "") or "")
            for material in materials
            if material is not None
        )
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        name, material_names = "", ()
    index = _submesh_index_from_names(name, material_names)
    return fallback if index is None else index


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
