<<<<<<< Updated upstream

import bpy

from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import CreateShaderNodeRGB, CreateShaderNodeValue, bsdf_socket_names, create_node, loc

from .mat_common import MaterialTypeBase, create_normal_map_rel


class Glass(MaterialTypeBase):
    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBDSF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        pBDSF.inputs[sockets['Transmission']].default_value = 1
        # JATO: setting for blender eevee that improves transmission/refraction look
        Mat.use_raytrace_refraction = True

        isVehicleGlass = False

        # JATO: should be a safe method to test for vehicleglass.mt
        if "ShatterTexture" in Data:
            isVehicleGlass = True

        if "TintColor" in Data:
            tintColor = CreateShaderNodeRGB(CurMat, Data["TintColor"], -800, 600, 'TintColor')
            tintColor.hide = False

        if "IOR" in Data:
            safeIOR = (Data['IOR'])
            if safeIOR < 1:
                safeIOR = 1
            else:
                safeIOR = (Data['IOR'])
            IOR = CreateShaderNodeValue(CurMat, safeIOR, -600, -50, "IOR")
            CurMat.links.new(IOR.outputs[0], pBDSF.inputs['IOR'])

        if "Roughness" in Data:
            rImg = imageFromRelPath(
                    Data["Roughness"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            rImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1200, 0), label="Roughness", image=rImg)
            CurMat.links.new(rImgNode.outputs[0], pBDSF.inputs['Roughness'])
            if isVehicleGlass:
                CurMat.links.new(rImgNode.outputs[1], pBDSF.inputs['Roughness'])

        if "Normal" in Data:
            nMap = create_normal_map_rel(
                CurMat, Data["Normal"], -600, -300, 'Normal', self.image_format, self.BasePath, self.ProjPath
                )

            # Normal Strength
            if "NormalStrength" in Data:
                strength_val = float(Data["NormalStrength"])
                strength_node = CreateShaderNodeValue(CurMat, strength_val, -450, -350, "NormalStrength")
                CurMat.links.new(strength_node.outputs[0], nMap.inputs['Strength'])

            # NormalTileAndOffset
            if "NormalTileAndOffset" in Data:
                tile_offset = Data["NormalTileAndOffset"]
                # Vector4: (tileX, tileY, offsetX, offsetY)
                uv_map = create_node(CurMat.nodes, "ShaderNodeUVMap", (-200, -300), label="UV Map")
                mapping = create_node(CurMat.nodes, "ShaderNodeMapping", (-400, -300), label="Normal Mapping")

                # Tile (scale)
                mapping.inputs['Scale'].default_value[0] = float(tile_offset.get('X', 1.0)) or 1.0
                mapping.inputs['Scale'].default_value[1] = float(tile_offset.get('Y', 1.0)) or 1.0
                # Offset
                mapping.inputs['Location'].default_value[0] = float(tile_offset.get('Z', 0.0)) or 0.0
                mapping.inputs['Location'].default_value[1] = float(tile_offset.get('W', 0.0)) or 0.0

                tex_img = [node for node in CurMat.nodes if
                           node.label == 'Normal' and isinstance(node, bpy.types.ShaderNodeTexImage)]
                if tex_img:
                    tex_img = tex_img[0]
                    CurMat.links.new(uv_map.outputs[0], mapping.inputs[0])
                    CurMat.links.new(mapping.outputs[0], tex_img.inputs[0])

            CurMat.links.new(nMap.outputs[0], pBDSF.inputs['Normal'])

        alphaAdd = create_node(CurMat.nodes, "ShaderNodeMath", (-800, 150), operation='ADD')

        transmissionMultiply = create_node(CurMat.nodes, "ShaderNodeMath", (-800, 300), operation='MULTIPLY')

        if "MaskTexture" in Data:
            mImg = imageFromRelPath(
                    Data["MaskTexture"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath,
                    isNormal=True
                    )
            mImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1200, 350), label="MaskTexture", image=mImg)

            CurMat.links.new(mImgNode.outputs[1], transmissionMultiply.inputs[0])

            CurMat.links.new(mImgNode.outputs[1], alphaAdd.inputs[0])
            CurMat.links.new(alphaAdd.outputs[0], pBDSF.inputs['Alpha'])

        mixRGB = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-800, 400), blend_type='MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        if "TintColor" in Data:
            CurMat.links.new(tintColor.outputs[0], mixRGB.inputs[1])
        else:
            mixRGB.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
        if "MaskTexture" in Data:
            CurMat.links.new(mImgNode.outputs[0], mixRGB.inputs[2])
        else:
            mixRGB.inputs[2].default_value = (1.0, 1.0, 1.0, 1.0)
            transmissionMultiply.inputs[0].default_value = 0.0
        CurMat.links.new(mixRGB.outputs[0], pBDSF.inputs['Base Color'])

        transmissionInvert = create_node(CurMat.nodes, "ShaderNodeMath", (-600, 300), operation='SUBTRACT')
        transmissionInvert.inputs[0].default_value = 1

        CurMat.links.new(transmissionMultiply.outputs[0], transmissionInvert.inputs[1])
        CurMat.links.new(transmissionInvert.outputs[0], pBDSF.inputs['Transmission Weight'])

        if "MaskOpacity" in Data:
            maskOpacity = CreateShaderNodeValue(CurMat, Data["MaskOpacity"], -800, 250, "MaskOpacity")
            CurMat.links.new(maskOpacity.outputs[0], mixRGB.inputs[0])
            CurMat.links.new(maskOpacity.outputs[0], transmissionMultiply.inputs[1])

        if "Opacity" in Data:
            opacity = CreateShaderNodeValue(CurMat, Data["Opacity"], -800, 100, "Opacity")
            CurMat.links.new(opacity.outputs[0], alphaAdd.inputs[1])


# The above is the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

=======
from ..assetio.paths import backslash_depot_key
from ..bartmoss.scalar import clamp01, clamp_scalar, lerp_three
from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .graph import mix_color_socket, set_transparent, value_socket
from .mat_common import (
    MaterialTypeBase,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
)
from .normal_math import decode_cp77_normal, tangent_to_normal_map

# Authored dielectric response anchors from smooth to sharp.
_GLASS_F0 = (0.25, 0.08, 0.04)
_MIRROR_GLASS_F0 = (0.25, 0.04, 0.0)

# Defaults are template-specific because the glass variants use different
# opacity and roughness behavior.
_TEMPLATE_DEFAULTS = {
    "base\\materials\\mirror_glass.mt": {
        "FresnelBias": 0.75,
        "FrontFacesReflectionPower": 1,
        "GlassRoughnessBias": -1,
        "GlassSpecularColor": (1, 1, 1, 1),
        "GlassTint": r"engine\textures\editor\white.xbm",
        "MaskOpacity": 0,
        "MaskRoughnessBias": 0,
        "MaskTexture": r"engine\textures\editor\white.xbm",
        "Opacity": 1,
        "Roughness": r"engine\textures\editor\white.xbm",
        "RoughnessTileAndOffset": (1, 1, 0, 0),
        "SurfaceMetalness": 0,
        "TintColor": (0.8, 0.8, 0.8, 1),
        "UvOffsetX": 0,
        "UvOffsetY": 0,
        "UvTilingX": 1,
        "UvTilingY": 1,
    },
    "base\\materials\\glass.mt": {
        "BackFacesReflectionPower": 1,
        "BlurByRoughness": 0,
        "BlurRadius": 0,
        "FresnelBias": 1,
        "FrontFacesReflectionPower": 1,
        "GlassRoughnessBias": -1,
        "GlassSpecularColor": (1, 1, 1, 1),
        "GlassTint": r"base\materials\placeholder\white.xbm",
        "GlassTintTileAndOffset": (1, 1, 0, 0),
        "IOR": 1,
        "MaskOpacity": 0,
        "MaskRoughnessBias": 0,
        "MaskTexture": r"engine\textures\editor\white.xbm",
        "Normal": r"engine\textures\editor\normal.xbm",
        "NormalMapAffectsSpecular": 1,
        "NormalStrength": 1,
        "NormalTileAndOffset": (1, 1, 0, 0),
        "Opacity": 1,
        "OpacityBackFace": 0,
        "RefractionDepth": 2.5,
        "Roughness": r"engine\textures\editor\white.xbm",
        "RoughnessTileAndOffset": (1, 1, 0, 0),
        "SurfaceMetalness": 0,
        "TintColor": (0.898039216, 0.898039216, 0.898039216, 1),
        "TintFromVertexPaint": 0,
        "UvOffsetX": 0,
        "UvOffsetY": 0,
        "UvTilingX": 1,
        "UvTilingY": 1,
    },
    "base\\materials\\glass_onesided.mt": {
        "BlurByRoughness": 0,
        "BlurRadius": 0,
        "FresnelBias": 1,
        "FrontFacesReflectionPower": 1,
        "GlassRoughnessBias": -1,
        "GlassSpecularColor": (1, 1, 1, 1),
        "GlassTint": r"base\materials\placeholder\white.xbm",
        "GlassTintTileAndOffset": (1, 1, 0, 0),
        "IOR": 1,
        "MaskOpacity": 0,
        "MaskRoughnessBias": 0,
        "MaskTexture": r"engine\textures\editor\white.xbm",
        "Normal": r"engine\textures\editor\normal.xbm",
        "NormalMapAffectsSpecular": 1,
        "NormalStrength": 1,
        "NormalTileAndOffset": (1, 1, 0, 0),
        "Opacity": 1,
        "RefractionDepth": 2.5,
        "Roughness": r"engine\textures\editor\white.xbm",
        "RoughnessTileAndOffset": (1, 1, 0, 0),
        "SurfaceMetalness": 0,
        "TintColor": (0.898039216, 0.898039216, 0.898039216, 1),
        "TintFromVertexPaint": 0,
        "UvOffsetX": 0,
        "UvOffsetY": 0,
        "UvTilingX": 1,
        "UvTilingY": 1,
    },
    "base\\materials\\glass_blendable.mt": {
        "BlurByRoughness": 0,
        "BlurRadius": 0,
        "FadeOutDistance": 0.5,
        "FadeOutOffset": 0.200000003,
        "FresnelBias": 1.20000005,
        "FresnelColor": (0, 0.898039216, 1, 1),
        "FresnelColorIntensity": 8,
        "FresnelExponent": 2,
        "FrontFacesReflectionPower": 1.20000005,
        "GlassRoughnessBias": -1,
        "GlassSpecularColor": (1, 0.988235294, 0.988235294, 1),
        "GlassTint": r"base\characters\main_npc\silverhand\textures\h1_001_ma_specs__silverhand_d01.xbm",
        "GlitchChance": 0,
        "GlitchOffset": 0,
        "IOR": 1.04999995,
        "MaskOpacity": 0,
        "MaskRoughnessBias": 0,
        "MaskTexture": r"base\characters\main_npc\silverhand\textures\h1_001_ma_specs__silverhand_d01.xbm",
        "Normal": r"base\characters\main_npc\silverhand\textures\h1_001_ma_specs__silverhand_n01.xbm",
        "NormalMapAffectsSpecular": 1,
        "NormalStrength": 1.20000005,
        "Opacity": 1,
        "RefractionDepth": 0.0500000007,
        "Roughness": r"base\materials\placeholder\black.xbm",
        "SurfaceMetalness": 0.200000003,
        "TintColor": (1, 1, 1, 1),
        "TintFromVertexPaint": 0,
        "VectorField": r"base\fx\textures\braindance\braindance_noise3d_05\braindance_noise3d_05.texarray",
    },
    "base\\materials\\glass_scope.mt": {
        "AberrationStrenght": 5,
        "Diffuse": r"base\materials\placeholder\white.xbm",
        "DistortionStrenght": 1.5,
        "EmissiveTint": 0,
        "EyeRelief": (0.5, 0.25, 1, 0),
        "FresnelBias": 1,
        "GlassTint": r"base\materials\placeholder\white.xbm",
        "GlassTintMultiplier": (0.203921569, 1, 0, 1),
        "LensBulge": r"base\materials\placeholder\normal.xbm",
        "LensBulgeHardness": 0,
        "LensBulgeRadius": 0.5,
        "LensBulgeStrength": 1,
        "LensMetalness": 0.5,
        "LensReflectionPower": 1,
        "LensRoughness": 0,
        "LensSpecularColor": (1, 0, 0, 1),
        "MaskOpacity": 0,
        "Normal": r"base\materials\placeholder\normal.xbm",
        "Roughness": r"base\materials\placeholder\black.xbm",
        "ScopeInside": (0.105882353, 0.2, 0.109803922, 1),
        "ScopeMaskClose": r"base\materials\placeholder\white.xbm",
        "ScopeMaskFar": r"base\materials\placeholder\white.xbm",
        "ScopeMaskFarDistance": 2,
        "SpecularPower": 1,
        "SphereMaskCloseHardness": 0.949999988,
        "SphereMaskCloseRadius": 0.5,
        "SphereMaskDistortionHardness": 0.5,
        "SphereMaskDistortionRadius": 0.5,
        "SphereMaskFarHardness": 0.5,
        "SphereMaskFarRadius": 0.5,
        "SurfaceMetalness": 1,
        "UseMask": (0, 0, 0, 0),
        "UvTilingOffset": (0, 0, 0, 0),
    },
    "base\\materials\\vehicle_glass_onesided.mt": {
        "Cracks": r"base\vehicles\common\textures\cracked_glass_mask.xbm",
        "CracksTiling": 14,
        "DamageGridCutout": 0.330000013,
        "DamageInfluence": 0,
        "DamageInfluenceDebug": 0,
        "DebugShatterPoint0": (0, 0, 0, 0),
        "DotsNormalTxt": r"base\vehicles\common\textures\vehicle_glass_rain_drops_n.xbm",
        "DotsTxt": r"base\vehicles\common\textures\vehicle_glass_rain_drops.xbm",
        "FlowNormal": r"base\vehicles\common\textures\vehicle_glass_rain_flow_n.xbm",
        "FlowTxt": r"base\vehicles\common\textures\vehicle_glass_rain_flow.xbm",
        "FresnelBias": 1,
        "FrontFacesReflectionPower": 1,
        "GlassSpecularColor": (1, 1, 1, 1),
        "GlassTint": r"base\materials\placeholder\white.xbm",
        "MaskOpacity": 1,
        "MaskRoughnessBias": -0.400000006,
        "MaskTexture": r"base\vehicles\common\textures\common_windows_dirt_d02.xbm",
        "Normal": r"engine\textures\small_flat_normal.xbm",
        "NormalStrength": 1,
        "Opacity": 1,
        "Roughness": r"engine\textures\small_white.xbm",
        "ShatterAspectRatio": 0.5,
        "ShatterColor": (0.552941176, 0.796078431, 0.82745098, 0.941176471),
        "ShatterCutout": 0.699999988,
        "ShatterNormal": r"base\vehicles\common\textures\bullethole_n01.xbm",
        "ShatterNormalStrength": 1,
        "ShatterRadiusScale": 0.125,
        "ShatterTexture": r"base\vehicles\common\textures\bullethole_mask.xbm",
        "SurfaceMetalness": 0,
        "TintColor": (0.635294118, 0.678431373, 0.705882353, 0),
        "TintSurface": (0.505882353, 0.51372549, 0.415686275, 1),
        "UseDamageGrid": 1,
        "UseShatterPoints": 1,
        "UvOffsetX": 0,
        "UvOffsetY": 0,
        "UvTilingX": 1,
        "UvTilingY": 1,
    },
    "base\\materials\\vehicle_glass_flat_twosided.mt": {
        "BackFacesReflectionPower": 1,
        "Cracks": r"base\vehicles\common\textures\cracked_glass_mask.xbm",
        "CracksTiling": 14,
        "DamageGridCutout": 0.330000013,
        "DamageInfluence": 0,
        "DamageInfluenceDebug": 0,
        "DebugShatterPoint0": (0, 0, 0, 0),
        "DotsNormalTxt": r"base\vehicles\common\textures\vehicle_glass_rain_drops_n.xbm",
        "DotsTxt": r"base\vehicles\common\textures\vehicle_glass_rain_drops.xbm",
        "FlowNormal": r"base\vehicles\common\textures\vehicle_glass_rain_flow_n.xbm",
        "FlowTxt": r"base\vehicles\common\textures\vehicle_glass_rain_flow.xbm",
        "FresnelBias": 1,
        "FrontFacesReflectionPower": 1,
        "GlassSpecularColor": (1, 1, 1, 1),
        "GlassTint": r"base\materials\placeholder\white.xbm",
        "MaskOpacity": 1,
        "MaskRoughnessBias": -0.400000006,
        "MaskTexture": r"base\vehicles\common\textures\common_windows_dirt_d02.xbm",
        "Normal": r"engine\textures\small_flat_normal.xbm",
        "NormalStrength": 1,
        "Opacity": 1,
        "OpacityBackFace": 1,
        "Roughness": r"engine\textures\small_white.xbm",
        "ShatterAspectRatio": 0.5,
        "ShatterColor": (0.552941176, 0.796078431, 0.82745098, 0.941176471),
        "ShatterCutout": 0.699999988,
        "ShatterNormal": r"base\vehicles\common\textures\bullethole_n01.xbm",
        "ShatterNormalStrength": 1,
        "ShatterRadiusScale": 0.125,
        "ShatterTexture": r"base\vehicles\common\textures\bullethole_mask.xbm",
        "SurfaceMetalness": 0,
        "TintColor": (0.635294118, 0.678431373, 0.705882353, 0),
        "TintSurface": (0.505882353, 0.51372549, 0.415686275, 1),
        "UseDamageGrid": 1,
        "UseShatterPoints": 1,
        "UvOffsetX": 0,
        "UvOffsetY": 0,
        "UvTilingX": 1,
        "UvTilingY": 1,
    },
}


# Fallback for templates without an explicit defaults table.
_SCALAR_DEFAULTS = {
    "Opacity": 1.0,
    "OpacityBackFace": 0.0,
    "TintFromVertexPaint": 0.0,
    "FrontFacesReflectionPower": 1.0,
    "BackFacesReflectionPower": 1.0,
    "IOR": 1.0,
    "RefractionDepth": 0.0,
    "FresnelBias": 1.0,
    "NormalStrength": 1.0,
    "NormalMapAffectsSpecular": 1.0,
    "SurfaceMetalness": 0.0,
    "MaskOpacity": 0.0,
    "GlassRoughnessBias": -1.0,
    "MaskRoughnessBias": 0.0,
    "BlurRadius": 0.0,
    "BlurByRoughness": 0.0,
    "UvTilingX": 1.0,
    "UvTilingY": 1.0,
    "UvOffsetX": 0.0,
    "UvOffsetY": 0.0,
}


# Frosted variants expose the same graph through a renamed parameter set.
_FROSTED_ALIASES = {
    "TintColor": "ColorMultiplier",
    "MaskTexture": "Diffuse",
    "OpacityBackFace": "RenderBackFaces",
    "GlassRoughnessBias": "RoughnessBase",
}

_FROSTED_TEMPLATES = frozenset(
    {
        "base\\materials\\frosted_glass.mt",
    }
)
_FROSTED_TEMPLATES_NORMALIZED = frozenset(
    backslash_depot_key(name) for name in _FROSTED_TEMPLATES
)


def _is_frosted(template):
    return backslash_depot_key(template) in _FROSTED_TEMPLATES_NORMALIZED


def _template_name(path):
    return backslash_depot_key(path).rsplit("\\", 1)[-1]


def _is_mirror_glass(template):
    return _template_name(template) == "mirror_glass.mt"


def _is_vehicle_glass(template):
    return "vehicle_glass" in backslash_depot_key(template)


_TEMPLATE_DEFAULTS_NORMALIZED = {
    backslash_depot_key(key): value for key, value in _TEMPLATE_DEFAULTS.items()
}


def template_defaults(template):
    """Authored .mt values for one template, falling back to the shared table"""
    return _TEMPLATE_DEFAULTS_NORMALIZED.get(
        backslash_depot_key(template), _SCALAR_DEFAULTS
    )


_UNIT = (1.0, 1.0, 1.0, 1.0)
_IDENTITY_TILE = (1.0, 1.0, 0.0, 0.0)


def _ior_from_f0(f0):
    """Inverts F0 = ((n-1)/(n+1))^2"""
    root = max(0.0, min(0.99, float(f0))) ** 0.5
    return (1.0 + root) / (1.0 - root)


class Glass(MaterialTypeBase):
    def _material_defaults(self, template):
        return template_defaults(template)

    def _uses_surface_tint(self, template):
        return _is_vehicle_glass(template)

    def _tiled_texture(
        self,
        nodes,
        links,
        data,
        key,
        location,
        *,
        tile_offset,
        non_color,
        defaults,
        aliases=None,
        uv_source=None,
    ):
        """Create one image node with an independent UV transform"""
        aliases = aliases or {}
        path = param_texture_path(data, aliases.get(key, key)) or defaults.get(
            aliases.get(key, key), defaults.get(key, "")
        )
        if not path:
            return None
        image = self._load_relative_image(
            path, non_color=non_color, error_label="glass"
        )
        if image is None:
            return None

        node = new_labeled_node(nodes, "ShaderNodeTexImage", key, location)
        node.image = image
        node.extension = "REPEAT"

        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", f"{key} UV", (location[0] - 220, location[1])
        )
        if uv_source is None:
            uv = new_labeled_node(
                nodes,
                "ShaderNodeUVMap",
                f"{key} UV Map",
                (location[0] - 400, location[1]),
            )
            uv_source = uv.outputs["UV"]
        links.new(uv_source, mapping.inputs["Vector"])
        tile_x, tile_y, offset_x, offset_y = tile_offset
        mapping.inputs["Location"].default_value = (
            float(offset_x),
            float(offset_y),
            0.0,
        )
        mapping.inputs["Scale"].default_value = (float(tile_x), float(tile_y), 1.0)
        links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    def _normal_sockets(self, nodes, links, data, normal_texture, scalar, material):
        if normal_texture is None:
            return None, None

        decoder = decode_cp77_normal(
            material.node_tree,
            normal_texture.outputs["Color"],
            strength=max(0.0, scalar("NormalStrength")),
            location=(-760, -460),
            label="Glass DirectX Normal",
        )
        mapped_normal = tangent_to_normal_map(
            material.node_tree,
            decoder.outputs["Color"],
            location=(-500, -460),
            label="Glass Normal",
        )

        affects = clamp01(scalar("NormalMapAffectsSpecular"))
        if affects >= 1.0:
            return mapped_normal, mapped_normal

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Geometry Normal", (-620, -660)
        )
        if affects <= 0.0:
            return mapped_normal, geometry.outputs["Normal"]

        blend = new_labeled_node(
            nodes, "ShaderNodeMix", "NormalMapAffectsSpecular", (-260, -560)
        )
        blend.data_type = "VECTOR"
        factor = find_input(blend, "Factor")
        if factor is not None:
            factor.default_value = affects
        links.new(
            geometry.outputs["Normal"],
            shader_nodes.socket_by_identifier(blend.inputs, "A_Vector"),
        )
        links.new(
            mapped_normal, shader_nodes.socket_by_identifier(blend.inputs, "B_Vector")
        )
        lighting_normal = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            blend.outputs.get("Result")
            or shader_nodes.socket_by_identifier(blend.outputs, "Result_Vector"),
            name="Normalized Specular Normal",
            location=(-40, -560),
        )
        return mapped_normal, lighting_normal

    def _glass_tint_fresnel(self, nodes, links, normal_socket, bias, location):
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Glass Tint View", location
        )
        view = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            geometry.outputs["Incoming"],
            name="Glass View Direction",
            location=(location[0] + 180, location[1] - 120),
        )
        normal = normal_socket or geometry.outputs["Normal"]
        ndotv = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            normal,
            view,
            name="Glass N dot V",
            location=(location[0] + 180, location[1]),
        )
        ndotv = shader_nodes.clamp(
            nodes,
            links,
            ndotv,
            name="Glass N dot V Saturate",
            location=(location[0] + 360, location[1]),
        )
        one_minus = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            ndotv,
            name="Glass One Minus N dot V",
            location=(location[0] + 720, location[1]),
        )
        remapped = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            one_minus,
            0.8,
            name="Glass Fresnel Remap",
            location=(location[0] + 900, location[1]),
            use_clamp=True,
        )
        exponent = float(lerp_three((0.5, 1.5, 4.0), bias))
        return shader_nodes.math(
            nodes,
            links,
            "POWER",
            remapped,
            exponent,
            name="Glass Tint Fresnel",
            location=(location[0] + 1080, location[1]),
            use_clamp=True,
        )

    def _glass_tint_background(self, nodes, links, tint, fresnel, location):
        saturated = shader_nodes.vector_math(
            nodes,
            links,
            "MAXIMUM",
            tint,
            (0.0, 0.0, 0.0),
            name="Glass Tint Min",
            location=location,
        )
        saturated = shader_nodes.vector_math(
            nodes,
            links,
            "MINIMUM",
            saturated,
            (1.0, 1.0, 1.0),
            name="Glass Tint Saturate",
            location=(location[0] + 180, location[1]),
        )
        edge_tint = shader_nodes.vector_math(
            nodes,
            links,
            "POWER",
            saturated,
            (1.5, 1.5, 1.5),
            name="Glass Edge Tint Power",
            location=(location[0] + 360, location[1]),
        )
        edge_tint = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            edge_tint,
            scale=0.75,
            name="Glass Edge Tint",
            location=(location[0] + 540, location[1]),
        )
        return mix_color_socket(
            nodes,
            links,
            "Glass Tint Background",
            tint,
            edge_tint,
            fresnel,
            (location[0] + 720, location[1]),
        )

    def _mask_uv(self, nodes, links, data, location, defaults):
        """Scale mask UV by the authored X/Y tiling, then add the authored X/Y offset"""
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "Mesh UV", location)
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "Mask UV", (location[0] + 200, location[1])
        )
        links.new(uv.outputs["UV"], mapping.inputs["Vector"])
        mapping.inputs["Location"].default_value = (
            param_float(data, "UvOffsetX", defaults.get("UvOffsetX", 0.0)),
            param_float(data, "UvOffsetY", defaults.get("UvOffsetY", 0.0)),
            0.0,
        )
        mapping.inputs["Scale"].default_value = (
            param_float(data, "UvTilingX", defaults.get("UvTilingX", 1.0)),
            param_float(data, "UvTilingY", defaults.get("UvTilingY", 1.0)),
            1.0,
        )
        return mapping.outputs["Vector"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        template = str(Mat.get("MaterialTemplate", "") or "")
        defaults = self._material_defaults(template)

        frosted = _is_frosted(template)
        aliases = _FROSTED_ALIASES if frosted else {}

        def raw_scalar(name):
            key = aliases.get(name, name)
            return param_float(
                data,
                key,
                defaults.get(key, defaults.get(name, _SCALAR_DEFAULTS.get(name, 0.0))),
            )

        def scalar(name):
            if not frosted:
                return raw_scalar(name)
            # Derived constants for the FROSTED_GLASS profile.
            if name == "OpacityFrontFace" or name == "Opacity":
                return 1.0
            if name == "TintFromVertexPaint":
                return 0.0
            if name == "GlassRoughnessBias":
                return clamp_scalar(param_float(data, "RoughnessBase", 0.0), -1.0, 1.0)
            if name == "MaskRoughnessBias":
                # Map roughness attenuation into the authored bias range.
                return -1.0 + clamp01(param_float(data, "RoughnessAttenuation", 0.0))
            return raw_scalar(name)

        def vector(name):
            key = aliases.get(name, name)
            return param_vector(
                data, key, defaults.get(key, defaults.get(name, _IDENTITY_TILE))
            )

        def texture(name):
            key = aliases.get(name, name)
            return param_texture_path(data, key) or defaults.get(
                key, defaults.get(name, "")
            )

        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (860, 0)
        )

        # MaskUV feeds both MaskTexture and (further transformed) GlassTint; it is
        # only worth building when one of those textures actually resolves.
        mask_uv = (
            self._mask_uv(nodes, links, data, (-2000, 400), defaults)
            if texture("MaskTexture") or texture("GlassTint")
            else None
        )

        mask = self._tiled_texture(
            nodes,
            links,
            data,
            "MaskTexture",
            (-1200, 500),
            tile_offset=_IDENTITY_TILE,
            non_color=False,
            defaults=defaults,
            aliases=aliases,
            uv_source=mask_uv,
        )
        glass_tint = self._tiled_texture(
            nodes,
            links,
            data,
            "GlassTint",
            (-1200, 200),
            tile_offset=vector("GlassTintTileAndOffset"),
            non_color=False,
            defaults=defaults,
            aliases=aliases,
            uv_source=mask_uv,
        )
        roughness_texture = self._tiled_texture(
            nodes,
            links,
            data,
            "Roughness",
            (-1200, -100),
            tile_offset=vector("RoughnessTileAndOffset"),
            non_color=True,
            defaults=defaults,
            aliases=aliases,
        )
        normal_texture = self._tiled_texture(
            nodes,
            links,
            data,
            "Normal",
            (-1200, -450),
            tile_offset=vector("NormalTileAndOffset"),
            non_color=True,
            defaults=defaults,
            aliases=aliases,
        )

        mapped_normal, lighting_normal = self._normal_sockets(
            nodes, links, data, normal_texture, scalar, Mat
        )

        tint_color = param_color(
            data,
            aliases.get("TintColor", "TintColor"),
            defaults.get("TintColor", _UNIT),
        )
        fresnel_bias = scalar("FresnelBias")
        if glass_tint is not None:
            refraction_tint = mix_color_socket(
                nodes,
                links,
                "GlassTint x TintColor",
                glass_tint.outputs["Color"],
                tint_color,
                1.0,
                (-900, 200),
                blend_type="MULTIPLY",
                clamp=False,
            )
        else:
            refraction_tint = None

        tinted = refraction_tint if refraction_tint is not None else tint_color
        tint_from_vertex = clamp01(scalar("TintFromVertexPaint"))
        if tint_from_vertex > 0.0:
            vertex = new_labeled_node(
                nodes, "ShaderNodeVertexColor", "Glass Vertex Tint", (-900, 360)
            )
            vertex_tint = mix_color_socket(
                nodes,
                links,
                "TintFromVertexPaint",
                _UNIT,
                vertex.outputs["Color"],
                tint_from_vertex,
                (-700, 360),
            )
            tinted = mix_color_socket(
                nodes,
                links,
                "Refraction Tint x Vertex Color",
                tinted,
                vertex_tint,
                1.0,
                (-520, 300),
                blend_type="MULTIPLY",
                clamp=False,
            )
        edge_weight = self._glass_tint_fresnel(
            nodes, links, mapped_normal, fresnel_bias, (-900, -20)
        )
        refraction_tint = self._glass_tint_background(
            nodes, links, tinted, edge_weight, (-520, 160)
        )

        mask_opacity = clamp01(scalar("MaskOpacity"))
        if mask is not None and mask_opacity > 0.0:
            diffuse_opacity = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                mask.outputs["Alpha"],
                mask_opacity,
                name="diffuseOpacity",
                location=(-900, 500),
                use_clamp=True,
            )
        else:
            diffuse_opacity = value_socket(nodes, "diffuseOpacity", 0.0, (-900, 500))

        if frosted:
            # Combine mask and surface opacity with clamping.
            diffuse_opacity = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY_ADD",
                diffuse_opacity,
                param_float(data, "MaskAddSurface", 1.0),
                name="MaskAddSurface",
                location=(-720, 500),
                use_clamp=True,
            )
            shader_nodes.socket_by_identifier(
                diffuse_opacity.node.inputs, "Value_002"
            ).default_value = clamp01(param_float(data, "SurfaceOpacity", 0.0))

        # Use the roughness texture red channel rather than luminance.
        if roughness_texture is not None:
            split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Roughness.r", (-900, -160)
            )
            split.mode = "RGB"
            links.new(
                roughness_texture.outputs["Color"],
                split.inputs["Color"],
            )
            sampled_roughness = split.outputs["Red"]
        else:
            sampled_roughness = value_socket(nodes, "Roughness", 0.0, (-900, -160))

        # Both lobes are built and mixed, fed from one roughness sample with separate biases.
        glass_roughness = shader_nodes.math(
            nodes,
            links,
            "ADD",
            sampled_roughness,
            clamp_scalar(scalar("GlassRoughnessBias"), -1.0, 1.0),
            name="Glass Roughness",
            location=(-380, -60),
            use_clamp=True,
        )
        surface_roughness = shader_nodes.math(
            nodes,
            links,
            "ADD",
            sampled_roughness,
            clamp_scalar(scalar("MaskRoughnessBias"), -1.0, 1.0),
            name="Surface Roughness",
            location=(-380, -180),
            use_clamp=True,
        )

        glass_f0 = lerp_three(
            _MIRROR_GLASS_F0 if _is_mirror_glass(template) else _GLASS_F0, fresnel_bias
        )
        specular_color = param_color(
            data, "GlassSpecularColor", defaults.get("GlassSpecularColor", _UNIT)
        )
        face_geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Face Orientation", (-360, 780)
        )
        backfacing_socket = face_geometry.outputs["Backfacing"]
        front_reflection = max(0.0, scalar("FrontFacesReflectionPower"))
        back_reflection = max(0.0, scalar("BackFacesReflectionPower"))
        reflection_select = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            name="Front/Back Reflection Power",
            location=(-120, 760),
        ).node
        links.new(backfacing_socket, reflection_select.inputs["Value"])
        shader_nodes.socket_by_identifier(
            reflection_select.inputs, "Value_001"
        ).default_value = back_reflection - front_reflection
        shader_nodes.socket_by_identifier(
            reflection_select.inputs, "Value_002"
        ).default_value = front_reflection
        specular_level = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            reflection_select.outputs["Value"],
            0.5,
            name="Glass Specular IOR Level",
            location=(80, 720),
            use_clamp=True,
        )

        # Represent the pure-specular background lobe as dielectric transmission; a
        # metallic Principled lobe would discard transmission and behave as a conductor.
        glass_bsdf = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Glass Lobe", (100, 260)
        )
        for name, value in (
            ("Base Color", refraction_tint),
            ("Roughness", glass_roughness),
            ("Specular IOR Level", specular_level),
            ("Metallic", 0.0),
            ("Transmission Weight", 1.0),
            ("IOR", _ior_from_f0(glass_f0)),
            ("Specular Tint", specular_color),
        ):
            socket = find_input(glass_bsdf, name)
            if socket is not None:
                assign_socket(links, value, socket)

        # Tint the non-glass mask layer by the glass color on backfaces.
        if mask is not None:
            mask_color = mask.outputs["Color"]
            if self._uses_surface_tint(template):
                tint_surface = param_color(
                    data, "TintSurface", defaults.get("TintSurface", _UNIT)
                )
                mask_color = mix_color_socket(
                    nodes,
                    links,
                    "Vehicle Mask x TintSurface"
                    if _is_vehicle_glass(template)
                    else "Mask x TintSurface",
                    mask_color,
                    tint_surface,
                    1.0,
                    (-280, 620),
                    blend_type="MULTIPLY",
                    clamp=False,
                )
            tinted_mask = mix_color_socket(
                nodes,
                links,
                "Backface Mask Tint",
                mask_color,
                refraction_tint,
                1.0,
                (-100, 560),
                blend_type="MULTIPLY",
                clamp=False,
            )
            surface_base = mix_color_socket(
                nodes,
                links,
                "Surface Base Color",
                mask_color,
                tinted_mask,
                backfacing_socket,
                (100, 560),
            )
        else:
            surface_base = refraction_tint

        surface_bsdf = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Surface Lobe", (100, -120)
        )
        for name, value in (
            ("Base Color", surface_base),
            ("Roughness", surface_roughness),
            ("Metallic", clamp01(scalar("SurfaceMetalness"))),
            ("Transmission Weight", 0.0),
            ("IOR", _ior_from_f0(glass_f0)),
        ):
            socket = find_input(surface_bsdf, name)
            if socket is not None:
                assign_socket(links, value, socket)

        if lighting_normal is not None:
            for node in (glass_bsdf, surface_bsdf):
                socket = find_input(node, "Normal")
                if socket is not None:
                    links.new(lighting_normal, socket)

        lobe_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Glass and Surface Lobe Blend", (420, 60)
        )
        links.new(diffuse_opacity, lobe_mix.inputs["Factor"])
        links.new(glass_bsdf.outputs["BSDF"], lobe_mix.inputs["Shader"])
        links.new(
            surface_bsdf.outputs["BSDF"],
            shader_nodes.socket_by_identifier(lobe_mix.inputs, "Shader_001"),
        )

        # Front and back opacity are evaluated independently.
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Background", (420, -220)
        )
        opacity_front = clamp01(scalar("Opacity"))
        opacity_back = clamp01(scalar("OpacityBackFace"))
        opacity_select = shader_nodes.math(
            nodes, links, "MULTIPLY_ADD", name="Front/Back Opacity", location=(420, -60)
        ).node
        links.new(backfacing_socket, opacity_select.inputs["Value"])
        shader_nodes.socket_by_identifier(
            opacity_select.inputs, "Value_001"
        ).default_value = opacity_back - opacity_front
        shader_nodes.socket_by_identifier(
            opacity_select.inputs, "Value_002"
        ).default_value = opacity_front
        one_minus_opacity = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            opacity_select.outputs["Value"],
            name="One Minus Glass Opacity",
            location=(600, -100),
        )
        final_opacity = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            diffuse_opacity,
            one_minus_opacity,
            opacity_select.outputs["Value"],
            name="Final Glass Opacity",
            location=(960, -100),
            use_clamp=True,
        )
        opacity_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Glass Opacity", (1140, 0)
        )
        links.new(final_opacity, opacity_mix.inputs["Factor"])
        links.new(transparent.outputs["BSDF"], opacity_mix.inputs["Shader"])
        links.new(
            lobe_mix.outputs["Shader"],
            shader_nodes.socket_by_identifier(opacity_mix.inputs, "Shader_001"),
        )
        links.new(opacity_mix.outputs["Shader"], output.inputs["Surface"])

        set_transparent(Mat)
        renders_backfaces = opacity_back >= 0.001
        Mat.use_backface_culling = not renders_backfaces
        Mat.use_transparency_overlap = renders_backfaces
        Mat.use_raytrace_refraction = True
        Mat.diffuse_color = (*tint_color[:3], opacity_front)
>>>>>>> Stashed changes
