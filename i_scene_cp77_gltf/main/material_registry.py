import os
from dataclasses import dataclass
from typing import Callable, Dict, Iterable

# Handlers
from ..material_types.multilayered import Multilayered
from ..material_types.multilayeredclearcoat import MultilayeredClearCoat
from ..material_types.vehicledestrblendshape import VehicleDestrBlendshape
from ..material_types.skin import Skin
from ..material_types.meshdecal import MeshDecal
from ..material_types.meshdecaldoublediffuse import MeshDecalDoubleDiffuse
from ..material_types.vehiclemeshdecal import VehicleMeshDecal
from ..material_types.vehiclelights import VehicleLights
from ..material_types.metalbase import MetalBase
from ..material_types.metalbasedet import MetalBaseDet
from ..material_types.hair import Hair
from ..material_types.meshdecalgradientmaprecolor import MeshDecalGradientMapReColor
from ..material_types.eye import Eye
from ..material_types.eyegradient import EyeGradient
from ..material_types.eyeshadow import EyeShadow
from ..material_types.meshdecalemissive import MeshDecalEmissive
from ..material_types.glass import Glass
from ..material_types.glassdeferred import GlassDeferred
from ..material_types.signages import Signages
from ..material_types.meshdecalparallax import MeshDecalParallax
from ..material_types.parallaxscreen import ParallaxScreen
from ..material_types.parallaxscreentransparent import ParallaxScreenTransparent
from ..material_types.speedtree import SpeedTree
from ..material_types.decal import Decal
from ..material_types.decal_gradientmap_recolor import DecalGradientmapRecolor
from ..material_types.televisionad import TelevisionAd
from ..material_types.window_parallax_interior_proxy import windowParallaxIntProx
from ..material_types.hologram import Hologram
from ..material_types.pbr_layer import pbr_layer


def _norm(path: str) -> str:
    return path.replace('/', '\\') if path else path


@dataclass(frozen=True)
class MaterialRule:
    factory: Callable[[object, dict], object]
    no_shadows: bool = False


class MaterialRegistry:
    def __init__(self) -> None:
        self.by_template: Dict[str, MaterialRule] = {}

    def register(self, templates: Iterable[str], rule: MaterialRule) -> None:
        for t in templates:
            self.by_template[_norm(t)] = rule

    def resolve(self, template: str) -> MaterialRule | None:
        return self.by_template.get(_norm(template))


REGISTRY = MaterialRegistry()

def _factory_bip(cls):
    return lambda b, raw: cls(b.BasePath, b.image_format, b.ProjPath)

def _factory_bi(cls):
    return lambda b, raw: cls(b.BasePath, b.image_format)

def _factory_bip_enablemask(cls):
    return lambda b, raw: cls(b.BasePath, b.image_format, b.ProjPath, raw.get('EnableMask', False))


# Multilayered group
REGISTRY.register([
    "engine\\materials\\multilayered.mt",
    "base\\materials\\silverhand_overlay_blendable.mt",
    "base\\materials\\silverhand_overlay.mt",
    "base\\materials\\vehicle_destr_blendshape.mt",
    "base\\materials\\multilayered_clear_coat.mt",
    "base\\materials\\multilayered_terrain.mt",
], MaterialRule(factory=_factory_bip(Multilayered)))

# Mesh decals
REGISTRY.register([
    "base\\materials\\mesh_decal.mt",
    "base\\materials\\mesh_decal_blendable.mt",
    "base\\materials\\mesh_decal_wet_character.mt",
], MaterialRule(factory=_factory_bip_enablemask(MeshDecal), no_shadows=True))

REGISTRY.register([
    "base\\materials\\mesh_decal_double_diffuse.mt",
], MaterialRule(factory=_factory_bi(MeshDecalDoubleDiffuse), no_shadows=True))

REGISTRY.register([
    "base\\materials\\vehicle_mesh_decal.mt",
], MaterialRule(factory=_factory_bip_enablemask(VehicleMeshDecal), no_shadows=True))

# Vehicle lights
REGISTRY.register([
    "base\\materials\\vehicle_lights.mt",
], MaterialRule(factory=_factory_bip(VehicleLights)))

# Skin
REGISTRY.register([
    "base\\materials\\skin.mt",
    "base\\materials\\skin_blendable.mt",
], MaterialRule(factory=_factory_bip(Skin)))

# Metal base
REGISTRY.register([
    "engine\\materials\\metal_base.remt",
    "engine\\materials\\metal_base_blendable.mt",
    "engine\\materials\\metal_base_proxy.mt",
    "base\\materials\\metal_base_parallax.mt",
    "base\\materials\\metal_base_gradientmap_recolor.mt",
], MaterialRule(factory=_factory_bip_enablemask(MetalBase)))

REGISTRY.register([
    "base\\materials\\metal_base_det.mt",
    "base\\materials\\lights_interactive.mt",
], MaterialRule(factory=_factory_bip(MetalBaseDet)))

# PBR layer
REGISTRY.register([
    "base\\materials\\pbr_layer.remt",
], MaterialRule(factory=_factory_bip(pbr_layer)))

# Hair
REGISTRY.register([
    "base\\materials\\hair.mt",
    "base\\materials\\hair_blendable.mt",
], MaterialRule(factory=_factory_bip(Hair)))

# Mesh decal gradient map recolor
REGISTRY.register([
    "base\\materials\\mesh_decal_gradientmap_recolor.mt",
    "base\\materials\\mesh_decal_gradientmap_recolor_blendable.mt",
], MaterialRule(factory=_factory_bip(MeshDecalGradientMapReColor), no_shadows=True))

# Eye
REGISTRY.register([
    "base\\materials\\eye.mt",
    "base\\materials\\eye_blendable.mt",
], MaterialRule(factory=_factory_bip(Eye)))

# Eye gradient
REGISTRY.register([
    "base\\materials\\eye_gradient.mt",
    "base\\materials\\eye_gradient_blendable.mt",
], MaterialRule(factory=_factory_bip(EyeGradient)))

# Eye shadow
REGISTRY.register([
    "base\\materials\\eye_shadow.mt",
    "base\\materials\\eye_shadow_blendable.mt",
], MaterialRule(factory=_factory_bip(EyeShadow)))

# Mesh decal emissive
REGISTRY.register([
    "base\\materials\\mesh_decal_emissive.mt",
], MaterialRule(factory=_factory_bip(MeshDecalEmissive), no_shadows=True))

# Glass
REGISTRY.register([
    "base\\materials\\glass.mt",
    "base\\materials\\vehicle_glass.mt",
    "base\\materials\\glass_blendable.mt",
    "base\\materials\\vehicle_glass_blendable.mt",
], MaterialRule(factory=_factory_bip(Glass)))

REGISTRY.register([
    "base\\materials\\glass_deferred.mt",
], MaterialRule(factory=_factory_bip(GlassDeferred)))

REGISTRY.register([
    "base\\materials\\glass_onesided.mt",
    "base\\materials\\vehicle_glass_onesided.mt",
], MaterialRule(factory=_factory_bip(Glass)))

# Signages
REGISTRY.register([
    "base\\fx\\shaders\\signages.mt",
], MaterialRule(factory=_factory_bip(Signages)))

# Mesh decal parallax
REGISTRY.register([
    "base\\materials\\mesh_decal_parallax.mt",
    "base\\materials\\vehicle_mesh_decal_parallax.mt",
], MaterialRule(factory=_factory_bip(MeshDecalParallax), no_shadows=True))

# Parallax screen
REGISTRY.register([
    "base\\fx\\shaders\\parallaxscreen.mt",
], MaterialRule(factory=_factory_bip(ParallaxScreen)))

REGISTRY.register([
    "base\\fx\\shaders\\parallaxscreen_transparent.mt",
], MaterialRule(factory=_factory_bip(ParallaxScreenTransparent)))

# Speedtree
REGISTRY.register([
    "base\\materials\\speedtree_3d_v8_twosided.mt",
    "base\\materials\\speedtree_3d_v8_onesided.mt",
    "base\\materials\\speedtree_3d_v8_seams.mt",
], MaterialRule(factory=_factory_bip(SpeedTree)))

# Television Ad
REGISTRY.register([
    "base\\fx\\shaders\\television_ad.mt",
], MaterialRule(factory=_factory_bip(TelevisionAd)))

# Window parallax interior
REGISTRY.register([
    "base\\materials\\window_parallax_interior_proxy.mt",
    "base\\materials\\window_parallax_interior.mt",
], MaterialRule(factory=_factory_bip(windowParallaxIntProx)))

# Hologram
REGISTRY.register([
    "base\\fx\\shaders\\hologram.mt",
], MaterialRule(factory=_factory_bip(Hologram)))


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
], MaterialRule(factory=_factory_bi(Decal)))

DECAL_REGISTRY.register([
    "base\\materials\\decal_gradientmap_recolor.mt",
], MaterialRule(factory=_factory_bip(DecalGradientmapRecolor)))


