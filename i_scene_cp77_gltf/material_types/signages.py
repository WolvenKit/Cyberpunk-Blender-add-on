from ..blender import shader_nodes
from .emissive_common import EmissiveSlotsMixin
from .graph import (
    combine_color_socket,
    mix_color_socket,
    mix_scalar_socket,
    separate_color_node,
)
from .mat_common import (
    MaterialTypeBase,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
    scene_time_socket,
    write_slot_values,
)

# The red channel picks a band: floor(red * 0.901 * 6) runs from 0 to 5.
_BAND_SCALE = 0.901 * 6.0
# Bands 0 to 4 take these colours; band 5 takes the gradient from ColorOneStart to ColorOneEnd.
_BAND_COLORS = ("ColorSix", "ColorFive", "ColorFour", "ColorThree", "ColorTwo")
_VALUE_MIN, _VALUE_MAX = 0.035, 0.93
# The largest single-precision value under one half: an alpha above it is at least one half.
_UNDER_HALF = 0.49999997
_WHITE = (1.0, 1.0, 1.0, 1.0)


def _uniform(data):
    return param_float(data, "UniformColor", 0.0) != 0.0


def _vertex_colored(data):
    # The setting is read as a whole number, so anything under one picks the vertex colour.
    return int(param_float(data, "UseVertexColorOrMap", 1.0)) == 0


def _blinks(data):
    return (
        param_float(data, "BlinkingSpeed", 0.0) > 0.0
        and param_float(data, "BlinkingMinimumValue", 0.0) != 1.0
    )


def _lights_up(data):
    return param_float(data, "LightupDensity", 0.0) > 0.0


def _fades(data):
    # Facing the camera the fade term is zero, so only a positive FresnelAmount dims anything.
    return param_float(data, "FresnelAmount", 0.0) > 0.0


def _roughness_textured(data):
    return param_float(data, "UseRoughnessTexture", 0.0) == 1.0


def _glow_dimmed(data):
    """Whether anything scales the glow per pixel"""
    return not _uniform(data) or _fades(data) or _blinks(data) or _lights_up(data)


def held_color(color):
    """color with its brightness held between 0.035 and 0.93, and the brightness before"""
    value = max(color[0], color[1], color[2])
    held = min(max(value, _VALUE_MIN), _VALUE_MAX)
    if value <= 0.0:
        return (held, held, held, color[3]), value
    scale = held / value
    return (color[0] * scale, color[1] * scale, color[2] * scale, color[3]), value


class Signages(EmissiveSlotsMixin, MaterialTypeBase):
    texture_defaults = {
        "MainTexture": "base\\fx\\textures\\other\\plazma_mask.xbm",
        "NoiseTexture": "base\\fx\\_textures\\masks\\noise\\fx_organic_noise_01_d.xbm",
        "RoughnessTexture": "engine\\textures\\editor\\black.xbm",
    }

    def __init__(self, BasePath, image_format, ProjPath="", enable_mask=False):
        super().__init__(BasePath, image_format, ProjPath)
        self.enable_mask = bool(enable_mask)

    def _images(self, data):
        """The textures the material samples, by parameter (None where it does not sample one or it is missing)"""
        uniform = _uniform(data)
        wanted = {
            "MainTexture": not uniform and not _vertex_colored(data),
            "NoiseTexture": _blinks(data),
            "RoughnessTexture": _roughness_textured(data),
        }
        return {
            key: self._load_relative_image(
                self._texture_path(data, key),
                non_color=key == "RoughnessTexture",
                error_label=f"signages {key}",
            )
            if use
            else None
            for key, use in wanted.items()
        }

    def structure_key(self, Data):
        data = Data if isinstance(Data, dict) else {}
        images = self._images(data)
        uniform = _uniform(data)
        return (
            uniform,
            None if uniform else _vertex_colored(data),
            tuple(image is not None for image in images.values()),
            _roughness_textured(data),
            _blinks(data),
            _lights_up(data),
            _fades(data),
            self.enable_mask and not uniform,
        )

    def _values(self, data):
        """Every per-material value, by slot"""
        uniform = _uniform(data)
        glow = 2.0 ** param_float(data, "EmissiveEV", 0.0)
        values = {
            "Metalness": param_float(data, "Metalness", 0.0),
            "Roughness": param_float(data, "Roughness", 0.0),
        }
        if uniform:
            color, brightness = held_color(param_color(data, "ColorOneStart", _WHITE))
            values["Color"] = color
            glow *= brightness
        if _glow_dimmed(data):
            values["Glow"] = glow
        else:
            values["Emission Strength"] = max(glow - 1.0, 0.0)
        if not uniform:
            for key in ("ColorOneStart", "ColorOneEnd", *_BAND_COLORS):
                values[key] = param_color(data, key, _WHITE)
            values["HorizontalOrVerticalGradient"] = param_float(
                data, "HorizontalOrVerticalGradient", 0.0
            )
            scale = param_float(data, "ColorGradientScale", 1.0)
            values["Gradient Scale"] = scale
            values["Gradient Offset"] = (
                -param_float(data, "GradientStartPosition", 0.0) * scale
            )
        if _roughness_textured(data):
            tiling = param_vector(
                data, "RoughnessTilingAndOffset", (0.0, 0.0, 0.0, 0.0)
            )
            # Material UVs run V down the texture, Blender's up:
            # v' = v * tiling + offset becomes 1 - ((1 - v) * tiling + offset).
            values["Roughness Scale"] = (tiling[0], tiling[1], 1.0)
            values["Roughness Offset"] = (tiling[2], 1.0 - tiling[1] - tiling[3], 0.0)
        if _blinks(data):
            smoothness = param_float(data, "BlinkSmoothness", 1.0)
            values["BlinkingSpeed"] = param_float(data, "BlinkingSpeed", 0.0)
            values["Blink V"] = 1.0 - param_float(data, "BlinkingPhase", 0.0)
            values["BlinkingMinimumValue"] = param_float(
                data, "BlinkingMinimumValue", 0.0
            )
            values["Blink Steps"] = 2.0 + (1000.0 - 2.0) * smoothness
        if _lights_up(data):
            minimum = param_float(data, "LightupMinimumValue", 0.5)
            half_range = (1.0 - minimum) * 0.5
            values["LightupDensity"] = param_float(data, "LightupDensity", 0.0)
            values["LightupHorizontalOrVertical"] = param_float(
                data, "LightupHorizontalOrVertical", 0.0
            )
            values["Lightup Swing"] = half_range
            values["Lightup Floor"] = half_range + minimum
        if _fades(data):
            values["Fade Start"] = 1.0 - param_float(data, "FresnelAmount", 0.0)
        return values

    def _write_values(self, Mat, data, slots):
        nodes = Mat.node_tree.nodes
        write_slot_values(nodes, slots, self._values(data))
        for key, image in self._images(data).items():
            for node_name in slots.get(f"image:{key}", ()):
                node = nodes[node_name]
                if node.image is not image:
                    node.image = image

    def _rgb(self, nodes, slot, location):
        node = new_labeled_node(nodes, "ShaderNodeRGB", slot, location)
        self._slot(slot, node)
        return node.outputs["Color"]

    def _texture(self, nodes, links, key, image, vector, location):
        node = new_labeled_node(nodes, "ShaderNodeTexImage", key, location)
        node.image = image
        node.extension = "REPEAT"
        if vector is not None:
            links.new(vector, node.inputs["Vector"])
        self.structure_slots.setdefault(f"image:{key}", []).append(node.name)
        return node

    def _material_uv(self, nodes, links):
        """The UV in the material's own axes"""
        uv = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", (-2200, 200))
        split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "UV Axes", (-2020, 200)
        )
        links.new(uv.outputs["UV"], split.inputs["Vector"])
        down = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            split.outputs["Y"],
            name="Material V",
            location=(-1840, 140),
        )
        return uv.outputs["UV"], split.outputs["X"], down

    def _axis_blend(self, nodes, links, material_uv, slot, label, location):
        _uv, u, v = material_uv
        return mix_scalar_socket(
            nodes,
            links,
            label,
            location,
            v,
            u,
            self._value(nodes, slot, (location[0] - 180, location[1] - 120)),
        )

    def _source_color(self, nodes, links, data, images, material_uv):
        """The colour and alpha the bands are read from"""
        if _vertex_colored(data):
            vertex = new_labeled_node(
                nodes, "ShaderNodeVertexColor", "Vertex Color", (-1840, 620)
            )
            return vertex.outputs["Color"], vertex.outputs["Alpha"]
        image = images["MainTexture"]
        if image is None:
            missing = new_labeled_node(
                nodes, "ShaderNodeRGB", "MainTexture Missing", (-1840, 620)
            )
            missing.outputs["Color"].default_value = _WHITE
            return missing.outputs["Color"], 1.0
        texture = self._texture(
            nodes, links, "MainTexture", image, material_uv[0], (-1840, 620)
        )
        return texture.outputs["Color"], texture.outputs["Alpha"]

    def _band_color(self, nodes, links, source, material_uv):
        """The band colour for the red channel of source"""
        red = separate_color_node(
            nodes, links, source, "Source Channels", (-1600, 620)
        ).outputs["Red"]
        band = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                red,
                _BAND_SCALE,
                name="Red x Bands",
                location=(-1420, 620),
            ),
            name="Band",
            location=(-1240, 620),
        )
        color = self._rgb(nodes, _BAND_COLORS[0], (-1240, 460))
        for index, key in enumerate(_BAND_COLORS[1:], start=1):
            reached = shader_nodes.math(
                nodes,
                links,
                "GREATER_THAN",
                band,
                index - 0.5,
                name=f"Band >= {index}",
                location=(-1060 + index * 180, 760),
            )
            color = mix_color_socket(
                nodes,
                links,
                f"Band {index} Colour",
                color,
                self._rgb(nodes, key, (-1240 + index * 180, 460)),
                reached,
                (-1060 + index * 180, 620),
            )
        along = self._axis_blend(
            nodes,
            links,
            material_uv,
            "HorizontalOrVerticalGradient",
            "Gradient Axis",
            (-1420, 280),
        )
        gradient_factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            name="Gradient Factor",
            location=(-1240, 280),
            use_clamp=True,
        ).node
        links.new(along, gradient_factor.inputs["Value"])
        links.new(
            self._value(nodes, "Gradient Scale", (-1420, 140)),
            shader_nodes.socket_by_identifier(gradient_factor.inputs, "Value_001"),
        )
        links.new(
            self._value(nodes, "Gradient Offset", (-1420, 40)),
            shader_nodes.socket_by_identifier(gradient_factor.inputs, "Value_002"),
        )
        gradient = mix_color_socket(
            nodes,
            links,
            "Gradient",
            self._rgb(nodes, "ColorOneStart", (-1240, 120)),
            self._rgb(nodes, "ColorOneEnd", (-1240, 20)),
            gradient_factor.outputs["Value"],
            (-1060, 280),
        )
        top = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            band,
            4.5,
            name="Band >= 5",
            location=(-100, 760),
        )
        return mix_color_socket(
            nodes, links, "Band 5 Colour", color, gradient, top, (-100, 620)
        )

    def _fade(self, nodes, links):
        """1 - saturate(FresnelAmount - cos(view angle))"""
        weight = new_labeled_node(
            nodes, "ShaderNodeLayerWeight", "View Facing", (-1240, -260)
        )
        fade = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            name="Grazing Fade",
            location=(-1060, -260),
            use_clamp=True,
        ).node
        links.new(weight.outputs["Facing"], fade.inputs["Value"])
        links.new(
            self._value(nodes, "Fade Start", (-1240, -420)),
            shader_nodes.socket_by_identifier(fade.inputs, "Value_001"),
        )
        return shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            fade.outputs["Value"],
            name="Facing Glow",
            location=(-880, -260),
        )

    def _blink(self, tree, images):
        """The noise texture read along its U by scene time, stepped"""
        nodes, links = tree.nodes, tree.links
        time = scene_time_socket(tree.nodes, (-2020, -620), "CP77 Signage Time")
        travel = shader_nodes.math(
            nodes,
            links,
            "FRACT",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                time,
                self._value(nodes, "BlinkingSpeed", (-2020, -760)),
                name="Time x BlinkingSpeed",
                location=(-1840, -620),
            ),
            name="Blink U",
            location=(-1660, -620),
        )
        coordinate = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Blink UV", (-1480, -620)
        )
        links.new(travel, coordinate.inputs["X"])
        links.new(self._value(nodes, "Blink V", (-1660, -760)), coordinate.inputs["Y"])
        image = images["NoiseTexture"]
        if image is None:
            noise = 0.0
        else:
            texture = self._texture(
                nodes,
                links,
                "NoiseTexture",
                image,
                coordinate.outputs["Vector"],
                (-1300, -620),
            )
            noise = separate_color_node(
                nodes, links, texture.outputs["Color"], "Noise Channels", (-1060, -620)
            ).outputs["Red"]
        lifted = shader_nodes.math(
            nodes,
            links,
            "ADD",
            name="Blink Floor",
            location=(-880, -620),
            use_clamp=True,
        ).node
        if isinstance(noise, float):
            lifted.inputs["Value"].default_value = noise
        else:
            links.new(noise, lifted.inputs["Value"])
        links.new(
            self._value(nodes, "BlinkingMinimumValue", (-1060, -760)),
            shader_nodes.socket_by_identifier(lifted.inputs, "Value_001"),
        )
        steps = self._value(nodes, "Blink Steps", (-880, -760))
        stepped = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                lifted.outputs["Value"],
                steps,
                name="Blink x Steps",
                location=(-700, -620),
            ),
            name="Blink Stepped",
            location=(-520, -620),
        )
        return shader_nodes.math(
            nodes, links, "DIVIDE", stepped, steps, name="Blink", location=(-340, -620)
        )

    def _lightup(self, nodes, links, material_uv):
        """saturate((sin(coordinate * density) + 1) / 2 * (1 - minimum) + minimum)"""
        along = self._axis_blend(
            nodes,
            links,
            material_uv,
            "LightupHorizontalOrVertical",
            "Lightup Axis",
            (-1420, -980),
        )
        wave = shader_nodes.math(
            nodes,
            links,
            "SINE",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                along,
                self._value(nodes, "LightupDensity", (-1420, -1120)),
                name="Lightup Phase",
                location=(-1240, -980),
            ),
            name="Lightup Wave",
            location=(-1060, -980),
        )
        lines = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            name="Lightup",
            location=(-880, -980),
            use_clamp=True,
        ).node
        links.new(wave, lines.inputs["Value"])
        links.new(
            self._value(nodes, "Lightup Swing", (-1060, -1120)),
            shader_nodes.socket_by_identifier(lines.inputs, "Value_001"),
        )
        links.new(
            self._value(nodes, "Lightup Floor", (-1060, -1220)),
            shader_nodes.socket_by_identifier(lines.inputs, "Value_002"),
        )
        return lines.outputs["Value"]

    def _roughness(self, nodes, links, images, material_uv):
        """The roughness texture's red channel, or None where the material uses its Roughness value"""
        image = images["RoughnessTexture"]
        if image is None:
            return None
        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "RoughnessTilingAndOffset", (-880, -1460)
        )
        links.new(material_uv[0], mapping.inputs["Vector"])
        self._slot("Roughness Scale", mapping, "Scale")
        self._slot("Roughness Offset", mapping, "Location")
        texture = self._texture(
            nodes,
            links,
            "RoughnessTexture",
            image,
            mapping.outputs["Vector"],
            (-700, -1460),
        )
        return separate_color_node(
            nodes, links, texture.outputs["Color"], "Roughness Channels", (-460, -1460)
        ).outputs["Red"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        self.structure_slots = {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes, links = tree.nodes, tree.links
        nodes.clear()
        images = self._images(data)
        uniform = _uniform(data)

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (900, 100)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Signage", (600, 100)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        needs_uv = (
            not uniform or _lights_up(data) or images["RoughnessTexture"] is not None
        )
        material_uv = self._material_uv(nodes, links) if needs_uv else None

        # The glow scale: every dimming term multiplied together, or none.
        terms = []
        if uniform:
            color = self._rgb(nodes, "Color", (200, 300))
        else:
            source, alpha = self._source_color(nodes, links, data, images, material_uv)
            banded = self._band_color(nodes, links, source, material_uv)
            hsv = separate_color_node(
                nodes, links, banded, "Band Colour HSV", (80, 620), mode="HSV"
            )
            held = new_labeled_node(
                nodes, "ShaderNodeClamp", "Held Brightness", (260, 560)
            )
            links.new(hsv.outputs["Blue"], held.inputs["Value"])
            held.inputs["Min"].default_value = _VALUE_MIN
            held.inputs["Max"].default_value = _VALUE_MAX
            color = combine_color_socket(
                nodes,
                links,
                "Held Colour",
                (440, 620),
                hsv.outputs["Red"],
                hsv.outputs["Green"],
                held.outputs["Result"],
                mode="HSV",
            )
            terms.append(hsv.outputs["Blue"])
            if self.enable_mask:
                cut = shader_nodes.math(
                    nodes,
                    links,
                    "GREATER_THAN",
                    alpha,
                    _UNDER_HALF,
                    name="Alpha Cut",
                    location=(440, 300),
                )
                links.new(cut, principled.inputs["Alpha"])
        if _fades(data):
            terms.append(self._fade(nodes, links))
        if _blinks(data):
            terms.append(self._blink(tree, images))
        if _lights_up(data):
            terms.append(self._lightup(nodes, links, material_uv))

        links.new(color, principled.inputs["Base Color"])
        links.new(color, find_input(principled, "Emission Color", "Emission"))
        if terms:
            scale = terms[0]
            for index, term in enumerate(terms[1:], start=1):
                scale = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    scale,
                    term,
                    name=f"Glow Term {index}",
                    location=(-160 + index * 120, -300),
                )
            # The glow EmissiveEV + log2(scale), floored at zero, is max(scale * 2^EmissiveEV, 1) as an intensity.
            scaled = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY_ADD",
                name="Scaled Glow - 1",
                location=(380, -300),
            ).node
            links.new(scale, scaled.inputs["Value"])
            links.new(
                self._value(nodes, "Glow", (200, -300)),
                shader_nodes.socket_by_identifier(scaled.inputs, "Value_001"),
            )
            shader_nodes.socket_by_identifier(
                scaled.inputs, "Value_002"
            ).default_value = -1.0
            strength = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                scaled.outputs["Value"],
                0.0,
                name="Emission Strength",
                location=(540, -300),
            )
            links.new(strength, principled.inputs["Emission Strength"])
        else:
            self._slot("Emission Strength", principled, "Emission Strength")

        self._slot("Metalness", principled, "Metallic")
        roughness = self._roughness(nodes, links, images, material_uv)
        if roughness is None:
            self._slot("Roughness", principled, "Roughness")
        else:
            links.new(roughness, principled.inputs["Roughness"])
        self._write_values(Mat, data, self.structure_slots)
