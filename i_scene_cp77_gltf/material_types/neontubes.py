<<<<<<< Updated upstream
from .mat_common import (
    MaterialTypeBase,
    clamp01,
=======
from ..assetio.paths import backslash_depot_key
from ..blender import shader_nodes
from .graph import mix_color_socket
from .mat_common import (
    MaterialTypeBase,
>>>>>>> Stashed changes
    create_scene_time_value,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
<<<<<<< Updated upstream
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
=======
    write_slot_values,
)
from .shader_hash import HASH_OFFSET, HASH_SCALE

# The editor's white texture leaves the colour as it is, so it is not sampled.
_WHITE_TEXTURE = "engine\\textures\\editor\\white.xbm"
_WHITE = (1.0, 1.0, 1.0, 1.0)


def _textured(texture_path):
    return bool(texture_path) and backslash_depot_key(texture_path) != _WHITE_TEXTURE


def _fades(data):
    return (
        param_float(data, "EmissiveEdgeMult", 0.0) != 1.0
        and param_float(data, "fresnelpower", 1.0) != 0.0
    )


def _blinks(data):
    return param_float(data, "UseBlinkingNoise", 0.0) > 0.0


def _modulated(data):
    return param_float(data, "UseMatParamToCtrlNoise", 0.0) >= 1.0


def _hash(nodes, links, value, location):
    """A pseudo-random number in [0, 1) from value"""
    x, y = location
    q = shader_nodes.math(
        nodes,
        links,
        "FRACT",
        shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            value,
            HASH_SCALE,
            name="Hash Scale",
            location=(x, y),
        ),
        name="Hash Fraction",
        location=(x + 180, y),
    )
    q = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        q,
        shader_nodes.math(
            nodes,
            links,
            "ADD",
            q,
            HASH_OFFSET,
            name="Hash Offset",
            location=(x + 360, y - 120),
        ),
        name="Hash Square",
        location=(x + 540, y),
    )
    q = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        q,
        shader_nodes.math(
            nodes, links, "ADD", q, q, name="Hash Double", location=(x + 720, y - 120)
        ),
        name="Hash Double Square",
        location=(x + 900, y),
    )
    return shader_nodes.math(
        nodes, links, "FRACT", q, name="Hash", location=(x + 1080, y)
    )


class NeonTubes(MaterialTypeBase):
    texture_defaults = {"tex1": _WHITE_TEXTURE}

    def _image(self, data):
        path = self._texture_path(data, "tex1")
        if not _textured(path):
            return None
        return self._load_relative_image(path, error_label="neon tubes tex1")

    def structure_key(self, Data):
        data = Data if isinstance(Data, dict) else {}
        return (
            self._image(data) is not None,
            _fades(data),
            _blinks(data),
            _modulated(data),
        )

    def _values(self, data, textured):
        tint = param_color(data, "color", _WHITE)
        values = {
            "color": tint,
            "RoughnessBias": param_float(data, "RoughnessBias", 0.01),
        }
        glow = 2.0 ** param_float(data, "EmissiveEV", 6.0)
        if _fades(data) or _blinks(data):
            values["Glow"] = glow
        else:
            values["Emission Strength"] = max(glow - 1.0, 0.0)
        if textured:
            u, v = (
                param_float(data, "TextureU", 1.0),
                param_float(data, "TextureV", 1.0),
            )
            # Material UVs run V down the texture, Blender's up: v' = v * TextureV becomes 1 - (1 - v) * TextureV.
            values["Texture Scale"] = (u, v, 1.0)
            values["Texture Offset"] = (0.0, 1.0 - v, 0.0)
            lift = 1.0 - param_float(data, "TextureIntensity", 0.0)
            values["Texture Lift"] = (lift, lift, lift, 1.0)
        if _fades(data):
            edge = param_float(data, "EmissiveEdgeMult", 0.0)
            values["fresnelpower"] = param_float(data, "fresnelpower", 1.0)
            values["Edge Rise"] = 1.0 - edge
            values["EmissiveEdgeMult"] = edge
        if _blinks(data):
            minimum = param_float(data, "MinNoiseValue", 0.1)
            gain = 1.0 / max(1.0 - minimum, 1.0e-7)
            values["Noise Seed"] = param_float(data, "TimeSeed", 12345.0) + 0.546
            values["Noise Gain"] = gain
            values["Noise Offset"] = -minimum * gain
            values["Blink Lift"] = 1.0 - param_float(data, "UseBlinkingNoise", 0.0)
        return values

    def apply_structure_values(self, Data, Mat, slots):
        data = Data if isinstance(Data, dict) else {}
        self._write_values(Mat, data, slots)

    def _write_values(self, Mat, data, slots):
        nodes = Mat.node_tree.nodes
        image = self._image(data)
        write_slot_values(nodes, slots, self._values(data, image is not None))
        for node_name in slots.get("image:tex1", ()):
            node = nodes[node_name]
            if node.image is not image:
                node.image = image
        Mat.diffuse_color = (*param_color(data, "color", _WHITE)[:3], 1.0)

    def _slot(self, slot, node, socket=None):
        self.structure_slots[slot] = (node.name, socket)

    def _value(self, nodes, slot, location):
        node = new_labeled_node(nodes, "ShaderNodeValue", slot, location)
        self._slot(slot, node)
        return node.outputs["Value"]

    def _color(self, nodes, links, image):
        tint = new_labeled_node(nodes, "ShaderNodeRGB", "color", (-500, 520))
        self._slot("color", tint)
        if image is None:
            return tint.outputs["Color"]
        uv = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", (-1380, 360))
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "TextureU / TextureV", (-1180, 360)
        )
        links.new(uv.outputs["UV"], mapping.inputs["Vector"])
        self._slot("Texture Scale", mapping, "Scale")
        self._slot("Texture Offset", mapping, "Location")
        texture = new_labeled_node(nodes, "ShaderNodeTexImage", "tex1", (-960, 360))
        texture.image = image
        texture.extension = "REPEAT"
        links.new(mapping.outputs["Vector"], texture.inputs["Vector"])
        self.structure_slots.setdefault("image:tex1", []).append(texture.name)
        lift = new_labeled_node(nodes, "ShaderNodeRGB", "Texture Lift", (-960, 140))
        self._slot("Texture Lift", lift)
        lifted = mix_color_socket(
            nodes,
            links,
            "Texture Intensity",
            texture.outputs["Color"],
            lift.outputs["Color"],
            1.0,
            (-720, 360),
            blend_type="ADD",
            clamp=True,
        )
        return mix_color_socket(
            nodes,
            links,
            "Neon Color",
            lifted,
            tint.outputs["Color"],
            1.0,
            (-500, 360),
            blend_type="MULTIPLY",
        )

    def _fade(self, nodes, links):
        """EmissiveEdgeMult + (1 - EmissiveEdgeMult) * cos(view angle)^fresnelpower"""
        weight = new_labeled_node(
            nodes, "ShaderNodeLayerWeight", "View Facing", (-1180, -100)
        )
        cosine = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            weight.outputs["Facing"],
            name="View Cosine",
            location=(-1000, -100),
        )
        power = shader_nodes.math(
            nodes,
            links,
            "POWER",
            cosine,
            self._value(nodes, "fresnelpower", (-1000, -240)),
            name="Cosine Power",
            location=(-820, -100),
        )
        fade = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            name="Emission By Fresnel",
            location=(-640, -100),
        ).node
        links.new(power, fade.inputs["Value"])
        links.new(
            self._value(nodes, "Edge Rise", (-820, -240)),
            shader_nodes.socket_by_identifier(fade.inputs, "Value_001"),
        )
        links.new(
            self._value(nodes, "EmissiveEdgeMult", (-820, -340)),
            shader_nodes.socket_by_identifier(fade.inputs, "Value_002"),
        )
        return fade.outputs["Value"]

    def _blink(self, tree):
        """saturate(remap(noise, MinNoiseValue..1) + 1 - UseBlinkingNoise), noise hashed from scene time"""
        nodes, links = tree.nodes, tree.links
        time = create_scene_time_value(tree, -1740, -460, "CP77 Neon Time")
        seeded = shader_nodes.math(
            nodes,
            links,
            "ADD",
            time.outputs["Value"],
            self._value(nodes, "Noise Seed", (-1740, -600)),
            name="Time + Seed",
            location=(-1560, -460),
        )
        noise = _hash(nodes, links, seeded, (-1380, -460))
        limited = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            name="Limited Noise",
            location=(-120, -460),
            use_clamp=True,
        ).node
        links.new(noise, limited.inputs["Value"])
        links.new(
            self._value(nodes, "Noise Gain", (-300, -600)),
            shader_nodes.socket_by_identifier(limited.inputs, "Value_001"),
        )
        links.new(
            self._value(nodes, "Noise Offset", (-300, -700)),
            shader_nodes.socket_by_identifier(limited.inputs, "Value_002"),
        )
        blink = shader_nodes.math(
            nodes, links, "ADD", name="Blink", location=(60, -460), use_clamp=True
        ).node
        links.new(limited.outputs["Value"], blink.inputs["Value"])
        links.new(
            self._value(nodes, "Blink Lift", (-120, -600)),
            shader_nodes.socket_by_identifier(blink.inputs, "Value_001"),
        )
        return blink.outputs["Value"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        self.structure_slots = {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes, links = tree.nodes, tree.links
        nodes.clear()
        image = self._image(data)

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1040, 120)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Neon Tubes", (780, 120)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        color = self._color(nodes, links, image)
        if _modulated(data):
            material_param = new_labeled_node(
                nodes, "ShaderNodeRGB", "CP77 MaterialParam0", (-500, 700)
            )
            material_param.label = "Editable gameplay material modifier preview"
            material_param.outputs["Color"].default_value = _WHITE
            color = mix_color_socket(
                nodes,
                links,
                "Material Modifier Color",
                color,
                material_param.outputs["Color"],
                1.0,
                (-260, 360),
                blend_type="MULTIPLY",
            )
        links.new(color, principled.inputs["Base Color"])
        links.new(color, find_input(principled, "Emission Color", "Emission"))

        terms = []
        if _fades(data):
            terms.append(self._fade(nodes, links))
        if _blinks(data):
            terms.append(self._blink(tree))
        if terms:
            scale = (
                terms[0]
                if len(terms) == 1
                else shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    terms[0],
                    terms[1],
                    name="Fresnel Times Blink",
                    location=(240, -180),
                )
            )
            # The glow EmissiveEV + log2(scale), floored at zero, is max(scale * 2^EmissiveEV, 1) as an intensity.
            scaled = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY_ADD",
                name="Scaled Glow - 1",
                location=(420, -180),
            ).node
            links.new(scale, scaled.inputs["Value"])
            links.new(
                self._value(nodes, "Glow", (240, -320)),
                shader_nodes.socket_by_identifier(scaled.inputs, "Value_001"),
            )
            shader_nodes.socket_by_identifier(
                scaled.inputs, "Value_002"
            ).default_value = -1.0
            links.new(
                shader_nodes.math(
                    nodes,
                    links,
                    "MAXIMUM",
                    scaled.outputs["Value"],
                    0.0,
                    name="Emission Strength",
                    location=(600, -180),
                ),
                principled.inputs["Emission Strength"],
            )
        else:
            self._slot("Emission Strength", principled, "Emission Strength")

        principled.inputs["Metallic"].default_value = 0.0
        self._slot("RoughnessBias", principled, "Roughness")
        self._write_values(Mat, data, self.structure_slots)
>>>>>>> Stashed changes
