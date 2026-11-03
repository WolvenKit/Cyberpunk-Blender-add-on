from __future__ import annotations

from pathlib import Path

import bpy

from ...assetio.paths import LocalPath, local_path_key
from ...blender.transactions import track_created_datablock
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

RESOURCE_PATH_KEY = "cp77_scenetools_resource_path"
_IMAGE_CACHE = {}
_IMAGE_COUNT = -1


def _resolved_path(path):
    return LocalPath.from_value(path).value


def _image_source_key(image):
    try:
        tagged = str(image.get(RESOURCE_PATH_KEY, "") or "")
        if tagged:
            return local_path_key(tagged)
        filepath = str(image.filepath_from_user() or "")
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_image_source_key", type(error).__name__),
            "image source key: fell back after %s",
            error,
            exc_info=True,
        )
        return ""
    return local_path_key(filepath) if filepath else ""


def clear_resource_image_cache():
    global _IMAGE_COUNT
    _IMAGE_CACHE.clear()
    _IMAGE_COUNT = -1


def _rebuild_image_cache():
    global _IMAGE_COUNT
    _IMAGE_CACHE.clear()
    for image in tuple(bpy.data.images):
        key = _image_source_key(image)
        if key:
            _IMAGE_CACHE.setdefault(key, image.name)
    _IMAGE_COUNT = len(bpy.data.images)


def _cache_image(source_key, image):
    global _IMAGE_COUNT
    _IMAGE_CACHE[source_key] = image.name
    _IMAGE_COUNT = len(bpy.data.images)


def _find_loaded_image(source_key):
    if _IMAGE_COUNT != len(bpy.data.images):
        _rebuild_image_cache()
    name = _IMAGE_CACHE.get(source_key)
    image = bpy.data.images.get(name) if name else None
    if image is not None and _image_source_key(image) == source_key:
        return image
    if name:
        _rebuild_image_cache()
        name = _IMAGE_CACHE.get(source_key)
        image = bpy.data.images.get(name) if name else None
        if image is not None and _image_source_key(image) == source_key:
            return image
    return None


def load_named_image(
    path, name, *, colorspace=None, check_existing=False, required=True
):
    path = Path(_resolved_path(path))
    source_path = str(path)
    source_key = local_path_key(source_path)
    image = _find_loaded_image(source_key)
    if image is None:
        if not path.is_file():
            if required:
                raise FileNotFoundError(path)
            return None
        before = len(bpy.data.images)
        image = bpy.data.images.load(str(path), check_existing=check_existing)
        if len(bpy.data.images) > before:
            track_created_datablock("images", image)
        image[RESOURCE_PATH_KEY] = source_path
        _cache_image(source_key, image)
        try:
            image.name = str(name)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("load_named_image 1", type(error).__name__),
                "load named image: fell back after %s",
                error,
                exc_info=True,
            )
    if colorspace:
        try:
            image.colorspace_settings.name = colorspace
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("load_named_image 2", type(error).__name__),
                "load named image: fell back after %s",
                error,
                exc_info=True,
            )
    return image
