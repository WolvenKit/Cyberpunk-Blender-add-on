from ....blender.animgraph.access import indexed_node_property_map
from ...services.animgraph import validation
from .node_widgets import (
    draw_binding,
    draw_bone_property,
    draw_preview,
    draw_property,
    draw_transform_property,
    draw_validation,
)


def _operator(
    row, operator, action, *, output_index=None, item_index=None, icon="NONE"
):
    op = row.operator(operator, text="", icon=icon)
    op.action = action
    if output_index is not None:
        op.transform_output_index = output_index
    if item_index is not None:
        op.item_index = item_index
    return op


def _draw_transform_outputs(node, layout):
    box = layout.box()
    box.label(text="Transform Outputs", icon="BONE_DATA")
    outputs = node.red_simple_bounce_transform_outputs
    for output_index, output in enumerate(outputs):
        item_box = box.box()
        header = item_box.row(align=True)
        header.prop(
            output,
            "expanded",
            text="",
            emboss=False,
            icon="TRIA_DOWN" if output.expanded else "TRIA_RIGHT",
        )
        header.label(text=output.target_transform or f"Output {output_index + 1}")
        _operator(
            header,
            "redengine.simple_bounce_transform_output",
            "UP",
            item_index=output_index,
            icon="TRIA_UP",
        )
        _operator(
            header,
            "redengine.simple_bounce_transform_output",
            "DOWN",
            item_index=output_index,
            icon="TRIA_DOWN",
        )
        _operator(
            header,
            "redengine.simple_bounce_transform_output",
            "REMOVE",
            item_index=output_index,
            icon="X",
        )
        if not output.expanded:
            continue
        draw_bone_property(node, item_box, output, "target_transform", "Target")
        draw_bone_property(
            node, item_box, output, "parent_transform", "Parent Override"
        )
        channels = item_box.box()
        channels.label(text="Ordered Channel Entries")
        for entry_index, entry in enumerate(output.channel_entries):
            row = channels.row(align=True)
            row.prop(entry, "transform_channel", text="")
            row.prop(entry, "multiplier", text="Multiplier")
            sub = row.row(align=True)
            _operator(
                sub,
                "redengine.simple_bounce_channel_entry",
                "UP",
                output_index=output_index,
                item_index=entry_index,
                icon="TRIA_UP",
            )
            _operator(
                sub,
                "redengine.simple_bounce_channel_entry",
                "DOWN",
                output_index=output_index,
                item_index=entry_index,
                icon="TRIA_DOWN",
            )
            remove = _operator(
                sub,
                "redengine.simple_bounce_channel_entry",
                "REMOVE",
                output_index=output_index,
                item_index=entry_index,
                icon="X",
            )
            remove.transform_output_index = output_index
        add = channels.operator(
            "redengine.simple_bounce_channel_entry", text="Add Channel", icon="ADD"
        )
        add.action = "ADD"
        add.transform_output_index = output_index
    add = box.operator(
        "redengine.simple_bounce_transform_output",
        text="Add Transform Output",
        icon="ADD",
    )
    add.action = "ADD"


def _draw_track_outputs(node, layout):
    box = layout.box()
    box.label(text="Track Outputs", icon="DRIVER")
    for index, output in enumerate(node.red_simple_bounce_track_outputs):
        row = box.row(align=True)
        row.prop(output, "target_track", text=f"Track {index + 1}")
        row.prop(output, "multiplier", text="Multiplier")
        _operator(
            row,
            "redengine.simple_bounce_track_output",
            "UP",
            item_index=index,
            icon="TRIA_UP",
        )
        _operator(
            row,
            "redengine.simple_bounce_track_output",
            "DOWN",
            item_index=index,
            icon="TRIA_DOWN",
        )
        _operator(
            row,
            "redengine.simple_bounce_track_output",
            "REMOVE",
            item_index=index,
            icon="X",
        )
    add = box.operator(
        "redengine.simple_bounce_track_output", text="Add Track Output", icon="ADD"
    )
    add.action = "ADD"


def draw_node(node, context, layout):
    properties = indexed_node_property_map(node)
    column = layout.column(align=True)
    draw_binding(node, context, column)

    input_box = column.box()
    input_box.label(text="Driver Transforms", icon="EMPTY_AXIS")
    draw_transform_property(node, input_box, properties, "startTransform", "Start")
    draw_transform_property(node, input_box, properties, "endTransform", "End")

    params = column.box()
    params.label(text="Driver Parameters")
    for key, label in (
        ("multiplier", "Positive Multiplier"),
        ("negativeMultiplier", "Negative Multiplier"),
        ("delay", "Delay"),
        ("smoothStep", "Smooth Region"),
        ("offset", "Offset"),
    ):
        draw_property(node, params, properties, key, label)

    _draw_transform_outputs(node, column)
    _draw_track_outputs(node, column)

    driver_box = column.box()
    driver_box.label(text="Raw Driver Output", icon="DRIVER")
    draw_property(node, driver_box, properties, "outputDriverTrack", "Track")

    draw_preview(
        node,
        column,
        evaluate_operator="redengine.simple_bounce_preview",
        restore_operator="redengine.simple_bounce_clear_preview",
    )
    draw_validation(column, validation.node_validation(node))
