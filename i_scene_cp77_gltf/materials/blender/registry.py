from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module


@lru_cache(maxsize=512)
def _norm(path: str) -> str:
    return path.replace("/", "\\").casefold() if path else ""


@lru_cache(maxsize=None)
def _handler_class(module_name: str, class_name: str):
    module = import_module(f"...material_types.{module_name}", __package__)
    return getattr(module, class_name)


@dataclass(frozen=True, slots=True)
class HandlerFactory:
    module_name: str
    class_name: str
    mode: str

    def __call__(self, builder, raw_material):
        handler = _handler_class(self.module_name, self.class_name)
        if self.mode == "bip":
            return handler(builder.BasePath, builder.image_format, builder.ProjPath)
        if self.mode == "bipm":
            return handler(builder.BasePath, builder.image_format, builder.ProjPath, builder.MeshPath)
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


class MaterialRegistry:
    def __init__(self) -> None:
        self.by_template = {}

    def register(self, templates, rule: MaterialRule) -> None:
        for template in templates:
            key = _norm(template)
            existing = self.by_template.get(key)
            if existing is not None and existing != rule:
                raise ValueError(f"Conflicting material handler for {template}")
            self.by_template[key] = rule

    def resolve(self, template: str):
        return self.by_template.get(_norm(template))


def _handler_factory(module_name, class_name, mode):
    return HandlerFactory(module_name, class_name, mode)


REGISTRY = MaterialRegistry()

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


