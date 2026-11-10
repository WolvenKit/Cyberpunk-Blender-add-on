from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .graph import grid_location
from .mat_common import (
    MaterialTypeBase,
    get_or_build_node_group,
    new_labeled_node,
    param_color,
    param_texture_path,
    param_vector,
    scene_time_socket,
)
from .overlay_common import combine_vector, control, split_vector, transmission_surface


def _iridescent_color(tree, cosine, sine, inverse_cosine):
    """The rotated iridescence colour, base·cos + cross·sin + axial·(1 - cos)"""
    color = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        (0.5, 0.5, 1.0),
        scale=cosine,
        name="Rotated Base",
        location=grid_location(tree, (200, 160)),
    )
    iris = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        (0.29, -0.29, 0.0),
        sine,
        color,
        name="Rotation Components",
        location=grid_location(tree, (200, 160)),
    )
    return shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        (0.6728, 0.6728, 0.6728),
        inverse_cosine,
        iris,
        name="Iridescent Color",
        location=grid_location(tree, (200, 160)),
    )


def _dirt_blend(tree, light, dirt_color, dirt):
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    mix.clamp_factor = False
    mix.name = mix.label = "Optical Dirt Color"
    mix.location = grid_location(tree, (200, 160))
    sockets = {socket.identifier: socket for socket in (*mix.inputs, *mix.outputs)}
    assign_socket(tree.links, dirt, sockets["Factor_Float"])
    assign_socket(tree.links, light, sockets["A_Vector"])
    assign_socket(tree.links, dirt_color, sockets["B_Vector"])
    return sockets["Result_Vector"]


def optical_terms_group():
    """Separate local optical color from the background transmission coefficient"""
    scalar_names = (
        "Facing",
        "Distortion",
        "Noise",
        "Dirt",
        "Normal Z",
        "Dirt Influence",
        "Dirt Power",
        "Dirt Multiplier",
        "Iridescence Dim",
        "Use Outline",
        "Outline Opacity",
        "Outline Size",
    )
    inputs = tuple(("NodeSocketFloat", name) for name in scalar_names) + (
        ("NodeSocketColor", "Tinge"),
        ("NodeSocketColor", "Dirt Color"),
    )

    def build(tree):
        source = tree.nodes.new("NodeGroupInput")
        output = tree.nodes.new("NodeGroupOutput")
        values = source.outputs
        facing = values["Facing"]
        phase = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            facing,
            3.14 * 9,
            name="Optical Phase",
            location=grid_location(tree, (200, 160)),
        )
        cosine = shader_nodes.math(
            tree.nodes,
            tree.links,
            "COSINE",
            phase,
            name="Phase Cosine",
            location=grid_location(tree, (200, 160)),
        )
        sine = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SINE",
            phase,
            name="Phase Sine",
            location=grid_location(tree, (200, 160)),
        )
        inverse_cosine = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            cosine,
            name="Inverse Cosine",
            location=grid_location(tree, (200, 160)),
        )
        iris = _iridescent_color(tree, cosine, sine, inverse_cosine)
        absolute_iris = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            iris,
            name="Absolute Iridescence",
            location=grid_location(tree, (200, 160)),
        )
        powered_iris = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "POWER",
            absolute_iris,
            (1.15, 1.15, 1.15),
            name="Iridescent Highlight",
            location=grid_location(tree, (200, 160)),
        )
        face = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            facing,
            name="Absolute Facing",
            location=grid_location(tree, (200, 160)),
        )
        face = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            face,
            0.3,
            name="Facing Weight",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        noise = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            values["Noise"],
            name="Absolute Noise",
            location=grid_location(tree, (200, 160)),
        )
        noise = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            noise,
            values["Iridescence Dim"],
            name="Iridescent Noise",
            location=grid_location(tree, (200, 160)),
        )
        blend = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            face,
            noise,
            name="Iridescent Blend",
            location=grid_location(tree, (200, 160)),
        )
        distortion = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            values["Distortion"],
            0.0,
            name="Distortion Weight",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        complement = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            blend,
            name="Blend Complement",
            location=grid_location(tree, (200, 160)),
        )
        rotated_weight = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            blend,
            complement,
            name="Rotated Weight",
            location=grid_location(tree, (200, 160)),
        )
        rotated_weight = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            rotated_weight,
            distortion,
            name="Distorted Weight",
            location=grid_location(tree, (200, 160)),
        )
        highlight_weight = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            blend,
            blend,
            name="Highlight Weight",
            location=grid_location(tree, (200, 160)),
        )
        foreground_weight = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            rotated_weight,
            highlight_weight,
            name="Foreground Weight",
            location=grid_location(tree, (200, 160)),
        )
        transmission = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            foreground_weight,
            name="Optical Transmission",
            location=grid_location(tree, (200, 160)),
        )
        tint_weight = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            face,
            name="Tint Facing",
            location=grid_location(tree, (200, 160)),
        )
        tint_weight = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            transmission,
            tint_weight,
            name="Tint Weight",
            location=grid_location(tree, (200, 160)),
        )
        tint = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            values["Tinge"],
            scale=tint_weight,
            name="Optical Tint",
            location=grid_location(tree, (200, 160)),
        )
        rotated = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            iris,
            scale=rotated_weight,
            name="Weighted Iridescence",
            location=grid_location(tree, (200, 160)),
        )
        highlight = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            powered_iris,
            scale=highlight_weight,
            name="Weighted Highlight",
            location=grid_location(tree, (200, 160)),
        )
        light = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            tint,
            rotated,
            name="Local Optical Terms",
            location=grid_location(tree, (200, 160)),
        )
        light = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            light,
            highlight,
            name="Local Optical Color",
            location=grid_location(tree, (200, 160)),
        )
        upward = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            values["Normal Z"],
            0.5,
            0.5,
            name="Upward Normal",
            location=grid_location(tree, (200, 160)),
        )
        dirt = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["Dirt"],
            upward,
            name="Directional Dirt",
            location=grid_location(tree, (200, 160)),
        )
        dirt = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            dirt,
            name="Absolute Dirt",
            location=grid_location(tree, (200, 160)),
        )
        dirt = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            dirt,
            values["Dirt Power"],
            name="Dirt Power",
            location=grid_location(tree, (200, 160)),
        )
        dirt = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            dirt,
            values["Dirt Multiplier"],
            name="Dirt Mask",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        dirt = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            dirt,
            values["Dirt Influence"],
            name="Dirt Influence",
            location=grid_location(tree, (200, 160)),
        )
        clean = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            dirt,
            name="Clean Weight",
            location=grid_location(tree, (200, 160)),
        )
        light = _dirt_blend(tree, light, values["Dirt Color"], dirt)
        transmission = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            transmission,
            clean,
            name="Transmission",
            location=grid_location(tree, (200, 160)),
        )
        edge = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            facing,
            name="Outline Facing",
            location=grid_location(tree, (200, 160)),
        )
        edge = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            edge,
            values["Outline Opacity"],
            name="Outline Weight",
            location=grid_location(tree, (200, 160)),
        )
        outline = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            values["Tinge"],
            scale=edge,
            name="Outline Color",
            location=grid_location(tree, (200, 160)),
        )
        outline = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            outline,
            name="Absolute Outline",
            location=grid_location(tree, (200, 160)),
        )
        exponent = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            (1.0, 1.0, 1.0),
            scale=values["Outline Size"],
            name="Outline Exponent",
            location=grid_location(tree, (200, 160)),
        )
        outline = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "POWER",
            outline,
            exponent,
            name="Outline Shape",
            location=grid_location(tree, (200, 160)),
        )
        outline = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            outline,
            scale=values["Use Outline"],
            name="Outline Contribution",
            location=grid_location(tree, (200, 160)),
        )
        light = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            light,
            outline,
            name="Light",
            location=grid_location(tree, (200, 160)),
        )
        tree.links.new(light, output.inputs["Light"])
        tree.links.new(transmission, output.inputs["Transmission"])

    return get_or_build_node_group(
        "CP77 Optical Terms v3",
        inputs,
        (("NodeSocketColor", "Light"), ("NodeSocketFloat", "Transmission")),
        build,
    )


class Cloak(MaterialTypeBase):
    """Combine view-dependent optical color with an explicitly unshifted transmitted background"""

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        tree.nodes.clear()
        controls = {
            name: control(tree, data, name, value)
            for name, value in (
                ("AdditiveAlphaBlend", 1.0),
                ("DistortionVisibility", 15.0),
                ("IridescenceSpeed", 0.200000003),
                ("IridescenceDim", 3.0),
                ("DirtMaskPower", 1.5),
                ("DirtMaskMultiplier", 1.5),
                ("UseOutline", 0.0),
                ("OutlineOpacity", 4.5),
                ("OutlineSize", 2.5),
            )
        }
        transition = control(tree, data, "MaterialParam0.x", 0.0)
        dirt_influence = control(tree, data, "MaterialParam1.x", 0.0)
        clock = scene_time_socket(tree.nodes, (-1600, -800), "Time")
        uv_node = new_labeled_node(
            tree.nodes, "ShaderNodeTexCoord", "Optical Coordinates", (-1400, 800)
        )
        uv = uv_node.outputs["UV"]
        distortion_scale = param_vector(
            data, "DistortionUVScale", (24.0, 24.0, 0.0, 0.0)
        )
        scale = combine_vector(
            tree, "Distortion Tiling", distortion_scale[0], distortion_scale[1]
        )
        transition_scale = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            1.0,
            0.5,
            transition,
            name="Transition Tiling",
            location=grid_location(tree, (200, 160)),
        )
        distortion_uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            uv,
            scale,
            name="Distortion Scaled UV",
            location=grid_location(tree, (200, 160)),
        )
        distortion_uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            distortion_uv,
            scale=transition_scale,
            name="Distortion UV",
            location=grid_location(tree, (200, 160)),
        )
        geometry = new_labeled_node(
            tree.nodes, "ShaderNodeNewGeometry", "Optical Geometry", (-1400, 0)
        )
        normal = split_vector(tree, "Surface Normal", geometry.outputs["Normal"])
        view = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "NORMALIZE",
            geometry.outputs["Incoming"],
            name="View Direction",
            location=grid_location(tree, (200, 160)),
        )
        facing = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            view,
            geometry.outputs["Normal"],
            name="Optical Facing",
            location=grid_location(tree, (200, 160)),
        )
        accelerated = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            controls["IridescenceSpeed"],
            30.0,
            name="Accelerated Iridescence",
            location=grid_location(tree, (200, 160)),
        )
        speed = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            controls["IridescenceSpeed"],
            accelerated,
            transition,
            name="Iridescence Rate",
            location=grid_location(tree, (200, 160)),
        )
        scroll = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            clock,
            speed,
            name="Iridescence Time",
            location=grid_location(tree, (200, 160)),
        )
        noise_y = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            normal["Y"],
            scroll,
            name="Iridescence Y",
            location=grid_location(tree, (200, 160)),
        )
        noise_uv = combine_vector(tree, "Iridescence UV", normal["X"], noise_y)
        dirt_mapping = param_vector(
            data, "DirtMaskScaleAndOffset", (1.0, 1.0, 0.0, 0.0)
        )
        dirt_scale = combine_vector(
            tree, "Dirt Tiling", dirt_mapping[0], dirt_mapping[1]
        )
        dirt_offset = combine_vector(
            tree, "Dirt Offset", dirt_mapping[2], dirt_mapping[3]
        )
        dirt_uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            uv,
            dirt_scale,
            name="Dirt Scaled UV",
            location=grid_location(tree, (200, 160)),
        )
        dirt_uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            dirt_uv,
            dirt_offset,
            name="Dirt UV",
            location=grid_location(tree, (200, 160)),
        )
        samples = {}
        for key, default, coordinates in (
            (
                "Distortion",
                r"base\surfaces\microblends\carbon_fiber.xbm",
                distortion_uv,
            ),
            (
                "IridescenceMask",
                r"base\fx\_textures\masks\noise\fx_low_frequency_noise_01_d.xbm",
                noise_uv,
            ),
            (
                "DirtMask",
                r"base\fx\_textures\masks\noise\fx_organic_noise_01_d.xbm",
                dirt_uv,
            ),
        ):
            path = param_texture_path(data, key) or default
            sample = self._relative_texture_node(
                tree.nodes, path, key, (-1000, 700), non_color=True, extension="REPEAT"
            )
            tree.links.new(coordinates, sample.inputs["Vector"])
            samples[key] = split_vector(
                tree, key + " Channels", sample.outputs["Color"]
            )["X"]
        distortion = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            samples["Distortion"],
            2.0,
            name="Signed Distortion Scale",
            location=grid_location(tree, (200, 160)),
        )
        distortion = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            distortion,
            1.0,
            name="Signed Distortion",
            location=grid_location(tree, (200, 160)),
        )
        visibility = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            controls["DistortionVisibility"],
            3500.0,
            transition,
            name="Transition Visibility",
            location=grid_location(tree, (200, 160)),
        )
        distortion = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            distortion,
            visibility,
            name="Distortion Intensity",
            location=grid_location(tree, (200, 160)),
        )
        tint = param_color(data, "Tinge", (78 / 255, 126 / 255, 132 / 255, 1.0))
        dirt_color = param_color(
            data, "DirtColor", (188 / 255, 188 / 255, 188 / 255, 1.0)
        )
        terms = new_labeled_node(
            tree.nodes, "ShaderNodeGroup", "Optical Terms", (1100, 400)
        )
        terms.node_tree = optical_terms_group()
        for name, value in {
            "Facing": facing,
            "Distortion": distortion,
            "Noise": samples["IridescenceMask"],
            "Dirt": samples["DirtMask"],
            "Normal Z": normal["Z"],
            "Dirt Influence": dirt_influence,
            "Dirt Power": controls["DirtMaskPower"],
            "Dirt Multiplier": controls["DirtMaskMultiplier"],
            "Iridescence Dim": controls["IridescenceDim"],
            "Use Outline": controls["UseOutline"],
            "Outline Opacity": controls["OutlineOpacity"],
            "Outline Size": controls["OutlineSize"],
            "Tinge": tint,
            "Dirt Color": dirt_color,
        }.items():
            assign_socket(tree.links, value, terms.inputs[name])
        additive_opacity = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            controls["AdditiveAlphaBlend"],
            0.0,
            name="Optical Blend Opacity",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        additive_background = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            additive_opacity,
            name="Additive Background",
            location=grid_location(tree, (200, 160)),
        )
        transmission = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            terms.outputs["Transmission"],
            additive_background,
            name="Optical Background",
            location=grid_location(tree, (200, 160)),
        )
        transmission_surface(Mat, terms.outputs["Light"], transmission)
        Mat.use_backface_culling = True
        Mat.diffuse_color = tint


used_params = (
    "AdditiveAlphaBlend",
    "Distortion",
    "DistortionUVScale",
    "DistortionVisibility",
    "IridescenceMask",
    "IridescenceSpeed",
    "IridescenceDim",
    "Tinge",
    "DirtMask",
    "DirtMaskScaleAndOffset",
    "DirtMaskPower",
    "DirtMaskMultiplier",
    "DirtColor",
    "UseOutline",
    "OutlineOpacity",
    "OutlineSize",
    "MaterialParam0.x",
    "MaterialParam1.x",
)
