from ....animation.model.animgraph import direct_conn
from ....blender.animgraph.access import indexed_node_property_map
from .node_widgets import (
    draw_binding,
    draw_preview,
    draw_property,
    draw_transform_property,
)


def draw_node(node, context, layout):
    properties = indexed_node_property_map(node)
    column = layout.column(align=True)
    draw_binding(node, context, column)

    transform_box = column.box()
    transform_box.label(text="Transforms", icon="BONE_DATA")
    draw_transform_property(
        node, transform_box, properties, "sourceTransformIndex", "Source"
    )
    draw_transform_property(node, transform_box, properties, "transformIndex", "Target")

    channel_box = column.box()
    channel_box.label(text="Channels")
    buttons = channel_box.row(align=True)
    for group, text in (
        ("POSITION", "Pos"),
        ("ROTATION", "Rot"),
        ("SCALE", "Scale"),
        ("ALL", "All"),
        ("CLEAR", "Clear"),
    ):
        op = buttons.operator("redengine.direct_conn_channels", text=text)
        op.channel_group = group
    header = channel_box.row(align=True)
    header.label(text="")
    for axis in "XYZ":
        header.label(text=axis)
    for group_name, fields in direct_conn.CHANNEL_GROUPS:
        row = channel_box.row(align=True)
        row.label(text=group_name.title())
        for field in fields:
            entry = properties.get(field)
            if entry is None:
                row.label(text="!")
            else:
                row.prop(entry[1], "bool_value", text="")

    weight_box = column.box()
    weight_box.label(text="Weight")
    draw_property(node, weight_box, properties, "weight", "Static Weight")

    draw_preview(
        node,
        column,
        evaluate_operator="redengine.direct_conn_preview",
        restore_operator="redengine.direct_conn_clear_preview",
    )

    enabled = [
        field
        for field in direct_conn.CHANNEL_FIELDS
        if properties.get(field) is not None
        and bool(getattr(properties[field][1], "bool_value", False))
    ]
    if not enabled:
        column.label(text="No channels enabled", icon="ERROR")
