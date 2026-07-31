from .mat_common import (
    MaterialTypeBase,
    clamp01,
    create_scene_time_value,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)

from .graph import (
    math_socket as _math,
    mix_color_at_socket as _mix_color,
    set_opaque as _set_opaque,
)

_TEMPLATES = {"base\\fx\\shaders\\neon_tubes.mt"}


def _store_metadata(material, data):
    material["cp77_neon_tubes_template"] = "base\\fx\\shaders\\neon_tubes.mt"
    material["cp77_neon_tubes_preview"] = "SOURCE_SHADER_WITH_EDITABLE_RUNTIME_PARAMETER"
    scalar_defaults = {
        "EmissiveEV": 6.0,
        "EmissiveEVRaytracingBias": 0.0,
        "EnableRaytracedEmissive": 1.0,
        "EmissiveDirectionality": 0.0,
        "EmissiveEdgeMult": 0.0,
        "fresnelpower": 1.0,
        "UseBlinkingNoise": 0.0,
        "BlinkSpeed": 100.0,
        "MinNoiseValue": 0.1,
        "TimeSeed": 12345.0,
        "UseMatParamToCtrlNoise": 0.0,
        "TextureU": 1.0,
        "TextureV": 1.0,
        "TextureIntensity": 0.0,
        "RoughnessBias": 0.01,
    }
    for name, default in scalar_defaults.items():
        material[f"cp77_{name}"] = param_float(data, name, default)
    material["cp77_color"] = list(param_color(data, "color", (1.0, 1.0, 1.0, 1.0)))
    material["cp77_tex1"] = param_texture_path(data, "tex1")


class NeonTubes(MaterialTypeBase):
    def _texture_node(self, nodes, path, location):
        image = self._load_relative_image(path, error_label="neon tubes")
        node = new_labeled_node(nodes, "ShaderNodeTexImage", "tex1", location)
        node.image = image
        try:
            node.extension = "REPEAT"
        except (AttributeError, TypeError, ValueError):
            pass
        return node

    def _create_uv(self, nodes, links, data):
        texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", (-1380, 360))
        mapping = new_labeled_node(nodes, "ShaderNodeMapping", "TextureU / TextureV", (-1180, 360))
        vector = find_input(mapping, "Vector") or mapping.inputs[0]
        scale = find_input(mapping, "Scale")
        links.new(texcoord.outputs["UV"], vector)
        if scale is not None:
            scale.default_value = (
                param_float(data, "TextureU", 1.0),
                param_float(data, "TextureV", 1.0),
                1.0,
            )
        return mapping.outputs.get("Vector") or mapping.outputs[0]

    def _create_fresnel(self, nodes, links, data):
        facing = new_labeled_node(nodes, "ShaderNodeLayerWeight", "View Facing", (-1180, -100))
        power = _math(
            nodes,
            links,
            "POWER",
            "Fresnel Power",
            (-960, -100),
            facing.outputs.get("Facing"),
            max(0.0001, param_float(data, "fresnelpower", 1.0)),
        )
        fresnel = _math(
            nodes,
            links,
            "SUBTRACT",
            "One Minus Facing Power",
            (-760, -100),
            1.0,
            power,
            clamp=True,
        )
        edge = param_float(data, "EmissiveEdgeMult", 0.0)
        return _math(
            nodes,
            links,
            "MULTIPLY_ADD",
            "Emission By Fresnel",
            (-560, -100),
            fresnel,
            edge - 1.0,
        ), edge

    def _create_blink(self, tree, data):
        nodes = tree.nodes
        links = tree.links
        use_blink = clamp01(param_float(data, "UseBlinkingNoise", 0.0))
        speed = max(0.0, param_float(data, "BlinkSpeed", 100.0))
        seed = param_float(data, "TimeSeed", 12345.0)
        minimum = clamp01(param_float(data, "MinNoiseValue", 0.1), 0.0, 0.999999)

        time = create_scene_time_value(tree, -1380, -460, "CP77 Neon Time")
        seeded = _math(nodes, links, "ADD", "Noise Time Seed", (-1160, -420), time.outputs[0], seed + 0.546)
        noise = new_labeled_node(nodes, "ShaderNodeTexWhiteNoise", "hash11(Time + Seed)", (-940, -420))
        try:
            noise.noise_dimensions = "1D"
        except (AttributeError, TypeError, ValueError):
            pass
        links.new(seeded, find_input(noise, "W") or noise.inputs[0])

        interval = _math(
            nodes,
            links,
            "MULTIPLY",
            "Blink Interval",
            (-1160, -580),
            time.outputs[0],
            speed * 1.0e-8,
        )
        interval_noise = new_labeled_node(nodes, "ShaderNodeTexWhiteNoise", "hash11(Blink Interval)", (-940, -580))
        try:
            interval_noise.noise_dimensions = "1D"
        except (AttributeError, TypeError, ValueError):
            pass
        links.new(interval, find_input(interval_noise, "W") or interval_noise.inputs[0])
        trigger_scaled = _math(
            nodes,
            links,
            "MULTIPLY",
            "Blink Trigger Scale",
            (-720, -580),
            interval_noise.outputs.get("Value") or interval_noise.outputs[0],
            100.0,
        )
        trigger = _math(
            nodes,
            links,
            "ADD",
            "Blink Trigger",
            (-540, -580),
            trigger_scaled,
            -50.0,
            clamp=True,
        )
        combined = _math(
            nodes,
            links,
            "ADD",
            "Noise Plus Trigger",
            (-720, -420),
            noise.outputs.get("Value") or noise.outputs[0],
            trigger,
        )
        remap = new_labeled_node(nodes, "ShaderNodeMapRange", "Minimum Noise Value", (-500, -420))
        remap.inputs[1].default_value = minimum
        remap.inputs[2].default_value = 1.0
        remap.inputs[3].default_value = 0.0
        remap.inputs[4].default_value = 1.0
        try:
            remap.clamp = True
        except (AttributeError, TypeError, ValueError):
            pass
        links.new(combined, remap.inputs[0])
        return _math(
            nodes,
            links,
            "ADD",
            "Blink Enable",
            (-280, -420),
            remap.outputs.get("Result") or remap.outputs[0],
            1.0 - use_blink,
            clamp=True,
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        _store_metadata(Mat, data)
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(nodes, "ShaderNodeOutputMaterial", "Material Output", (1040, 120))
        principled = new_labeled_node(nodes, "ShaderNodeBsdfPrincipled", "Neon Tubes", (780, 120))
        links.new(principled.outputs[0], output.inputs["Surface"])

        uv = self._create_uv(nodes, links, data)
        texture = self._texture_node(nodes, param_texture_path(data, "tex1"), (-940, 360))
        links.new(uv, texture.inputs.get("Vector") or texture.inputs[0])
        lift = 1.0 - clamp01(param_float(data, "TextureIntensity", 0.0))
        color_from_texture = _mix_color(
            nodes,
            links,
            "Texture Intensity",
            (-720, 360),
            texture.outputs.get("Color") or texture.outputs[0],
            (lift, lift, lift, 1.0),
            1.0,
            blend_type="ADD",
            clamp=True,
        )
        tint = param_color(data, "color", (1.0, 1.0, 1.0, 1.0))
        tinted = _mix_color(
            nodes,
            links,
            "Neon Color",
            (-500, 360),
            color_from_texture,
            tint,
            1.0,
            blend_type="MULTIPLY",
            clamp=True,
        )

        material_param = new_labeled_node(nodes, "ShaderNodeRGB", "CP77 MaterialParam0", (-500, 540))
        material_param.label = "Editable gameplay material modifier preview"
        material_param.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        use_material_param = param_float(data, "UseMatParamToCtrlNoise", 0.0) >= 1.0
        final_color = tinted
        if use_material_param:
            final_color = _mix_color(
                nodes,
                links,
                "Material Modifier Color",
                (-260, 360),
                tinted,
                material_param.outputs[0],
                1.0,
                blend_type="MULTIPLY",
                clamp=True,
            )

        base_color = find_input(principled, "Base Color")
        emission_color = find_input(principled, "Emission Color", "Emission")
        if base_color is not None:
            links.new(final_color, base_color)
        if emission_color is not None:
            links.new(final_color, emission_color)

        fresnel_raw, edge = self._create_fresnel(nodes, links, data)
        emission_by_fresnel = _math(
            nodes,
            links,
            "ADD",
            "Fresnel Base",
            (-360, -100),
            fresnel_raw,
            1.0,
            clamp=True if 0.0 <= edge <= 1.0 else False,
        )
        blink = self._create_blink(tree, data)
        modulation = _math(
            nodes,
            links,
            "MULTIPLY",
            "Fresnel Times Blink",
            (0, -180),
            emission_by_fresnel,
            blink,
        )
        emissive_ev = max(0.0, param_float(data, "EmissiveEV", 6.0))
        strength = _math(
            nodes,
            links,
            "MULTIPLY",
            "Scale Emissive EV",
            (220, -180),
            modulation,
            emissive_ev,
        )
        emission_strength = find_input(principled, "Emission Strength")
        if emission_strength is not None:
            links.new(strength, emission_strength)

        metallic = find_input(principled, "Metallic")
        roughness = find_input(principled, "Roughness")
        alpha = find_input(principled, "Alpha")
        if metallic is not None:
            metallic.default_value = 0.0
        if roughness is not None:
            roughness.default_value = clamp01(param_float(data, "RoughnessBias", 0.01))
        if alpha is not None:
            alpha.default_value = 1.0

        Mat.diffuse_color = (*tint[:3], 1.0)
        _set_opaque(Mat)


used_params = [
    "EmissiveEV",
    "EmissiveEVRaytracingBias",
    "EnableRaytracedEmissive",
    "EmissiveDirectionality",
    "EmissiveEdgeMult",
    "color",
    "tex1",
    "fresnelpower",
    "UseBlinkingNoise",
    "BlinkSpeed",
    "MinNoiseValue",
    "TimeSeed",
    "UseMatParamToCtrlNoise",
    "TextureU",
    "TextureV",
    "TextureIntensity",
    "RoughnessBias",
]
