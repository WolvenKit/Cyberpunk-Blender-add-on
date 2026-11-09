from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .bundles import light_zone_emission, light_zone_index
from .graph import color_channel_socket, mix_color_socket, mix_scalar_socket
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
)
from .normal_math import create_cp77_normal_texture

_DEFAULT_ZONE_COLORS = (
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0, 1.0),
    (0.0, 30.0 / 255.0, 1.0, 1.0),
    (1.0, 1.0, 1.0, 1.0),
)


def _uv(tree, data):
    nodes = tree.nodes
    links = tree.links
    uv = new_labeled_node(nodes, "ShaderNodeTexCoord", "UV", (-1500, 200))
    mapping = new_labeled_node(
        nodes, "ShaderNodeMapping", "Vehicle Light UV", (-1280, 200)
    )
    mapping.vector_type = "POINT"
    mapping.inputs["Location"].default_value[0] = param_float(data, "UvOffsetX", 0.0)
    mapping.inputs["Location"].default_value[1] = param_float(data, "UvOffsetY", 0.0)
    mapping.inputs["Scale"].default_value[0] = param_float(data, "UvTilingX", 1.0)
    mapping.inputs["Scale"].default_value[1] = param_float(data, "UvTilingY", 1.0)
    links.new(
        uv.outputs.get("UV") or uv.outputs["UV"],
        mapping.inputs.get("Vector") or mapping.inputs["Vector"],
    )
    return uv.outputs.get("UV") or uv.outputs["UV"], mapping.outputs.get(
        "Vector"
    ) or mapping.outputs["Vector"]


class VehicleLights(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        principled = shader_nodes.principled_bsdf(nodes)
        if principled is None:
            return

        raw_uv, tiled_uv = _uv(tree, data)

        base = create_relative_texture_node(
            self, tree, data, "BaseColor", tiled_uv, (-1040, 560)
        )
        base_color = base.outputs.get("Color") if base else None
        base_alpha = base.outputs.get("Alpha") if base else None
        base_scale = new_labeled_node(
            nodes, "ShaderNodeRGB", "BaseColorScale", (-760, 700)
        )
        base_scale.outputs["Color"].default_value = param_vector(
            data, "BaseColorScale", (1.0, 1.0, 1.0, 1.0)
        )
        if base_alpha is not None:
            links.new(base_alpha, find_input(principled, "Alpha"))
        Mat.surface_render_method = "DITHERED"
        if hasattr(Mat, "alpha_threshold"):
            Mat.alpha_threshold = clamp01(param_float(data, "AlphaThreshold", 0.3333))

        metal_tex = create_relative_texture_node(
            self, tree, data, "Metalness", tiled_uv, (-1040, 280), non_color=True
        )
        rough_tex = create_relative_texture_node(
            self, tree, data, "Roughness", tiled_uv, (-1040, 60), non_color=True
        )
        metal = 0.0
        rough = 0.5
        if metal_tex is not None:
            metal_r = color_channel_socket(
                tree.nodes,
                tree.links,
                metal_tex.outputs.get("Color") or metal_tex.outputs["Color"],
                "Metalness R",
                (-800, 280),
            )
        if rough_tex is not None:
            rough_r = color_channel_socket(
                tree.nodes,
                tree.links,
                rough_tex.outputs.get("Color") or rough_tex.outputs["Color"],
                "Roughness R",
                (-800, 60),
            )
            rough_node = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY_ADD",
                name="Roughness Scale Bias",
                location=(-560, 60),
                use_clamp=True,
            ).node
            shader_nodes.socket_by_identifier(
                rough_node.inputs, "Value_001"
            ).default_value = param_float(data, "RoughnessScale", 1.0)
            shader_nodes.socket_by_identifier(
                rough_node.inputs, "Value_002"
            ).default_value = param_float(data, "RoughnessBias", 0.0)
            links.new(rough_r, rough_node.inputs["Value"])
            rough = rough_node.outputs["Value"]

        if metal_tex is not None:
            metal_node = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY_ADD",
                name="Metalness Scale Bias Exact",
                location=(-360, 280),
                use_clamp=True,
            ).node
            shader_nodes.socket_by_identifier(
                metal_node.inputs, "Value_001"
            ).default_value = param_float(data, "MetalnessScale", 1.0)
            shader_nodes.socket_by_identifier(
                metal_node.inputs, "Value_002"
            ).default_value = param_float(data, "MetalnessBias", 0.0)
            links.new(metal_r, metal_node.inputs["Value"])
            metal = metal_node.outputs["Value"]

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            uv=tiled_uv,
            strength_key="NormalStrength",
            default_strength=1.0,
            location=(-1040, -220),
        )
        if normal is not None:
            links.new(normal, find_input(principled, "Normal"))

        emission_tiling = param_float(data, "EmissionTiling", 1.0)
        emission_mapping = new_labeled_node(
            nodes, "ShaderNodeMapping", "Emission UV", (-1040, -500)
        )
        emission_mapping.vector_type = "POINT"
        emission_mapping.inputs["Scale"].default_value[0] = emission_tiling
        emission_mapping.inputs["Scale"].default_value[1] = emission_tiling
        links.new(
            raw_uv,
            emission_mapping.inputs.get("Vector") or emission_mapping.inputs["Vector"],
        )
        emissive_tex = create_relative_texture_node(
            self,
            tree,
            data,
            "Emissive",
            emission_mapping.outputs.get("Vector")
            or emission_mapping.outputs["Vector"],
            (-800, -500),
            non_color=True,
        )
        emission_mask = 0.0
        if emissive_tex is not None:
            emission_mask = color_channel_socket(
                tree.nodes,
                tree.links,
                emissive_tex.outputs.get("Color") or emissive_tex.outputs["Color"],
                "Emissive R",
                (-560, -500),
            )

        debug_colors = tuple(
            param_color(data, f"DebugLightsColor{index}", _DEFAULT_ZONE_COLORS[index])
            for index in range(4)
        )
        zone_color, emissive_blend, emission_strength = light_zone_emission(
            tree,
            light_zone_index(tree, (-1480, -720)),
            data,
            debug_colors,
            emission_mask,
            (-360, -620),
        )
        emission_color_input = find_input(principled, "Emission Color", "Emission")
        if emission_color_input is not None:
            links.new(zone_color, emission_color_input)
        emission_strength_input = find_input(principled, "Emission Strength")
        if emission_strength_input is not None:
            assign_socket(links, emission_strength, emission_strength_input)

        if base_color is not None:
            color_multiplier = mix_color_socket(
                nodes,
                links,
                "Base Scale to Zone Color",
                base_scale.outputs["Color"],
                zone_color,
                emissive_blend,
                (700, 420),
            )
            final_color = mix_color_socket(
                nodes,
                links,
                "Vehicle Light Color",
                base_color,
                color_multiplier,
                1.0,
                (900, 420),
                blend_type="MULTIPLY",
                clamp=True,
            )
            links.new(final_color, find_input(principled, "Base Color"))

        if metal_tex is not None:
            mask_sq = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                emission_mask,
                emission_mask,
                name="Emissive Mask²",
                location=(520, 160),
            )
            metal_curve = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                mask_sq,
                0.5,
                name="Metalness Emissive Curve",
                location=(700, 160),
            )
            metal_final = mix_scalar_socket(
                nodes,
                links,
                "Emission to Dielectric",
                (900, 160),
                metal,
                0.0,
                metal_curve,
            )
            links.new(metal_final, find_input(principled, "Metallic"))
        else:
            find_input(principled, "Metallic").default_value = 0.0

        if hasattr(rough, "is_output"):
            links.new(rough, find_input(principled, "Roughness"))
        else:
            find_input(principled, "Roughness").default_value = rough
