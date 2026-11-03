from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ...core.log import get_logger, log_once
from ..blender.vehicle_lights import has_vehicle_lights

_LOG = get_logger(__name__)

_VEHICLE_COLLECTIONS = []
_COLLECTION_COUNT = -1


@persistent
def clear_vehicle_light_cache(_unused=None):
    global _COLLECTION_COUNT
    _VEHICLE_COLLECTIONS.clear()
    _COLLECTION_COUNT = -1


def _cache_is_live():
    try:
        return all(
            bpy.data.collections.get(collection.name) == collection
            for collection in _VEHICLE_COLLECTIONS
        )
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_cache_is_live", type(error).__name__),
            "cache is live: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def vehicle_light_collections():
    """Imported entity collections that carry vehicle lights or vehicle light zones"""
    global _COLLECTION_COUNT
    collection_count = len(bpy.data.collections)
    if collection_count != _COLLECTION_COUNT or not _cache_is_live():
        _VEHICLE_COLLECTIONS[:] = (
            collection
            for collection in bpy.data.collections
            if has_vehicle_lights(collection)
        )
        _COLLECTION_COUNT = collection_count
    return tuple(_VEHICLE_COLLECTIONS)
