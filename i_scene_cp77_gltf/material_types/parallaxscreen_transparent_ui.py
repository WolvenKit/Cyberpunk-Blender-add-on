from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .graph import mix_color_socket, mix_scalar_socket, set_transparent
from .mat_common import param_color, param_float
from .metalbaseui import MetalBaseUI
from .screen_preview import premultiplied_surface


class ParallaxScreenTransparentUI(MetalBaseUI):
    scanlines_intensity_default = 1.0
    texture_defaults = {
        **MetalBaseUI.texture_defaults,
        "ScanlineTexture": r"base\fx\_textures\masks\gradients\fx_reflected_vertical_gradient_01_d.xbm",
        "UIRenderTexture": r"engine\ink\textures\4x4_transparent.xbm",
    }

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        image = self._resolve_render_texture(data)
        base_uv, part_size, texcoord = self._create_base_uv(tree, data)
        mod_uv = self._create_mod_uv(tree, data)
        scanlines = self._create_scanlines(tree, data, texcoord)
        composite, composite_alpha = self._create_layers(
            tree, data, base_uv, mod_uv, part_size, scanlines, image, return_alpha=True
        )

        separate_uv = create_node(
            nodes, "ShaderNodeSeparateXYZ", (-360, -100), label="Screen UV"
        )
        links.new(texcoord.outputs["UV"], separate_uv.inputs["Vector"])
        one_minus_v = shader_nodes.math(
            nodes, links, "SUBTRACT", label="1 - V", location=(-180, -160), hide=True
        ).node
        one_minus_v.inputs["Value"].default_value = 1.0
        links.new(
            separate_uv.outputs["Y"],
            shader_nodes.socket_by_identifier(one_minus_v.inputs, "Value_001"),
        )
        edge = shader_nodes.math(
            nodes, links, "MULTIPLY", label="V(1-V)", location=(0, -120), hide=True
        ).node
        links.new(separate_uv.outputs["Y"], edge.inputs["Value"])
        links.new(
            one_minus_v.outputs["Value"],
            shader_nodes.socket_by_identifier(edge.inputs, "Value_001"),
        )
        edge4 = shader_nodes.math(
            nodes, links, "MULTIPLY", label="Edge x 4", location=(180, -120), hide=True
        ).node
        shader_nodes.socket_by_identifier(edge4.inputs, "Value_001").default_value = 4.0
        links.new(edge.outputs["Value"], edge4.inputs["Value"])
        edge_bias = shader_nodes.math(
            nodes, links, "ADD", label="EdgeMask", location=(360, -120), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            edge_bias.inputs, "Value_001"
        ).default_value = 1.0 - param_float(data, "EdgeMask", 0.0)
        edge_bias.use_clamp = True
        links.new(edge4.outputs["Value"], edge_bias.inputs["Value"])

        tint = create_node(nodes, "ShaderNodeRGB", (0, 320), label="Tint")
        tint.outputs["Color"].default_value = param_color(
            data, "Tint", (1.0, 1.0, 1.0, 1.0)
        )
        tinted = mix_color_socket(
            nodes,
            links,
            "UI x Tint",
            composite,
            tint.outputs["Color"],
            1.0,
            (180, 320),
            blend_type="MULTIPLY",
            clamp=False,
        )

        edge_rgb = create_node(
            nodes, "ShaderNodeCombineXYZ", (360, 120), label="Edge.xxx"
        )
        for socket in ("X", "Y", "Z"):
            links.new(edge_bias.outputs["Value"], edge_rgb.inputs[socket])
        edged = mix_color_socket(
            nodes,
            links,
            "Edge Attenuation",
            tinted,
            edge_rgb.outputs["Vector"],
            1.0,
            (540, 320),
            blend_type="MULTIPLY",
            clamp=False,
        )

        ev = max(0.0, param_float(data, "EmissiveEV", 6.0))
        ev_rgb = create_node(nodes, "ShaderNodeRGB", (540, 140), label="EmissiveEV.xxx")
        ev_rgb.outputs["Color"].default_value = (ev, ev, ev, 1.0)
        final_color = mix_color_socket(
            nodes,
            links,
            "FinalColor",
            edged,
            ev_rgb.outputs["Color"],
            1.0,
            (720, 320),
            blend_type="MULTIPLY",
            clamp=False,
        )

        channels = create_node(
            nodes, "ShaderNodeSeparateColor", (900, 320), label="FinalColor RGB"
        )
        links.new(final_color, channels.inputs["Color"])
        max_rg = shader_nodes.math(
            nodes, links, "MAXIMUM", label="max(R,G)", location=(1080, 360), hide=True
        ).node
        links.new(channels.outputs["Red"], max_rg.inputs["Value"])
        links.new(
            channels.outputs["Green"],
            shader_nodes.socket_by_identifier(max_rg.inputs, "Value_001"),
        )
        max_rgb = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            label="FinalAlpha Color",
            location=(1240, 360),
            use_clamp=True,
            hide=True,
        ).node
        links.new(max_rg.outputs["Value"], max_rgb.inputs["Value"])
        links.new(
            channels.outputs["Blue"],
            shader_nodes.socket_by_identifier(max_rgb.inputs, "Value_001"),
        )

        additive = max(0.0, min(1.0, param_float(data, "AdditiveAlphaBlend", 0.0)))
        alpha_mix = mix_scalar_socket(
            nodes,
            links,
            "Additive Alpha",
            (1080, 180),
            max_rgb.outputs["Value"],
            composite_alpha,
            additive,
        )
        alpha_one = param_float(data, "AlphaAsOne", 0.0)
        final_alpha = shader_nodes.lerp(
            nodes,
            links,
            alpha_mix,
            1.0,
            alpha_one,
            name="AlphaAsOne",
            location=(1380, 180),
        )

        output = create_node(nodes, "ShaderNodeOutputMaterial", (1920, 260), hide=False)
        surface = premultiplied_surface(tree, final_color, final_alpha, (1740, 260))
        links.new(surface, output.inputs["Surface"])

        set_transparent(Mat)
