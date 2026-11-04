import bpy

from ..model.additive import ActionListSlot
from ..services.actions import action_counts


def _draw_layer_header(layout, props, *, secondary: bool):
    if secondary:
        weight_prop = "secondary_weight"
        mask_prop = "secondary_mask"
        label = "Second Additive"
    else:
        weight_prop = "weight"
        mask_prop = "mask"
        label = "Additive Animations"

    row = layout.row(align=True)
    split = row.split(factor=0.72, align=True)
    left = split.row(align=True)
    left.label(text=label)
    op = left.operator("cp77.new_action", icon="ADD", text="")
    op.additive = True
    right = split.row(align=True)
    right.scale_x = 0.72
    right.prop(props, weight_prop, text="", slider=True)

    row = layout.row(align=True)
    row.prop(props, mask_prop, text="Mask")
    if not secondary:
        row.prop(props, "storage_mode", text="", expand=True)


def _draw_timing(layout, props, *, secondary: bool):
    prefix = "secondary_" if secondary else ""
    row = layout.row(align=True)
    row.prop(props, f"{prefix}time_scale", text="Speed")
    row.prop(props, f"{prefix}time_offset", text="Offset (s)")
    row.prop(props, f"{prefix}loop", text="Loop", toggle=True)


def _draw_additive_list(layout, props, slot: ActionListSlot, additive_count: int):
    if additive_count:
        layout.template_list(
            "CP77_UL_AdditiveAnimList",
            slot.name,
            bpy.data,
            "actions",
            props,
            slot.selector,
            rows=min(5, additive_count),
        )
    else:
        layout.label(text="No additive animations loaded", icon="INFO")


def draw_additive(context, layout):
    props = context.scene.cp77_additive_preview
    normal_count, additive_count = action_counts()

    row = layout.row(align=True)
    row.label(text="Base")
    op = row.operator("cp77.new_action", icon="ADD", text="")
    op.additive = False
    if normal_count:
        layout.template_list(
            "CP77_UL_AnimList",
            "NORMAL",
            bpy.data,
            "actions",
            props,
            ActionListSlot.NORMAL.selector,
            rows=min(5, normal_count),
        )
    else:
        layout.label(text="No normal animations loaded", icon="INFO")

    layout.separator()
    _draw_layer_header(layout, props, secondary=False)
    _draw_additive_list(layout, props, ActionListSlot.PRIMARY, additive_count)
    _draw_timing(layout, props, secondary=False)

    layout.separator()
    layout.prop(props, "secondary_enabled", text="Second Additive")
    if props.secondary_enabled:
        _draw_layer_header(layout, props, secondary=True)
        _draw_additive_list(layout, props, ActionListSlot.SECONDARY, additive_count)
        _draw_timing(layout, props, secondary=True)
