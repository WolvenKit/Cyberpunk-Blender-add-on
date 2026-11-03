from __future__ import annotations

from dataclasses import dataclass

<<<<<<< Updated upstream
from .model import NodeCategory
from ..common.paths import depot_path_key
from ..entity.resources import ENTITY_INDEX_EXTENSIONS
from ...materials.repository import MATERIAL_IMAGE_EXTENSIONS

SECTOR_INDEX_EXTENSIONS = tuple(dict.fromkeys((
    *ENTITY_INDEX_EXTENSIONS,
    ".streamingsector.json",
    ".mi.json",
    ".cfoliage.json",
    ".particle.json",
    ".effect.json",
    ".acousticdata.json",
    ".envprobe.json",
    ".cminimap.json",
    ".gidata.json",
    ".smartobjects.json",
    ".workspot.json",
    ".actionanimdb.json",
    ".ies.json",
    ".ies",
)))

OPTIONAL_SECTOR_NODE_TYPES = {
    "lights": frozenset({"worldStaticLightNode"}),
    "foliage": frozenset({
        "worldFoliageNode",
        "worldFoliageDestructionNode",
    }),
    "effects": frozenset({
        "worldStaticParticleNode",
        "worldEffectNode",
    }),
    "collisions": frozenset({
        "worldCollisionNode",
        "worldFoliageDestructionNode",
        "worldTerrainCollisionNode",
    }),
    "proxies": frozenset({
=======
from ...assetio.paths import depot_path_key
from ...materials.repository import MATERIAL_IMAGE_EXTENSIONS
from ..entity.policy import SHADOW_MESH_SUFFIX
from ..entity.resources import (
    ENTITY_INDEX_EXTENSIONS,
    ENTITY_INK_INDEX_EXTENSIONS,
)
from .model import NodeCategory

SECTOR_INDEX_EXTENSIONS = tuple(
    dict.fromkeys(
        (
            *ENTITY_INDEX_EXTENSIONS,
            ".streamingsector.json",
            ".mi.json",
            ".cfoliage.json",
            ".particle.json",
            ".effect.json",
            ".acousticdata.json",
            ".envprobe.json",
            ".cminimap.json",
            ".gidata.json",
            ".smartobjects.json",
            ".workspot.json",
            ".actionanimdb.json",
            ".ies.json",
            ".ies",
        )
    )
)

# Nodes that place an entity template.
ENTITY_NODE_TYPES = frozenset(
    {
        "worldEntityNode",
        "worldDeviceNode",
    }
)

# The import choices, in dialog order. Each names one kind of sector content; a ticked choice counts only while its
# category is switched on, which the dialog resolves before building the options.
SECTOR_CHOICES = (
    "sector_lights",
    "entity_lights",
    "light_linking",
    "light_channel_volumes",
    "reflection_probes",
    "gi_data",
    "foliage",
    "effects",
    "fog",
    "screens",
    "world_collisions",
    "entity_colliders",
    "terrain_heightfields",
    "foliage_destruction",
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
    "sound_emitters",
    "acoustic_data",
)

PROXY_NODE_TYPES = frozenset(
    {
>>>>>>> Stashed changes
        "worldBuildingProxyMeshNode",
        "worldGenericProxyMeshNode",
        "worldEntityProxyMeshNode",
        "worldDestructibleEntityProxyMeshNode",
        "worldDestructibleProxyMeshNode",
        "worldTerrainProxyMeshNode",
        "worldRoadProxyMeshNode",
<<<<<<< Updated upstream
    }),
    "acoustics": frozenset({"worldAcousticSectorNode"}),
    "occluders": frozenset({
        "worldStaticOccluderMeshNode",
        "worldInstancedOccluderNode",
    }),
    "minimap": frozenset({"MinimapDataNode"}),
    "environment_probes": frozenset({"worldReflectionProbeNode"}),
    "world_metadata": frozenset({
        "worldAmbientAreaNode",
        "worldLightChannelVolumeNode",
        "worldLightChannelShapeNode",
        "worldInteriorAreaNode",
        "worldInteriorMapNode",
        "worldStaticFogVolumeNode",
        "worldStaticSoundEmitterNode",
        "gameWorldBoundaryNode",
    }),
    "gi": frozenset({
        "worldGINode",
        "worldGISpaceNode",
    }),
}

OPTIONAL_SECTOR_INDEX_EXTENSIONS = {
    "lights": frozenset({".ies", ".ies.json"}),
    "foliage": frozenset({".cfoliage.json"}),
    "effects": frozenset({".particle.json", ".effect.json"}),
    "acoustics": frozenset({".acousticdata.json"}),
    "minimap": frozenset({".cminimap.json"}),
    "environment_probes": frozenset({".envprobe.json"}),
    "gi": frozenset({".gidata.json"}),
}

GI_HELPER_MESH_PATHS = frozenset({
    "base/lighting/gi_visible_game_invisible.w2mesh",
})

_CATEGORY_BY_OPTION = {
    "lights": NodeCategory.LIGHT,
    "foliage": NodeCategory.FOLIAGE,
    "effects": NodeCategory.EFFECT,
    "collisions": NodeCategory.COLLISION,
    "proxies": NodeCategory.PROXY,
    "acoustics": NodeCategory.ACOUSTIC,
    "occluders": NodeCategory.OCCLUDER,
    "minimap": NodeCategory.MINIMAP,
    "environment_probes": NodeCategory.ENVIRONMENT_PROBE,
    "world_metadata": NodeCategory.WORLD_METADATA,
    "gi": NodeCategory.GI,
}
_OPTION_FIELD_BY_NAME = {
    "lights": "with_lights",
    "foliage": "import_foliage",
    "effects": "import_effects",
    "collisions": "import_collisions",
    "proxies": "import_proxies",
    "acoustics": "import_acoustics",
    "occluders": "import_occluders",
    "minimap": "import_minimap",
    "environment_probes": "import_environment_probes",
    "world_metadata": "import_world_metadata",
    "gi": "import_gi",
}
_OPTIONS_BY_NODE_TYPE = {}
_CATEGORY_BY_NODE_TYPE = {}
for _option_name, _node_types in OPTIONAL_SECTOR_NODE_TYPES.items():
    for _node_type in _node_types:
        _OPTIONS_BY_NODE_TYPE.setdefault(_node_type, []).append(_option_name)
        _CATEGORY_BY_NODE_TYPE.setdefault(
            _node_type,
            _CATEGORY_BY_OPTION[_option_name],
        )
_OPTIONS_BY_NODE_TYPE = {
    node_type: tuple(option_names)
    for node_type, option_names in _OPTIONS_BY_NODE_TYPE.items()
}

=======
    }
)

# Node type -> the choices that import it; any one of them is enough.
NODE_TYPE_CHOICES = {
    "worldStaticLightNode": frozenset({"sector_lights"}),
    "worldLightChannelVolumeNode": frozenset(
        {"light_linking", "light_channel_volumes"}
    ),
    "worldLightChannelShapeNode": frozenset({"light_linking", "light_channel_volumes"}),
    "worldReflectionProbeNode": frozenset({"reflection_probes"}),
    "worldGINode": frozenset({"gi_data"}),
    "worldGISpaceNode": frozenset({"gi_data"}),
    "worldFoliageNode": frozenset({"foliage"}),
    "worldStaticParticleNode": frozenset({"effects"}),
    "worldEffectNode": frozenset({"effects"}),
    "worldStaticFogVolumeNode": frozenset({"fog"}),
    "worldCollisionNode": frozenset({"world_collisions"}),
    "worldTerrainCollisionNode": frozenset({"terrain_heightfields"}),
    "worldFoliageDestructionNode": frozenset({"foliage_destruction"}),
    "worldStaticOccluderMeshNode": frozenset({"occluders"}),
    "worldInstancedOccluderNode": frozenset({"occluders"}),
    "worldAmbientAreaNode": frozenset({"ambient_areas"}),
    "worldInteriorAreaNode": frozenset({"interior_areas"}),
    "worldInteriorMapNode": frozenset({"interior_maps"}),
    "gameWorldBoundaryNode": frozenset({"world_boundaries"}),
    "worldTriggerAreaNode": frozenset({"triggers"}),
    "gameKillTriggerNode": frozenset({"triggers"}),
    "worldSplineNode": frozenset({"splines"}),
    "worldSpeedSplineNode": frozenset({"splines"}),
    "worldAISpotNode": frozenset({"ai_spawners"}),
    "worldPopulationSpawnerNode": frozenset({"ai_spawners"}),
    "worldSmartObjectNode": frozenset({"smart_objects"}),
    "worldCompiledSmartObjectsNode": frozenset({"smart_objects"}),
    "worldStaticGpsLocationEntranceMarkerNode": frozenset({"gps_markers"}),
    "MinimapDataNode": frozenset({"minimap"}),
    "worldStaticSoundEmitterNode": frozenset({"sound_emitters"}),
    "worldAcousticSectorNode": frozenset({"acoustic_data"}),
}

# Choices a node type needs on top of its own: foliage destruction hangs off the foliage instances.
NODE_TYPE_REQUIREMENTS = {
    "worldFoliageDestructionNode": frozenset({"foliage"}),
}

# Index extension -> the choices that need it; with none of them chosen the extension stays out of the asset index.
CHOICE_INDEX_EXTENSIONS = {
    ".ies": frozenset({"sector_lights", "entity_lights"}),
    ".ies.json": frozenset({"sector_lights", "entity_lights"}),
    ".cfoliage.json": frozenset({"foliage"}),
    ".particle.json": frozenset({"effects"}),
    ".effect.json": frozenset({"effects"}),
    ".acousticdata.json": frozenset({"acoustic_data"}),
    ".cminimap.json": frozenset({"minimap"}),
    ".envprobe.json": frozenset({"reflection_probes"}),
    ".gidata.json": frozenset({"gi_data"}),
    ".smartobjects.json": frozenset({"smart_objects"}),
    ".workspot.json": frozenset({"smart_objects"}),
    ".actionanimdb.json": frozenset({"smart_objects"}),
}

GI_HELPER_MESH_PATHS = frozenset(
    {
        "base/lighting/gi_visible_game_invisible.w2mesh",
    }
)

# The choices that bring PhysX actors into the scene.
COLLISION_CHOICES = frozenset(
    {
        "world_collisions",
        "entity_colliders",
        "terrain_heightfields",
        "foliage_destruction",
    }
)

_CATEGORY_BY_CHOICE = {
    **dict.fromkeys(
        (
            "sector_lights",
            "light_linking",
            "light_channel_volumes",
            "reflection_probes",
            "gi_data",
        ),
        NodeCategory.LIGHT,
    ),
    "foliage": NodeCategory.FOLIAGE,
    "effects": NodeCategory.EFFECT,
    "fog": NodeCategory.FOG,
    **dict.fromkeys(
        ("world_collisions", "terrain_heightfields", "foliage_destruction"),
        NodeCategory.COLLISION,
    ),
    **dict.fromkeys(
        (
            "occluders",
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
        NodeCategory.GAMEPLAY,
    ),
    **dict.fromkeys(("sound_emitters", "acoustic_data"), NodeCategory.AUDIO),
}
_CATEGORY_BY_NODE_TYPE = {
    **{
        node_type: _CATEGORY_BY_CHOICE[min(choices)]
        for node_type, choices in NODE_TYPE_CHOICES.items()
    },
    **dict.fromkeys(PROXY_NODE_TYPES, NodeCategory.PROXY),
}

DECAL_MODES = frozenset({"CONFORMAL", "LEGACY_PLANES", "PROJECTORS_ONLY"})
EXISTING_SECTOR_MODES = frozenset({"ADD_MISSING", "REPLACE"})
COLLECTION_LAYOUTS = frozenset({"SOURCE_NODES", "SECTOR"})


>>>>>>> Stashed changes
def classify_node_type(node_type):
    return _CATEGORY_BY_NODE_TYPE.get(
        str(node_type or ""),
        NodeCategory.STANDARD,
    )


@dataclass(slots=True, frozen=True)
class SectorImportOptions:
    with_materials: bool
<<<<<<< Updated upstream
    remap_depot: bool = False
    import_collisions: bool = False
    am_modding: bool = False
    with_lights: bool = False
    import_foliage: bool = False
    import_effects: bool = False
    selected_variant: int | None = None
    import_proxies: bool = False
    import_acoustics: bool = False
    import_occluders: bool = False
    import_minimap: bool = False
    import_environment_probes: bool = False
    import_world_metadata: bool = False
    import_gi: bool = False
    scale_factor: float = 1.0

    def optional_import_enabled(self, option_name):
        return bool(getattr(self, _OPTION_FIELD_BY_NAME[option_name]))

    @property
    def optional_imports(self):
        return {
            option_name: self.optional_import_enabled(option_name)
            for option_name in _OPTION_FIELD_BY_NAME
        }

    @property
    def index_extensions(self):
        excluded = set()
        for option_name, extensions in OPTIONAL_SECTOR_INDEX_EXTENSIONS.items():
            if not self.optional_import_enabled(option_name):
                excluded.update(extensions)
        extensions = [
            extension
            for extension in SECTOR_INDEX_EXTENSIONS
            if extension not in excluded
        ]
        if self.with_materials:
            extensions.extend(MATERIAL_IMAGE_EXTENSIONS)
        return tuple(dict.fromkeys(extensions))

    def node_skip_reason(self, node):
        for option_name in _OPTIONS_BY_NODE_TYPE.get(
            node.node_type,
            (),
        ):
            if not self.optional_import_enabled(option_name):
                return f"optional:{option_name}"

        if (
            not self.import_gi
            and depot_path_key(node.mesh_path) in GI_HELPER_MESH_PATHS
        ):
            return "optional:gi-helper"

=======
    decal_mode: str = "CONFORMAL"
    remap_depot: bool = False
    import_proxies: bool = False
    selected_variant: int | None = None
    scale_factor: float = 1.0
    existing_sector_mode: str = "ADD_MISSING"
    collection_layout: str = "SOURCE_NODES"
    choices: frozenset[str] = frozenset()

    def __post_init__(self):
        mode = str(self.decal_mode or "CONFORMAL").upper()
        if mode not in DECAL_MODES:
            raise ValueError(f"Unsupported sector decal mode: {self.decal_mode}")
        object.__setattr__(self, "decal_mode", mode)
        existing_mode = str(self.existing_sector_mode or "ADD_MISSING").upper()
        if existing_mode not in EXISTING_SECTOR_MODES:
            raise ValueError(
                f"Unsupported existing-sector mode: {self.existing_sector_mode}"
            )
        object.__setattr__(self, "existing_sector_mode", existing_mode)
        layout = str(self.collection_layout or "SOURCE_NODES").upper()
        if layout not in COLLECTION_LAYOUTS:
            raise ValueError(
                f"Unsupported sector collection layout: {self.collection_layout}"
            )
        object.__setattr__(self, "collection_layout", layout)
        choices = frozenset(str(choice) for choice in self.choices)
        unknown = sorted(choices.difference(SECTOR_CHOICES))
        if unknown:
            raise ValueError(f"Unknown sector import choices: {', '.join(unknown)}")
        object.__setattr__(self, "choices", choices)

    def chosen(self, name):
        return name in self.choices

    @property
    def index_extensions(self):
        extensions = [
            extension
            for extension in SECTOR_INDEX_EXTENSIONS
            if extension not in CHOICE_INDEX_EXTENSIONS
            or CHOICE_INDEX_EXTENSIONS[extension] & self.choices
        ]
        if self.with_materials:
            extensions.extend(MATERIAL_IMAGE_EXTENSIONS)
        if self.chosen("screens"):
            extensions.extend(ENTITY_INK_INDEX_EXTENSIONS)
        return tuple(dict.fromkeys(extensions))

    def missing_choice(self, node_type):
        """The choice a node type still needs to import, or "" when the choices import it"""
        owners = NODE_TYPE_CHOICES.get(node_type)
        if owners and not owners & self.choices:
            return min(owners)
        for required in sorted(NODE_TYPE_REQUIREMENTS.get(node_type, ())):
            if not self.chosen(required):
                return required
        return ""

    def node_skip_reason(self, node):
        node_type = node.node_type
        mesh_key = depot_path_key(node.mesh_path)
        # Sectors never import shadow meshes.
        if mesh_key.endswith(SHADOW_MESH_SUFFIX):
            return "shadow"
        if node_type in PROXY_NODE_TYPES and not self.import_proxies:
            return "proxies"
        missing = self.missing_choice(node_type)
        if missing:
            return f"choice:{missing}"
        if not self.chosen("gi_data") and mesh_key in GI_HELPER_MESH_PATHS:
            return "choice:gi_data"
>>>>>>> Stashed changes
        return ""
