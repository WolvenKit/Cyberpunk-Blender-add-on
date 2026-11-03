import os

from ..assetio.atomic import atomic_write_json
from ..assetio.documents import load_json_payload
from ..assetio.resources import get_resources_dir
from ..core.addon_identity import user_config_dir

_FILE_NAME = "vertex_color_presets.json"
# Blender reads enum item strings after the callback returns, so the items stay alive here until a save.
_ITEMS_CACHE = {}


def user_presets_path():
    return os.path.join(user_config_dir(), _FILE_NAME)


def get_color_presets():
    for path in (user_presets_path(), os.path.join(get_resources_dir(), _FILE_NAME)):
        if os.path.exists(path):
            return dict(load_json_payload(path))
    return {}


def save_presets(presets):
    atomic_write_json(user_presets_path(), presets, indent=4)
    invalidate_preset_items()


def invalidate_preset_items():
    _ITEMS_CACHE.clear()


def preset_enum_items(_self, _context):
    items = _ITEMS_CACHE.get("items")
    if items is None:
        items = _ITEMS_CACHE["items"] = [
            (name, name, "") for name in get_color_presets()
        ]
    return items
