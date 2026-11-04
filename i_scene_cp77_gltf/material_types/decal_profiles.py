from dataclasses import dataclass, field

from ..assetio.paths import backslash_depot_key
from .decal_contracts import contract_defaults


@dataclass(frozen=True, slots=True)
class DecalProfile:
    name: str
    family: str
    features: frozenset = field(default_factory=frozenset)
    fidelity: str = "compiled_contract"
    cull_mode: str = "FRONT"
    winding: str = "CW"
    depth_bias: bool = False
    defaults: dict = field(default_factory=dict)
    parameters: frozenset = field(default_factory=frozenset)


PROJECTED_BASE_PARAMETERS = frozenset(
    {
        "DiffuseTexture",
        "DiffuseTextureAsMaskTexture",
        "MaskTexture",
        "DiffuseColor",
        "DiffuseAlpha",
        "NormalTexture",
        "RoughnessTexture",
        "MetalnessTexture",
        "AlphaMaskContrast",
        "RoughnessScale",
        "RoughnessBias",
        "MetalnessScale",
        "MetalnessBias",
        "RoughnessMetalnessAlpha",
        "SubUVx",
        "SubUVy",
        "Frame",
    }
)

MESH_BASE_PARAMETERS = frozenset(
    {
        "VertexOffsetFactor",
        "DiffuseTexture",
        "MaskTexture",
        "DiffuseColor",
        "DiffuseAlpha",
        "UVOffsetX",
        "UVOffsetY",
        "UVRotation",
        "UVScaleX",
        "UVScaleY",
        "SecondaryMask",
        "SecondaryMaskUVScale",
        "SecondaryMaskInfluence",
        "NormalTexture",
        "NormalAlpha",
        "NormalAlphaTex",
        "UseNormalAlphaTex",
        "NormalsBlendingMode",
        "NormalsBlendingModeAlpha",
        "RoughnessTexture",
        "RoughnessScale",
        "RoughnessBias",
        "MetalnessTexture",
        "MetalnessScale",
        "MetalnessBias",
        "AlphaMaskContrast",
        "RoughnessMetalnessAlpha",
        "AnimationSpeed",
        "AnimationFramesWidth",
        "AnimationFramesHeight",
        "DepthThreshold",
    }
)

PROJECTED_DEFAULTS = {
    "DiffuseTexture": "engine\\textures\\small_white.xbm",
    "NormalTexture": "engine\\textures\\small_flat_normal.xbm",
    "RoughnessTexture": "engine\\textures\\editor\\grey.xbm",
    "MetalnessTexture": "engine\\textures\\editor\\black.xbm",
    "DiffuseTextureAsMaskTexture": 0.0,
    "DiffuseColor": (1.0, 1.0, 1.0, 1.0),
    "DiffuseAlpha": 1.0,
    "AlphaMaskContrast": 0.0,
    "RoughnessScale": 1.0,
    "RoughnessBias": 0.0,
    "MetalnessScale": 1.0,
    "MetalnessBias": 0.0,
    "RoughnessMetalnessAlpha": 1.0,
    "SubUVx": 1.0,
    "SubUVy": 1.0,
    "Frame": 0.0,
}

MESH_DEFAULTS = {
    "VertexOffsetFactor": 0.0,
    "DiffuseTexture": "engine\\textures\\editor\\grey.xbm",
    "DiffuseColor": (1.0, 1.0, 1.0, 1.0),
    "DiffuseAlpha": 0.0,
    "UVOffsetX": 0.0,
    "UVOffsetY": 0.0,
    "UVRotation": 0.0,
    "UVScaleX": 1.0,
    "UVScaleY": 1.0,
    "SecondaryMaskUVScale": 1.0,
    "SecondaryMaskInfluence": 0.0,
    "SecondaryMask": "engine\\textures\\editor\\white.xbm",
    "NormalTexture": "engine\\textures\\editor\\normal.xbm",
    "NormalAlpha": 0.0,
    "UseNormalAlphaTex": 0.0,
    "NormalAlphaTex": "engine\\textures\\editor\\white.xbm",
    "NormalsBlendingMode": 0.0,
    "NormalsBlendingModeAlpha": "engine\\textures\\editor\\white.xbm",
    "RoughnessTexture": "engine\\textures\\editor\\white.xbm",
    "RoughnessScale": 1.0,
    "RoughnessBias": 0.0,
    "MetalnessScale": 1.0,
    "MetalnessBias": 0.0,
    "MetalnessTexture": "engine\\textures\\editor\\black.xbm",
    "AlphaMaskContrast": 0.0,
    "RoughnessMetalnessAlpha": 0.0,
    "AnimationSpeed": 1.0,
    "AnimationFramesWidth": 1.0,
    "AnimationFramesHeight": 1.0,
    "DepthThreshold": 0.5,
}

VEHICLE_MESH_DEFAULTS = {
    "DiffuseTexture": "engine\\textures\\small_white.xbm",
    "DiffuseColor": (1.0, 1.0, 1.0, 1.0),
    "DiffuseAlpha": 1.0,
    "MaskTexture": "engine\\textures\\small_white.xbm",
    "GradientMap": "engine\\textures\\small_white.xbm",
    "UseGradientMap": 0.0,
    "NormalTexture": "engine\\textures\\small_flat_normal.xbm",
    "NormalAlpha": 1.0,
    "NormalsBlendingMode": 0.0,
    "RoughnessTexture": "engine\\textures\\small_white.xbm",
    "MetalnessTexture": "engine\\textures\\small_white.xbm",
    "RoughnessMetalnessAlpha": 1.0,
    "DepthThreshold": 0.5,
    "DamageInfluence": 1.0,
    "DamageInfluenceDebug": 0.0,
    "DirtMap": "base\\vehicles\\common\\textures\\dust_fine.xbm",
    "DirtOpacity": 0.0,
    "DirtMaskOffsets": (1.5, 1.0, 0.5, 3.0),
}


def _projected(
    name,
    features,
    *,
    exact=False,
    fidelity=None,
    defaults=None,
    parameters=(),
    cull="FRONT",
):
    return DecalProfile(
        name=name,
        family="projected",
        features=frozenset(features),
        fidelity=fidelity or ("source_math" if exact else "compiled_contract"),
        cull_mode=cull,
        defaults={**PROJECTED_DEFAULTS, **(defaults or {})},
        parameters=PROJECTED_BASE_PARAMETERS | frozenset(parameters),
    )


def _mesh(name, features, *, exact=False, fidelity=None, defaults=None, parameters=()):
    return DecalProfile(
        name=name,
        family="mesh",
        features=frozenset(features),
        fidelity=fidelity or ("source_math" if exact else "compiled_contract"),
        cull_mode="FRONT",
        winding="CCW",
        depth_bias=True,
        defaults={**MESH_DEFAULTS, **(defaults or {})},
        parameters=MESH_BASE_PARAMETERS | frozenset(parameters),
    )


PROJECTED_PROFILES = {
    "base\\materials\\decal.remt": _projected(
        "decal", {"diffuse", "roughness_bias"}, exact=True
    ),
    "base\\materials\\decal_normal.remt": _projected(
        "decal_normal", {"diffuse", "normal"}, exact=True
    ),
    "base\\materials\\decal_roughness.mt": _projected(
        "decal_roughness", {"diffuse", "roughness"}
    ),
    "base\\materials\\decal_roughness_only.mt": _projected(
        "decal_roughness_only", {"roughness"}
    ),
    "base\\materials\\decal_normal_roughness.mt": _projected(
        "decal_normal_roughness",
        {"diffuse", "normal", "roughness"},
        defaults={"RoughnessTexture": "engine\\textures\\small_white.xbm"},
    ),
    "base\\materials\\decal_normal_roughness_metalness.mt": _projected(
        "decal_normal_roughness_metalness",
        {"diffuse", "normal", "roughness", "metalness"},
        defaults={
            "RoughnessTexture": "engine\\textures\\small_white.xbm",
            "MetalnessTexture": "engine\\textures\\editor\\white.xbm",
        },
    ),
    "base\\materials\\decal_normal_roughness_metalness_2.mt": _projected(
        "decal_normal_roughness_metalness_2",
        {"diffuse", "normal", "roughness", "metalness", "atlas"},
        defaults={
            "DiffuseColor": (1.0, 1.0, 1.0, 0.0),
            "AtlasSize": (1024.0, 1024.0, 0.0, 0.0),
            "SubRegion": (400.0, 0.0, 80.0, 1024.0),
        },
        parameters={"AtlasSize", "SubRegion"},
    ),
    "base\\materials\\decal_puddle.mt": _projected(
        "decal_puddle",
        {"diffuse", "normal", "roughness"},
        defaults={
            "DiffuseTexture": "base\\surfaces\\textures\\decals\\megabuiding\\puddle\\puddle_d.xbm",
            "RoughnessTexture": "base\\surfaces\\textures\\decals\\megabuiding\\puddle\\puddle_r.xbm",
            "DiffuseColor": (0.0, 0.0, 0.0, 0.0),
            "DiffuseAlpha": 0.0833330005,
        },
    ),
    "base\\materials\\decal_gradientmap_recolor.mt": _projected(
        "decal_gradientmap_recolor",
        {"diffuse", "mask", "gradient", "roughness"},
        defaults={
            "MaskTexture": "engine\\textures\\small_white.xbm",
            "GradientMap": "engine\\textures\\small_white.xbm",
        },
        parameters={"GradientMap"},
    ),
    "base\\materials\\decal_gradientmap_recolor_emissive.mt": _projected(
        "decal_gradientmap_recolor_emissive",
        {"diffuse", "mask", "gradient", "emissive_gradient", "normal"},
        defaults={
            "MaskTexture": "engine\\textures\\small_white.xbm",
            "GradientMap": "engine\\textures\\small_white.xbm",
            "EmissiveGradientMap": "engine\\textures\\editor\\black.xbm",
            "EmissiveEV": 0.0,
            "EmissiveAlphaThreshold": 0.005,
        },
        parameters={
            "GradientMap",
            "EmissiveGradientMap",
            "EmissiveEV",
            "EmissiveAlphaThreshold",
        },
    ),
    "base\\materials\\decal_emissive_color.mt": _projected(
        "decal_emissive_color",
        {"emissive_color"},
        exact=True,
        defaults={
            "Emissive": "engine\\textures\\editor\\black.xbm",
            "EmissiveColor": (254 / 255, 254 / 255, 254 / 255, 254 / 255),
            "EmissiveEV": 0.0,
            "EmissiveAlphaThreshold": 0.005,
        },
        parameters={
            "Emissive",
            "EmissiveColor",
            "EmissiveEV",
            "EmissiveAlphaThreshold",
        },
    ),
    "base\\materials\\decal_emissive_only.mt": _projected(
        "decal_emissive_only",
        {"emissive_only"},
        exact=True,
        defaults={
            "EmissiveMask": "engine\\textures\\editor\\black.xbm",
            "EmissiveEV": 0.0,
            "EmissiveAlphaThreshold": 0.005,
        },
        parameters={"EmissiveMask", "EmissiveEV", "EmissiveAlphaThreshold"},
    ),
    "base\\materials\\decal_tintable.mt": _projected(
        "decal_tintable",
        {"diffuse", "normal", "roughness", "metalness", "tint3", "atlas"},
        defaults={
            "DiffuseTexture": "engine\\textures\\editor\\white.xbm",
            "NormalTexture": "engine\\textures\\editor\\normal.xbm",
            "RoughnessTexture": "engine\\textures\\editor\\white.xbm",
            "TintMaskTexture": "test\\env_test\\masktest.xbm",
            "MaskColorR": (192 / 255, 0.0, 1 / 255, 1.0),
            "MaskColorG": (30 / 255, 189 / 255, 0.0, 1.0),
            "MaskColorB": (0.0, 44 / 255, 226 / 255, 1.0),
            "AtlasSize": (1.0, 1.0, 1.0, 1.0),
            "SubRegion": (1.0, 1.0, 1.0, 1.0),
        },
        parameters={
            "TintMaskTexture",
            "MaskColorR",
            "MaskColorG",
            "MaskColorB",
            "AtlasSize",
            "SubRegion",
        },
    ),
    "base\\materials\\decal_terrain_projected.mt": _projected(
        "decal_terrain_projected",
        {"terrain"},
        fidelity="source_limited_preview",
        defaults={
            "AlphaMask": "base\\environment\\terrain\\decals\\textures\\terrain_decal_mask_generic.xbm",
            "BaseColor": "engine\\textures\\editor\\white.xbm",
            "Roughness": "engine\\textures\\editor\\white.xbm",
            "SpecularIntensity": "engine\\textures\\editor\\white.xbm",
            "Normal": "engine\\textures\\small_flat_normal.xbm",
            "Microblend": "base\\surfaces\\microblends\\default.xbm",
            "BaseColorScale": (0.5, 0.5, 0.5, 0.0),
            "NormalStrength": 1.0,
            "MicroblendContrast": 0.4,
            "MaterialTiling": 100.0,
            "LayerTiling": 1.0,
            "MicroblendTiling": 1.0,
        },
        parameters={
            "AlphaMask",
            "AlphaMaskBlackPoint",
            "AlphaMaskWhitePoint",
            "BaseColor",
            "BaseColorScale",
            "Roughness",
            "SpecularIntensity",
            "RoughnessLevels",
            "SpecularIntensityLevels",
            "ColorMaskLevels",
            "Normal",
            "NormalStrength",
            "Microblend",
            "MicroblendContrast",
            "MaterialTiling",
            "LayerTiling",
            "MicroblendTiling",
        },
    ),
    "base\\materials\\decal_parallax.mt": _projected(
        "decal_parallax",
        {"diffuse", "normal", "roughness", "metalness", "atlas", "parallax"},
        defaults={
            "AtlasSize": (1024.0, 1024.0, 0.0, 0.0),
            "SubRegion": (400.0, 0.0, 80.0, 0.0),
            "HeightTexture": "engine\\textures\\editor\\grey.xbm",
            "HeightStrength": 0.0,
        },
        parameters={"AtlasSize", "SubRegion", "HeightTexture", "HeightStrength"},
    ),
    "base\\materials\\decal_forward.mt": _projected(
        "decal_forward",
        {"forward"},
        exact=True,
        cull="NONE",
        defaults={
            "BaseColor": "engine\\textures\\editor\\white.xbm",
            "Metalness": "engine\\textures\\editor\\black.xbm",
            "Roughness": "engine\\textures\\editor\\black.xbm",
            "Normal": "engine\\textures\\editor\\normal.xbm",
            "BaseColorScale": (0.0, 0.0, 0.0, 0.0),
            "MetalnessScale": 0.0,
            "MetalnessBias": 0.0,
            "RoughnessScale": 0.0,
            "RoughnessBias": 0.0,
            "Alpha": 1.0,
            "AlphaThreshold": 0.01,
            "EmissiveEV": 0.0,
        },
        parameters={
            "BaseColor",
            "BaseColorScale",
            "Normal",
            "Roughness",
            "Metalness",
            "Alpha",
            "AlphaThreshold",
            "EmissiveEV",
            "EmissiveEVRaytracingBias",
            "EmissiveDirectionality",
            "EnableRaytracedEmissive",
        },
    ),
    "base\\materials\\decal_braindance_thermal.mt": _projected(
        "decal_braindance_thermal",
        {"thermal"},
        fidelity="source_limited_preview",
        parameters={"DitherIntensity"},
    ),
    "base\\materials\\decal_caustics.mt": _projected(
        "decal_caustics",
        {"caustics"},
        fidelity="source_limited_preview",
        parameters={
            "Color",
            "EmissiveEV",
            "Distortion",
            "Contrast",
            "Speed",
            "SmallMovementSpeed",
            "Spread",
            "DistortionAmount",
            "DistortionUVScaling",
            "UVScaling",
            "EdgeWidth",
            "EdgeMultiplier",
            "MaxValue",
            "GradientStartPosition",
            "GradientLength",
        },
    ),
    "base\\materials\\decal_glitch.mt": _projected(
        "decal_glitch",
        {"glitch", "roughness"},
        fidelity="source_limited_preview",
        parameters={
            "GradientMap",
            "GlitchScale",
            "GlitchStrength",
            "GlitchChance",
            "GlitchOffOn",
            "DissapearingChance",
            "ColorChangeAmount",
            "EmissiveEV",
        },
    ),
    "base\\materials\\decal_glitch_emissive.mt": _projected(
        "decal_glitch_emissive",
        {"glitch_emissive"},
        parameters={
            "GradientMap",
            "GlitchScale",
            "GlitchStrength",
            "GlitchChance",
            "GlitchOffOn",
            "DissapearingChance",
            "ColorChangeAmount",
            "EmissiveEV",
        },
    ),
    "base\\surfaces\\textures\\decals\\road_markings\\materials\\road_markings_white.mi": _projected(
        "road_markings_white",
        {"diffuse"},
        exact=True,
    ),
}

MESH_PROFILES = {
    "base\\materials\\mesh_decal.mt": _mesh(
        "mesh_decal", {"base", "normal", "roughness", "metalness"}, exact=True
    ),
    "base\\materials\\mesh_decal_particles.mt": _mesh(
        "mesh_decal_particles",
        {"base", "normal", "roughness", "metalness", "particles"},
    ),
    "base\\materials\\mesh_decal_wet_character.mt": _mesh(
        "mesh_decal_wet_character",
        {"base", "normal", "roughness", "metalness", "wet"},
        exact=True,
    ),
    "base\\materials\\mesh_decal_gradientmap_recolor.mt": _mesh(
        "mesh_decal_gradientmap_recolor",
        {"gradient", "mask", "normal", "roughness", "metalness"},
        exact=True,
        defaults={
            "MaskTexture": "engine\\textures\\editor\\white.xbm",
            "GradientMap": "engine\\textures\\editor\\white.xbm",
            "SecondaryMaskUVScale": 0.0,
        },
        parameters={"MaskTexture", "GradientMap"},
    ),
    "base\\materials\\mesh_decal_gradientmap_recolor_2.mt": _mesh(
        "mesh_decal_gradientmap_recolor_2",
        {"gradient", "mask", "gradient_resource", "normal", "roughness", "metalness"},
        exact=True,
        defaults={"MaskTexture": "engine\\textures\\editor\\white.xbm"},
        parameters={"MaskTexture", "Gradient"},
    ),
    "base\\materials\\mesh_decal_gradientmap_recolor_emissive.mt": _mesh(
        "mesh_decal_gradientmap_recolor_emissive",
        {"gradient", "mask", "emissive_gradient", "normal"},
        exact=True,
        defaults={
            "MaskTexture": "engine\\textures\\editor\\white.xbm",
            "GradientMap": "engine\\textures\\editor\\white.xbm",
            "EmissiveGradientMap": "engine\\textures\\editor\\black.xbm",
            "DiffuseColor": (226 / 255, 226 / 255, 226 / 255, 1.0),
            "DiffuseAlpha": 1.0,
            "EmissiveEV": 1.0,
            "EmissiveAlphaThreshold": 0.0,
        },
        parameters={
            "MaskTexture",
            "GradientMap",
            "EmissiveGradientMap",
            "EmissiveEV",
            "EmissiveAlphaThreshold",
        },
    ),
    "base\\materials\\mesh_decal_multitinted.mt": _mesh(
        "mesh_decal_multitinted",
        {"multitint", "normal", "roughness", "metalness"},
        exact=True,
        defaults={
            "DiffuseColor": (0.0, 0.0, 0.0, 0.0),
            "TintMaskTexture": "engine\\textures\\editor\\white.xbm",
            "DepthThreshold": 0.997530997,
            **{f"TintColor{index}": (1.0, 1.0, 1.0, 1.0) for index in range(8)},
        },
        parameters={"TintMaskTexture", *(f"TintColor{index}" for index in range(8))},
    ),
    "base\\materials\\mesh_decal_revealed.mt": _mesh(
        "mesh_decal_revealed",
        {"revealed", "normal", "roughness", "metalness"},
        exact=True,
        defaults={
            "TileNumber": 0.0,
            "FlowTexture": "base\\fx\\textures\\gradients\\fx_gradient_falloff.xbm",
        },
        parameters={"TileNumber", "FlowTexture"},
    ),
    "base\\materials\\mesh_decal_parallax.mt": _mesh(
        "mesh_decal_parallax",
        {"base", "normal", "roughness", "metalness", "parallax"},
        fidelity="source_limited_preview",
        defaults={
            "SecondaryMaskUVScale": 0.0,
            "HeightTexture": "engine\\textures\\editor\\grey.xbm",
            "HeightStrength": 0.0,
        },
        parameters={"HeightTexture", "HeightStrength"},
    ),
    "base\\materials\\mesh_decal_double_diffuse.mt": _mesh(
        "mesh_decal_double_diffuse",
        {"base", "normal", "roughness", "metalness", "double_diffuse"},
        defaults={
            "SecondaryDiffuseAlpha": "engine\\textures\\editor\\grey.xbm",
            "SecondaryMaskUVScale": 0.0,
            "DepthThreshold": 0.0,
        },
        parameters={
            "GradientMap",
            "GradientMapIntensity",
            "GradientMapUV",
            "UseGradientMap",
            "SecondaryDiffuseAlpha",
            "SecondaryDiffuseColor",
            "SecondaryDiffuseAlphaIntensity",
        },
    ),
    "base\\materials\\mesh_decal_morph.mt": _mesh(
        "mesh_decal_morph",
        {"base", "normal", "roughness", "metalness", "double_diffuse", "morph"},
        defaults={
            "SecondaryDiffuseAlpha": "engine\\textures\\editor\\grey.xbm",
            "SecondaryMaskUVScale": 0.0,
            "DepthThreshold": 0.0,
            "Morph": 1.0,
            "StartAlpha": 0.0,
            "FinalAlpha": 1.0,
        },
        parameters={
            "Morph",
            "StartAlpha",
            "FinalAlpha",
            "GradientMap",
            "GradientMapIntensity",
            "GradientMapUV",
            "UseGradientMap",
            "SecondaryDiffuseAlpha",
            "SecondaryDiffuseColor",
            "SecondaryDiffuseAlphaIntensity",
        },
    ),
    "base\\materials\\mesh_decal_blendable.mt": _mesh(
        "mesh_decal_blendable",
        {"base", "normal", "roughness", "metalness", "blendable"},
        defaults={
            "DiffuseTexture": "base\\materials\\placeholder\\grey.xbm",
            "SecondaryMask": "base\\materials\\placeholder\\white.xbm",
            "SecondaryMaskUVScale": 0.0,
            "NormalTexture": "base\\materials\\placeholder\\normal.xbm",
            "NormalAlphaTex": "base\\materials\\placeholder\\white.xbm",
            "NormalsBlendingModeAlpha": "base\\materials\\placeholder\\white.xbm",
            "RoughnessTexture": "base\\materials\\placeholder\\grey.xbm",
            "MetalnessTexture": "base\\materials\\placeholder\\black.xbm",
        },
        parameters={
            "VectorField",
            "FadeOutDistance",
            "FadeOutOffset",
            "GlitchChance",
            "GlitchOffset",
            "FresnelColor",
            "FresnelColorIntensity",
            "FresnelExponent",
        },
    ),
    "base\\materials\\mesh_decal_gradientmap_recolor_blendable.mt": _mesh(
        "mesh_decal_gradientmap_recolor_blendable",
        {"gradient", "mask", "normal", "roughness", "metalness", "blendable"},
        defaults={
            "DiffuseTexture": "base\\materials\\placeholder\\grey.xbm",
            "MaskTexture": "base\\materials\\placeholder\\white.xbm",
            "GradientMap": "base\\materials\\placeholder\\white.xbm",
            "SecondaryMask": "base\\materials\\placeholder\\white.xbm",
            "SecondaryMaskUVScale": 0.0,
            "NormalTexture": "base\\materials\\placeholder\\normal.xbm",
            "RoughnessTexture": "base\\materials\\placeholder\\grey.xbm",
            "MetalnessTexture": "base\\materials\\placeholder\\black.xbm",
        },
        parameters={
            "MaskTexture",
            "GradientMap",
            "VectorField",
            "FadeOutDistance",
            "FadeOutOffset",
            "GlitchChance",
            "GlitchOffset",
            "FresnelColor",
            "FresnelColorIntensity",
            "FresnelExponent",
        },
    ),
    "base\\materials\\mesh_decal_emissive.mt": _mesh(
        "mesh_decal_emissive",
        {"emissive"},
        exact=True,
        defaults={
            "DiffuseTexture": "engine\\textures\\small_white.xbm",
            "DiffuseColor2": (0.0, 0.0, 0.0, 0.0),
            "EmissiveEV": 0.0,
            "ScrollSpeed": (0.0, 0.0, 0.0, 0.0),
            "HardOrSoftTransition": 0.0,
            "FullVisibilityFactor": 1.0,
            "EnableAlternateColor": 0.0,
            "EnableAlternateUVcoord": 0.0,
            "Preview2ndState": 0.0,
            "LayerTile": 1.0,
        },
        parameters={
            "DamageInfluence",
            "DamageInfluenceDebug",
            "DiffuseColor2",
            "EmissiveEV",
            "ScrollSpeed",
            "HardOrSoftTransition",
            "FullVisibilityFactor",
            "EnableAlternateColor",
            "EnableAlternateUVcoord",
            "Preview2ndState",
            "LayerTile",
            "MaterialParam0",
        },
    ),
    "base\\materials\\mesh_decal_emissive_subsurface.mt": _mesh(
        "mesh_decal_emissive_subsurface",
        {"emissive_subsurface"},
        exact=True,
        defaults={
            "EmissiveMask": "engine\\textures\\small_white.xbm",
            "SecondaryMask": "engine\\textures\\editor\\white.xbm",
            "EmissiveMaskChannel": (1.0, 0.0, 0.0, 0.0),
            "EmissiveColor": (1.0, 0.0, 0.0, 1.0),
            "EmissiveEV": 2.07620502,
            "AlphaThreshold": 0.0,
        },
        parameters={
            "EmissiveMask",
            "SecondaryMask",
            "EmissiveMaskChannel",
            "EmissiveColor",
            "EmissiveEV",
            "AlphaThreshold",
            "MaterialParam0",
        },
    ),
    "base\\materials\\vehicle_mesh_decal.mt": _mesh(
        "vehicle_mesh_decal",
        {"vehicle", "normal", "roughness", "metalness"},
        defaults=VEHICLE_MESH_DEFAULTS,
        parameters={
            "MaskTexture",
            "GradientMap",
            "UseGradientMap",
            "DamageInfluence",
            "DamageInfluenceDebug",
            "DirtMap",
            "DirtMapTilling",
            "DirtMask",
            "DirtMaskContrast",
            "DirtMaskOffsets",
            "DirtOpacity",
        },
    ),
    "base\\materials\\vehicle_mesh_decal_parallax.mt": _mesh(
        "vehicle_mesh_decal_parallax",
        {"vehicle", "normal", "roughness", "metalness", "parallax"},
        defaults={
            **VEHICLE_MESH_DEFAULTS,
            "HeightTexture": "engine\\textures\\editor\\grey.xbm",
            "HeightStrength": 0.0,
        },
        parameters={
            "MaskTexture",
            "GradientMap",
            "UseGradientMap",
            "DamageInfluence",
            "DamageInfluenceDebug",
            "DirtMap",
            "DirtMapTilling",
            "DirtMask",
            "DirtMaskContrast",
            "DirtMaskOffsets",
            "DirtOpacity",
            "HeightTexture",
            "HeightStrength",
        },
    ),
    "base\\fx\\_shaders\\blackwall_blendable_mesh_decal.mt": _mesh(
        "blackwall_blendable_mesh_decal",
        {"base", "normal", "roughness", "metalness", "blendable"},
        parameters={
            "VectorField",
            "FadeOutDistance",
            "FadeOutOffset",
            "GlitchChance",
            "GlitchOffset",
        },
    ),
    "base\\fx\\_shaders\\blackwall_blendable_mesh_decal_gradient.mt": _mesh(
        "blackwall_blendable_mesh_decal_gradient",
        {"gradient", "mask", "normal", "roughness", "metalness", "blendable"},
        parameters={
            "MaskTexture",
            "GradientMap",
            "VectorField",
            "FadeOutDistance",
            "FadeOutOffset",
            "GlitchChance",
            "GlitchOffset",
        },
    ),
}


def projected_profile(path):
    return PROJECTED_PROFILES.get(backslash_depot_key(path))


def mesh_profile(path):
    return MESH_PROFILES.get(backslash_depot_key(path))


ALL_PROFILES = {**PROJECTED_PROFILES, **MESH_PROFILES}

for _template, _profile in ALL_PROFILES.items():
    _profile.defaults.update(contract_defaults(_template))
