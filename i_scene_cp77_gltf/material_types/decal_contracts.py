from ..assetio.paths import backslash_depot_key

CONTRACTS = {
    "base\\fx\\_shaders\\mesh_decal__blackbody.mt": {
        "EmissiveAlphaContrast": ((2, "Scalar", 1, 0, 20),),
        "EmissiveEV": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "HSV_Mod": ((2, "Vector", (1, 1, 0, 0), None, None),),
        "HeatDistribution": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "HeatTiling": ((2, "Vector", (1, 1, 0, 0), None, None),),
        "MaskMinimum": ((2, "Scalar", 0, 0, 1),),
        "MaskTexture": (
            (
                2,
                "Texture",
                "base\\fx\\_textures\\masks\\noise\\fx_organic_noise_01_d.xbm",
                None,
                None,
            ),
        ),
        "Temperature": ((2, "Scalar", 30, 0, 100),),
        "UseFloatParam": ((2, "Scalar", 0, 0, 1),),
        "VehicleDamageInfluence": ((1, "Scalar", 1, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\decal_emissive_color.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "Emissive": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "EmissiveAlphaThreshold": (
            (2, "Scalar", 0.00499999989, -3.40282347e38, 3.40282347e38),
        ),
        "EmissiveColor": (
            (
                2,
                "Color",
                (
                    0.996078431372549,
                    0.996078431372549,
                    0.996078431372549,
                    0.996078431372549,
                ),
                None,
                None,
            ),
        ),
        "EmissiveEV": ((2, "Scalar", 0, 0, 10),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_emissive_only.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "EmissiveAlphaThreshold": (
            (2, "Scalar", 0.00499999989, -3.40282347e38, 3.40282347e38),
        ),
        "EmissiveEV": ((2, "Scalar", 0, 0, 10),),
        "EmissiveMask": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_forward.mt": {
        "Alpha": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AlphaThreshold": (
            (2, "Scalar", 0.00999999978, -3.40282347e38, 3.40282347e38),
        ),
        "BaseColor": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "BaseColorScale": ((2, "Color", (0.0, 0.0, 0.0, 0.0), None, None),),
        "EmissiveDirectionality": ((2, "Scalar", 0, 0, 1),),
        "EmissiveEV": ((2, "Scalar", 0, 0, 10),),
        "EmissiveEVRaytracingBias": ((2, "Scalar", 0, -10, 10),),
        "EnableRaytracedEmissive": ((2, "Scalar", 0, 0, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "Metalness": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "MetalnessScale": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "Normal": ((2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),),
        "Roughness": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_gradientmap_recolor.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "GradientMap": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "MaskTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_gradientmap_recolor_emissive.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "EmissiveEV": ((2, "Scalar", 0, 0, 10),),
        "EmissiveGradientMap": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "GradientMap": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "MaskTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_normal_roughness.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\small_flat_normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_normal_roughness_metalness.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\small_flat_normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_normal_roughness_metalness_2.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AtlasSize": ((2, "Vector", (1024, 1024, 0, 0), None, None),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 0.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\small_flat_normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SubRegion": ((2, "Vector", (400, 0, 80, 1024), None, None),),
    },
    "base\\materials\\decal_parallax.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AtlasSize": ((2, "Vector", (1024, 1024, 0, 0), None, None),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "HeightStrength": ((2, "Scalar", 0, 0, 3.40282347e38),),
        "HeightTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\small_flat_normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SubRegion": ((2, "Vector", (400, 0, 80, 0), None, None),),
    },
    "base\\materials\\decal_puddle.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "DiffuseAlpha": ((2, "Scalar", 0.0833330005, 0, 1),),
        "DiffuseColor": ((2, "Color", (0.0, 0.0, 0.0, 0.0), None, None),),
        "DiffuseTexture": (
            (
                2,
                "Texture",
                "base\\surfaces\\textures\\decals\\megabuiding\\puddle\\puddle_d.xbm",
                None,
                None,
            ),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\small_flat_normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (
                2,
                "Texture",
                "base\\surfaces\\textures\\decals\\megabuiding\\puddle\\puddle_r.xbm",
                None,
                None,
            ),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_roughness.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_roughness_only.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "Frame": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SubUVx": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "SubUVy": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
    },
    "base\\materials\\decal_terrain_projected.mt": {
        "AlphaMask": (
            (
                2,
                "Texture",
                "base\\environment\\terrain\\decals\\textures\\terrain_decal_mask_generic.xbm",
                None,
                None,
            ),
        ),
        "AlphaMaskBlackPoint": ((2, "Scalar", 0, -1, 1),),
        "AlphaMaskWhitePoint": ((2, "Scalar", 1, 0, 2),),
        "BaseColor": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "BaseColorScale": ((2, "Vector", (0.5, 0.5, 0.5, 0), None, None),),
        "ColorMaskLevels": ((2, "Vector", (1, 0, 1, 0), None, None),),
        "LayerTiling": ((2, "Scalar", 1, 9.99999975e-05, 300),),
        "MaterialTiling": ((2, "Scalar", 100, 9.99999975e-05, 300),),
        "Microblend": (
            (2, "Texture", "base\\surfaces\\microblends\\default.xbm", None, None),
        ),
        "MicroblendContrast": ((2, "Scalar", 0.400000006, 9.99999975e-05, 1),),
        "MicroblendTiling": ((2, "Scalar", 1, 9.99999975e-05, 300),),
        "Normal": (
            (2, "Texture", "engine\\textures\\small_flat_normal.xbm", None, None),
        ),
        "NormalStrength": ((2, "Scalar", 1, 0, 16),),
        "Roughness": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "RoughnessLevels": ((2, "Vector", (1, 0, 1, 0), None, None),),
        "SpecularIntensity": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SpecularIntensityLevels": ((2, "Vector", (0, 1, 0, 1), None, None),),
    },
    "base\\materials\\decal_tintable.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AtlasSize": ((2, "Vector", (1, 1, 1, 1), None, None),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "DiffuseTextureAsMaskTexture": ((2, "Scalar", 0, 0, 1),),
        "MaskColorB": (
            (
                2,
                "Color",
                (0.0, 0.17254901960784313, 0.8862745098039215, 1.0),
                None,
                None,
            ),
        ),
        "MaskColorG": (
            (
                2,
                "Color",
                (0.11764705882352941, 0.7411764705882353, 0.0, 1.0),
                None,
                None,
            ),
        ),
        "MaskColorR": (
            (
                2,
                "Color",
                (0.7529411764705882, 0.0, 0.00392156862745098, 1.0),
                None,
                None,
            ),
        ),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, -8, 8),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 1, 0, 1),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SubRegion": ((2, "Vector", (1, 1, 1, 1), None, None),),
        "TintMaskTexture": (
            (2, "Texture", "test\\env_test\\masktest.xbm", None, None),
        ),
    },
    "base\\materials\\mesh_decal.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "NormalsBlendingModeAlpha": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 1, 1, 100),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_blendable.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "base\\materials\\placeholder\\grey.xbm", None, None),
        ),
        "FadeOutDistance": (
            (1, "Scalar", 0.5, 0.00100000005, 100),
            (2, "Scalar", 0.5, 0.00100000005, 100),
        ),
        "FadeOutOffset": (
            (1, "Scalar", 0.200000003, -10, 10),
            (2, "Scalar", 0.200000003, -10, 10),
        ),
        "FresnelColor": (
            (2, "Color", (0.0, 0.8980392156862745, 1.0, 1.0), None, None),
        ),
        "FresnelColorIntensity": ((2, "Scalar", 8, 0, 20),),
        "FresnelExponent": ((2, "Scalar", 2, 0, 20),),
        "GlitchChance": ((1, "Scalar", 0, 0, 5),),
        "GlitchOffset": ((1, "Scalar", 0, 0, 5),),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "base\\materials\\placeholder\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "base\\materials\\placeholder\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "NormalsBlendingModeAlpha": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "base\\materials\\placeholder\\grey.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 0, 1, 100),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
        "VectorField": (
            (
                1,
                "TextureArray",
                "base\\fx\\textures\\braindance\\braindance_noise3d_05\\braindance_noise3d_05.texarray",
                None,
                None,
            ),
            (
                2,
                "TextureArray",
                "base\\fx\\textures\\braindance\\braindance_noise3d_05\\braindance_noise3d_05.texarray",
                None,
                None,
            ),
        ),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_double_diffuse.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "GradientMap": (
            (
                2,
                "Texture",
                "base\\characters\\common\\hair\\textures\\cap_gradiants\\hh_cap_grad__black_carbon.xbm",
                None,
                None,
            ),
        ),
        "GradientMapIntensity": ((2, "Scalar", 1, 0, 2),),
        "GradientMapUV": ((2, "Scalar", 1, 0, 1),),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "NormalsBlendingModeAlpha": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryDiffuseAlpha": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SecondaryDiffuseAlphaIntensity": ((2, "Scalar", 0, 0, 1),),
        "SecondaryDiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 0, 1, 100),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseGradientMap": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_emissive.mt": {
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DamageInfluence": ((1, "Scalar", 1, 0, 2),),
        "DamageInfluenceDebug": ((1, "Scalar", 0, 0, 1),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseColor2": ((2, "Color", (0.0, 0.0, 0.0, 0.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "EmissiveEV": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "EnableAlternateColor": ((2, "Scalar", 0, 0, 1),),
        "EnableAlternateUVcoord": ((2, "Scalar", 0, 0, 1),),
        "FullVisibilityFactor": ((2, "Scalar", 1, 1, 5),),
        "HardOrSoftTransition": ((2, "Scalar", 0, 0, 1),),
        "LayerTile": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "Preview2ndState": ((2, "Scalar", 0, 0, 1),),
        "ScrollSpeed": ((2, "Vector", (0, 0, 0, 0), None, None),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_emissive_subsurface.mt": {
        "AlphaThreshold": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "EmissiveColor": ((2, "Color", (1.0, 0.0, 0.0, 1.0), None, None),),
        "EmissiveEV": ((2, "Scalar", 2.07620502, -3.40282347e38, 3.40282347e38),),
        "EmissiveMask": (
            (2, "Texture", "engine\\textures\\small_white.xbm", None, None),
        ),
        "EmissiveMaskChannel": ((2, "Vector", (1, 0, 0, 0), None, None),),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_gradientmap_recolor.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "GradientMap": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "MaskTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 0, 1, 100),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_gradientmap_recolor_2.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "Gradient": ((2, "Gradient", None, None, None),),
        "MaskTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_gradientmap_recolor_blendable.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "base\\materials\\placeholder\\grey.xbm", None, None),
        ),
        "FadeOutDistance": (
            (1, "Scalar", 0.5, 0.00100000005, 100),
            (2, "Scalar", 0.5, 0.00100000005, 100),
        ),
        "FadeOutOffset": (
            (1, "Scalar", 0.200000003, -10, 10),
            (2, "Scalar", 0.200000003, -10, 10),
        ),
        "FresnelColor": (
            (2, "Color", (0.0, 0.8980392156862745, 1.0, 1.0), None, None),
        ),
        "FresnelColorIntensity": ((2, "Scalar", 8, 0, 20),),
        "FresnelExponent": ((2, "Scalar", 2, 0, 20),),
        "GlitchChance": ((1, "Scalar", 0, 0, 5),),
        "GlitchOffset": ((1, "Scalar", 0, 0, 5),),
        "GradientMap": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "MaskTexture": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "base\\materials\\placeholder\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "base\\materials\\placeholder\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "base\\materials\\placeholder\\grey.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "base\\materials\\placeholder\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 0, 1, 100),),
        "VectorField": (
            (
                1,
                "TextureArray",
                "base\\fx\\textures\\braindance\\braindance_noise3d_05\\braindance_noise3d_05.texarray",
                None,
                None,
            ),
            (
                2,
                "TextureArray",
                "base\\fx\\textures\\braindance\\braindance_noise3d_05\\braindance_noise3d_05.texarray",
                None,
                None,
            ),
        ),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_gradientmap_recolor_emissive.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": (
            (
                2,
                "Color",
                (0.8862745098039215, 0.8862745098039215, 0.8862745098039215, 1.0),
                None,
                None,
            ),
        ),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "EmissiveEV": ((2, "Scalar", 1, 0, 10),),
        "EmissiveGradientMap": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "GradientMap": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "MaskTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_morph.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "FinalAlpha": ((2, "Scalar", 1, 0, 1),),
        "GradientMap": (
            (
                2,
                "Texture",
                "base\\characters\\common\\hair\\textures\\cap_gradiants\\hh_cap_grad__black_carbon.xbm",
                None,
                None,
            ),
        ),
        "GradientMapIntensity": ((2, "Scalar", 1, 0, 2),),
        "GradientMapUV": ((2, "Scalar", 1, 0, 1),),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "Morph": ((1, "Scalar", 1, 0, 1), (2, "Scalar", 1, 0, 1)),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "NormalsBlendingModeAlpha": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryDiffuseAlpha": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "SecondaryDiffuseAlphaIntensity": ((2, "Scalar", 0, 0, 1),),
        "SecondaryDiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 0, 1, 100),),
        "StartAlpha": ((2, "Scalar", 0, 0, 1),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseGradientMap": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_multitinted.mt": {
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.997530997, 0, 1),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (0.0, 0.0, 0.0, 0.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "TintColor0": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor1": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor2": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor3": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor4": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor5": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor6": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintColor7": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "TintMaskTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_parallax.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "HeightStrength": ((2, "Scalar", 0, 0, 3.40282347e38),),
        "HeightTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 0, 1, 100),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_particles.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "NormalsBlendingModeAlpha": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 1, 1, 100),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_revealed.mt": {
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "FlowTexture": (
            (
                2,
                "Texture",
                "base\\fx\\textures\\gradients\\fx_gradient_falloff.xbm",
                None,
                None,
            ),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "TileNumber": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
    "base\\materials\\mesh_decal_wet_character.mt": {
        "AlphaMaskContrast": ((2, "Scalar", 0, -1, 1),),
        "AnimationFramesHeight": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationFramesWidth": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "AnimationSpeed": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "DepthThreshold": ((2, "Scalar", 0.5, 0, 10),),
        "DiffuseAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "DiffuseColor": ((2, "Color", (1.0, 1.0, 1.0, 1.0), None, None),),
        "DiffuseTexture": (
            (2, "Texture", "engine\\textures\\editor\\grey.xbm", None, None),
        ),
        "MetalnessBias": ((2, "Scalar", 0, 0, 1),),
        "MetalnessScale": ((2, "Scalar", 1, 0, 2),),
        "MetalnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\black.xbm", None, None),
        ),
        "NormalAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "NormalAlphaTex": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "NormalTexture": (
            (2, "Texture", "engine\\textures\\editor\\normal.xbm", None, None),
        ),
        "NormalsBlendingMode": ((2, "Scalar", 0, 0, 1),),
        "RoughnessBias": ((2, "Scalar", 0, 0, 1),),
        "RoughnessMetalnessAlpha": ((2, "Scalar", 0, -3.40282347e38, 3.40282347e38),),
        "RoughnessScale": ((2, "Scalar", 1, 0, 2),),
        "RoughnessTexture": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMask": (
            (2, "Texture", "engine\\textures\\editor\\white.xbm", None, None),
        ),
        "SecondaryMaskInfluence": ((2, "Scalar", 0, 0, 1),),
        "SecondaryMaskUVScale": ((2, "Scalar", 1, 1, 100),),
        "UVOffsetX": ((2, "Scalar", 0, -1, 1),),
        "UVOffsetY": ((2, "Scalar", 0, -1, 1),),
        "UVRotation": ((2, "Scalar", 0, -1, 1),),
        "UVScaleX": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UVScaleY": ((2, "Scalar", 1, -3.40282347e38, 3.40282347e38),),
        "UseNormalAlphaTex": ((2, "Scalar", 0, 0, 1),),
        "VertexOffsetFactor": ((1, "Scalar", 0, 0, 1),),
    },
}


def contract_records(template):
    return CONTRACTS.get(backslash_depot_key(template), {})


def contract_defaults(template):
    return {
        name: records[-1][2] for name, records in contract_records(template).items()
    }
