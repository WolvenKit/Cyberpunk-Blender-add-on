from .mat_common import (
    MaterialTypeBase,
    clamp01,
    create_scene_time_value,
    find_input,
    lookup_param,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)

from .graph import (
    connect_math as _connect_math,
    math_node as _math,
    mix_color_socket as _mix_color,
    multiply_color_socket as _multiply_color,
    red_channel_socket as _red_channel,
    rgb_socket as _rgb,
    set_alpha_clip as _set_alpha_mode,
    unary_math_socket as _unary_math,
    value_node as _value,
)

_TEMPLATES = {
    "base\\fx\\shaders\\device_diode.mt",
    "base\\fx\\shaders\\device_diode_multi_state.mt",
}

_DEVICE_DEFAULTS = {
    "NormalOffset": 0.0,
    "VehicleDamageInfluence": 1.0,
    "BaseColor": "base\\surfaces\\materials\\common\\plastic_common_01_300_d.xbm",
    "BaseColorScale": (150.0 / 255.0, 0.0, 0.0, 0.0),
    "Metalness": "engine\\textures\\editor\\black.xbm",
    "MetalnessScale": 1.0,
    "MetalnessBias": 0.0,
    "Roughness": "base\\surfaces\\materials\\plastic\\plastic_lightcover\\plastic_lightcover_01_50_r.xbm",
    "RoughnessScale": 1.0,
    "RoughnessBias": 0.0,
    "Normal": "base\\surfaces\\materials\\plastic\\plastic_lightcover\\plastic_lightcover_01_50_n.xbm",
    "Emissive": "base\\fx\\_textures\\masks\\gradients\\fx_reflected_vertical_gradient_01_d.xbm",
    "EmissiveEV": 5.0,
    "AlphaThreshold": 0.330000013,
    "Blinking": 0.0,
    "EmissiveEVRaytracingBias": 0.0,
    "EmissiveDirectionality": 0.0,
    "EnableRaytracedEmissive": 1.0,
    "BlinkingSpeed": 8.0,
    "UseMaterialParameter": 1.0,
    "EmissiveColor1": (127.0 / 255.0, 0.0, 0.0, 1.0),
    "EmissiveColor2": (0.0, 12.0 / 255.0, 127.0 / 255.0, 1.0),
    "EmissiveInitialState": 0.0,
    "UseTwoEmissiveColors": 0.0,
    "SwitchingTwoEmissiveColorsSpeed": 0.0,
    "UseFresnel": 0.0,
}

_MULTI_STATE_DEFAULTS = {
    **_DEVICE_DEFAULTS,
    "VehicleDamageInfluence": 0.0,
    "EmissiveColor3": (1.0, 1.0, 1.0, 1.0),
    "EmissiveColor4": (1.0, 1.0, 1.0, 1.0),
    "EmissiveColorSelector": 1.0,
    "UseTwoEmissiveColors": 0.0,
    "SwitchingTwoEmissiveColorsSpeed": 0.0,
    "UseFresnel": 0.0,
}


def _lerp_float(nodes, links, name, first, second, factor, location):
    difference = _math(
        nodes,
        "SUBTRACT",
        f"{name} Difference",
        (location[0] - 400, location[1]),
    )
    difference_output = _connect_math(links, difference, second, first)
    scaled = _math(
        nodes,
        "MULTIPLY",
        f"{name} Factor",
        (location[0] - 200, location[1]),
    )
    scaled_output = _connect_math(links, scaled, difference_output, factor)
    result = _math(nodes, "ADD", name, location)
    return _connect_math(links, result, first, scaled_output)


def _param_float(data, name, defaults):
    return param_float(data, name, defaults[name])


def _param_color(data, name, defaults):
    return param_color(data, name, defaults[name])


def _param_texture(data, name, defaults):
    return param_texture_path(data, name) or defaults[name]


def _store_metadata(material, data, is_multi_state, defaults):
    template = (
        "base\\fx\\shaders\\device_diode_multi_state.mt"
        if is_multi_state
        else "base\\fx\\shaders\\device_diode.mt"
    )
    material["cp77_device_diode_template"] = template
    material["cp77_device_diode_preview"] = "SOURCE_SHADER_RUNTIME_PREVIEW"
    material["cp77_device_diode_runtime_nodes"] = (
        "MaterialParam0;MaterialParam1;VehicleDamageMagnitude"
    )
    material["cp77_device_diode_viewport_limits"] = (
        "raytracing_controls_are_metadata_only"
    )

    scalar_names = (
        "NormalOffset",
        "VehicleDamageInfluence",
        "MetalnessScale",
        "MetalnessBias",
        "RoughnessScale",
        "RoughnessBias",
        "EmissiveEV",
        "AlphaThreshold",
        "Blinking",
        "BlinkingSpeed",
        "UseMaterialParameter",
        "EmissiveInitialState",
        "EmissiveColorSelector",
        "EmissiveEVRaytracingBias",
        "EmissiveDirectionality",
        "EnableRaytracedEmissive",
        "UseTwoEmissiveColors",
        "SwitchingTwoEmissiveColorsSpeed",
        "UseFresnel",
    )
    color_names = (
        "BaseColorScale",
        "EmissiveColor1",
        "EmissiveColor2",
        "EmissiveColor3",
        "EmissiveColor4",
    )
    texture_names = ("BaseColor", "Metalness", "Roughness", "Normal", "Emissive")

    for name in scalar_names:
        if name in defaults:
            material[f"cp77_{name}"] = _param_float(data, name, defaults)
    for name in color_names:
        if name in defaults:
            material[f"cp77_{name}"] = list(_param_color(data, name, defaults))
    for name in texture_names:
        material[f"cp77_{name}"] = _param_texture(data, name, defaults)


def _decode_two_channel_normal(nodes, links, color_socket, location):
    separate = new_labeled_node(
        nodes,
        "ShaderNodeSeparateColor",
        "Normal RG",
        location,
    )
    separate.mode = "RGB"
    links.new(color_socket, separate.inputs[0])

    x_scale = _math(nodes, "MULTIPLY", "Normal X Scale", (location[0] + 190, location[1] + 80), second=2.0)
    x_scaled = _connect_math(links, x_scale, separate.outputs["Red"])
    x_bias = _math(nodes, "SUBTRACT", "Normal X Bias", (location[0] + 380, location[1] + 80), second=1.0)
    x = _connect_math(links, x_bias, x_scaled)

    y_scale = _math(nodes, "MULTIPLY", "Normal Y Scale", (location[0] + 190, location[1] - 40), second=2.0)
    y_scaled = _connect_math(links, y_scale, separate.outputs["Green"])
    y_bias = _math(nodes, "SUBTRACT", "Normal Y Bias", (location[0] + 380, location[1] - 40), second=1.0)
    y = _connect_math(links, y_bias, y_scaled)

    x_squared = _math(nodes, "MULTIPLY", "Normal X Squared", (location[0] + 570, location[1] + 80))
    x2 = _connect_math(links, x_squared, x, x)
    y_squared = _math(nodes, "MULTIPLY", "Normal Y Squared", (location[0] + 570, location[1] - 40))
    y2 = _connect_math(links, y_squared, y, y)
    sum_xy = _math(nodes, "ADD", "Normal XY Squared", (location[0] + 760, location[1] + 20))
    xy2 = _connect_math(links, sum_xy, x2, y2)
    z_squared = _math(
        nodes,
        "SUBTRACT",
        "Normal Z Squared",
        (location[0] + 950, location[1] + 20),
        first=1.0,
        clamp=True,
    )
    z2 = _connect_math(links, z_squared, 1.0, xy2)
    z = _unary_math(
        nodes,
        links,
        "SQRT",
        "Reconstruct Normal Z",
        z2,
        (location[0] + 1140, location[1] + 20),
    )
    z_half = _math(nodes, "MULTIPLY", "Encode Normal Z", (location[0] + 1330, location[1] + 20), second=0.5)
    z_half_output = _connect_math(links, z_half, z)
    z_encoded = _math(nodes, "ADD", "Normal Z Offset", (location[0] + 1520, location[1] + 20), second=0.5)
    z_encoded_output = _connect_math(links, z_encoded, z_half_output)

    combine = new_labeled_node(
        nodes,
        "ShaderNodeCombineColor",
        "Reconstructed Normal",
        (location[0] + 1710, location[1]),
    )
    combine.mode = "RGB"
    links.new(separate.outputs["Red"], combine.inputs["Red"])
    links.new(separate.outputs["Green"], combine.inputs["Green"])
    links.new(z_encoded_output, combine.inputs["Blue"])
    return combine.outputs[0]


class DeviceDiode(MaterialTypeBase):
    def _load_image(self, path, *, non_color=False):
        return self._load_relative_image(
            path,
            non_color=non_color,
            error_label="device diode",
        )

    def _texture_node(self, nodes, path, name, location, *, non_color=False):
        image = self._load_image(path, non_color=non_color)
        if image is None:
            return None
        node = new_labeled_node(nodes, "ShaderNodeTexImage", name, location)
        node.image = image
        node.extension = "REPEAT"
        node.interpolation = "Linear"
        return node

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        base_material = str(Mat.get("BaseMaterial", "")).replace("/", "\\").lower()
        is_multi_state = (
            base_material.endswith("device_diode_multi_state.mt")
            or any(
                lookup_param(data, key) is not None
                for key in (
                    "EmissiveColor3",
                    "EmissiveColor4",
                    "EmissiveColorSelector",
                )
            )
        )
        defaults = _MULTI_STATE_DEFAULTS if is_multi_state else _DEVICE_DEFAULTS
        _store_metadata(Mat, data, is_multi_state, defaults)

        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes,
            "ShaderNodeOutputMaterial",
            "Material Output",
            (1700, 180),
        )
        principled = new_labeled_node(
            nodes,
            "ShaderNodeBsdfPrincipled",
            "Device Diode",
            (1420, 180),
        )
        links.new(principled.outputs[0], output.inputs["Surface"])

        base_scale = _param_color(data, "BaseColorScale", defaults)
        metalness_scale = _param_float(data, "MetalnessScale", defaults)
        metalness_bias = _param_float(data, "MetalnessBias", defaults)
        roughness_scale = _param_float(data, "RoughnessScale", defaults)
        roughness_bias = _param_float(data, "RoughnessBias", defaults)
        alpha_threshold = clamp01(_param_float(data, "AlphaThreshold", defaults))
        emissive_ev = max(0.0, _param_float(data, "EmissiveEV", defaults))
        blinking = clamp01(_param_float(data, "Blinking", defaults))
        blinking_speed = _param_float(data, "BlinkingSpeed", defaults)
        use_material_parameter = clamp01(
            _param_float(data, "UseMaterialParameter", defaults)
        )
        initial_state = clamp01(
            _param_float(data, "EmissiveInitialState", defaults)
        )
        normal_offset = _param_float(data, "NormalOffset", defaults)

        base_node = self._texture_node(
            nodes,
            _param_texture(data, "BaseColor", defaults),
            "BaseColor",
            (-1500, 540),
        )
        if base_node is not None:
            sampled_base = base_node.outputs["Color"]
            base_alpha = base_node.outputs["Alpha"]
        else:
            sampled_base = _rgb(
                nodes,
                "BaseColor Fallback",
                (1.0, 1.0, 1.0, 1.0),
                (-1500, 540),
            )
            base_alpha = _value(
                nodes,
                "Base Alpha Fallback",
                1.0,
                (-1500, 450),
            ).outputs[0]

        scaled_base = _multiply_color(
            nodes,
            links,
            "Scaled Base Color",
            sampled_base,
            base_scale,
            (-1180, 540),
        )

        metalness_node = self._texture_node(
            nodes,
            _param_texture(data, "Metalness", defaults),
            "Metalness",
            (-1500, 260),
            non_color=True,
        )
        if metalness_node is not None:
            metalness_source = _red_channel(
                nodes,
                links,
                metalness_node.outputs["Color"],
                "Metalness Red",
                (-1260, 260),
            )
        else:
            metalness_source = 0.0
        metalness_mul = _math(
            nodes,
            "MULTIPLY",
            "Metalness Scale",
            (-1000, 260),
            second=metalness_scale,
        )
        metalness_scaled = _connect_math(links, metalness_mul, metalness_source)
        metalness_add = _math(
            nodes,
            "ADD",
            "Metalness Bias",
            (-780, 260),
            second=metalness_bias,
            clamp=True,
        )
        metalness_output = _connect_math(links, metalness_add, metalness_scaled)
        metalness_socket = find_input(principled, "Metallic")
        if metalness_socket is not None:
            links.new(metalness_output, metalness_socket)

        roughness_node = self._texture_node(
            nodes,
            _param_texture(data, "Roughness", defaults),
            "Roughness",
            (-1500, 60),
            non_color=True,
        )
        if roughness_node is not None:
            roughness_source = _red_channel(
                nodes,
                links,
                roughness_node.outputs["Color"],
                "Roughness Red",
                (-1260, 60),
            )
        else:
            roughness_source = 0.5
        roughness_mul = _math(
            nodes,
            "MULTIPLY",
            "Roughness Scale",
            (-1000, 60),
            second=roughness_scale,
        )
        roughness_scaled = _connect_math(links, roughness_mul, roughness_source)
        roughness_add = _math(
            nodes,
            "ADD",
            "Roughness Bias",
            (-780, 60),
            second=roughness_bias,
            clamp=True,
        )
        roughness_output = _connect_math(links, roughness_add, roughness_scaled)
        roughness_socket = find_input(principled, "Roughness")
        if roughness_socket is not None:
            links.new(roughness_output, roughness_socket)

        normal_node = self._texture_node(
            nodes,
            _param_texture(data, "Normal", defaults),
            "Normal",
            (-1500, -220),
            non_color=True,
        )
        if normal_node is not None:
            reconstructed = _decode_two_channel_normal(
                nodes,
                links,
                normal_node.outputs["Color"],
                (-1260, -220),
            )
            normal_map = new_labeled_node(
                nodes,
                "ShaderNodeNormalMap",
                "Tangent Normal",
                (650, -220),
            )
            links.new(reconstructed, normal_map.inputs["Color"])
            normal_socket = find_input(principled, "Normal")
            if normal_socket is not None:
                links.new(normal_map.outputs["Normal"], normal_socket)

        time_node = create_scene_time_value(
            tree,
            -1500,
            -600,
            "CP77 Device Time",
        )
        time_output = time_node.outputs[0]

        runtime_param0 = _value(
            nodes,
            "CP77 Material Parameter 0",
            0.0,
            (-1500, -760),
            "Editable runtime on/off parameter",
        ).outputs[0]
        material_param = _lerp_float(
            nodes,
            links,
            "Material Parameter State",
            1.0,
            runtime_param0,
            use_material_parameter,
            (-820, -760),
        )
        inverted_param = _math(
            nodes,
            "SUBTRACT",
            "Inverted Material Parameter",
            (-580, -820),
            first=1.0,
        )
        inverted_output = _connect_math(links, inverted_param, 1.0, material_param)
        state_factor = _lerp_float(
            nodes,
            links,
            "Initial Emissive State",
            material_param,
            inverted_output,
            initial_state,
            (-120, -760),
        )

        blink_phase = _math(
            nodes,
            "MULTIPLY",
            "Blink Phase",
            (-1240, -600),
            second=blinking_speed,
        )
        blink_phase_output = _connect_math(links, blink_phase, time_output)
        blink_cos = _unary_math(
            nodes,
            links,
            "COSINE",
            "Blink Cosine",
            blink_phase_output,
            (-1020, -600),
        )
        blink_half = _math(
            nodes,
            "MULTIPLY",
            "Blink Half Range",
            (-800, -600),
            second=0.5,
        )
        blink_half_output = _connect_math(links, blink_half, blink_cos)
        blink_wave = _math(
            nodes,
            "ADD",
            "Blink Wave",
            (-580, -600),
            second=0.5,
        )
        blink_wave_output = _connect_math(links, blink_wave, blink_half_output)
        steady_addition = 1.0 - blinking
        blink_speed_node = _math(
            nodes,
            "ADD",
            "Blinking",
            (-360, -600),
            second=steady_addition,
            clamp=True,
        )
        blink_factor = _connect_math(links, blink_speed_node, blink_wave_output)

        emissive_node = self._texture_node(
            nodes,
            _param_texture(data, "Emissive", defaults),
            "Emissive Mask",
            (-1500, -1000),
            non_color=True,
        )
        if emissive_node is not None:
            emissive_mask = _red_channel(
                nodes,
                links,
                emissive_node.outputs["Color"],
                "Emissive Red",
                (-1260, -1000),
            )
        else:
            emissive_mask = 0.0

        mask_blink = _math(
            nodes,
            "MULTIPLY",
            "Emissive Mask and Blink",
            (-1000, -1000),
        )
        mask_blink_output = _connect_math(
            links,
            mask_blink,
            emissive_mask,
            blink_factor,
        )
        state_mask = _math(
            nodes,
            "MULTIPLY",
            "Emissive Runtime State",
            (-760, -1000),
            clamp=True,
        )
        emissive_factor = _connect_math(
            links,
            state_mask,
            mask_blink_output,
            state_factor,
        )
        if emissive_ev <= 0.0:
            emissive_factor = 0.0

        emissive_colors = [
            _param_color(data, f"EmissiveColor{index}", defaults)
            for index in range(1, 5 if is_multi_state else 3)
        ]
        color_outputs = [
            _rgb(
                nodes,
                f"Emissive Color {index}",
                color,
                (-1180, -1220 - 110 * (index - 1)),
            )
            for index, color in enumerate(emissive_colors, start=1)
        ]

        if is_multi_state:
            authored_selector = clamp01(
                _param_float(data, "EmissiveColorSelector", defaults),
                1.0,
                4.0,
            )
            runtime_param1 = _value(
                nodes,
                "CP77 Material Parameter 1",
                authored_selector,
                (-900, -1450),
                "Editable runtime colour selector",
            ).outputs[0]
            selector_mix = _lerp_float(
                nodes,
                links,
                "Material Parameter Selector",
                authored_selector,
                runtime_param1,
                use_material_parameter,
                (-340, -1450),
            )
            selector_floor = _unary_math(
                nodes,
                links,
                "FLOOR",
                "Floor Emissive Selector",
                selector_mix,
                (-100, -1450),
            )
            selector_min = _math(
                nodes,
                "MAXIMUM",
                "Minimum Emissive Selector",
                (120, -1450),
                second=1.0,
            )
            selector_min_output = _connect_math(links, selector_min, selector_floor)
            selector_max = _math(
                nodes,
                "MINIMUM",
                "Maximum Emissive Selector",
                (340, -1450),
                second=4.0,
            )
            selector = _connect_math(links, selector_max, selector_min_output)

            selected_color = color_outputs[0]
            for threshold, color_output, index in zip(
                (1.5, 2.5, 3.5),
                color_outputs[1:],
                (2, 3, 4),
            ):
                compare = _math(
                    nodes,
                    "GREATER_THAN",
                    f"Selector Is At Least {index}",
                    (560, -1240 - 110 * (index - 2)),
                    second=threshold,
                )
                compare_output = _connect_math(links, compare, selector)
                selected_color = _mix_color(
                    nodes,
                    links,
                    f"Select Emissive Color {index}",
                    selected_color,
                    color_output,
                    compare_output,
                    (800, -1240 - 110 * (index - 2)),
                )
        else:
            use_two_colors = clamp01(
                _param_float(data, "UseTwoEmissiveColors", defaults)
            )
            switching_speed = _param_float(
                data,
                "SwitchingTwoEmissiveColorsSpeed",
                defaults,
            )
            switch_phase = _math(
                nodes,
                "MULTIPLY",
                "Two Color Phase",
                (-900, -1390),
                second=switching_speed,
            )
            switch_phase_output = _connect_math(links, switch_phase, time_output)
            switch_sine = _unary_math(
                nodes,
                links,
                "SINE",
                "Two Color Sine",
                switch_phase_output,
                (-680, -1390),
            )
            switch_half = _math(
                nodes,
                "MULTIPLY",
                "Two Color Half Range",
                (-460, -1390),
                second=0.5,
            )
            switch_half_output = _connect_math(links, switch_half, switch_sine)
            switch_offset = _math(
                nodes,
                "ADD",
                "Two Color Offset",
                (-240, -1390),
                second=0.5,
            )
            switch_wave = _connect_math(links, switch_offset, switch_half_output)
            switch_enable = _math(
                nodes,
                "MULTIPLY",
                "Use Two Emissive Colors",
                (-20, -1390),
                second=use_two_colors,
            )
            color_factor = _connect_math(links, switch_enable, switch_wave)
            selected_color = _mix_color(
                nodes,
                links,
                "Select Emissive Color",
                color_outputs[0],
                color_outputs[1],
                color_factor,
                (240, -1280),
            )

        emissive_tinted_base = _multiply_color(
            nodes,
            links,
            "Emissive Tinted Base",
            sampled_base,
            selected_color,
            (600, 470),
        )
        final_base = _mix_color(
            nodes,
            links,
            "Final Base Color",
            scaled_base,
            emissive_tinted_base,
            emissive_factor,
            (900, 470),
        )

        damage_gate = None
        if not is_multi_state:
            damage_influence = clamp01(
                _param_float(data, "VehicleDamageInfluence", defaults)
            )
            damage_preview = _value(
                nodes,
                "CP77 Vehicle Damage Magnitude",
                0.0,
                (360, 720),
                "Editable vehicle damage preview",
            ).outputs[0]
            damage_scaled = _math(
                nodes,
                "MULTIPLY",
                "Vehicle Damage Influence",
                (580, 720),
                second=damage_influence,
            )
            damage_value = _connect_math(links, damage_scaled, damage_preview)
            damage_compare = _math(
                nodes,
                "GREATER_THAN",
                "Vehicle Damage Threshold",
                (800, 720),
                second=0.332999999,
            )
            damage_gate = _connect_math(links, damage_compare, damage_value)
            damage_tint = _mix_color(
                nodes,
                links,
                "Vehicle Damage Darkening",
                (1.0, 1.0, 1.0, 1.0),
                (0.25, 0.25, 0.25, 1.0),
                damage_gate,
                (1020, 680),
            )
            final_base = _multiply_color(
                nodes,
                links,
                "Damaged Base Color",
                final_base,
                damage_tint,
                (1210, 470),
            )

        base_color_socket = find_input(principled, "Base Color")
        if base_color_socket is not None:
            links.new(final_base, base_color_socket)
        Mat.diffuse_color = (*base_scale[:3], 1.0)

        ev_strength = (
            max(0.0, min(65536.0, 2.0 ** max(-16.0, min(16.0, emissive_ev))))
            if emissive_ev > 0.0
            else 0.0
        )
        ev_scale = _math(
            nodes,
            "MULTIPLY",
            "Scale Emissive EV",
            (900, -900),
            second=ev_strength,
        )
        emission_strength = _connect_math(links, ev_scale, emissive_factor)

        if not is_multi_state:
            use_fresnel = clamp01(_param_float(data, "UseFresnel", defaults))
            layer_weight = new_labeled_node(
                nodes,
                "ShaderNodeLayerWeight",
                "View Facing",
                (660, -760),
            )
            facing_power = _math(
                nodes,
                "POWER",
                "Facing Power 4",
                (880, -760),
                second=4.0,
            )
            facing4 = _connect_math(
                links,
                facing_power,
                layer_weight.outputs["Facing"],
            )
            fresnel_factor = _lerp_float(
                nodes,
                links,
                "Use Fresnel",
                1.0,
                facing4,
                use_fresnel,
                (1320, -760),
            )
            fresnel_mul = _math(
                nodes,
                "MULTIPLY",
                "Fresnel Emissive",
                (1500, -900),
            )
            emission_strength = _connect_math(
                links,
                fresnel_mul,
                emission_strength,
                fresnel_factor,
            )

        if damage_gate is not None:
            damage_off = _math(
                nodes,
                "SUBTRACT",
                "Disable Damaged Emissive",
                (1280, -1020),
                first=1.0,
            )
            damage_emission = _connect_math(
                links,
                damage_off,
                1.0,
                damage_gate,
            )
            damage_mul = _math(
                nodes,
                "MULTIPLY",
                "Vehicle Damage Emissive",
                (1500, -1020),
            )
            emission_strength = _connect_math(
                links,
                damage_mul,
                emission_strength,
                damage_emission,
            )

        emission_color_socket = find_input(principled, "Emission Color", "Emission")
        if emission_color_socket is not None:
            links.new(final_base, emission_color_socket)
        emission_strength_socket = find_input(principled, "Emission Strength")
        if emission_strength_socket is not None:
            links.new(emission_strength, emission_strength_socket)

        alpha_socket = find_input(principled, "Alpha")
        if alpha_socket is not None:
            if alpha_threshold > 0.0:
                alpha_compare = _math(
                    nodes,
                    "GREATER_THAN",
                    "Alpha Threshold",
                    (900, 180),
                    second=alpha_threshold,
                )
                alpha_output = _connect_math(links, alpha_compare, base_alpha)
                links.new(alpha_output, alpha_socket)
            else:
                links.new(base_alpha, alpha_socket)
        if alpha_threshold > 0.0:
            _set_alpha_mode(Mat, alpha_threshold)

        if abs(normal_offset) > 1e-12 and output.inputs.get("Displacement") is not None:
            camera = new_labeled_node(
                nodes,
                "ShaderNodeCameraData",
                "Camera Distance",
                (-620, -220),
            )
            distance_offset = _math(
                nodes,
                "SUBTRACT",
                "Distance Minus 0.5",
                (-400, -220),
                second=0.5,
            )
            distance_value = _connect_math(
                links,
                distance_offset,
                camera.outputs["View Distance"],
            )
            positive_distance = _math(
                nodes,
                "MAXIMUM",
                "Positive Camera Distance",
                (-180, -220),
                second=0.0,
            )
            positive_output = _connect_math(links, positive_distance, distance_value)
            offset_scale = _math(
                nodes,
                "MULTIPLY",
                "Normal Offset",
                (40, -220),
                second=normal_offset,
            )
            offset_output = _connect_math(links, offset_scale, positive_output)
            displacement = new_labeled_node(
                nodes,
                "ShaderNodeDisplacement",
                "Device Diode Normal Offset",
                (260, -220),
            )
            displacement.inputs["Midlevel"].default_value = 0.0
            displacement.inputs["Scale"].default_value = 1.0
            links.new(offset_output, displacement.inputs["Height"])
            links.new(displacement.outputs[0], output.inputs["Displacement"])
