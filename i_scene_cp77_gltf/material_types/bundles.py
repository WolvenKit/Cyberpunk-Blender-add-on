from __future__ import annotations

from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from ..entity.domain.light_zones import ZONES, zone_color_property, zone_level_property
from ..materials.blender.nodes import create_node
from .mat_common import (
    add_group_node,
    get_or_build_node_group,
    param_float,
    param_vector,
)


def material_bundle_node(tree, group, location, label, values):
    node = add_group_node(tree, group, location, label=label)
    node.width = 210.0
    node["cp77_material_bundle"] = group.name
    node.show_options = False
    for name, value in values.items():
        assign_socket(tree.links, value, node.inputs[name])
    return node


def _smoothstep_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        curve = group.nodes.new("ShaderNodeMapRange")
        curve.interpolation_type = "SMOOTHSTEP"
        curve.clamp = True
        curve.inputs["To Min"].default_value = 0.0
        curve.inputs["To Max"].default_value = 1.0
        group.links.new(group_input.outputs["Value"], curve.inputs["Value"])
        group.links.new(group_input.outputs["Edge 0"], curve.inputs["From Min"])
        group.links.new(group_input.outputs["Edge 1"], curve.inputs["From Max"])
        group.links.new(curve.outputs["Result"], group_output.inputs["Result"])

    return get_or_build_node_group(
        "CP77 Smoothstep Bundle v1",
        (
            ("NodeSocketFloat", "Value"),
            ("NodeSocketFloat", "Edge 0"),
            ("NodeSocketFloat", "Edge 1"),
        ),
        (("NodeSocketFloat", "Result"),),
        build,
    )


def smoothstep_socket(tree, value, edge0, edge1, location, label="Smoothstep"):
    node = material_bundle_node(
        tree,
        _smoothstep_group(),
        location,
        label,
        {"Value": value, "Edge 0": edge0, "Edge 1": edge1},
    )
    return node.outputs["Result"]


def _normal_blend_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")
        base_vector, detail_vector = (
            group_input.outputs["Base"],
            group_input.outputs["Detail"],
        )

        base = nodes.new("ShaderNodeSeparateXYZ")
        detail = nodes.new("ShaderNodeSeparateXYZ")
        links.new(base_vector, base.inputs["Vector"])
        links.new(detail_vector, detail.inputs["Vector"])
        # (ax bz + bx az, ay bz + by az, az bz) for base a and detail b.
        base_z = nodes.new("ShaderNodeCombineXYZ")
        base_z.label = "Base Z, Base Z, 0"
        links.new(base.outputs["Z"], base_z.inputs["X"])
        links.new(base.outputs["Z"], base_z.inputs["Y"])
        cross = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            base_z.outputs["Vector"],
            detail_vector,
            label="Detail XY × Base Z",
        )
        combined = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            base_vector,
            detail.outputs["Z"],
            cross,
            label="Blended Normal",
        )

        mixed = shader_nodes.vector_lerp(
            nodes,
            links,
            base_vector,
            combined,
            group_input.outputs["Factor"],
            name="Weighted Normal",
        )
        normalized = shader_nodes.vector_math(
            nodes, links, "NORMALIZE", mixed, label="Normalize"
        )
        links.new(normalized, group_output.inputs["Normal"])

    return get_or_build_node_group(
        "CP77 Tangent Normal Blend Bundle v2",
        (
            ("NodeSocketVector", "Base"),
            ("NodeSocketVector", "Detail"),
            ("NodeSocketFloat", "Factor"),
        ),
        (("NodeSocketVector", "Normal"),),
        build,
    )


def tangent_normal_blend_socket(
    tree,
    base,
    detail,
    factor,
    location,
    label="Tangent Normal Blend",
):
    node = material_bundle_node(
        tree,
        _normal_blend_group(),
        location,
        label,
        {"Base": base, "Detail": detail, "Factor": factor},
    )
    return node.outputs["Normal"]


def _additive_normal_blend_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")
        added = shader_nodes.vector_math(nodes, links, "ADD", label="Add Detail").node
        target = shader_nodes.vector_math(
            nodes, links, "NORMALIZE", label="Normalize Target"
        ).node
        delta = shader_nodes.vector_math(
            nodes, links, "SUBTRACT", label="Detail Delta"
        ).node
        weighted = shader_nodes.vector_math(
            nodes, links, "SCALE", label="Blend Weight"
        ).node
        mixed = shader_nodes.vector_math(
            nodes, links, "ADD", label="Weighted Normal"
        ).node
        normalized = shader_nodes.vector_math(
            nodes, links, "NORMALIZE", label="Normalize"
        ).node
        links.new(group_input.outputs["Base"], added.inputs["Vector"])
        links.new(
            group_input.outputs["Detail"],
            shader_nodes.socket_by_identifier(added.inputs, "Vector_001"),
        )
        links.new(added.outputs["Vector"], target.inputs["Vector"])
        links.new(target.outputs["Vector"], delta.inputs["Vector"])
        links.new(
            group_input.outputs["Base"],
            shader_nodes.socket_by_identifier(delta.inputs, "Vector_001"),
        )
        links.new(delta.outputs["Vector"], weighted.inputs["Vector"])
        links.new(group_input.outputs["Factor"], weighted.inputs["Scale"])
        links.new(group_input.outputs["Base"], mixed.inputs["Vector"])
        links.new(
            weighted.outputs["Vector"],
            shader_nodes.socket_by_identifier(mixed.inputs, "Vector_001"),
        )
        links.new(mixed.outputs["Vector"], normalized.inputs["Vector"])
        links.new(normalized.outputs["Vector"], group_output.inputs["Normal"])

    return get_or_build_node_group(
        "CP77 Additive Normal Blend Bundle v1",
        (
            ("NodeSocketVector", "Base"),
            ("NodeSocketVector", "Detail"),
            ("NodeSocketFloat", "Factor"),
        ),
        (("NodeSocketVector", "Normal"),),
        build,
    )


def additive_normal_blend_socket(
    tree,
    base,
    detail,
    factor,
    location,
    label="Additive Normal Blend",
):
    node = material_bundle_node(
        tree,
        _additive_normal_blend_group(),
        location,
        label,
        {"Base": base, "Detail": detail, "Factor": factor},
    )
    return node.outputs["Normal"]


def _emissive_scale_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")

        safe_scale = shader_nodes.math(nodes, links, "MAXIMUM", label="Safe Scale").node
        shader_nodes.socket_by_identifier(
            safe_scale.inputs, "Value_001"
        ).default_value = 1.0e-7
        log_scale = shader_nodes.math(
            nodes, links, "LOGARITHM", label="log2 Scale"
        ).node
        shader_nodes.socket_by_identifier(
            log_scale.inputs, "Value_001"
        ).default_value = 2.0
        scaled_ev = shader_nodes.math(nodes, links, "ADD", label="Scaled EV").node
        clamped_ev = shader_nodes.math(
            nodes, links, "MAXIMUM", label="Non-negative EV"
        ).node
        shader_nodes.socket_by_identifier(
            clamped_ev.inputs, "Value_001"
        ).default_value = 0.0
        exponent = shader_nodes.math(nodes, links, "POWER", label="2^EV").node
        exponent.inputs["Value"].default_value = 2.0
        scaled = shader_nodes.math(
            nodes, links, "MULTIPLY", label="Exposure × Scale"
        ).node
        subtract = shader_nodes.math(
            nodes, links, "SUBTRACT", label="Linear Strength"
        ).node
        shader_nodes.socket_by_identifier(
            subtract.inputs, "Value_001"
        ).default_value = 1.0
        strength = shader_nodes.math(
            nodes, links, "MAXIMUM", label="Non-negative Strength"
        ).node
        shader_nodes.socket_by_identifier(
            strength.inputs, "Value_001"
        ).default_value = 0.0
        raw_scaled = shader_nodes.math(
            nodes, links, "MULTIPLY", label="Exposure × Raw Scale"
        ).node
        raw_subtract = shader_nodes.math(
            nodes, links, "SUBTRACT", label="Raw Linear Strength"
        ).node
        shader_nodes.socket_by_identifier(
            raw_subtract.inputs, "Value_001"
        ).default_value = 1.0
        raw_strength = shader_nodes.math(
            nodes, links, "MAXIMUM", label="Non-negative Raw Strength"
        ).node
        shader_nodes.socket_by_identifier(
            raw_strength.inputs, "Value_001"
        ).default_value = 0.0

        links.new(group_input.outputs["Scale"], safe_scale.inputs["Value"])
        links.new(safe_scale.outputs["Value"], log_scale.inputs["Value"])
        links.new(group_input.outputs["Base EV"], scaled_ev.inputs["Value"])
        links.new(
            log_scale.outputs["Value"],
            shader_nodes.socket_by_identifier(scaled_ev.inputs, "Value_001"),
        )
        links.new(scaled_ev.outputs["Value"], clamped_ev.inputs["Value"])
        links.new(
            group_input.outputs["Base EV"],
            shader_nodes.socket_by_identifier(exponent.inputs, "Value_001"),
        )
        links.new(exponent.outputs["Value"], scaled.inputs["Value"])
        links.new(
            safe_scale.outputs["Value"],
            shader_nodes.socket_by_identifier(scaled.inputs, "Value_001"),
        )
        links.new(scaled.outputs["Value"], subtract.inputs["Value"])
        links.new(subtract.outputs["Value"], strength.inputs["Value"])
        links.new(exponent.outputs["Value"], raw_scaled.inputs["Value"])
        links.new(
            group_input.outputs["Scale"],
            shader_nodes.socket_by_identifier(raw_scaled.inputs, "Value_001"),
        )
        links.new(raw_scaled.outputs["Value"], raw_subtract.inputs["Value"])
        links.new(raw_subtract.outputs["Value"], raw_strength.inputs["Value"])
        links.new(clamped_ev.outputs["Value"], group_output.inputs["Scaled EV"])
        links.new(strength.outputs["Value"], group_output.inputs["Strength"])
        links.new(raw_strength.outputs["Value"], group_output.inputs["Raw Strength"])

    return get_or_build_node_group(
        "CP77 Emissive Scale Bundle v1",
        (("NodeSocketFloat", "Scale"), ("NodeSocketFloat", "Base EV")),
        (
            ("NodeSocketFloat", "Scaled EV"),
            ("NodeSocketFloat", "Strength"),
            ("NodeSocketFloat", "Raw Strength"),
        ),
        build,
    )


def emissive_scale_bundle(tree, scale, base_ev, location, label="Emissive Scale"):
    return material_bundle_node(
        tree,
        _emissive_scale_group(),
        location,
        label,
        {"Scale": scale, "Base EV": base_ev},
    )


def _alpha_contrast_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")
        contrast = shader_nodes.clamp(
            nodes, links, None, -1.0, 1.0, label="Contrast Range"
        ).node
        angle = shader_nodes.math(
            nodes, links, "MULTIPLY_ADD", label="Contrast Angle"
        ).node
        shader_nodes.socket_by_identifier(
            angle.inputs, "Value_001"
        ).default_value = 0.7853981633974483
        shader_nodes.socket_by_identifier(
            angle.inputs, "Value_002"
        ).default_value = 0.7853981633974483
        slope = shader_nodes.math(nodes, links, "TANGENT", label="Contrast Slope").node
        centered = shader_nodes.math(
            nodes, links, "SUBTRACT", label="Center Alpha"
        ).node
        shader_nodes.socket_by_identifier(
            centered.inputs, "Value_001"
        ).default_value = 0.5
        scaled = shader_nodes.math(nodes, links, "MULTIPLY", label="Apply Slope").node
        result = shader_nodes.math(nodes, links, "ADD", label="Restore Center").node
        shader_nodes.socket_by_identifier(
            result.inputs, "Value_001"
        ).default_value = 0.5
        result.use_clamp = True
        links.new(group_input.outputs["Contrast"], contrast.inputs["Value"])
        links.new(contrast.outputs["Result"], angle.inputs["Value"])
        links.new(angle.outputs["Value"], slope.inputs["Value"])
        links.new(group_input.outputs["Alpha"], centered.inputs["Value"])
        links.new(centered.outputs["Value"], scaled.inputs["Value"])
        links.new(
            slope.outputs["Value"],
            shader_nodes.socket_by_identifier(scaled.inputs, "Value_001"),
        )
        links.new(scaled.outputs["Value"], result.inputs["Value"])
        links.new(result.outputs["Value"], group_output.inputs["Alpha"])

    return get_or_build_node_group(
        "CP77 Alpha Contrast Bundle v2",
        (("NodeSocketFloat", "Alpha"), ("NodeSocketFloat", "Contrast")),
        (("NodeSocketFloat", "Alpha"),),
        build,
    )


def alpha_contrast_socket(tree, alpha, contrast, location, label="Alpha Contrast"):
    node = material_bundle_node(
        tree,
        _alpha_contrast_group(),
        location,
        label,
        {"Alpha": alpha, "Contrast": contrast},
    )
    return node.outputs["Alpha"]


def _signed_fraction_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")
        separate = nodes.new("ShaderNodeSeparateXYZ")
        combine = nodes.new("ShaderNodeCombineXYZ")
        links.new(group_input.outputs["Value"], separate.inputs["Vector"])
        for axis in ("X", "Y"):
            absolute = shader_nodes.math(
                nodes, links, "ABSOLUTE", label=f"Absolute {axis}"
            ).node
            fraction = shader_nodes.math(
                nodes, links, "FRACT", label=f"Fraction {axis}"
            ).node
            sign = shader_nodes.math(nodes, links, "SIGN", label=f"Sign {axis}").node
            signed = shader_nodes.math(
                nodes, links, "MULTIPLY", label=f"Signed Fraction {axis}"
            ).node
            links.new(separate.outputs[axis], absolute.inputs["Value"])
            links.new(absolute.outputs["Value"], fraction.inputs["Value"])
            links.new(separate.outputs[axis], sign.inputs["Value"])
            links.new(fraction.outputs["Value"], signed.inputs["Value"])
            links.new(
                sign.outputs["Value"],
                shader_nodes.socket_by_identifier(signed.inputs, "Value_001"),
            )
            links.new(signed.outputs["Value"], combine.inputs[axis])
        links.new(combine.outputs["Vector"], group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 Signed Fraction Bundle v1",
        (("NodeSocketVector", "Value"),),
        (("NodeSocketVector", "Value"),),
        build,
    )


def signed_fraction_socket(tree, value, location, label="Signed Fraction"):
    node = material_bundle_node(
        tree,
        _signed_fraction_group(),
        location,
        label,
        {"Value": value},
    )
    node.name = label
    return node.outputs["Value"]


def _decal_uv_transform_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")

        texel = shader_nodes.vector_math(nodes, links, "ADD", label="Half Texel").node
        frame_scale = shader_nodes.vector_math(
            nodes, links, "DIVIDE", label="Frame Scale"
        ).node
        frame_offset = shader_nodes.vector_math(
            nodes, links, "ADD", label="Frame Offset"
        ).node
        atlas_scale = shader_nodes.vector_math(
            nodes, links, "MULTIPLY", label="Atlas Scale"
        ).node
        atlas_offset = shader_nodes.vector_math(
            nodes, links, "ADD", label="Atlas Offset"
        ).node
        links.new(group_input.outputs["UV"], texel.inputs["Vector"])
        links.new(
            group_input.outputs["Half Texel"],
            shader_nodes.socket_by_identifier(texel.inputs, "Vector_001"),
        )
        links.new(texel.outputs["Vector"], frame_scale.inputs["Vector"])
        links.new(
            group_input.outputs["Frame Size"],
            shader_nodes.socket_by_identifier(frame_scale.inputs, "Vector_001"),
        )
        links.new(frame_scale.outputs["Vector"], frame_offset.inputs["Vector"])
        links.new(
            group_input.outputs["Frame Offset"],
            shader_nodes.socket_by_identifier(frame_offset.inputs, "Vector_001"),
        )
        links.new(frame_offset.outputs["Vector"], atlas_scale.inputs["Vector"])
        links.new(
            group_input.outputs["Atlas Scale"],
            shader_nodes.socket_by_identifier(atlas_scale.inputs, "Vector_001"),
        )
        links.new(atlas_scale.outputs["Vector"], atlas_offset.inputs["Vector"])
        links.new(
            group_input.outputs["Atlas Offset"],
            shader_nodes.socket_by_identifier(atlas_offset.inputs, "Vector_001"),
        )
        links.new(atlas_offset.outputs["Vector"], group_output.inputs["UV"])

    return get_or_build_node_group(
        "CP77 Decal UV Transform Bundle v1",
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketVector", "Half Texel"),
            ("NodeSocketVector", "Frame Size"),
            ("NodeSocketVector", "Frame Offset"),
            ("NodeSocketVector", "Atlas Scale"),
            ("NodeSocketVector", "Atlas Offset"),
        ),
        (("NodeSocketVector", "UV"),),
        build,
    )


def decal_uv_transform_socket(
    tree,
    uv,
    location,
    *,
    half_texel=(0.0, 0.0, 0.0),
    frame_size=(1.0, 1.0, 1.0),
    frame_offset=(0.0, 0.0, 0.0),
    atlas_scale=(1.0, 1.0, 1.0),
    atlas_offset=(0.0, 0.0, 0.0),
    label="Decal UV Transform",
):
    node = material_bundle_node(
        tree,
        _decal_uv_transform_group(),
        location,
        label,
        {
            "UV": uv,
            "Half Texel": half_texel,
            "Frame Size": frame_size,
            "Frame Offset": frame_offset,
            "Atlas Scale": atlas_scale,
            "Atlas Offset": atlas_offset,
        },
    )
    return node.outputs["UV"]


def _sphere_mask_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")

        split = nodes.new("ShaderNodeSeparateXYZ")
        x = shader_nodes.math(nodes, links, "SUBTRACT", label="Centered X").node
        y = shader_nodes.math(nodes, links, "SUBTRACT", label="Centered Y").node
        shader_nodes.socket_by_identifier(x.inputs, "Value_001").default_value = 0.5
        shader_nodes.socket_by_identifier(y.inputs, "Value_001").default_value = 0.5
        x2 = shader_nodes.math(nodes, links, "MULTIPLY", label="X²").node
        y2 = shader_nodes.math(nodes, links, "MULTIPLY", label="Y²").node
        distance2 = shader_nodes.math(nodes, links, "ADD", label="Distance²").node
        distance = shader_nodes.math(nodes, links, "SQRT", label="Distance").node
        hardness = shader_nodes.clamp(nodes, links, None, label="Hardness Range").node
        safe_radius = shader_nodes.math(
            nodes, links, "MAXIMUM", label="Safe Radius"
        ).node
        shader_nodes.socket_by_identifier(
            safe_radius.inputs, "Value_001"
        ).default_value = 1.0e-6
        hard_radius = shader_nodes.math(
            nodes, links, "MULTIPLY", label="Hard Radius"
        ).node
        edge = shader_nodes.math(nodes, links, "SUBTRACT", label="Edge Distance").node
        width = shader_nodes.math(nodes, links, "SUBTRACT", label="Edge Width").node
        safe_width = shader_nodes.math(
            nodes, links, "MAXIMUM", label="Safe Edge Width"
        ).node
        shader_nodes.socket_by_identifier(
            safe_width.inputs, "Value_001"
        ).default_value = 1.0e-6
        ramp = shader_nodes.math(
            nodes, links, "DIVIDE", label="Edge Ramp", use_clamp=True
        ).node
        mask = shader_nodes.math(nodes, links, "SUBTRACT", label="Mask").node
        mask.inputs["Value"].default_value = 1.0
        mask.use_clamp = True

        links.new(group_input.outputs["UV"], split.inputs["Vector"])
        links.new(split.outputs["X"], x.inputs["Value"])
        links.new(split.outputs["Y"], y.inputs["Value"])
        links.new(x.outputs["Value"], x2.inputs["Value"])
        links.new(
            x.outputs["Value"],
            shader_nodes.socket_by_identifier(x2.inputs, "Value_001"),
        )
        links.new(y.outputs["Value"], y2.inputs["Value"])
        links.new(
            y.outputs["Value"],
            shader_nodes.socket_by_identifier(y2.inputs, "Value_001"),
        )
        links.new(x2.outputs["Value"], distance2.inputs["Value"])
        links.new(
            y2.outputs["Value"],
            shader_nodes.socket_by_identifier(distance2.inputs, "Value_001"),
        )
        links.new(distance2.outputs["Value"], distance.inputs["Value"])
        links.new(group_input.outputs["Hardness"], hardness.inputs["Value"])
        links.new(group_input.outputs["Radius"], safe_radius.inputs["Value"])
        links.new(hardness.outputs["Result"], hard_radius.inputs["Value"])
        links.new(
            safe_radius.outputs["Value"],
            shader_nodes.socket_by_identifier(hard_radius.inputs, "Value_001"),
        )
        links.new(distance.outputs["Value"], edge.inputs["Value"])
        links.new(
            hard_radius.outputs["Value"],
            shader_nodes.socket_by_identifier(edge.inputs, "Value_001"),
        )
        links.new(safe_radius.outputs["Value"], width.inputs["Value"])
        links.new(
            hard_radius.outputs["Value"],
            shader_nodes.socket_by_identifier(width.inputs, "Value_001"),
        )
        links.new(width.outputs["Value"], safe_width.inputs["Value"])
        links.new(edge.outputs["Value"], ramp.inputs["Value"])
        links.new(
            safe_width.outputs["Value"],
            shader_nodes.socket_by_identifier(ramp.inputs, "Value_001"),
        )
        links.new(
            ramp.outputs["Value"],
            shader_nodes.socket_by_identifier(mask.inputs, "Value_001"),
        )
        links.new(mask.outputs["Value"], group_output.inputs["Mask"])

    return get_or_build_node_group(
        "CP77 Sphere Mask Bundle v2",
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Radius"),
            ("NodeSocketFloat", "Hardness"),
        ),
        (("NodeSocketFloat", "Mask"),),
        build,
    )


def sphere_mask_socket(tree, uv, radius, hardness, location, label="Sphere Mask"):
    node = material_bundle_node(
        tree,
        _sphere_mask_group(),
        location,
        label,
        {"UV": uv, "Radius": radius, "Hardness": hardness},
    )
    return node.outputs["Mask"]


_FOUR_WAY_SOCKETS = {
    "FLOAT": ("NodeSocketFloat", "Value", "Float"),
    "RGBA": ("NodeSocketColor", "Color", "Color"),
}


def _four_way_group(kind):
    socket_type, prefix, suffix = _FOUR_WAY_SOCKETS[kind]

    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")
        current = group_input.outputs[f"{prefix} 0"]
        for index in range(1, 4):
            condition = shader_nodes.math(
                nodes, links, "GREATER_THAN", label=f"Index ≥ {index}"
            ).node
            shader_nodes.socket_by_identifier(
                condition.inputs, "Value_001"
            ).default_value = index - 0.5
            selected = nodes.new("ShaderNodeMix")
            selected.data_type = kind
            selected.label = f"Select {prefix} {index}"
            selected.clamp_factor = False
            links.new(group_input.outputs["Index"], condition.inputs["Value"])
            links.new(
                condition.outputs["Value"],
                shader_nodes.socket_by_identifier(selected.inputs, "Factor_Float"),
            )
            links.new(
                current,
                shader_nodes.socket_by_identifier(selected.inputs, f"A_{suffix}"),
            )
            links.new(
                group_input.outputs[f"{prefix} {index}"],
                shader_nodes.socket_by_identifier(selected.inputs, f"B_{suffix}"),
            )
            current = shader_nodes.socket_by_identifier(
                selected.outputs, f"Result_{suffix}"
            )
        links.new(current, group_output.inputs[prefix])

    label = "Scalar" if kind == "FLOAT" else "Color"
    return get_or_build_node_group(
        f"CP77 Four-way {label} Select Bundle v1",
        (
            ("NodeSocketFloat", "Index"),
            *((socket_type, f"{prefix} {item}") for item in range(4)),
        ),
        ((socket_type, prefix),),
        build,
    )


def four_way_socket(tree, index, values, location, label=None, *, kind):
    _socket_type, prefix, _suffix = _FOUR_WAY_SOCKETS[kind]
    node = material_bundle_node(
        tree,
        _four_way_group(kind),
        location,
        label or f"Select {prefix}",
        {
            "Index": index,
            **{f"{prefix} {item}": values[item] for item in range(4)},
        },
    )
    return node.outputs[prefix]


def _light_zone_group():
    def build(group):
        nodes = group.nodes
        links = group.links
        group_input = nodes.new("NodeGroupInput")
        group_output = nodes.new("NodeGroupOutput")
        colors = []
        levels = []
        for zone in range(len(ZONES)):
            # An attribute the object lacks outputs zero: a zone no light writes has colour and level zero, dark.
            color = nodes.new("ShaderNodeAttribute")
            color.label = f"Zone {zone} Object Color"
            color.attribute_type = "OBJECT"
            color.attribute_name = zone_color_property(zone)
            colors.append(color.outputs["Color"])
            level = nodes.new("ShaderNodeAttribute")
            level.label = f"Zone {zone} Object Level"
            level.attribute_type = "OBJECT"
            level.attribute_name = zone_level_property(zone)
            levels.append(level.outputs["Fac"])
        links.new(
            four_way_socket(
                group,
                group_input.outputs["Zone"],
                colors,
                (0, 0),
                "Select Zone Color",
                kind="RGBA",
            ),
            group_output.inputs["Color"],
        )
        links.new(
            four_way_socket(
                group,
                group_input.outputs["Zone"],
                levels,
                (0, 0),
                "Select Zone Level",
                kind="FLOAT",
            ),
            group_output.inputs["Level"],
        )

    return get_or_build_node_group(
        "CP77 Light Zone Bundle v2",
        (("NodeSocketFloat", "Zone"),),
        (("NodeSocketColor", "Color"), ("NodeSocketFloat", "Level")),
        build,
    )


def light_zone_bundle(tree, zone, location, label="Light Zone Object Values"):
    """The colour and level of the light zone zone picks, as sockets"""
    node = material_bundle_node(
        tree, _light_zone_group(), location, label, {"Zone": zone}
    )
    return node.outputs["Color"], node.outputs["Level"]


def light_zone_index(tree, location):
    nodes, links = tree.nodes, tree.links
    x, y = location
    vertex = shader_nodes.new_node(
        tree, "ShaderNodeVertexColor", "Light Zone Vertex Color", (x, y)
    )
    split = shader_nodes.new_node(
        tree, "ShaderNodeSeparateColor", "Light Zone Red", (x + 180, y)
    )
    links.new(vertex.outputs["Color"], split.inputs["Color"])
    scaled = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY_ADD",
        split.outputs["Red"],
        4.0,
        0.001,
        name="Scaled Zone",
        location=(x + 360, y),
    )
    rounded = shader_nodes.math(
        nodes, links, "FLOOR", scaled, name="Rounded Zone", location=(x + 540, y)
    )
    return shader_nodes.math(
        nodes, links, "MINIMUM", rounded, 3.0, name="Zone Index", location=(x + 720, y)
    )


def light_zone_emission(tree, zone, data, debug_colors, mask, location):
    """The zone colour, glow blend and emission strength of a light-zone material, as sockets"""
    x, y = location
    debug = param_vector(data, "DebugLightsIntensity", (0.0, 0.0, 0.0, 0.0))
    if any(abs(value) > 1.0e-6 for value in debug):
        color = four_way_socket(
            tree, zone, debug_colors, (x, y + 200), "Debug Zone Color", kind="RGBA"
        )
        level = four_way_socket(
            tree, zone, debug, (x, y), "Debug Zone Level", kind="FLOAT"
        )
    else:
        color, level = light_zone_bundle(
            tree, zone, (x, y + 100), "Zone Color and Level"
        )
    zone_evs = tuple(
        param_float(data, f"Zone{index}EmissiveEV", 5.0) for index in range(4)
    )
    zone_ev = four_way_socket(
        tree, zone, zone_evs, (x, y - 200), "Zone Emissive EV", kind="FLOAT"
    )
    leveled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        level,
        zone_ev,
        name="Zone Level x Zone EV",
        location=(x + 200, y - 100),
    )
    emissive = emissive_scale_bundle(
        tree, mask, leveled, (x + 400, y - 100), "Zone Emissive Scale"
    )
    blend = shader_nodes.clamp(
        tree.nodes,
        tree.links,
        emissive.outputs["Scaled EV"],
        name="Zone Glow Blend",
        location=(x + 600, y),
    )
    return color, blend, emissive.outputs["Strength"]


def _build_direct_ev_strength(
    CurMat, ev_value, location=(0, 0), label="Direct EmissiveEV"
):
    """Convert a PBROutput.EmissiveEV value to Blender linear emission strength"""
    exponent = shader_nodes.math(
        CurMat.nodes, CurMat.links, "POWER", label=label, location=location, hide=True
    ).node
    exponent.inputs["Value"].default_value = 2.0
    assign_socket(
        CurMat.links,
        ev_value,
        shader_nodes.socket_by_identifier(exponent.inputs, "Value_001"),
    )
    subtract = shader_nodes.math(
        CurMat.nodes,
        CurMat.links,
        "SUBTRACT",
        label=f"{label} - 1",
        location=(location[0] + 160, location[1]),
        hide=True,
    ).node
    CurMat.links.new(exponent.outputs["Value"], subtract.inputs["Value"])
    shader_nodes.socket_by_identifier(subtract.inputs, "Value_001").default_value = 1.0
    clamp = shader_nodes.math(
        CurMat.nodes,
        CurMat.links,
        "MAXIMUM",
        label=f"{label} >= 0",
        location=(location[0] + 320, location[1]),
        hide=True,
    ).node
    CurMat.links.new(subtract.outputs["Value"], clamp.inputs["Value"])
    shader_nodes.socket_by_identifier(clamp.inputs, "Value_001").default_value = 0.0
    return clamp.outputs["Value"]


def _build_peak_channel(CurMat, source, location, label="Peak Channel"):
    channels = create_node(
        CurMat.nodes, "ShaderNodeSeparateColor", location, label=f"{label} split"
    )
    CurMat.links.new(source, channels.inputs["Color"])
    first = shader_nodes.math(
        CurMat.nodes,
        CurMat.links,
        "MAXIMUM",
        label=f"{label} rg",
        location=(location[0] + 160, location[1]),
        hide=True,
    ).node
    CurMat.links.new(channels.outputs["Red"], first.inputs["Value"])
    CurMat.links.new(
        channels.outputs["Green"],
        shader_nodes.socket_by_identifier(first.inputs, "Value_001"),
    )
    second = shader_nodes.math(
        CurMat.nodes,
        CurMat.links,
        "MAXIMUM",
        label=label,
        location=(location[0] + 320, location[1]),
        use_clamp=True,
        hide=True,
    ).node
    CurMat.links.new(first.outputs["Value"], second.inputs["Value"])
    CurMat.links.new(
        channels.outputs["Blue"],
        shader_nodes.socket_by_identifier(second.inputs, "Value_001"),
    )
    return second.outputs["Value"]


def _scalar_operation_group(kind):
    definitions = {
        "Direct Emission EV": (
            (("NodeSocketFloat", "EV"),),
            "Strength",
            _build_direct_ev_strength,
            1,
        ),
        "Peak Color": (
            (("NodeSocketColor", "Color"),),
            "Peak",
            _build_peak_channel,
            1,
        ),
        "Scalar Blend": (
            (
                ("NodeSocketFloat", "First"),
                ("NodeSocketFloat", "Second"),
                ("NodeSocketFloat", "Factor"),
            ),
            "Value",
            lambda tree, first, second, factor, location, label: shader_nodes.lerp(
                tree.nodes,
                tree.links,
                first,
                second,
                factor,
                name=label,
                location=location,
            ),
            2,
        ),
    }
    inputs, output, builder, version = definitions[kind]

    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = builder(
            group,
            *(group_input.outputs[name] for _, name in inputs),
            location=(0, 0),
            label=kind,
        )
        group.links.new(result, group_output.inputs[output])

    return get_or_build_node_group(
        f"CP77 {kind} Bundle v{version}",
        inputs,
        (("NodeSocketFloat", output),),
        build,
    )


def direct_ev_strength_socket(tree, ev, location, label="Direct Emission EV"):
    return material_bundle_node(
        tree,
        _scalar_operation_group("Direct Emission EV"),
        location,
        label,
        {"EV": ev},
    ).outputs["Strength"]


def peak_color_socket(tree, color, location, label="Peak Color"):
    return material_bundle_node(
        tree,
        _scalar_operation_group("Peak Color"),
        location,
        label,
        {"Color": color},
    ).outputs["Peak"]


def scalar_lerp_socket(tree, first, second, factor, location, label="Scalar Blend"):
    return material_bundle_node(
        tree,
        _scalar_operation_group("Scalar Blend"),
        location,
        label,
        {"First": first, "Second": second, "Factor": factor},
    ).outputs["Value"]


def _dithered_alpha_group():
    def build(group):
        source = group.nodes.new("NodeGroupInput")
        output = group.nodes.new("NodeGroupOutput")
        numerator = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", label="Alpha - Threshold"
        ).node
        denominator = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", label="1 - Threshold"
        ).node
        safe = shader_nodes.math(
            group.nodes, group.links, "MAXIMUM", label="Safe Alpha Range"
        ).node
        remap = shader_nodes.math(
            group.nodes, group.links, "DIVIDE", label="Dithered Alpha"
        ).node
        denominator.inputs["Value"].default_value = 1.0
        shader_nodes.socket_by_identifier(
            safe.inputs, "Value_001"
        ).default_value = 1.0e-6
        remap.use_clamp = True
        group.links.new(source.outputs["Alpha"], numerator.inputs["Value"])
        group.links.new(
            source.outputs["Threshold"],
            shader_nodes.socket_by_identifier(numerator.inputs, "Value_001"),
        )
        group.links.new(
            source.outputs["Threshold"],
            shader_nodes.socket_by_identifier(denominator.inputs, "Value_001"),
        )
        group.links.new(denominator.outputs["Value"], safe.inputs["Value"])
        group.links.new(numerator.outputs["Value"], remap.inputs["Value"])
        group.links.new(
            safe.outputs["Value"],
            shader_nodes.socket_by_identifier(remap.inputs, "Value_001"),
        )
        group.links.new(remap.outputs["Value"], output.inputs["Alpha"])

    return get_or_build_node_group(
        "CP77 Dithered Alpha Remap Bundle v1",
        (("NodeSocketFloat", "Alpha"), ("NodeSocketFloat", "Threshold")),
        (("NodeSocketFloat", "Alpha"),),
        build,
    )


def _alpha_mask_group(dithered):
    def build(group):
        source = group.nodes.new("NodeGroupInput")
        output = group.nodes.new("NodeGroupOutput")
        if dithered:
            alpha = material_bundle_node(
                group,
                _dithered_alpha_group(),
                (0, 0),
                "Dithered Alpha Remap",
                {
                    "Alpha": source.outputs["Alpha"],
                    "Threshold": source.outputs["Threshold"],
                },
            ).outputs["Alpha"]
        else:
            compare = shader_nodes.math(
                group.nodes, group.links, "GREATER_THAN", label="Alpha Threshold"
            ).node
            group.links.new(source.outputs["Alpha"], compare.inputs["Value"])
            group.links.new(
                source.outputs["Threshold"],
                shader_nodes.socket_by_identifier(compare.inputs, "Value_001"),
            )
            alpha = compare.outputs["Value"]
        invert = shader_nodes.math(
            group.nodes, group.links, "SUBTRACT", label="1 - Enable Mask"
        ).node
        invert.inputs["Value"].default_value = 1.0
        clamp = group.nodes.new("ShaderNodeClamp")
        clamp.label = "Mask Enable Range"
        group.links.new(
            source.outputs["Enable Mask"],
            shader_nodes.socket_by_identifier(invert.inputs, "Value_001"),
        )
        group.links.new(invert.outputs["Value"], clamp.inputs["Min"])
        group.links.new(alpha, clamp.inputs["Value"])
        group.links.new(clamp.outputs["Result"], output.inputs["Alpha"])

    mode = "Dithered" if dithered else "Threshold"
    return get_or_build_node_group(
        f"CP77 {mode} Alpha Mask Bundle v1",
        (
            ("NodeSocketFloat", "Alpha"),
            ("NodeSocketFloat", "Threshold"),
            ("NodeSocketFloat", "Enable Mask"),
        ),
        (("NodeSocketFloat", "Alpha"),),
        build,
    )


def alpha_mask_socket(tree, alpha, threshold, enabled, location, *, dithered=False):
    return material_bundle_node(
        tree,
        _alpha_mask_group(dithered),
        location,
        "Dithered Alpha Mask" if dithered else "Alpha Threshold Mask",
        {"Alpha": alpha, "Threshold": threshold, "Enable Mask": enabled},
    ).outputs["Alpha"]


def vector_lerp_socket(tree, first, second, factor, location, label="Vector Blend"):
    def build(group):
        source = group.nodes.new("NodeGroupInput")
        output = group.nodes.new("NodeGroupOutput")
        vector = shader_nodes.vector_lerp(
            group.nodes,
            group.links,
            source.outputs["First"],
            source.outputs["Second"],
            source.outputs["Factor"],
            name="Vector Blend",
            location=(0, 0),
        )
        group.links.new(vector, output.inputs["Vector"])

    group = get_or_build_node_group(
        "CP77 Vector Blend Bundle v2",
        (
            ("NodeSocketVector", "First"),
            ("NodeSocketVector", "Second"),
            ("NodeSocketFloat", "Factor"),
        ),
        (("NodeSocketVector", "Vector"),),
        build,
    )
    return material_bundle_node(
        tree,
        group,
        location,
        label,
        {"First": first, "Second": second, "Factor": factor},
    ).outputs["Vector"]
