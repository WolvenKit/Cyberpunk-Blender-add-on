from ..blender import shader_nodes
from .bundles import tangent_normal_blend_socket
from .graph import mix_color_socket, separate_color_node
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)
from .normal_math import (
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)


class pbr_layer(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        principled = shader_nodes.principled_bsdf(nodes)
        if principled is None:
            return

        texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", (-1400, 320))
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "LayerTile", (-1180, 320)
        )
        mapping.vector_type = "POINT"
        tile = param_float(data, "LayerTile", 2.0)
        mapping.inputs["Scale"].default_value[0] = tile
        mapping.inputs["Scale"].default_value[1] = tile
        uv = texcoord.outputs["UV"]
        links.new(uv, mapping.inputs["Vector"])
        tiled_uv = mapping.outputs["Vector"]

        diffuse = create_relative_texture_node(
            self, tree, data, "Diffuse", tiled_uv, (-940, 560)
        )
        if diffuse is not None:
            tint = new_labeled_node(nodes, "ShaderNodeRGB", "TintColor", (-700, 700))
            tint.outputs["Color"].default_value = param_color(
                data, "TintColor", (0.5, 0.5, 0.5, 1.0)
            )
            color = mix_color_socket(
                nodes,
                links,
                "Diffuse × TintColor",
                diffuse.outputs["Color"],
                tint.outputs["Color"],
                1.0,
                (-420, 560),
                blend_type="MULTIPLY",
                clamp=False,
            )
            links.new(color, find_input(principled, "Base Color"))

        rough_metal = create_relative_texture_node(
            self, tree, data, "RoughMetalBlend", tiled_uv, (-940, 120), non_color=True
        )
        if rough_metal is not None:
            split = separate_color_node(
                tree.nodes,
                tree.links,
                rough_metal.outputs["Color"],
                "R=Rough G=Metal",
                (-680, 120),
            )
            links.new(split.outputs["Red"], find_input(principled, "Roughness"))
            links.new(split.outputs["Green"], find_input(principled, "Metallic"))

        normal_path = param_texture_path(data, "Normal")
        normal_tangent = None
        if normal_path:
            image = self._load_relative_image(
                normal_path, non_color=True, error_label="Normal"
            )
            if image is not None:
                tex = new_labeled_node(
                    nodes, "ShaderNodeTexImage", "Normal", (-940, -180)
                )
                tex.image = image
                links.new(tiled_uv, tex.inputs["Vector"])
                normal_tangent = decode_cp77_normal(
                    tree,
                    tex.outputs["Color"],
                    strength=1.0,
                    location=(-680, -180),
                    label="Normal DirectX Decode",
                ).outputs["Tangent"]

        global_path = param_texture_path(data, "GlobalNormal")
        if normal_tangent is not None and global_path:
            image = self._load_relative_image(
                global_path, non_color=True, error_label="GlobalNormal"
            )
            if image is not None:
                tex = new_labeled_node(
                    nodes, "ShaderNodeTexImage", "GlobalNormal", (-940, -480)
                )
                tex.image = image
                links.new(uv, tex.inputs["Vector"])
                global_tangent = decode_cp77_normal(
                    tree,
                    tex.outputs["Color"],
                    strength=1.0,
                    location=(-680, -480),
                    label="GlobalNormal DirectX Decode",
                ).outputs["Tangent"]
                normal_tangent = tangent_normal_blend_socket(
                    tree,
                    normal_tangent,
                    global_tangent,
                    1.0,
                    (-440, -300),
                    "PBR Layer Normal Blend",
                )

        if normal_tangent is not None:
            encoded = encode_tangent_normal(
                tree, normal_tangent, location=(180, -240), label="PBR Layer Encode"
            )
            normal = tangent_to_normal_map(
                tree, encoded, location=(400, -240), label="PBR Layer Normal"
            )
            links.new(normal, find_input(principled, "Normal"))
