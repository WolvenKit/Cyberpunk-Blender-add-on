<<<<<<< Updated upstream
from .mat_common import (
    MaterialTypeBase,
    clamp01,
=======
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
>>>>>>> Stashed changes
    new_labeled_node,
    param_color,
    param_float,
)

<<<<<<< Updated upstream
from .graph import (
    connect_math as _connect_math,
    math_node as _math,
    mix_color_socket as _mix_color,
    multiply_color_socket as _multiply_color,
    rgb_socket as _rgb,
    safe_positive as _safe_positive,
    safe_unit_interval as _safe_unit_interval,
    set_transparent as _set_transparent_mode,
    value_socket as _value,
)

_TEMPLATE = "base\\fx\\shaders\\light_gradients.mt"
=======
>>>>>>> Stashed changes
_EPSILON = 1.0e-5
_MAX_ADDITIVE_COMPENSATION = 64.0


<<<<<<< Updated upstream
def _store_metadata(material, data):
    material["cp77_light_gradients_template"] = _TEMPLATE
    material["cp77_light_gradients_soft_transparency"] = (
        "SCENE_DEPTH_UNAVAILABLE_EDITABLE_SURFACE_SEPARATION_APPROXIMATION"
    )
    for name, default in (
        ("AdditiveAlphaBlend", 0.0),
        ("LerpGradient", 0.0),
        ("Multiplier", 1.0),
        ("MinProximityAlpha", 0.0),
        ("MaxProximityAlpha", 1.0),
        ("GroundPosition", 0.0),
        ("TopPosition", 1.0),
        ("GradientDirection", 0.5),
        ("RoundGradientPosition", 0.5),
        ("RoundGradientScale", 1.0),
        ("DistanceToSurfaceModifier", 1.0),
    ):
        material[f"cp77_{name}"] = param_float(data, name, default)
    material["cp77_BottomColor"] = list(
        param_color(data, "BottomColor", (1.0, 1.0, 1.0, 1.0))
    )
    material["cp77_TopColor"] = list(
        param_color(data, "TopColor", (1.0, 1.0, 1.0, 1.0))
    )


class LightGradients(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        _store_metadata(Mat, data)
        _set_transparent_mode(Mat)
=======
class LightGradients(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        set_transparent(Mat)
>>>>>>> Stashed changes

        bottom_color = param_color(data, "BottomColor", (1.0, 1.0, 1.0, 1.0))
        top_color = param_color(data, "TopColor", (1.0, 1.0, 1.0, 1.0))
        additive_alpha_blend = clamp01(param_float(data, "AdditiveAlphaBlend", 0.0))
        lerp_gradient = clamp01(param_float(data, "LerpGradient", 0.0))
        multiplier = max(0.0, param_float(data, "Multiplier", 1.0))
        min_proximity_alpha = max(0.0, param_float(data, "MinProximityAlpha", 0.0))
        max_proximity_alpha = max(0.0, param_float(data, "MaxProximityAlpha", 1.0))
        ground_position = param_float(data, "GroundPosition", 0.0)
<<<<<<< Updated upstream
        top_position = _safe_positive(param_float(data, "TopPosition", 1.0))
        gradient_direction = _safe_unit_interval(
            param_float(data, "GradientDirection", 0.5)
        )
        round_position = _safe_unit_interval(
            param_float(data, "RoundGradientPosition", 0.5)
        )
        round_scale = max(0.0, param_float(data, "RoundGradientScale", 1.0))
        distance_modifier = _safe_positive(
=======
        top_position = safe_positive(param_float(data, "TopPosition", 1.0))
        gradient_direction = safe_unit_interval(
            param_float(data, "GradientDirection", 0.5)
        )
        round_position = safe_unit_interval(
            param_float(data, "RoundGradientPosition", 0.5)
        )
        round_scale = max(0.0, param_float(data, "RoundGradientScale", 1.0))
        distance_modifier = safe_positive(
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        links.new(transparent.outputs[0], surface_mix.inputs[1])
        links.new(emission.outputs[0], surface_mix.inputs[2])
        links.new(surface_mix.outputs[0], output.inputs["Surface"])
=======
        links.new(transparent.outputs["BSDF"], surface_mix.inputs["Shader"])
        links.new(
            emission.outputs["Emission"],
            shader_nodes.socket_by_identifier(surface_mix.inputs, "Shader_001"),
        )
        links.new(surface_mix.outputs["Shader"], output.inputs["Surface"])
>>>>>>> Stashed changes

        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Texture Coordinates", (-1600, 520)
        )
        separate_uv = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Separate UV", (-1420, 520)
        )
<<<<<<< Updated upstream
        links.new(texcoord.outputs["UV"], separate_uv.inputs[0])
        uv_x = separate_uv.outputs["X"]
        uv_y = separate_uv.outputs["Y"]

        round_position_value = _value(
            nodes, "RoundGradientPosition", round_position, (-1600, 300)
        )
        one_minus_round = _math(
            nodes, "SUBTRACT", "1 - RoundGradientPosition", (-1420, 250), first=1.0
        )
        one_minus_round_output = _connect_math(
            links, one_minus_round, second=round_position_value
        )
        uv_top = _math(nodes, "DIVIDE", "UV Y / Round Position", (-1240, 410))
        uv_top_output = _connect_math(links, uv_top, uv_y, round_position_value)
        one_minus_y = _math(nodes, "SUBTRACT", "1 - UV Y", (-1420, 350), first=1.0)
        one_minus_y_output = _connect_math(links, one_minus_y, second=uv_y)
        uv_bottom = _math(
            nodes, "DIVIDE", "Inverse UV Y / Inverse Round Position", (-1240, 330)
        )
        uv_bottom_output = _connect_math(
            links, uv_bottom, one_minus_y_output, one_minus_round_output
        )
        uv_y_min = _math(nodes, "MINIMUM", "Round Gradient Y", (-1060, 380))
        uv_y_min_output = _connect_math(links, uv_y_min, uv_top_output, uv_bottom_output)

        centered_x = _math(nodes, "SUBTRACT", "UV X - 0.5", (-1240, 570), second=0.5)
        centered_x_output = _connect_math(links, centered_x, uv_x)
        doubled_x = _math(nodes, "MULTIPLY", "Round Gradient X", (-1060, 570), second=2.0)
        doubled_x_output = _connect_math(links, doubled_x, centered_x_output)
        radial_y = _math(nodes, "SUBTRACT", "1 - Round Gradient Y", (-880, 410), first=1.0)
        radial_y_output = _connect_math(links, radial_y, second=uv_y_min_output)
        round_scale_value = _value(
            nodes, "RoundGradientScale", round_scale, (-1060, 200)
        )
        scaled_x = _math(nodes, "MULTIPLY", "Scaled Round X", (-880, 570))
        scaled_x_output = _connect_math(links, scaled_x, doubled_x_output, round_scale_value)
        scaled_y = _math(nodes, "MULTIPLY", "Scaled Round Y", (-700, 410))
        scaled_y_output = _connect_math(links, scaled_y, radial_y_output, round_scale_value)
        x_squared = _math(nodes, "MULTIPLY", "Round X Squared", (-700, 570))
        x_squared_output = _connect_math(links, x_squared, scaled_x_output, scaled_x_output)
        y_squared = _math(nodes, "MULTIPLY", "Round Y Squared", (-520, 410))
        y_squared_output = _connect_math(links, y_squared, scaled_y_output, scaled_y_output)
        radius_squared = _math(nodes, "ADD", "Round Radius Squared", (-340, 500))
        radius_squared_output = _connect_math(
            links, radius_squared, x_squared_output, y_squared_output
        )
        radius = _math(nodes, "SQRT", "Round Radius", (-160, 500))
        radius_output = _connect_math(links, radius, radius_squared_output)
        uv_mask_node = _math(
            nodes, "SUBTRACT", "Round Gradient Mask", (20, 500), first=1.0, clamp=True
        )
        uv_mask = _connect_math(links, uv_mask_node, second=radius_output)
=======
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
>>>>>>> Stashed changes

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "World Geometry", (-1600, -80)
        )
        separate_position = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "World Position", (-1420, 20)
        )
<<<<<<< Updated upstream
        links.new(geometry.outputs["Position"], separate_position.inputs[0])
        z_minus_ground = _math(
            nodes, "SUBTRACT", "World Z - GroundPosition", (-1240, 20), second=ground_position
        )
        z_minus_ground_output = _connect_math(
            links, z_minus_ground, separate_position.outputs["Z"]
        )
        above_ground = _math(
            nodes, "MAXIMUM", "Above Ground", (-1060, 20), second=0.0
        )
        above_ground_output = _connect_math(links, above_ground, z_minus_ground_output)
        height_gradient = _math(
            nodes, "DIVIDE", "World Height Gradient", (-880, 20), second=top_position
        )
        height_gradient_output = _connect_math(links, height_gradient, above_ground_output)

        gradient_lerp_value = _value(
            nodes, "LerpGradient", lerp_gradient, (-520, 180)
        )
        color_factor = _mix_color(
=======
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
>>>>>>> Stashed changes
            nodes,
            links,
            "Vertical / Round Gradient",
            height_gradient_output,
            uv_mask,
            gradient_lerp_value,
            (-160, 170),
        )
<<<<<<< Updated upstream
        color_factor_clamp = _math(
            nodes, "MULTIPLY", "Saturate Color Gradient", (20, 170), second=1.0, clamp=True
        )
        color_factor = _connect_math(links, color_factor_clamp, color_factor)
        bottom = _rgb(nodes, "BottomColor", bottom_color, (-160, 40))
        top = _rgb(nodes, "TopColor", top_color, (-160, -80))
        gradient_color = _mix_color(
            nodes, links, "Bottom / Top Color", bottom, top, color_factor, (220, 100)
        )
        multiplier_value = _value(nodes, "Multiplier", multiplier, (220, -70))
        source_color = _multiply_color(
            nodes, links, "Color Multiplier", gradient_color, multiplier_value, (420, 100)
        )

        gradient_direction_value = _value(
            nodes, "GradientDirection", gradient_direction, (-1420, 760)
        )
        one_minus_direction = _math(
            nodes, "SUBTRACT", "1 - GradientDirection", (-1240, 700), first=1.0
        )
        one_minus_direction_output = _connect_math(
            links, one_minus_direction, second=gradient_direction_value
        )
        vertical_first = _math(
            nodes, "DIVIDE", "UV Y / GradientDirection", (-1060, 800)
        )
        vertical_first_output = _connect_math(
            links, vertical_first, uv_y, gradient_direction_value
        )
        vertical_second = _math(
            nodes, "DIVIDE", "Inverse UV Y / Inverse GradientDirection", (-1060, 700)
        )
        vertical_second_output = _connect_math(
            links, vertical_second, one_minus_y_output, one_minus_direction_output
        )
        vertical_mask_node = _math(
            nodes, "MINIMUM", "Top / Bottom Gradient", (-880, 760)
        )
        vertical_mask = _connect_math(
=======
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
>>>>>>> Stashed changes
            links, vertical_mask_node, vertical_first_output, vertical_second_output
        )

        camera = new_labeled_node(
            nodes, "ShaderNodeCameraData", "Camera Distance", (-1420, -220)
        )
<<<<<<< Updated upstream
        distance_divide = _math(
            nodes,
            "DIVIDE",
            "Distance / DistanceToSurfaceModifier",
            (-1240, -220),
            second=distance_modifier,
        )
        distance_output = _connect_math(
            links, distance_divide, camera.outputs["View Distance"]
        )
        distance_clamp = _math(
            nodes, "MINIMUM", "Distance Fade", (-1060, -220), second=1.0
        )
        distance_fade = _connect_math(links, distance_clamp, distance_output)

        invert_normal = new_labeled_node(
            nodes, "ShaderNodeVectorMath", "-World Normal", (-1420, -440)
        )
        invert_normal.operation = "MULTIPLY"
        invert_normal.inputs[1].default_value = (-1.0, -1.0, -1.0)
        links.new(geometry.outputs["Normal"], invert_normal.inputs[0])
        look_dot = new_labeled_node(
            nodes, "ShaderNodeVectorMath", "Look At Dot", (-1240, -440)
        )
        look_dot.operation = "DOT_PRODUCT"
        links.new(invert_normal.outputs[0], look_dot.inputs[0])
        links.new(geometry.outputs["Incoming"], look_dot.inputs[1])
        look_min = _math(nodes, "MAXIMUM", "Look Dot Min", (-1060, -440), second=0.0)
        look_min_output = _connect_math(links, look_min, look_dot.outputs["Value"])
        look_max = _math(nodes, "MINIMUM", "Look Dot Saturate", (-880, -440), second=1.0)
        look_factor = _connect_math(links, look_max, look_min_output)
        min_proximity = _value(
            nodes, "MinProximityAlpha", min_proximity_alpha, (-1060, -600)
        )
        max_proximity = _value(
            nodes, "MaxProximityAlpha", max_proximity_alpha, (-1060, -680)
        )
        proximity_range = _math(
            nodes, "SUBTRACT", "Proximity Alpha Range", (-880, -640)
        )
        proximity_range_output = _connect_math(
            links, proximity_range, max_proximity, min_proximity
        )
        proximity_scaled = _math(
            nodes, "MULTIPLY", "View Angle Proximity", (-700, -600)
        )
        proximity_scaled_output = _connect_math(
            links, proximity_scaled, proximity_range_output, look_factor
        )
        proximity_alpha = _math(
            nodes, "ADD", "Soft Transparency Distance", (-520, -600)
        )
        proximity_alpha_output = _connect_math(
            links, proximity_alpha, min_proximity, proximity_scaled_output
        )
        proximity_safe = _math(
            nodes, "MAXIMUM", "Safe Soft Distance", (-340, -600), second=_EPSILON
        )
        proximity_safe_output = _connect_math(
            links, proximity_safe, proximity_alpha_output
        )
        separation = _value(
=======
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
>>>>>>> Stashed changes
            nodes,
            "CP77 Surface Separation Preview",
            1.0,
            (-520, -760),
        )
<<<<<<< Updated upstream
        soft_divide = _math(
            nodes, "DIVIDE", "Soft Transparency Approximation", (-160, -640), clamp=True
        )
        soft_alpha = _connect_math(
            links, soft_divide, separation, proximity_safe_output
        )

        alpha_vertical = _math(nodes, "MULTIPLY", "Soft × Vertical", (220, 700))
        alpha_vertical_output = _connect_math(
            links, alpha_vertical, soft_alpha, vertical_mask
        )
        alpha_round = _math(nodes, "MULTIPLY", "× Round Mask", (400, 700))
        alpha_round_output = _connect_math(
            links, alpha_round, alpha_vertical_output, uv_mask
        )
        alpha_distance = _math(
            nodes, "MULTIPLY", "× Camera Distance", (580, 700), clamp=True
        )
        final_alpha = _connect_math(
            links, alpha_distance, alpha_round_output, distance_fade
        )
        links.new(final_alpha, surface_mix.inputs[0])

        safe_alpha = _math(
            nodes, "MAXIMUM", "Safe Alpha", (580, 500), second=1.0 / _MAX_ADDITIVE_COMPENSATION
        )
        safe_alpha_output = _connect_math(links, safe_alpha, final_alpha)
        inverse_alpha = _math(
            nodes, "DIVIDE", "Additive Compensation", (760, 500), first=1.0
        )
        inverse_alpha_output = _connect_math(
            links, inverse_alpha, second=safe_alpha_output
        )
        inverse_alpha_cap = _math(
            nodes,
            "MINIMUM",
            "Limit Additive Compensation",
            (940, 500),
            second=_MAX_ADDITIVE_COMPENSATION,
        )
        additive_scale = _connect_math(
            links, inverse_alpha_cap, inverse_alpha_output
        )
        additive_blend_value = _value(
            nodes, "AdditiveAlphaBlend", additive_alpha_blend, (760, 360)
        )
        additive_to_alpha = _math(
            nodes,
            "SUBTRACT",
            "1 - Additive Compensation",
            (940, 400),
            first=1.0,
        )
        additive_to_alpha_output = _connect_math(
            links, additive_to_alpha, second=additive_scale
        )
        additive_transition = _math(
            nodes,
            "MULTIPLY",
            "AdditiveAlphaBlend Transition",
            (1120, 400),
        )
        additive_transition_output = _connect_math(
=======
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
>>>>>>> Stashed changes
            links,
            additive_transition,
            additive_to_alpha_output,
            additive_blend_value,
        )
<<<<<<< Updated upstream
        blend_scale_node = _math(
            nodes,
            "ADD",
            "Additive / Alpha Blend Compensation",
            (1300, 400),
        )
        blend_scale = _connect_math(
            links, blend_scale_node, additive_scale, additive_transition_output
        )
        final_color = _multiply_color(
=======
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
>>>>>>> Stashed changes
            nodes,
            links,
            "Premultiplied Blend Approximation",
            source_color,
            blend_scale,
<<<<<<< Updated upstream
            (940, 140),
=======
            1.0,
            (940, 140),
            blend_type="MULTIPLY",
            clamp=False,
>>>>>>> Stashed changes
        )
        links.new(final_color, emission.inputs["Color"])
        emission.inputs["Strength"].default_value = 1.0

        Mat.diffuse_color = (*bottom_color[:3], 1.0)
<<<<<<< Updated upstream


used_params = [
    "AdditiveAlphaBlend",
    "BottomColor",
    "TopColor",
    "LerpGradient",
    "Multiplier",
    "MinProximityAlpha",
    "MaxProximityAlpha",
    "GroundPosition",
    "TopPosition",
    "GradientDirection",
    "RoundGradientPosition",
    "RoundGradientScale",
    "DistanceToSurfaceModifier",
]
=======
>>>>>>> Stashed changes
