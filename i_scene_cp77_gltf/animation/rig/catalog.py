from __future__ import annotations

import os

from ...paths import get_rig_dir


_BUNDLED_RIGS = (
    ("man_base", "man_base_full.glb"),
    ("woman_base", "woman_base_full.glb"),
    ("man_big", "man_big_full.glb"),
    ("man_fat", "man_fat_full.glb"),
    ("Judy", "judy_full.glb"),
    ("Songbird", "songbird_full.glb"),
    ("Panam", "panam_full.glb"),
    ("Jackie", "jackie_full.glb"),
    ("Rhino", "rhino_full.glb"),
    ("Dex", "dex_full.glb"),
    ("Adam Smasher", "smasher_full.glb"),
)


def bundled_rig_paths_and_names() -> tuple[tuple[str, ...], tuple[str, ...]]:
    root = get_rig_dir()
    names = tuple(name for name, _filename in _BUNDLED_RIGS)
    paths = tuple(os.path.join(root, filename) for _name, filename in _BUNDLED_RIGS)
    return paths, names


_BUNDLED_RIG_ENUM_ITEMS = tuple((name, name, "") for name, _filename in _BUNDLED_RIGS)


def bundled_rig_enum_items(_self=None, _context=None):
    return _BUNDLED_RIG_ENUM_ITEMS
