from __future__ import annotations

import math

from . import shader_nodes
from .shader_nodes import outputs_detached, socket_by_identifier

# The node a decal material takes each placement's colour scale, roughness scale, alpha and emissive scale on.
OVERRIDE_NODE = "CP77 Decal Instance Overrides"


def alpha_factor_present(
    alpha_socket,
    sector_alpha,
    tolerance=1e-6,
):
    if alpha_socket is None or not getattr(alpha_socket, "is_linked", False):
        return False
    links = list(getattr(alpha_socket, "links", ()))
    if len(links) != 1:
        return False
    source_node = getattr(links[0], "from_node", None)
    if (
        source_node is None
        or getattr(source_node, "bl_idname", "") != "ShaderNodeMath"
        or getattr(source_node, "operation", "") != "MULTIPLY"
    ):
        return False
    for socket in list(getattr(source_node, "inputs", ()))[:2]:
        if getattr(socket, "is_linked", False):
            continue
        try:
            if math.isclose(
                float(socket.default_value),
                sector_alpha,
                abs_tol=tolerance,
            ):
                return True
        except (TypeError, ValueError):
            continue
    return False


def apply_sector_alpha(material, sector_alpha):
    if not material.use_nodes or material.node_tree is None:
        return "NO_NODE_TREE"

    tree = material.node_tree
    alpha_sockets = []
    for node in tree.nodes:
        if getattr(node, "bl_idname", "") != "ShaderNodeBsdfPrincipled":
            continue
        alpha_socket = node.inputs.get("Alpha")
        if alpha_socket is not None:
            alpha_sockets.append(alpha_socket)

    if not alpha_sockets:
        return "NO_PRINCIPLED_ALPHA"

    modes = []
    for alpha_socket in alpha_sockets:
        if alpha_factor_present(
            alpha_socket,
            sector_alpha,
        ):
            modes.append("HANDLER")
            continue

        links = list(alpha_socket.links)
        if links:
            source_socket = links[0].from_socket
            for link in links:
                tree.links.remove(link)
            multiplied = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                source_socket,
                sector_alpha,
                name="CP77 Sector Decal Alpha",
                location=(
                    alpha_socket.node.location.x - 220.0,
                    alpha_socket.node.location.y - 260.0,
                ),
            )
            tree.links.new(multiplied, alpha_socket)
            modes.append("POST_MULTIPLY")
        else:
            try:
                alpha_socket.default_value = (
                    float(alpha_socket.default_value) * sector_alpha
                )
            except (TypeError, ValueError):
                alpha_socket.default_value = sector_alpha
            modes.append("SOCKET_DEFAULT")

    return "+".join(sorted(set(modes)))


def apply_override_values(tree, values):
    """Write values into the decal's override node, or every node with such inputs"""
    override_node = tree.nodes.get(OVERRIDE_NODE)
    candidate_nodes = (
        (override_node,) if override_node is not None else tuple(tree.nodes)
    )
    for node in candidate_nodes:
        for socket in node.inputs:
            key = socket.name.replace(" ", "").replace("_", "").lower()
            if key not in values or not hasattr(socket, "default_value"):
                continue
            try:
                socket.default_value = values[key]
            except (TypeError, ValueError):
                pass


def capture_graph_state(material):
    """Capture inputs changed by sector finalization without retaining RNA sockets"""
    if "alpha" in material or material.node_tree is None:
        return None
    tree = material.node_tree
    override = tree.nodes.get(OVERRIDE_NODE)
    if override is None:
        return None
    alpha = []
    for node in tree.nodes:
        if node.bl_idname != "ShaderNodeBsdfPrincipled":
            continue
        socket = node.inputs.get("Alpha")
        if socket is not None:
            alpha.append(
                (
                    node.name,
                    float(socket.default_value),
                    tuple(
                        (link.from_node.name, link.from_socket.identifier)
                        for link in socket.links
                    ),
                )
            )
    values = []
    for socket in override.inputs:
        if not hasattr(socket, "default_value"):
            continue
        value = socket.default_value
        values.append(
            (socket.name, tuple(value) if hasattr(value, "__len__") else value)
        )
    return tuple(alpha), tuple(values), frozenset(node.name for node in tree.nodes)


def restore_graph_state(tree, state, added_nodes):
    """Put a copy of a placed decal's material back as capture_graph_state found it"""
    with outputs_detached(tree):
        for name in added_nodes:
            node = tree.nodes.get(name)
            if node is not None:
                tree.nodes.remove(node)
        for name, value, sources in state[0]:
            socket = tree.nodes[name].inputs["Alpha"]
            for link in tuple(socket.links):
                tree.links.remove(link)
            socket.default_value = value
            for source_name, identifier in sources:
                tree.links.new(
                    socket_by_identifier(tree.nodes[source_name].outputs, identifier),
                    socket,
                )
        override = tree.nodes[OVERRIDE_NODE]
        for name, value in state[1]:
            override.inputs[name].default_value = value


def nodes_added_since(tree, state):
    """The names of the nodes added to tree since capture_graph_state returned state"""
    return tuple(node.name for node in tree.nodes if node.name not in state[2])
