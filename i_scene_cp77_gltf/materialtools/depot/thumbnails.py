from pathlib import Path

import bpy
import bpy.utils.previews

from ...assetio.paths import LocalPath, local_path_key
from ...blender.identity import rna_identity
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

_PREVIEWS = None
_KEYS = {}
_LIMIT = 32


def clear_thumbnails():
    global _PREVIEWS
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None
    _KEYS.clear()


def microblend_icon(image):
    global _PREVIEWS
    if image is None:
        return 0
    try:
        raw_path = bpy.path.abspath(image.filepath, library=image.library)
        if not raw_path:
            preview = image.preview
            return preview.icon_id if preview is not None else 0
        path = LocalPath.from_value(raw_path).value
        if not Path(path).is_file():
            preview = image.preview
            return preview.icon_id if preview is not None else 0
        stamp = Path(path).stat().st_mtime_ns
        key = (rna_identity(image), local_path_key(path), stamp)
        cached = _KEYS.get(key)
        if cached is not None:
            return _PREVIEWS[cached].icon_id
        if _PREVIEWS is None:
            _PREVIEWS = bpy.utils.previews.new()
        if len(_KEYS) >= _LIMIT:
            oldest = next(iter(_KEYS))
            del _PREVIEWS[_KEYS.pop(oldest)]
        name = str(key)
        preview = _PREVIEWS.load(name, path, "IMAGE")
        _KEYS[key] = name
        return preview.icon_id
    except (OSError, AttributeError, ReferenceError, RuntimeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("microblend_icon", type(error).__name__),
            "microblend icon: fell back after %s",
            error,
            exc_info=True,
        )
        return 0
