from ..blender import shader_nodes
from .graph import mix_color_socket, set_transparent, value_socket, white_noise_socket
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    find_input,
    new_labeled_node,
    param_float,
)

TEMPLATE = "base\\fx\\_shaders\\crystal_dome.mt"

# Authored template defaults; slider bounds are retained in comments.
_DEFAULTS = {
    "AdditiveAlphaBlend": 0.0,
    "ScanlineDensity": 140.103973,  # 1.0 .. 3500.0
    "GainMin": 0.0149999997,  # 0.0 .. 10.0
    "GainMax": 0.150000006,  # 0.0 .. 10.0
    "NoiseMax": 0.0,  # 0.0 .. 1.0
    "NoiseBrightness": 150.0,  # 0.0 .. 750.0
    "IntialGradientTime": 0.100000001,  # 0.0 .. 1.0
}

# Quantisation rates for the three per-channel glitch hashes.
_CHANNEL_RATES = (5.646, 5.986, 6.351)
_CHANNEL_SEEDS = (0.0, 0.1565, 0.1357)


def _quantised_time(nodes, links, time_socket, rate, location):
    """Quantize scene time to the requested update rate"""
    scaled = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        time_socket,
        rate,
        name=f"Time x {rate}",
        location=location,
    )
    stepped = shader_nodes.math(
        nodes,
        links,
        "FLOOR",
        scaled,
        name=f"floor(Time x {rate})",
        location=(location[0] + 170, location[1]),
    )
    divided = shader_nodes.math(
        nodes,
        links,
        "DIVIDE",
        stepped,
        rate,
        name=f"Step / {rate}",
        location=(location[0] + 340, location[1]),
    )
    return shader_nodes.math(
        nodes,
        links,
        "FRACT",
        divided,
        name=f"frac(Step / {rate})",
        location=(location[0] + 510, location[1]),
    )


class CrystalDome(MaterialTypeBase):
    def _runtime_params(self, nodes):
        """MM_MaterialParams slots driven by gameplay, editable for preview"""
        param0 = value_socket(
            nodes,
            "CP77 MaterialParam0",
            1.0,
            (-2600, 620),
            "MaterialParam0 (effect time)",
        )
        param1 = value_socket(
            nodes,
            "CP77 MaterialParam1",
            1.0,
            (-2600, 500),
            "MaterialParam1 (noise gate)",
        )
        return param0, param1

    def _scanline_coordinate(self, nodes, links, data, time_socket, param1):
        """Build scanline division from vertical UV, color-noise offset, and scanline density"""
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2600, 300))
        split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "UV.x / UV.y", (-2420, 300)
        )
        links.new(uv.outputs["UV"], split.inputs["Vector"])
        uv_x = split.outputs["X"]
        uv_y = split.outputs["Y"]

        # Quantise time to five steps per second.
        time_step = _quantised_time(nodes, links, time_socket, 5.0, (-2420, 140))

        offset_x = shader_nodes.math(
            nodes,
            links,
            "ADD",
            uv_x,
            time_step,
            name="UV.x + TimeStep",
            location=(-1740, 300),
        )
        scaled_x = shader_nodes.math(
            nodes, links, "MULTIPLY", offset_x, 10.0, name="x10", location=(-1570, 300)
        )
        floor_x = shader_nodes.math(
            nodes, links, "FLOOR", scaled_x, name="floor", location=(-1400, 300)
        )
        band_x = shader_nodes.math(
            nodes, links, "DIVIDE", floor_x, 10.0, name="/10", location=(-1230, 300)
        )
        noise_x = white_noise_socket(
            nodes, links, "hash11 Column", (-1060, 300), band_x
        )

        # Apply quantisation before the final scale to preserve operator precedence.
        row_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            uv_x,
            noise_x,
            name="UV.x x Column",
            location=(-1060, 140),
        )
        row_scaled = shader_nodes.math(
            nodes, links, "MULTIPLY", row_scale, 20.0, name="x20", location=(-890, 140)
        )
        row_floor = shader_nodes.math(
            nodes, links, "FLOOR", row_scaled, name="floor", location=(-720, 140)
        )
        row_divided = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            row_floor,
            noise_x,
            name="/ Column",
            location=(-550, 140),
        )
        row_key = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            row_divided,
            20.0,
            name="x20",
            location=(-380, 140),
        )
        noise_y = white_noise_socket(nodes, links, "hash11 Row", (-210, 140), row_key)

        jitter = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            noise_y,
            param1,
            name="Row x MaterialParam1",
            location=(-210, 20),
        )
        offset_y = shader_nodes.math(
            nodes, links, "ADD", uv_y, jitter, name="UV.y + Jitter", location=(-40, 20)
        )
        division = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset_y,
            param_float(data, "ScanlineDensity", _DEFAULTS["ScanlineDensity"]),
            name="Scanline Density",
            location=(130, 20),
        )
        return division, time_step

    def _scanlines(self, nodes, links, data, division, time_step):
        """Shape the fractional coordinate into a peaked pulse, remap its gain, then square again"""
        fractional = shader_nodes.math(
            nodes,
            links,
            "FRACT",
            division,
            name="frac(UVDivision)",
            location=(300, 180),
        )
        inverse = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            fractional,
            name="1 - frac",
            location=(470, 260),
        )
        product = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fractional,
            inverse,
            name="frac x (1 - frac)",
            location=(640, 180),
        )
        widened = shader_nodes.math(
            nodes, links, "MULTIPLY", product, 4.0, name="x4", location=(810, 180)
        )
        squared = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            widened,
            widened,
            name="Square",
            location=(980, 180),
        )

        gain_min = param_float(data, "GainMin", _DEFAULTS["GainMin"])
        gain_max = param_float(data, "GainMax", _DEFAULTS["GainMax"])
        gained = new_labeled_node(
            nodes, "ShaderNodeMapRange", "lerp(GainMin, GainMax)", (1150, 180)
        )
        gained.inputs["From Min"].default_value = 0.0
        gained.inputs["From Max"].default_value = 1.0
        gained.inputs["To Min"].default_value = gain_min
        gained.inputs["To Max"].default_value = gain_max
        gained.clamp = True
        links.new(squared, gained.inputs["Value"])
        gained_socket = gained.outputs["Result"]

        gain_squared = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            gained_socket,
            gained_socket,
            name="Square Gain",
            location=(1360, 180),
        )
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            gain_squared,
            time_step,
            name="Background x TimeStep",
            location=(1530, 180),
        )

    def _glitch_channels(self, nodes, links, data, division, time_socket, param1):
        """Build per-channel hashes at the authored quantisation rates"""
        floor_division = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            division,
            name="floor(UVDivision)",
            location=(300, -240),
        )
        doubled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            division,
            2.0,
            name="UVDivision x 2",
            location=(300, -560),
        )
        floor_doubled = shader_nodes.math(
            nodes, links, "FLOOR", doubled, name="floor(x2)", location=(470, -560)
        )

        keys = []
        for index, (rate, seed) in enumerate(zip(_CHANNEL_RATES, _CHANNEL_SEEDS)):
            base = floor_doubled if index == 2 else floor_division
            step = _quantised_time(
                nodes, links, time_socket, rate, (470, -300 - index * 130)
            )
            combined = shader_nodes.math(
                nodes,
                links,
                "ADD",
                base,
                step,
                name=f"Key {rate}",
                location=(1030, -300 - index * 130),
            )
            if seed:
                combined = shader_nodes.math(
                    nodes,
                    links,
                    "ADD",
                    combined,
                    seed,
                    name=f"Seed {seed}",
                    location=(1200, -300 - index * 130),
                )
            keys.append(
                white_noise_socket(
                    nodes, links, f"hash11 {rate}", (1370, -300 - index * 130), combined
                )
            )

        # Derive the secondary noise channel before saturation.
        signed_x = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            keys[0],
            0.5,
            name="Red - 0.5",
            location=(1540, -300),
        )
        signed_y = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            keys[1],
            0.5,
            name="Green - 0.5",
            location=(1540, -430),
        )
        blue = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            0.5,
            signed_y,
            name="0.5 - Green",
            location=(1710, -560),
            use_clamp=True,
        )
        red = shader_nodes.math(
            nodes,
            links,
            "ADD",
            signed_x,
            0.0,
            name="saturate(Red)",
            location=(1710, -300),
            use_clamp=True,
        )
        green = shader_nodes.math(
            nodes,
            links,
            "ADD",
            signed_y,
            0.0,
            name="saturate(Green)",
            location=(1710, -430),
            use_clamp=True,
        )

        brightness = shader_nodes.math(
            nodes,
            links,
            "ADD",
            keys[2],
            0.0,
            name="saturate(Alpha)",
            location=(1540, -560),
            use_clamp=True,
        )
        fourth = shader_nodes.math(
            nodes,
            links,
            "POWER",
            brightness,
            4.0,
            name="Alpha^4",
            location=(1880, -690),
        )
        fifth = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            brightness,
            fourth,
            name="Alpha^5",
            location=(2050, -690),
        )
        tenth = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fifth,
            fifth,
            name="Alpha^10",
            location=(2220, -690),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            tenth,
            param_float(data, "NoiseBrightness", _DEFAULTS["NoiseBrightness"]),
            name="Noise Brightness",
            location=(2390, -690),
        )

        gate = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            param_float(data, "NoiseMax", _DEFAULTS["NoiseMax"]),
            param1,
            name="NoiseMax x MaterialParam1",
            location=(1880, -820),
        )
        return red, green, blue, alpha, gate

    def _apply_channel(self, nodes, links, name, location, background, channel, gate):
        """Blend from one toward the noise by the gate, then multiply by a second clamped noise blend"""
        mixed = new_labeled_node(nodes, "ShaderNodeMapRange", f"{name} Gate", location)
        mixed.inputs["From Min"].default_value = 0.0
        mixed.inputs["From Max"].default_value = 1.0
        mixed.inputs["To Max"].default_value = 1.0
        links.new(gate, mixed.inputs["Value"])
        links.new(channel, mixed.inputs["To Min"])
        mixed.clamp = False
        gated = mixed.outputs["Result"]

        weight = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            gated,
            5.0,
            name=f"{name} x5",
            location=(location[0] + 190, location[1] - 130),
            use_clamp=True,
        )
        shaped = new_labeled_node(
            nodes,
            "ShaderNodeMapRange",
            f"{name} Shape",
            (location[0] + 380, location[1]),
        )
        shaped.inputs["From Min"].default_value = 0.0
        shaped.inputs["From Max"].default_value = 1.0
        shaped.inputs["To Min"].default_value = 1.0
        links.new(weight, shaped.inputs["Value"])
        links.new(gated, shaped.inputs["To Max"])
        shaped_socket = shaped.outputs["Result"]
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            background,
            shaped_socket,
            name=f"Background x {name}",
            location=(location[0] + 570, location[1]),
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        time = create_scene_time_value(tree, -2600, 760, "CP77 Crystal Dome Time")
        time_socket = time.outputs["Value"]
        param0, param1 = self._runtime_params(nodes)

        division, time_step = self._scanline_coordinate(
            nodes, links, data, time_socket, param1
        )
        background = self._scanlines(nodes, links, data, division, time_step)
        red, green, blue, alpha, gate = self._glitch_channels(
            nodes,
            links,
            data,
            division,
            time_socket,
            param1,
        )

        channels = [
            self._apply_channel(
                nodes, links, "Red", (1880, 320), background, red, gate
            ),
            self._apply_channel(
                nodes, links, "Green", (1880, 100), background, green, gate
            ),
            self._apply_channel(
                nodes, links, "Blue", (1880, -120), background, blue, gate
            ),
        ]
        combine = new_labeled_node(
            nodes, "ShaderNodeCombineColor", "Background", (2600, 100)
        )
        combine.mode = "RGB"
        for socket, channel in zip(("Red", "Green", "Blue"), channels):
            links.new(
                channel,
                combine.inputs.get(socket)
                or shader_nodes.socket_by_identifier(combine.inputs, "Red"),
            )
        # Modulate the background color by the noise mask.
        brightness_scaled = mix_color_socket(
            nodes,
            links,
            "Background x Noise Brightness",
            combine.outputs["Color"],
            alpha,
            1.0,
            (2790, 100),
            blend_type="MULTIPLY",
        )

        # Derive alpha from the runtime material parameter and gradient duration.
        gradient_time = max(
            1.0e-4,
            param_float(data, "IntialGradientTime", _DEFAULTS["IntialGradientTime"]),
        )
        squared_param = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            param0,
            param0,
            name="MaterialParam0^2",
            location=(2600, -180),
        )
        fade = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            squared_param,
            gradient_time,
            name="Initial Gradient Time",
            location=(2790, -180),
            use_clamp=True,
        )

        # Compensate Blender's Mix Shader for premultiplied alpha blending by pre-dividing the
        # emission to keep dst*(1-a) + colour rather than dst*(1-a) + colour*a.
        safe_alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            fade,
            1.0e-4,
            name="Guard Alpha",
            location=(2960, -300),
        )
        premultiplied = mix_color_socket(
            nodes,
            links,
            "Premultiply Compensation",
            brightness_scaled,
            safe_alpha,
            1.0,
            (3130, 100),
            blend_type="DIVIDE",
        )

        emission = new_labeled_node(
            nodes, "ShaderNodeEmission", "Crystal Dome", (3320, 200)
        )
        links.new(
            premultiplied, find_input(emission, "Color") or emission.inputs["Color"]
        )
        strength = find_input(emission, "Strength")
        if strength is not None:
            strength.default_value = 1.0

        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Backdrop", (3320, 20)
        )
        mix = new_labeled_node(nodes, "ShaderNodeMixShader", "FinalAlpha", (3510, 120))
        links.new(fade, mix.inputs["Factor"])
        links.new(transparent.outputs["BSDF"], mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (3700, 120)
        )
        links.new(mix.outputs["Shader"], output.inputs["Surface"])

        # Render as a two-sided transparent surface without depth writes.
        set_transparent(Mat)
        Mat.diffuse_color = (0.05, 0.35, 0.55, 1.0)
