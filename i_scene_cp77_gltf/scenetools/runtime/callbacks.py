from __future__ import annotations

import bpy

from ..blender.images import RESOURCE_IMAGES
from .ownership import clear_runtime_cache


@bpy.app.handlers.persistent
def clear_loaded_file_caches(_dummy=None):
    clear_runtime_cache()
    RESOURCE_IMAGES.clear()
