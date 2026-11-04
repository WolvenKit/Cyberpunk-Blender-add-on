from __future__ import annotations

from dataclasses import dataclass

from ..common import dialog_model
from ..common.dialog_model import Category
from .options import (
    COLLECTION_LAYOUTS,
    DECAL_MODES,
    EXISTING_SECTOR_MODES,
    SECTOR_CHOICES,
    SectorImportOptions,
)

CATEGORIES = (
    Category(
        "lighting",
        "Lighting",
        (
            "sector_lights",
            "entity_lights",
            "light_linking",
            "light_channel_volumes",
            "reflection_probes",
            "gi_data",
        ),
    ),
    Category("foliage", "Foliage", ("foliage",)),
    Category("effects", "Effects", ("effects",)),
    Category("fog", "Fog", ("fog",)),
    Category("screens", "Screens", ("screens",)),
    Category(
        "collisions",
        "Collisions",
        (
            "world_collisions",
            "entity_colliders",
            "terrain_heightfields",
            "foliage_destruction",
        ),
    ),
    Category(
        "gameplay",
        "Gameplay",
        (
            "occluders",
            "entity_occluders",
            "ambient_areas",
            "interior_areas",
            "interior_maps",
            "world_boundaries",
            "triggers",
            "splines",
            "ai_spawners",
            "smart_objects",
            "gps_markers",
            "minimap",
        ),
    ),
    Category("audio", "Audio", ("sound_emitters", "acoustic_data")),
)
CATEGORY_NAMES = frozenset(category.name for category in CATEGORIES)

CHOICE_LABELS = {
    "sector_lights": "Sector Lights",
    "entity_lights": "Entity Lights",
    "light_linking": "Light Linking",
    "light_channel_volumes": "Light Channel Volumes",
    "reflection_probes": "Reflection Probes",
    "gi_data": "GI Data",
    "foliage": "Foliage",
    "effects": "Effects",
    "fog": "Fog",
    "screens": "Screens",
    "world_collisions": "World Collisions",
    "entity_colliders": "Entity Colliders",
    "terrain_heightfields": "Terrain Heightfields",
    "foliage_destruction": "Foliage Destruction",
    "occluders": "Occluders",
    "entity_occluders": "Entity Occluders",
    "ambient_areas": "Ambient Areas",
    "interior_areas": "Interior Areas",
    "interior_maps": "Interior Maps",
    "world_boundaries": "World Boundaries",
    "triggers": "Triggers",
    "splines": "Splines",
    "ai_spawners": "AI & Spawners",
    "smart_objects": "Smart Objects",
    "gps_markers": "GPS Markers",
    "minimap": "Minimap Data",
    "sound_emitters": "Sound Emitters",
    "acoustic_data": "Acoustic Data",
}

# The ticks a category brings the first time it is switched on.
STARTING_CHOICES = frozenset(
    {
        "sector_lights",
        "light_linking",
        "world_collisions",
        "splines",
        "ambient_areas",
        "interior_areas",
        "sound_emitters",
    }
)

_MEMORY_KEY = "sector_import_choices"
SECTOR_IMPORT_SETTINGS = (
    "materials",
    "proxies",
    "refresh_index",
    "decal_mode",
    "existing_sectors",
    "collections",
)


@dataclass(frozen=True, slots=True)
class DialogState:
    materials: bool
    proxies: bool
    refresh_index: bool
    decal_mode: str
    existing_sectors: str
    collections: str
    categories: frozenset[str]
    choices: frozenset[str]

    @classmethod
    def default(cls):
        return cls(
            materials=True,
            proxies=False,
            refresh_index=False,
            decal_mode="CONFORMAL",
            existing_sectors="ADD_MISSING",
            collections="SOURCE_NODES",
            categories=frozenset(),
            choices=STARTING_CHOICES,
        )

    def to_json(self):
        return dialog_model.memory_json(self)

    @classmethod
    def from_json(cls, text):
        """The state in text"""
        return dialog_model.read_memory(
            text,
            cls.default(),
            flags=("materials", "proxies", "refresh_index"),
            names={
                "decal_mode": DECAL_MODES,
                "existing_sectors": EXISTING_SECTOR_MODES,
                "collections": COLLECTION_LAYOUTS,
            },
            sets={"categories": CATEGORY_NAMES, "choices": frozenset(SECTOR_CHOICES)},
        )

    def effective_choices(self):
        """The ticked choices of the switched-on categories"""
        return dialog_model.effective_choices(CATEGORIES, self.categories, self.choices)

    def options(self, remap_depot):
        return SectorImportOptions(
            with_materials=self.materials,
            decal_mode=self.decal_mode,
            remap_depot=bool(remap_depot),
            import_proxies=self.proxies,
            existing_sector_mode=self.existing_sectors,
            collection_layout=self.collections,
            choices=self.effective_choices(),
        )

    def inactive_choices(self):
        return (
            frozenset()
            if "foliage" in self.categories
            else frozenset({"foliage_destruction"})
        )


def remembered_state(preferences):
    return DialogState.from_json(dialog_model.remembered_text(preferences, _MEMORY_KEY))


def remember_state(preferences, state):
    dialog_model.remember_text(preferences, _MEMORY_KEY, state.to_json())
