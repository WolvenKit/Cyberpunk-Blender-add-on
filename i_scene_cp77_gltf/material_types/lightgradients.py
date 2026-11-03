from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from .graph import (
    connect_math,
    mix_color_socket,
    rgb_socket,
    safe_positive,
    safe_unit_interval,
    set_transparent,
    value_socket,
)
from .mat_common import (
    MaterialTypeBase,
    new_labeled_node,
    param_color,
    param_float,
)

_EPSILON = 1.0e-5
_MAX_ADDITIVE_COMPENSATION = 64.0


class LightGradients(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        set_transparent(Mat)

        bottom_color = param_color(data, "BottomColor", (1.0, 1.0, 1.0, 1.0))
        top_color = param_color(data, "TopColor", (1.0, 1.0, 1.0, 1.0))
        additive_alpha_blend = clamp01(param_float(data, "AdditiveAlphaBlend", 0.0))
        lerp_gradient = clamp01(param_float(data, "LerpGradient", 0.0))
        multiplier = max(0.0, param_float(data, "Multiplier", 1.0))
        min_proximity_alpha = max(0.0, param_float(data, "MinProximityAlpha", 0.0))
        max_proximity_alpha = max(0.0, param_float(data, "MaxProximityAlpha", 1.0))
        ground_position = param_float(data, "GroundPosition", 0.0)
        top_position = safe_positive(param_float(data, "TopPosition", 1.0))
        gradient_direction = safe_unit_interval(
            param_float(data, "GradientDirection", 0.5)
        )
        round_position = safe_unit_interval(
            param_float(data, "RoundGradientPosition", 0.5)
        )
        round_scale = max(0.0, param_float(data, "RoundGradientScale", 1.0))
        distance_modifier = safe_positive(
            param_float(data, "DistanceToSurfaceModifier", 1.0)
        )

        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1540, 80)
        )
        transparent = new_labeled_node(
            nodes, "ShaderNodeBsdfTransparent", "Transparent", (1160, -80)
        )
        emission = new_labeled_node(
            nodes, "ShaderNodeEmission", "Light Gradient Emission", (1160, 160)
        )
        surface_mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Final Alpha", (1380, 80)
        )
        links.new(transparent.outputs["BSDF"], surface_mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(surface_mix.inputs, "Shader_001"),
        )
        links.new(surface_mix.outputs["Shader"], output.inputs["Surface"])

        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Texture Coordinates", (-1600, 520)
        )
        separate_uv = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Separate UV", (-1420, 520)
        )
        links.new(texcoord.outputs["UV"], separate_uv.inputs["Vector"])
        uv_x = separate_uv.outputs["X"]
        uv_y = separate_uv.outputs["Y"]

        round_position_value = value_socket(
            nodes, "RoundGradientPosition", round_position, (-1600, 300)
        )
        one_minus_round = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            name="1 - RoundGradientPosition",
            location=(-1420, 250),
        ).node
        one_minus_round_output = connect_math(
            links, one_minus_round, second=round_position_value
        )
        uv_top = shader_nodes.math(
            nodes, links, "DIVIDE", name="UV Y / Round Position", location=(-1240, 410)
        ).node
        uv_top_output = connect_math(links, uv_top, uv_y, round_position_value)
        one_minus_y = shader_nodes.math(
            nodes, links, "SUBTRACT", 1.0, name="1 - UV Y", location=(-1420, 350)
        ).node
        one_minus_y_output = connect_math(links, one_minus_y, second=uv_y)
        uv_bottom = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            name="Inverse UV Y / Inverse Round Position",
            location=(-1240, 330),
        ).node
        uv_bottom_output = connect_math(
            links, uv_bottom, one_minus_y_output, one_minus_round_output
        )
        uv_y_min = shader_nodes.math(
            nodes, links, "MINIMUM", name="Round Gradient Y", location=(-1060, 380)
        ).node
        uv_y_min_output = connect_math(links, uv_y_min, uv_top_output, uv_bottom_output)

        centered_x = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            None,
            0.5,
            name="UV X - 0.5",
            location=(-1240, 570),
        ).node
        centered_x_output = connect_math(links, centered_x, uv_x)
        doubled_x = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            None,
            2.0,
            name="Round Gradient X",
            location=(-1060, 570),
        ).node
        doubled_x_output = connect_math(links, doubled_x, centered_x_output)
        radial_y = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            name="1 - Round Gradient Y",
            location=(-880, 410),
        ).node
        radial_y_output = connect_math(links, radial_y, second=uv_y_min_output)
        round_scale_value = value_socket(
            nodes, "RoundGradientScale", round_scale, (-1060, 200)
        )
        scaled_x = shader_nodes.math(
            nodes, links, "MULTIPLY", name="Scaled Round X", location=(-880, 570)
        ).node
        scaled_x_output = connect_math(
            links, scaled_x, doubled_x_output, round_scale_value
        )
        scaled_y = shader_nodes.math(
            nodes, links, "MULTIPLY", name="Scaled Round Y", location=(-700, 410)
        ).node
        scaled_y_output = connect_math(
            links, scaled_y, radial_y_output, round_scale_value
        )
        x_squared = shader_nodes.math(
            nodes, links, "MULTIPLY", name="Round X Squared", location=(-700, 570)
        ).node
        x_squared_output = connect_math(
            links, x_squared, scaled_x_output, scaled_x_output
        )
        y_squared = shader_nodes.math(
            nodes, links, "MULTIPLY", name="Round Y Squared", location=(-520, 410)
        ).node
        y_squared_output = connect_math(
            links, y_squared, scaled_y_output, scaled_y_output
        )
        radius_squared = shader_nodes.math(
            nodes, links, "ADD", name="Round Radius Squared", location=(-340, 500)
        ).node
        radius_squared_output = connect_math(
            links, radius_squared, x_squared_output, y_squared_output
        )
        radius = shader_nodes.math(
            nodes, links, "SQRT", name="Round Radius", location=(-160, 500)
        ).node
        radius_output = connect_math(links, radius, radius_squared_output)
        uv_mask_node = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            name="Round Gradient Mask",
            location=(20, 500),
            use_clamp=True,
        ).node
        uv_mask = connect_math(links, uv_mask_node, second=radius_output)

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "World Geometry", (-1600, -80)
        )
        separate_position = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "World Position", (-1420, 20)
        )
        links.new(geometry.outputs["Position"], separate_position.inputs["Vector"])
        z_minus_ground = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            None,
            ground_position,
            name="World Z - GroundPosition",
            location=(-1240, 20),
        ).node
        z_minus_ground_output = connect_math(
            links, z_minus_ground, separate_position.outputs["Z"]
        )
        above_ground = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            None,
            0.0,
            name="Above Ground",
            location=(-1060, 20),
        ).node
        above_ground_output = connect_math(links, above_ground, z_minus_ground_output)
        height_gradient = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            None,
            top_position,
            name="World Height Gradient",
            location=(-880, 20),
        ).node
        height_gradient_output = connect_math(
            links, height_gradient, above_ground_output
        )

        gradient_lerp_value = value_socket(
            nodes, "LerpGradient", lerp_gradient, (-520, 180)
        )
        color_factor = mix_color_socket(
            nodes,
            links,
            "Vertical / Round Gradient",
            height_gradient_output,
            uv_mask,
            gradient_lerp_value,
            (-160, 170),
        )
        color_factor_clamp = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            None,
            1.0,
            name="Saturate Color Gradient",
            location=(20, 170),
            use_clamp=True,
        ).node
        color_factor = connect_math(links, color_factor_clamp, color_factor)
        bottom = rgb_socket(nodes, "BottomColor", bottom_color, (-160, 40))
        top = rgb_socket(nodes, "TopColor", top_color, (-160, -80))
        gradient_color = mix_color_socket(
            nodes, links, "Bottom / Top Color", bottom, top, color_factor, (220, 100)
        )
        multiplier_value = value_socket(nodes, "Multiplier", multiplier, (220, -70))
        source_color = mix_color_socket(
            nodes,
            links,
            "Color Multiplier",
            gradient_color,
            multiplier_value,
            1.0,
            (420, 100),
            blend_type="MULTIPLY",
            clamp=False,
        )

        gradient_direction_value = value_socket(
            nodes, "GradientDirection", gradient_direction, (-1420, 760)
        )
        one_minus_direction = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            name="1 - GradientDirection",
            location=(-1240, 700),
        ).node
        one_minus_direction_output = connect_math(
            links, one_minus_direction, second=gradient_direction_value
        )
        vertical_first = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            name="UV Y / GradientDirection",
            location=(-1060, 800),
        ).node
        vertical_first_output = connect_math(
            links, vertical_first, uv_y, gradient_direction_value
        )
        vertical_second = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            name="Inverse UV Y / Inverse GradientDirection",
            location=(-1060, 700),
        ).node
        vertical_second_output = connect_math(
            links, vertical_second, one_minus_y_output, one_minus_direction_output
        )
        vertical_mask_node = shader_nodes.math(
            nodes, links, "MINIMUM", name="Top / Bottom Gradient", location=(-880, 760)
        ).node
        vertical_mask = connect_math(
            links, vertical_mask_node, vertical_first_output, vertical_second_output
        )

        camera = new_labeled_node(
            nodes, "ShaderNodeCameraData", "Camera Distance", (-1420, -220)
        )
        distance_divide = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            None,
            distance_modifier,
            name="Distance / DistanceToSurfaceModifier",
            location=(-1240, -220),
        ).node
        distance_output = connect_math(
            links, distance_divide, camera.outputs["View Distance"]
        )
        distance_clamp = shader_nodes.math(
            nodes,
            links,
            "MINIMUM",
            None,
            1.0,
            name="Distance Fade",
            location=(-1060, -220),
        ).node
        distance_fade = connect_math(links, distance_clamp, distance_output)

        invert_normal = shader_nodes.vector_math(
            nodes, links, "MULTIPLY", name="-World Normal", location=(-1420, -440)
        ).node
        shader_nodes.socket_by_identifier(
            invert_normal.inputs, "Vector_001"
        ).default_value = (-1.0, -1.0, -1.0)
        links.new(geometry.outputs["Normal"], invert_normal.inputs["Vector"])
        look_dot = shader_nodes.vector_math(
            nodes, links, "DOT_PRODUCT", name="Look At Dot", location=(-1240, -440)
        ).node
        links.new(invert_normal.outputs["Vector"], look_dot.inputs["Vector"])
        links.new(
            geometry.outputs["Incoming"],
            shader_nodes.socket_by_identifier(look_dot.inputs, "Vector_001"),
        )
        look_factor = shader_nodes.clamp(
            nodes,
            links,
            look_dot.outputs["Value"],
            name="Look Dot Saturate",
            location=(-1060, -440),
        )
        min_proximity = value_socket(
            nodes, "MinProximityAlpha", min_proximity_alpha, (-1060, -600)
        )
        max_proximity = value_socket(
            nodes, "MaxProximityAlpha", max_proximity_alpha, (-1060, -680)
        )
        proximity_range = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            name="Proximity Alpha Range",
            location=(-880, -640),
        ).node
        proximity_range_output = connect_math(
            links, proximity_range, max_proximity, min_proximity
        )
        proximity_scaled = shader_nodes.math(
            nodes, links, "MULTIPLY", name="View Angle Proximity", location=(-700, -600)
        ).node
        proximity_scaled_output = connect_math(
            links, proximity_scaled, proximity_range_output, look_factor
        )
        proximity_alpha = shader_nodes.math(
            nodes,
            links,
            "ADD",
            name="Soft Transparency Distance",
            location=(-520, -600),
        ).node
        proximity_alpha_output = connect_math(
            links, proximity_alpha, min_proximity, proximity_scaled_output
        )
        proximity_safe = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            None,
            _EPSILON,
            name="Safe Soft Distance",
            location=(-340, -600),
        ).node
        proximity_safe_output = connect_math(
            links, proximity_safe, proximity_alpha_output
        )
        separation = value_socket(
            nodes,
            "CP77 Surface Separation Preview",
            1.0,
            (-520, -760),
        )
        soft_divide = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            name="Soft Transparency Approximation",
            location=(-160, -640),
            use_clamp=True,
        ).node
        soft_alpha = connect_math(links, soft_divide, separation, proximity_safe_output)

        alpha_vertical = shader_nodes.math(
            nodes, links, "MULTIPLY", name="Soft × Vertical", location=(220, 700)
        ).node
        alpha_vertical_output = connect_math(
            links, alpha_vertical, soft_alpha, vertical_mask
        )
        alpha_round = shader_nodes.math(
            nodes, links, "MULTIPLY", name="× Round Mask", location=(400, 700)
        ).node
        alpha_round_output = connect_math(
            links, alpha_round, alpha_vertical_output, uv_mask
        )
        alpha_distance = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            name="× Camera Distance",
            location=(580, 700),
            use_clamp=True,
        ).node
        final_alpha = connect_math(
            links, alpha_distance, alpha_round_output, distance_fade
        )
        links.new(final_alpha, surface_mix.inputs["Factor"])

        safe_alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            None,
            1.0 / _MAX_ADDITIVE_COMPENSATION,
            name="Safe Alpha",
            location=(580, 500),
        ).node
        safe_alpha_output = connect_math(links, safe_alpha, final_alpha)
        inverse_alpha = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            1.0,
            name="Additive Compensation",
            location=(760, 500),
        ).node
        inverse_alpha_output = connect_math(
            links, inverse_alpha, second=safe_alpha_output
        )
        inverse_alpha_cap = shader_nodes.math(
            nodes,
            links,
            "MINIMUM",
            None,
            _MAX_ADDITIVE_COMPENSATION,
            name="Limit Additive Compensation",
            location=(940, 500),
        ).node
        additive_scale = connect_math(links, inverse_alpha_cap, inverse_alpha_output)
        additive_blend_value = value_socket(
            nodes, "AdditiveAlphaBlend", additive_alpha_blend, (760, 360)
        )
        additive_to_alpha = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            name="1 - Additive Compensation",
            location=(940, 400),
        ).node
        additive_to_alpha_output = connect_math(
            links, additive_to_alpha, second=additive_scale
        )
        additive_transition = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            name="AdditiveAlphaBlend Transition",
            location=(1120, 400),
        ).node
        additive_transition_output = connect_math(
            links,
            additive_transition,
            additive_to_alpha_output,
            additive_blend_value,
        )
        blend_scale_node = shader_nodes.math(
            nodes,
            links,
            "ADD",
            name="Additive / Alpha Blend Compensation",
            location=(1300, 400),
        ).node
        blend_scale = connect_math(
            links, blend_scale_node, additive_scale, additive_transition_output
        )
        final_color = mix_color_socket(
            nodes,
            links,
            "Premultiplied Blend Approximation",
            source_color,
            blend_scale,
            1.0,
            (940, 140),
            blend_type="MULTIPLY",
            clamp=False,
        )
        links.new(final_color, emission.inputs["Color"])
        emission.inputs["Strength"].default_value = 1.0

        Mat.diffuse_color = (*bottom_color[:3], 1.0)
