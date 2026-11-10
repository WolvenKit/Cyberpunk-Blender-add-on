from ..blender import shader_nodes
from ..blender.shader_nodes import replace_link
from ..materials.cache_identity import filtered_material_data_identity
from . import multilayered
from .blackbody_nodes import blackbody_bundle, hsv_to_rgb_bundle, rgb_to_hsv_bundle
from .bundles import emissive_scale_bundle
from .graph import (
    color_channel_socket,
    combine_color_socket,
    mix_color_socket,
    mix_scalar_socket,
    separate_color_sockets,
)
from .mat_common import (
    find_input,
    material_property_socket,
    new_labeled_node,
    param_float,
    param_vector,
    scene_time_socket,
)
from .multilayered import Multilayered

TEMPLATE = r"base\fx\_shaders\multilayer_blackbody_inject.mt"

_DEFAULTS = {
    "Emissive": 2.0,
    "Temperature": 22.0,
    "MaximumTemperature": 100.0,
    "ColorExponent": 1.0,
    "Debug": 0.0,
    "FireHSV": (0.0, 0.0, 0.0, 0.0),
    "PoisonHSV": (0.0, 0.0, 0.0, 0.0),
    "ElectricHSV": (0.0, 0.0, 0.0, 0.0),
    "DamageTypeNoiseIntesityAdd": 0.0,
    "DamageTypeNoiseUV": (1.0, 1.0, 0.05, 0.05),
}

_TEXTURE_DEFAULTS = {
    "DamageTypeRGBMask": r"base\fx\_textures\masks\noise\fx_perlin_noise_3d_01_d.xbm",
    "DamageTypeNoise": r"base\fx\_textures\masks\noise\fx_perlin_noise_01_d.xbm",
}


def _linked_source(socket):
    links = tuple(getattr(socket, "links", ()) or ()) if socket is not None else ()
    return links[0].from_socket if links else None


def _replace_link(tree, target, source):
    if target is None or source is None:
        return
    replace_link(tree.links, source, target)


def _select_damage_value(
    nodes, links, name, location, fire, poison, electric, poison_gate, electric_gate
):
    fire_or_poison = mix_scalar_socket(
        nodes,
        links,
        f"{name} Fire/Poison",
        location,
        fire,
        poison,
        poison_gate,
    )
    return mix_scalar_socket(
        nodes,
        links,
        name,
        (location[0] + 200, location[1]),
        fire_or_poison,
        electric,
        electric_gate,
    )


def _pow_abs_color(nodes, links, color, exponent, location):
    split = new_labeled_node(
        nodes, "ShaderNodeSeparateColor", "Blackbody RGB", location
    )
    split.mode = "RGB"
    links.new(color, split.inputs["Color"])
    channels = []
    for index, name in enumerate(("Red", "Green", "Blue")):
        absolute = shader_nodes.math(
            nodes,
            links,
            "ABSOLUTE",
            split.outputs[name],
            name=f"abs({name})",
            location=(location[0] + 180, location[1] - index * 100),
        )
        channels.append(
            shader_nodes.math(
                nodes,
                links,
                "POWER",
                absolute,
                exponent,
                name=f"Absolute {name} Power",
                location=(location[0] + 360, location[1] - index * 100),
            )
        )
    return combine_color_socket(
        nodes,
        links,
        "Blackbody Color Exponent",
        (location[0] + 560, location[1] - 100),
        *channels,
    )


class MultilayerBlackbodyInject(Multilayered):
    texture_defaults = _TEXTURE_DEFAULTS

    def _texture(self, nodes, links, data, key, location, uv):
        node = self._relative_texture_node(
            nodes,
            self._texture_path(data, key),
            key,
            location,
            non_color=True,
            error_label="multilayer blackbody inject",
            extension="REPEAT",
        )
        if node is not None:
            vector_input = node.inputs["Vector"]
            links.new(uv, vector_input)
        return node

    def configure_multilayer_surface(self, Mat, Data, context):
        tree = context["tree"]
        nodes = tree.nodes
        links = tree.links
        principled = context["principled"]

        base_input = find_input(principled, "Base Color")
        metal_input = find_input(principled, "Metallic")
        rough_input = find_input(principled, "Roughness")
        base_color = _linked_source(base_input)
        base_metal = _linked_source(metal_input)
        base_rough = _linked_source(rough_input)
        if base_color is None or base_metal is None or base_rough is None:
            return

        uv_node = new_labeled_node(
            nodes, "ShaderNodeUVMap", "Blackbody UV", (-2320, -1020)
        )
        uv = uv_node.outputs["UV"]

        damage_mask = self._texture(
            nodes, links, Data, "DamageTypeRGBMask", (-2080, -820), uv
        )
        noise_intensity = param_float(
            Data,
            "DamageTypeNoiseIntesityAdd",
            _DEFAULTS["DamageTypeNoiseIntesityAdd"],
        )
        damage_noise = None
        if abs(noise_intensity) > 1.0e-12:
            noise_uv = param_vector(
                Data, "DamageTypeNoiseUV", _DEFAULTS["DamageTypeNoiseUV"]
            )
            animated_uv = shader_nodes.vector_math(
                nodes,
                links,
                "MULTIPLY",
                uv,
                (noise_uv[0], noise_uv[1], 1.0),
                name="Damage Noise UV Scale",
                location=(-2080, -1120),
            )
            if abs(noise_uv[2]) > 1.0e-12 or abs(noise_uv[3]) > 1.0e-12:
                scene_time = scene_time_socket(
                    tree.nodes, (-2080, -1420), "CP77 Blackbody Time"
                )
                offset_u = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    scene_time,
                    noise_uv[2],
                    name="Damage Noise U Speed",
                    location=(-1880, -1400),
                )
                offset_v = shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    scene_time,
                    noise_uv[3],
                    name="Damage Noise V Speed",
                    location=(-1880, -1500),
                )
                offset = new_labeled_node(
                    nodes,
                    "ShaderNodeCombineXYZ",
                    "Damage Noise UV Offset",
                    (-1660, -1430),
                )
                links.new(offset_u, offset.inputs["X"])
                links.new(offset_v, offset.inputs["Y"])
                animated_uv = shader_nodes.vector_math(
                    nodes,
                    links,
                    "ADD",
                    animated_uv,
                    offset.outputs["Vector"],
                    name="Animated Damage Noise UV",
                    location=(-1460, -1180),
                )
            damage_noise = self._texture(
                nodes, links, Data, "DamageTypeNoise", (-1240, -1120), animated_uv
            )

        fire_hsv = param_vector(Data, "FireHSV", _DEFAULTS["FireHSV"])
        poison_hsv = param_vector(Data, "PoisonHSV", _DEFAULTS["PoisonHSV"])
        electric_hsv = param_vector(Data, "ElectricHSV", _DEFAULTS["ElectricHSV"])
        material_param1 = material_property_socket(
            nodes,
            Mat,
            "cp77_MaterialParam1",
            0.0,
            (-2080, -1660),
            "MaterialParam1 Damage Type",
        )
        debug = param_float(Data, "Debug", _DEFAULTS["Debug"])
        picker = electric_hsv[3] if abs(debug) > 1.0e-12 else material_param1
        picker = shader_nodes.clamp(
            nodes,
            links,
            picker,
            0.0,
            2.0,
            name="Damage Type in [0, 2]",
            location=(-1840, -1660),
        )
        picker = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            picker,
            name="Damage Type Index",
            location=(-1480, -1660),
        )
        poison_gate = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            picker,
            0.5,
            name="Damage Type >= Poison",
            location=(-1280, -1620),
        )
        electric_gate = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            picker,
            1.5,
            name="Damage Type >= Electric",
            location=(-1280, -1720),
        )

        if damage_mask is not None:
            damage_color = damage_mask.outputs["Color"]
            fire_mask, poison_mask, electric_mask = separate_color_sockets(
                nodes, links, damage_color, "Damage Mask RGB", (-1640, -700)
            )
            damage_factor = _select_damage_value(
                nodes,
                links,
                "Selected Damage Mask",
                (-1260, -800),
                fire_mask,
                poison_mask,
                electric_mask,
                poison_gate,
                electric_gate,
            )
        else:
            damage_factor = 1.0

        selected_hue = _select_damage_value(
            nodes,
            links,
            "Selected Hue Mod",
            (-1200, -1780),
            fire_hsv[0],
            poison_hsv[0],
            electric_hsv[0],
            poison_gate,
            electric_gate,
        )
        selected_saturation = _select_damage_value(
            nodes,
            links,
            "Selected Saturation Mod",
            (-1200, -1880),
            fire_hsv[1],
            poison_hsv[1],
            electric_hsv[1],
            poison_gate,
            electric_gate,
        )
        selected_value = _select_damage_value(
            nodes,
            links,
            "Selected Value Mod",
            (-1200, -1980),
            fire_hsv[2],
            poison_hsv[2],
            electric_hsv[2],
            poison_gate,
            electric_gate,
        )

        if damage_noise is not None:
            noise_red = color_channel_socket(
                nodes,
                links,
                damage_noise.outputs["Color"],
                "Damage Noise Red",
                (-980, -1120),
                channel="Red",
            )
            noise_red = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                noise_red,
                noise_intensity,
                name="Damage Noise Intensity",
                location=(-780, -1120),
            )
            noise_factor = shader_nodes.math(
                nodes,
                links,
                "ADD",
                noise_red,
                1.0,
                name="Damage Noise + 1",
                location=(-580, -1120),
            )
            damage_factor = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                damage_factor,
                noise_factor,
                name="Damage Mask x Noise",
                location=(-380, -1000),
            )

        fire_roughness_mix = max(0.0, min(1.0, fire_hsv[3]))
        rough_temp_mod = mix_scalar_socket(
            nodes,
            links,
            "Roughness Temperature Modulation",
            (-700, -620),
            1.0,
            base_rough,
            fire_roughness_mix,
        )
        base_temperature = param_float(Data, "Temperature", _DEFAULTS["Temperature"])
        temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            rough_temp_mod,
            base_temperature,
            name="Base Temperature",
            location=(-500, -620),
        )
        material_param0 = material_property_socket(
            nodes,
            Mat,
            "cp77_MaterialParam0",
            0.0,
            (-700, -1480),
            "MaterialParam0 Temperature Progress",
        )
        maximum_delta = (
            param_float(Data, "MaximumTemperature", _DEFAULTS["MaximumTemperature"])
            - base_temperature
        )
        temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            material_param0,
            maximum_delta,
            temperature,
            name="Progressed Temperature",
            location=(-280, -720),
        )
        temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            temperature,
            damage_factor,
            name="Damage Temperature",
            location=(-80, -620),
        )
        blackbody_temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            temperature,
            120.0,
            name="Blackbody Temperature x120",
            location=(20, -620),
        )
        blackbody = blackbody_bundle(tree, blackbody_temperature, (220, -620))

        hue, saturation, value = rgb_to_hsv_bundle(
            tree, blackbody, (620, -620), "Blackbody HSV"
        )
        intensity = value
        hue = shader_nodes.math(
            nodes,
            links,
            "ADD",
            hue,
            selected_hue,
            name="Blackbody Hue Mod",
            location=(920, -620),
        )
        saturation = shader_nodes.math(
            nodes,
            links,
            "ADD",
            saturation,
            selected_saturation,
            name="Blackbody Saturation Mod",
            location=(920, -720),
        )
        value = shader_nodes.math(
            nodes,
            links,
            "ADD",
            value,
            selected_value,
            name="Blackbody Value Mod",
            location=(920, -820),
        )
        modified_blackbody = hsv_to_rgb_bundle(
            tree, hue, saturation, value, (1120, -700), "Damage HSV"
        )
        modified_blackbody = _pow_abs_color(
            nodes,
            links,
            modified_blackbody,
            param_float(Data, "ColorExponent", _DEFAULTS["ColorExponent"]),
            (1420, -620),
        )

        saturated_intensity = shader_nodes.math(
            nodes,
            links,
            "ADD",
            intensity,
            0.0,
            name="saturate(Blackbody Intensity)",
            location=(1120, -260),
            use_clamp=True,
        )
        base_suppression = shader_nodes.math(
            nodes,
            links,
            "POWER",
            saturated_intensity,
            0.25,
            name="Blackbody Base Suppression",
            location=(1320, -260),
        )
        base_influence = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            base_suppression,
            name="Remaining Base Influence",
            location=(1520, -260),
        )
        base_influence_rgb = combine_color_socket(
            nodes,
            links,
            "Remaining Base Influence RGB",
            (1720, -260),
            base_influence,
            base_influence,
            base_influence,
        )
        attenuated_base = mix_color_socket(
            nodes,
            links,
            "Attenuated Multilayer Base",
            base_color,
            base_influence_rgb,
            1.0,
            (1920, 220),
            blend_type="MULTIPLY",
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "Multilayer + Blackbody",
            attenuated_base,
            modified_blackbody,
            1.0,
            (2140, 220),
            blend_type="ADD",
        )

        poison_surface_mix = poison_hsv[3]
        poison_shift = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            intensity,
            poison_surface_mix,
            name="Poison Surface Shift",
            location=(1500, 40),
        )
        metal_influence = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            poison_shift,
            name="Heated Metal Influence",
            location=(1700, 40),
            use_clamp=True,
        )
        final_metal = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            base_metal,
            metal_influence,
            name="Heated Metalness",
            location=(1920, 20),
        )
        final_rough = shader_nodes.math(
            nodes,
            links,
            "ADD",
            base_rough,
            poison_shift,
            name="Heated Roughness",
            location=(1920, -80),
            use_clamp=True,
        )

        emissive_ev = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            intensity,
            param_float(Data, "Emissive", _DEFAULTS["Emissive"]),
            name="Blackbody Emissive EV",
            location=(1720, -480),
        )
        emission_strength = emissive_scale_bundle(
            tree,
            1.0,
            emissive_ev,
            (1940, -480),
            "Multilayer Blackbody Emission",
        ).outputs["Strength"]

        _replace_link(tree, base_input, final_color)
        _replace_link(tree, metal_input, final_metal)
        _replace_link(tree, rough_input, final_rough)
        _replace_link(
            tree, find_input(principled, "Emission Color", "Emission"), final_color
        )
        _replace_link(
            tree, find_input(principled, "Emission Strength"), emission_strength
        )


used_params = list(
    dict.fromkeys(
        multilayered.used_params
        + [
            "Emissive",
            "Temperature",
            "MaximumTemperature",
            "ColorExponent",
            "Debug",
            "FireHSV",
            "PoisonHSV",
            "ElectricHSV",
            "DamageTypeRGBMask",
            "DamageTypeNoise",
            "DamageTypeNoiseIntesityAdd",
            "DamageTypeNoiseUV",
        ]
    )
)

_CACHE_PARAMETERS = frozenset(used_params)


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, _CACHE_PARAMETERS)
