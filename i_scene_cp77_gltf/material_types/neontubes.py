from ..assetio.paths import backslash_depot_key
from ..blender import shader_nodes
from .emissive_common import EmissiveSlotsMixin
from .graph import mix_color_socket
from .mat_common import (
    MaterialTypeBase,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    scene_time_socket,
    write_slot_values,
)
from .shader_hash import hash11_socket

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


class NeonTubes(EmissiveSlotsMixin, MaterialTypeBase):
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

    def _write_values(self, Mat, data, slots):
        nodes = Mat.node_tree.nodes
        image = self._image(data)
        write_slot_values(nodes, slots, self._values(data, image is not None))
        for node_name in slots.get("image:tex1", ()):
            node = nodes[node_name]
            if node.image is not image:
                node.image = image
        Mat.diffuse_color = (*param_color(data, "color", _WHITE)[:3], 1.0)

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
        time = scene_time_socket(tree.nodes, (-1740, -460), "CP77 Neon Time")
        seeded = shader_nodes.math(
            nodes,
            links,
            "ADD",
            time,
            self._value(nodes, "Noise Seed", (-1740, -600)),
            name="Time + Seed",
            location=(-1560, -460),
        )
        noise = hash11_socket(tree, seeded, (-1380, -460), "Hash")
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
