from ..blender import shader_nodes
from .graph import grid_location, mix_color_socket
from .hud_markers import VERTEX_COLOR_PRESENT_ATTRIBUTE
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    get_or_build_node_group,
    new_labeled_node,
    param_color,
    param_texture_path,
    param_vector,
)
from .overlay_common import (
    additive_surface,
    combine_vector,
    control,
    split_vector,
)

from .overlay_common import material_cache_identity as material_cache_identity


def coverage_group():
    inputs = tuple(
        ("NodeSocketFloat", name)
        for name in (
            "Texture Alpha",
            "Color Alpha",
            "Vertex Alpha",
            "Depth Delta",
            "Sharpness",
            "Contrast",
            "Alpha Multiplier",
            "Distance",
        )
    )

    def build(tree):
        values = tree.nodes.new("NodeGroupInput").outputs
        output = tree.nodes.new("NodeGroupOutput")
        depth = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["Depth Delta"],
            values["Sharpness"],
            name="Soft Depth",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        soft = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            depth,
            name="Inverse Soft Depth",
            location=grid_location(tree, (200, 160)),
        )
        interior = shader_nodes.math(
            tree.nodes,
            tree.links,
            "LESS_THAN",
            soft,
            1.0,
            name="Soft Interior",
            location=grid_location(tree, (200, 160)),
        )
        soft = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            soft,
            0.5,
            name="Soft Midpoint",
            location=grid_location(tree, (200, 160)),
        )
        soft = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            soft,
            values["Contrast"],
            name="Soft Contrast",
            location=grid_location(tree, (200, 160)),
        )
        soft = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            soft,
            0.5,
            name="Soft Contrast Bias",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        soft = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            soft,
            interior,
            name="Soft Interior Coverage",
            location=grid_location(tree, (200, 160)),
        )
        disabled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "COMPARE",
            values["Sharpness"],
            0.0,
            name="Soft Disabled",
            location=grid_location(tree, (200, 160)),
        )
        shader_nodes.socket_by_identifier(
            disabled.node.inputs, "Value_002"
        ).default_value = 0.0
        soft = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            soft,
            1.0,
            disabled,
            name="Soft Coverage",
            location=grid_location(tree, (200, 160)),
        )
        distance = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            values["Distance"],
            40.0,
            name="Distance Scale",
            location=grid_location(tree, (200, 160)),
        )
        distance = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.3,
            distance,
            name="Distance Coverage",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        alpha = values["Texture Alpha"]
        for name, factor in (
            ("Tint Coverage", values["Color Alpha"]),
            ("Vertex Coverage", values["Vertex Alpha"]),
            ("Depth Coverage", soft),
            ("Alpha Gain", values["Alpha Multiplier"]),
            ("Distance Alpha", distance),
        ):
            alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                alpha,
                factor,
                name=name,
                location=grid_location(tree, (200, 160)),
            )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            alpha,
            0.0,
            name="Saturated Alpha",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        discarded = shader_nodes.math(
            tree.nodes,
            tree.links,
            "LESS_THAN",
            alpha,
            0.01,
            name="Discarded Alpha",
            location=grid_location(tree, (200, 160)),
        )
        retained = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            discarded,
            name="Retained Alpha",
            location=grid_location(tree, (200, 160)),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            alpha,
            retained,
            name="Coverage",
            location=grid_location(tree, (200, 160)),
        )
        tree.links.new(alpha, output.inputs["Coverage"])

    return get_or_build_node_group(
        "CP77 Vision Coverage v2", inputs, (("NodeSocketFloat", "Coverage"),), build
    )


class HUDVisionPass(MaterialTypeBase):
    """Build a scrolling textured overlay with vertex tint, depth preview and distance fading"""

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        tree.nodes.clear()
        controls = {
            key: control(tree, data, key, default)
            for key, default in (
                ("ColorMultiplier", 1.0),
                ("AlphaMultiplier", 1.0),
                ("AdditiveAlphaBlend", 1.0),
                ("SoftTransparencyAmount", 1.0),
                ("SoftContrast", 0.0),
                ("UseVertexColor", 1.0),
            )
        }
        depth = control(tree, data, "SceneDepthDelta", 1.0)
        clock = create_scene_time_value(tree, -1400, -800, "Time")
        clock.name = "Time"
        transform = param_vector(data, "TextureTilingAndSpeed", (1.0, 1.0, 0.0, 0.0))
        uv = new_labeled_node(
            tree.nodes, "ShaderNodeTexCoord", "Overlay Coordinates", (-1400, 800)
        )
        uv_axes = split_vector(tree, "Overlay UV", uv.outputs["UV"])
        mapped = []
        for axis, tiling, speed in zip("XY", transform[:2], transform[2:]):
            tile = control(tree, {}, "UV Tiling " + axis, tiling)
            rate = control(tree, {}, "UV Speed " + axis, speed)
            scroll = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                clock.outputs["Value"],
                rate,
                name="UV Time " + axis,
                location=grid_location(tree, (200, 160)),
            )
            scroll = shader_nodes.math(
                tree.nodes,
                tree.links,
                "FRACT",
                scroll,
                name="UV Scroll " + axis,
                location=grid_location(tree, (200, 160)),
            )
            mapped.append(
                shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "MULTIPLY_ADD",
                    uv_axes[axis],
                    tile,
                    scroll,
                    name="UV Sample " + axis,
                    location=grid_location(tree, (200, 160)),
                )
            )
        sample_uv = combine_vector(tree, "Overlay Sample UV", *mapped)
        texture = (
            param_texture_path(data, "Diffuse")
            or r"base\fx\textures\ui\trajectory_arrow.xbm"
        )
        sample = self._relative_texture_node(
            tree.nodes, texture, "Diffuse", (-800, 800), extension="REPEAT"
        )
        tree.links.new(sample_uv, sample.inputs["Vector"])
        tint = param_color(data, "Color", (1.0, 1.0, 1.0, 1.0))
        tint_node = new_labeled_node(tree.nodes, "ShaderNodeRGB", "Color", (-1200, 500))
        tint_node.outputs["Color"].default_value = tint
        color_alpha = control(tree, {"Color.a": tint[3]}, "Color.a", 1.0)
        vertex = new_labeled_node(
            tree.nodes, "ShaderNodeVertexColor", "Vertex Color", (-1200, 100)
        )
        vertex.layer_name = "Color"
        presence = new_labeled_node(
            tree.nodes, "ShaderNodeAttribute", "Vertex Color Present", (-1200, -150)
        )
        presence.attribute_name = VERTEX_COLOR_PRESENT_ATTRIBUTE
        vertex_color = mix_color_socket(
            tree.nodes,
            tree.links,
            "Available Vertex Color",
            (1.0,) * 4,
            vertex.outputs["Color"],
            presence.outputs["Fac"],
            (-900, 100),
        )
        vertex_alpha = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            1.0,
            vertex.outputs["Alpha"],
            presence.outputs["Fac"],
            name="Available Vertex Alpha",
            location=grid_location(tree, (200, 160)),
        )
        vertex_color = mix_color_socket(
            tree.nodes,
            tree.links,
            "Vertex Tint",
            (1.0,) * 4,
            vertex_color,
            controls["UseVertexColor"],
            (-700, 100),
        )
        vertex_alpha = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            1.0,
            vertex_alpha,
            controls["UseVertexColor"],
            name="Vertex Alpha",
            location=grid_location(tree, (200, 160)),
        )
        color = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            sample.outputs["Color"],
            tint_node.outputs["Color"],
            name="Texture Tint",
            location=grid_location(tree, (200, 160)),
        )
        color = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            color,
            scale=controls["ColorMultiplier"],
            name="Color Gain",
            location=grid_location(tree, (200, 160)),
        )
        color = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            color,
            vertex_color,
            name="Overlay Color",
            location=grid_location(tree, (200, 160)),
        )
        camera = new_labeled_node(
            tree.nodes, "ShaderNodeCameraData", "Camera Distance", (-900, -450)
        )
        coverage = new_labeled_node(
            tree.nodes, "ShaderNodeGroup", "Vision Coverage", (1100, 500)
        )
        coverage.node_tree = coverage_group()
        for key, value in {
            "Texture Alpha": sample.outputs["Alpha"],
            "Color Alpha": color_alpha,
            "Vertex Alpha": vertex_alpha,
            "Depth Delta": depth,
            "Sharpness": controls["SoftTransparencyAmount"],
            "Contrast": controls["SoftContrast"],
            "Alpha Multiplier": controls["AlphaMultiplier"],
            "Distance": camera.outputs["View Distance"],
        }.items():
            tree.links.new(value, coverage.inputs[key])
        additive_surface(
            Mat, color, coverage.outputs["Coverage"], controls["AdditiveAlphaBlend"]
        )
        Mat["cp77_hud_color_required"] = True
        Mat.diffuse_color = tint


used_params = (
    "Diffuse",
    "Color",
    "ColorMultiplier",
    "AdditiveAlphaBlend",
    "TextureTilingAndSpeed",
    "AlphaMultiplier",
    "SoftTransparencyAmount",
    "SoftContrast",
    "UseVertexColor",
    "SceneDepthDelta",
)
