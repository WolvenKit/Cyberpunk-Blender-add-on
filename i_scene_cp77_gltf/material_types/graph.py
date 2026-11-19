import logging

from ..assetio.values import coerce_float
from ..blender import shader_nodes
from ..blender.mesh import TANGENT_SIGN_ATTRIBUTE, TANGENT_SIGN_VALID_ATTRIBUTE
from ..blender.shader_nodes import assign_socket, mix_color_sockets
from ..core.log import get_logger, log_once
from ..materials.blender.nodes import create_node
from .mat_common import find_input, get_or_build_node_group, new_labeled_node

_LOG = get_logger(__name__)


def fract_socket(tree, source, location, label):
    node = shader_nodes.math(
        tree.nodes, tree.links, "FRACT", label=label, location=location, hide=True
    ).node
    tree.links.new(source, node.inputs["Value"])
    return node.outputs["Value"]


def combine_xyz_socket(tree, x, y, z=None, location=(0, 0), label="Vector"):
    node = create_node(tree.nodes, "ShaderNodeCombineXYZ", location, label=label)
    tree.links.new(x, node.inputs["X"])
    tree.links.new(y, node.inputs["Y"])
    if z is not None:
        tree.links.new(z, node.inputs["Z"])
    return node.outputs["Vector"]


def set_material_properties(material, **properties):
    for name, value in properties.items():
        if not hasattr(material, name):
            continue
        try:
            setattr(material, name, value)
        except (AttributeError, TypeError, ValueError):
            log_once(
                _LOG,
                logging.DEBUG,
                "set_material_properties",
                "set_material_properties skipped what it could not read or write",
                exc_info=True,
            )
            continue


def set_alpha_clip(material, threshold, *, render_method="DITHERED"):
    set_material_properties(
        material,
        surface_render_method=render_method,
        alpha_threshold=float(threshold),
    )


def set_transparent(material):
    material.use_nodes = True
    set_material_properties(
        material,
        use_backface_culling=False,
        use_transparency_overlap=False,
        surface_render_method="BLENDED",
    )


def add_displacement(material, nodes, links, output, height, label, location):
    """Move the surface along its normal by height, a number or a socket, through the output's Displacement

    Sets Displacement and Bump: Blender's default Bump Only turns a constant offset such as a decal's
    VertexOffsetFactor into nothing and leaves the surface z-fighting its receiver.
    """
    if not hasattr(height, "is_output") and abs(float(height)) <= 1.0e-12:
        return None
    node = new_labeled_node(nodes, "ShaderNodeDisplacement", label, location)
    assign_socket(
        links,
        height if hasattr(height, "is_output") else float(height),
        find_input(node, "Height"),
    )
    find_input(node, "Midlevel").default_value = 0.0
    find_input(node, "Scale").default_value = 1.0
    links.new(node.outputs["Displacement"], find_input(output, "Displacement"))
    set_material_properties(material, displacement_method="BOTH")
    return node


def connect_math(links, node, first=None, second=None):
    if first is not None:
        assign_socket(links, first, node.inputs["Value"])
    if second is not None and len(node.inputs) > 1:
        assign_socket(
            links, second, shader_nodes.socket_by_identifier(node.inputs, "Value_001")
        )
    return node.outputs["Value"]


def grid_location(tree, spacing=(180, 140)):
    """The next cell of a grid eight nodes wide, counted by the tree's nodes"""
    count = len(tree.nodes)
    return (spacing[0] * (count % 8), -spacing[1] * (count // 8))


def mix_color_socket(
    nodes,
    links,
    name,
    first,
    second,
    factor,
    location,
    *,
    blend_type="MIX",
    clamp=False,
):
    node = new_labeled_node(nodes, "ShaderNodeMix", name, location)
    node.data_type = "RGBA"
    node.blend_type = blend_type
    node.clamp_factor = False
    node.clamp_result = clamp
    factor_input, first_input, second_input, result = mix_color_sockets(node)
    assign_socket(links, factor, factor_input)
    assign_socket(links, first, first_input)
    assign_socket(links, second, second_input)
    return result


def mix_color_second_input(node):
    """The colour mix node's B input, which mix_color_socket fills with its second"""
    return mix_color_sockets(node)[2]


def cp77_uv_tangent_node(nodes, location, *, label="CP77 UV Tangent", uv_map="UVMap"):
    tangent = new_labeled_node(nodes, "ShaderNodeTangent", label, location)
    tangent.direction_type = "UV_MAP"
    tangent.uv_map = uv_map
    return tangent


def cp77_tangent_sign_socket(
    nodes,
    links,
    location,
    *,
    label="CP77 Tangent Sign",
    sign_attribute=TANGENT_SIGN_ATTRIBUTE,
    valid_attribute=TANGENT_SIGN_VALID_ATTRIBUTE,
):
    attribute = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        f"{label} Attribute",
        location,
    )
    attribute.attribute_type = "GEOMETRY"
    attribute.attribute_name = sign_attribute
    source = attribute.outputs.get("Fac") or attribute.outputs["Factor"]

    valid_attribute_node = new_labeled_node(
        nodes,
        "ShaderNodeAttribute",
        f"{label} Valid Attribute",
        (location[0] + 180, location[1] - 80),
    )
    valid_attribute_node.attribute_type = "GEOMETRY"
    valid_attribute_node.attribute_name = valid_attribute
    valid = (
        valid_attribute_node.outputs.get("Fac")
        or valid_attribute_node.outputs["Factor"]
    )

    return mix_scalar_socket(
        nodes,
        links,
        label,
        (location[0] + 420, location[1]),
        1.0,
        source,
        valid,
    )


def _cp77_signed_bitangent_group():
    def build(group):
        group_input = group.nodes.new("NodeGroupInput")
        group_output = group.nodes.new("NodeGroupOutput")

        cross = shader_nodes.vector_math(group.nodes, group.links, "CROSS_PRODUCT").node
        group.links.new(group_input.outputs["Normal"], cross.inputs["Vector"])
        group.links.new(
            group_input.outputs["Tangent"],
            shader_nodes.socket_by_identifier(cross.inputs, "Vector_001"),
        )

        sign_attribute = group.nodes.new("ShaderNodeAttribute")
        sign_attribute.attribute_type = "GEOMETRY"
        sign_attribute.attribute_name = TANGENT_SIGN_ATTRIBUTE
        sign = sign_attribute.outputs.get("Fac") or sign_attribute.outputs["Factor"]

        valid_attribute = group.nodes.new("ShaderNodeAttribute")
        valid_attribute.attribute_type = "GEOMETRY"
        valid_attribute.attribute_name = TANGENT_SIGN_VALID_ATTRIBUTE
        valid = valid_attribute.outputs.get("Fac") or valid_attribute.outputs["Factor"]

        select_sign = group.nodes.new("ShaderNodeMix")
        select_sign.data_type = "FLOAT"
        factor_input = find_input(select_sign, "Factor")
        a_input = find_input(select_sign, "A")
        b_input = find_input(select_sign, "B")
        a_input.default_value = 1.0
        group.links.new(valid, factor_input)
        group.links.new(sign, b_input)

        scale = shader_nodes.vector_math(group.nodes, group.links, "SCALE").node
        group.links.new(
            cross.outputs["Vector"],
            scale.inputs["Vector"],
        )
        group.links.new(
            select_sign.outputs.get("Result")
            or shader_nodes.socket_by_identifier(select_sign.outputs, "Result_Float"),
            find_input(scale, "Scale"),
        )
        group.links.new(
            scale.outputs["Vector"],
            group_output.inputs["Bitangent"],
        )

    return get_or_build_node_group(
        "CP77 Signed Bitangent v1",
        (("NodeSocketVector", "Normal"), ("NodeSocketVector", "Tangent")),
        (("NodeSocketVector", "Bitangent"),),
        build,
    )


def cp77_bitangent_socket(
    nodes,
    links,
    normal,
    tangent,
    location,
    *,
    label="CP77 Bitangent",
    sign_attribute=TANGENT_SIGN_ATTRIBUTE,
    valid_attribute=TANGENT_SIGN_VALID_ATTRIBUTE,
):
    if (
        sign_attribute != TANGENT_SIGN_ATTRIBUTE
        or valid_attribute != TANGENT_SIGN_VALID_ATTRIBUTE
    ):
        cross = shader_nodes.vector_math(
            nodes,
            links,
            "CROSS_PRODUCT",
            normal,
            tangent,
            name=f"{label} Cross",
            location=location,
        )
        sign = cp77_tangent_sign_socket(
            nodes,
            links,
            (location[0], location[1] - 160),
            label=f"{label} Sign",
            sign_attribute=sign_attribute,
            valid_attribute=valid_attribute,
        )
        return shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            cross,
            scale=sign,
            name=label,
            location=(location[0] + 560, location[1]),
        )

    node = new_labeled_node(nodes, "ShaderNodeGroup", label, location)
    node.node_tree = _cp77_signed_bitangent_group()
    assign_socket(links, normal, node.inputs["Normal"])
    assign_socket(links, tangent, node.inputs["Tangent"])
    return node.outputs["Bitangent"]


def mix_scalar_socket(nodes, links, name, location, first, second, factor):
    node = new_labeled_node(nodes, "ShaderNodeMix", name, location)
    node.data_type = "FLOAT"
    assign_socket(links, factor, find_input(node, "Factor"))
    assign_socket(links, first, find_input(node, "A"))
    assign_socket(links, second, find_input(node, "B"))
    return node.outputs["Result"]


def rgb_socket(nodes, name, color, location):
    node = new_labeled_node(nodes, "ShaderNodeRGB", name, location)
    node.outputs["Color"].default_value = color
    return node.outputs["Color"]


def value_node(nodes, name, value, location, label=None):
    node = new_labeled_node(nodes, "ShaderNodeValue", name, location)
    node.outputs["Value"].default_value = float(value)
    if label:
        node.label = label
    return node


def value_socket(nodes, name, value, location, label=None):
    return value_node(nodes, name, value, location, label).outputs["Value"]


def separate_color_node(nodes, links, source, name, location, *, mode="RGB"):
    node = new_labeled_node(nodes, "ShaderNodeSeparateColor", name, location)
    try:
        node.mode = mode
    except ValueError:
        pass
    links.new(source, node.inputs["Color"])
    return node


def separate_color_sockets(nodes, links, source, name, location, *, mode="RGB"):
    node = separate_color_node(
        nodes,
        links,
        source,
        name,
        location,
        mode=mode,
    )
    return tuple(
        shader_nodes.socket_by_identifier(node.outputs, identifier)
        for identifier in ("Red", "Green", "Blue")
    )


def color_channel_socket(
    nodes,
    links,
    source,
    name,
    location,
    *,
    channel="Red",
    mode="RGB",
):
    node = separate_color_node(
        nodes,
        links,
        source,
        name,
        location,
        mode=mode,
    )
    return node.outputs.get(channel) or shader_nodes.socket_by_identifier(
        node.outputs, "Red"
    )


def combine_color_socket(
    nodes,
    links,
    name,
    location,
    first,
    second,
    third,
    *,
    mode="RGB",
):
    node = new_labeled_node(nodes, "ShaderNodeCombineColor", name, location)
    try:
        node.mode = mode
    except ValueError:
        pass
    assign_socket(links, first, node.inputs["Red"])
    assign_socket(links, second, node.inputs["Green"])
    assign_socket(links, third, node.inputs["Blue"])
    return node.outputs["Color"]


def white_noise_socket(
    nodes,
    links,
    name,
    location,
    source,
    *,
    dimensions="1D",
):
    node = new_labeled_node(nodes, "ShaderNodeTexWhiteNoise", name, location)
    try:
        node.noise_dimensions = dimensions
    except ValueError:
        pass
    input_name = "W" if dimensions == "1D" else "Vector"
    socket = find_input(node, input_name) or node.inputs["Vector"]
    links.new(source, socket)
    return node.outputs["Value"]


def safe_positive(value, fallback=1.0, epsilon=1.0e-5):
    value = coerce_float(value, fallback, unwrap=False, finite=False)
    return max(float(epsilon), value)


def safe_unit_interval(value, fallback=0.5, epsilon=1.0e-5):
    value = coerce_float(value, fallback, unwrap=False, finite=False)
    epsilon = float(epsilon)
    return max(epsilon, min(1.0 - epsilon, value))
