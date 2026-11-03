from dataclasses import dataclass

from ..blender import shader_nodes
from ..blender.mesh import (
    SOURCE_FRAME_VALID_ATTRIBUTE,
    SOURCE_NORMAL_ATTRIBUTE,
    SOURCE_TANGENT_ATTRIBUTE,
    SOURCE_TANGENT_SIGN_ATTRIBUTE,
)
from ..materials.blender.nodes import create_node
from .bundles import material_bundle_node
from .graph import cp77_bitangent_socket, cp77_uv_tangent_node, fract_socket
from .mat_common import get_or_build_node_group, param_float, param_vector
from .shader_hash import HASH_OFFSET, HASH_SCALE

_EPSILON = 1.0e-4
_VERTICAL_BASIS_THRESHOLD = 0.5


@dataclass(slots=True)
class WindowParallaxCoordinates:
    room_uv: object
    room_atlas_uv: object
    layer_atlas_uv: object
    curtain_atlas_uv: object
    layer_mask: object
    curtain_mask: object
    room_interp: object
    room_hit_y: object
    random: object
    room_on_random: object
    view_angle: object
    object_pivot: object


def _combine(tree, x, y, z=None, location=(0, 0), label="Vector"):
    node = create_node(tree.nodes, "ShaderNodeCombineXYZ", location, label=label)
    tree.links.new(x, node.inputs["X"])
    tree.links.new(y, node.inputs["Y"])
    if z is not None:
        tree.links.new(z, node.inputs["Z"])
    return node.outputs["Vector"]


def _build_hash11_nodes(tree, source, location, label):
    mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        HASH_SCALE,
        label=f"{label} * .1031",
        location=location,
        hide=True,
    ).node
    tree.links.new(source, mul.inputs["Value"])
    p = fract_socket(
        tree, mul.outputs["Value"], (location[0] + 150, location[1]), f"{label} frac"
    )
    plus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        HASH_OFFSET,
        label=f"{label} + 33.33",
        location=(location[0] + 300, location[1]),
        hide=True,
    ).node
    tree.links.new(p, plus.inputs["Value"])
    p2 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} scramble",
        location=(location[0] + 450, location[1]),
        hide=True,
    ).node
    tree.links.new(p, p2.inputs["Value"])
    tree.links.new(
        plus.outputs["Value"], shader_nodes.socket_by_identifier(p2.inputs, "Value_001")
    )
    doubled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        2.0,
        label=f"{label} x2",
        location=(location[0] + 600, location[1]),
        hide=True,
    ).node
    tree.links.new(p2.outputs["Value"], doubled.inputs["Value"])
    final_mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} final",
        location=(location[0] + 750, location[1]),
        hide=True,
    ).node
    tree.links.new(p2.outputs["Value"], final_mul.inputs["Value"])
    tree.links.new(
        doubled.outputs["Value"],
        shader_nodes.socket_by_identifier(final_mul.inputs, "Value_001"),
    )
    return fract_socket(
        tree, final_mul.outputs["Value"], (location[0] + 900, location[1]), label
    )


def _build_hash_p3_nodes(tree, source, mode, location, label):
    if mode == "21":
        p3 = _combine(
            tree, source, source, source, location=location, label=f"{label} p.xxx"
        )
    elif mode == "22":
        split = create_node(
            tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} Input"
        )
        tree.links.new(source, split.inputs["Vector"])
        p3 = _combine(
            tree,
            split.outputs["X"],
            split.outputs["Y"],
            split.outputs["X"],
            location=(location[0] + 170, location[1]),
            label=f"{label} p.xyx",
        )
    else:
        p3 = source

    scale = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} Hash Scale",
        location=(location[0] + 340, location[1]),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
        0.1031,
        0.1030,
        0.0973,
    )
    tree.links.new(p3, scale.inputs["Vector"])
    frac = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        label=f"{label} frac",
        location=(location[0] + 510, location[1]),
        hide=True,
    ).node
    tree.links.new(scale.outputs["Vector"], frac.inputs["Vector"])
    split = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 680, location[1]),
        label=f"{label} p3",
    )
    tree.links.new(frac.outputs["Vector"], split.inputs["Vector"])

    permute = _combine(
        tree,
        split.outputs["Y"],
        split.outputs["Z"],
        split.outputs["X"],
        location=(location[0] + 850, location[1] - 120),
        label=f"{label} p3.yzx",
    )
    add_const = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} +33.33",
        location=(location[0] + 1020, location[1] - 120),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(add_const.inputs, "Vector_001").default_value = (
        33.33,
        33.33,
        33.33,
    )
    tree.links.new(permute, add_const.inputs["Vector"])
    dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        label=f"{label} Dot",
        location=(location[0] + 1190, location[1] - 40),
        hide=True,
    ).node
    tree.links.new(frac.outputs["Vector"], dot.inputs["Vector"])
    tree.links.new(
        add_const.outputs["Vector"],
        shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
    )
    dot_value = dot.outputs["Value"]
    dot3 = _combine(
        tree,
        dot_value,
        dot_value,
        dot_value,
        location=(location[0] + 1360, location[1] - 40),
        label=f"{label} Dot.xxx",
    )
    scrambled = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} Scrambled",
        location=(location[0] + 1530, location[1]),
        hide=True,
    ).node
    tree.links.new(frac.outputs["Vector"], scrambled.inputs["Vector"])
    tree.links.new(
        dot3, shader_nodes.socket_by_identifier(scrambled.inputs, "Vector_001")
    )
    split2 = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 1700, location[1]),
        label=f"{label} Scrambled XYZ",
    )
    tree.links.new(scrambled.outputs["Vector"], split2.inputs["Vector"])

    sum_xy = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} x+y",
        location=(location[0] + 1870, location[1] + 70),
        hide=True,
    ).node
    tree.links.new(split2.outputs["X"], sum_xy.inputs["Value"])
    tree.links.new(
        split2.outputs["Y"],
        shader_nodes.socket_by_identifier(sum_xy.inputs, "Value_001"),
    )
    out_x_mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} X",
        location=(location[0] + 2040, location[1] + 70),
        hide=True,
    ).node
    tree.links.new(sum_xy.outputs["Value"], out_x_mul.inputs["Value"])
    tree.links.new(
        split2.outputs["Z"],
        shader_nodes.socket_by_identifier(out_x_mul.inputs, "Value_001"),
    )
    out_x = fract_socket(
        tree,
        out_x_mul.outputs["Value"],
        (location[0] + 2210, location[1] + 70),
        f"{label}.x",
    )

    sum_xz = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} x+z",
        location=(location[0] + 1870, location[1] - 90),
        hide=True,
    ).node
    tree.links.new(split2.outputs["X"], sum_xz.inputs["Value"])
    tree.links.new(
        split2.outputs["Z"],
        shader_nodes.socket_by_identifier(sum_xz.inputs, "Value_001"),
    )
    out_y_mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} Y",
        location=(location[0] + 2040, location[1] - 90),
        hide=True,
    ).node
    tree.links.new(sum_xz.outputs["Value"], out_y_mul.inputs["Value"])
    tree.links.new(
        split2.outputs["Y"],
        shader_nodes.socket_by_identifier(out_y_mul.inputs, "Value_001"),
    )
    out_y = fract_socket(
        tree,
        out_y_mul.outputs["Value"],
        (location[0] + 2210, location[1] - 90),
        f"{label}.y",
    )
    return _combine(
        tree, out_x, out_y, location=(location[0] + 2380, location[1]), label=label
    )


def _build_hash12_nodes(tree, source, location, label):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} Input"
    )
    tree.links.new(source, split.inputs["Vector"])
    p3 = _combine(
        tree,
        split.outputs["X"],
        split.outputs["Y"],
        split.outputs["X"],
        location=(location[0] + 170, location[1]),
        label=f"{label} p.xyx",
    )
    scale = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        label=f"{label} * .1031",
        location=(location[0] + 340, location[1]),
        hide=True,
    ).node
    scale.inputs["Scale"].default_value = HASH_SCALE
    tree.links.new(p3, scale.inputs["Vector"])
    frac = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        label=f"{label} frac",
        location=(location[0] + 510, location[1]),
        hide=True,
    ).node
    tree.links.new(scale.outputs["Vector"], frac.inputs["Vector"])
    p = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 680, location[1]),
        label=f"{label} p3",
    )
    tree.links.new(frac.outputs["Vector"], p.inputs["Vector"])
    permute = _combine(
        tree,
        p.outputs["Y"],
        p.outputs["Z"],
        p.outputs["X"],
        location=(location[0] + 850, location[1] - 120),
        label=f"{label} p3.yzx",
    )
    plus = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} +33.33",
        location=(location[0] + 1020, location[1] - 120),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(plus.inputs, "Vector_001").default_value = (
        HASH_OFFSET,
    ) * 3
    tree.links.new(permute, plus.inputs["Vector"])
    dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        label=f"{label} Dot",
        location=(location[0] + 1190, location[1]),
        hide=True,
    ).node
    tree.links.new(frac.outputs["Vector"], dot.inputs["Vector"])
    tree.links.new(
        plus.outputs["Vector"],
        shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
    )
    dot_value = dot.outputs["Value"]
    dot3 = _combine(
        tree,
        dot_value,
        dot_value,
        dot_value,
        location=(location[0] + 1360, location[1] - 100),
        label=f"{label} Dot.xxx",
    )
    scrambled = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} Scrambled",
        location=(location[0] + 1530, location[1]),
        hide=True,
    ).node
    tree.links.new(frac.outputs["Vector"], scrambled.inputs["Vector"])
    tree.links.new(
        dot3, shader_nodes.socket_by_identifier(scrambled.inputs, "Vector_001")
    )
    ps = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 1700, location[1]),
        label=f"{label} XYZ",
    )
    tree.links.new(scrambled.outputs["Vector"], ps.inputs["Vector"])
    xy = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} x+y",
        location=(location[0] + 1870, location[1] + 40),
        hide=True,
    ).node
    tree.links.new(ps.outputs["X"], xy.inputs["Value"])
    tree.links.new(
        ps.outputs["Y"], shader_nodes.socket_by_identifier(xy.inputs, "Value_001")
    )
    mul = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} Product",
        location=(location[0] + 2040, location[1] + 40),
        hide=True,
    ).node
    tree.links.new(xy.outputs["Value"], mul.inputs["Value"])
    tree.links.new(
        ps.outputs["Z"], shader_nodes.socket_by_identifier(mul.inputs, "Value_001")
    )
    return fract_socket(
        tree, mul.outputs["Value"], (location[0] + 2210, location[1] + 40), label
    )


def _hash11_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash11_nodes(
            group,
            group_input.outputs["Value"],
            (-500, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 Window Hash 1 from 1 Bundle v1",
        (("NodeSocketFloat", "Value"),),
        (("NodeSocketFloat", "Value"),),
        build,
    )


def _hash11(tree, source, location, label):
    node = material_bundle_node(
        tree,
        _hash11_group(),
        location,
        label,
        {"Value": source},
    )
    return node.outputs["Value"]


def _hash_p3_group(mode):
    socket_type = "NodeSocketFloat" if mode == "21" else "NodeSocketVector"

    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash_p3_nodes(
            group,
            group_input.outputs["Value"],
            mode,
            (-1200, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Vector"])

    return get_or_build_node_group(
        f"CP77 Window Hash {mode} Bundle v2",
        ((socket_type, "Value"),),
        (("NodeSocketVector", "Vector"),),
        build,
    )


def _hash_p3(tree, source, mode, location, label):
    node = material_bundle_node(
        tree,
        _hash_p3_group(mode),
        location,
        label,
        {"Value": source},
    )
    return node.outputs["Vector"]


def _hash12_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        result = _build_hash12_nodes(
            group,
            group_input.outputs["Vector"],
            (-1100, 0),
            "Hash",
        )
        group.links.new(result, group_output.inputs["Value"])

    return get_or_build_node_group(
        "CP77 Window Hash 1 from 2 Bundle v1",
        (("NodeSocketVector", "Vector"),),
        (("NodeSocketFloat", "Value"),),
        build,
    )


def _hash12(tree, source, location, label):
    node = material_bundle_node(
        tree,
        _hash12_group(),
        location,
        label,
        {"Vector": source},
    )
    return node.outputs["Value"]


def _build_source_basis_nodes(tree, location=(-4200, 700)):
    geometry = create_node(
        tree.nodes, "ShaderNodeNewGeometry", location, label="Window Source Geometry"
    )

    fallback_tangent_world = cp77_uv_tangent_node(
        tree.nodes,
        (location[0], location[1] - 180),
        label="Window Fallback Tangent",
    )
    fallback_bitangent_world = cp77_bitangent_socket(
        tree.nodes,
        tree.links,
        geometry.outputs["Normal"],
        fallback_tangent_world.outputs["Tangent"],
        (location[0] + 180, location[1] - 520),
        label="Window Fallback Binormal",
    )

    position_local = create_node(
        tree.nodes,
        "ShaderNodeVectorTransform",
        (location[0] + 180, location[1] + 120),
        label="Window Local Position",
    )
    position_local.vector_type = "POINT"
    position_local.convert_from = "WORLD"
    position_local.convert_to = "OBJECT"
    tree.links.new(geometry.outputs["Position"], position_local.inputs["Vector"])

    source_view_world = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        label="Surface - Camera",
        location=(location[0], location[1] - 860),
        hide=True,
    ).node
    source_view_world.inputs["Scale"].default_value = -1.0
    tree.links.new(geometry.outputs["Incoming"], source_view_world.inputs["Vector"])
    source_view_local = create_node(
        tree.nodes,
        "ShaderNodeVectorTransform",
        (location[0] + 180, location[1] - 860),
        label="Window Local View Direction",
    )
    source_view_local.vector_type = "VECTOR"
    source_view_local.convert_from = "WORLD"
    source_view_local.convert_to = "OBJECT"
    tree.links.new(
        source_view_world.outputs["Vector"], source_view_local.inputs["Vector"]
    )

    fallback_tangent_local = create_node(
        tree.nodes,
        "ShaderNodeVectorTransform",
        (location[0] + 350, location[1] - 120),
        label="Window Fallback Tangent Local",
    )
    fallback_tangent_local.vector_type = "VECTOR"
    fallback_tangent_local.convert_from = "WORLD"
    fallback_tangent_local.convert_to = "OBJECT"
    tree.links.new(
        fallback_tangent_world.outputs["Tangent"],
        fallback_tangent_local.inputs["Vector"],
    )

    fallback_normal_local = create_node(
        tree.nodes,
        "ShaderNodeVectorTransform",
        (location[0] + 350, location[1] - 300),
        label="Window Fallback Normal Local",
    )
    fallback_normal_local.vector_type = "NORMAL"
    fallback_normal_local.convert_from = "WORLD"
    fallback_normal_local.convert_to = "OBJECT"
    tree.links.new(geometry.outputs["Normal"], fallback_normal_local.inputs["Vector"])

    fallback_bitangent_local = create_node(
        tree.nodes,
        "ShaderNodeVectorTransform",
        (location[0] + 350, location[1] - 500),
        label="Window Fallback Binormal Local",
    )
    fallback_bitangent_local.vector_type = "VECTOR"
    fallback_bitangent_local.convert_from = "WORLD"
    fallback_bitangent_local.convert_to = "OBJECT"
    tree.links.new(fallback_bitangent_world, fallback_bitangent_local.inputs["Vector"])

    valid_attribute = create_node(
        tree.nodes,
        "ShaderNodeAttribute",
        (location[0] + 180, location[1] + 300),
        label="Window Source Frame Valid",
    )
    valid_attribute.attribute_type = "GEOMETRY"
    valid_attribute.attribute_name = SOURCE_FRAME_VALID_ATTRIBUTE
    valid = valid_attribute.outputs.get("Fac") or valid_attribute.outputs["Factor"]

    tangent_attribute = create_node(
        tree.nodes,
        "ShaderNodeAttribute",
        (location[0] + 180, location[1] - 120),
        label="Window Source Tangent Attribute",
    )
    tangent_attribute.attribute_type = "GEOMETRY"
    tangent_attribute.attribute_name = SOURCE_TANGENT_ATTRIBUTE

    normal_attribute = create_node(
        tree.nodes,
        "ShaderNodeAttribute",
        (location[0] + 180, location[1] - 300),
        label="Window Source Normal Attribute",
    )
    normal_attribute.attribute_type = "GEOMETRY"
    normal_attribute.attribute_name = SOURCE_NORMAL_ATTRIBUTE

    sign_attribute = create_node(
        tree.nodes,
        "ShaderNodeAttribute",
        (location[0] + 180, location[1] - 680),
        label="Window Source Tangent Sign",
    )
    sign_attribute.attribute_type = "GEOMETRY"
    sign_attribute.attribute_name = SOURCE_TANGENT_SIGN_ATTRIBUTE
    source_sign = sign_attribute.outputs.get("Fac") or sign_attribute.outputs["Factor"]

    valid_threshold = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        0.5,
        label="Window Source Frame Sentinel Valid",
        location=(location[0] + 530, location[1] + 300),
        hide=True,
    ).node
    tree.links.new(valid, valid_threshold.inputs["Value"])

    tangent_length = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        label="Window Source Tangent Length",
        location=(location[0] + 530, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(tangent_attribute.outputs["Vector"], tangent_length.inputs["Vector"])
    tangent_valid = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        _EPSILON,
        label="Window Source Tangent Valid",
        location=(location[0] + 710, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(tangent_length.outputs["Value"], tangent_valid.inputs["Value"])

    normal_length = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        label="Window Source Normal Length",
        location=(location[0] + 530, location[1] - 300),
        hide=True,
    ).node
    tree.links.new(normal_attribute.outputs["Vector"], normal_length.inputs["Vector"])
    normal_valid = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        _EPSILON,
        label="Window Source Normal Valid",
        location=(location[0] + 710, location[1] - 300),
        hide=True,
    ).node
    tree.links.new(normal_length.outputs["Value"], normal_valid.inputs["Value"])

    sign_absolute = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        label="Window Source Tangent Sign Absolute",
        location=(location[0] + 530, location[1] - 720),
        hide=True,
    ).node
    tree.links.new(source_sign, sign_absolute.inputs["Value"])
    sign_valid = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        _EPSILON,
        label="Window Source Tangent Sign Valid",
        location=(location[0] + 710, location[1] - 720),
        hide=True,
    ).node
    tree.links.new(sign_absolute.outputs["Value"], sign_valid.inputs["Value"])

    frame_and_tangent = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Window Source Frame and Tangent Valid",
        location=(location[0] + 900, location[1] + 300),
        hide=True,
    ).node
    tree.links.new(valid_threshold.outputs["Value"], frame_and_tangent.inputs["Value"])
    tree.links.new(
        tangent_valid.outputs["Value"],
        shader_nodes.socket_by_identifier(frame_and_tangent.inputs, "Value_001"),
    )
    frame_and_normal = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Window Source Frame and Normal Valid",
        location=(location[0] + 1070, location[1] + 300),
        hide=True,
    ).node
    tree.links.new(frame_and_tangent.outputs["Value"], frame_and_normal.inputs["Value"])
    tree.links.new(
        normal_valid.outputs["Value"],
        shader_nodes.socket_by_identifier(frame_and_normal.inputs, "Value_001"),
    )
    frame_valid = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Window Source Frame Data Valid",
        location=(location[0] + 1240, location[1] + 300),
        hide=True,
    ).node
    tree.links.new(frame_and_normal.outputs["Value"], frame_valid.inputs["Value"])
    tree.links.new(
        sign_valid.outputs["Value"],
        shader_nodes.socket_by_identifier(frame_valid.inputs, "Value_001"),
    )
    valid = frame_valid.outputs["Value"]

    source_bitangent_cross = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "CROSS_PRODUCT",
        label="Window Source Local Binormal Cross",
        location=(location[0] + 530, location[1] - 560),
        hide=True,
    ).node
    tree.links.new(
        normal_attribute.outputs["Vector"], source_bitangent_cross.inputs["Vector"]
    )
    tree.links.new(
        tangent_attribute.outputs["Vector"],
        shader_nodes.socket_by_identifier(source_bitangent_cross.inputs, "Vector_001"),
    )
    source_cross_normalize = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        label="Window Source Local Binormal Cross Normalize",
        location=(location[0] + 710, location[1] - 560),
        hide=True,
    ).node
    tree.links.new(
        source_bitangent_cross.outputs["Vector"],
        source_cross_normalize.inputs["Vector"],
    )
    source_cross_split = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 880, location[1] - 620),
        label="Window Source Binormal Cross XYZ",
    )
    tree.links.new(
        source_cross_normalize.outputs["Vector"], source_cross_split.inputs["Vector"]
    )
    source_cross_z_abs = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        label="Window Source Binormal Vertical Absolute",
        location=(location[0] + 1050, location[1] - 700),
        hide=True,
    ).node
    tree.links.new(source_cross_split.outputs["Z"], source_cross_z_abs.inputs["Value"])
    source_vertical_valid = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        _VERTICAL_BASIS_THRESHOLD,
        label="Window Source Binormal Vertical Valid",
        location=(location[0] + 1220, location[1] - 700),
        hide=True,
    ).node
    tree.links.new(
        source_cross_z_abs.outputs["Value"], source_vertical_valid.inputs["Value"]
    )
    source_cross_z_positive = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        0.0,
        label="Window Source Binormal Cross Z Positive",
        location=(location[0] + 1050, location[1] - 820),
        hide=True,
    ).node
    tree.links.new(
        source_cross_split.outputs["Z"], source_cross_z_positive.inputs["Value"]
    )
    source_cross_z_scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        -2.0,
        label="Window Source Vertical Sign Scale",
        location=(location[0] + 1220, location[1] - 820),
        hide=True,
    ).node
    tree.links.new(
        source_cross_z_positive.outputs["Value"], source_cross_z_scale.inputs["Value"]
    )
    source_vertical_sign = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        1.0,
        label="Window Source Vertical Sign",
        location=(location[0] + 1390, location[1] - 820),
        hide=True,
    ).node
    tree.links.new(
        source_cross_z_scale.outputs["Value"], source_vertical_sign.inputs["Value"]
    )
    parallax_sign = shader_nodes.lerp(
        tree.nodes,
        tree.links,
        source_sign,
        source_vertical_sign.outputs["Value"],
        source_vertical_valid.outputs["Value"],
        name="Window Parallax Binormal Sign Select",
        location=(location[0] + 1390, location[1] - 660),
    )
    source_bitangent = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        label="Window Source Local Binormal",
        location=(location[0] + 1760, location[1] - 560),
        hide=True,
    ).node
    tree.links.new(
        source_bitangent_cross.outputs["Vector"], source_bitangent.inputs["Vector"]
    )
    tree.links.new(parallax_sign, source_bitangent.inputs["Scale"])

    tangent_selected = shader_nodes.vector_lerp(
        tree.nodes,
        tree.links,
        fallback_tangent_local.outputs["Vector"],
        tangent_attribute.outputs["Vector"],
        valid,
        name="Window Source Tangent Select",
        location=(location[0] + 900, location[1] - 120),
    )
    tangent_normalize = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        label="Window Source Tangent Normalize",
        location=(location[0] + 1240, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(tangent_selected, tangent_normalize.inputs["Vector"])
    tangent_source = tangent_normalize.outputs["Vector"]

    normal_selected = shader_nodes.vector_lerp(
        tree.nodes,
        tree.links,
        fallback_normal_local.outputs["Vector"],
        normal_attribute.outputs["Vector"],
        valid,
        name="Window Source Normal Select",
        location=(location[0] + 900, location[1] - 300),
    )
    normal_normalize = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        label="Window Source Normal Normalize",
        location=(location[0] + 1240, location[1] - 300),
        hide=True,
    ).node
    tree.links.new(normal_selected, normal_normalize.inputs["Vector"])
    normal_source = normal_normalize.outputs["Vector"]

    bitangent_selected = shader_nodes.vector_lerp(
        tree.nodes,
        tree.links,
        fallback_bitangent_local.outputs["Vector"],
        source_bitangent.outputs["Vector"],
        valid,
        name="Window Source Binormal Select",
        location=(location[0] + 900, location[1] - 500),
    )
    bitangent_normalize = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        label="Window Source Binormal Normalize",
        location=(location[0] + 1240, location[1] - 500),
        hide=True,
    ).node
    tree.links.new(bitangent_selected, bitangent_normalize.inputs["Vector"])
    negative_bitangent = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        label="-Window Source Binormal",
        location=(location[0] + 1420, location[1] - 500),
        hide=True,
    ).node
    negative_bitangent.inputs["Scale"].default_value = -1.0
    tree.links.new(
        bitangent_normalize.outputs["Vector"], negative_bitangent.inputs["Vector"]
    )

    basis = (
        (tangent_source, "X", 100),
        (negative_bitangent.outputs["Vector"], "Y", -20),
        (normal_source, "Z", -140),
    )
    tan_components = []
    for axis, name, y in basis:
        dot = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            label=f"tanPos.{name.lower()}",
            location=(location[0] + 1600, location[1] + y),
            hide=True,
        ).node
        tree.links.new(position_local.outputs["Vector"], dot.inputs["Vector"])
        tree.links.new(
            axis, shader_nodes.socket_by_identifier(dot.inputs, "Vector_001")
        )
        tan_components.append(dot.outputs["Value"])
    tan_pos = _combine(
        tree,
        *tan_components,
        location=(location[0] + 1780, location[1]),
        label="Window Tangent Position",
    )

    view_components = []
    for axis, name, y in basis:
        dot = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            label=f"viewDir.{name.lower()}",
            location=(location[0] + 1600, location[1] - 820 + y),
            hide=True,
        ).node
        tree.links.new(source_view_local.outputs["Vector"], dot.inputs["Vector"])
        tree.links.new(
            axis, shader_nodes.socket_by_identifier(dot.inputs, "Vector_001")
        )
        view_components.append(dot.outputs["Value"])
    view_dir = _combine(
        tree,
        *view_components,
        location=(location[0] + 1780, location[1] - 840),
        label="Window View Direction",
    )

    object_info = create_node(
        tree.nodes,
        "ShaderNodeObjectInfo",
        (location[0], location[1] + 300),
        label="Window Object Pivot",
    )
    return geometry, tan_pos, view_dir, object_info.outputs["Location"]


def _source_basis_group():
    def build(group):
        group_output = group.nodes.new("NodeGroupOutput")
        geometry, tan_pos, view_dir, pivot = _build_source_basis_nodes(group)
        for source, name in (
            (geometry.outputs["Incoming"], "Incoming"),
            (geometry.outputs["Normal"], "Normal"),
            (tan_pos, "Tan Position"),
            (view_dir, "View Direction"),
            (pivot, "Object Pivot"),
        ):
            group.links.new(source, group_output.inputs[name])

    return get_or_build_node_group(
        "CP77 Window Source Basis Bundle v2",
        (),
        (
            ("NodeSocketVector", "Incoming"),
            ("NodeSocketVector", "Normal"),
            ("NodeSocketVector", "Tan Position"),
            ("NodeSocketVector", "View Direction"),
            ("NodeSocketVector", "Object Pivot"),
        ),
        build,
    )


def _source_basis(tree, location=(-4200, 700)):
    node = material_bundle_node(
        tree,
        _source_basis_group(),
        location,
        "Window Source Basis",
        {},
    )
    return (
        node,
        node.outputs["Tan Position"],
        node.outputs["View Direction"],
        node.outputs["Object Pivot"],
    )


def _object_id(tree, pivot, location=(-3300, 1050)):
    floor = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FLOOR",
        label="floor(Object Translation)",
        location=location,
        hide=True,
    ).node
    tree.links.new(pivot, floor.inputs["Vector"])
    xy = _hash_p3(
        tree,
        floor.outputs["Vector"],
        "23",
        (location[0] + 180, location[1] + 160),
        "hash23(Object Translation)",
    )
    split_floor = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 180, location[1] - 120),
        label="Object Translation XYZ",
    )
    tree.links.new(floor.outputs["Vector"], split_floor.inputs["Vector"])
    zw = _hash_p3(
        tree,
        split_floor.outputs["Z"],
        "21",
        (location[0] + 180, location[1] - 260),
        "hash21(Object Z)",
    )
    return xy, zw


def _view_angle(tree, geometry, location=(-1800, -1450)):
    dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        label="abs(View·Normal)",
        location=location,
        hide=True,
    ).node
    tree.links.new(geometry.outputs["Incoming"], dot.inputs["Vector"])
    tree.links.new(
        geometry.outputs["Normal"],
        shader_nodes.socket_by_identifier(dot.inputs, "Vector_001"),
    )
    absolute = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        label="abs(View·Normal)",
        location=(location[0] + 170, location[1]),
        hide=True,
    ).node
    tree.links.new(dot.outputs["Value"], absolute.inputs["Value"])
    squared = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="View Angle²",
        location=(location[0] + 340, location[1]),
        hide=True,
    ).node
    tree.links.new(absolute.outputs["Value"], squared.inputs["Value"])
    tree.links.new(
        absolute.outputs["Value"],
        shader_nodes.socket_by_identifier(squared.inputs, "Value_001"),
    )

    camera = create_node(
        tree.nodes,
        "ShaderNodeCameraData",
        (location[0], location[1] - 180),
        label="Window Camera Data",
    )
    distance_minus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        None,
        4.0,
        label="View Distance - 4",
        location=(location[0] + 340, location[1] - 180),
        hide=True,
    ).node
    tree.links.new(camera.outputs["View Distance"], distance_minus.inputs["Value"])
    transition = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        4.0,
        label="View Distance Transition",
        location=(location[0] + 510, location[1] - 180),
        use_clamp=True,
        hide=True,
    ).node
    tree.links.new(distance_minus.outputs["Value"], transition.inputs["Value"])
    delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        None,
        1.0,
        label="View Angle² - 1",
        location=(location[0] + 510, location[1]),
        hide=True,
    ).node
    tree.links.new(squared.outputs["Value"], delta.inputs["Value"])
    weighted = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Distance Weighted View Angle",
        location=(location[0] + 680, location[1]),
        hide=True,
    ).node
    tree.links.new(delta.outputs["Value"], weighted.inputs["Value"])
    tree.links.new(
        transition.outputs["Value"],
        shader_nodes.socket_by_identifier(weighted.inputs, "Value_001"),
    )
    result = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        1.0,
        label="Window View Angle",
        location=(location[0] + 850, location[1]),
        hide=True,
    ).node
    result.inputs["Value"].default_value = 1.0
    tree.links.new(
        weighted.outputs["Value"],
        shader_nodes.socket_by_identifier(result.inputs, "Value_001"),
    )
    return result.outputs["Value"]


def _build_room_state_nodes(
    tree,
    tan_pos,
    my_id_xy,
    my_id_zw,
    width,
    height,
    scale_random,
    position_random,
    position_x,
    position_y,
    location=(-3200, 500),
):
    split_pos = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label="Window tanPos XYZ"
    )
    tree.links.new(tan_pos, split_pos.inputs["Vector"])
    split_id_xy = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0], location[1] + 220),
        label="Window myID.xy",
    )
    split_id_zw = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0], location[1] - 220),
        label="Window myID.zw",
    )
    tree.links.new(my_id_xy, split_id_xy.inputs["Vector"])
    tree.links.new(my_id_zw, split_id_zw.inputs["Vector"])

    row = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label="tanPos.y / roomHeight",
        location=(location[0] + 180, location[1]),
        hide=True,
    ).node
    tree.links.new(split_pos.outputs["Y"], row.inputs["Value"])
    tree.links.new(height, shader_nodes.socket_by_identifier(row.inputs, "Value_001"))
    row_floor = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FLOOR",
        label="Room Row",
        location=(location[0] + 340, location[1]),
        hide=True,
    ).node
    tree.links.new(row.outputs["Value"], row_floor.inputs["Value"])
    z_random = _hash11(
        tree,
        row_floor.outputs["Value"],
        (location[0] + 500, location[1]),
        "ZaxisRandom",
    )
    z_double = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label="ZaxisRandom*2-1",
        location=(location[0] + 1450, location[1]),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(z_double.inputs, "Value_001").default_value = 2.0
    shader_nodes.socket_by_identifier(z_double.inputs, "Value_002").default_value = -1.0
    tree.links.new(z_random, z_double.inputs["Value"])

    row_width_delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Row Width Random",
        location=(location[0] + 1620, location[1] + 60),
        hide=True,
    ).node
    tree.links.new(z_double.outputs["Value"], row_width_delta.inputs["Value"])
    tree.links.new(
        scale_random,
        shader_nodes.socket_by_identifier(row_width_delta.inputs, "Value_001"),
    )
    object_width_delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Object Width Random",
        location=(location[0] + 1620, location[1] - 60),
        hide=True,
    ).node
    tree.links.new(split_id_zw.outputs["X"], object_width_delta.inputs["Value"])
    tree.links.new(
        scale_random,
        shader_nodes.socket_by_identifier(object_width_delta.inputs, "Value_001"),
    )
    width_sum = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Randomized Room Width",
        location=(location[0] + 1790, location[1] + 20),
        hide=True,
    ).node
    tree.links.new(width, width_sum.inputs["Value"])
    tree.links.new(
        row_width_delta.outputs["Value"],
        shader_nodes.socket_by_identifier(width_sum.inputs, "Value_001"),
    )
    width_final = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="roomWidth2",
        location=(location[0] + 1960, location[1] + 20),
        hide=True,
    ).node
    tree.links.new(width_sum.outputs["Value"], width_final.inputs["Value"])
    tree.links.new(
        object_width_delta.outputs["Value"],
        shader_nodes.socket_by_identifier(width_final.inputs, "Value_001"),
    )
    width_safe = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        None,
        _EPSILON,
        label="roomWidth2 Safe",
        location=(location[0] + 2130, location[1] + 20),
        hide=True,
    ).node
    tree.links.new(width_final.outputs["Value"], width_safe.inputs["Value"])

    row_pos_delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Row X Offset Random",
        location=(location[0] + 1620, location[1] - 180),
        hide=True,
    ).node
    tree.links.new(z_double.outputs["Value"], row_pos_delta.inputs["Value"])
    tree.links.new(
        position_random,
        shader_nodes.socket_by_identifier(row_pos_delta.inputs, "Value_001"),
    )
    object_pos_delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Object X Offset Random",
        location=(location[0] + 1620, location[1] - 300),
        hide=True,
    ).node
    tree.links.new(split_id_zw.outputs["Y"], object_pos_delta.inputs["Value"])
    tree.links.new(
        position_random,
        shader_nodes.socket_by_identifier(object_pos_delta.inputs, "Value_001"),
    )
    pos_sum = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Randomized X Offset",
        location=(location[0] + 1790, location[1] - 220),
        hide=True,
    ).node
    tree.links.new(position_x, pos_sum.inputs["Value"])
    tree.links.new(
        row_pos_delta.outputs["Value"],
        shader_nodes.socket_by_identifier(pos_sum.inputs, "Value_001"),
    )
    pos_final = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="positionXoffset2",
        location=(location[0] + 1960, location[1] - 220),
        hide=True,
    ).node
    tree.links.new(pos_sum.outputs["Value"], pos_final.inputs["Value"])
    tree.links.new(
        object_pos_delta.outputs["Value"],
        shader_nodes.socket_by_identifier(pos_final.inputs, "Value_001"),
    )

    grid_x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label="Window Grid X",
        location=(location[0] + 2300, location[1] + 80),
        hide=True,
    ).node
    tree.links.new(split_pos.outputs["X"], grid_x.inputs["Value"])
    tree.links.new(
        width_safe.outputs["Value"],
        shader_nodes.socket_by_identifier(grid_x.inputs, "Value_001"),
    )
    grid_x_offset = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Window Grid X + Offset",
        location=(location[0] + 2470, location[1] + 80),
        hide=True,
    ).node
    tree.links.new(grid_x.outputs["Value"], grid_x_offset.inputs["Value"])
    tree.links.new(
        pos_final.outputs["Value"],
        shader_nodes.socket_by_identifier(grid_x_offset.inputs, "Value_001"),
    )
    grid_y_offset = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Window Grid Y + Offset",
        location=(location[0] + 2470, location[1] - 80),
        hide=True,
    ).node
    tree.links.new(row.outputs["Value"], grid_y_offset.inputs["Value"])
    tree.links.new(
        position_y, shader_nodes.socket_by_identifier(grid_y_offset.inputs, "Value_001")
    )

    room_x = fract_socket(
        tree,
        grid_x_offset.outputs["Value"],
        (location[0] + 2640, location[1] + 120),
        "roomUV.x",
    )
    room_y = fract_socket(
        tree,
        grid_y_offset.outputs["Value"],
        (location[0] + 2640, location[1] - 120),
        "roomUV.y",
    )
    room_uv = _combine(
        tree, room_x, room_y, location=(location[0] + 2810, location[1]), label="roomUV"
    )

    cell_x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FLOOR",
        label="Room Cell X",
        location=(location[0] + 2810, location[1] + 180),
        hide=True,
    ).node
    cell_y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FLOOR",
        label="Room Cell Y",
        location=(location[0] + 2810, location[1] - 180),
        hide=True,
    ).node
    tree.links.new(grid_x_offset.outputs["Value"], cell_x.inputs["Value"])
    tree.links.new(grid_y_offset.outputs["Value"], cell_y.inputs["Value"])
    cell_x_scaled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        0.01,
        label="Room Cell X * .01",
        location=(location[0] + 2980, location[1] + 180),
        hide=True,
    ).node
    cell_y_scaled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        0.01,
        label="Room Cell Y * .01",
        location=(location[0] + 2980, location[1] - 180),
        hide=True,
    ).node
    tree.links.new(cell_x.outputs["Value"], cell_x_scaled.inputs["Value"])
    tree.links.new(cell_y.outputs["Value"], cell_y_scaled.inputs["Value"])

    my_x_1000 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        1000.0,
        label="myID.x * 1000",
        location=(location[0] + 2810, location[1] + 340),
        hide=True,
    ).node
    my_y_1000 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        1000.0,
        label="myID.y * 1000",
        location=(location[0] + 2810, location[1] + 280),
        hide=True,
    ).node
    tree.links.new(split_id_xy.outputs["X"], my_x_1000.inputs["Value"])
    tree.links.new(split_id_xy.outputs["Y"], my_y_1000.inputs["Value"])
    my_x_floor = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FLOOR",
        label="floor(myID.x*1000)",
        location=(location[0] + 2980, location[1] + 340),
        hide=True,
    ).node
    my_y_floor = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FLOOR",
        label="floor(myID.y*1000)",
        location=(location[0] + 2980, location[1] + 280),
        hide=True,
    ).node
    tree.links.new(my_x_1000.outputs["Value"], my_x_floor.inputs["Value"])
    tree.links.new(my_y_1000.outputs["Value"], my_y_floor.inputs["Value"])
    my_x_q = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        1000.0,
        label="myID.x Quantized",
        location=(location[0] + 3150, location[1] + 340),
        hide=True,
    ).node
    my_y_q = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        1000.0,
        label="myID.y Quantized",
        location=(location[0] + 3150, location[1] + 280),
        hide=True,
    ).node
    tree.links.new(my_x_floor.outputs["Value"], my_x_q.inputs["Value"])
    tree.links.new(my_y_floor.outputs["Value"], my_y_q.inputs["Value"])
    seed_x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Room Seed X",
        location=(location[0] + 3320, location[1] + 180),
        hide=True,
    ).node
    seed_y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Room Seed Y",
        location=(location[0] + 3320, location[1] - 180),
        hide=True,
    ).node
    tree.links.new(cell_x_scaled.outputs["Value"], seed_x.inputs["Value"])
    tree.links.new(
        my_x_q.outputs["Value"],
        shader_nodes.socket_by_identifier(seed_x.inputs, "Value_001"),
    )
    tree.links.new(cell_y_scaled.outputs["Value"], seed_y.inputs["Value"])
    tree.links.new(
        my_y_q.outputs["Value"],
        shader_nodes.socket_by_identifier(seed_y.inputs, "Value_001"),
    )
    seed_input = _combine(
        tree,
        seed_x.outputs["Value"],
        seed_y.outputs["Value"],
        location=(location[0] + 3490, location[1]),
        label="Room Seed Input",
    )
    random_seed = _hash_p3(
        tree, seed_input, "22", (location[0] + 3660, location[1]), "randomSeed"
    )
    random = _hash12(
        tree, random_seed, (location[0] + 6100, location[1] - 60), "Room Random"
    )

    idw_plus_row = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="myID.w + Room Row",
        location=(location[0] + 6100, location[1] - 220),
        hide=True,
    ).node
    tree.links.new(split_id_zw.outputs["Y"], idw_plus_row.inputs["Value"])
    tree.links.new(
        cell_y.outputs["Value"],
        shader_nodes.socket_by_identifier(idw_plus_row.inputs, "Value_001"),
    )
    stable = _hash11(
        tree,
        idw_plus_row.outputs["Value"],
        (location[0] + 6270, location[1] - 220),
        "Room On Random Stable",
    )
    delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        label="Room On Random Delta",
        location=(location[0] + 7200, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(random, delta.inputs["Value"])
    tree.links.new(stable, shader_nodes.socket_by_identifier(delta.inputs, "Value_001"))
    tiny = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        0.005,
        label="Room On Random 0.005",
        location=(location[0] + 7370, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(delta.outputs["Value"], tiny.inputs["Value"])
    room_on_random = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Room On Random",
        location=(location[0] + 7540, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(stable, room_on_random.inputs["Value"])
    tree.links.new(
        tiny.outputs["Value"],
        shader_nodes.socket_by_identifier(room_on_random.inputs, "Value_001"),
    )

    return {
        "room_uv": room_uv,
        "cell_x": cell_x.outputs["Value"],
        "cell_y": cell_y.outputs["Value"],
        "width": width_safe.outputs["Value"],
        "height": height,
        "random_seed": random_seed,
        "random": random,
        "room_on_random": room_on_random.outputs["Value"],
        "my_id_xy": my_id_xy,
    }


def _room_state_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        state = _build_room_state_nodes(
            group,
            group_input.outputs["Tan Position"],
            group_input.outputs["ID XY"],
            group_input.outputs["ID ZW"],
            group_input.outputs["Room Width"],
            group_input.outputs["Room Height"],
            group_input.outputs["Scale X Randomization"],
            group_input.outputs["Position X Randomization"],
            group_input.outputs["Position X Offset"],
            group_input.outputs["Position Y Offset"],
        )
        for source_name, output_name in (
            ("room_uv", "Room UV"),
            ("width", "Room Width"),
            ("height", "Room Height"),
            ("random_seed", "Random Seed"),
            ("random", "Random"),
            ("room_on_random", "Room On Random"),
            ("my_id_xy", "ID XY"),
        ):
            group.links.new(state[source_name], group_output.inputs[output_name])

    return get_or_build_node_group(
        "CP77 Window Room State Bundle v2",
        (
            ("NodeSocketVector", "Tan Position"),
            ("NodeSocketVector", "ID XY"),
            ("NodeSocketVector", "ID ZW"),
            ("NodeSocketFloat", "Room Width"),
            ("NodeSocketFloat", "Room Height"),
            ("NodeSocketFloat", "Scale X Randomization"),
            ("NodeSocketFloat", "Position X Randomization"),
            ("NodeSocketFloat", "Position X Offset"),
            ("NodeSocketFloat", "Position Y Offset"),
        ),
        (
            ("NodeSocketVector", "Room UV"),
            ("NodeSocketFloat", "Room Width"),
            ("NodeSocketFloat", "Room Height"),
            ("NodeSocketVector", "Random Seed"),
            ("NodeSocketFloat", "Random"),
            ("NodeSocketFloat", "Room On Random"),
            ("NodeSocketVector", "ID XY"),
        ),
        build,
    )


def _room_state(tree, tan_pos, my_id_xy, my_id_zw, data, owner, location=(-3200, 500)):
    node = material_bundle_node(
        tree,
        _room_state_group(),
        location,
        "Window Room State",
        {
            "Tan Position": tan_pos,
            "ID XY": my_id_xy,
            "ID ZW": my_id_zw,
            "Room Width": max(
                _EPSILON,
                param_float(data, "roomWidth", owner.room_width_default),
            ),
            "Room Height": max(
                _EPSILON,
                param_float(data, "roomHeight", owner.room_height_default),
            ),
            "Scale X Randomization": param_float(
                data,
                "scaleXrandomization",
                0.0,
            ),
            "Position X Randomization": param_float(
                data,
                "positionXrandomization",
                0.0,
            ),
            "Position X Offset": param_float(
                data,
                "positionXoffset",
                owner.position_x_default,
            ),
            "Position Y Offset": param_float(
                data,
                "positionYoffset",
                owner.position_y_default,
            ),
        },
    )
    return {
        "room_uv": node.outputs["Room UV"],
        "width": node.outputs["Room Width"],
        "height": node.outputs["Room Height"],
        "random_seed": node.outputs["Random Seed"],
        "random": node.outputs["Random"],
        "room_on_random": node.outputs["Room On Random"],
        "my_id_xy": node.outputs["ID XY"],
    }


def _room_pos(tree, room_uv, location):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label="roomUV Components"
    )
    tree.links.new(room_uv, split.inputs["Vector"])
    x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label="roomPos.x",
        location=(location[0] + 170, location[1] + 70),
        hide=True,
    ).node
    y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label="roomPos.y",
        location=(location[0] + 170, location[1] - 70),
        hide=True,
    ).node
    for node in (x, y):
        shader_nodes.socket_by_identifier(node.inputs, "Value_001").default_value = 2.0
        shader_nodes.socket_by_identifier(node.inputs, "Value_002").default_value = -1.0
    tree.links.new(split.outputs["X"], x.inputs["Value"])
    tree.links.new(split.outputs["Y"], y.inputs["Value"])
    z_value = create_node(
        tree.nodes,
        "ShaderNodeValue",
        (location[0] + 170, location[1] - 180),
        label="roomPos.z = -1",
    )
    z_value.outputs["Value"].default_value = -1.0
    return _combine(
        tree,
        x.outputs["Value"],
        y.outputs["Value"],
        z_value.outputs["Value"],
        location=(location[0] + 340, location[1]),
        label="roomPos",
    )


def _eye_components(tree, view_dir, width, height, location, label):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} viewDir"
    )
    tree.links.new(view_dir, split.inputs["Vector"])
    x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} eye.x / roomWidth",
        location=(location[0] + 170, location[1] + 100),
        hide=True,
    ).node
    tree.links.new(split.outputs["X"], x.inputs["Value"])
    tree.links.new(width, shader_nodes.socket_by_identifier(x.inputs, "Value_001"))
    y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} eye.y / roomHeight",
        location=(location[0] + 170, location[1]),
        hide=True,
    ).node
    tree.links.new(split.outputs["Y"], y.inputs["Value"])
    tree.links.new(height, shader_nodes.socket_by_identifier(y.inputs, "Value_001"))
    return x.outputs["Value"], y.outputs["Value"], split.outputs["Z"]


def _eye_vector(tree, components, z_scale, location, label):
    x, y, source_z = components
    z = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        z_scale,
        label=f"{label} eye.z",
        location=(location[0] + 170, location[1] - 100),
        hide=True,
    ).node
    tree.links.new(source_z, z.inputs["Value"])
    return _combine(
        tree,
        x,
        y,
        z.outputs["Value"],
        location=(location[0] + 340, location[1]),
        label=f"{label} eyeVector",
    )


def _build_ray_hit_nodes(tree, room_pos, eye, location, label, room=False):
    inv = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} 1/eye",
        location=location,
        hide=True,
    ).node
    inv.inputs["Vector"].default_value = (1.0, 1.0, 1.0)
    tree.links.new(eye, shader_nodes.socket_by_identifier(inv.inputs, "Vector_001"))
    abs_inv = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        label=f"{label} abs(id)",
        location=(location[0] + 170, location[1]),
        hide=True,
    ).node
    tree.links.new(inv.outputs["Vector"], abs_inv.inputs["Vector"])
    pos_inv = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} roomPos*id",
        location=(location[0] + 170, location[1] - 140),
        hide=True,
    ).node
    tree.links.new(room_pos, pos_inv.inputs["Vector"])
    tree.links.new(
        inv.outputs["Vector"],
        shader_nodes.socket_by_identifier(pos_inv.inputs, "Vector_001"),
    )
    k = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        label=f"{label} k",
        location=(location[0] + 340, location[1] - 60),
        hide=True,
    ).node
    tree.links.new(abs_inv.outputs["Vector"], k.inputs["Vector"])
    tree.links.new(
        pos_inv.outputs["Vector"],
        shader_nodes.socket_by_identifier(k.inputs, "Vector_001"),
    )
    split = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0] + 510, location[1] - 60),
        label=f"{label} k.xyz",
    )
    tree.links.new(k.outputs["Vector"], split.inputs["Vector"])
    if room:
        xy = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MINIMUM",
            label=f"{label} min(k.x,k.y)",
            location=(location[0] + 680, location[1] + 30),
            hide=True,
        ).node
        tree.links.new(split.outputs["X"], xy.inputs["Value"])
        tree.links.new(
            split.outputs["Y"],
            shader_nodes.socket_by_identifier(xy.inputs, "Value_001"),
        )
        distance = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MINIMUM",
            label=f"{label} min(k.xy,k.z)",
            location=(location[0] + 850, location[1] + 30),
            hide=True,
        ).node
        tree.links.new(xy.outputs["Value"], distance.inputs["Value"])
        tree.links.new(
            split.outputs["Z"],
            shader_nodes.socket_by_identifier(distance.inputs, "Value_001"),
        )
        distance_socket = distance.outputs["Value"]
    else:
        distance_socket = split.outputs["Z"]
    travel = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        label=f"{label} Ray Travel",
        location=(location[0] + 680, location[1] - 140),
        hide=True,
    ).node
    tree.links.new(eye, travel.inputs["Vector"])
    tree.links.new(distance_socket, travel.inputs["Scale"])
    hit = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} Hit",
        location=(location[0] + 850, location[1] - 140),
        hide=True,
    ).node
    tree.links.new(room_pos, hit.inputs["Vector"])
    tree.links.new(
        travel.outputs["Vector"],
        shader_nodes.socket_by_identifier(hit.inputs, "Vector_001"),
    )
    return hit.outputs["Vector"], split


def _ray_hit_group(room):
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        hit, k = _build_ray_hit_nodes(
            group,
            group_input.outputs["Room Position"],
            group_input.outputs["Eye"],
            (-500, 0),
            "Ray",
            room=room,
        )
        group.links.new(hit, group_output.inputs["Hit"])
        for name in ("X", "Y", "Z"):
            group.links.new(k.outputs[name], group_output.inputs[name])

    mode = "Room" if room else "Plane"
    return get_or_build_node_group(
        f"CP77 Window {mode} Ray Hit Bundle v1",
        (("NodeSocketVector", "Room Position"), ("NodeSocketVector", "Eye")),
        (
            ("NodeSocketVector", "Hit"),
            ("NodeSocketFloat", "X"),
            ("NodeSocketFloat", "Y"),
            ("NodeSocketFloat", "Z"),
        ),
        build,
    )


def _ray_hit(tree, room_pos, eye, location, label, room=False):
    node = material_bundle_node(
        tree,
        _ray_hit_group(room),
        location,
        f"{label} Ray Hit",
        {"Room Position": room_pos, "Eye": eye},
    )
    return node.outputs["Hit"], node


def _build_perspective_interp_nodes(tree, hit, depth_scale, location, label):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} Hit XYZ"
    )
    tree.links.new(hit, split.inputs["Vector"])
    z01 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label=f"{label} Depth",
        location=(location[0] + 170, location[1]),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(z01.inputs, "Value_001").default_value = 0.5
    shader_nodes.socket_by_identifier(z01.inputs, "Value_002").default_value = 0.5
    tree.links.new(split.outputs["Z"], z01.inputs["Value"])
    saturated2 = shader_nodes.clamp(
        tree.nodes,
        tree.links,
        z01.outputs["Value"],
        label=f"{label} Depth Saturate",
        location=(location[0] + 340, location[1]),
    ).node
    divide = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} / DepthScale",
        location=(location[0] + 680, location[1]),
        hide=True,
    ).node
    tree.links.new(saturated2.outputs["Value"], divide.inputs["Value"])
    tree.links.new(
        depth_scale, shader_nodes.socket_by_identifier(divide.inputs, "Value_001")
    )
    add = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        1.0,
        label=f"{label} RealZ",
        location=(location[0] + 850, location[1]),
        hide=True,
    ).node
    tree.links.new(divide.outputs["Value"], add.inputs["Value"])
    reciprocal = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        1.0,
        label=f"{label} 1/RealZ",
        location=(location[0] + 1020, location[1]),
        hide=True,
    ).node
    tree.links.new(
        add.outputs["Value"],
        shader_nodes.socket_by_identifier(reciprocal.inputs, "Value_001"),
    )
    one_minus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        label=f"{label} Perspective",
        location=(location[0] + 1190, location[1]),
        hide=True,
    ).node
    tree.links.new(
        reciprocal.outputs["Value"],
        shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001"),
    )
    scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        1.0,
        label=f"{label} Depth Scale + 1",
        location=(location[0] + 1360, location[1] - 100),
        hide=True,
    ).node
    tree.links.new(depth_scale, scale.inputs["Value"])
    scaled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} Perspective Scale",
        location=(location[0] + 1530, location[1]),
        hide=True,
    ).node
    tree.links.new(one_minus.outputs["Value"], scaled.inputs["Value"])
    tree.links.new(
        scale.outputs["Value"],
        shader_nodes.socket_by_identifier(scaled.inputs, "Value_001"),
    )
    return scaled.outputs["Value"], split


def _perspective_interp_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        perspective, hit = _build_perspective_interp_nodes(
            group,
            group_input.outputs["Hit"],
            group_input.outputs["Depth Scale"],
            (-750, 0),
            "Perspective",
        )
        group.links.new(perspective, group_output.inputs["Perspective"])
        group.links.new(group_input.outputs["Hit"], group_output.inputs["Hit"])
        for name in ("X", "Y", "Z"):
            group.links.new(hit.outputs[name], group_output.inputs[name])

    return get_or_build_node_group(
        "CP77 Window Perspective Bundle v2",
        (("NodeSocketVector", "Hit"), ("NodeSocketFloat", "Depth Scale")),
        (
            ("NodeSocketFloat", "Perspective"),
            ("NodeSocketVector", "Hit"),
            ("NodeSocketFloat", "X"),
            ("NodeSocketFloat", "Y"),
            ("NodeSocketFloat", "Z"),
        ),
        build,
    )


def _perspective_interp(tree, hit, depth_scale, location, label):
    node = material_bundle_node(
        tree,
        _perspective_interp_group(),
        location,
        f"{label} Perspective",
        {"Hit": hit, "Depth Scale": depth_scale},
    )
    return node.outputs["Perspective"], node


def _build_mapped_uv_nodes(tree, hit, interp, near_scale, far_scale, location, label):
    hit_split = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0], location[1] - 180),
        label=f"{label} Hit",
    )
    tree.links.new(hit, hit_split.inputs["Vector"])
    delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        label=f"{label} Scale Range",
        location=location,
        hide=True,
    ).node
    tree.links.new(far_scale, delta.inputs["Value"])
    tree.links.new(
        near_scale, shader_nodes.socket_by_identifier(delta.inputs, "Value_001")
    )
    factor = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label=f"{label} Perspective XY",
        location=(location[0] + 170, location[1]),
        hide=True,
    ).node
    tree.links.new(interp, factor.inputs["Value"])
    tree.links.new(
        delta.outputs["Value"],
        shader_nodes.socket_by_identifier(factor.inputs, "Value_001"),
    )
    tree.links.new(
        near_scale, shader_nodes.socket_by_identifier(factor.inputs, "Value_002")
    )
    x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} X",
        location=(location[0] + 340, location[1] + 70),
        hide=True,
    ).node
    y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label=f"{label} Y",
        location=(location[0] + 340, location[1] - 70),
        hide=True,
    ).node
    tree.links.new(hit_split.outputs["X"], x.inputs["Value"])
    tree.links.new(
        factor.outputs["Value"],
        shader_nodes.socket_by_identifier(x.inputs, "Value_001"),
    )
    tree.links.new(hit_split.outputs["Y"], y.inputs["Value"])
    tree.links.new(
        factor.outputs["Value"],
        shader_nodes.socket_by_identifier(y.inputs, "Value_001"),
    )
    x01 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label=f"{label} U",
        location=(location[0] + 510, location[1] + 70),
        hide=True,
    ).node
    y01 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label=f"{label} V",
        location=(location[0] + 510, location[1] - 70),
        hide=True,
    ).node
    for node in (x01, y01):
        shader_nodes.socket_by_identifier(node.inputs, "Value_001").default_value = 0.5
        shader_nodes.socket_by_identifier(node.inputs, "Value_002").default_value = 0.5
    tree.links.new(x.outputs["Value"], x01.inputs["Value"])
    tree.links.new(y.outputs["Value"], y01.inputs["Value"])
    return _combine(
        tree,
        x01.outputs["Value"],
        y01.outputs["Value"],
        location=(location[0] + 680, location[1]),
        label=f"{label} UV",
    )


def _mapped_uv_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        uv = _build_mapped_uv_nodes(
            group,
            group_input.outputs["Hit"],
            group_input.outputs["Perspective"],
            group_input.outputs["Near Scale"],
            group_input.outputs["Far Scale"],
            (-340, 0),
            "Interior",
        )
        group.links.new(uv, group_output.inputs["UV"])

    return get_or_build_node_group(
        "CP77 Window Interior Mapping Bundle v1",
        (
            ("NodeSocketVector", "Hit"),
            ("NodeSocketFloat", "Perspective"),
            ("NodeSocketFloat", "Near Scale"),
            ("NodeSocketFloat", "Far Scale"),
        ),
        (("NodeSocketVector", "UV"),),
        build,
    )


def _mapped_uv(tree, hit_stage, interp, near_scale, far_scale, location, label):
    node = material_bundle_node(
        tree,
        _mapped_uv_group(),
        location,
        label,
        {
            "Hit": hit_stage.outputs["Hit"],
            "Perspective": interp,
            "Near Scale": near_scale,
            "Far Scale": far_scale,
        },
    )
    return node.outputs["UV"]


def _flip_room_uv(tree, uv, random, location):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label="Interior UV Before Flip"
    )
    tree.links.new(uv, split.inputs["Vector"])
    r100 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        100.0,
        label="Room Random * 100",
        location=(location[0] + 170, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(random, r100.inputs["Value"])
    fraction = fract_socket(
        tree,
        r100.outputs["Value"],
        (location[0] + 340, location[1] - 120),
        "frac(Room Random*100)",
    )
    flip = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        0.5,
        label="Room Horizontal Flip",
        location=(location[0] + 510, location[1] - 120),
        hide=True,
    ).node
    tree.links.new(fraction, flip.inputs["Value"])
    one_minus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        label="1 - Interior U",
        location=(location[0] + 170, location[1] + 80),
        hide=True,
    ).node
    tree.links.new(
        split.outputs["X"],
        shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001"),
    )
    delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        label="Flipped U Delta",
        location=(location[0] + 340, location[1] + 80),
        hide=True,
    ).node
    tree.links.new(one_minus.outputs["Value"], delta.inputs["Value"])
    tree.links.new(
        split.outputs["X"], shader_nodes.socket_by_identifier(delta.inputs, "Value_001")
    )
    weighted = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Flip U Select",
        location=(location[0] + 510, location[1] + 80),
        hide=True,
    ).node
    tree.links.new(delta.outputs["Value"], weighted.inputs["Value"])
    tree.links.new(
        flip.outputs["Value"],
        shader_nodes.socket_by_identifier(weighted.inputs, "Value_001"),
    )
    x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Interior U Flipped",
        location=(location[0] + 680, location[1] + 80),
        hide=True,
    ).node
    tree.links.new(split.outputs["X"], x.inputs["Value"])
    tree.links.new(
        weighted.outputs["Value"],
        shader_nodes.socket_by_identifier(x.inputs, "Value_001"),
    )
    return _combine(
        tree,
        x.outputs["Value"],
        split.outputs["Y"],
        location=(location[0] + 850, location[1]),
        label="Interior UV Source Flip",
    )


def _atlas_index(tree, my_id_xy, random_seed, columns, rows, location=(-1100, 1100)):
    my = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label="myID.xy Atlas"
    )
    rnd = create_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        (location[0], location[1] - 180),
        label="randomSeed Atlas",
    )
    tree.links.new(my_id_xy, my.inputs["Vector"])
    tree.links.new(random_seed, rnd.inputs["Vector"])
    outputs = []
    for source_a, source_b, size, y, axis in (
        (my.outputs["X"], rnd.outputs["X"], columns, 80, "X"),
        (my.outputs["Y"], rnd.outputs["Y"], rows, -100, "Y"),
    ):
        a_mul = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            size,
            label=f"Atlas {axis} myID",
            location=(location[0] + 170, location[1] + y),
            hide=True,
        ).node
        b_mul = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            size,
            label=f"Atlas {axis} Random",
            location=(location[0] + 170, location[1] + y - 60),
            hide=True,
        ).node
        tree.links.new(source_a, a_mul.inputs["Value"])
        tree.links.new(source_b, b_mul.inputs["Value"])
        a_floor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label=f"Atlas {axis} myID Floor",
            location=(location[0] + 340, location[1] + y),
            hide=True,
        ).node
        b_floor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label=f"Atlas {axis} Random Floor",
            location=(location[0] + 340, location[1] + y - 60),
            hide=True,
        ).node
        tree.links.new(a_mul.outputs["Value"], a_floor.inputs["Value"])
        tree.links.new(b_mul.outputs["Value"], b_floor.inputs["Value"])
        total = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label=f"Atlas {axis} Sum",
            location=(location[0] + 510, location[1] + y - 30),
            hide=True,
        ).node
        tree.links.new(a_floor.outputs["Value"], total.inputs["Value"])
        tree.links.new(
            b_floor.outputs["Value"],
            shader_nodes.socket_by_identifier(total.inputs, "Value_001"),
        )
        modulo = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MODULO",
            None,
            float(size),
            label=f"Atlas {axis} Modulo",
            location=(location[0] + 680, location[1] + y - 30),
            hide=True,
        ).node
        tree.links.new(total.outputs["Value"], modulo.inputs["Value"])
        outputs.append(modulo.outputs["Value"])
    return outputs[0], outputs[1]


def _build_atlas_uv_nodes(tree, uv, index_x, index_y, columns, rows, location, label):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label=f"{label} UV"
    )
    tree.links.new(uv, split.inputs["Vector"])
    u = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} U / Columns",
        location=(location[0] + 170, location[1] + 80),
        hide=True,
    ).node
    v = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} V / Rows",
        location=(location[0] + 170, location[1] - 80),
        hide=True,
    ).node
    tree.links.new(split.outputs["X"], u.inputs["Value"])
    tree.links.new(columns, shader_nodes.socket_by_identifier(u.inputs, "Value_001"))
    tree.links.new(split.outputs["Y"], v.inputs["Value"])
    tree.links.new(rows, shader_nodes.socket_by_identifier(v.inputs, "Value_001"))
    iu = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} Cell U",
        location=(location[0] + 170, location[1] + 180),
        hide=True,
    ).node
    iv = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        label=f"{label} Cell V",
        location=(location[0] + 170, location[1] - 180),
        hide=True,
    ).node
    tree.links.new(index_x, iu.inputs["Value"])
    tree.links.new(columns, shader_nodes.socket_by_identifier(iu.inputs, "Value_001"))
    tree.links.new(index_y, iv.inputs["Value"])
    tree.links.new(rows, shader_nodes.socket_by_identifier(iv.inputs, "Value_001"))
    out_u = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} U",
        location=(location[0] + 340, location[1] + 80),
        hide=True,
    ).node
    out_v = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label=f"{label} V",
        location=(location[0] + 340, location[1] - 80),
        hide=True,
    ).node
    tree.links.new(u.outputs["Value"], out_u.inputs["Value"])
    tree.links.new(
        iu.outputs["Value"],
        shader_nodes.socket_by_identifier(out_u.inputs, "Value_001"),
    )
    tree.links.new(v.outputs["Value"], out_v.inputs["Value"])
    tree.links.new(
        iv.outputs["Value"],
        shader_nodes.socket_by_identifier(out_v.inputs, "Value_001"),
    )
    return _combine(
        tree,
        out_u.outputs["Value"],
        out_v.outputs["Value"],
        location=(location[0] + 510, location[1]),
        label=label,
    )


def _atlas_uv_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")
        uv = _build_atlas_uv_nodes(
            group,
            group_input.outputs["UV"],
            group_input.outputs["Index X"],
            group_input.outputs["Index Y"],
            group_input.outputs["Columns"],
            group_input.outputs["Rows"],
            (-250, 0),
            "Atlas",
        )
        group.links.new(uv, group_output.inputs["UV"])

    return get_or_build_node_group(
        "CP77 Window Atlas Mapping Bundle v1",
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Index X"),
            ("NodeSocketFloat", "Index Y"),
            ("NodeSocketFloat", "Columns"),
            ("NodeSocketFloat", "Rows"),
        ),
        (("NodeSocketVector", "UV"),),
        build,
    )


def _atlas_uv(tree, uv, index_x, index_y, columns, rows, location, label):
    node = material_bundle_node(
        tree,
        _atlas_uv_group(),
        location,
        label,
        {
            "UV": uv,
            "Index X": index_x,
            "Index Y": index_y,
            "Columns": columns,
            "Rows": rows,
        },
    )
    return node.outputs["UV"]


def build_window_parallax_coordinates(
    owner, tree, data, room_atlas_depth, *, include_layer=True
):
    geometry, tan_pos, view_dir, pivot = _source_basis(tree)
    my_id_xy, my_id_zw = _object_id(tree, pivot)
    state = _room_state(tree, tan_pos, my_id_xy, my_id_zw, data, owner)
    room_pos = _room_pos(tree, state["room_uv"], (-2200, 1600))

    room_depth_scale = 1.0 / max(_EPSILON, 1.0 - room_atlas_depth) - 1.0
    layer_depth = (
        max(0.001, 1.0 - param_float(data, "LayerDepth", 0.4))
        if include_layer
        else None
    )
    curtain_depth = max(0.001, 1.0 - param_float(data, "CurtainDepth", 0.3))
    layer_depth_scale = (
        (1.0 / max(_EPSILON, 1.0 - layer_depth) - 1.0) if include_layer else None
    )
    curtain_depth_scale = 1.0 / max(_EPSILON, 1.0 - curtain_depth) - 1.0
    room_depth = max(_EPSILON, param_float(data, "roomDepth", owner.room_depth_default))

    eye_components = _eye_components(
        tree, view_dir, state["width"], state["height"], (-2200, 1300), "Room"
    )
    room_eye = _eye_vector(
        tree, eye_components, -room_depth_scale / room_depth, (-2200, 1300), "Room"
    )
    layer_eye = (
        _eye_vector(tree, eye_components, -layer_depth_scale, (-2200, 1000), "Layer")
        if include_layer
        else None
    )
    curtain_eye = _eye_vector(
        tree, eye_components, -curtain_depth_scale, (-2200, 700), "Curtain"
    )

    room_hit, room_k = _ray_hit(
        tree, room_pos, room_eye, (-1500, 1450), "Room", room=True
    )
    layer_hit, layer_k = (
        _ray_hit(tree, room_pos, layer_eye, (-1500, 1000), "Layer")
        if include_layer
        else (None, None)
    )
    curtain_hit, curtain_k = _ray_hit(
        tree, room_pos, curtain_eye, (-1500, 550), "Curtain"
    )

    seed_split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", (-580, 420), label="Curtain randomSeed"
    )
    tree.links.new(state["random_seed"], seed_split.inputs["Vector"])
    cover_random = max(0.0, param_float(data, "CurtainCoverRandomize", 0.5))
    max_cover = max(0.0, min(1.0, param_float(data, "CurtainMaxCover", 0.4)))
    random_shift = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        cover_random * 3.0,
        label="Curtain Random Cover",
        location=(-400, 500),
        hide=True,
    ).node
    tree.links.new(seed_split.outputs["X"], random_shift.inputs["Value"])
    fixed_shift = (1.0 - max_cover) * 2.0
    shift_sum = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        fixed_shift,
        label="Curtain Cover Shift",
        location=(-230, 500),
        hide=True,
    ).node
    tree.links.new(random_shift.outputs["Value"], shift_sum.inputs["Value"])
    sun_facing = create_node(
        tree.nodes, "ShaderNodeValue", (-400, 300), label="Sun Facing Preview"
    )
    sun_facing.outputs["Value"].default_value = 0.5
    sun_double = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        2.0,
        label="Sun Facing x2",
        location=(-230, 300),
        hide=True,
    ).node
    tree.links.new(sun_facing.outputs["Value"], sun_double.inputs["Value"])
    sun_sq = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="(Sun Facing x2)^2",
        location=(-60, 300),
        hide=True,
    ).node
    tree.links.new(sun_double.outputs["Value"], sun_sq.inputs["Value"])
    tree.links.new(
        sun_double.outputs["Value"],
        shader_nodes.socket_by_identifier(sun_sq.inputs, "Value_001"),
    )
    sun_one_minus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        label="1 - Sun Facing²",
        location=(110, 300),
        hide=True,
    ).node
    tree.links.new(
        sun_sq.outputs["Value"],
        shader_nodes.socket_by_identifier(sun_one_minus.inputs, "Value_001"),
    )
    sun_seed = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Sun Curtain Random",
        location=(280, 300),
        hide=True,
    ).node
    tree.links.new(sun_one_minus.outputs["Value"], sun_seed.inputs["Value"])
    tree.links.new(
        seed_split.outputs["Y"],
        shader_nodes.socket_by_identifier(sun_seed.inputs, "Value_001"),
    )
    sun_term = shader_nodes.clamp(
        tree.nodes,
        tree.links,
        sun_seed.outputs["Value"],
        label="Sun Curtain Saturate",
        location=(450, 300),
    ).node
    shift_sun = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Curtain Cover + Sun",
        location=(-60, 500),
        hide=True,
    ).node
    tree.links.new(shift_sum.outputs["Value"], shift_sun.inputs["Value"])
    tree.links.new(
        sun_term.outputs["Value"],
        shader_nodes.socket_by_identifier(shift_sun.inputs, "Value_001"),
    )
    neg_shift = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        -1.0,
        label="Curtain Cover Shift Y",
        location=(110, 500),
        hide=True,
    ).node
    tree.links.new(shift_sun.outputs["Value"], neg_shift.inputs["Value"])
    shift_vector = create_node(
        tree.nodes, "ShaderNodeCombineXYZ", (280, 500), label="Curtain Source Offset"
    )
    tree.links.new(neg_shift.outputs["Value"], shift_vector.inputs["Y"])
    shifted_curtain = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        label="Curtain Hit + Cover Offset",
        location=(450, 500),
        hide=True,
    ).node
    tree.links.new(curtain_hit, shifted_curtain.inputs["Vector"])
    tree.links.new(
        shift_vector.outputs["Vector"],
        shader_nodes.socket_by_identifier(shifted_curtain.inputs, "Vector_001"),
    )
    curtain_hit = shifted_curtain.outputs["Vector"]

    room_interp, room_hit_split = _perspective_interp(
        tree, room_hit, room_depth_scale, (-580, 1500), "Room"
    )
    if include_layer:
        layer_interp, layer_hit_split = _perspective_interp(
            tree, layer_hit, layer_depth_scale, (-580, 1040), "Layer"
        )
    else:
        layer_interp, layer_hit_split = None, None
    curtain_interp, curtain_hit_split = _perspective_interp(
        tree, curtain_hit, curtain_depth_scale, (-580, 620), "Curtain"
    )

    ratio = param_vector(data, "AtlasGridUvRatio", (1.0, 1.0, 1.0, 1.0))
    columns = max(1, int(float(ratio[1])))
    rows = max(1, int(float(ratio[0])))
    max_size = max(_EPSILON, float(ratio[2]), float(ratio[3]))
    room_far_scale = max_size / (max_size + (1.0 / max(_EPSILON, room_depth_scale)))

    room_map = _mapped_uv(
        tree,
        room_hit_split,
        room_interp,
        1.0,
        room_far_scale,
        (900, 1500),
        "Room Interior",
    )
    room_map = _flip_room_uv(tree, room_map, state["random"], (1480, 1500))
    layer_map = (
        _mapped_uv(
            tree,
            layer_hit_split,
            layer_interp,
            layer_depth,
            1.0,
            (900, 1050),
            "Layer Interior",
        )
        if include_layer
        else None
    )
    curtain_map = _mapped_uv(
        tree,
        curtain_hit_split,
        curtain_interp,
        curtain_depth,
        1.0,
        (900, 620),
        "Curtain Interior",
    )

    curtain_k_split = curtain_k
    if include_layer:
        layer_k_split = layer_k
        layer_x = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label="Layer k.x >= k.z",
            location=(900, 850),
            hide=True,
        ).node
        layer_y = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            label="Layer k.y >= k.z",
            location=(900, 760),
            hide=True,
        ).node
        tree.links.new(layer_k_split.outputs["X"], layer_x.inputs["Value"])
        tree.links.new(
            layer_k_split.outputs["Z"],
            shader_nodes.socket_by_identifier(layer_x.inputs, "Value_001"),
        )
        tree.links.new(layer_k_split.outputs["Y"], layer_y.inputs["Value"])
        tree.links.new(
            layer_k_split.outputs["Z"],
            shader_nodes.socket_by_identifier(layer_y.inputs, "Value_001"),
        )
        layer_mask = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Layer Geometry Mask",
            location=(1070, 800),
            hide=True,
        ).node
        tree.links.new(layer_x.outputs["Value"], layer_mask.inputs["Value"])
        tree.links.new(
            layer_y.outputs["Value"],
            shader_nodes.socket_by_identifier(layer_mask.inputs, "Value_001"),
        )
        layer_mask_socket = layer_mask.outputs["Value"]
    else:
        layer_mask_socket = None

    curtain_y01 = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        label="Curtain Y 0..1",
        location=(900, 420),
        hide=True,
    ).node
    shader_nodes.socket_by_identifier(
        curtain_y01.inputs, "Value_001"
    ).default_value = 0.5
    shader_nodes.socket_by_identifier(
        curtain_y01.inputs, "Value_002"
    ).default_value = 0.5
    tree.links.new(curtain_hit_split.outputs["Y"], curtain_y01.inputs["Value"])
    curtain_y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        0.01,
        label="Curtain Y >= .01",
        location=(1070, 420),
        hide=True,
    ).node
    tree.links.new(curtain_y01.outputs["Value"], curtain_y.inputs["Value"])
    curtain_x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        label="Curtain k.x >= k.z",
        location=(1070, 330),
        hide=True,
    ).node
    tree.links.new(curtain_k_split.outputs["X"], curtain_x.inputs["Value"])
    tree.links.new(
        curtain_k_split.outputs["Z"],
        shader_nodes.socket_by_identifier(curtain_x.inputs, "Value_001"),
    )
    curtain_mask = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="Curtain Geometry Mask",
        location=(1240, 380),
        hide=True,
    ).node
    tree.links.new(curtain_y.outputs["Value"], curtain_mask.inputs["Value"])
    tree.links.new(
        curtain_x.outputs["Value"],
        shader_nodes.socket_by_identifier(curtain_mask.inputs, "Value_001"),
    )

    index_x, index_y = _atlas_index(
        tree, state["my_id_xy"], state["random_seed"], columns, rows
    )
    room_atlas_uv = _atlas_uv(
        tree, room_map, index_x, index_y, columns, rows, (2450, 1480), "Room Atlas UV"
    )
    layer_atlas_uv = (
        _atlas_uv(
            tree,
            layer_map,
            index_x,
            index_y,
            columns,
            rows,
            (2450, 1030),
            "Layer Atlas UV",
        )
        if include_layer
        else None
    )
    curtain_atlas_uv = _atlas_uv(
        tree,
        curtain_map,
        index_x,
        index_y,
        columns,
        rows,
        (2450, 580),
        "Curtain Atlas UV",
    )

    room_texture_uv = state["room_uv"]
    view_angle = _view_angle(tree, geometry)

    return WindowParallaxCoordinates(
        room_uv=room_texture_uv,
        room_atlas_uv=room_atlas_uv,
        layer_atlas_uv=layer_atlas_uv,
        curtain_atlas_uv=curtain_atlas_uv,
        layer_mask=layer_mask_socket,
        curtain_mask=curtain_mask.outputs["Value"],
        room_interp=room_interp,
        room_hit_y=room_hit_split.outputs["Y"],
        random=state["random"],
        room_on_random=state["room_on_random"],
        view_angle=view_angle,
        object_pivot=pivot,
    )


def color_overlay_uv(tree, object_pivot, location=(-800, -900)):
    split = create_node(
        tree.nodes, "ShaderNodeSeparateXYZ", location, label="Window Object Pivot XY"
    )
    tree.links.new(object_pivot, split.inputs["Vector"])
    outputs = []
    for source, low, high, y, axis in (
        (split.outputs["X"], 2000.0, 12500.0, 60, "X"),
        (split.outputs["Y"], 3000.0, 13500.0, -60, "Y"),
    ):
        add = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            None,
            8000.0,
            label=f"Overlay {axis} + 8000",
            location=(location[0] + 170, location[1] + y),
            hide=True,
        ).node
        tree.links.new(source, add.inputs["Value"])
        upper = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            add.outputs["Value"],
            low,
            high,
            label=f"Overlay {axis} Clamp",
            location=(location[0] + 340, location[1] + y),
        ).node
        origin = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            None,
            low,
            label=f"Overlay {axis} Origin",
            location=(location[0] + 680, location[1] + y),
            hide=True,
        ).node
        tree.links.new(upper.outputs["Result"], origin.inputs["Value"])
        normalized = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            None,
            high - low,
            label=f"Overlay {axis} Normalize",
            location=(location[0] + 850, location[1] + y),
            hide=True,
        ).node
        tree.links.new(origin.outputs["Value"], normalized.inputs["Value"])
        outputs.append(normalized.outputs["Value"])
    return _combine(
        tree,
        outputs[0],
        outputs[1],
        location=(location[0] + 1020, location[1]),
        label="Color Overlay Pivot UV",
    )
