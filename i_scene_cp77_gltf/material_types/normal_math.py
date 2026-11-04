from ..blender import shader_nodes
from ..materials.blender.nodes import configure_tangent_normal_map
from .mat_common import (
    add_group_node,
    find_input,
    get_or_build_node_group,
    new_labeled_node,
    param_float,
    param_texture_path,
)

_GROUP_NAME = "CP77 DirectX Tangent Normal v1"


def _build_decode_group(group):
    nodes = group.nodes
    links = group.links
    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-980, 0)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (760, 0)

    encoded = group_in.outputs["Encoded"]
    strength = group_in.outputs["Strength"]

    split = new_labeled_node(nodes, "ShaderNodeSeparateColor", "Encoded RG", (-800, 0))
    split.mode = "RGB"
    links.new(encoded, split.inputs["Color"])

    x2 = shader_nodes.math(
        nodes, links, "MULTIPLY", name="R x 2", location=(-620, 120)
    ).node
    shader_nodes.socket_by_identifier(x2.inputs, "Value_001").default_value = 2.0
    links.new(split.outputs["Red"], x2.inputs["Value"])
    x = shader_nodes.math(
        nodes, links, "SUBTRACT", name="X = 2R - 1", location=(-460, 120)
    ).node
    shader_nodes.socket_by_identifier(x.inputs, "Value_001").default_value = 1.0
    links.new(x2.outputs["Value"], x.inputs["Value"])

    y2 = shader_nodes.math(
        nodes, links, "MULTIPLY", name="G x 2", location=(-620, -40)
    ).node
    shader_nodes.socket_by_identifier(y2.inputs, "Value_001").default_value = 2.0
    links.new(split.outputs["Green"], y2.inputs["Value"])
    y_dx = shader_nodes.math(
        nodes, links, "SUBTRACT", name="Ydx = 2G - 1", location=(-460, -40)
    ).node
    shader_nodes.socket_by_identifier(y_dx.inputs, "Value_001").default_value = 1.0
    links.new(y2.outputs["Value"], y_dx.inputs["Value"])

    x_sq = shader_nodes.math(
        nodes, links, "MULTIPLY", name="X²", location=(-280, 160)
    ).node
    links.new(x.outputs["Value"], x_sq.inputs["Value"])
    links.new(
        x.outputs["Value"], shader_nodes.socket_by_identifier(x_sq.inputs, "Value_001")
    )
    y_sq = shader_nodes.math(
        nodes, links, "MULTIPLY", name="Y²", location=(-280, 40)
    ).node
    links.new(y_dx.outputs["Value"], y_sq.inputs["Value"])
    links.new(
        y_dx.outputs["Value"],
        shader_nodes.socket_by_identifier(y_sq.inputs, "Value_001"),
    )
    sum_sq = shader_nodes.math(
        nodes, links, "ADD", name="X² + Y²", location=(-100, 100)
    ).node
    links.new(x_sq.outputs["Value"], sum_sq.inputs["Value"])
    links.new(
        y_sq.outputs["Value"],
        shader_nodes.socket_by_identifier(sum_sq.inputs, "Value_001"),
    )
    z_sq = shader_nodes.math(
        nodes, links, "SUBTRACT", name="1 - X² - Y²", location=(80, 100)
    ).node
    z_sq.inputs["Value"].default_value = 1.0
    links.new(
        sum_sq.outputs["Value"],
        shader_nodes.socket_by_identifier(z_sq.inputs, "Value_001"),
    )
    safe_z_sq = shader_nodes.math(
        nodes, links, "MAXIMUM", name="max(Z², 0)", location=(240, 100)
    ).node
    shader_nodes.socket_by_identifier(safe_z_sq.inputs, "Value_001").default_value = 0.0
    links.new(z_sq.outputs["Value"], safe_z_sq.inputs["Value"])
    z = shader_nodes.math(
        nodes, links, "SQRT", name="Reconstruct Z", location=(400, 100)
    ).node
    links.new(safe_z_sq.outputs["Value"], z.inputs["Value"])

    y_blender = shader_nodes.math(
        nodes, links, "MULTIPLY", name="DirectX Y → Blender Y", location=(-100, -100)
    ).node
    shader_nodes.socket_by_identifier(
        y_blender.inputs, "Value_001"
    ).default_value = -1.0
    links.new(y_dx.outputs["Value"], y_blender.inputs["Value"])

    x_strength = shader_nodes.math(
        nodes, links, "MULTIPLY", name="X x Strength", location=(80, -120)
    ).node
    links.new(x.outputs["Value"], x_strength.inputs["Value"])
    links.new(
        strength, shader_nodes.socket_by_identifier(x_strength.inputs, "Value_001")
    )
    y_strength = shader_nodes.math(
        nodes, links, "MULTIPLY", name="Y x Strength", location=(80, -240)
    ).node
    links.new(y_blender.outputs["Value"], y_strength.inputs["Value"])
    links.new(
        strength, shader_nodes.socket_by_identifier(y_strength.inputs, "Value_001")
    )

    tangent = new_labeled_node(
        nodes, "ShaderNodeCombineXYZ", "Strength-adjusted Tangent", (260, -140)
    )
    links.new(x_strength.outputs["Value"], tangent.inputs["X"])
    links.new(y_strength.outputs["Value"], tangent.inputs["Y"])
    links.new(z.outputs["Value"], tangent.inputs["Z"])

    normalize = shader_nodes.vector_math(
        nodes, links, "NORMALIZE", name="Normalize Tangent", location=(440, -120)
    ).node
    links.new(tangent.outputs["Vector"], normalize.inputs["Vector"])

    encode = shader_nodes.vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        name="Encode for Blender Normal Map",
        location=(600, -120),
    ).node
    shader_nodes.socket_by_identifier(encode.inputs, "Vector_001").default_value = (
        0.5,
        0.5,
        0.5,
    )
    shader_nodes.socket_by_identifier(encode.inputs, "Vector_002").default_value = (
        0.5,
        0.5,
        0.5,
    )
    links.new(normalize.outputs["Vector"], encode.inputs["Vector"])

    links.new(normalize.outputs["Vector"], group_out.inputs["Tangent"])
    links.new(encode.outputs["Vector"], group_out.inputs["Color"])


def cp77_directx_normal_group():
    return get_or_build_node_group(
        _GROUP_NAME,
        (("NodeSocketColor", "Encoded"), ("NodeSocketFloat", "Strength")),
        (("NodeSocketVector", "Tangent"), ("NodeSocketColor", "Color")),
        _build_decode_group,
    )


def decode_cp77_normal(
    tree, encoded_socket, *, strength=1.0, location=(0, 0), label="CP77 Normal"
):
    node = add_group_node(tree, cp77_directx_normal_group(), location, label=label)
    tree.links.new(encoded_socket, node.inputs["Encoded"])
    if hasattr(strength, "is_output"):
        tree.links.new(strength, node.inputs["Strength"])
    else:
        node.inputs["Strength"].default_value = max(0.0, float(strength))
    return node


def tangent_to_normal_map(
    tree, tangent_color_socket, *, location=(0, 0), label="Normal"
):
    node = configure_tangent_normal_map(
        new_labeled_node(tree.nodes, "ShaderNodeNormalMap", label, location)
    )
    strength = find_input(node, "Strength")
    if strength is not None:
        strength.default_value = 1.0
    tree.links.new(tangent_color_socket, node.inputs["Color"])
    return node.outputs["Normal"]


def create_cp77_normal_texture(
    owner,
    tree,
    data,
    key="Normal",
    *,
    uv=None,
    strength_key="NormalStrength",
    default_strength=1.0,
    location=(-1000, -300),
    label=None,
    extension="REPEAT",
):
    resolver = getattr(owner, "_texture_path", None)
    path = resolver(data, key) if callable(resolver) else param_texture_path(data, key)
    if not path:
        return None
    image = owner._load_relative_image(path, non_color=True, error_label=key)
    if image is None:
        return None
    texture = new_labeled_node(tree.nodes, "ShaderNodeTexImage", label or key, location)
    texture.image = image
    texture.extension = extension
    if uv is not None:
        tree.links.new(uv, texture.inputs["Vector"])
    decoder = decode_cp77_normal(
        tree,
        texture.outputs["Color"],
        strength=max(0.0, param_float(data, strength_key, default_strength)),
        location=(location[0] + 260, location[1]),
        label=f"{label or key} DirectX Decode",
    )
    normal = tangent_to_normal_map(
        tree,
        decoder.outputs["Color"],
        location=(location[0] + 500, location[1]),
        label=label or key,
    )
    return normal


def combine_cp77_tangent_normals(
    tree, base_tangent, detail_tangent, *, location=(0, 0), label="Combined Normal"
):
    base_split = new_labeled_node(
        tree.nodes, "ShaderNodeSeparateXYZ", f"{label} Base", location
    )
    detail_split = new_labeled_node(
        tree.nodes,
        "ShaderNodeSeparateXYZ",
        f"{label} Detail",
        (location[0], location[1] - 180),
    )
    tree.links.new(base_tangent, base_split.inputs["Vector"])
    tree.links.new(detail_tangent, detail_split.inputs["Vector"])

    x = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        name=f"{label} X",
        location=(location[0] + 180, location[1] + 40),
    ).node
    y = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        name=f"{label} Y",
        location=(location[0] + 180, location[1] - 60),
    ).node
    z = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name=f"{label} Z",
        location=(location[0] + 180, location[1] - 160),
    ).node
    tree.links.new(base_split.outputs["X"], x.inputs["Value"])
    tree.links.new(
        detail_split.outputs["X"],
        shader_nodes.socket_by_identifier(x.inputs, "Value_001"),
    )
    tree.links.new(base_split.outputs["Y"], y.inputs["Value"])
    tree.links.new(
        detail_split.outputs["Y"],
        shader_nodes.socket_by_identifier(y.inputs, "Value_001"),
    )
    tree.links.new(base_split.outputs["Z"], z.inputs["Value"])
    tree.links.new(
        detail_split.outputs["Z"],
        shader_nodes.socket_by_identifier(z.inputs, "Value_001"),
    )

    combined = new_labeled_node(
        tree.nodes, "ShaderNodeCombineXYZ", label, (location[0] + 360, location[1] - 40)
    )
    tree.links.new(x.outputs["Value"], combined.inputs["X"])
    tree.links.new(y.outputs["Value"], combined.inputs["Y"])
    tree.links.new(z.outputs["Value"], combined.inputs["Z"])
    normalize = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        name=f"{label} Normalize",
        location=(location[0] + 540, location[1] - 40),
    ).node
    tree.links.new(combined.outputs["Vector"], normalize.inputs["Vector"])
    return normalize.outputs["Vector"]


def encode_tangent_normal(
    tree, tangent_socket, *, location=(0, 0), label="Encode Tangent Normal"
):
    node = shader_nodes.vector_math(
        tree.nodes, tree.links, "MULTIPLY_ADD", name=label, location=location
    ).node
    shader_nodes.socket_by_identifier(node.inputs, "Vector_001").default_value = (
        0.5,
        0.5,
        0.5,
    )
    shader_nodes.socket_by_identifier(node.inputs, "Vector_002").default_value = (
        0.5,
        0.5,
        0.5,
    )
    tree.links.new(tangent_socket, node.inputs["Vector"])
    return node.outputs["Vector"]


def directx_tangent_to_blender(
    tree,
    tangent_socket,
    *,
    strength=1.0,
    location=(0, 0),
    label="DirectX Tangent",
):
    scale = shader_nodes.vector_math(
        tree.nodes, tree.links, "MULTIPLY", name=f"{label} Strength", location=location
    ).node
    tree.links.new(tangent_socket, scale.inputs["Vector"])

    if hasattr(strength, "is_output"):
        strength_vector = new_labeled_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            f"{label} Strength Vector",
            (location[0], location[1] - 160),
        )
        tree.links.new(strength, strength_vector.inputs["X"])
        tree.links.new(strength, strength_vector.inputs["Y"])
        strength_vector.inputs["Z"].default_value = 1.0
        tree.links.new(
            strength_vector.outputs["Vector"],
            shader_nodes.socket_by_identifier(scale.inputs, "Vector_001"),
        )
    else:
        value = float(strength)
        shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
            value,
            value,
            1.0,
        )

    orient = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name=f"{label} DirectX Y to Blender Y",
        location=(location[0] + 180, location[1]),
    ).node
    shader_nodes.socket_by_identifier(orient.inputs, "Vector_001").default_value = (
        1.0,
        -1.0,
        1.0,
    )
    tree.links.new(scale.outputs["Vector"], orient.inputs["Vector"])

    normalize = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        name=f"{label} Normalize",
        location=(location[0] + 360, location[1]),
    ).node
    tree.links.new(orient.outputs["Vector"], normalize.inputs["Vector"])
    return normalize.outputs["Vector"]


def directx_tangent_to_normal_map(
    tree,
    tangent_socket,
    *,
    strength=1.0,
    location=(0, 0),
    label="Normal",
):
    tangent = directx_tangent_to_blender(
        tree,
        tangent_socket,
        strength=strength,
        location=location,
        label=label,
    )
    encoded = encode_tangent_normal(
        tree,
        tangent,
        location=(location[0] + 540, location[1]),
        label=f"{label} Encode",
    )
    return tangent_to_normal_map(
        tree,
        encoded,
        location=(location[0] + 720, location[1]),
        label=label,
    )
