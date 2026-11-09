from ..blender import shader_nodes
from ..materials.blender.images import image_has_alpha
from ..materials.blender.nodes import (
    CreateShaderNodeValue,
    bsdf_socket_names,
    create_node,
)
from .emissive_common import ABSENT_COLOR_FALLBACK
from .graph import set_alpha_clip
from .mat_common import (
    MaterialTypeBase,
    create_normal_map_rel,
    param_color,
    param_float,
    param_texture_path,
)
from .metalbase_common import scale_components


class EmissiveControl(MaterialTypeBase):
    def _channel(self, CurMat, data, key, y, scale_key, bias_key, socket):
        path = param_texture_path(data, key)
        if not path:
            return
        image = self._load_relative_image(
            path, non_color=True, error_label="emissive control"
        )
        node = create_node(
            CurMat.nodes, "ShaderNodeTexImage", (-1400, y), label=key, image=image
        )

        scale_bias = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY_ADD",
            label=f"{scale_key} / {bias_key}",
            location=(-1050, y),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scale_bias.inputs, "Value_001"
        ).default_value = param_float(data, scale_key, 0.0)
        shader_nodes.socket_by_identifier(
            scale_bias.inputs, "Value_002"
        ).default_value = param_float(data, bias_key, 0.0)
        CurMat.links.new(node.outputs["Color"], scale_bias.inputs["Value"])
        CurMat.links.new(scale_bias.outputs["Value"], socket)

    def _base_color(self, CurMat, data):
        path = param_texture_path(data, "BaseColor")
        if not path:
            return None
        image = self._load_relative_image(path, error_label="emissive control")
        return create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1400, 600),
            label="BaseColor",
            image=image,
        )

    def _modifier_brightness(self, CurMat, data, modifier):
        """Build modifier arithmetic only for an active emission branch"""

        saturated = create_node(
            CurMat.nodes,
            "ShaderNodeClamp",
            (-1150, -700),
            label="saturate(MaterialParam0.x)",
        )
        saturated.inputs["Min"].default_value = 0.0
        saturated.inputs["Max"].default_value = 1.0
        CurMat.links.new(modifier.outputs["Value"], saturated.inputs["Value"])

        brightness = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="ModulatedEmissiveBrightness",
            location=(-920, -700),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            brightness.inputs, "Value_001"
        ).default_value = max(0.0, param_float(data, "EmissiveEV", 0.0))
        CurMat.links.new(saturated.outputs["Result"], brightness.inputs["Value"])
        return brightness.outputs["Value"]

    def _emissive(
        self, CurMat, data, base_color_node, scaled_color, modifier, pBSDF, sockets
    ):
        """Returns the FinalBaseColor socket, or scaled_color when unused"""
        path = param_texture_path(data, "Emissive")
        if not path:
            return scaled_color, False
        image = self._load_relative_image(
            path, non_color=True, error_label="emissive control"
        )
        if image is None:
            return scaled_color, False

        brightness = self._modifier_brightness(CurMat, data, modifier)
        mask_tex = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-1400, -300),
            label="Emissive",
            image=image,
        )
        channels = create_node(
            CurMat.nodes,
            "ShaderNodeSeparateColor",
            (-1150, -300),
            label="EmissiveMask.r",
        )
        CurMat.links.new(mask_tex.outputs["Color"], channels.inputs["Color"])

        mask = create_node(
            CurMat.nodes,
            "ShaderNodeClamp",
            (-950, -300),
            label="saturate(EmissiveMask)",
        )
        mask.inputs["Min"].default_value = 0.0
        mask.inputs["Max"].default_value = 1.0
        CurMat.links.new(channels.outputs["Red"], mask.inputs["Value"])

        emissive_color = param_color(data, "EmissiveColor", ABSENT_COLOR_FALLBACK)
        tint = create_node(
            CurMat.nodes, "ShaderNodeRGB", (-1150, -450), label="EmissiveColor"
        )
        tint.outputs["Color"].default_value = emissive_color
        tinted = create_node(
            CurMat.nodes,
            "ShaderNodeMix",
            (-800, -450),
            blend_type="MULTIPLY",
            label="BaseColor x EmissiveColor",
        )
        tinted.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            tinted.inputs, "Factor_Float"
        ).default_value = 1.0
        if base_color_node is not None:
            CurMat.links.new(
                base_color_node.outputs["Color"],
                shader_nodes.socket_by_identifier(tinted.inputs, "A_Color"),
            )
        else:
            shader_nodes.socket_by_identifier(
                tinted.inputs, "A_Color"
            ).default_value = ABSENT_COLOR_FALLBACK
        CurMat.links.new(
            tint.outputs["Color"],
            shader_nodes.socket_by_identifier(tinted.inputs, "B_Color"),
        )

        final_color = create_node(
            CurMat.nodes,
            "ShaderNodeMix",
            (-520, 500),
            label="lerp(ScaledBaseColor, Tinted, EmissiveMask)",
        )
        final_color.data_type = "RGBA"
        CurMat.links.new(
            mask.outputs["Result"],
            shader_nodes.socket_by_identifier(final_color.inputs, "Factor_Float"),
        )
        CurMat.links.new(
            scaled_color,
            shader_nodes.socket_by_identifier(final_color.inputs, "A_Color"),
        )
        CurMat.links.new(
            shader_nodes.socket_by_identifier(tinted.outputs, "Result_Color"),
            shader_nodes.socket_by_identifier(final_color.inputs, "B_Color"),
        )

        # Convert EV brightness to linear emission strength.
        # The exponent remains connected so the runtime value is editable.
        exponent = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "POWER",
            label="2^brightness",
            location=(-720, -700),
            hide=True,
        ).node
        exponent.inputs["Value"].default_value = 2.0
        CurMat.links.new(
            brightness, shader_nodes.socket_by_identifier(exponent.inputs, "Value_001")
        )

        linear = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "SUBTRACT",
            label="Scaled Emissive EV",
            location=(-520, -700),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            linear.inputs, "Value_001"
        ).default_value = 1.0
        linear.use_clamp = False
        CurMat.links.new(exponent.outputs["Value"], linear.inputs["Value"])

        strength = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            label="output.EmissiveEV",
            location=(-320, -700),
            hide=True,
        ).node
        CurMat.links.new(mask.outputs["Result"], strength.inputs["Value"])
        CurMat.links.new(
            linear.outputs["Value"],
            shader_nodes.socket_by_identifier(strength.inputs, "Value_001"),
        )

        CurMat.links.new(
            shader_nodes.socket_by_identifier(final_color.outputs, "Result_Color"),
            pBSDF.inputs[sockets["Emission"]],
        )
        CurMat.links.new(strength.outputs["Value"], pBSDF.inputs["Emission Strength"])
        return shader_nodes.socket_by_identifier(
            final_color.outputs, "Result_Color"
        ), True

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        CurMat = Mat.node_tree
        sockets = bsdf_socket_names()
        pBSDF = shader_nodes.principled_bsdf(CurMat.nodes)

        base_color_node = self._base_color(CurMat, data)

        base_scale = scale_components(data, "BaseColorScale", ABSENT_COLOR_FALLBACK)
        scale_node = create_node(
            CurMat.nodes, "ShaderNodeRGB", (-1400, 450), label="BaseColorScale"
        )
        scale_node.outputs["Color"].default_value = base_scale
        scale_socket = scale_node.outputs["Color"]

        scaled = create_node(
            CurMat.nodes,
            "ShaderNodeMix",
            (-800, 600),
            blend_type="MULTIPLY",
            label="ScaledBaseColor",
        )
        scaled.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            scaled.inputs, "Factor_Float"
        ).default_value = 1.0
        if base_color_node is not None:
            CurMat.links.new(
                base_color_node.outputs["Color"],
                shader_nodes.socket_by_identifier(scaled.inputs, "A_Color"),
            )
        else:
            shader_nodes.socket_by_identifier(
                scaled.inputs, "A_Color"
            ).default_value = ABSENT_COLOR_FALLBACK
        CurMat.links.new(
            scale_socket, shader_nodes.socket_by_identifier(scaled.inputs, "B_Color")
        )
        surface_color = shader_nodes.socket_by_identifier(
            scaled.outputs, "Result_Color"
        )

        self._channel(
            CurMat,
            data,
            "Metalness",
            250,
            "MetalnessScale",
            "MetalnessBias",
            pBSDF.inputs["Metallic"],
        )
        self._channel(
            CurMat,
            data,
            "Roughness",
            50,
            "RoughnessScale",
            "RoughnessBias",
            pBSDF.inputs["Roughness"],
        )

        normal_path = param_texture_path(data, "Normal")
        if normal_path:
            nMap = create_normal_map_rel(
                CurMat,
                normal_path,
                -500,
                -150,
                "Normal",
                self.image_format,
                self.BasePath,
                self.ProjPath,
            )
            CurMat.links.new(nMap.outputs["Normal"], pBSDF.inputs["Normal"])

        modifier = CreateShaderNodeValue(
            CurMat, 1.0, -1400, -700, "MaterialParam0 (runtime)"
        )
        modifier.hide = False
        modifier.label = "MaterialParam0"
        emissive_ev = max(0.0, param_float(data, "EmissiveEV", 0.0))
        emissive_active = False
        if emissive_ev > 0.0:
            surface_color, emissive_active = self._emissive(
                CurMat, data, base_color_node, surface_color, modifier, pBSDF, sockets
            )
        if not emissive_active:
            pBSDF.inputs["Emission Strength"].default_value = 0.0

        CurMat.links.new(surface_color, pBSDF.inputs["Base Color"])

        alpha_threshold = param_float(data, "AlphaThreshold", 0.0)
        if base_color_node is not None:
            alpha_mask = shader_nodes.math(
                CurMat.nodes,
                CurMat.links,
                "SUBTRACT",
                label="BaseColor.a - AlphaThreshold",
                location=(-800, 300),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                alpha_mask.inputs, "Value_001"
            ).default_value = alpha_threshold
            alpha_mask.use_clamp = True
            CurMat.links.new(
                base_color_node.outputs["Alpha"], alpha_mask.inputs["Value"]
            )
            CurMat.links.new(alpha_mask.outputs["Value"], pBSDF.inputs["Alpha"])

        base_image = (
            getattr(base_color_node, "image", None) if base_color_node else None
        )
        has_alpha = bool(base_image is not None and image_has_alpha(base_image))
        if has_alpha or alpha_threshold > 0.0:
            set_alpha_clip(Mat, 0.0)

        Mat.diffuse_color = (*base_scale[:3], 1.0)
