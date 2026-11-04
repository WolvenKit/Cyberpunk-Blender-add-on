from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from .decal_math import ev_to_linear
from .graph import mix_color_socket, set_alpha_clip, value_socket, white_noise_socket

# Opaque dome material with a swipe-in reveal.
# The authored normal texture and distortion parameters do not affect the final
# surface, so they are retained as metadata without adding dead graph links.
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
)

TEMPLATE = "base\\fx\\_shaders\\crystal_dome_opaque.mt"

_SCALAR_DEFAULTS = {
    "EmissiveEV": 10.0,  # 0.0 .. 10.0
    "EmissiveEVRaytracingBias": 0.0,  # -10.0 .. 10.0
    "EmissiveDirectionality": 0.0,  # 0.0 .. 1.0
    "EnableRaytracedEmissive": 0.0,  # 0.0 .. 1.0
    "InitialTime": 0.49565199,  # 0.0 .. 1.0
    "MaxTimeOffset": 0.326086998,  # 0.0 .. 1.0
    "SwipeAngle": 0.0,  # 0.0 .. 1.0
    "UVDivision": 500.0,  # 0.0 .. 500.0
    "NoiseMax": 0.0,  # 0.0 .. 1.0
    "DebugValue": 0.0,  # 0.0 .. 1.0
    "Debug": 0.0,  # 0.0 .. 1.0
    "UVDivision_FluffMask": 1.0,  # 0.0 .. 1000.0
    "MinUV": 0.0,  # -5.0 .. 5.0
    "MaxUV": 1.0,  # -5.0 .. 5.0
    "DistortionScale": 2.0,  # retained as metadata only
}

_PRIMARY_GLOW = (0.0, 159.0 / 255.0, 1.0, 1.0)
_SECONDARY_GLOW = (193.0 / 255.0, 140.0 / 255.0, 0.0, 1.0)
_TILING = (5.0, 5.0, 10.0, 10.0)


def _step(nodes, links, name, location, edge, source):
    """Build a zero-width threshold using a Map Range node"""
    node = new_labeled_node(nodes, "ShaderNodeMapRange", name, location)
    node.inputs["From Min"].default_value = float(edge)
    node.inputs["From Max"].default_value = float(edge) + 1.0e-6
    node.inputs["To Min"].default_value = 0.0
    node.inputs["To Max"].default_value = 1.0
    node.clamp = True
    links.new(source, node.inputs["Value"])
    return node.outputs["Result"]


class CrystalDomeOpaque(MaterialTypeBase):
    def _runtime_params(self, nodes, links, data):
        """t and g from the MM_MaterialParams slots, blended with the Debug override"""
        param0 = value_socket(
            nodes,
            "CP77 MaterialParam0",
            1.0,
            (-3000, 700),
            "MaterialParam0 (reveal time)",
        )
        param1 = value_socket(
            nodes,
            "CP77 MaterialParam1",
            1.0,
            (-3000, 580),
            "MaterialParam1 (glitch gate)",
        )
        debug = clamp01(param_float(data, "Debug", 0.0))
        debug_value = param_float(data, "DebugValue", 0.0)
        noise_max = param_float(data, "NoiseMax", 0.0)

        # Debug is authored per-material, so the two lerps resolve at build time.
        time_source = (
            param0
            if debug <= 0.0
            else value_socket(
                nodes,
                "Debug Time",
                debug_value,
                (-2820, 700),
                "DebugValue override",
            )
        )
        reveal = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time_source,
            2.0,
            name="t = Param0 x 2",
            location=(-2640, 700),
        )
        if debug <= 0.0:
            gate = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                param1,
                noise_max,
                name="g = Param1 x NoiseMax",
                location=(-2640, 580),
            )
        else:
            gate = value_socket(
                nodes, "g = NoiseMax", noise_max, (-2640, 580), "Debug glitch gate"
            )
        return reveal, gate

    def _glitch(self, nodes, links, data, uv_split, gate, time_socket):
        """The glitch result, scaled to zero while g is off"""
        uv_x = uv_split.outputs["X"]
        uv_y = uv_split.outputs["Y"]
        division = max(1.0e-4, param_float(data, "UVDivision", 500.0))

        change_seed = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time_socket,
            3.0,
            name="Time x 3",
            location=(-2640, 300),
        )
        change_floor = shader_nodes.math(
            nodes, links, "FLOOR", change_seed, name="floor", location=(-2470, 300)
        )
        change_hash = white_noise_socket(
            nodes, links, "hash11 Change", (-2300, 300), change_floor
        )
        change_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            change_hash,
            division,
            name="x UVDivision",
            location=(-2130, 300),
        )
        change_step = shader_nodes.math(
            nodes, links, "FLOOR", change_scaled, name="floor", location=(-1960, 300)
        )
        change_chance = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            change_step,
            division,
            name="/ UVDivision",
            location=(-1790, 300),
        )

        shifted_x = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            uv_x,
            change_chance,
            name="UV.x - Change",
            location=(-1620, 300),
        )
        rect_a = self._quantised_pair_hash(
            nodes, links, "Rect A", (-1450, 300), shifted_x, uv_y, division
        )
        rect_b = self._quantised_pair_hash(
            nodes, links, "Rect B", (-1450, 140), shifted_x, uv_y, division * 0.25
        )
        rect = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            rect_a,
            rect_b,
            name="Rect A x B",
            location=(-960, 220),
        )

        added_x = shader_nodes.math(
            nodes,
            links,
            "ADD",
            uv_x,
            change_chance,
            name="UV.x + Change",
            location=(-1620, -20),
        )
        unoise_seed = self._pair_hash(
            nodes, links, "UNoise Seed", (-1450, -20), added_x, uv_y, division * 0.05
        )
        rect_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            rect,
            unoise_seed,
            name="Rect x Seed",
            location=(-790, 220),
        )
        rect_signed = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            rect_scaled,
            2.0,
            name="Rect to signed",
            location=(-620, 220),
        )
        rect_signed_node = rect_signed.node
        shader_nodes.socket_by_identifier(
            rect_signed_node.inputs, "Value_002"
        ).default_value = -1.0

        vertical_time = self._quantised_time(
            nodes, links, time_socket, 10.357, (-2640, -200)
        )
        vertical_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            uv_x,
            division,
            name="UV.x x UVDivision",
            location=(-1960, -200),
        )
        vertical_tenth = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            vertical_scaled,
            10.0,
            name="/10",
            location=(-1790, -200),
        )
        vertical_floor = shader_nodes.math(
            nodes, links, "FLOOR", vertical_tenth, name="floor", location=(-1620, -200)
        )
        vertical_key = shader_nodes.math(
            nodes,
            links,
            "ADD",
            vertical_floor,
            vertical_time,
            name="+ GlitchTime",
            location=(-1450, -200),
        )
        vertical = white_noise_socket(
            nodes, links, "hash11 Vertical", (-1280, -200), vertical_key
        )

        horizontal_time = self._quantised_time(
            nodes, links, time_socket, 2.429, (-2640, -420)
        )
        seeded_y = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            unoise_seed,
            0.05,
            name="UV.y + Seed x 0.05",
            location=(-1960, -420),
        )
        shader_nodes.socket_by_identifier(
            seeded_y.node.inputs, "Value_002"
        ).default_value = 0.0
        offset_y = shader_nodes.math(
            nodes,
            links,
            "ADD",
            uv_y,
            seeded_y,
            name="UV.y + Offset",
            location=(-1790, -420),
        )
        horizontal_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset_y,
            division,
            name="x UVDivision",
            location=(-1620, -420),
        )
        horizontal_floor = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            horizontal_scaled,
            name="floor",
            location=(-1450, -420),
        )
        horizontal_key = shader_nodes.math(
            nodes,
            links,
            "ADD",
            horizontal_floor,
            horizontal_time,
            name="+ GlitchTime",
            location=(-1280, -420),
        )
        horizontal_hash = white_noise_socket(
            nodes, links, "hash11 Horizontal", (-1110, -420), horizontal_key
        )

        gate_y = shader_nodes.math(
            nodes, links, "ADD", uv_y, 5.0, name="UV.y + 5", location=(-1620, -580)
        )
        gate_hash = self._pair_hash(
            nodes,
            links,
            "Horizontal Gate",
            (-1450, -580),
            added_x,
            gate_y,
            division * 0.55,
        )
        gate_step = _step(
            nodes, links, "step(0.25, Gate)", (-1110, -580), 0.25, gate_hash
        )
        horizontal_gated = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            horizontal_hash,
            gate_step,
            name="Horizontal x Gate",
            location=(-940, -420),
        )
        rect_unit = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            rect_signed,
            0.5,
            name="(Rect + 1) / 2",
            location=(-940, -580),
        )
        shader_nodes.socket_by_identifier(
            rect_unit.node.inputs, "Value_002"
        ).default_value = 0.5
        horizontal = shader_nodes.math(
            nodes,
            links,
            "ADD",
            horizontal_gated,
            rect_unit,
            name="Horizontal Noise",
            location=(-770, -420),
        )

        offset_key = shader_nodes.math(
            nodes,
            links,
            "ADD",
            uv_y,
            rect_signed,
            name="UV.y + Rect",
            location=(-450, 220),
        )
        offset_scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset_key,
            division,
            name="x UVDivision",
            location=(-280, 220),
        )
        offset_half = shader_nodes.math(
            nodes, links, "DIVIDE", offset_scaled, 2.0, name="/2", location=(-110, 220)
        )
        offset_floor = shader_nodes.math(
            nodes, links, "FLOOR", offset_half, name="floor", location=(60, 220)
        )
        offset_hash = white_noise_socket(
            nodes, links, "hash11 UNoise", (230, 220), offset_floor
        )
        offset_signed = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            offset_hash,
            0.5,
            name="saturate - 0.5",
            location=(400, 220),
        )
        unoise_x = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset_signed,
            gate,
            name="UNoise.x x g",
            location=(570, 220),
        )
        return unoise_x, horizontal, vertical

    def _quantised_time(self, nodes, links, time_socket, rate, location):
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
            name="floor",
            location=(location[0] + 170, location[1]),
        )
        return shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            stepped,
            rate,
            name=f"/ {rate}",
            location=(location[0] + 340, location[1]),
        )

    def _pair_hash(self, nodes, links, name, location, x_socket, y_socket, scale):
        """Build the deterministic pair hash from independently floored scaled UV components"""
        scaled_x = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            x_socket,
            scale,
            name=f"{name} x",
            location=location,
        )
        scaled_y = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            y_socket,
            scale,
            name=f"{name} y",
            location=(location[0], location[1] - 120),
        )
        floor_x = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            scaled_x,
            name=f"{name} floor x",
            location=(location[0] + 170, location[1]),
        )
        floor_y = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            scaled_y,
            name=f"{name} floor y",
            location=(location[0] + 170, location[1] - 120),
        )
        combine = new_labeled_node(
            nodes,
            "ShaderNodeCombineXYZ",
            f"{name} Key",
            (location[0] + 340, location[1] - 60),
        )
        links.new(floor_x, combine.inputs["X"])
        links.new(floor_y, combine.inputs["Y"])
        return white_noise_socket(
            nodes,
            links,
            name,
            (location[0] + 510, location[1] - 60),
            combine.outputs["Vector"],
            dimensions="2D",
        )

    def _quantised_pair_hash(
        self, nodes, links, name, location, x_socket, y_socket, scale
    ):
        """Apply ten-step quantisation to the hash value"""
        raw = self._pair_hash(nodes, links, name, location, x_socket, y_socket, scale)
        scaled = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            raw,
            10.0,
            name=f"{name} x10",
            location=(location[0] + 680, location[1] - 60),
        )
        floored = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            scaled,
            name=f"{name} floor",
            location=(location[0] + 850, location[1] - 60),
        )
        return shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            floored,
            10.0,
            name=f"{name} /10",
            location=(location[0] + 1020, location[1] - 60),
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        tiling = param_vector(data, "Tiling", _TILING)
        time = create_scene_time_value(tree, -3000, 840, "CP77 Crystal Dome Time")
        time_socket = time.outputs["Value"]
        reveal, gate = self._runtime_params(nodes, links, data)

        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-3000, 60))
        uv_split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "UV.x / UV.y", (-2820, 60)
        )
        links.new(uv.outputs["UV"], uv_split.inputs["Vector"])

        unoise_x, horizontal, vertical = self._glitch(
            nodes, links, data, uv_split, gate, time_socket
        )

        base_offset = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "UNoise", (740, 220)
        )
        links.new(unoise_x, base_offset.inputs["X"])
        base_mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "UV x Tiling.xy", (920, 60)
        )
        links.new(uv.outputs["UV"], base_mapping.inputs["Vector"])
        links.new(base_offset.outputs["Vector"], base_mapping.inputs["Location"])
        base_mapping.inputs["Scale"].default_value = (tiling[0], tiling[1], 1.0)
        base_uv = base_mapping.outputs["Vector"]

        base_color = self._parameter_texture_node(
            nodes,
            links,
            data,
            "BaseColor",
            (1140, 420),
            base_uv,
            error_label="crystal dome opaque",
        )
        metalness = self._parameter_texture_node(
            nodes,
            links,
            data,
            "Metalness",
            (1140, 160),
            base_uv,
            non_color=True,
            error_label="crystal dome opaque",
        )
        roughness = self._parameter_texture_node(
            nodes,
            links,
            data,
            "Roughness",
            (1140, -100),
            base_uv,
            non_color=True,
            error_label="crystal dome opaque",
        )
        # Retain the sampled value for parity with the exported material contract.
        self._parameter_texture_node(
            nodes,
            links,
            data,
            "Normal",
            (1140, -360),
            base_uv,
            non_color=True,
            error_label="crystal dome opaque",
        )

        clamped = shader_nodes.clamp(
            nodes,
            links,
            unoise_x,
            0.03,
            1.0,
            name="clamp(UNoise.x, 0.03, 1)",
            location=(1400, 620),
        )
        darken = new_labeled_node(
            nodes, "ShaderNodeMapRange", "lerp(1, UNoise.x, UNoise.x)", (1740, 620)
        )
        darken.inputs["From Min"].default_value = 0.0
        darken.inputs["From Max"].default_value = 1.0
        darken.inputs["To Min"].default_value = 1.0
        links.new(clamped, darken.inputs["Value"])
        links.new(clamped, darken.inputs["To Max"])
        darken_socket = darken.outputs["Result"]
        shaded_base = mix_color_socket(
            nodes,
            links,
            "BaseColor x UNoise",
            base_color.outputs["Color"],
            darken_socket,
            1.0,
            (1960, 420),
            blend_type="MULTIPLY",
        )

        fluff_division = param_float(data, "UVDivision_FluffMask", 1.0)
        max_uv = param_float(data, "MaxUV", 1.0)
        min_uv = param_float(data, "MinUV", 0.0)
        vertical_offset = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            vertical,
            param_float(data, "NoiseMax", 0.0) * 0.05,
            name="verticalNoise x NoiseMax x 0.05",
            location=(740, -200),
        )
        fluff_mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "FluffMask UV", (920, -200)
        )
        links.new(uv.outputs["UV"], fluff_mapping.inputs["Vector"])
        fluff_mapping.inputs["Scale"].default_value = (
            fluff_division,
            fluff_division * max_uv,
            1.0,
        )
        fluff_y = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            vertical_offset,
            min_uv,
            name="UNoise.y - MinUV",
            location=(740, -320),
        )
        fluff_offset = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Fluff Offset", (920, -320)
        )
        fluff_offset.inputs["X"].default_value = 0.0
        links.new(fluff_y, fluff_offset.inputs["Y"])
        links.new(fluff_offset.outputs["Vector"], fluff_mapping.inputs["Location"])
        fluff_mask = self._parameter_texture_node(
            nodes,
            links,
            data,
            "FluffMask",
            (1140, -620),
            fluff_mapping.outputs["Vector"],
            error_label="crystal dome opaque",
        )
        fluff_split = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "FluffMask.xy", (1400, -620)
        )
        links.new(
            fluff_mask.outputs["Color"],
            fluff_split.inputs["Color"],
        )
        fluff_r = fluff_split.outputs["Red"]
        fluff_g = fluff_split.outputs["Green"]

        initial_time = max(
            1.0e-4, param_float(data, "InitialTime", _SCALAR_DEFAULTS["InitialTime"])
        )
        fluff_time = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            reveal,
            initial_time,
            name="fluffTime",
            location=(1570, -760),
            use_clamp=True,
        )
        fluff_step = _step(
            nodes, links, "step(0.65, FluffMask.x)", (1570, -620), 0.65, fluff_r
        )
        fluff_reveal = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fluff_step,
            fluff_time,
            name="FluffMask x fluffTime",
            location=(1740, -620),
        )

        swipe_time = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            reveal,
            initial_time,
            name="t - InitialTime",
            location=(1570, -900),
        )
        swipe_time = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            swipe_time,
            max(1.0e-4, 1.0 - initial_time),
            name="swipeTime",
            location=(1740, -900),
        )

        # PatternMask tiling widens where the fluff mask is set.
        pattern_scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            fluff_reveal,
            3.0,
            name="FluffMask x 3 + 1",
            location=(1960, -620),
        )
        shader_nodes.socket_by_identifier(
            pattern_scale.node.inputs, "Value_002"
        ).default_value = 1.0
        pattern_scale_x = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            pattern_scale,
            tiling[2],
            name="x Tiling.z",
            location=(2130, -620),
        )
        pattern_scale_y = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            pattern_scale,
            tiling[3],
            name="x Tiling.w",
            location=(2130, -740),
        )
        pattern_scale_vec = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Pattern Scale", (2300, -680)
        )
        links.new(pattern_scale_x, pattern_scale_vec.inputs["X"])
        links.new(pattern_scale_y, pattern_scale_vec.inputs["Y"])
        pattern_scale_vec.inputs["Z"].default_value = 1.0
        pattern_offset = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Pattern Offset", (2300, -840)
        )
        pattern_offset.inputs["X"].default_value = 0.0
        links.new(vertical_offset, pattern_offset.inputs["Y"])
        pattern_mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "PatternMask UV", (2470, -620)
        )
        links.new(uv.outputs["UV"], pattern_mapping.inputs["Vector"])
        links.new(pattern_offset.outputs["Vector"], pattern_mapping.inputs["Location"])
        links.new(pattern_scale_vec.outputs["Vector"], pattern_mapping.inputs["Scale"])
        pattern = self._parameter_texture_node(
            nodes,
            links,
            data,
            "PatternMask",
            (2660, -620),
            pattern_mapping.outputs["Vector"],
            error_label="crystal dome opaque",
        )
        pattern_r = shader_nodes.math(
            nodes,
            links,
            "ADD",
            pattern.outputs["Color"],
            0.0,
            name="PatternMask.x",
            location=(2900, -620),
        )

        # Blend horizontal and vertical coordinates for the swipe mask.
        centred = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            uv_split.outputs["X"],
            0.5,
            name="UV.x - 0.5",
            location=(1960, -1040),
        )
        centred = shader_nodes.math(
            nodes, links, "ABSOLUTE", centred, name="abs", location=(2130, -1040)
        )
        centred = shader_nodes.math(
            nodes, links, "MULTIPLY", centred, 2.0, name="x2", location=(2300, -1040)
        )
        angle = new_labeled_node(
            nodes, "ShaderNodeMapRange", "lerp by SwipeAngle", (2470, -1040)
        )
        angle.inputs["From Min"].default_value = 0.0
        angle.inputs["From Max"].default_value = 1.0
        angle.inputs["Value"].default_value = clamp01(
            param_float(data, "SwipeAngle", 0.0)
        )
        links.new(centred, angle.inputs["To Min"])
        links.new(uv_split.outputs["Y"], angle.inputs["To Max"])
        angle_socket = angle.outputs["Result"]

        swipe = shader_nodes.math(
            nodes,
            links,
            "ADD",
            pattern_r,
            angle_socket,
            name="Pattern + Angle",
            location=(3070, -620),
        )
        offset_term = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fluff_g,
            param_float(data, "MaxTimeOffset", _SCALAR_DEFAULTS["MaxTimeOffset"]),
            name="MaxTimeOffset x FluffMask.y",
            location=(2900, -900),
        )
        time_term = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            swipe_time,
            offset_term,
            name="swipeTime - Offset",
            location=(3070, -900),
        )
        time_term = shader_nodes.math(
            nodes, links, "MULTIPLY", time_term, 2.0, name="x2", location=(3240, -900)
        )
        swipe = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            swipe,
            time_term,
            name="- Time Term",
            location=(3410, -620),
        )
        swipe = shader_nodes.math(
            nodes,
            links,
            "ADD",
            swipe,
            fluff_reveal,
            name="+ FluffMask.x",
            location=(3580, -620),
        )

        unoise_gate = _step(
            nodes, links, "step(0.15, UNoise.x)", (3410, -420), 0.15, unoise_x
        )
        swipe_final = new_labeled_node(
            nodes, "ShaderNodeMapRange", "lerp(swipe, UNoise.x)", (3750, -620)
        )
        swipe_final.inputs["From Min"].default_value = 0.0
        swipe_final.inputs["From Max"].default_value = 1.0
        links.new(unoise_gate, swipe_final.inputs["Value"])
        links.new(swipe, swipe_final.inputs["To Min"])
        links.new(unoise_x, swipe_final.inputs["To Max"])
        swipe_socket = swipe_final.outputs["Result"]

        primary = param_color(data, "PrimaryGlowColor", _PRIMARY_GLOW)
        secondary = param_color(data, "SecondaryGlowColor", _SECONDARY_GLOW)
        swipe_clamped = shader_nodes.math(
            nodes,
            links,
            "ADD",
            swipe_socket,
            0.0,
            name="saturate(swipe)",
            location=(3940, -620),
            use_clamp=True,
        )
        glow = mix_color_socket(
            nodes, links, "Glow Ramp", secondary, primary, swipe_clamped, (4130, -420)
        )
        glow = mix_color_socket(
            nodes, links, "Glow x fluffTime", secondary, glow, fluff_time, (4300, -420)
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "BaseColor to Glow",
            shaded_base,
            glow,
            fluff_reveal,
            (4470, 120),
        )

        emissive_mask = shader_nodes.math(
            nodes,
            links,
            "POWER",
            fluff_reveal,
            3.0,
            name="FluffMask^3",
            location=(4130, -900),
        )
        horizontal_step = _step(
            nodes, links, "step(0.75, horizontalNoise)", (3940, -1040), 0.75, horizontal
        )
        horizontal_term = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            horizontal_step,
            gate,
            name="x g",
            location=(4130, -1040),
        )
        emissive_mask = shader_nodes.math(
            nodes,
            links,
            "ADD",
            emissive_mask,
            horizontal_term,
            name="Emissive Mask",
            location=(4300, -900),
        )
        emissive_strength = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emissive_mask,
            max(
                0.0,
                ev_to_linear(
                    param_float(data, "EmissiveEV", _SCALAR_DEFAULTS["EmissiveEV"])
                )
                - 1.0,
            ),
            name="Scaled Emissive EV",
            location=(4470, -900),
        )

        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Crystal Dome Opaque", (4760, 120)
        )
        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (5060, 120)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        base_input = find_input(principled, "Base Color")
        if base_input is not None:
            links.new(final_color, base_input)
        emission_color = find_input(principled, "Emission Color", "Emission")
        if emission_color is not None:
            links.new(glow, emission_color)
        emission_input = find_input(principled, "Emission Strength")
        if emission_input is not None:
            links.new(emissive_strength, emission_input)
        metal_split = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "Metalness.r", (4480, -80)
        )
        links.new(metalness.outputs["Color"], metal_split.inputs["Color"])
        rough_split = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "Roughness.r", (4480, -200)
        )
        links.new(roughness.outputs["Color"], rough_split.inputs["Color"])
        metallic_input = find_input(principled, "Metallic")
        if metallic_input is not None:
            links.new(metal_split.outputs["Red"], metallic_input)
        roughness_input = find_input(principled, "Roughness")
        if roughness_input is not None:
            links.new(rough_split.outputs["Red"], roughness_input)
        alpha_input = find_input(principled, "Alpha")
        if alpha_input is not None:
            links.new(swipe_clamped, alpha_input)

        # Use the alpha mask for cutout rendering.
        set_alpha_clip(Mat, 0.5)
        Mat.diffuse_color = (*primary[:3], 1.0)
