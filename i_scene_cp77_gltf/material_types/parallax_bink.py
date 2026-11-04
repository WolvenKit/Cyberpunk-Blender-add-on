from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .bink_math import decode_bink_preview
from .graph import mix_color_socket, set_transparent
from .mat_common import MaterialTypeBase, param_color


class BinkParallax(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = create_node(nodes, "ShaderNodeOutputMaterial", (720, 80), hide=False)
        emission = create_node(
            nodes, "ShaderNodeEmission", (440, 180), label="Bink FinalColor"
        )
        transparent = create_node(nodes, "ShaderNodeBsdfTransparent", (440, -60))
        mix = create_node(
            nodes, "ShaderNodeMixShader", (590, 80), label="Premultiplied Video"
        )
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        video, alpha = decode_bink_preview(self, tree, data, extension="EXTEND")
        color_scale_value = param_color(data, "ColorScale", (1.0, 1.0, 1.0, 1.0))
        color_scale = create_node(
            nodes, "ShaderNodeRGB", (-240, 320), label="ColorScale"
        )
        color_scale.outputs["Color"].default_value = color_scale_value
        vertex = create_node(
            nodes, "ShaderNodeVertexColor", (-240, 180), label="VertexColor"
        )

        base = video if video is not None else (1.0, 1.0, 1.0, 1.0)
        tinted = mix_color_socket(
            nodes,
            links,
            "Video x ColorScale",
            base,
            color_scale.outputs["Color"],
            1.0,
            (0, 300),
            blend_type="MULTIPLY",
            clamp=False,
        )
        final = mix_color_socket(
            nodes,
            links,
            "x VertexColor",
            tinted,
            vertex.outputs["Color"],
            1.0,
            (190, 300),
            blend_type="MULTIPLY",
            clamp=False,
        )
        links.new(final, emission.inputs["Color"])

        video_alpha = alpha
        if video_alpha is None:
            alpha_value = vertex.outputs["Alpha"]
        else:
            video_vertex_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                label="BinkA x VertexAlpha",
                location=(80, 0),
                hide=True,
            ).node
            links.new(video_alpha, video_vertex_alpha.inputs["Value"])
            links.new(
                vertex.outputs["Alpha"],
                shader_nodes.socket_by_identifier(
                    video_vertex_alpha.inputs, "Value_001"
                ),
            )
            alpha_value = video_vertex_alpha.outputs["Value"]

        final_alpha = shader_nodes.math(
            nodes, links, "MULTIPLY", label="FinalAlpha", location=(240, 0), hide=True
        ).node
        links.new(alpha_value, final_alpha.inputs["Value"])
        shader_nodes.socket_by_identifier(
            final_alpha.inputs, "Value_001"
        ).default_value = color_scale_value[3]
        links.new(final_alpha.outputs["Value"], mix.inputs["Factor"])
        emission.inputs["Strength"].default_value = 1.0
        set_transparent(Mat)
