from __future__ import annotations

from contextlib import contextmanager
from itertools import count

import bpy
import numpy as np

from ..bartmoss.scalar import clamp_scalar
from .identity import rna_identity, rna_is_live


def new_node(tree, node_type, name, location, *, label=None, strip_label_prefix=""):
    node = tree.nodes.new(node_type)
    node.name = name
    display_label = str(name) if label is None else str(label)
    if (
        label is None
        and strip_label_prefix
        and display_label.startswith(strip_label_prefix)
    ):
        display_label = display_label[len(strip_label_prefix) :]
    node.label = display_label
    node.location = location
    return node


_MATH_INPUTS = ("Value", "Value_001", "Value_002")
_VECTOR_INPUTS = ("Vector", "Vector_001", "Vector_002")
_VECTOR_VALUE_OPERATIONS = frozenset({"DOT_PRODUCT", "DISTANCE", "LENGTH"})


def assign_socket(links, value, target):
    """Link an output socket into target, or set a number or tuple as its value"""
    if hasattr(value, "is_output"):
        links.new(value, target)
    elif value is not None:
        if target.type == "RGBA" and isinstance(value, (int, float)):
            value = (value, value, value, 1.0)
        elif target.type == "VECTOR" and isinstance(value, (int, float)):
            value = (value,) * len(target.default_value)
        elif target.type == "VECTOR" and isinstance(value, (tuple, list)):
            # A colour constant reaches a vector input as its red, green and blue.
            value = tuple(value)[: len(target.default_value)]
        target.default_value = value
    return target


def _operation_node(nodes, node_type, operation, name, label, location, hide):
    node = nodes.new(node_type)
    if name:
        node.name = name
    label = name if label is None else label
    if label:
        node.label = label
    node.location = location
    node.hide = hide
    node.operation = operation
    return node


def math(
    nodes,
    links,
    operation,
    a=None,
    b=None,
    c=None,
    *,
    name="",
    label=None,
    location=(0, 0),
    use_clamp=False,
    hide=False,
):
    """A Math node's result"""
    node = _operation_node(
        nodes, "ShaderNodeMath", operation, name, label, location, hide
    )
    node.use_clamp = use_clamp
    for operand, identifier in zip((a, b, c), _MATH_INPUTS):
        if operand is not None:
            assign_socket(links, operand, socket_by_identifier(node.inputs, identifier))
    return socket_by_identifier(node.outputs, "Value")


def vector_math(
    nodes,
    links,
    operation,
    a=None,
    b=None,
    c=None,
    *,
    scale=None,
    name="",
    label=None,
    location=(0, 0),
    hide=False,
):
    """A Vector Math node's result"""
    node = _operation_node(
        nodes, "ShaderNodeVectorMath", operation, name, label, location, hide
    )
    for operand, identifier in zip((a, b, c, scale), (*_VECTOR_INPUTS, "Scale")):
        if operand is not None:
            assign_socket(links, operand, socket_by_identifier(node.inputs, identifier))
    return socket_by_identifier(
        node.outputs, "Value" if operation in _VECTOR_VALUE_OPERATIONS else "Vector"
    )


def lerp(nodes, links, a, b, t, *, name="", location=(0, 0)):
    difference = math(
        nodes, links, "SUBTRACT", b, a, name=f"{name} Difference", location=location
    )
    return math(
        nodes,
        links,
        "MULTIPLY_ADD",
        difference,
        t,
        a,
        name=name,
        location=(location[0] + 140, location[1]),
    )


def vector_lerp(nodes, links, a, b, t, *, name="", location=(0, 0)):
    """t is a float or a vector"""
    delta = vector_math(
        nodes, links, "SUBTRACT", b, a, name=f"{name} Delta", location=location
    )
    return vector_math(
        nodes,
        links,
        "MULTIPLY_ADD",
        delta,
        t,
        a,
        name=name,
        location=(location[0] + 170, location[1]),
    )


def clamp(
    nodes, links, value, low=0.0, high=1.0, *, name="", label=None, location=(0, 0)
):
    producer = getattr(value, "node", None)
    if (
        isinstance(low, float)
        and isinstance(high, float)
        and (low, high) == (0.0, 1.0)
        and getattr(producer, "bl_idname", "") == "ShaderNodeMath"
        and not value.is_linked
    ):
        producer.use_clamp = True
        return value
    node = nodes.new("ShaderNodeClamp")
    if name:
        node.name = name
    label = name if label is None else label
    if label:
        node.label = label
    node.location = location
    for operand, identifier in ((value, "Value"), (low, "Min"), (high, "Max")):
        if operand is not None:
            assign_socket(links, operand, socket_by_identifier(node.inputs, identifier))
    return socket_by_identifier(node.outputs, "Result")


def value_node(tree, name, value, location):
    node = new_node(tree, "ShaderNodeValue", name, location)
    node.outputs["Value"].default_value = float(value)
    return node


def rgb_node(tree, name, value, location):
    node = new_node(tree, "ShaderNodeRGB", name, location)
    node.outputs["Color"].default_value = (*value[:3], 1.0)
    return node


def socket(collection, *names):
    """The first socket found under any of the names, else None"""
    for name in names:
        found = collection.get(name)
        if found is not None:
            return found
    return None


def link(tree, output_socket, input_socket):
    """Link two sockets when both exist"""
    if output_socket is not None and input_socket is not None:
        tree.links.new(output_socket, input_socket)


def replace_link(links, output_socket, input_socket):
    """Link output_socket into input_socket in place of its current links"""
    if getattr(input_socket, "is_multi_input", False):
        for existing in list(input_socket.links):
            links.remove(existing)
    return links.new(output_socket, input_socket, verify_limits=True)


_OUTPUT_NODE_TYPES = frozenset(
    {
        "ShaderNodeOutputMaterial",
        "ShaderNodeOutputLight",
        "ShaderNodeOutputWorld",
        "ShaderNodeOutputAOV",
        "NodeGroupOutput",
    }
)


def socket_by_identifier(sockets, identifier):
    """The socket of sockets with this identifier, or None"""
    return next((socket for socket in sockets if socket.identifier == identifier), None)


def principled_bsdf(nodes):
    return next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)


def material_output(nodes):
    return next((node for node in nodes if node.type == "OUTPUT_MATERIAL"), None)


# The colour Mix node's factor, A, B and result sockets.
MIX_COLOR_SOCKETS = ("Factor_Float", "A_Color", "B_Color", "Result_Color")


def mix_color_sockets(node):
    """The (factor, A, B, result) sockets of a colour Mix node"""
    factor, first, second, result = MIX_COLOR_SOCKETS
    inputs = node.inputs
    return (
        socket_by_identifier(inputs, factor),
        socket_by_identifier(inputs, first),
        socket_by_identifier(inputs, second),
        socket_by_identifier(node.outputs, result),
    )


_DETACHED_MARK = "_cp77_outputs_detached"
_detach_calls = count(1)


@contextmanager
def outputs_detached(tree):
    """Unlink the inputs of tree's output nodes while it is edited, then link them as they were"""
    if tree is None:
        yield
        return
    links = tree.links
    mark = f"{_DETACHED_MARK}_{next(_detach_calls)}"
    tokens = count()
    detached = []

    def token(node):
        if mark not in node:
            node[mark] = next(tokens)
        return node[mark]

    for node in tree.nodes:
        if node.bl_idname not in _OUTPUT_NODE_TYPES:
            continue
        for target in node.inputs:
            for link in tuple(target.links):
                detached.append(
                    (
                        token(link.from_node),
                        link.from_socket.identifier,
                        token(node),
                        target.identifier,
                        link.is_muted,
                    )
                )
                links.remove(link)
    try:
        yield
    finally:
        if detached:
            nodes = {}
            for node in tree.nodes:
                if mark in node:
                    nodes[node[mark]] = node
                    del node[mark]
            for from_node, from_socket, to_node, to_socket, muted in detached:
                source_node, target_node = nodes.get(from_node), nodes.get(to_node)
                if source_node is None or target_node is None:
                    continue
                source = socket_by_identifier(source_node.outputs, from_socket)
                target = socket_by_identifier(target_node.inputs, to_socket)
                if (
                    source is None
                    or target is None
                    or (target.is_linked and not target.is_multi_input)
                ):
                    continue
                restored = links.new(source, target)
                if muted:
                    restored.is_muted = True


def _stored_equal(current, value):
    """Whether writing value would leave the stored single-precision RNA value unchanged"""
    try:
        if hasattr(current, "__len__"):
            return np.array_equal(
                np.asarray(current[:], dtype=np.float32),
                np.asarray(value, dtype=np.float32),
            )
        return np.float32(current) == np.float32(value)
    except (TypeError, ValueError):
        return False


def assign_if_changed(owner, attribute, value):
    """Set an RNA float property unless the stored value would not change"""
    if _stored_equal(getattr(owner, attribute), value):
        return False
    setattr(owner, attribute, value)
    return True


def set_default_if_changed(socket_or_none, value):
    if socket_or_none is None:
        return False
    return assign_if_changed(socket_or_none, "default_value", value)


def _value_tree(owner):
    """The node tree holding preview value nodes"""
    if owner is None:
        return None
    if hasattr(owner, "nodes"):
        return owner
    if getattr(owner, "use_nodes", False):
        return owner.node_tree
    return None


def set_value_output(owner, name, value, *, epsilon=1.0e-10):
    """Write a named Value node of a material or node group unless it is already within epsilon"""
    tree = _value_tree(owner)
    if tree is None:
        return False
    node = tree.nodes.get(name)
    if node is None or not node.outputs:
        return False
    target = float(value)
    try:
        current = float(node.outputs["Value"].default_value)
    except (ReferenceError, ValueError):
        return False
    if abs(current - target) <= float(epsilon):
        return False
    node.outputs["Value"].default_value = target
    return True


def set_color_output(
    owner,
    name,
    rgb,
    *,
    minimum=0.0,
    maximum=1.0,
    epsilon=1.0e-10,
):
    tree = _value_tree(owner)
    if tree is None:
        return False
    node = tree.nodes.get(name)
    if node is None or not node.outputs:
        return False
    values = []
    for component in rgb[:3]:
        value = max(float(minimum), float(component))
        if maximum is not None:
            value = clamp_scalar(value, float(minimum), float(maximum))
        values.append(value)
    target = (*values, 1.0)
    try:
        current = tuple(
            float(value) for value in node.outputs["Color"].default_value[:4]
        )
    except (ReferenceError, ValueError):
        return False
    if len(current) == 4 and all(
        abs(current[index] - target[index]) <= float(epsilon) for index in range(4)
    ):
        return False
    node.outputs["Color"].default_value = target
    return True


def _group_node_trees(tree):
    for node in getattr(tree, "nodes", ()):
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree is not None:
            yield node.node_tree


def remove_unused_shading(datablocks):
    """Remove the unused materials and node groups in datablocks and return how many"""
    removed = 0
    pending = tuple(datablocks)
    while pending:
        unused = {}
        for value in pending:
            if rna_is_live(value) and value.users == 0:
                unused.setdefault(rna_identity(value), value)
        if not unused:
            break
        nested = {}
        for value in unused.values():
            tree = (
                value
                if isinstance(value, bpy.types.NodeTree)
                else getattr(value, "node_tree", None)
            )
            for group in _group_node_trees(tree):
                nested.setdefault(rna_identity(group), group)
        bpy.data.batch_remove(tuple(unused.values()))
        removed += len(unused)
        pending = tuple(nested.values())
    return removed
