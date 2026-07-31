import json
import os

from .paths import get_resources_dir


_PRESETS_PATH = os.path.join(get_resources_dir(), "vertex_color_presets.json")


def get_color_presets():
    if not os.path.exists(_PRESETS_PATH):
        return {}
    with open(_PRESETS_PATH, "r", encoding="utf-8") as preset_file:
        return json.load(preset_file)


def save_presets(presets):
    with open(_PRESETS_PATH, "w", encoding="utf-8") as preset_file:
        json.dump(presets, preset_file, indent=4)
    update_presets_items()


def update_presets_items():
    return [(name, name, "") for name in get_color_presets()]
