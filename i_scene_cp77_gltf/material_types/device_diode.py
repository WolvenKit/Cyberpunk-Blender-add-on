import math

from ..main.common import imageFromRelPath

from .mat_common import (
    clamp01,
    create_scene_time_value,
    find_input,
    lookup_param,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    set_non_color,
)


_TEMPLATES = {
    "base\\fx\\shaders\\device_diode.mt",
    "base\\fx\\shaders\\device_diode_multi_state.mt",
}


def _set_alpha_mode(material, threshold):
    if threshold <= 0.0:
        return
    if hasattr(material, "surface_render_method"):
        try:
            material.surface_render_method = "DITHERED"
        except (TypeError, ValueError):
            pass
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "CLIP"
        except (TypeError, ValueError):
            pass
    if hasattr(material, "alpha_threshold"):
        material.alpha_threshold = threshold


def _mix_color(nodes, links, name, first, second, factor, location):
    mix = new_labeled_node(nodes, "ShaderNodeMixRGB", name, location)
    mix.blend_type = "MIX"
    mix.inputs[0].default_value = clamp01(factor) if isinstance(factor, (int, float)) else 0.0
    if hasattr(first, "is_output"):
        links.new(first, mix.inputs[1])
    else:
        mix.inputs[1].default_value = first
    if hasattr(second, "is_output"):
        links.new(second, mix.inputs[2])
    else:
        mix.inputs[2].default_value = second
    if hasattr(factor, "is_output"):
        links.new(factor, mix.inputs[0])
    return mix.outputs[0]


def _math(nodes, operation, name, location, first=None, second=None, clamp=False):
    node = new_labeled_node(nodes, "ShaderNodeMath", name, location)
    node.operation = operation
    node.use_clamp = clamp
    if first is not None and not hasattr(first, "is_output"):
        node.inputs[0].default_value = float(first)
    if second is not None and not hasattr(second, "is_output"):
        node.inputs[1].default_value = float(second)
    return node


def _connect_math(links, node, first=None, second=None):
    if hasattr(first, "is_output"):
        links.new(first, node.inputs[0])
    elif first is not None:
        node.inputs[0].default_value = float(first)
    if hasattr(second, "is_output"):
        links.new(second, node.inputs[1])
    elif second is not None:
        node.inputs[1].default_value = float(second)
    return node.outputs[0]


def _rgb(nodes, name, color, location):
    node = new_labeled_node(nodes, "ShaderNodeRGB", name, location)
    node.outputs[0].default_value = color
    return node.outputs[0]


def _value(nodes, name, value, location):
    node = new_labeled_node(nodes, "ShaderNodeValue", name, location)
    node.outputs[0].default_value = float(value)
    return node


def _store_metadata(material, data, is_multi_state):
    material["cp77_device_diode_template"] = (
        "base\\fx\\shaders\\device_diode_multi_state.mt"
        if is_multi_state else "base\\fx\\shaders\\device_diode.mt"
    )
    material["cp77_device_diode_preview"] = "EDITABLE_STATE_AND_FRAME_TIME_APPROXIMATION"

    scalar_names = (
        "NormalOffset", "VehicleDamageInfluence", "MetalnessScale", "MetalnessBias",
        "RoughnessScale", "RoughnessBias", "EmissiveEV", "AlphaThreshold",
        "Blinking", "BlinkingSpeed", "UseMaterialParameter", "EmissiveInitialState",
        "EmissiveColorSelector", "EmissiveEVRaytracingBias", "EmissiveDirectionality",
        "EnableRaytracedEmissive", "UseTwoEmissiveColors",
        "SwitchingTwoEmissiveColorsSpeed", "UseFresnel",
    )
    color_names = ("BaseColorScale", "EmissiveColor1", "EmissiveColor2", "EmissiveColor3", "EmissiveColor4")
    texture_names = ("BaseColor", "Metalness", "Roughness", "Normal", "Emissive")

    defaults = {
        "VehicleDamageInfluence": 0.0,
        "MetalnessScale": 1.0,
        "RoughnessScale": 1.0,
        "EmissiveEV": 0.0,
        "EmissiveColorSelector": 1.0,
    }
    for name in scalar_names:
        material[f"cp77_{name}"] = param_float(data, name, defaults.get(name, 0.0))
    for name in color_names:
        material[f"cp77_{name}"] = list(param_color(data, name, (1.0, 1.0, 1.0, 1.0)))
    for name in texture_names:
        material[f"cp77_{name}"] = param_texture_path(data, name)


class DeviceDiode:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def _load_image(self, path, *, non_color=False):
        if not path:
            return None
        try:
            image = imageFromRelPath(
                path,
                self.image_format,
                isNormal=non_color,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
        except Exception as exc:
            print(f"Failed to load device diode texture {path}: {exc}")
            return None
        if non_color:
            set_non_color(image)
        return image

    def _texture_node(self, nodes, path, name, location, *, non_color=False):
        image = self._load_image(path, non_color=non_color)
        if image is None:
            return None
        node = new_labeled_node(nodes, "ShaderNodeTexImage", name, location)
        node.image = image
        return node

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        is_multi_state = any(
            lookup_param(data, key) is not None
            for key in ("EmissiveColor3", "EmissiveColor4", "EmissiveColorSelector")
        )
        _store_metadata(Mat, data, is_multi_state)

        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(nodes, "ShaderNodeOutputMaterial", "Material Output", (1120, 120))
        principled = new_labeled_node(nodes, "ShaderNodeBsdfPrincipled", "Device Diode", (840, 120))
        links.new(principled.outputs[0], output.inputs["Surface"])

        base_scale = param_color(data, "BaseColorScale", (1.0, 1.0, 1.0, 1.0))
        emissive_colors = [
            param_color(data, f"EmissiveColor{index}", (1.0, 1.0, 1.0, 1.0))
            for index in range(1, 5)
        ]
        metallic_scale = param_float(data, "MetalnessScale", 1.0)
        metallic_bias = param_float(data, "MetalnessBias", 0.0)
        roughness_scale = param_float(data, "RoughnessScale", 1.0)
        roughness_bias = param_float(data, "RoughnessBias", 0.0)
        alpha_threshold = clamp01(param_float(data, "AlphaThreshold", 0.0))
        emissive_ev = param_float(data, "EmissiveEV", 0.0)
        blinking = clamp01(param_float(data, "Blinking", 0.0))
        blinking_speed = max(0.0, param_float(data, "BlinkingSpeed", 0.0))
        switching_speed = max(0.0, param_float(data, "SwitchingTwoEmissiveColorsSpeed", 0.0))
        initial_state = clamp01(param_float(data, "EmissiveInitialState", 1.0))
        use_two_colors = clamp01(param_float(data, "UseTwoEmissiveColors", 0.0))
        use_fresnel = clamp01(param_float(data, "UseFresnel", 0.0))
        directionality = clamp01(param_float(data, "EmissiveDirectionality", 0.0))
        selector = clamp01(param_float(data, "EmissiveColorSelector", 1.0), 1.0, 4.0)

        base_node = self._texture_node(
            nodes, param_texture_path(data, "BaseColor"), "BaseColor", (-920, 430)
        )
        if base_node is not None:
            base_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Base Color Scale", (-620, 430))
            base_mix.blend_type = "MULTIPLY"
            base_mix.inputs[0].default_value = 1.0
            base_mix.inputs[2].default_value = base_scale
            links.new(base_node.outputs["Color"], base_mix.inputs[1])
            base_color_output = base_mix.outputs[0]
        else:
            base_color_output = _rgb(nodes, "Base Color Scale", base_scale, (-620, 430))
        base_color_socket = find_input(principled, "Base Color")
        if base_color_socket is not None:
            links.new(base_color_output, base_color_socket)
        Mat.diffuse_color = (*base_scale[:3], 1.0)

        metallic_node = self._texture_node(
            nodes, param_texture_path(data, "Metalness"), "Metalness", (-920, 220), non_color=True
        )
        metallic_source = metallic_node.outputs["Color"] if metallic_node is not None else 0.0
        metallic_mul = _math(nodes, "MULTIPLY", "Metalness Scale", (-620, 220), second=metallic_scale)
        metallic_scaled = _connect_math(links, metallic_mul, metallic_source)
        metallic_add = _math(nodes, "ADD", "Metalness Bias", (-410, 220), second=metallic_bias, clamp=True)
        metallic_output = _connect_math(links, metallic_add, metallic_scaled)
        metallic_socket = find_input(principled, "Metallic")
        if metallic_socket is not None:
            links.new(metallic_output, metallic_socket)

        roughness_node = self._texture_node(
            nodes, param_texture_path(data, "Roughness"), "Roughness", (-920, 20), non_color=True
        )
        roughness_source = roughness_node.outputs["Color"] if roughness_node is not None else 0.5
        roughness_mul = _math(nodes, "MULTIPLY", "Roughness Scale", (-620, 20), second=roughness_scale)
        roughness_scaled = _connect_math(links, roughness_mul, roughness_source)
        roughness_add = _math(nodes, "ADD", "Roughness Bias", (-410, 20), second=roughness_bias, clamp=True)
        roughness_output = _connect_math(links, roughness_add, roughness_scaled)
        roughness_socket = find_input(principled, "Roughness")
        if roughness_socket is not None:
            links.new(roughness_output, roughness_socket)

        normal_node = self._texture_node(
            nodes, param_texture_path(data, "Normal"), "Normal", (-920, -180), non_color=True
        )
        if normal_node is not None:
            normal_map = new_labeled_node(nodes, "ShaderNodeNormalMap", "Normal Map", (-620, -180))
            links.new(normal_node.outputs["Color"], normal_map.inputs["Color"])
            normal_socket = find_input(principled, "Normal")
            if normal_socket is not None:
                links.new(normal_map.outputs["Normal"], normal_socket)

        state_node = _value(nodes, "CP77 Emissive State", initial_state, (-930, -530))
        state_node.label = "Editable runtime state preview"
        state_output = state_node.outputs[0]

        color_outputs = [
            _rgb(nodes, f"Emissive Color {index}", color, (-910, -760 - 90 * (index - 1)))
            for index, color in enumerate(emissive_colors, start=1)
        ]
        if is_multi_state:
            selector_node = _value(nodes, "CP77 Emissive Color Selector", selector, (-680, -860))
            selected = color_outputs[0]
            for threshold, color_output, y in zip((1.5, 2.5, 3.5), color_outputs[1:], (-760, -850, -940)):
                compare = _math(nodes, "GREATER_THAN", f"Selector > {threshold}", (-470, y), second=threshold)
                factor = _connect_math(links, compare, selector_node.outputs[0])
                selected = _mix_color(nodes, links, f"Select Emissive Color {int(threshold + 0.5)}", selected, color_output, factor, (-240, y))
        else:
            color_factor = state_output
            if switching_speed > 1e-6:
                switch_time = create_scene_time_value(tree, -700, -900, "CP77 Device Time").outputs[0]
                switch_angle = _math(
                    nodes, "MULTIPLY", "Two Color Switching Speed", (-500, -900),
                    second=switching_speed * math.tau,
                )
                switch_phase = _connect_math(links, switch_angle, switch_time)
                switch_sine = _math(nodes, "SINE", "Two Color Switching", (-300, -900))
                switch_wave = _connect_math(links, switch_sine, switch_phase)
                switch_scale = _math(nodes, "MULTIPLY", "Two Color Range", (-100, -900), second=0.5)
                switch_half = _connect_math(links, switch_scale, switch_wave)
                switch_add = _math(nodes, "ADD", "Two Color Offset", (100, -900), second=0.5, clamp=True)
                color_factor = _connect_math(links, switch_add, switch_half)
            two_color_factor = _math(nodes, "MULTIPLY", "Two Color State", (300, -860), second=use_two_colors)
            factor = _connect_math(links, two_color_factor, color_factor)
            selected = _mix_color(
                nodes, links, "Select Emissive Color", color_outputs[0], color_outputs[1], factor, (500, -820)
            )

        emissive_node = self._texture_node(
            nodes, param_texture_path(data, "Emissive"), "Emissive Mask", (-680, -440), non_color=True
        )
        if emissive_node is not None:
            emissive_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Tint Emissive Mask", (0, -520))
            emissive_mix.blend_type = "MULTIPLY"
            emissive_mix.inputs[0].default_value = 1.0
            links.new(emissive_node.outputs["Color"], emissive_mix.inputs[1])
            links.new(selected, emissive_mix.inputs[2])
            emission_color = emissive_mix.outputs[0]
        else:
            emission_color = selected

        if use_fresnel > 0.0 or directionality > 0.0:
            layer_weight = new_labeled_node(nodes, "ShaderNodeLayerWeight", "Diode Fresnel", (20, -730))
            facing_invert = _math(nodes, "SUBTRACT", "Edge Fresnel", (220, -730), first=1.0)
            edge_factor = _connect_math(links, facing_invert, None, layer_weight.outputs["Facing"])
            fresnel_factor = _mix_color(
                nodes, links, "Fresnel Enable", (1.0, 1.0, 1.0, 1.0), edge_factor, use_fresnel, (420, -690)
            )
            directional_factor = _mix_color(
                nodes, links, "Directionality", (1.0, 1.0, 1.0, 1.0), layer_weight.outputs["Facing"], directionality, (420, -790)
            )
            fresnel_mult = new_labeled_node(nodes, "ShaderNodeMixRGB", "Fresnel Directionality", (610, -650))
            fresnel_mult.blend_type = "MULTIPLY"
            fresnel_mult.inputs[0].default_value = 1.0
            links.new(fresnel_factor, fresnel_mult.inputs[1])
            links.new(directional_factor, fresnel_mult.inputs[2])
            color_mult = new_labeled_node(nodes, "ShaderNodeMixRGB", "Directional Emission", (610, -500))
            color_mult.blend_type = "MULTIPLY"
            color_mult.inputs[0].default_value = 1.0
            links.new(emission_color, color_mult.inputs[1])
            links.new(fresnel_mult.outputs[0], color_mult.inputs[2])
            emission_color = color_mult.outputs[0]

        time_output = create_scene_time_value(tree, -930, -620, "CP77 Device Time").outputs[0]
        blink_angle = _math(nodes, "MULTIPLY", "Blink Speed", (-700, -620), second=blinking_speed * math.tau)
        blink_phase = _connect_math(links, blink_angle, time_output)
        blink_sine = _math(nodes, "SINE", "Blink Sine", (-500, -620))
        blink_wave = _connect_math(links, blink_sine, blink_phase)
        blink_gate = _math(nodes, "GREATER_THAN", "Blink Gate", (-300, -620), second=0.0)
        blink_pulse = _connect_math(links, blink_gate, blink_wave)
        effective_blinking = blinking if blinking_speed > 1e-6 else 0.0
        blink_factor = _math(nodes, "MULTIPLY", "Blink Enabled", (-100, -620), second=effective_blinking)
        blink_enabled = _connect_math(links, blink_factor, blink_pulse)
        steady_factor = _math(nodes, "SUBTRACT", "Steady When Not Blinking", (-100, -690), first=1.0, second=effective_blinking)
        brightness_add = _math(nodes, "ADD", "Blink Or Steady", (100, -620))
        brightness = _connect_math(links, brightness_add, steady_factor.outputs[0], blink_enabled)
        state_mul = _math(nodes, "MULTIPLY", "Emissive State", (300, -620))
        state_brightness = _connect_math(links, state_mul, state_output, brightness)

        ev_strength = max(0.0, min(65536.0, 2.0 ** max(-16.0, min(16.0, emissive_ev))))
        strength_mul = _math(nodes, "MULTIPLY", "Emissive EV", (520, -620), second=ev_strength)
        emission_strength = _connect_math(links, strength_mul, state_brightness)

        emission_color_socket = find_input(principled, "Emission Color", "Emission")
        if emission_color_socket is not None:
            links.new(emission_color, emission_color_socket)
        emission_strength_socket = find_input(principled, "Emission Strength")
        if emission_strength_socket is not None:
            links.new(emission_strength, emission_strength_socket)

        if base_node is not None and alpha_threshold > 0.0:
            alpha_gate = _math(nodes, "GREATER_THAN", "Alpha Threshold", (-380, 470), second=alpha_threshold)
            alpha_output = _connect_math(links, alpha_gate, base_node.outputs["Alpha"])
            alpha_socket = find_input(principled, "Alpha")
            if alpha_socket is not None:
                links.new(alpha_output, alpha_socket)
        _set_alpha_mode(Mat, alpha_threshold)
