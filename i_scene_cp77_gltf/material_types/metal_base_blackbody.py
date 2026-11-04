from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from .blackbody_nodes import (
    blackbody_bundle,
    hsv_to_rgb_bundle,
    rgb_to_hsv_bundle,
)
from .bundles import emissive_scale_bundle
from .graph import (
    color_channel_socket,
    mix_color_socket,
    mix_scalar_socket,
    set_alpha_clip,
    value_socket,
)
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    default_texture_path,
    find_input,
    new_labeled_node,
    param_float,
    param_vector,
)
from .normal_math import create_cp77_normal_texture

TEMPLATE = "base\\fx\\shaders\\metal_base_blackbody.mt"

_TEXTURE_DEFAULTS = {
    "BaseColor": r"base\materials\placeholder\black.xbm",
    "Metalness": r"base\weapons\melee\w_melee_001__katana\textures\w_melee_001__katana_blade_m01.xbm",
    "Roughness": r"base\weapons\melee\w_melee_001__katana\textures\w_melee_001__katana_blade_r01.xbm",
    "Normal": r"base\materials\placeholder\normal.xbm",
    "EmissiveMask": r"base\materials\placeholder\white.xbm",
    "HeatDistribution": r"base\fx\_textures\masks\noise\fx_organic_noise_01_d.xbm",
}


_DEFAULTS = {
    "MaskMinimum": 0.300000012,
    "HeatTilingX": 2.0,
    "HeatTilingY": 2.0,
    "EmissiveEV": 10.0,
    "EmissiveEVRaytracingBias": 0.0,
    "EmissiveDirectionality": 0.0,
    "EnableRaytracedEmissive": 1.0,
    "AlphaThreshold": 0.0,
    "MaxTemperature": 12.9032249,
    "DebugTemperature": 1.0,
    "DebugOrExternalCurve": 0.0,
    "HeatMoveSpeed": 0.0,
}


class MetalBaseBlackbody(MaterialTypeBase):
    def _texture_path(self, data, key):
        return default_texture_path(data, key, _TEXTURE_DEFAULTS)

    def _texture(self, nodes, links, data, key, location, uv, *, non_color=False):
        node = self._relative_texture_node(
            nodes,
            self._texture_path(data, key),
            key,
            location,
            non_color=non_color,
            error_label="metal base blackbody",
            extension="REPEAT",
        )
        links.new(uv, node.inputs["Vector"])
        return node

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (2940, 160)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Metal Base Blackbody", (2660, 160)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2500, 660)).outputs[
            "UV"
        ]
        base = self._texture(nodes, links, data, "BaseColor", (-2260, 760), uv)
        metal = self._texture(
            nodes, links, data, "Metalness", (-2260, 520), uv, non_color=True
        )
        rough = self._texture(
            nodes, links, data, "Roughness", (-2260, 300), uv, non_color=True
        )
        emissive_mask = self._texture(
            nodes, links, data, "EmissiveMask", (-2260, 40), uv, non_color=True
        )

        mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "Heat Tiling", (-2260, -280)
        )
        heat_tile_x = param_float(data, "HeatTilingX", _DEFAULTS["HeatTilingX"])
        heat_tile_y = param_float(data, "HeatTilingY", _DEFAULTS["HeatTilingY"])
        mapping.inputs.get("Scale").default_value = (heat_tile_x, heat_tile_y, 1.0)
        links.new(uv, mapping.inputs["Vector"])
        heat = self._texture(
            nodes,
            links,
            data,
            "HeatDistribution",
            (-1800, -280),
            mapping.outputs["Vector"],
            non_color=True,
        )

        heat_value = color_channel_socket(
            nodes,
            links,
            heat.outputs["Color"],
            "HeatDistribution.x",
            (-1560, -280),
            channel="Red",
            mode="RGB",
        )
        move_speed = param_float(data, "HeatMoveSpeed", _DEFAULTS["HeatMoveSpeed"])
        if move_speed > 0.0:
            time = create_scene_time_value(tree, -1800, -520, "CP77 Blackbody Time")
            offset = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                time.outputs["Value"],
                move_speed,
                name="Time x HeatMoveSpeed",
                location=(-1560, -520),
            )
            offset = shader_nodes.math(
                nodes,
                links,
                "FRACT",
                offset,
                name="frac(Time x Speed)",
                location=(-1380, -520),
            )
            moving = shader_nodes.math(
                nodes,
                links,
                "ADD",
                heat_value,
                offset,
                name="Moving Heat",
                location=(-1380, -280),
            )
            moving = shader_nodes.math(
                nodes,
                links,
                "FRACT",
                moving,
                name="frac(Moving Heat)",
                location=(-1200, -280),
            )
            inverse = shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                1.0,
                moving,
                name="1 - Heat",
                location=(-1200, -420),
            )
            shaped = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                moving,
                inverse,
                name="Heat Bell",
                location=(-1020, -280),
            )
            shaped = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                shaped,
                4.0,
                name="Heat Bell x4",
                location=(-840, -280),
            )
            heat_value = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                shaped,
                shaped,
                name="Heat Bell Squared",
                location=(-660, -280),
            )

        mask_value = color_channel_socket(
            nodes,
            links,
            emissive_mask.outputs["Color"],
            "EmissiveMask.x",
            (-1800, 40),
            channel="Red",
            mode="RGB",
        )
        temperature_control = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            mask_value,
            heat_value,
            name="Mask x Heat",
            location=(-420, -120),
        )
        temperature_control = shader_nodes.math(
            nodes,
            links,
            "ADD",
            temperature_control,
            param_float(data, "MaskMinimum", _DEFAULTS["MaskMinimum"]),
            name="MaskMinimum",
            location=(-240, -120),
            use_clamp=True,
        )

        debug_temperature = value_socket(
            nodes,
            "DebugTemperature",
            param_float(data, "DebugTemperature", _DEFAULTS["DebugTemperature"]),
            (-1800, -760),
        )
        external_curve = value_socket(
            nodes,
            "MaterialParam0",
            1.0,
            (-1800, -900),
            "MaterialParam0 (external curve)",
        )
        curve = mix_scalar_socket(
            nodes,
            links,
            "Debug or External Curve",
            (-1380, -820),
            debug_temperature,
            external_curve,
            clamp01(
                param_float(
                    data, "DebugOrExternalCurve", _DEFAULTS["DebugOrExternalCurve"]
                )
            ),
        )
        temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            temperature_control,
            120.0 * param_float(data, "MaxTemperature", _DEFAULTS["MaxTemperature"]),
            name="Maximum Temperature",
            location=(0, -120),
        )
        temperature = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            temperature,
            curve,
            name="External Temperature Curve",
            location=(180, -120),
        )

        blackbody = blackbody_bundle(tree, temperature, (380, -120))
        heat_h, heat_s, heat_v = rgb_to_hsv_bundle(
            tree, blackbody, (700, -120), "Blackbody HSV"
        )

        clamp_value = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            heat_v,
            3.26,
            name="BlackBody Value x3.26",
            location=(980, -360),
            use_clamp=True,
        )
        clamp_value = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            clamp_value,
            name="Cold Base Influence",
            location=(1160, -360),
        )
        clamp_value = shader_nodes.math(
            nodes,
            links,
            "POWER",
            clamp_value,
            4.0,
            name="Cold Base Influence^4",
            location=(1340, -360),
        )
        scaled_base = mix_color_socket(
            nodes,
            links,
            "BaseColor x Cold Influence",
            base.outputs["Color"],
            clamp_value,
            1.0,
            (1320, 600),
            blend_type="MULTIPLY",
        )

        hsv_mod = param_vector(data, "HSV_Mod", (0.0, 0.0, 0.0, 0.0))
        modified_h = shader_nodes.math(
            nodes,
            links,
            "ADD",
            heat_h,
            hsv_mod[0],
            name="Hue + HSV_Mod.x",
            location=(1160, -40),
        )
        modified_s = shader_nodes.math(
            nodes,
            links,
            "ADD",
            heat_s,
            hsv_mod[1],
            name="Saturation + HSV_Mod.y",
            location=(1160, -120),
        )
        clamped_v = shader_nodes.math(
            nodes,
            links,
            "ADD",
            heat_v,
            0.0,
            name="saturate(Value)",
            location=(980, -200),
            use_clamp=True,
        )
        modified_v = shader_nodes.math(
            nodes,
            links,
            "ADD",
            clamped_v,
            hsv_mod[2],
            name="Value + HSV_Mod.z",
            location=(1160, -200),
        )
        modified_heat = hsv_to_rgb_bundle(
            tree,
            modified_h,
            modified_s,
            modified_v,
            (1360, -80),
            "Modified Blackbody",
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "BlackBody + BaseColor",
            modified_heat,
            scaled_base,
            1.0,
            (1540, 420),
            blend_type="ADD",
        )

        _, _, base_value = rgb_to_hsv_bundle(
            tree, base.outputs["Color"], (580, 760), "Base Color HSV"
        )
        blend = mix_scalar_socket(
            nodes, links, "Base Value Exponent", (960, 760), 0.525, 3.6, base_value
        )
        emissive_value = shader_nodes.math(
            nodes,
            links,
            "POWER",
            heat_v,
            blend,
            name="Absolute BlackBody Power",
            location=(1140, -620),
        )
        emissive_value = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emissive_value,
            2.0,
            name="Emissive Value x2",
            location=(1320, -620),
        )
        influence = shader_nodes.math(
            nodes,
            links,
            "ADD",
            emissive_value,
            0.0,
            name="saturate(Emissive Value)",
            location=(1500, -620),
            use_clamp=True,
        )

        metal_value = color_channel_socket(
            nodes,
            links,
            metal.outputs["Color"],
            "Metalness.x",
            (-1800, 520),
            channel="Red",
            mode="RGB",
        )
        rough_value = color_channel_socket(
            nodes,
            links,
            rough.outputs["Color"],
            "Roughness.x",
            (-1800, 300),
            channel="Red",
            mode="RGB",
        )
        final_metal = mix_scalar_socket(
            nodes, links, "Heated Metalness", (1880, 240), metal_value, 0.0, influence
        )
        final_rough = mix_scalar_socket(
            nodes, links, "Heated Roughness", (1880, 80), rough_value, 1.0, influence
        )

        emissive_ev = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emissive_value,
            param_float(data, "EmissiveEV", _DEFAULTS["EmissiveEV"]),
            name="EmissiveEV",
            location=(1680, -420),
        )
        emission_strength = emissive_scale_bundle(
            tree,
            1.0,
            emissive_ev,
            (1880, -420),
            "Blackbody Emission",
        ).outputs["Strength"]

        links.new(final_color, find_input(principled, "Base Color"))
        links.new(final_color, find_input(principled, "Emission Color", "Emission"))
        links.new(emission_strength, find_input(principled, "Emission Strength"))
        links.new(final_metal, find_input(principled, "Metallic"))
        links.new(final_rough, find_input(principled, "Roughness"))

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            strength_key=None,
            default_strength=1.0,
            location=(1880, -40),
            label="Normal",
        )
        if normal is not None:
            links.new(normal, find_input(principled, "Normal"))

        scaled_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            base.outputs["Alpha"],
            clamp_value,
            name="Base Alpha x Cold Influence",
            location=(1540, 760),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            scaled_alpha,
            param_float(data, "AlphaThreshold", _DEFAULTS["AlphaThreshold"]),
            name="AlphaMask",
            location=(1880, 620),
        )
        links.new(alpha, find_input(principled, "Alpha"))

        set_alpha_clip(Mat, 0.5)
        Mat.diffuse_color = (0.8, 0.18, 0.03, 1.0)
