from __future__ import annotations

from pathlib import Path

import bpy

from ...assetio.paths import LocalPath, local_path_key
from ...blender.image_cache import LoadedImageIndex
from ...blender.transactions import track_created_datablock
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

RESOURCE_PATH_KEY = "cp77_scenetools_resource_path"


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


RESOURCE_IMAGES = LoadedImageIndex(_image_source_key)


def load_named_image(
    path, name, *, colorspace=None, check_existing=False, required=True
):
    path = Path(_resolved_path(path))
    source_path = str(path)
    source_key = local_path_key(source_path)
    image = RESOURCE_IMAGES.find(source_key)
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
        RESOURCE_IMAGES.remember(source_key, image)
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
