from ..assetio.paths import backslash_depot_key
from ..blender import shader_nodes
from ..materials.blender.images import image_is_placeholder, ui_default_render_image
from ..materials.blender.nodes import bsdf_socket_names, create_node
from .bundles import emissive_scale_bundle
from .graph import cp77_bitangent_socket, cp77_uv_tangent_node, mix_scalar_socket
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    param_color,
    param_float,
    param_vector,
)

LAYER_COUNT = 4
_UI_TEXTURE_DEFAULTS = {
    "ScanlineTexture": r"base\fx\_textures\masks\gradients\fx_reflected_vertical_gradient_02_d.xbm",
    "UIRenderTexture": r"engine\ink\textures\4x4_transparent.xbm",
    "DirtTexture": r"base\environment\decoration\alpha_empty.xbm",
}


class MetalBaseUI(MaterialTypeBase):
    texture_defaults = _UI_TEXTURE_DEFAULTS
    scanlines_intensity_default = 0.25

    def __init__(self, BasePath, image_format, ProjPath, render_texture=None):
        super().__init__(BasePath, image_format, ProjPath)
        self.render_texture = render_texture

    def _resolve_render_texture(self, Data):
        if self.render_texture is not None and not image_is_placeholder(
            self.render_texture
        ):
            return self.render_texture

        reference = self._texture_path(Data, "UIRenderTexture")
        normalized = backslash_depot_key(reference)
        if normalized == "engine\\ink\\textures\\4x4_transparent.xbm":
            return ui_default_render_image()

        image = self._image_from_rel_path(reference) if reference else None
        if image is None or image_is_placeholder(image):
            return None
        return image

    def _create_mod_uv(self, CurMat, Data):
        geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-2400, -100))
        tangent = cp77_uv_tangent_node(
            CurMat.nodes, (-2400, -180), label="UI World Tangent"
        )

        binormal = cp77_bitangent_socket(
            CurMat.nodes,
            CurMat.links,
            geometry.outputs["Normal"],
            tangent.outputs["Tangent"],
            (-2200, -180),
            label="UI World Binormal",
        )

        view = shader_nodes.vector_math(
            CurMat.nodes,
            CurMat.links,
            "SCALE",
            label="WorldPosition - CameraPosition",
            location=(-2200, -80),
            hide=True,
        ).node
        view.inputs["Scale"].default_value = -1.0
        CurMat.links.new(geometry.outputs["Incoming"], view.inputs["Vector"])

        left_right = shader_nodes.vector_math(
            CurMat.nodes,
            CurMat.links,
            "DOT_PRODUCT",
            label="leftRightDot",
            location=(-2000, -140),
            hide=True,
        ).node
        CurMat.links.new(view.outputs["Vector"], left_right.inputs["Vector"])
        CurMat.links.new(
            tangent.outputs["Tangent"],
            shader_nodes.socket_by_identifier(left_right.inputs, "Vector_001"),
        )

        top_down = shader_nodes.vector_math(
            CurMat.nodes,
            CurMat.links,
            "DOT_PRODUCT",
            label="topDownDot",
            location=(-2000, -200),
            hide=True,
        ).node
        CurMat.links.new(view.outputs["Vector"], top_down.inputs["Vector"])
        CurMat.links.new(
            binormal, shader_nodes.socket_by_identifier(top_down.inputs, "Vector_001")
        )

        slide = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="FixForVerticalSlide",
            location=(-1820, -200),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            slide.inputs, "Value_001"
        ).default_value = param_float(Data, "FixForVerticalSlide", 1.0)
        CurMat.links.new(top_down.outputs["Value"], slide.inputs["Value"])

        mod_uv = create_node(
            CurMat.nodes, "ShaderNodeCombineXYZ", (-1650, -170), label="modUV"
        )
        CurMat.links.new(left_right.outputs["Value"], mod_uv.inputs["X"])
        CurMat.links.new(slide.outputs["Value"], mod_uv.inputs["Y"])
        return mod_uv

    def _create_base_uv(self, CurMat, Data):
        part_uv = param_vector(Data, "TexturePartUV", (0.0, 0.0, 1.0, 1.0))
        part_size = (part_uv[2] - part_uv[0], part_uv[3] - part_uv[1])
        flip = param_float(Data, "VerticalFlipEnabled", 0.0) >= 0.5

        texCoord = create_node(CurMat.nodes, "ShaderNodeTexCoord", (-2400, 400))
        separate = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-2200, 400))
        CurMat.links.new(texCoord.outputs["UV"], separate.inputs["Vector"])

        invert_v = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "SUBTRACT",
            label="1-v",
            location=(-2050, 360),
            hide=True,
        ).node
        invert_v.inputs["Value"].default_value = 1.0
        CurMat.links.new(
            separate.outputs["Y"],
            shader_nodes.socket_by_identifier(invert_v.inputs, "Value_001"),
        )

        remap_u = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY_ADD",
            label="TexturePartUV.u",
            location=(-1880, 420),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            remap_u.inputs, "Value_001"
        ).default_value = part_size[0]
        shader_nodes.socket_by_identifier(
            remap_u.inputs, "Value_002"
        ).default_value = part_uv[0]
        CurMat.links.new(separate.outputs["X"], remap_u.inputs["Value"])

        remap_v = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY_ADD",
            label="TexturePartUV.v",
            location=(-1880, 360),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(remap_v.inputs, "Value_001").default_value = (
            -part_size[1] if flip else part_size[1]
        )
        shader_nodes.socket_by_identifier(remap_v.inputs, "Value_002").default_value = (
            part_uv[3] if flip else part_uv[1]
        )
        CurMat.links.new(invert_v.outputs["Value"], remap_v.inputs["Value"])

        base_uv = create_node(
            CurMat.nodes, "ShaderNodeCombineXYZ", (-1700, 400), label="newUV"
        )
        CurMat.links.new(remap_u.outputs["Value"], base_uv.inputs["X"])
        CurMat.links.new(remap_v.outputs["Value"], base_uv.inputs["Y"])
        return base_uv, part_size, texCoord

    def _create_scanlines(self, CurMat, Data, texCoord):
        image = self._load_relative_image(
            self._texture_path(Data, "ScanlineTexture"),
            non_color=True,
            error_label="scanline",
        )
        if image is None:
            return None

        density = param_vector(Data, "ScanlinesDensity", (125.0, 125.0, 0.0, 2.0))
        time = create_scene_time_value(CurMat, -2200, 120)
        scroll_u = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-2030, 150), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            scroll_u.inputs, "Value_001"
        ).default_value = density[2]
        CurMat.links.new(time.outputs["Value"], scroll_u.inputs["Value"])
        scroll_v = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="Scanlines Scroll V",
            location=(-2030, 100),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scroll_v.inputs, "Value_001"
        ).default_value = density[3]
        CurMat.links.new(time.outputs["Value"], scroll_v.inputs["Value"])

        scroll = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1880, 130))
        CurMat.links.new(scroll_u.outputs["Value"], scroll.inputs["X"])
        CurMat.links.new(scroll_v.outputs["Value"], scroll.inputs["Y"])

        scaled = shader_nodes.vector_math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="ScanlinesDensity",
            location=(-1880, 200),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(scaled.inputs, "Vector_001").default_value = (
            density[0],
            density[1],
            1.0,
        )
        CurMat.links.new(texCoord.outputs["UV"], scaled.inputs["Vector"])

        offset = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "ADD", location=(-1700, 180), hide=True
        ).node
        CurMat.links.new(scaled.outputs["Vector"], offset.inputs["Vector"])
        CurMat.links.new(
            scroll.outputs["Vector"],
            shader_nodes.socket_by_identifier(offset.inputs, "Vector_001"),
        )

        node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1500, 180),
            label="ScanlineTexture",
            image=image,
        )
        CurMat.links.new(offset.outputs["Vector"], node.inputs["Vector"])

        modulation = create_node(
            CurMat.nodes, "ShaderNodeMapRange", (-1300, 180), label="ScanlinesIntensity"
        )
        modulation.inputs["From Min"].default_value = 0.0
        modulation.inputs["From Max"].default_value = 1.0
        modulation.inputs["To Min"].default_value = param_float(
            Data, "ScanlinesIntensity", self.scanlines_intensity_default
        )
        modulation.inputs["To Max"].default_value = 1.0
        CurMat.links.new(node.outputs["Color"], modulation.inputs["Value"])
        return modulation

    def _create_layers(
        self,
        CurMat,
        Data,
        base_uv,
        mod_uv,
        part_size,
        scanlines,
        image,
        *,
        return_alpha=False,
    ):
        intensity = param_vector(
            Data, "IntensityPerLayer", (1.0, 0.100000001, 0.075000003, 0.0500000007)
        )
        separation = min(
            max(param_float(Data, "LayersSeparation", 0.100000001) * part_size[0], 0.0),
            0.5,
        )
        samples = []
        alpha_samples = []
        for index in range(LAYER_COUNT):
            y = 900 - index * 260
            if index == 0:
                uv_out = base_uv.outputs["Vector"]
            else:
                step = shader_nodes.vector_math(
                    CurMat.nodes,
                    CurMat.links,
                    "SCALE",
                    label=f"layerSeparation x{index}",
                    location=(-1500, y + 60),
                    hide=True,
                ).node
                step.inputs["Scale"].default_value = separation * index
                CurMat.links.new(mod_uv.outputs["Vector"], step.inputs["Vector"])

                offset = shader_nodes.vector_math(
                    CurMat.nodes,
                    CurMat.links,
                    "ADD",
                    location=(-1340, y + 60),
                    hide=True,
                ).node
                CurMat.links.new(base_uv.outputs["Vector"], offset.inputs["Vector"])
                CurMat.links.new(
                    step.outputs["Vector"],
                    shader_nodes.socket_by_identifier(offset.inputs, "Vector_001"),
                )
                uv_out = offset.outputs["Vector"]

            texture = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-1150, y),
                label=f"UIRenderTexture L{index + 1}",
                image=image,
            )
            texture.extension = "REPEAT"
            CurMat.links.new(uv_out, texture.inputs["Vector"])
            sample = texture.outputs["Color"]

            weighted = create_node(
                CurMat.nodes, "ShaderNodeMix", (-900, y), blend_type="MULTIPLY"
            )
            weighted.data_type = "RGBA"
            shader_nodes.socket_by_identifier(
                weighted.inputs, "Factor_Float"
            ).default_value = 1.0
            shader_nodes.socket_by_identifier(
                weighted.inputs, "B_Color"
            ).default_value = (intensity[index],) * 3 + (1.0,)
            CurMat.links.new(
                sample, shader_nodes.socket_by_identifier(weighted.inputs, "A_Color")
            )

            if return_alpha:
                alpha_weight = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "MULTIPLY",
                    label=f"L{index + 1} Alpha Intensity",
                    location=(-900, y - 90),
                    hide=True,
                ).node
                shader_nodes.socket_by_identifier(
                    alpha_weight.inputs, "Value_001"
                ).default_value = intensity[index]
                CurMat.links.new(texture.outputs["Alpha"], alpha_weight.inputs["Value"])
                alpha_sample = alpha_weight.outputs["Value"]

            if index > 0 and scanlines is not None:
                modulated = create_node(
                    CurMat.nodes, "ShaderNodeMix", (-730, y), blend_type="MULTIPLY"
                )
                modulated.data_type = "RGBA"
                shader_nodes.socket_by_identifier(
                    modulated.inputs, "Factor_Float"
                ).default_value = 1.0
                CurMat.links.new(
                    shader_nodes.socket_by_identifier(weighted.outputs, "Result_Color"),
                    shader_nodes.socket_by_identifier(modulated.inputs, "A_Color"),
                )
                CurMat.links.new(
                    scanlines.outputs["Result"],
                    shader_nodes.socket_by_identifier(modulated.inputs, "B_Color"),
                )
                samples.append(
                    shader_nodes.socket_by_identifier(modulated.outputs, "Result_Color")
                )
                if return_alpha:
                    alpha_mod = shader_nodes.math(
                        CurMat.nodes,
                        CurMat.links,
                        "MULTIPLY",
                        label=f"L{index + 1} Alpha Scanline",
                        location=(-730, y - 90),
                        hide=True,
                    ).node
                    CurMat.links.new(alpha_sample, alpha_mod.inputs["Value"])
                    CurMat.links.new(
                        scanlines.outputs["Result"],
                        shader_nodes.socket_by_identifier(
                            alpha_mod.inputs, "Value_001"
                        ),
                    )
                    alpha_samples.append(alpha_mod.outputs["Value"])
            else:
                samples.append(
                    shader_nodes.socket_by_identifier(weighted.outputs, "Result_Color")
                )
                if return_alpha:
                    alpha_samples.append(alpha_sample)

        composite = samples[LAYER_COUNT - 1]
        composite_alpha = alpha_samples[LAYER_COUNT - 1] if return_alpha else None
        for index in range(LAYER_COUNT - 2, -1, -1):
            screen = create_node(
                CurMat.nodes,
                "ShaderNodeMix",
                (-550, 200 + index * 120),
                blend_type="SCREEN",
                label=f"screen L{index + 1}",
            )
            screen.data_type = "RGBA"
            shader_nodes.socket_by_identifier(
                screen.inputs, "Factor_Float"
            ).default_value = 1.0
            CurMat.links.new(
                composite, shader_nodes.socket_by_identifier(screen.inputs, "A_Color")
            )
            CurMat.links.new(
                samples[index],
                shader_nodes.socket_by_identifier(screen.inputs, "B_Color"),
            )
            composite = shader_nodes.socket_by_identifier(
                screen.outputs, "Result_Color"
            )

            if return_alpha:
                one_minus_a = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "SUBTRACT",
                    label=f"1 - Alpha L{index + 2}",
                    location=(-560, -520 - index * 80),
                    hide=True,
                ).node
                one_minus_a.inputs["Value"].default_value = 1.0
                CurMat.links.new(
                    composite_alpha,
                    shader_nodes.socket_by_identifier(one_minus_a.inputs, "Value_001"),
                )
                one_minus_b = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "SUBTRACT",
                    label=f"1 - Alpha L{index + 1}",
                    location=(-400, -520 - index * 80),
                    hide=True,
                ).node
                one_minus_b.inputs["Value"].default_value = 1.0
                CurMat.links.new(
                    alpha_samples[index],
                    shader_nodes.socket_by_identifier(one_minus_b.inputs, "Value_001"),
                )
                product = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "MULTIPLY",
                    label="Screen Alpha Product",
                    location=(-240, -520 - index * 80),
                    hide=True,
                ).node
                CurMat.links.new(one_minus_a.outputs["Value"], product.inputs["Value"])
                CurMat.links.new(
                    one_minus_b.outputs["Value"],
                    shader_nodes.socket_by_identifier(product.inputs, "Value_001"),
                )
                screen_alpha = shader_nodes.math(
                    CurMat.nodes,
                    CurMat.links,
                    "SUBTRACT",
                    label="Screen Alpha",
                    location=(-80, -520 - index * 80),
                    hide=True,
                ).node
                screen_alpha.inputs["Value"].default_value = 1.0
                CurMat.links.new(
                    product.outputs["Value"],
                    shader_nodes.socket_by_identifier(screen_alpha.inputs, "Value_001"),
                )
                composite_alpha = screen_alpha.outputs["Value"]
        return (composite, composite_alpha) if return_alpha else composite

    def _create_dirt_mask(self, CurMat, Data):
        reference = self._texture_path(Data, "DirtTexture")
        normalized = backslash_depot_key(reference)
        if not reference or normalized.endswith(
            "base\\environment\\decoration\\alpha_empty.xbm"
        ):
            return None

        contrast = param_float(Data, "DirtContrast", 1.0)
        dirt_color = param_color(Data, "DirtColor", (1.0, 1.0, 1.0, 1.0))

        image = self._load_relative_image(
            reference,
            non_color=True,
            error_label="dirt",
        )
        if image is None:
            return None
        node = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1500, -500),
            label="DirtTexture",
            image=image,
        )

        scaled = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="DirtContrast",
            location=(-1300, -500),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scaled.inputs, "Value_001"
        ).default_value = contrast
        scaled.use_clamp = True
        CurMat.links.new(node.outputs["Alpha"], scaled.inputs["Value"])

        squared = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-1150, -500), hide=True
        ).node
        CurMat.links.new(node.outputs["Alpha"], squared.inputs["Value"])
        CurMat.links.new(
            scaled.outputs["Value"],
            shader_nodes.socket_by_identifier(squared.inputs, "Value_001"),
        )

        centred = shader_nodes.math(
            CurMat.nodes, CurMat.links, "SUBTRACT", location=(-1000, -500), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            centred.inputs, "Value_001"
        ).default_value = 0.5
        CurMat.links.new(squared.outputs["Value"], centred.inputs["Value"])

        recontrast = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MULTIPLY_ADD", location=(-850, -500), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            recontrast.inputs, "Value_001"
        ).default_value = contrast
        shader_nodes.socket_by_identifier(
            recontrast.inputs, "Value_002"
        ).default_value = 0.5
        recontrast.use_clamp = True
        CurMat.links.new(centred.outputs["Value"], recontrast.inputs["Value"])

        masked = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="DirtColor.w",
            location=(-700, -500),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            masked.inputs, "Value_001"
        ).default_value = dirt_color[3]
        CurMat.links.new(recontrast.outputs["Value"], masked.inputs["Value"])
        return masked

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = shader_nodes.principled_bsdf(CurMat.nodes)
        sockets = bsdf_socket_names()

        image = self._resolve_render_texture(Data)

        base_uv, part_size, texCoord = self._create_base_uv(CurMat, Data)
        mod_uv = self._create_mod_uv(CurMat, Data)
        scanlines = self._create_scanlines(CurMat, Data, texCoord)
        composite = self._create_layers(
            CurMat, Data, base_uv, mod_uv, part_size, scanlines, image
        )

        desaturate = create_node(CurMat.nodes, "ShaderNodeHueSaturation", (-400, 400))
        desaturate.inputs["Saturation"].default_value = 0.96
        CurMat.links.new(composite, desaturate.inputs["Color"])
        composite = desaturate.outputs["Color"]

        tint = param_color(Data, "Tint", (1.0, 1.0, 1.0, 1.0))
        tinted = create_node(
            CurMat.nodes, "ShaderNodeMix", (-250, 400), blend_type="MULTIPLY"
        )
        tinted.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            tinted.inputs, "Factor_Float"
        ).default_value = 1.0
        shader_nodes.socket_by_identifier(tinted.inputs, "B_Color").default_value = (
            tint[:3] + (1.0,)
        )
        CurMat.links.new(
            composite, shader_nodes.socket_by_identifier(tinted.inputs, "A_Color")
        )
        base_color = shader_nodes.socket_by_identifier(tinted.outputs, "Result_Color")

        dirt_mask = self._create_dirt_mask(CurMat, Data)
        emission_intensity = None

        if dirt_mask is not None:
            dirt_color = param_color(Data, "DirtColor", (1.0, 1.0, 1.0, 1.0))
            contrast = param_float(Data, "DirtContrast", 1.0)

            dirt_mix = create_node(
                CurMat.nodes, "ShaderNodeMix", (-100, 400), label="DirtColor"
            )
            dirt_mix.data_type = "RGBA"
            shader_nodes.socket_by_identifier(
                dirt_mix.inputs, "B_Color"
            ).default_value = dirt_color[:3] + (1.0,)
            CurMat.links.new(
                dirt_mask.outputs["Value"],
                shader_nodes.socket_by_identifier(dirt_mix.inputs, "Factor_Float"),
            )
            CurMat.links.new(
                base_color,
                shader_nodes.socket_by_identifier(dirt_mix.inputs, "A_Color"),
            )
            base_color = shader_nodes.socket_by_identifier(
                dirt_mix.outputs, "Result_Color"
            )
            attenuation = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "SUBTRACT",
                label="DirtEmissiveAttenuation",
                location=(-400, -700),
                hide=True,
            ).node
            attenuation.inputs["Value"].default_value = 1.0 + param_float(
                Data, "DirtEmissiveAttenuation", 0.5
            )
            attenuation.use_clamp = True
            CurMat.links.new(
                dirt_mask.outputs["Value"],
                shader_nodes.socket_by_identifier(attenuation.inputs, "Value_001"),
            )

            centred = shader_nodes.math(
                CurMat.nodes, CurMat.links, "SUBTRACT", location=(-250, -700), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                centred.inputs, "Value_001"
            ).default_value = 0.5
            CurMat.links.new(attenuation.outputs["Value"], centred.inputs["Value"])

            emission_intensity = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY_ADD",
                label="emissionIntensity",
                location=(-100, -700),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                emission_intensity.inputs, "Value_001"
            ).default_value = contrast * 1.5
            shader_nodes.socket_by_identifier(
                emission_intensity.inputs, "Value_002"
            ).default_value = 0.5
            emission_intensity.use_clamp = True
            CurMat.links.new(
                centred.outputs["Value"], emission_intensity.inputs["Value"]
            )

            metalness = create_node(
                CurMat.nodes, "ShaderNodeMapRange", (-100, -900), label="Metalness"
            )
            metalness.inputs["To Min"].default_value = param_float(
                Data, "Metalness", 0.9
            )
            metalness.inputs["To Max"].default_value = 0.0
            CurMat.links.new(dirt_mask.outputs["Value"], metalness.inputs["Value"])
            CurMat.links.new(metalness.outputs["Result"], pBSDF.inputs["Metallic"])

            roughness = create_node(
                CurMat.nodes, "ShaderNodeMapRange", (-100, -1050), label="Roughness"
            )
            roughness.inputs["To Min"].default_value = param_float(
                Data, "RoughnessScale", 0.1
            )
            roughness.inputs["To Max"].default_value = param_float(
                Data, "DirtRoughness", 0.564516008
            )
            CurMat.links.new(dirt_mask.outputs["Value"], roughness.inputs["Value"])
            CurMat.links.new(roughness.outputs["Result"], pBSDF.inputs["Roughness"])
        else:
            pBSDF.inputs["Metallic"].default_value = param_float(Data, "Metalness", 0.9)
            pBSDF.inputs["Roughness"].default_value = param_float(
                Data, "RoughnessScale", 0.1
            )

        channels = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (60, 250))
        CurMat.links.new(base_color, channels.inputs["Vector"])
        max_rg = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MAXIMUM", location=(200, 250), hide=True
        ).node
        CurMat.links.new(channels.outputs["X"], max_rg.inputs["Value"])
        CurMat.links.new(
            channels.outputs["Y"],
            shader_nodes.socket_by_identifier(max_rg.inputs, "Value_001"),
        )
        max_rgb = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MAXIMUM",
            label="bright",
            location=(340, 250),
            hide=True,
        ).node
        CurMat.links.new(max_rg.outputs["Value"], max_rgb.inputs["Value"])
        CurMat.links.new(
            channels.outputs["Z"],
            shader_nodes.socket_by_identifier(max_rgb.inputs, "Value_001"),
        )
        forced = param_color(Data, "ForcedTint", (1.0, 1.0, 1.0, 0.0))
        if forced[3] > 0.0:
            forced_scale = create_node(
                CurMat.nodes,
                "ShaderNodeMix",
                (480, 400),
                blend_type="MULTIPLY",
                label="ForcedTint",
            )
            forced_scale.data_type = "RGBA"
            shader_nodes.socket_by_identifier(
                forced_scale.inputs, "Factor_Float"
            ).default_value = 1.0
            shader_nodes.socket_by_identifier(
                forced_scale.inputs, "B_Color"
            ).default_value = forced[:3] + (1.0,)
            CurMat.links.new(
                max_rgb.outputs["Value"],
                shader_nodes.socket_by_identifier(forced_scale.inputs, "A_Color"),
            )

            forced_mix = create_node(CurMat.nodes, "ShaderNodeMix", (640, 400))
            forced_mix.data_type = "RGBA"
            shader_nodes.socket_by_identifier(
                forced_mix.inputs, "Factor_Float"
            ).default_value = forced[3]
            CurMat.links.new(
                base_color,
                shader_nodes.socket_by_identifier(forced_mix.inputs, "A_Color"),
            )
            CurMat.links.new(
                shader_nodes.socket_by_identifier(forced_scale.outputs, "Result_Color"),
                shader_nodes.socket_by_identifier(forced_mix.inputs, "B_Color"),
            )
            base_color = shader_nodes.socket_by_identifier(
                forced_mix.outputs, "Result_Color"
            )
        fix_for_black = param_float(Data, "FixForBlack", 1.0)
        emissive_bright = max_rgb.outputs["Value"]
        if fix_for_black > 0.0:
            doubled = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "MULTIPLY",
                label="FixForBlack",
                location=(480, 250),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                doubled.inputs, "Value_001"
            ).default_value = 2.0
            doubled.use_clamp = True
            CurMat.links.new(max_rgb.outputs["Value"], doubled.inputs["Value"])

            emissive_bright = mix_scalar_socket(
                CurMat.nodes,
                CurMat.links,
                "FixForBlack brightness",
                (640, 250),
                1.0,
                doubled.outputs["Value"],
                min(max(fix_for_black, 0.0), 1.0),
            )

            lift_amount = shader_nodes.math(
                CurMat.nodes, CurMat.links, "SUBTRACT", location=(640, 120), hide=True
            ).node
            lift_amount.inputs["Value"].default_value = 1.0
            CurMat.links.new(
                emissive_bright,
                shader_nodes.socket_by_identifier(lift_amount.inputs, "Value_001"),
            )

            lift_scaled = shader_nodes.math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(800, 120), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                lift_scaled.inputs, "Value_001"
            ).default_value = 0.03 * fix_for_black
            CurMat.links.new(lift_amount.outputs["Value"], lift_scaled.inputs["Value"])

            lift_rgb = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (800, 60))
            for socket in ("X", "Y", "Z"):
                CurMat.links.new(lift_scaled.outputs["Value"], lift_rgb.inputs[socket])

            lift = create_node(
                CurMat.nodes,
                "ShaderNodeMix",
                (960, 250),
                blend_type="ADD",
                label="black lift",
            )
            lift.data_type = "RGBA"
            shader_nodes.socket_by_identifier(
                lift.inputs, "Factor_Float"
            ).default_value = 1.0
            CurMat.links.new(
                base_color, shader_nodes.socket_by_identifier(lift.inputs, "A_Color")
            )
            CurMat.links.new(
                lift_rgb.outputs["Vector"],
                shader_nodes.socket_by_identifier(lift.inputs, "B_Color"),
            )
            base_color = shader_nodes.socket_by_identifier(lift.outputs, "Result_Color")

        emissive_ev = max(0.0, param_float(Data, "EmissiveEV", 6.02741003))
        floor_mix = create_node(
            CurMat.nodes, "ShaderNodeMix", (1120, 400), label="base floor"
        )
        floor_mix.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            floor_mix.inputs, "Factor_Float"
        ).default_value = min(emissive_ev, 1.0)
        shader_nodes.socket_by_identifier(floor_mix.inputs, "A_Color").default_value = (
            0.03,
            0.03,
            0.03,
            1.0,
        )
        CurMat.links.new(
            base_color, shader_nodes.socket_by_identifier(floor_mix.inputs, "B_Color")
        )

        CurMat.links.new(
            shader_nodes.socket_by_identifier(floor_mix.outputs, "Result_Color"),
            pBSDF.inputs["Base Color"],
        )
        CurMat.links.new(base_color, pBSDF.inputs[sockets["Emission"]])

        base_ev = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="EmissiveEV x bright",
            location=(1080, 120),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            base_ev.inputs, "Value_001"
        ).default_value = emissive_ev
        CurMat.links.new(emissive_bright, base_ev.inputs["Value"])

        emission_scale = (
            emission_intensity.outputs["Value"]
            if emission_intensity is not None
            else 1.0
        )
        final_strength = emissive_scale_bundle(
            CurMat,
            emission_scale,
            base_ev.outputs["Value"],
            (1240, 120),
            "Scale Emissive EV",
        ).outputs["Strength"]
        CurMat.links.new(final_strength, pBSDF.inputs["Emission Strength"])
