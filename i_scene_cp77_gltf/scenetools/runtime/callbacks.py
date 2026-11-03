from __future__ import annotations

import bpy

from ..blender.images import clear_resource_image_cache
from .ownership import clear_runtime_cache


@bpy.app.handlers.persistent
def clear_loaded_file_caches(_dummy=None):
    clear_runtime_cache()
    clear_resource_image_cache()
