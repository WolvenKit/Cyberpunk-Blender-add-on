from __future__ import annotations

from dataclasses import dataclass

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
        "worldBuildingProxyMeshNode",
        "worldGenericProxyMeshNode",
        "worldEntityProxyMeshNode",
        "worldDestructibleEntityProxyMeshNode",
        "worldDestructibleProxyMeshNode",
        "worldTerrainProxyMeshNode",
        "worldRoadProxyMeshNode",
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

def classify_node_type(node_type):
    return _CATEGORY_BY_NODE_TYPE.get(
        str(node_type or ""),
        NodeCategory.STANDARD,
    )


@dataclass(slots=True, frozen=True)
class SectorImportOptions:
    with_materials: bool
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

        return ""
