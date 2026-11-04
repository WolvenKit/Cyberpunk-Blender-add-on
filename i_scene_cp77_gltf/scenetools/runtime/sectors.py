from __future__ import annotations

from dataclasses import dataclass

import bpy
from bpy.app.handlers import persistent

from ...blender.identity import rna_is_live
from ...exporters.sector.buffers import imported_sector_collections
from ...exporters.sector.new_sectors import new_sector_collections

# Each scene's sector collections by its session id, with the collection count they were found at.
_SECTORS: dict[int, tuple[int, SceneSectors]] = {}


@dataclass(frozen=True, slots=True)
class SceneSectors:
    """A scene's imported sector collections and its new-sector collections"""

    imported: tuple
    new: tuple


@persistent
def clear_sector_cache(_unused=None):
    _SECTORS.clear()


def scene_sectors(scene) -> SceneSectors:
    """The scene's sector collections"""
    count = len(bpy.data.collections)
    cached = _SECTORS.get(scene.session_uid)
    if (
        cached is not None
        and cached[0] == count
        and all(
            rna_is_live(collection)
            for collection in (*cached[1].imported, *cached[1].new)
        )
    ):
        return cached[1]
    sectors = SceneSectors(
        imported_sector_collections(scene), new_sector_collections(scene)
    )
    _SECTORS[scene.session_uid] = (count, sectors)
    return sectors
