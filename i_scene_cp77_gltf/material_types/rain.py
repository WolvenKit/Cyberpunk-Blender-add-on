from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import color_channel_socket, separate_color_sockets, set_transparent
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    new_labeled_node,
    param_float,
    scene_time_socket,
)

TEMPLATE = r"base\materials\rain.mt"


def _uv(tree, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeTexCoord", "Rain UV", location)
    return node.outputs["UV"]


def _offset_uv(tree, uv, time_socket, speed, scale, offset, location, label):
    nodes = tree.nodes
    links = tree.links
    shifted = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        uv,
        scale,
        (float(offset[0]), 0.0, 0.0),
        name=f"{label} Scale",
        location=location,
    )
    return shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        time_socket,
        (0.0, speed, 0.0),
        shifted,
        name=label,
        location=(location[0] + 180, location[1]),
    )


class Rain(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (820, 80)
        )
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent", (500, -100)
        )
        emission = new_labeled_node(
            nodes, "ShaderNodeEmission", "Rain Lighting", (500, 160)
        )
        mix = new_labeled_node(nodes, "ShaderNodeMixShader", "Rain Alpha", (660, 80))
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        rain_type = 0 if param_float(data, "RainType", 0.0) < 0.5 else 1
        brightness = max(
            0.0,
            param_float(
                data, "BrightnessDrops" if rain_type == 0 else "BrightnessCards", 1.0
            ),
        )
        emission.inputs["Color"].default_value = (0.72, 0.78, 0.84, 1.0)
        emission.inputs["Strength"].default_value = brightness

        uv = _uv(tree, (-1320, 220))
        speed = param_float(data, "UvSpeed", 1.0)
        alpha = None

        if rain_type == 1:
            time = scene_time_socket(tree.nodes, (-1320, -40), "Rain Time")
            channels = []
            specs = (
                ("Red", 1.0, 1.0, 1.0),
                ("Green", 1.2, 1.4, 1.0),
                ("Blue", -1.4, 1.8, 0.5),
            )
            for index, (channel, seed_scale, time_scale, weight) in enumerate(specs):
                shifted = _offset_uv(
                    tree,
                    uv,
                    time,
                    speed * time_scale,
                    (1.0, 5.0, 1.0),
                    (0.5 * seed_scale, 0.0),
                    (-1040, 360 - index * 220),
                    f"Rain Card {index + 1} UV",
                )
                tex = create_relative_texture_node(
                    self,
                    tree,
                    data,
                    "Mask",
                    shifted,
                    (-440, 360 - index * 220),
                    non_color=True,
                    error_label="rain Mask",
                )
                if tex is None:
                    continue
                value = color_channel_socket(
                    nodes,
                    links,
                    tex.outputs["Color"],
                    f"Rain Card {channel}",
                    (-180, 360 - index * 220),
                    channel=channel,
                )
                if weight != 1.0:
                    value = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        value,
                        weight,
                        name=f"{channel} Weight",
                        location=(20, 360 - index * 220),
                    )
                channels.append(value)
            if channels:
                alpha = channels[0]
                for index, channel in enumerate(channels[1:], start=2):
                    alpha = shader_nodes.math(
                        nodes,
                        links,
                        "ADD",
                        alpha,
                        channel,
                        name=f"Rain Card Sum {index}",
                        location=(180 + index * 120, 260),
                        use_clamp=True,
                    )
        else:
            drop_uv = shader_nodes.vector_math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                uv,
                (2.0, 1.0, 1.0),
                (-0.5, 0.0, 0.0),
                name="Drop UV",
                location=(-820, 220),
            )
            tex = create_relative_texture_node(
                self,
                tree,
                data,
                "Mask",
                drop_uv,
                (-360, 220),
                non_color=True,
                error_label="rain Mask",
            )
            if tex is not None:
                red, green, blue = separate_color_sockets(
                    nodes, links, tex.outputs["Color"], "Drop RGB", (-100, 260)
                )
                rg = shader_nodes.math(
                    nodes,
                    links,
                    "MAXIMUM",
                    red,
                    green,
                    name="Drop max(R,G)",
                    location=(120, 200),
                )
                alpha = shader_nodes.math(
                    nodes,
                    links,
                    "MAXIMUM",
                    rg,
                    blue,
                    name="Drop Packed Mask",
                    location=(320, 160),
                    use_clamp=True,
                )

        if alpha is None:
            mix.inputs["Factor"].default_value = 1.0
        else:
            links.new(alpha, mix.inputs["Factor"])

        set_transparent(Mat)


used_params = ["RainType", "UvSpeed", "Mask", "BrightnessCards", "BrightnessDrops"]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
