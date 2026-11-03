from ..assetio.paths import backslash_depot_key
from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from ..materials.blender.images import imageFromFilePath, resolve_relative_image_path
from .graph import grid_location, mix_color_socket, set_transparent
from .mat_common import (
    MaterialTypeBase,
    coerce_texture_path,
    create_scene_time_value,
    get_or_build_node_group,
    lookup_param,
    new_labeled_node,
    param_color,
    param_float,
)

_LINE = r"base\fx\textures\ui\fx_network_vis_solidline.xbm"
_GRADIENT = (
    r"base\fx\_textures\masks\gradients\fx_reflected_vertical_gradient_02_alpha_d.xbm"
)
_NOISE = r"base\fx\_textures\masks\noise\fx_organic_noise_01_d.xbm"
VERTEX_COLOR_PRESENT_ATTRIBUTE = "CP77_HUDMarkerColorPresent"
_RED = {"Red": 255, "Green": 0, "Blue": 0, "Alpha": 255}
_CYAN = {"Red": 4, "Green": 255, "Blue": 193, "Alpha": 255}
_DEFAULTS = {
    "AdditiveAlphaBlend": 1.0,
    "ColorMultiplier": 1.0,
    "ClampOrWrap": 0.0,
    "TillingX": 1.0,
    "TillingY": 0.0,
    "OffsetX": 0.0,
    "OffsetY": 0.0,
    "RotateUV90Deg": 0.0,
    "WipeValue": 0.0,
    "SoftAlpha": 1.0,
    "InverseSoftAlphaValue": 1.0,
    "UseOnMeshes": 0.0,
    "UseWorldSpaceNoise": 0.0,
    "WorldSpaceNoiseTilling": 0.0,
    "NoiseSpeed": 0.0,
    "FresnelPower": 0.0,
    "FresnelContrast": 0.0,
    "SecondSoftAlpha": 0.0,
}
_VARIANTS = {
    "hud_markers_notxaa.mt": {},
    "hud_markers_transparent.mt": {"TillingY": 1.0, "WorldSpaceNoiseTilling": 1.0},
    "hud_markers_vision.mt": {
        "ColorMultiplier": 3.0,
        "TillingY": 4.0,
        "WipeValue": 0.143646002,
        "SecondSoftAlpha": 1.0,
    },
}


def _equal(tree, name, first, second):
    result = shader_nodes.math(
        tree.nodes,
        tree.links,
        "COMPARE",
        first,
        second,
        name=name,
        location=grid_location(tree),
    )
    shader_nodes.socket_by_identifier(
        result.node.inputs, "Value_002"
    ).default_value = 0.0
    return result


def _smoothstep(tree, name, value, minimum, maximum):
    """Preserve HLSL smoothstep arithmetic, including descending edge ranges"""
    offset = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        value,
        minimum,
        name=f"{name} Offset",
        location=grid_location(tree),
    )
    span = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        maximum,
        minimum,
        name=f"{name} Range",
        location=grid_location(tree),
    )
    factor = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        offset,
        span,
        name=f"{name} Saturate",
        location=grid_location(tree),
        use_clamp=True,
    )
    squared = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        factor,
        factor,
        name=f"{name} Squared",
        location=grid_location(tree),
    )
    cubic = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        factor,
        -2.0,
        3.0,
        name=f"{name} Cubic",
        location=grid_location(tree),
    )
    return shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        squared,
        cubic,
        name=name,
        location=grid_location(tree),
    )


def _group_node(tree, group, name, values, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeGroup", name, location)
    node.node_tree = group
    for key, value in values.items():
        assign_socket(tree.links, value, node.inputs[key])
    return node


def _noise_uv_group():
    """Select the source's dominant world-normal plane with Y, Z, X tie priority"""
    inputs = (
        ("NodeSocketVector", "Position"),
        ("NodeSocketVector", "Normal"),
        ("NodeSocketFloat", "Tiling"),
        ("NodeSocketFloat", "Speed"),
        ("NodeSocketFloat", "Time"),
    )

    def build(tree):
        source = tree.nodes.new("NodeGroupInput")
        output = tree.nodes.new("NodeGroupOutput")
        position = new_labeled_node(
            tree.nodes, "ShaderNodeSeparateXYZ", "World Position", (-600, 300)
        )
        normal = new_labeled_node(
            tree.nodes, "ShaderNodeSeparateXYZ", "World Normal", (-600, 0)
        )
        tree.links.new(source.outputs["Position"], position.inputs["Vector"])
        tree.links.new(source.outputs["Normal"], normal.inputs["Vector"])
        axes = [
            shader_nodes.math(
                tree.nodes,
                tree.links,
                "ABSOLUTE",
                normal.outputs[axis],
                name=f"Normal {axis}",
                location=grid_location(tree),
            )
            for axis in "XYZ"
        ]
        largest = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            axes[0],
            axes[1],
            name="Largest XY",
            location=grid_location(tree),
        )
        largest = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            largest,
            axes[2],
            name="Largest Normal Axis",
            location=grid_location(tree),
        )
        y_plane = _equal(tree, "Dominant Y", axes[1], largest)
        z_plane = _equal(tree, "Dominant Z", axes[2], largest)
        not_y = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            y_plane,
            name="Y Priority",
            location=grid_location(tree),
        )
        z_plane = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            z_plane,
            not_y,
            name="Z After Y",
            location=grid_location(tree),
        )
        negative_x = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            position.outputs["X"],
            -1.0,
            name="Negative World X",
            location=grid_location(tree),
        )
        u = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            position.outputs["Y"],
            negative_x,
            y_plane,
            name="Planar U",
            location=grid_location(tree),
        )
        v = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            position.outputs["Z"],
            negative_x,
            z_plane,
            name="Planar V",
            location=grid_location(tree),
        )
        time = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            source.outputs["Time"],
            source.outputs["Speed"],
            name="Noise Time",
            location=grid_location(tree),
        )
        time = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            time,
            0.1,
            name="Noise Time Scale",
            location=grid_location(tree),
        )
        time = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FRACT",
            time,
            name="Noise Time Wrap",
            location=grid_location(tree),
        )
        uv = new_labeled_node(tree.nodes, "ShaderNodeCombineXYZ", "Noise UV", (1600, 0))
        for axis, value in (("X", u), ("Y", v)):
            value = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                value,
                source.outputs["Tiling"],
                name=f"Noise {axis} Tiling",
                location=grid_location(tree),
            )
            value = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                value,
                time,
                name=f"Noise {axis} Scroll",
                location=grid_location(tree),
            )
            tree.links.new(value, uv.inputs[axis])
        tree.links.new(uv.outputs["Vector"], output.inputs["UV"])

    return get_or_build_node_group(
        "CP77 HUD Marker Noise UV v2",
        inputs,
        (("NodeSocketVector", "UV"),),
        build,
    )


def _mask_group():
    inputs = tuple(
        ("NodeSocketFloat", name)
        for name in (
            "U",
            "Texture Alpha",
            "Vertex Alpha",
            "TransparencySlot.w",
            "UseOnMeshes",
            "WipeValue",
            "SoftAlpha",
            "InverseSoftAlphaValue",
            "SceneDepthDelta",
            "Noise",
            "UseWorldSpaceNoise",
            "FresnelPower",
            "FresnelContrast",
            "SecondSoftAlpha",
            "Facing",
            "AdditiveAlphaBlend",
        )
    )

    def build(tree):
        source = tree.nodes.new("NodeGroupInput")
        output = tree.nodes.new("NodeGroupOutput")
        values = source.outputs
        wipe = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            0.5,
            values["U"],
            name="Wipe Center",
            location=grid_location(tree),
        )
        wipe = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            wipe,
            name="Wipe Distance",
            location=grid_location(tree),
        )
        wipe = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            wipe,
            2.0,
            name="Wipe Distance Scale",
            location=grid_location(tree),
        )
        wipe_shift = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["WipeValue"],
            -2.0,
            name="Wipe Amount",
            location=grid_location(tree),
        )
        wipe_shift = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            wipe_shift,
            1.0,
            name="Wipe Bias",
            location=grid_location(tree),
        )
        wipe = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            wipe,
            wipe_shift,
            name="Wipe Input",
            location=grid_location(tree),
        )
        wipe = _smoothstep(tree, "Wipe", wipe, 0.05, 0.1)

        soft = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["SceneDepthDelta"],
            values["SoftAlpha"],
            name="Soft Depth",
            location=grid_location(tree),
            use_clamp=True,
        )
        lower = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            0.5,
            values["InverseSoftAlphaValue"],
            name="Outer Edge",
            location=grid_location(tree),
        )
        upper = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            0.5,
            values["InverseSoftAlphaValue"],
            name="Inner Edge",
            location=grid_location(tree),
        )
        outer = _smoothstep(tree, "Outer Scanline", soft, lower, 0.5)
        inner = _smoothstep(tree, "Inner Scanline", soft, upper, 0.5)
        scanline = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            outer,
            inner,
            name="Scanline",
            location=grid_location(tree),
        )

        vertex = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["Vertex Alpha"],
            values["TransparencySlot.w"],
            name="Vertex Transparency",
            location=grid_location(tree),
        )
        vertex = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            vertex,
            1.0,
            values["UseOnMeshes"],
            name="Use On Meshes",
            location=grid_location(tree),
        )
        noise_enabled = _equal(tree, "Noise Enabled", values["UseWorldSpaceNoise"], 1.0)
        noise = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            1.0,
            values["Noise"],
            noise_enabled,
            name="World Noise",
            location=grid_location(tree),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            vertex,
            values["Texture Alpha"],
            name="Texture Coverage",
            location=grid_location(tree),
        )
        for name, mask in (
            ("Wipe Coverage", wipe),
            ("Scanline Coverage", scanline),
            ("Noise Coverage", noise),
        ):
            alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                alpha,
                mask,
                name=name,
                location=grid_location(tree),
            )

        facing = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            values["Facing"],
            name="Absolute Facing",
            location=grid_location(tree),
        )
        power = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            facing,
            values["FresnelPower"],
            name="Facing Power",
            location=grid_location(tree),
        )
        fresnel = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            power,
            name="Inverse Facing",
            location=grid_location(tree),
        )
        zero_power = _equal(tree, "Zero Fresnel Power", values["FresnelPower"], 0.0)
        fresnel = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            fresnel,
            1.0,
            zero_power,
            name="Fresnel Power Bypass",
            location=grid_location(tree),
        )
        fresnel = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            fresnel,
            0.5,
            name="Fresnel Midpoint",
            location=grid_location(tree),
        )
        fresnel = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            fresnel,
            values["FresnelContrast"],
            name="Fresnel Contrast",
            location=grid_location(tree),
        )
        fresnel = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            fresnel,
            0.5,
            name="Fresnel Bias",
            location=grid_location(tree),
        )
        fresnel = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            fresnel,
            0.0,
            name="Fresnel",
            location=grid_location(tree),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            alpha,
            fresnel,
            name="Fresnel Coverage",
            location=grid_location(tree),
        )

        second = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["SceneDepthDelta"],
            values["SecondSoftAlpha"],
            name="Second Soft Depth",
            location=grid_location(tree),
            use_clamp=True,
        )
        second = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            second,
            name="Second Soft Subtraction",
            location=grid_location(tree),
        )
        secondary_alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            alpha,
            second,
            name="Second Soft Coverage",
            location=grid_location(tree),
            use_clamp=True,
        )
        second_disabled = _equal(
            tree, "Second Soft Disabled", values["SecondSoftAlpha"], 0.0
        )
        alpha = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            secondary_alpha,
            alpha,
            second_disabled,
            name="FinalAlpha",
            location=grid_location(tree),
        )
        blend_alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            alpha,
            values["AdditiveAlphaBlend"],
            name="Blend Alpha",
            location=grid_location(tree),
            use_clamp=True,
        )
        tree.links.new(alpha, output.inputs["FinalAlpha"])
        tree.links.new(blend_alpha, output.inputs["Blend Alpha"])

    return get_or_build_node_group(
        "CP77 HUD Marker Masks v3",
        inputs,
        (("NodeSocketFloat", "FinalAlpha"), ("NodeSocketFloat", "Blend Alpha")),
        build,
    )


class HUDMarkers(MaterialTypeBase):
    """Preview the metadata-selected HUD pixel shader in Eevee and Cycles"""

    def _load_relative_image(
        self, path, *, non_color=False, reject_suffixes=(), error_label="HUD marker"
    ):
        """Resolve project overrides before reusing an image already loaded from the depot"""
        if path and not any(
            str(path).lower().endswith(suffix) for suffix in reject_suffixes
        ):
            resolved = resolve_relative_image_path(
                path,
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
            if resolved:
                return imageFromFilePath(resolved, isNormal=non_color)
        return super()._load_relative_image(
            path,
            non_color=non_color,
            reject_suffixes=reject_suffixes,
            error_label=error_label,
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        variant = backslash_depot_key(Mat.get("MaterialTemplate", "")).rsplit("\\", 1)[
            -1
        ]
        defaults = {**_DEFAULTS, **_VARIANTS.get(variant, {})}
        vision = variant == "hud_markers_vision.mt"
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        controls = {}
        for index, (key, default) in enumerate(defaults.items()):
            node = new_labeled_node(
                nodes, "ShaderNodeValue", key, (-1800, -120 * index)
            )
            node.outputs["Value"].default_value = param_float(data, key, default)
            controls[key] = node.outputs["Value"]
        for index, (key, default) in enumerate(
            (
                ("MaterialParam0.x", 0.0),
                ("TransparencySlot.w", 1.0),
                ("SceneDepthDelta", 1.0),
            )
        ):
            node = new_labeled_node(
                nodes, "ShaderNodeValue", key, (-1600, -120 * index)
            )
            node.outputs["Value"].default_value = param_float(data, key, default)
            controls[key] = node.outputs["Value"]
        time = create_scene_time_value(tree, -1600, -400, "Time")
        time.name = "Time"

        colors = []
        color_alphas = []
        for index, key in enumerate(("Color", "Second_Color")):
            color = param_color(data, key, _CYAN if vision else _RED)
            node = new_labeled_node(
                nodes, "ShaderNodeRGB", key, (-1400, 650 - index * 200)
            )
            node.outputs["Color"].default_value = color
            colors.append(node.outputs["Color"])
            alpha = new_labeled_node(
                nodes, "ShaderNodeValue", f"{key}.a", (-1400, 200 - index * 120)
            )
            alpha.outputs["Value"].default_value = color[3]
            color_alphas.append(alpha.outputs["Value"])
        tint = mix_color_socket(
            nodes,
            links,
            "Runtime Tint",
            *colors,
            controls["MaterialParam0.x"],
            (-1100, 600),
        )
        tint_alpha = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            *color_alphas,
            controls["MaterialParam0.x"],
            name="Tint Alpha",
            location=grid_location(tree),
        )

        coords = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "HUD Coordinates", (-1400, 1000)
        )
        uv = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Original UV", (-1200, 1000)
        )
        links.new(coords.outputs["UV"], uv.inputs["Vector"])
        mapped = []
        for axis, tiling, offset in (
            ("X", "TillingX", "OffsetX"),
            ("Y", "TillingY", "OffsetY"),
        ):
            value = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                uv.outputs[axis],
                controls[tiling],
                name=f"UV {axis} Tiling",
                location=grid_location(tree),
            )
            mapped.append(
                shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "ADD",
                    value,
                    controls[offset],
                    name=f"UV {axis} Offset",
                    location=grid_location(tree),
                )
            )
        zero_rotation = _equal(tree, "UV Swap Disabled", controls["RotateUV90Deg"], 0.0)
        sample_uv = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Sample UV", (-400, 1000)
        )
        for axis, first, second in (
            ("X", mapped[1], mapped[0]),
            ("Y", mapped[0], mapped[1]),
        ):
            value = shader_nodes.lerp(
                tree.nodes,
                tree.links,
                first,
                second,
                zero_rotation,
                name=f"UV {axis} Swap",
                location=grid_location(tree),
            )
            links.new(value, sample_uv.inputs[axis])

        diffuse_path = coerce_texture_path(
            lookup_param(data, "Diffuse", _GRADIENT if vision else _LINE)
        )
        image = self._load_relative_image(
            diffuse_path, error_label="HUD marker Diffuse"
        )
        samples = []
        for index, extension in enumerate(("EXTEND", "REPEAT")):
            sample = new_labeled_node(
                nodes,
                "ShaderNodeTexImage",
                f"Diffuse {extension}",
                (-200, 1000 - index * 300),
            )
            sample.image = image
            sample.extension = extension
            sample.interpolation = "Closest"
            links.new(sample_uv.outputs["Vector"], sample.inputs["Vector"])
            samples.append(sample)
        wrap = _equal(tree, "Wrap Sampler", controls["ClampOrWrap"], 1.0)
        sampled_color = mix_color_socket(
            nodes,
            links,
            "Diffuse Sampler",
            samples[0].outputs["Color"],
            samples[1].outputs["Color"],
            wrap,
            (80, 1000),
        )
        sampled_alpha = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            samples[0].outputs["Alpha"],
            samples[1].outputs["Alpha"],
            wrap,
            name="Diffuse Alpha",
            location=grid_location(tree),
        )
        tinted = mix_color_socket(
            nodes,
            links,
            "Diffuse x Tint",
            sampled_color,
            tint,
            1.0,
            (300, 1000),
            blend_type="MULTIPLY",
        )
        color = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            tinted,
            scale=controls["ColorMultiplier"],
            name="Color Multiplier",
            location=(500, 1000),
        )
        color = shader_nodes.vector_math(
            nodes,
            links,
            "MAXIMUM",
            color,
            (0.0, 0.0, 0.0),
            name="Color Minimum",
            location=(700, 1000),
        )
        color = shader_nodes.vector_math(
            nodes,
            links,
            "MINIMUM",
            color,
            (10.0, 10.0, 10.0),
            name="FinalColor",
            location=(900, 1000),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            sampled_alpha,
            tint_alpha,
            name="Diffuse x Tint Alpha",
            location=grid_location(tree),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            alpha,
            controls["ColorMultiplier"],
            name="Color Multiplier Alpha",
            location=grid_location(tree),
        )
        alpha_clamp = new_labeled_node(
            nodes, "ShaderNodeClamp", "FinalColor.a", (700, 700)
        )
        alpha_clamp.inputs["Max"].default_value = 10.0
        links.new(alpha, alpha_clamp.inputs["Value"])

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "HUD Geometry", (-1200, -200)
        )
        view = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            geometry.outputs["Incoming"],
            name="View Direction",
            location=(-1000, -200),
        )
        facing = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            view,
            geometry.outputs["Normal"],
            name="View Dot Normal",
            location=(-800, -200),
        )
        noise_uv = _group_node(
            tree,
            _noise_uv_group(),
            "World Noise Coordinates",
            {
                "Position": geometry.outputs["Position"],
                "Normal": geometry.outputs["Normal"],
                "Tiling": controls["WorldSpaceNoiseTilling"],
                "Speed": controls["NoiseSpeed"],
                "Time": time.outputs["Value"],
            },
            (-600, -400),
        )
        noise_path = coerce_texture_path(lookup_param(data, "WorldSpaceNoise", _NOISE))
        noise = self._relative_texture_node(
            nodes,
            noise_path,
            "WorldSpaceNoise",
            (-400, -400),
            non_color=True,
            extension="REPEAT",
            interpolation="Closest",
            error_label="HUD marker noise",
        )
        links.new(noise_uv.outputs["UV"], noise.inputs["Vector"])
        red = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "Noise Red", (-200, -400)
        )
        links.new(noise.outputs["Color"], red.inputs["Color"])
        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Vertex Color", (-600, -700)
        )
        vertex.layer_name = "Color"
        presence = new_labeled_node(
            nodes, "ShaderNodeAttribute", "Vertex Color Present", (-600, -950)
        )
        presence.attribute_name = VERTEX_COLOR_PRESENT_ATTRIBUTE
        vertex_alpha = shader_nodes.lerp(
            tree.nodes,
            tree.links,
            1.0,
            vertex.outputs["Alpha"],
            presence.outputs["Fac"],
            name="Vertex Alpha Fallback",
            location=grid_location(tree),
        )
        values = {
            key: controls[key]
            for key in (
                "TransparencySlot.w",
                "UseOnMeshes",
                "WipeValue",
                "SoftAlpha",
                "InverseSoftAlphaValue",
                "SceneDepthDelta",
                "UseWorldSpaceNoise",
                "FresnelPower",
                "FresnelContrast",
                "SecondSoftAlpha",
                "AdditiveAlphaBlend",
            )
        }
        values.update(
            {
                "U": uv.outputs["X"],
                "Texture Alpha": alpha_clamp.outputs["Result"],
                "Vertex Alpha": vertex_alpha,
                "Noise": red.outputs["Red"],
                "Facing": facing,
            }
        )
        masks = _group_node(tree, _mask_group(), "HUD Masks", values, (1100, 500))

        transmittance = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            masks.outputs["Blend Alpha"],
            name="Background Transmittance",
            location=grid_location(tree),
        )
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "HUD Background", (1400, 300)
        )
        links.new(transmittance, transparent.inputs["Color"])
        emission = new_labeled_node(
            nodes, "ShaderNodeEmission", "HUD Emission", (1400, 650)
        )
        links.new(color, emission.inputs["Color"])
        links.new(masks.outputs["FinalAlpha"], emission.inputs["Strength"])
        combined = new_labeled_node(
            nodes, "ShaderNodeAddShader", "Premultiplied HUD", (1600, 500)
        )
        links.new(transparent.outputs["BSDF"], combined.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(combined.inputs, "Shader_001"),
        )
        shadow_transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Shadow Transparency", (1600, 200)
        )
        light_path = new_labeled_node(
            nodes, "ShaderNodeLightPath", "HUD Ray Type", (1600, 0)
        )
        shadow_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "HUD Shadow Bypass", (1800, 500)
        )
        links.new(light_path.outputs["Is Shadow Ray"], shadow_mix.inputs["Factor"])
        links.new(combined.outputs["Shader"], shadow_mix.inputs["Shader"])
        links.new(
            shadow_transparent.outputs["BSDF"],
            shader_nodes.socket_by_identifier(shadow_mix.inputs, "Shader_001"),
        )
        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (2000, 500)
        )
        links.new(shadow_mix.outputs["Shader"], output.inputs["Surface"])
        set_transparent(Mat)
        Mat.use_transparency_overlap = True
        Mat.diffuse_color = tuple(colors[0].default_value)
        Mat["cp77_hud_markers_version"] = 1


def material_cache_identity(raw_material):
    """Invalidate earlier unhandled HUD graphs without changing other material caches"""
    if not isinstance(raw_material, dict):
        return raw_material
    identity = dict(raw_material)
    identity["cp77_hud_markers_version"] = 1
    return identity


used_params = tuple(_DEFAULTS) + ("Diffuse", "WorldSpaceNoise", "Color", "Second_Color")
