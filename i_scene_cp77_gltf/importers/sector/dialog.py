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

# Tooltips: what each button and tick places and how it shows in Blender, as the placement handlers build it.
CATEGORY_DESCRIPTIONS = {
    "lighting": (
        "Sector and entity lights, light channels, reflection probes and GI markers. Lights are Blender lights, "
        "probes are sphere light probes, channel volumes and GI markers are wireframes"
    ),
    "foliage": "worldFoliageNode grass, bushes and trees, one instance per foliage population entry",
    "effects": "Particle and effect positions as small wire sphere empties; the effects themselves are not built",
    "fog": "Fog volumes as boxes with a volume scatter material, which renders as haze",
    "screens": "The ink widgets of entities placed in the sector, bound to their screen meshes",
    "collisions": (
        "PhysX collision actors: empties whose shapes are drawn as viewport lines by the collision overlay. "
        "They are not meshes and do not render"
    ),
    "gameplay": (
        "Occluders, areas, triggers, boundaries, splines, spawners and markers. Occluders are ordinary solid "
        "meshes laid over the real geometry; the rest are wireframes, empties and curves"
    ),
    "audio": "Sound emitters as sphere empties and acoustic sectors as 32 m wireframe boxes",
}
CHOICE_DESCRIPTIONS = {
    "sector_lights": "Import worldStaticLightNode as Blender lights, with their IES profiles",
    "entity_lights": "Import the light components of entities placed in the sector",
    "light_linking": "Link lights to meshes through their light channels; drops the channel volume objects afterwards",
    "light_channel_volumes": "Keep the light channel volumes as wireframes hidden from renders",
    "reflection_probes": "Import worldReflectionProbeNode as Blender sphere light probes",
    "gi_data": "Import worldGINode as wire cube empties and worldGISpaceNode as wireframes; also keeps GI helper meshes",
    "foliage": "Import worldFoliageNode grass, bushes and trees as instances of their meshes",
    "effects": "Import worldStaticParticleNode and worldEffectNode as wire sphere empties at the effect positions",
    "fog": "Import worldStaticFogVolumeNode as boxes with a volume scatter material",
    "screens": "Import the WorldWidgetComponent ink widgets of placed entities and bind them to their meshes",
    "world_collisions": "Import worldCollisionNode as collision actors drawn as viewport lines; not rendered",
    "entity_colliders": "Import the collider components of placed entities as collision actors",
    "terrain_heightfields": "Import worldTerrainCollisionNode heightfields as collision actors, overlay drawing off",
    "foliage_destruction": "Import worldFoliageDestructionNode as box collision actors; needs Foliage switched on",
    "occluders": (
        "Import worldStaticOccluderMeshNode and worldInstancedOccluderNode, the game's occlusion meshes, as "
        "ordinary solid meshes. They sit over the real geometry and hide it"
    ),
    "entity_occluders": (
        "Import the entStaticOccluderMeshComponent meshes of placed entities as solid meshes over the real ones"
    ),
    "ambient_areas": "Import worldAmbientAreaNode outlines as wireframe volumes",
    "interior_areas": "Import worldInteriorAreaNode outlines as wireframe volumes",
    "interior_maps": "Import worldInteriorMapNode as wire cube empties, with its map packed as a greyscale image",
    "world_boundaries": "Import gameWorldBoundaryNode outlines as wireframe volumes",
    "triggers": "Import worldTriggerAreaNode and gameKillTriggerNode outlines as wireframe volumes",
    "splines": "Import worldSplineNode and worldSpeedSplineNode as curves",
    "ai_spawners": "Import worldAISpotNode as cone empties and worldPopulationSpawnerNode as axes empties",
    "smart_objects": "Import worldSmartObjectNode and worldCompiledSmartObjectsNode as empties, with their workspots",
    "gps_markers": "Import worldStaticGpsLocationEntranceMarkerNode as arrow empties",
    "minimap": "Import MinimapDataNode bounds as wireframe boxes",
    "sound_emitters": "Import worldStaticSoundEmitterNode as sphere empties sized to their radius",
    "acoustic_data": "Import worldAcousticSectorNode as 32 m wireframe boxes",
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
