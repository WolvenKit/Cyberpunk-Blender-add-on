from dataclasses import dataclass
<<<<<<< Updated upstream
from functools import lru_cache
from importlib import import_module


@lru_cache(maxsize=512)
def _norm(path: str) -> str:
    return path.replace("/", "\\").casefold() if path else ""


@lru_cache(maxsize=None)
def _handler_class(module_name: str, class_name: str):
    module = import_module(f"...material_types.{module_name}", __package__)
    return getattr(module, class_name)
=======
from functools import cache
from importlib import import_module

from ...assetio.paths import backslash_depot_key


@cache
def _handler_module(module_name: str):
    return import_module(f"...material_types.{module_name}", __package__)


@cache
def _handler_class(module_name: str, class_name: str):
    return getattr(_handler_module(module_name), class_name)


@cache
def _handler_cache_identity(module_name: str):
    return getattr(_handler_module(module_name), "material_cache_identity", None)
>>>>>>> Stashed changes


@dataclass(frozen=True, slots=True)
class HandlerFactory:
    module_name: str
    class_name: str
    mode: str

<<<<<<< Updated upstream
=======
    def cache_identity(self, raw_material):
        identity = _handler_cache_identity(self.module_name)
        return identity(raw_material) if identity is not None else raw_material

>>>>>>> Stashed changes
    def __call__(self, builder, raw_material):
        handler = _handler_class(self.module_name, self.class_name)
        if self.mode == "bip":
            return handler(builder.BasePath, builder.image_format, builder.ProjPath)
        if self.mode == "bipm":
<<<<<<< Updated upstream
            return handler(builder.BasePath, builder.image_format, builder.ProjPath, builder.MeshPath)
=======
            return handler(
                builder.BasePath,
                builder.image_format,
                builder.ProjPath,
                builder.MeshPath,
            )
>>>>>>> Stashed changes
        if self.mode == "bi":
            return handler(builder.BasePath, builder.image_format)
        if self.mode == "bip_enablemask":
            return handler(
                builder.BasePath,
                builder.image_format,
                builder.ProjPath,
                raw_material.get("EnableMask", False),
            )
        raise ValueError(f"Unknown material handler mode: {self.mode}")


@dataclass(frozen=True, slots=True)
class MaterialRule:
    factory: HandlerFactory
    no_shadows: bool = False
    preserve_render_method: bool = False
    mesh_path_sensitive: bool = False
<<<<<<< Updated upstream
=======
    semantic_cache_identity: bool = False
>>>>>>> Stashed changes


class MaterialRegistry:
    def __init__(self) -> None:
        self.by_template = {}

    def register(self, templates, rule: MaterialRule) -> None:
        for template in templates:
<<<<<<< Updated upstream
            key = _norm(template)
=======
            key = backslash_depot_key(template)
>>>>>>> Stashed changes
            existing = self.by_template.get(key)
            if existing is not None and existing != rule:
                raise ValueError(f"Conflicting material handler for {template}")
            self.by_template[key] = rule

    def resolve(self, template: str):
<<<<<<< Updated upstream
        return self.by_template.get(_norm(template))


def _handler_factory(module_name, class_name, mode):
    return HandlerFactory(module_name, class_name, mode)
=======
        return self.by_template.get(backslash_depot_key(template))
>>>>>>> Stashed changes


REGISTRY = MaterialRegistry()

<<<<<<< Updated upstream
# Multilayered group
REGISTRY.register([
    "engine\\materials\\multilayered.mt",
    "base\\materials\\silverhand_overlay_blendable.mt",
    "base\\materials\\silverhand_overlay.mt",
    "base\\materials\\vehicle_destr_blendshape.mt",
    "base\\materials\\multilayered_clear_coat.mt",
    "base\\materials\\multilayered_terrain.mt",
    "base\\materials\\cloth_tarps.mt",
    "base\\fx\\_shaders\\blackwall_blendable.mt",
], MaterialRule(factory=_handler_factory("multilayered", "Multilayered", "bip")))

# Mesh decals
REGISTRY.register([
    "base\\materials\\mesh_decal.mt",
    "base\\materials\\mesh_decal_blendable.mt",
    "base\\materials\\mesh_decal_wet_character.mt",
    "base\\materials\\mesh_decal_revealed.mt",
    "base\\materials\\mesh_decal_double_diffuse.mt",
    "base\\materials\\mesh_decal_gradientmap_recolor.mt",
    "base\\materials\\mesh_decal_gradientmap_recolor_blendable.mt",
    "base\\fx\\_shaders\\blackwall_blendable_mesh_decal.mt",
    "base\\fx\\_shaders\\blackwall_blendable_mesh_decal_gradient.mt",
    "base\\materials\\vehicle_mesh_decal.mt",
], MaterialRule(factory=_handler_factory("meshdecal", "MeshDecal", "bip_enablemask"), no_shadows=True))

# Vehicle lights
REGISTRY.register([
    "base\\materials\\vehicle_lights.mt",
], MaterialRule(factory=_handler_factory("vehiclelights", "VehicleLights", "bip")))

# Skin
REGISTRY.register([
    "base\\materials\\skin.mt",
    "base\\materials\\skin_blendable.mt",
    "base\\materials\\skin_morph.mt",
    "base\\fx\\_shaders\\blackwall_blendable_skin.mt",
], MaterialRule(factory=_handler_factory("skin", "Skin", "bip")))

# Metal base
REGISTRY.register([
    "engine\\materials\\metal_base.remt",
    "engine\\materials\\metal_base_blendable.mt",
    "engine\\materials\\metal_base_proxy.mt",
    "base\\materials\\metal_base_parallax.mt",
    "base\\materials\\metal_base_gradientmap_recolor.mt",
    "base\\fx\\_shaders\\blackwall_blendable_metal_base.mt",
    "base\\materials\\metal_base_det.mt",
    "base\\materials\\lights_interactive.mt",
], MaterialRule(factory=_handler_factory("metalbase", "MetalBase", "bip_enablemask")))

# Metal base UI
REGISTRY.register([
    "base\\materials\\metal_base_ui.mt",
], MaterialRule(
    factory=_handler_factory("metalbaseui", "MetalBaseUI", "bip"),
    preserve_render_method=True,
))

# PBR layer
REGISTRY.register([
    "base\\materials\\pbr_layer.remt",
], MaterialRule(factory=_handler_factory("pbr_layer", "pbr_layer", "bip")))

# Hair
REGISTRY.register([
    "base\\materials\\hair.mt",
    "base\\materials\\hair_blendable.mt",
    "base\\fx\\_shaders\\blackwall_blendable_hair.mt",
], MaterialRule(factory=_handler_factory("hair", "Hair", "bip")))

# Eye
REGISTRY.register([
    "base\\materials\\eye.mt",
    "base\\materials\\eye_blendable.mt",
    "base\\fx\\_shaders\\blackwall_blendable_eye.mt",
    "base\\materials\\eye_gradient.mt",
    "base\\materials\\eye_gradient_blendable.mt",
    "base\\fx\\_shaders\\blackwall_blendable_eye_gradient.mt",
], MaterialRule(factory=_handler_factory("eye", "Eye", "bip")))

# Eye shadow
REGISTRY.register([
    "base\\materials\\eye_shadow.mt",
    "base\\materials\\eye_shadow_blendable.mt",
    "base\\fx\\_shaders\\blackwall_blendable_eye_wet.mt",
], MaterialRule(factory=_handler_factory("eyeshadow", "EyeShadow", "bip")))

# Mesh decal emissive
REGISTRY.register([
    "base\\materials\\mesh_decal_emissive.mt",
    "base\\materials\\mesh_decal_emissive_subsurface.mt",
], MaterialRule(factory=_handler_factory("meshdecalemissive", "MeshDecalEmissive", "bip"), no_shadows=True))

# Glass
REGISTRY.register([
    "base\\materials\\glass.mt",
    "base\\materials\\vehicle_glass.mt",
    "base\\materials\\glass_blendable.mt",
    "base\\materials\\vehicle_glass_blendable.mt",
    "base\\fx\\_shaders\\blackwall_blendable_glass.mt",
], MaterialRule(factory=_handler_factory("glass", "Glass", "bip")))

REGISTRY.register([
    "base\\materials\\glass_deferred.mt",
], MaterialRule(factory=_handler_factory("glassdeferred", "GlassDeferred", "bip")))

REGISTRY.register([
    "base\\materials\\glass_onesided.mt",
    "base\\materials\\vehicle_glass_onesided.mt",
], MaterialRule(factory=_handler_factory("glass", "Glass", "bip")))

# Signages
REGISTRY.register([
    "base\\fx\\shaders\\signages.mt",
], MaterialRule(factory=_handler_factory("signages", "Signages", "bip")))

# Mesh decal parallax
REGISTRY.register([
    "base\\materials\\mesh_decal_parallax.mt",
    "base\\materials\\vehicle_mesh_decal_parallax.mt",
], MaterialRule(factory=_handler_factory("meshdecalparallax", "MeshDecalParallax", "bip"), no_shadows=True))

# Parallax screen
REGISTRY.register([
    "base\\fx\\shaders\\parallaxscreen.mt",
], MaterialRule(factory=_handler_factory("parallaxscreen", "ParallaxScreen", "bip")))

REGISTRY.register([
    "base\\fx\\shaders\\parallaxscreen_transparent_ui.mt",
    "base\\fx\\shaders\\parallaxscreen_transparent.mt",
], MaterialRule(factory=_handler_factory("parallaxscreentransparent", "ParallaxScreenTransparent", "bip")))

# Speedtree
REGISTRY.register([
    "base\\materials\\speedtree_3d_v8_twosided.mt",
    "base\\materials\\speedtree_3d_v8_onesided.mt",
    "base\\materials\\speedtree_3d_v8_seams.mt",
    "base\\materials\\ver_skinned_mov.mt",
], MaterialRule(factory=_handler_factory("speedtree", "SpeedTree", "bip")))

# Television Ad
REGISTRY.register([
    "base\\fx\\shaders\\television_ad.mt",
], MaterialRule(factory=_handler_factory("televisionad", "TelevisionAd", "bip")))

# Window parallax interior
REGISTRY.register([
    "base\\materials\\window_parallax_interior_proxy.mt",
    "base\\materials\\window_parallax_interior.mt",
], MaterialRule(factory=_handler_factory("window_parallax_interior_proxy", "windowParallaxIntProx", "bip")))

# Hologram
REGISTRY.register([
    "base\\fx\\shaders\\hologram.mt",
], MaterialRule(factory=_handler_factory("hologram", "Hologram", "bip")))

# Invisible
REGISTRY.register([
    "base\\fx\\_shaders\\invisible.mt",
], MaterialRule(factory=_handler_factory("invisible", "Invisible", "bip"), no_shadows=True))


# Global water patch
REGISTRY.register([
    "engine\\materials\\global_water_patch.mt",
], MaterialRule(
    factory=_handler_factory("global_water_patch", "GlobalWaterPatch", "bipm"),
    no_shadows=True,
    preserve_render_method=True,
    mesh_path_sensitive=True,
))


# Device diode
REGISTRY.register([
    "base\\fx\\shaders\\device_diode.mt",
    "base\\fx\\shaders\\device_diode_multi_state.mt",
], MaterialRule(
    factory=_handler_factory("device_diode", "DeviceDiode", "bip"),
    preserve_render_method=True,
))


# Light gradients
REGISTRY.register([
    "base\\fx\\shaders\\light_gradients.mt",
], MaterialRule(
    factory=_handler_factory("lightgradients", "LightGradients", "bip"),
    no_shadows=True,
    preserve_render_method=True,
))


# Neon tubes
REGISTRY.register([
    "base\\fx\\shaders\\neon_tubes.mt",
], MaterialRule(
    factory=_handler_factory("neontubes", "NeonTubes", "bip"),
))

# Neon parallax
REGISTRY.register([
    "base\\materials\\neon_parallax.mt",
], MaterialRule(
    factory=_handler_factory("neonparallax", "NeonParallax", "bip"),
    preserve_render_method=True,
))

# Decal registry (baseMaterial path flow)
DECAL_REGISTRY = MaterialRegistry()

DECAL_REGISTRY.register([
    "base\\materials\\decal.remt",
    "base\\materials\\decal_roughness.mt",
    "base\\materials\\decal_puddle.mt",
    "base\\materials\\decal_normal_roughness_metalness.mt",
    "base\\materials\\decal_normal_roughness.mt",
    "base\\surfaces\\textures\\decals\\road_markings\\materials\\road_markings_white.mi",
    "base\\materials\\decal_parallax.mt",
    "base\\materials\\decal_normal.remt",
    "base\\materials\\decal_normal_roughness_metalness_2.mt",
    "base\\materials\\decal_terrain_projected.mt",
], MaterialRule(factory=_handler_factory("decal", "Decal", "bi")))

DECAL_REGISTRY.register([
    "base\\materials\\decal_gradientmap_recolor.mt",
], MaterialRule(factory=_handler_factory("decal_gradientmap_recolor", "DecalGradientmapRecolor", "bip")))

DECAL_REGISTRY.register([
    "base\\materials\\decal_gradientmap_recolor_emissive.mt",
], MaterialRule(factory=_handler_factory("decal_gradientmap_recolor_emissive", "DecalGradientmapRecolorEmissive", "bip")))


=======

REGISTRY.register(
    [
        "engine\\materials\\multilayered.mt",
        "base\\materials\\silverhand_overlay_blendable.mt",
        "base\\materials\\silverhand_overlay.mt",
        "base\\materials\\multilayered_terrain.mt",
        "base\\materials\\cloth_tarps.mt",
        "base\\fx\\_shaders\\blackwall_blendable.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("multilayered", "Multilayered", "bip"),
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\vehicle_destr_blendshape.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "vehicle_destr_blendshape", "VehicleDestrBlendshape", "bip"
        ),
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\multilayered_clear_coat.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "multilayered_clear_coat", "MultilayeredClearCoat", "bip"
        )
    ),
)

REGISTRY.register(
    [
        "base\\fx\\_shaders\\multilayer_blackbody_inject.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "multilayer_blackbody_inject", "MultilayerBlackbodyInject", "bip"
        ),
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)


REGISTRY.register(
    [
        "base\\materials\\mesh_decal.mt",
        "base\\materials\\mesh_decal_blendable.mt",
        "base\\materials\\mesh_decal_particles.mt",
        "base\\materials\\mesh_decal_wet_character.mt",
        "base\\materials\\mesh_decal_revealed.mt",
        "base\\materials\\mesh_decal_double_diffuse.mt",
        "base\\materials\\mesh_decal_morph.mt",
        "base\\materials\\mesh_decal_gradientmap_recolor.mt",
        "base\\materials\\mesh_decal_gradientmap_recolor_2.mt",
        "base\\materials\\mesh_decal_gradientmap_recolor_emissive.mt",
        "base\\materials\\mesh_decal_gradientmap_recolor_blendable.mt",
        "base\\materials\\mesh_decal_multitinted.mt",
        "base\\materials\\mesh_decal_emissive.mt",
        "base\\materials\\mesh_decal_emissive_subsurface.mt",
        "base\\materials\\mesh_decal_parallax.mt",
        "base\\materials\\vehicle_mesh_decal.mt",
        "base\\materials\\vehicle_mesh_decal_parallax.mt",
        "base\\fx\\_shaders\\blackwall_blendable_mesh_decal.mt",
        "base\\fx\\_shaders\\blackwall_blendable_mesh_decal_gradient.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_nodes", "MeshDecal", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\decal_forward.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_nodes", "ProjectedDecal", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\trail_decal.mt",
        "base\\materials\\trail_decal_normal.mt",
        "base\\materials\\trail_decal_normal_color.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_source_materials", "TrailDecal", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\animated_decal.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_source_materials", "AnimatedDecal", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\blood_puddle_decal.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_source_materials", "BloodPuddleDecal", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\simple_emissive_decals.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_source_materials", "SimpleEmissiveDecal", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\materials\\vehicle_lights.mt",
    ],
    MaterialRule(factory=HandlerFactory("vehiclelights", "VehicleLights", "bip")),
)


REGISTRY.register(
    [
        "base\\materials\\skin.mt",
        "base\\materials\\skin_blendable.mt",
        "base\\materials\\skin_morph.mt",
        "base\\fx\\_shaders\\blackwall_blendable_skin.mt",
    ],
    MaterialRule(factory=HandlerFactory("skin", "Skin", "bip")),
)


REGISTRY.register(
    [
        "engine\\materials\\metal_base.remt",
    ],
    MaterialRule(factory=HandlerFactory("metalbase", "MetalBase", "bip_enablemask")),
)

REGISTRY.register(
    [
        "base\\materials\\lights_interactive.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "lights_interactive", "LightsInteractive", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "engine\\materials\\metal_base_animated_uv.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseAnimatedUV", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_dithered.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseDithered", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "engine\\materials\\metal_base_blendable.mt",
        "base\\fx\\_shaders\\blackwall_blendable_metal_base.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_blendable", "MetalBaseBlendable", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "engine\\materials\\metal_base_fence.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseFence", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "engine\\materials\\metal_base_packed.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBasePacked", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_det.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseDetail", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_det_vc.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseDetailVC", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_det_dithered.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseDetailDithered", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\metal_base_alpha_animated.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase", "MetalBaseAlphaAnimated", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "engine\\materials\\metal_base_garment.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_garment", "MetalBaseGarment", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\cloth_mov.mt",
    ],
    MaterialRule(factory=HandlerFactory("cloth_mov", "ClothMOV", "bip_enablemask")),
)

REGISTRY.register(
    [
        "base\\materials\\cloth_mov_multilayered.mt",
    ],
    MaterialRule(factory=HandlerFactory("cloth_mov", "ClothMOVMultilayered", "bip")),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_parallax.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_parallax", "MetalBaseParallax", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_bink.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase_bink", "MetalBaseBink", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_trafficlight_proxy.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_trafficlight_proxy",
            "MetalBaseTrafficLightProxy",
            "bip_enablemask",
        )
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\metal_base_atlas_animation.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_atlas_animation", "MetalBaseAtlasAnimation", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\metal_base_glitter.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_glitter", "MetalBaseGlitter", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_gradientmap_recolor.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_gradientmap_recolor", "MetalBaseGradient", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "engine\\materials\\metal_base_proxy.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbase_proxy", "MetalBaseProxy", "bip_enablemask")
    ),
)

REGISTRY.register(
    [
        "base\\fx\\_shaders\\metal_base_scrolling.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_scrolling", "MetalBaseScrolling", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_vertexcolored.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_vertexcolored", "MetalBaseVertexColored", "bip_enablemask"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_ui_q303.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "metalbase_ui_q303", "MetalBaseUIQ303", "bip_enablemask"
        ),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\metal_base_blackbody.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metal_base_blackbody", "MetalBaseBlackbody", "bip"),
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\_shaders\\mesh_decal__blackbody.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("mesh_decal_blackbody", "MeshDecalBlackbody", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\metal_base_ui.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("metalbaseui", "MetalBaseUI", "bip"),
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\materials\\weapon.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("weapon", "Weapon", "bip"),
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\terrain_simple.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("terrain_simple", "TerrainSimple", "bip"),
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\fur_shell.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("fur_shell", "FurShell", "bip"),
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\transparent_liquid.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("transparent_liquid", "TransparentLiquid", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\rain.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("rain", "Rain", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\pbr_layer.remt",
    ],
    MaterialRule(factory=HandlerFactory("pbr_layer", "pbr_layer", "bip")),
)


REGISTRY.register(
    [
        "base\\materials\\hair.mt",
        "base\\materials\\hair_blendable.mt",
        "base\\fx\\_shaders\\blackwall_blendable_hair.mt",
    ],
    MaterialRule(factory=HandlerFactory("hair", "Hair", "bip")),
)


REGISTRY.register(
    [
        "base\\materials\\eye.mt",
        "base\\materials\\eye_blendable.mt",
        "base\\fx\\_shaders\\blackwall_blendable_eye.mt",
        "base\\materials\\eye_gradient.mt",
        "base\\materials\\eye_gradient_blendable.mt",
        "base\\fx\\_shaders\\blackwall_blendable_eye_gradient.mt",
    ],
    MaterialRule(factory=HandlerFactory("eye", "Eye", "bip")),
)


REGISTRY.register(
    [
        "base\\materials\\eye_shadow.mt",
        "base\\materials\\eye_shadow_blendable.mt",
        "base\\fx\\_shaders\\blackwall_blendable_eye_wet.mt",
    ],
    MaterialRule(factory=HandlerFactory("eyeshadow", "EyeShadow", "bip")),
)


REGISTRY.register(
    [
        "base\\materials\\glass.mt",
        "base\\materials\\vehicle_glass.mt",
        "base\\materials\\glass_blendable.mt",
        "base\\materials\\vehicle_glass_blendable.mt",
        "base\\fx\\_shaders\\blackwall_blendable_glass.mt",
        "base\\materials\\vehicle_glass_flat_twosided.mt",
        "base\\materials\\frosted_glass.mt",
        "base\\materials\\mirror_glass.mt",
    ],
    MaterialRule(factory=HandlerFactory("glass", "Glass", "bip")),
)

REGISTRY.register(
    [
        "base\\materials\\glass_scope.mt",
    ],
    MaterialRule(factory=HandlerFactory("glass_scope", "GlassScope", "bip")),
)

REGISTRY.register(
    [
        "base\\materials\\glass_deferred.mt",
    ],
    MaterialRule(factory=HandlerFactory("glassdeferred", "GlassDeferred", "bip")),
)

REGISTRY.register(
    [
        "base\\materials\\glass_onesided.mt",
        "base\\materials\\vehicle_glass_onesided.mt",
    ],
    MaterialRule(factory=HandlerFactory("glass", "Glass", "bip")),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\signages.mt",
    ],
    MaterialRule(factory=HandlerFactory("signages", "Signages", "bip_enablemask")),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\parallaxscreen.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("parallaxscreen", "ParallaxScreen", "bip"),
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\parallaxscreen_transparent.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "parallaxscreentransparent", "ParallaxScreenTransparent", "bip"
        ),
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\parallaxscreen_transparent_ui.mt",
        "base\\fx\\shaders\\parallaxscreen_transparent_ui_txaa.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "parallaxscreen_transparent_ui", "ParallaxScreenTransparentUI", "bip"
        ),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\speedtree_3d_v8_twosided.mt",
        "base\\materials\\speedtree_3d_v8_onesided.mt",
        "base\\materials\\speedtree_3d_v8_seams.mt",
        "base\\materials\\ver_skinned_mov.mt",
    ],
    MaterialRule(factory=HandlerFactory("speedtree", "SpeedTree", "bip")),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\television_ad.mt",
    ],
    MaterialRule(factory=HandlerFactory("televisionad", "TelevisionAd", "bip")),
)


REGISTRY.register(
    [
        "base\\materials\\window_parallax_interior.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "window_parallax_interior", "WindowParallaxInterior", "bip"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\window_parallax_interior_proxy.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "window_parallax_interior_proxy", "WindowParallaxInteriorProxy", "bip"
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\window_parallax_interior_proxy_buffer.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "window_parallax_interior_proxy_buffer",
            "WindowParallaxInteriorProxyBuffer",
            "bip_enablemask",
        )
    ),
)

REGISTRY.register(
    [
        "base\\materials\\mikoshi_parallax.mt",
    ],
    MaterialRule(factory=HandlerFactory("mikoshi_parallax", "MikoshiParallax", "bip")),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\parallax_bink.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("parallax_bink", "BinkParallax", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\hologram.mt",
    ],
    MaterialRule(factory=HandlerFactory("hologram", "Hologram", "bip")),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\hud_markers_notxaa.mt",
        "base\\fx\\shaders\\hud_markers_transparent.mt",
        "base\\fx\\shaders\\hud_markers_vision.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("hud_markers", "HUDMarkers", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\hud_ui_dot.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("hud_ui_dot", "HUDUIDot", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\hud_vision_pass.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("hud_vision_pass", "HUDVisionPass", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\cloak.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("cloak", "Cloak", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\glass_window_rain.mt",
        "base\\fx\\shaders\\glass_window_rain.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("glass_window_rain", "GlassWindowRain", "bip"),
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\hologram_two_sided.mt",
        "base\\fx\\shaders\\hologram_txaa.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("hologram", "Hologram", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\_shaders\\hologram_v2.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("hologram_v2", "HologramV2", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\shaders\\water_plane.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("water_plane", "WaterPlane", "bip"),
        no_shadows=True,
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\circuit_wires.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("circuit_wires", "CircuitWires", "bip"),
        semantic_cache_identity=True,
    ),
)


REGISTRY.register(
    [
        "base\\fx\\_shaders\\invisible.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("invisible", "Invisible", "bip"), no_shadows=True
    ),
)


REGISTRY.register(
    [
        "engine\\materials\\global_water_patch.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("global_water_patch", "GlobalWaterPatch", "bipm"),
        no_shadows=True,
        preserve_render_method=True,
        mesh_path_sensitive=True,
    ),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\device_diode.mt",
        "base\\fx\\shaders\\device_diode_multi_state.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("device_diode", "DeviceDiode", "bip"),
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\light_gradients.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("lightgradients", "LightGradients", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\materials\\emissive_control.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("emissive_control", "EmissiveControl", "bip"),
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\emissive_basic_transparent.mt",
    ],
    MaterialRule(
        factory=HandlerFactory(
            "emissive_basic_transparent",
            "EmissiveBasicTransparent",
            "bip",
        ),
        no_shadows=True,
        preserve_render_method=True,
    ),
)


REGISTRY.register(
    [
        "base\\fx\\shaders\\neon_tubes.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("neontubes", "NeonTubes", "bip"),
    ),
)


REGISTRY.register(
    [
        "base\\materials\\neon_parallax.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("neonparallax", "NeonParallax", "bip"),
        preserve_render_method=True,
        semantic_cache_identity=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\_shaders\\crystal_dome.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("crystal_dome", "CrystalDome", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\fx\\_shaders\\crystal_dome_opaque.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("crystal_dome_opaque", "CrystalDomeOpaque", "bip"),
    ),
)


REGISTRY.register(
    [
        "base\\materials\\fillable_fluid.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("fillable_fluid", "FillableFluid", "bip"),
        preserve_render_method=True,
    ),
)

REGISTRY.register(
    [
        "base\\materials\\fillable_fluid_vertex.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("fillable_fluid_vertex", "FillableFluidVertex", "bip"),
        no_shadows=True,
        preserve_render_method=True,
    ),
)


DECAL_REGISTRY = MaterialRegistry()

DECAL_REGISTRY.register(
    [
        "base\\materials\\decal.remt",
        "base\\materials\\decal_roughness.mt",
        "base\\materials\\decal_roughness_only.mt",
        "base\\materials\\decal_puddle.mt",
        "base\\materials\\decal_normal_roughness_metalness.mt",
        "base\\materials\\decal_normal_roughness.mt",
        "base\\surfaces\\textures\\decals\\road_markings\\materials\\road_markings_white.mi",
        "base\\materials\\decal_parallax.mt",
        "base\\materials\\decal_normal.remt",
        "base\\materials\\decal_normal_roughness_metalness_2.mt",
        "base\\materials\\decal_terrain_projected.mt",
        "base\\materials\\decal_gradientmap_recolor.mt",
        "base\\materials\\decal_gradientmap_recolor_emissive.mt",
        "base\\materials\\decal_emissive_color.mt",
        "base\\materials\\decal_emissive_only.mt",
        "base\\materials\\decal_tintable.mt",
        "base\\materials\\decal_braindance_thermal.mt",
        "base\\materials\\decal_caustics.mt",
        "base\\materials\\decal_glitch.mt",
        "base\\materials\\decal_glitch_emissive.mt",
    ],
    MaterialRule(
        factory=HandlerFactory("decal_nodes", "ProjectedDecal", "bip"),
        preserve_render_method=True,
    ),
)
>>>>>>> Stashed changes
