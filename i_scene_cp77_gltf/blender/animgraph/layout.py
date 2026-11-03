import typing

import bpy

from ...animation.model.animgraph.constants import ANIM_NODE_PREFIX
from ...bartmoss.graph_layout import LayoutItem, layout_graph
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

_STRUCTURAL_TOKENS = (
    "statefrozen",
    "animanimnode_state",
    "animanimnode_output",
    "animanimnode_root",
    "editordangle",
    "editorrounded",
)
_BRANCH_EXEMPT_TOKENS = (
    "statefrozen",
    "animanimnode_state",
    "animanimnode_output",
    "animanimnode_root",
)


def _node_property_count(node: bpy.types.Node) -> int:
    props = getattr(node, "red_properties", None)
    if props is None:
        return 0
    try:
        # A curve widget takes about three property rows.
        return sum(
            3 if getattr(prop, "value_kind", "") == "CURVE_FLOAT" else 1
            for prop in props
        )
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
            ("_node_property_count", type(error).__name__),
            "node property count: fell back after %s",
            error,
            exc_info=True,
        )
        return 0


def estimated_node_size(node: bpy.types.Node) -> tuple[float, float]:
    """Estimate a node's drawn rectangle for import-time layout"""
    sockets = len(node.inputs) + len(node.outputs)
    prop_rows = _node_property_count(node)
    label = getattr(node, "label", "") or getattr(node, "name", "") or ""
    red_type = getattr(node, "red_type", "") or getattr(node, "bl_idname", "") or ""
    short = (
        red_type.replace(ANIM_NODE_PREFIX, "")
        .replace("editorPseudo_", "")
        .replace("editor", "")
    )

    min_width = 240.0
    if node.bl_idname == "REDengine_AnimGraphContainer":
        min_width = 300.0
    if short in {"State", "StateFrozen", "StateMachine", "LocomotionMachine"}:
        min_width = 300.0

    width = max(min_width, 10.0 * len(label) + 96.0, _transition_row_width(node))
    height = 76.0 + 26.0 * max(1, sockets)
    if prop_rows:
        height += 46.0 + 28.0 * prop_rows
    return width, height


def _transition_row_width(node: bpy.types.Node) -> float:
    """Width that fits the node's widest transition row button"""
    records = getattr(node, "red_transitions", None)
    if not records:
        return 0.0
    try:
        from .sm_sockets import is_state_machine, row_text

        if is_state_machine(node):
            return 0.0  # its rows are shown in the sidebar only
        longest = max(len(row_text(node, index)[0]) for index in range(len(records)))
    except (
        AttributeError,
        IndexError,
        KeyError,
        ReferenceError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_transition_row_width", type(error).__name__),
            "transition row width: fell back after %s",
            error,
            exc_info=True,
        )
        return 0.0
    return 7.0 * longest + 60.0


def _layout_item(node: bpy.types.Node) -> LayoutItem:
    red_type = getattr(node, "red_type", "") or ""
    lowered = red_type.lower()
    identity = lowered + " " + (getattr(node, "bl_idname", "") or "").lower()
    width, height = estimated_node_size(node)
    return LayoutItem(
        node.name,
        getattr(node, "label", "") or "",
        width,
        height,
        structural=any(token in identity for token in _STRUCTURAL_TOKENS),
        branch_exempt=(
            red_type.startswith("editorDangle")
            or red_type.startswith("editorRounded")
            or any(token in lowered for token in _BRANCH_EXEMPT_TOKENS)
        ),
        x=float(node.location.x),
        y=float(node.location.y),
    )


def layout_node_tree(
    tree: bpy.types.NodeTree,
    edges: typing.Iterable[tuple[bpy.types.Node, bpy.types.Node]],
    x_gap: float = 240.0,
    y_gap: float = 170.0,
    component_gap: float = 300.0,
) -> int:
    """Lay out one tree and return the number of overlapping node pairs left"""
    nodes = list(tree.nodes)
    if not nodes:
        return 0
    items = [_layout_item(node) for node in nodes]
    item_of = dict(zip(nodes, items))
    item_edges = [
        (item_of[a], item_of[b]) for a, b in edges if a in item_of and b in item_of
    ]
    overlaps = layout_graph(
        items, item_edges, x_gap=x_gap, y_gap=y_gap, component_gap=component_gap
    )
    tree.nodes.foreach_set("location", [v for item in items for v in (item.x, item.y)])
    tree.nodes.foreach_set(
        "width",
        [max(float(node.width), item.width) for node, item in zip(nodes, items)],
    )
    return overlaps
