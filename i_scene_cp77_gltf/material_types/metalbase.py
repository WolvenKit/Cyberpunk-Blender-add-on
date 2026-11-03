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
