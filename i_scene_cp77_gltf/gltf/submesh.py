from __future__ import annotations

import re
from functools import lru_cache

SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)
LOD_PATTERN = re.compile(r"LOD_(\d+)", re.IGNORECASE)


def submesh_index_from_name(name, fallback=None):
    match = SUBMESH_PATTERN.search(str(name or ""))
    return int(match.group(1)) if match else fallback


def lod_from_name(name, fallback=1):
    match = LOD_PATTERN.search(str(name or ""))
    return int(match.group(1)) if match else fallback


def submesh_name(index, lod=1):
    """The name a mesh exports under as submesh index of detail level lod"""
    return f"submesh_{int(index):02d}_LOD_{int(lod)}"


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
