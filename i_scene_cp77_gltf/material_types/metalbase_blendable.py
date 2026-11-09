from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .mat_common import param_color, param_float
from .metalbase import MetalBase


class MetalBaseBlendable(MetalBase):
    texture_defaults = {
        **MetalBase.texture_defaults,
        "BaseColor": r"base\materials\placeholder\grey.xbm",
        "Metalness": r"base\materials\placeholder\black.xbm",
        "Roughness": r"base\materials\placeholder\grey.xbm",
        "Normal": r"base\materials\placeholder\normal.xbm",
        "Emissive": r"base\materials\placeholder\black.xbm",
    }
    colour_defaults = {
        **MetalBase.colour_defaults,
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
    }
    alpha_threshold_default = 0.333000004

    def _fade_distance(self, tree, data):
        geometry = create_node(
            tree.nodes, "ShaderNodeNewGeometry", (-520, 820), label="Blendable Geometry"
        )
        camera = create_node(
            tree.nodes, "ShaderNodeCameraData", (-520, 700), label="Blendable Camera"
        )
        object_info = create_node(
            tree.nodes,
            "ShaderNodeObjectInfo",
            (-520, 580),
            label="Blendable Object Pivot",
        )

        camera_offset = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            label="Incoming x View Distance",
            location=(-320, 760),
            hide=True,
        ).node
        tree.links.new(geometry.outputs["Incoming"], camera_offset.inputs["Vector"])
        tree.links.new(camera.outputs["View Distance"], camera_offset.inputs["Scale"])
        camera_position = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Camera World Position",
            location=(-140, 760),
            hide=True,
        ).node
        tree.links.new(geometry.outputs["Position"], camera_position.inputs["Vector"])
        tree.links.new(
            camera_offset.outputs["Vector"],
            shader_nodes.socket_by_identifier(camera_position.inputs, "Vector_001"),
        )

        pivot_delta = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Camera - Object Pivot",
            location=(40, 760),
            hide=True,
        ).node
        tree.links.new(camera_position.outputs["Vector"], pivot_delta.inputs["Vector"])
        tree.links.new(
            object_info.outputs["Location"],
            shader_nodes.socket_by_identifier(pivot_delta.inputs, "Vector_001"),
        )
        split = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (220, 760),
            label="Horizontal Pivot Delta",
        )
        tree.links.new(pivot_delta.outputs["Vector"], split.inputs["Vector"])
        horizontal = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (400, 760),
            label="Horizontal Pivot Distance Vector",
        )
        tree.links.new(split.outputs["X"], horizontal.inputs["X"])
        tree.links.new(split.outputs["Y"], horizontal.inputs["Y"])
        length = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "LENGTH",
            label="Horizontal Pivot Distance",
            location=(580, 760),
            hide=True,
        ).node
        tree.links.new(horizontal.outputs["Vector"], length.inputs["Vector"])

        offset = param_float(data, "FadeOutOffset", 0.200000003)
        distance = max(0.001, param_float(data, "FadeOutDistance", 0.5))
        subtract = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Distance - Fade Offset",
            location=(760, 760),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            subtract.inputs, "Value_001"
        ).default_value = offset
        tree.links.new(length.outputs["Value"], subtract.inputs["Value"])
        divide = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label="Fade Distance Ratio",
            location=(940, 760),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            divide.inputs, "Value_001"
        ).default_value = distance
        tree.links.new(subtract.outputs["Value"], divide.inputs["Value"])
        clamp = create_node(
            tree.nodes, "ShaderNodeClamp", (1120, 760), label="saturate(Fade Ratio)"
        )
        clamp.inputs["Min"].default_value = 0.0
        clamp.inputs["Max"].default_value = 1.0
        tree.links.new(divide.outputs["Value"], clamp.inputs["Value"])
        invert = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Blendable FadeDistance",
            location=(1300, 760),
            hide=True,
        ).node
        invert.inputs["Value"].default_value = 1.0
        tree.links.new(
            clamp.outputs["Result"],
            shader_nodes.socket_by_identifier(invert.inputs, "Value_001"),
        )
        return invert.outputs["Value"]

    def _fresnel(self, tree, data, fade_distance, alpha_gate):
        geometry = create_node(
            tree.nodes,
            "ShaderNodeNewGeometry",
            (-180, 600),
            label="Blendable Fresnel Geometry",
        )
        dot = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            label="N dot V",
            location=(0, 600),
            hide=True,
        ).node
        tree.links.new(geometry.outputs["Normal"], dot.inputs["Vector"])
        tree.links.new(
            geometry.outputs["Incoming"],
            shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
        )
        one_minus = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="1 - N dot V",
            location=(180, 600),
            hide=True,
        ).node
        one_minus.inputs["Value"].default_value = 1.0
        tree.links.new(
            dot.outputs["Value"],
            shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001"),
        )
        absolute = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            label="Absolute Base",
            location=(360, 600),
            hide=True,
        ).node
        tree.links.new(one_minus.outputs["Value"], absolute.inputs["Value"])
        power = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            label="Fresnel Exponent",
            location=(520, 600),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            power.inputs, "Value_001"
        ).default_value = max(0.001, param_float(data, "FresnelExponent", 2.0))
        tree.links.new(absolute.outputs["Value"], power.inputs["Value"])
        saturated = create_node(
            tree.nodes, "ShaderNodeClamp", (680, 600), label="saturate(Fresnel)"
        )
        saturated.inputs["Min"].default_value = 0.0
        saturated.inputs["Max"].default_value = 1.0
        tree.links.new(power.outputs["Value"], saturated.inputs["Value"])
        scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Fresnel Intensity",
            location=(840, 600),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            scale.inputs, "Value_001"
        ).default_value = max(0.0, param_float(data, "FresnelColorIntensity", 8.0))
        tree.links.new(saturated.outputs["Result"], scale.inputs["Value"])
        weighted = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Fresnel x Blend Distance",
            location=(1000, 600),
            hide=True,
        ).node
        tree.links.new(scale.outputs["Value"], weighted.inputs["Value"])
        tree.links.new(
            fade_distance,
            shader_nodes.socket_by_identifier(weighted.inputs, "Value_001"),
        )
        gated = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Fresnel x Base Alpha Gate",
            location=(1160, 600),
            hide=True,
        ).node
        tree.links.new(weighted.outputs["Value"], gated.inputs["Value"])
        tree.links.new(
            alpha_gate, shader_nodes.socket_by_identifier(gated.inputs, "Value_001")
        )
        return gated.outputs["Value"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        context = super().create(data, Mat)
        tree = Mat.node_tree
        bsdf = shader_nodes.principled_bsdf(tree.nodes)
        fade_distance = self._fade_distance(tree, data)
        base_texture = context["base_texture"]
        raw_alpha = base_texture.outputs["Alpha"] if base_texture is not None else None
        alpha_minus_threshold = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="BaseAlpha - AlphaThreshold",
            location=(180, 500),
            hide=True,
        ).node
        if raw_alpha is not None:
            tree.links.new(raw_alpha, alpha_minus_threshold.inputs["Value"])
        else:
            alpha_minus_threshold.inputs["Value"].default_value = 1.0
        shader_nodes.socket_by_identifier(
            alpha_minus_threshold.inputs, "Value_001"
        ).default_value = param_float(
            data, "AlphaThreshold", self.alpha_threshold_default
        )
        alpha_gate = create_node(
            tree.nodes,
            "ShaderNodeClamp",
            (360, 500),
            label="saturate(BaseAlpha - Threshold)",
        )
        tree.links.new(
            alpha_minus_threshold.outputs["Value"], alpha_gate.inputs["Value"]
        )
        fresnel = self._fresnel(tree, data, fade_distance, alpha_gate.outputs["Result"])

        base_input = bsdf.inputs["Base Color"]
        base_source = context["surface"]
        color = param_color(data, "FresnelColor", (1.0, 1.0, 1.0, 1.0))
        fresnel_color = create_node(
            tree.nodes, "ShaderNodeRGB", (700, 600), label="FresnelColor"
        )
        fresnel_color.outputs["Color"].default_value = color
        factor_rgb = create_node(
            tree.nodes, "ShaderNodeCombineColor", (520, 480), label="Fresnel.xxx"
        )
        for socket in ("Red", "Green", "Blue"):
            tree.links.new(fresnel, factor_rgb.inputs[socket])
        multiply = self._mix_color(
            tree,
            (700, 500),
            1.0,
            fresnel_color.outputs["Color"],
            factor_rgb.outputs["Color"],
            blend_type="MULTIPLY",
            label="Colored Fresnel",
        )
        add = self._mix_color(
            tree,
            (880, 600),
            1.0,
            base_source if base_source is not None else base_input.default_value,
            multiply,
            blend_type="ADD",
            label="Blendable Fresnel Color",
        )
        tree.links.new(add, base_input)

        alpha_input = bsdf.inputs["Alpha"]
        for link in tuple(tree.links):
            if link.to_socket == alpha_input:
                tree.links.remove(link)

        if self.enableMask:
            active_fade = shader_nodes.math(
                tree.nodes,
                tree.links,
                "GREATER_THAN",
                label="FadeDistance > 0",
                location=(520, 420),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                active_fade.inputs, "Value_001"
            ).default_value = 0.0
            tree.links.new(fade_distance, active_fade.inputs["Value"])
            one_minus = shader_nodes.math(
                tree.nodes,
                tree.links,
                "SUBTRACT",
                label="1 - FadeDistance",
                location=(680, 420),
                hide=True,
            ).node
            one_minus.inputs["Value"].default_value = 1.0
            tree.links.new(
                fade_distance,
                shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001"),
            )
            final_alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="FinalAlpha Preview",
                location=(840, 420),
                hide=True,
            ).node
            tree.links.new(active_fade.outputs["Value"], final_alpha.inputs["Value"])
            tree.links.new(
                one_minus.outputs["Value"],
                shader_nodes.socket_by_identifier(final_alpha.inputs, "Value_001"),
            )
            alpha_mask = shader_nodes.math(
                tree.nodes,
                tree.links,
                "SUBTRACT",
                label="Blendable AlphaMask",
                location=(1000, 420),
                hide=True,
            ).node
            tree.links.new(
                alpha_minus_threshold.outputs["Value"], alpha_mask.inputs["Value"]
            )
            tree.links.new(
                final_alpha.outputs["Value"],
                shader_nodes.socket_by_identifier(alpha_mask.inputs, "Value_001"),
            )
            preview_alpha = create_node(
                tree.nodes,
                "ShaderNodeClamp",
                (1160, 420),
                label="Blendable Dither Coverage",
            )
            tree.links.new(alpha_mask.outputs["Value"], preview_alpha.inputs["Value"])
            tree.links.new(preview_alpha.outputs["Result"], alpha_input)
            Mat.surface_render_method = "DITHERED"
        else:
            alpha_input.default_value = 1.0
