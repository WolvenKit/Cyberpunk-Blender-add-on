import itertools

import bpy

from ...animation.animgraph.schema import rtti
from . import presenters
from .categories import NODE_CATEGORY_COLORS
from ...animation.animgraph_constants import ANIMGRAPH_TREE_ID, CONTAINER_OUTPUT_NAME, LINK_SOCKET
from .property_codec import add_node_property, clear_node_properties
from .sockets import bind_input_socket, bind_output_socket

_counter = itertools.count(1)


def new_handle_id():
    return f"new:{next(_counter)}"


def _unique_input_caption(node, base: str) -> str:
    name = base
    suffix = 2
    while node.inputs.get(name) is not None:
        name = f"{base} ({suffix})"
        suffix += 1
    return name


def _make_subtree(short: str):
    sub = bpy.data.node_groups.new(name=f"{short}", type=ANIMGRAPH_TREE_ID)
    sub.interface.new_socket(name=CONTAINER_OUTPUT_NAME, in_out='OUTPUT',
                             socket_type='REDengine_AnimGraphSocket_Pose')
    sub.nodes.new('NodeGroupOutput')
    return sub


def _seed_authored_properties(node, definition: rtti.NodeDefinition) -> None:
    clear_node_properties(node)
    for prop in definition.properties:
        add_node_property(
            node,
            prop.name,
            prop.default,
            json_path=prop.name,
            label=prop.label,
            editable=True,
            red_type_hint=prop.red_type,
        )


def build_node(tree, short: str, location=(0.0, 0.0)):
    definition = rtti.node_definition(short)
    hid = new_handle_id()

    if definition.is_container:
        node = tree.nodes.new('REDengine_AnimGraphContainer')
        node.node_tree = _make_subtree(definition.short_name)
        if node.node_tree is None:
            sock = node.outputs.new('REDengine_AnimGraphSocket_Pose', CONTAINER_OUTPUT_NAME)
            bind_output_socket(sock, owner_handle=hid, link_type='animPoseLink', edge_semantics='dataflow')
    else:
        node = tree.nodes.new('REDengine_AnimGraphNode_Generic')
        out_kind = definition.output_link_type
        if out_kind is not None:
            socket_bl, _ = LINK_SOCKET[out_kind]
            caption = "Out Pose" if out_kind == "animPoseLink" else "Out Value"
            sock = node.outputs.new(socket_bl, caption)
            bind_output_socket(sock, owner_handle=hid, link_type=out_kind, edge_semantics='dataflow')

    node.red_type = definition.red_type
    node.red_handle_id = hid
    try:
        node.red_exportable = True
        node.red_pseudo = False
        node.red_metadata_known = True
        node.red_parent_class = definition.parent_chain[-2] if len(definition.parent_chain) >= 2 else ''
        node.red_output_kind = definition.output_link_type or ""
        node.red_roundtrip_ready = True
        node.red_roundtrip_notes = "authored synthetic HandleId"
        node.red_layout_auto = True
        node.red_presenter = presenters.presenter_id_for(definition.red_type)
    except Exception:
        pass

    node.name = f"{definition.red_type}_{hid}"
    node.label = definition.short_name
    node.use_custom_color = True
    node.color = NODE_CATEGORY_COLORS[categories.node_category(definition.short_name)]
    node.location = location

    for field in definition.input_fields:
        socket_bl, _ = LINK_SOCKET[field.link_type]
        sock = node.inputs.new(socket_bl, _unique_input_caption(node, field.caption))
        bind_input_socket(
            sock,
            owner_handle=hid,
            json_path=field.json_path,
            link_type=field.link_type,
            edge_semantics='dataflow',
        )

    _seed_authored_properties(node, definition)
    presenters.seed_authored_node(node, definition)
    return node
