from __future__ import annotations

import bpy

from ....animation.domain.animgraph.curve_points import inserted_curve_point
from ....animation.model.animgraph import direct_conn
from ....blender.animgraph import builder, curve_mapping, sm_edit, variables
from ....blender.animgraph.access import edit_collection
from ....blender.animgraph.property_codec import (
    reset_curve_property_from_raw_json,
    sort_curve_points,
)
from ....blender.operator_results import OperationResult

DANGLE_NODE_TYPE = "Dangle"


def _init_point_input(item) -> None:
    item.weight = 1.0
    item.expanded = True


def _init_channel_entry(entry) -> None:
    entry.transform_channel = "PosX"
    entry.multiplier = 1.0


def _init_transform_output(output) -> None:
    output.expanded = True
    _init_channel_entry(output.channel_entries.add())


def _init_track_output(item) -> None:
    item.expanded = True
    item.multiplier = 1.0


_INITIALIZERS = {
    "red_point_constraint_inputs": _init_point_input,
    "red_simple_bounce_transform_outputs": _init_transform_output,
    "channel_entries": _init_channel_entry,
    "red_simple_bounce_track_outputs": _init_track_output,
}


def edit_node_list(
    owner, list_name: str, action: str, item_index: int
) -> OperationResult:
    """Add, remove or move an item of owner's list_name collection and follow it with the list index"""
    index_attr = f"{list_name}_index"
    index = item_index if item_index >= 0 else int(getattr(owner, index_attr))
    new_index = edit_collection(
        getattr(owner, list_name), index, action, initialize=_INITIALIZERS[list_name]
    )
    if new_index is not None:
        setattr(owner, index_attr, new_index)
    return OperationResult.finished()


def edit_bounce_channel_entries(
    node, output_index: int, action: str, item_index: int
) -> OperationResult:
    outputs = node.red_simple_bounce_transform_outputs
    if output_index < 0:
        output_index = int(node.red_simple_bounce_transform_outputs_index)
    if not outputs or output_index < 0 or output_index >= len(outputs):
        return OperationResult.cancelled()
    return edit_node_list(outputs[output_index], "channel_entries", action, item_index)


def set_direct_conn_channels(node, channel_group: str) -> OperationResult:
    properties = {
        str(getattr(item, "key", "") or ""): item
        for item in getattr(node, "red_properties", ()) or ()
    }
    if channel_group == "CLEAR":
        fields, enabled = direct_conn.CHANNEL_FIELDS, False
    elif channel_group == "ALL":
        fields, enabled = direct_conn.CHANNEL_FIELDS, True
    else:
        fields, enabled = dict(direct_conn.CHANNEL_GROUPS)[channel_group.lower()], True
    for field in fields:
        item = properties.get(field)
        if item is not None:
            item.bool_value = enabled
    return OperationResult.finished()


def _select_only(tree, node) -> None:
    for other in tree.nodes:
        other.select = False
    node.select = True
    tree.nodes.active = node


def _dangle_rig(tree):
    root = variables.root_tree_for(tree) or tree
    rig = getattr(root, "red_bound_armature", None)
    if rig is None:
        rig_name = str(root.get("cp77_dangle_rig", "") or "")
        rig = bpy.data.objects.get(rig_name) if rig_name else None
    if rig is None or not str(
        getattr(rig.dangle_state, "animgraph_source_text", "") or ""
    ):
        return None
    return rig


def add_node(tree, node_type: str, location) -> OperationResult:
    """Add a node of node_type at location and make it the only selected, active node"""
    if node_type == DANGLE_NODE_TYPE and _dangle_rig(tree) is not None:
        return OperationResult.cancelled(
            "New Dangle creation is unavailable until pose-chain insertion is supported."
        )
    node = builder.build_node(tree, node_type, location=location)
    warnings = ()
    try:
        # A new state machine gets Entry, Any State and a default State; a
        # State added inside a state machine becomes one of its states.
        sm_edit.on_node_added(node)
    except ValueError as exc:
        warnings = (str(exc),)
    _select_only(tree, node)
    return OperationResult(True, warnings=warnings)


def add_curve_point(item) -> OperationResult:
    points = [(float(point.point), float(point.value)) for point in item.curve_points]
    x, y = inserted_curve_point(points, int(item.curve_points_index))
    point = item.curve_points.add()
    point.point = x
    point.value = y
    item.curve_points_index = len(item.curve_points) - 1
    return OperationResult.finished()


def remove_curve_point(item) -> OperationResult:
    if not item.curve_points:
        return OperationResult.cancelled()
    index = max(0, min(item.curve_points_index, len(item.curve_points) - 1))
    item.curve_points.remove(index)
    item.curve_points_index = min(index, max(0, len(item.curve_points) - 1))
    return OperationResult.finished()


def move_curve_point(item, direction: str) -> OperationResult:
    if len(item.curve_points) < 2:
        return OperationResult.cancelled()
    index = max(0, min(item.curve_points_index, len(item.curve_points) - 1))
    new_index = index - 1 if direction == "UP" else index + 1
    if new_index < 0 or new_index >= len(item.curve_points):
        return OperationResult.cancelled()
    item.curve_points.move(index, new_index)
    item.curve_points_index = new_index
    return OperationResult.finished()


def sort_curve(item) -> OperationResult:
    sort_curve_points(item)
    return OperationResult.finished()


def reset_curve(item) -> OperationResult:
    if not reset_curve_property_from_raw_json(item):
        return OperationResult.cancelled(
            "The stored raw JSON is not a curveData payload", "WARNING"
        )
    return OperationResult.finished()


def push_curve_widget(node, item, *, failure: str) -> OperationResult:
    """Create or update the native curve widget from the REDengine curve points"""
    helper = curve_mapping.get_helper_node(node, item, create=True)
    if helper is None or not curve_mapping.sync_native_from_property(item, helper):
        return OperationResult.cancelled(failure, "WARNING")
    return OperationResult.finished()


def apply_curve_widget(node, item) -> OperationResult:
    helper = curve_mapping.get_helper_node(node, item, create=False)
    if helper is None or not curve_mapping.sync_property_from_native(item, helper):
        return OperationResult.cancelled(
            "Could not read the native Blender curve widget", "WARNING"
        )
    return OperationResult.finished()
