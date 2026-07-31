from .mat_common import find_input, new_labeled_node


def is_output_socket(value):
    return hasattr(value, "is_output")


def find_socket(collection, name, fallback=None):
    socket = collection.get(name) if hasattr(collection, "get") else None
    if socket is None and fallback is not None and fallback < len(collection):
        socket = collection[fallback]
    return socket


def set_node_input(node, name, value, fallback=None):
    socket = find_socket(node.inputs, name, fallback)
    if socket is not None:
        socket.default_value = value
    return socket


def link_tree(tree, output_socket, input_socket):
    if output_socket is not None and input_socket is not None:
        tree.links.new(output_socket, input_socket)


def set_material_properties(material, **properties):
    for name, value in properties.items():
        if not hasattr(material, name):
            continue
        try:
            setattr(material, name, value)
        except (AttributeError, TypeError, ValueError):
            continue


def set_alpha_clip(material, threshold, *, render_method="DITHERED"):
    set_material_properties(
        material,
        surface_render_method=render_method,
        blend_method="CLIP",
        alpha_threshold=float(threshold),
    )


def set_opaque(material):
    set_material_properties(material, blend_method="OPAQUE")


def set_transparent(material):
    material.use_nodes = True
    set_material_properties(
        material,
        use_backface_culling=False,
        show_transparent_back=True,
        use_transparency_overlap=False,
        surface_render_method="DITHERED",
        blend_method="BLEND",
        shadow_method="NONE",
    )


def link_or_value(links, source, target, value=None):
    if source is not None:
        links.new(source, target)
    elif value is not None:
        target.default_value = value
    return target


def assign_socket(links, value, target):
    if is_output_socket(value):
        links.new(value, target)
    elif value is not None:
        target.default_value = value
    return target


def math_node(nodes, operation, name, location, first=None, second=None, clamp=False):
    node = new_labeled_node(nodes, "ShaderNodeMath", name, location)
    node.operation = operation
    node.use_clamp = clamp
    if first is not None and not is_output_socket(first):
        node.inputs[0].default_value = float(first)
    if second is not None and not is_output_socket(second) and len(node.inputs) > 1:
        node.inputs[1].default_value = float(second)
    return node


def connect_math(links, node, first=None, second=None):
    if first is not None:
        assign_socket(links, first, node.inputs[0])
    if second is not None and len(node.inputs) > 1:
        assign_socket(links, second, node.inputs[1])
    return node.outputs[0]


def math_socket(nodes, links, operation, name, location, first=None, second=None, clamp=False):
    node = math_node(nodes, operation, name, location, clamp=clamp)
    return connect_math(links, node, first, second)


def unary_math_socket(nodes, links, operation, name, value, location, clamp=False):
    return math_socket(nodes, links, operation, name, location, value, clamp=clamp)


def vector_math_socket(
    nodes,
    links,
    operation,
    name,
    location,
    first=None,
    second=None,
    scale=None,
):
    node = new_labeled_node(nodes, "ShaderNodeVectorMath", name, location)
    node.operation = operation
    if first is not None:
        assign_socket(links, first, node.inputs[0])
    if second is not None and len(node.inputs) > 1:
        assign_socket(links, second, node.inputs[1])
    if scale is not None:
        scale_input = find_input(node, "Scale")
        if scale_input is None and len(node.inputs) > 3:
            scale_input = node.inputs[3]
        if scale_input is not None:
            assign_socket(links, scale, scale_input)
    if operation in {"DOT_PRODUCT", "DISTANCE", "LENGTH"}:
        return node.outputs.get("Value") or node.outputs[-1]
    return node.outputs.get("Vector") or node.outputs[0]


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
    node = new_labeled_node(nodes, "ShaderNodeMixRGB", name, location)
    node.blend_type = blend_type
    node.use_clamp = clamp
    assign_socket(links, factor, node.inputs[0])
    assign_socket(links, first, node.inputs[1])
    assign_socket(links, second, node.inputs[2])
    return node.outputs[0]


def multiply_color_socket(nodes, links, name, first, second, location, *, clamp=False):
    return mix_color_socket(
        nodes,
        links,
        name,
        first,
        second,
        1.0,
        location,
        blend_type="MULTIPLY",
        clamp=clamp,
    )


def mix_color_at_socket(
    nodes,
    links,
    name,
    location,
    first,
    second,
    factor=1.0,
    *,
    blend_type="MIX",
    clamp=False,
):
    return mix_color_socket(
        nodes,
        links,
        name,
        first,
        second,
        factor,
        location,
        blend_type=blend_type,
        clamp=clamp,
    )


def multiply_color_at_socket(nodes, links, name, location, first, second, *, clamp=False):
    return multiply_color_socket(
        nodes,
        links,
        name,
        first,
        second,
        location,
        clamp=clamp,
    )


def red_channel_at_socket(nodes, links, name, location, source):
    return red_channel_socket(nodes, links, source, name, location)

def mix_scalar_socket(nodes, links, name, location, first, second, factor):
    node = new_labeled_node(nodes, "ShaderNodeMix", name, location)
    try:
        node.data_type = "FLOAT"
    except (AttributeError, TypeError, ValueError):
        pass
    factor_input = find_input(node, "Factor")
    first_input = find_input(node, "A")
    second_input = find_input(node, "B")
    result = node.outputs.get("Result") if hasattr(node.outputs, "get") else None
    if all(socket is not None for socket in (factor_input, first_input, second_input, result)):
        assign_socket(links, factor, factor_input)
        assign_socket(links, first, first_input)
        assign_socket(links, second, second_input)
        return result
    try:
        nodes.remove(node)
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass
    delta = math_socket(nodes, links, "SUBTRACT", f"{name} Delta", location, second, first)
    weighted = math_socket(
        nodes,
        links,
        "MULTIPLY",
        f"{name} Weight",
        (location[0] + 150, location[1]),
        delta,
        factor,
    )
    return math_socket(
        nodes,
        links,
        "ADD",
        name,
        (location[0] + 300, location[1]),
        first,
        weighted,
    )


def rgb_socket(nodes, name, color, location):
    node = new_labeled_node(nodes, "ShaderNodeRGB", name, location)
    node.outputs[0].default_value = color
    return node.outputs[0]


def value_node(nodes, name, value, location, label=None):
    node = new_labeled_node(nodes, "ShaderNodeValue", name, location)
    node.outputs[0].default_value = float(value)
    if label:
        node.label = label
    return node


def value_socket(nodes, name, value, location, label=None):
    return value_node(nodes, name, value, location, label).outputs[0]


def red_channel_socket(nodes, links, source, name, location):
    node = new_labeled_node(nodes, "ShaderNodeSeparateColor", name, location)
    try:
        node.mode = "RGB"
    except (AttributeError, TypeError, ValueError):
        pass
    links.new(source, node.inputs.get("Color") or node.inputs[0])
    return node.outputs.get("Red") or node.outputs[0]


def safe_positive(value, fallback=1.0, epsilon=1.0e-5):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(fallback)
    return max(float(epsilon), value)


def safe_unit_interval(value, fallback=0.5, epsilon=1.0e-5):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(fallback)
    epsilon = float(epsilon)
    return max(epsilon, min(1.0 - epsilon, value))
