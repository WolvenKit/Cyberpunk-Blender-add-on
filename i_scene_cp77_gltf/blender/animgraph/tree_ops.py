import typing

import bpy

from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ...core.log import get_logger
from ..transactions import track_created_datablock

_LOG = get_logger(__name__)

GENERIC_NODE_ID = "REDengine_AnimGraphNode_Generic"
CONTAINER_NODE_ID = "REDengine_AnimGraphContainer"


def new_graph_tree(name: str) -> bpy.types.NodeTree:
    """Create an AnimGraph node tree, tracked for undo of a failed import"""
    return track_created_datablock(
        "node_groups", bpy.data.node_groups.new(name=name, type=ANIMGRAPH_TREE_ID)
    )


def new_graph_node(
    tree: bpy.types.NodeTree, *, container: bool = False
) -> bpy.types.Node:
    return tree.nodes.new(CONTAINER_NODE_ID if container else GENERIC_NODE_ID)


def new_editor_node(
    tree: bpy.types.NodeTree,
    *,
    red_type: str,
    handle: str,
    label: str,
    color: typing.Sequence[float],
    output_kind: str = "",
    notes: str = "editor-only node",
) -> bpy.types.Node:
    """Create an editor-derived helper node that is excluded from export"""
    node = new_graph_node(tree)
    node.red_type = red_type
    node.red_handle_id = handle
    try:
        node.red_exportable = False
        node.red_pseudo = True
        node.red_metadata_known = False
        node.red_parent_class = ""
        node.red_output_kind = output_kind
        node.red_roundtrip_ready = True
        node.red_roundtrip_notes = notes
        node.red_layout_auto = True
    except Exception:
        _LOG.debug("Editor node annotation failed", exc_info=True)
    node.name = handle
    node.label = label
    node.use_custom_color = True
    try:
        node.color = color
    except Exception:
        _LOG.debug("Editor node color failed", exc_info=True)
    return node


def new_socket(
    node: bpy.types.Node, in_out: str, socket_type: str, name: str
) -> bpy.types.NodeSocket:
    collection = node.outputs if in_out == "OUTPUT" else node.inputs
    return collection.new(socket_type, name)


def ensure_socket(
    node: bpy.types.Node, in_out: str, name: str, socket_type: str
) -> bpy.types.NodeSocket:
    """Return an existing socket by name or create it on the node"""
    collection = node.outputs if in_out == "OUTPUT" else node.inputs
    existing = collection.get(name)
    if existing is not None:
        return existing
    return collection.new(socket_type, name)


def link_sockets(
    tree: bpy.types.NodeTree,
    from_socket: bpy.types.NodeSocket,
    to_socket: bpy.types.NodeSocket,
) -> bpy.types.NodeLink:
    return tree.links.new(from_socket, to_socket)


def has_link(
    tree: bpy.types.NodeTree,
    from_socket: bpy.types.NodeSocket,
    to_socket: bpy.types.NodeSocket,
) -> bool:
    return any(
        link.from_socket is from_socket and link.to_socket is to_socket
        for link in tree.links
    )
