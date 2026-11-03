<<<<<<< Updated upstream
from ..materials.blender.images import image_has_alpha
from ..materials.blender.nodes import CreateCalculateVecNormalZ, CreateCullBackfaceGroup, CreateGradMapRamp, CreateShaderNodeRGB, CreateShaderNodeValue, bsdf_socket_names, create_node, loc

from .mat_common import MaterialTypeBase, create_global_normal_rel


class MetalBase(MaterialTypeBase):
    def __init__(self, BasePath, image_format, ProjPath, enableMask):
        super().__init__(BasePath, image_format, ProjPath)
        self.enableMask = enableMask

    def _create_layer_tile_mapping(self, CurMat, Data):
        if "LayerTile" not in Data:
            return None

        texCoord = CurMat.nodes.new("ShaderNodeTexCoord")
        texCoord.location = (-2200, 400)
        texCoord.hide = True

        mappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mappingNode.location = (-2000, 400)
        mappingNode.label = "LayerTile"
        mappingNode.hide = True

        tileValue = Data["LayerTile"]
        if tileValue <= 0:
            tileValue = 1.0
        mappingNode.inputs[3].default_value = (tileValue, tileValue, 1.0)
        CurMat.links.new(texCoord.outputs[2], mappingNode.inputs[0])
        return mappingNode

    def _create_detail_mapping(self, CurMat, Data):
        texCoord = CurMat.nodes.new("ShaderNodeTexCoord")
        texCoord.location = (-2300, 0)

        mappingNode = CurMat.nodes.new("ShaderNodeMapping")
        mappingNode.location = (-2100, 0)
        if "DetailU" in Data and "DetailV" in Data:
            mappingNode.inputs[3].default_value = (Data["DetailU"], Data["DetailV"], 0)
        CurMat.links.new(texCoord.outputs[2], mappingNode.inputs[0])
        return mappingNode

    def _create_image_node(self, CurMat, Data, key, loc, label=None, is_normal=False):
        if key not in Data:
            return None, None
        image = self._image_from_rel_path(Data[key], is_normal=is_normal)
        node = create_node(CurMat.nodes, "ShaderNodeTexImage", loc, label=label or key, image=image)
        return node, image

    def _create_pbr_channel(self, Data, CurMat, channel_name, bsdf_input, layerTileMapping, y_loc):
        node, _ = self._create_image_node(CurMat, Data, channel_name, (-1400, y_loc), is_normal=True)
        if node is None:
            return None

        if layerTileMapping:
            CurMat.links.new(layerTileMapping.outputs[0], node.inputs[0])

        math_node = create_node(CurMat.nodes, "ShaderNodeMath", (-1050, y_loc), operation='MULTIPLY_ADD')
        math_node.inputs[1].default_value = 1
        math_node.inputs[2].default_value = 0

        scale_key = f"{channel_name}Scale"
        bias_key = f"{channel_name}Bias"
        if scale_key in Data:
            scale = CreateShaderNodeValue(CurMat, Data[scale_key], -1400, y_loc - 50, scale_key)
            CurMat.links.new(scale.outputs[0], math_node.inputs[1])
        if bias_key in Data:
            bias = CreateShaderNodeValue(CurMat, Data[bias_key], -1400, y_loc - 100, bias_key)
            CurMat.links.new(bias.outputs[0], math_node.inputs[2])

        CurMat.links.new(node.outputs[0], math_node.inputs[0])
        CurMat.links.new(math_node.outputs[0], bsdf_input)
        return math_node

    def _create_normal_nodes(self, CurMat, Data, pBSDF, layerTileMapping, detailMapping):
        if "Normal" not in Data:
            return None

        nMap = create_global_normal_rel(
                CurMat, Data["Normal"], -1000, -200, 'Normal', self.image_format, self.BasePath, self.ProjPath,
                )
        if layerTileMapping:
            try:
                CurMat.links.new(layerTileMapping.outputs[0], nMap.inputs[0])
            except Exception:
                pass

        normalVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
        normalVectorize.operation = 'MULTIPLY_ADD'
        normalVectorize.location = (-1050, -200)
        normalVectorize.hide = True
        normalVectorize.inputs[1].default_value = 2, 2, 0
        normalVectorize.inputs[2].default_value = -1, -1, 0

        normalCreateVecZGroup = CreateCalculateVecNormalZ(CurMat, -800, -350)
        normalMap = create_node(CurMat.nodes, "ShaderNodeNormalMap", (-500, -350))

        CurMat.links.new(nMap.outputs[0], normalVectorize.inputs[0])

        detail_normal = None
        if "DetailNormal" in Data:
            dNNode = create_global_normal_rel(
                    CurMat, Data["DetailNormal"], -1000, -500, 'Normal', self.image_format, self.BasePath,
                    self.ProjPath,
                    )
            if detailMapping:
                CurMat.links.new(detailMapping.outputs[0], dNNode.inputs[0])

            normalDetVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
            normalDetVectorize.operation = 'MULTIPLY_ADD'
            normalDetVectorize.location = (-1050, -500)
            normalDetVectorize.hide = True
            normalDetVectorize.inputs[1].default_value = 2, 2, 0
            normalDetVectorize.inputs[2].default_value = -1, -1, 0

            normalAdd = create_node(CurMat.nodes, "ShaderNodeVectorMath", (-1050, -350), operation='ADD')
            CurMat.links.new(dNNode.outputs[0], normalDetVectorize.inputs[0])
            CurMat.links.new(normalVectorize.outputs[0], normalAdd.inputs[0])
            CurMat.links.new(normalDetVectorize.outputs[0], normalAdd.inputs[1])
            CurMat.links.new(normalAdd.outputs[0], normalCreateVecZGroup.inputs[0])
            detail_normal = dNNode
        else:
            CurMat.links.new(normalVectorize.outputs[0], normalCreateVecZGroup.inputs[0])

        CurMat.links.new(normalCreateVecZGroup.outputs[0], normalMap.inputs[1])
        CurMat.links.new(normalMap.outputs[0], pBSDF.inputs['Normal'])
        return detail_normal

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        has_detail = all(key in Data for key in ("BaseColor", "DetailColor", "Normal", "DetailNormal"))

        layerTileMapping = self._create_layer_tile_mapping(CurMat, Data)
        detailMapping = self._create_detail_mapping(CurMat, Data) if has_detail else None

        mixRGB = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-800, 500), blend_type='MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0], pBSDF.inputs['Base Color'])

        bColNode = None
        bcolImg = None
        if "BaseColor" in Data:
            bColNode, bcolImg = self._create_image_node(CurMat, Data, "BaseColor", (-1400, 650))
            if layerTileMapping:
                CurMat.links.new(layerTileMapping.outputs[0], bColNode.inputs[0])

        dColNode = None
        if "DetailColor" in Data:
            dColNode, _ = self._create_image_node(CurMat, Data, "DetailColor", (-1400, 950))
            if detailMapping:
                CurMat.links.new(detailMapping.outputs[0], dColNode.inputs[0])

        if bColNode is not None and dColNode is not None and has_detail:
            dColmul = create_node(CurMat.nodes, "ShaderNodeMixRGB", (-800, 650), blend_type='MULTIPLY')
            dColmul.inputs[0].default_value = 1
            CurMat.links.new(dColNode.outputs[0], dColmul.inputs[1])
            CurMat.links.new(bColNode.outputs[0], dColmul.inputs[2])
            CurMat.links.new(dColmul.outputs[0], mixRGB.inputs[1])
        elif bColNode is not None:
            CurMat.links.new(bColNode.outputs[0], mixRGB.inputs[1])

        self._create_pbr_channel(Data, CurMat, "Metalness", pBSDF.inputs['Metallic'], layerTileMapping, 250)
        self._create_pbr_channel(Data, CurMat, "Roughness", pBSDF.inputs['Roughness'], layerTileMapping, 50)

        dNNode = self._create_normal_nodes(CurMat, Data, pBSDF, layerTileMapping, detailMapping)

        if "BaseColorScale" in Data:
            dColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"], -1400, 500, 'BaseColorScale', True)
            baseColorGamma = CurMat.nodes.new("ShaderNodeGamma")
            baseColorGamma.location = (-1050, 500)
            baseColorGamma.inputs[1].default_value = 2.2
            baseColorGamma.hide = True
            CurMat.links.new(dColScale.outputs[0], baseColorGamma.inputs[0])
            CurMat.links.new(baseColorGamma.outputs[0], mixRGB.inputs[2])

        if 'GradientMap' in Data:
            gradImg = self._image_from_rel_path(Data["GradientMap"])
            grad_image_node = create_node(
                CurMat.nodes, "ShaderNodeTexImage", (-800, 0), label="GradientMap", image=gradImg
                )
            color_ramp_node = CreateGradMapRamp(CurMat, grad_image_node)
            CurMat.links.new(mixRGB.outputs[0], color_ramp_node.inputs[0])
            CurMat.links.new(color_ramp_node.outputs[0], pBSDF.inputs['Base Color'])

        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat, Data["AlphaThreshold"], -1400, 400, "AlphaThreshold")
        else:
            aThreshold = CreateShaderNodeValue(CurMat, 1.0, -1400, 400, "AlphaThreshold")

        maskThreshold = create_node(CurMat.nodes, "ShaderNodeMath", (-1050, 400), operation='GREATER_THAN')
        if bColNode is not None:
            if dColNode is not None and has_detail:
                alphaMultiply = create_node(CurMat.nodes, "ShaderNodeMath", (-1050, 800), operation='MULTIPLY')
                CurMat.links.new(dColNode.outputs[1], alphaMultiply.inputs[0])
                CurMat.links.new(bColNode.outputs[1], alphaMultiply.inputs[1])
                CurMat.links.new(alphaMultiply.outputs[0], maskThreshold.inputs[0])
            else:
                CurMat.links.new(bColNode.outputs[1], maskThreshold.inputs[0])
        CurMat.links.new(aThreshold.outputs[0], maskThreshold.inputs[1])

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450, -450)
        mulNode.hide = True

        if "Emissive" in Data:
            emImg = self._image_from_rel_path(Data["Emissive"])
            emTexNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-800, -500), label="Emissive", image=emImg)
            if layerTileMapping:
                CurMat.links.new(layerTileMapping.outputs[0], emTexNode.inputs[0])
            CurMat.links.new(emTexNode.outputs[0], mulNode.inputs[2])

        if "EmissiveColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["EmissiveColor"], -700, -450, "EmissiveColor")
            CurMat.links.new(emColor.outputs[0], mulNode.inputs[1])

        CurMat.links.new(mulNode.outputs[0], pBSDF.inputs[sockets['Emission']])

        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value = Data["EmissiveEV"]

        enableMask = create_node(CurMat.nodes, "ShaderNodeValue", (-800, -150), label="EnableMask")
        enableMask.outputs[0].default_value = int(self.enableMask)

        mathSubtract = create_node(CurMat.nodes, "ShaderNodeMath", (-800, -100), operation='SUBTRACT', label="Math")
        mathSubtract.inputs[0].default_value = 1

        enableMaskClamp = create_node(CurMat.nodes, "ShaderNodeClamp", (-800, -50))
        backfaceGroup = CreateCullBackfaceGroup(CurMat, x=-500, y=-50, name='Cull Backface')

        CurMat.links.new(enableMask.outputs['Value'], mathSubtract.inputs[1])
        CurMat.links.new(mathSubtract.outputs['Value'], enableMaskClamp.inputs[1])
        if bColNode is not None and bcolImg is not None and not image_has_alpha(bcolImg):
            CurMat.links.new(bColNode.outputs['Color'], enableMaskClamp.inputs['Value'])
        else:
            CurMat.links.new(maskThreshold.outputs[0], enableMaskClamp.inputs[0])
        CurMat.links.new(enableMaskClamp.outputs[0], backfaceGroup.inputs[0])
        CurMat.links.new(backfaceGroup.outputs[0], pBSDF.inputs['Alpha'])


used_params = [
    'BaseColor',
    'BaseColorScale',
    'Metalness',
    'Roughness',
    'Normal',
    'AlphaThreshold',
    'MetalnessScale',
    'MetalnessBias',
    'RoughnessScale',
    'RoughnessBias',
    'NormalStrength',
    'Emissive',
    'EmissiveLift',
    'EmissiveEV',
    'EmissiveEVRaytracingBias',
    'EmissiveDirectionality',
    'EnableRaytracedEmissive',
    'EmissiveColor',
    'LayerTile',
    'VehicleDamageInfluence',
    ]
=======
from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bundles import scalar_lerp_socket
from .mat_common import param_float
from .metalbase_common import (
    COLUMN_ADJUST,
    COLUMN_COMBINE,
    COLUMN_TEXTURE,
    MetalBaseCore,
    uv_panning_offset,
)


class MetalBase(MetalBaseCore):
    """Shared graph for plain/detail MetalBase raster behavior"""

    suppress_emissive = False
    clamp_base_color = True
    clamp_pbr = True
    dithered_alpha = False
    alpha_threshold_default = 0.379999995
    detail_u_default = 10.0
    detail_v_default = 5.0

    def _detail_uv(self, CurMat, data):
        if not (
            self._texture_path(data, "DetailColor")
            or self._texture_path(data, "DetailNormal")
        ):
            return None
        u = param_float(data, "DetailU", self.detail_u_default)
        v = param_float(data, "DetailV", self.detail_v_default)
        return self._uv_scale_offset(
            CurMat, (u, v), (0.0, 0.0), (-2100, 60), "Detail UV"
        ).outputs["Vector"]

    def _source_uv(self, CurMat, data):
        offset = uv_panning_offset(self, CurMat, data, (-2100, 200))
        if offset is None:
            return None
        coord = create_node(
            CurMat.nodes, "ShaderNodeTexCoord", (-2300, 400), label="Source UV"
        )
        panned = shader_nodes.vector_math(
            CurMat.nodes,
            CurMat.links,
            "ADD",
            label="UV + Panning",
            location=(-2100, 400),
            hide=True,
        ).node
        CurMat.links.new(coord.outputs["UV"], panned.inputs["Vector"])
        CurMat.links.new(
            offset, shader_nodes.socket_by_identifier(panned.inputs, "Vector_001")
        )
        return panned.outputs["Vector"]

    def _surface_uv(self, CurMat, data, source_uv=None):
        tile = param_float(data, "LayerTile", self.layer_tile_default)
        if source_uv is None:
            return self._uv_source(CurMat, data)
        if abs(tile - 1.0) <= 1.0e-6:
            return source_uv
        scaled = shader_nodes.vector_math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="Source UV x LayerTile",
            location=(-1900, 400),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(scaled.inputs, "Vector_001").default_value = (
            tile,
            tile,
            1.0,
        )
        CurMat.links.new(source_uv, scaled.inputs["Vector"])
        return scaled.outputs["Vector"]

    def _base_and_detail(self, CurMat, data, uv, detail_uv):
        base = self._texture(CurMat, data, "BaseColor", (COLUMN_TEXTURE, 640), uv)
        surface, scale = self._scaled_base_color(
            CurMat, data, base, clamp=self.clamp_base_color
        )

        detail = self._texture(
            CurMat, data, "DetailColor", (COLUMN_TEXTURE, 940), detail_uv
        )
        if detail is None:
            return base, detail, surface, scale

        detail_scale_socket, _ = self._colour_scale_socket(
            CurMat, data, "BaseColorScale", (COLUMN_TEXTURE, 820)
        )
        detail_scaled = self._mix_color(
            CurMat,
            (COLUMN_COMBINE, 880),
            1.0,
            detail.outputs["Color"],
            detail_scale_socket,
            blend_type="MULTIPLY",
            label="ScaledDetailColor",
        )
        combined = self._mix_color(
            CurMat,
            (COLUMN_COMBINE + 200, 700),
            1.0,
            surface,
            detail_scaled,
            blend_type="MULTIPLY",
            label="Base x Detail",
        )
        return base, detail, combined, scale

    def _fill_blend(
        self, CurMat, data, surface, bsdf, roughness_source, metalness_source
    ):
        """The vertex-colour driven fill layer of the vertex-coloured detail set"""
        fill = self._texture(CurMat, data, "Fill", (COLUMN_TEXTURE, 1180))
        if fill is None:
            return surface

        tiling = param_float(data, "FillTiling", 1.0)
        if abs(tiling - 1.0) > 1.0e-6:
            uv = self._uv_scale_offset(
                CurMat, (tiling, tiling), (0.0, 0.0), (-2100, 1180), "Fill UV"
            )
            CurMat.links.new(uv.outputs["Vector"], fill.inputs["Vector"])

        fill_scale, _ = self._colour_scale_socket(
            CurMat, data, "FillColorScale", (COLUMN_TEXTURE, 1240)
        )
        tint = self._mix_color(
            CurMat,
            (COLUMN_ADJUST, 1180),
            1.0,
            fill.outputs["Color"],
            fill_scale,
            blend_type="MULTIPLY",
            label="FillColorScale",
        )

        attribute = create_node(
            CurMat.nodes,
            "ShaderNodeVertexColor",
            (COLUMN_TEXTURE, 1080),
            label="Vertex Colour",
        )
        channels = create_node(
            CurMat.nodes,
            "ShaderNodeSeparateColor",
            (COLUMN_ADJUST, 1080),
            label="VertexColor.r",
        )
        CurMat.links.new(attribute.outputs["Color"], channels.inputs["Color"])
        weight = create_node(
            CurMat.nodes,
            "ShaderNodeClamp",
            (COLUMN_ADJUST + 160, 1080),
            label="Fill Weight",
        )
        CurMat.links.new(channels.outputs["Red"], weight.inputs["Value"])

        blended = self._mix_color(
            CurMat,
            (COLUMN_COMBINE + 200, 1120),
            weight.outputs["Result"],
            tint,
            surface,
            label="Fill Blend",
        )

        for target, source, toward, y, label in (
            (bsdf.inputs["Roughness"], roughness_source, 1.0, 1000, "Fill Roughness"),
            (bsdf.inputs["Metallic"], metalness_source, 0.0, 940, "Fill Metalness"),
        ):
            current = source if source is not None else target.default_value
            CurMat.links.new(
                scalar_lerp_socket(
                    CurMat,
                    current,
                    toward,
                    weight.outputs["Result"],
                    (COLUMN_COMBINE, y),
                    label,
                ),
                target,
            )
        return blended

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        CurMat = Mat.node_tree
        bsdf, sockets = self._bsdf(CurMat)

        source_uv = self._source_uv(CurMat, data)
        uv = self._surface_uv(CurMat, data, source_uv)
        detail_uv = self._detail_uv(CurMat, data)

        base, detail, surface, base_scale = self._base_and_detail(
            CurMat, data, uv, detail_uv
        )

        if self._texture_path(data, "RoughMetal"):
            roughness_source, metalness_source = self._packed_pbr(
                CurMat,
                data,
                "RoughMetal",
                uv,
                bsdf.inputs["Roughness"],
                bsdf.inputs["Metallic"],
                180,
                clamp=self.clamp_pbr,
            )
        else:
            metalness_source = self._pbr_channel(
                CurMat,
                data,
                "Metalness",
                bsdf.inputs["Metallic"],
                uv,
                260,
                clamp=self.clamp_pbr,
            )
            roughness_source = self._pbr_channel(
                CurMat,
                data,
                "Roughness",
                bsdf.inputs["Roughness"],
                uv,
                80,
                clamp=self.clamp_pbr,
            )

        self._normal(CurMat, data, bsdf, uv, detail_uv=detail_uv)

        if self._texture_path(data, "Fill"):
            surface = self._fill_blend(
                CurMat, data, surface, bsdf, roughness_source, metalness_source
            )

        if not self.suppress_emissive:
            base_socket = base.outputs["Color"] if base is not None else surface
            surface = self._emissive_block(
                CurMat, data, bsdf, sockets, surface, base_socket, uv=source_uv
            )
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0

        CurMat.links.new(surface, bsdf.inputs["Base Color"])

        detail_alpha = detail.outputs["Alpha"] if detail is not None else None
        alpha = self._multiplied_alpha(
            CurMat,
            (
                base.outputs["Alpha"] if base is not None else None,
                detail_alpha,
            ),
            base_scale[3] if detail is not None else None,
            (COLUMN_ADJUST, 760),
            "Alpha",
        )
        direct_base_alpha = detail is None and alpha is not None
        self._alpha_mask(
            CurMat,
            data,
            bsdf,
            alpha,
            base.image if direct_base_alpha and base is not None else None,
        )
        if self.dithered_alpha:
            Mat.surface_render_method = "DITHERED"
        return {"surface": surface, "base_texture": base}


class MetalBaseAnimatedUV(MetalBase):
    texture_defaults = {
        **MetalBase.texture_defaults,
        "BaseColor": r"engine\textures\editor\checker_d.xbm",
    }
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (0.0, 0.0, 0.0, 0.0),
    }
    uv_panning_speed_y_default = 0.200000003


class MetalBaseDithered(MetalBase):
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
    }
    dithered_alpha = True
    alpha_threshold_default = 0.0500000007


class MetalBaseDetail(MetalBase):
    normal_strength_param = None
    texture_defaults = {
        **MetalBase.texture_defaults,
        "BaseColor": r"engine\textures\editor\checker_h.xbm",
        "Metalness": r"test\level_design\ld_kit\textures\ruler_checker_5m_road.xbm",
        "Roughness": r"test\level_design\ld_kit\textures\ruler_checker_1m_wall.xbm",
        "Normal": r"engine\textures\editor\checker_n.xbm",
        "DetailColor": r"engine\textures\editor\white.xbm",
        "DetailNormal": r"engine\textures\editor\checker_n.xbm",
    }
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
    }
    suppress_emissive = True
    metalness_bias_default = 0.980000019
    clamp_base_color = False
    clamp_pbr = False
    alpha_threshold_default = 0.300000012


class MetalBaseDetailVC(MetalBase):
    """Untiled base PBR plus vertex-color fill"""

    normal_strength_param = None
    suppress_emissive = True
    clamp_base_color = False
    clamp_pbr = False
    alpha_threshold_default = 0.300000012


class MetalBaseDetailDithered(MetalBaseDetail):
    dithered_alpha = True


class MetalBaseAlphaAnimated(MetalBaseDetailDithered):
    texture_defaults = {
        **MetalBaseDetail.texture_defaults,
        "BaseColor": r"engine\textures\editor\grey.xbm",
        "Metalness": r"engine\textures\editor\white.xbm",
        "Roughness": r"engine\textures\editor\grey.xbm",
        "Normal": r"engine\textures\editor\normal.xbm",
        "DetailColor": r"base\surfaces\masks\alpha_normals\grates\grate_05_d.xbm",
        "DetailNormal": r"base\surfaces\masks\alpha_normals\grates\grate_05_n.xbm",
    }
    roughness_bias_default = 0.371794999
    alpha_threshold_default = 0.800000012
    detail_u_default = 40.0
    detail_v_default = 40.0


class MetalBaseFence(MetalBase):
    normal_strength_param = None
    emissive_lift_param = None
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
    }
    clamp_base_color = False
    clamp_pbr = False
    alpha_threshold_default = 0.5


class MetalBasePacked(MetalBase):
    normal_strength_param = None
    emissive_lift_param = None
    texture_defaults = {
        **MetalBase.texture_defaults,
        "RoughMetal": r"engine\textures\editor\roughmetal.xbm",
    }
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
    }
    clamp_base_color = False
    clamp_pbr = False
    alpha_threshold_default = 0.300000012
>>>>>>> Stashed changes
