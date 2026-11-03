from ....animation.model.animgraph import aim_constraint
from ....animation.model.animgraph.source_channels import STATIC_VECTOR_TYPE
from ....blender.animgraph.access import indexed_node_property_map
from ...services.animgraph import validation
from .node_widgets import (
    bound_armature,
    draw_binding,
    draw_preview,
    draw_property,
    draw_transform_property,
    draw_validation,
)


def draw_node(node, context, layout):
    properties = indexed_node_property_map(node)
    column = layout.column(align=True)
    node_type = str(getattr(node, "red_type", "") or "")
    draw_binding(node, context, column)

    transforms = column.box()
    transforms.label(text="Transforms", icon="BONE_DATA")
    draw_transform_property(
        node, transforms, properties, "transformIndex", "Constrained"
    )
    draw_transform_property(node, transforms, properties, "targetTransform", "Target")
    if node_type == aim_constraint.RED_TYPE:
        transforms.prop(node, "red_aim_up_channel_type", text="Up Source")
        armature = bound_armature(node)
        up_type = str(getattr(node, "red_aim_up_channel_type", "") or "")
        if up_type in (
            aim_constraint.TRANSFORM_VECTOR_TYPE,
            aim_constraint.REFERENCE_TRANSFORM_VECTOR_TYPE,
            aim_constraint.ORIENTATION_VECTOR_TYPE,
        ):
            if (
                armature is not None
                and getattr(getattr(armature, "data", None), "bones", None) is not None
            ):
                transforms.prop_search(
                    node,
                    "red_aim_up_transform",
                    armature.data,
                    "bones",
                    text="Up Transform",
                )
            else:
                transforms.prop(node, "red_aim_up_transform", text="Up Transform")
        if up_type == aim_constraint.ORIENTATION_VECTOR_TYPE:
            if (
                armature is not None
                and getattr(getattr(armature, "data", None), "bones", None) is not None
            ):
                transforms.prop_search(
                    node,
                    "red_aim_up_anchor_transform",
                    armature.data,
                    "bones",
                    text="Up Anchor",
                )
            else:
                transforms.prop(node, "red_aim_up_anchor_transform", text="Up Anchor")
            transforms.prop(node, "red_aim_up_vector", text="Local Up")
        elif up_type == STATIC_VECTOR_TYPE:
            transforms.prop(node, "red_aim_up_vector", text="Model-Space Point")
    else:
        draw_transform_property(
            node, transforms, properties, "upTransform", "Up Transform"
        )
        if node_type == aim_constraint.OBJECT_ROTATION_UP_TYPE:
            draw_property(
                node, transforms, properties, "upTransformVector", "Up Vector"
            )

    axes = column.box()
    axes.label(text="Local Axes")
    draw_property(node, axes, properties, "forwardAxisLS", "Forward")
    draw_property(node, axes, properties, "upAxisLS", "Up")

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
        evaluate_operator="redengine.aim_constraint_preview",
        restore_operator="redengine.aim_constraint_clear_preview",
    )
    draw_validation(column, validation.node_validation(node))
