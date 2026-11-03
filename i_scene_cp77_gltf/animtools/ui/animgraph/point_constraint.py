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


def _draw_inputs(node, layout):
    box = layout.box()
    box.label(text="Weighted Input Transforms", icon="BONE_DATA")
    inputs = node.red_point_constraint_inputs
    for index, item in enumerate(inputs):
        panel = box.box()
        header = panel.row(align=True)
        header.prop(
            item,
            "expanded",
            text="",
            emboss=False,
            icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT",
        )
        header.label(text=f"Input {index + 1}: {item.transform or '<unset>'}")
        for action, icon in (("UP", "TRIA_UP"), ("DOWN", "TRIA_DOWN"), ("REMOVE", "X")):
            op = header.operator("redengine.point_constraint_input", text="", icon=icon)
            op.action = action
            op.item_index = index
        if item.expanded:
            draw_bone_property(node, panel, item, "transform", "Transform")
            panel.prop(item, "weight", text="Weight")
    add = box.operator("redengine.point_constraint_input", text="Add Input", icon="ADD")
    add.action = "ADD"


def draw_node(node, context, layout):
    properties = indexed_node_property_map(node)
    column = layout.column(align=True)
    draw_binding(node, context, column)

    target_box = column.box()
    target_box.label(text="Constrained Transform", icon="BONE_DATA")
    draw_transform_property(node, target_box, properties, "transformIndex", "Target")

    _draw_inputs(node, column)

    weight_box = column.box()
    weight_box.label(text="Constraint Weight")
    draw_property(node, weight_box, properties, "weightMode", "Mode")
    mode = "Static"
    entry = properties.get("weightMode")
    if entry is not None:
        mode = str(
            getattr(entry[1], "string_value", "")
            or getattr(entry[1], "enum_choice", "")
            or "Static"
        )
    if mode == "FloatTrack":
        draw_property(node, weight_box, properties, "weightFloatTrack", "Track")
    else:
        draw_property(node, weight_box, properties, "weight", "Static Weight")

    draw_preview(
        node,
        column,
        evaluate_operator="redengine.point_constraint_preview",
        restore_operator="redengine.point_constraint_clear_preview",
    )
    draw_validation(column, validation.node_validation(node))
