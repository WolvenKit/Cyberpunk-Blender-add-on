import uuid

from ...animation.model.animgraph.constants import CONTAINER_OUTPUT_NAME, LINK_SOCKET
from ...animation.model.animgraph.schema import rtti
from ...core.log import get_logger, log_once
from . import categories, presenters, sm_records
from .categories import NODE_CATEGORY_COLORS
from .property_codec import add_node_property, clear_node_properties
from .sockets import bind_input_socket, bind_red_socket
from .tree_ops import ensure_socket, new_graph_node, new_graph_tree, new_socket

_LOG = get_logger(__name__)


def new_handle_id():
    """Placeholder id unique across sessions"""
    return f"new:{uuid.uuid4().hex}"


def _unique_input_caption(node, base: str) -> str:
    name = base
    suffix = 2
    while node.inputs.get(name) is not None:
        name = f"{base} ({suffix})"
        suffix += 1
    return name


# State machines hold their states in ``states`` rather than ``nodes``, so the
# metadata does not count them as containers; the editor keeps them in a subtree.
_STATE_MACHINE_SHORTS = frozenset({"StateMachine", "LocomotionMachine"})


def _root_name(tree) -> str:
    """Name of the root graph tree belongs to (the tree itself for a root)"""
    parent = str(tree.get("red_parent_graph", "") or "") if tree is not None else ""
    return parent or str(getattr(tree, "name", "") or "")


def _make_subtree(short: str, parent_tree=None):
    sub = new_graph_tree(f"{short}")
    sub.interface.new_socket(
        name=CONTAINER_OUTPUT_NAME,
        in_out="OUTPUT",
        socket_type="REDengine_AnimGraphSocket_Pose",
    )
    sub.nodes.new("NodeGroupOutput")
    root_name = _root_name(parent_tree)
    if root_name:
        # Same linkage as imported subtrees, so root lookups work from inside.
        sub["red_internal_subgraph"] = True
        sub["red_parent_graph"] = root_name
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

    if definition.is_container or definition.short_name in _STATE_MACHINE_SHORTS:
        node = new_graph_node(tree, container=True)
        node.node_tree = _make_subtree(definition.short_name, tree)
        # Like the importer: the container's pose output is its own bound socket.
        sock = ensure_socket(
            node, "OUTPUT", CONTAINER_OUTPUT_NAME, "REDengine_AnimGraphSocket_Pose"
        )
        bind_red_socket(
            sock,
            role="output",
            owner_handle=hid,
            link_type="animPoseLink",
            exportable=True,
            edge_semantics="dataflow",
            source_handle=hid,
            pseudo=False,
        )
    else:
        node = new_graph_node(tree)
        out_kind = definition.output_link_type
        if out_kind is not None:
            socket_bl, _ = LINK_SOCKET[out_kind]
            caption = "Out Pose" if out_kind == "animPoseLink" else "Out Value"
            sock = new_socket(node, "OUTPUT", socket_bl, caption)
            bind_red_socket(
                sock,
                role="output",
                owner_handle=hid,
                link_type=out_kind,
                exportable=True,
                edge_semantics="dataflow",
                source_handle=hid,
                pseudo=False,
            )

    node.red_type = definition.red_type
    node.red_handle_id = hid
    sm_records.bump_graph_generation()  # the container may just have become a state machine
    try:
        node.red_exportable = True
        node.red_pseudo = False
        node.red_metadata_known = True
        node.red_parent_class = (
            definition.parent_chain[-2] if len(definition.parent_chain) >= 2 else ""
        )
        node.red_output_kind = definition.output_link_type or ""
        node.red_roundtrip_ready = True
        node.red_roundtrip_notes = "authored synthetic HandleId"
        node.red_layout_auto = True
        node.red_presenter = presenters.presenter_id_for(definition.red_type)
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("build_node", type(error).__name__),
            "build node: fell back after %s",
            error,
            exc_info=True,
        )

    node.name = f"{definition.red_type}_{hid}"
    node.label = definition.short_name
    node.use_custom_color = True
    node.color = NODE_CATEGORY_COLORS[categories.node_category(definition.short_name)]
    node.location = location

    for field in definition.input_fields:
        socket_bl, _ = LINK_SOCKET[field.link_type]
        sock = new_socket(
            node, "INPUT", socket_bl, _unique_input_caption(node, field.caption)
        )
        bind_input_socket(
            sock,
            owner_handle=hid,
            json_path=field.json_path,
            link_type=field.link_type,
            edge_semantics="dataflow",
        )

    _seed_authored_properties(node, definition)
    presenters.seed_authored_node(node, definition)
    return node
