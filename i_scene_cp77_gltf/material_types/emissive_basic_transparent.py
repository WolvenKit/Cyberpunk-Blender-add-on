from ..blender import shader_nodes
from ..materials.blender.nodes import CreateShaderNodeValue, create_node
from .emissive_common import ABSENT_COLOR_FALLBACK
from .graph import set_transparent
from .mat_common import (
    MaterialTypeBase,
    param_color,
    param_texture_path,
)

# Floor for the premultiplied-alpha compensation divide; see create().
_ALPHA_FLOOR = 1.0e-4


class EmissiveBasicTransparent(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        CurMat = Mat.node_tree
        nodes = CurMat.nodes
        links = CurMat.links
        nodes.clear()

        output = create_node(nodes, "ShaderNodeOutputMaterial", (600, 0), hide=False)
        emission = create_node(
            nodes, "ShaderNodeEmission", (340, 120), label="FinalColor"
        )
        transparent = create_node(nodes, "ShaderNodeBsdfTransparent", (340, -80))
        mix = create_node(
            nodes, "ShaderNodeMixShader", (480, 0), label="FinalColor over FinalAlpha"
        )
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        diffuse_path = param_texture_path(data, "Diffuse")
        diffuse = None
        if diffuse_path:
            image = self._load_relative_image(
                diffuse_path, error_label="emissive basic transparent"
            )
            diffuse = create_node(
                nodes, "ShaderNodeTexImage", (-800, 200), label="Diffuse", image=image
            )

        emissive_color = param_color(data, "EmissiveColor", ABSENT_COLOR_FALLBACK)
        tint = create_node(nodes, "ShaderNodeRGB", (-800, 0), label="EmissiveColor")
        tint.outputs["Color"].default_value = emissive_color

        modifier = CreateShaderNodeValue(
            CurMat, 1.0, -800, -160, "MaterialParam0 (runtime)"
        )
        modifier.hide = False
        modifier.label = "MaterialParam0"

        tinted = create_node(
            nodes,
            "ShaderNodeMix",
            (-480, 120),
            blend_type="MULTIPLY",
            label="Diffuse x EmissiveColor",
        )
        tinted.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            tinted.inputs, "Factor_Float"
        ).default_value = 1.0
        if diffuse is not None:
            links.new(
                diffuse.outputs["Color"],
                shader_nodes.socket_by_identifier(tinted.inputs, "A_Color"),
            )
        else:
            shader_nodes.socket_by_identifier(
                tinted.inputs, "A_Color"
            ).default_value = ABSENT_COLOR_FALLBACK
        links.new(
            tint.outputs["Color"],
            shader_nodes.socket_by_identifier(tinted.inputs, "B_Color"),
        )

        modulated = create_node(
            nodes,
            "ShaderNodeMix",
            (-220, 120),
            blend_type="MULTIPLY",
            label="x MaterialParam0",
        )
        modulated.data_type = "RGBA"
        shader_nodes.socket_by_identifier(
            modulated.inputs, "Factor_Float"
        ).default_value = 1.0
        links.new(
            shader_nodes.socket_by_identifier(tinted.outputs, "Result_Color"),
            shader_nodes.socket_by_identifier(modulated.inputs, "A_Color"),
        )
        scale_rgb = create_node(
            nodes, "ShaderNodeCombineColor", (-480, -160), label="MaterialParam0.xxx"
        )
        for socket in ("Red", "Green", "Blue"):
            links.new(modifier.outputs["Value"], scale_rgb.inputs[socket])
        links.new(
            scale_rgb.outputs["Color"],
            shader_nodes.socket_by_identifier(modulated.inputs, "B_Color"),
        )
        links.new(
            shader_nodes.socket_by_identifier(modulated.outputs, "Result_Color"),
            emission.inputs["Color"],
        )

        # Combine diffuse alpha, tint alpha, and the runtime material parameter.
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            label="Diffuse.a x EmissiveColor.a",
            location=(-220, -160),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            alpha.inputs, "Value_001"
        ).default_value = emissive_color[3]
        if diffuse is not None:
            links.new(diffuse.outputs["Alpha"], alpha.inputs["Value"])
        else:
            alpha.inputs["Value"].default_value = 1.0

        final_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            label="FinalAlpha",
            location=(40, -160),
            use_clamp=True,
            hide=True,
        ).node
        links.new(alpha.outputs["Value"], final_alpha.inputs["Value"])
        links.new(
            modifier.outputs["Value"],
            shader_nodes.socket_by_identifier(final_alpha.inputs, "Value_001"),
        )
        links.new(final_alpha.outputs["Value"], mix.inputs["Factor"])

        # Compensate Blender's straight-alpha mix to preserve premultiplied emission.
        # The floor prevents division by zero when the mix factor is fully transparent.
        safe_alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            label="max(FinalAlpha, eps)",
            location=(200, -300),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            safe_alpha.inputs, "Value_001"
        ).default_value = _ALPHA_FLOOR
        links.new(final_alpha.outputs["Value"], safe_alpha.inputs["Value"])

        premultiplied = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            label="Premultiplied compensation",
            location=(340, -300),
            hide=True,
        ).node
        premultiplied.inputs["Value"].default_value = 1.0
        links.new(
            safe_alpha.outputs["Value"],
            shader_nodes.socket_by_identifier(premultiplied.inputs, "Value_001"),
        )
        links.new(premultiplied.outputs["Value"], emission.inputs["Strength"])

        set_transparent(Mat)
        Mat.diffuse_color = (*emissive_color[:3], 1.0)
