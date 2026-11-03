from ....blender.animgraph import rig_binding
from ....blender.animgraph.property_ui import draw_property_row


def bound_armature(node):
    return rig_binding.bound_armature(getattr(node, "id_data", None))


def draw_property(node, layout, properties, key, label=None):
    entry = properties.get(key)
    if entry is None:
        layout.label(text=f"Missing property: {key}", icon="ERROR")
        return
    index, item = entry
    draw_property_row(node, layout, item, index, label_override=label)


def draw_transform_property(node, layout, properties, key, label):
    entry = properties.get(key)
    if entry is None:
        layout.label(text=f"Missing property: {key}", icon="ERROR")
        return
    _index, item = entry
    draw_bone_property(node, layout, item, "string_value", label)


def draw_bone_property(node, layout, item, attribute, label):
    armature = bound_armature(node)
    bones = (
        getattr(getattr(armature, "data", None), "bones", None)
        if armature is not None
        else None
    )
    if bones is not None:
        layout.prop_search(item, attribute, armature.data, "bones", text=label)
    else:
        layout.prop(item, attribute, text=label)


def draw_binding_box(layout, owner, context, *, armature):
    box = layout.box()
    box.label(text="Runtime Binding", icon="ARMATURE_DATA")
    box.prop(owner, "red_bound_armature", text="Armature")
    row = box.row(align=True)
    active = getattr(context, "active_object", None)
    bind_row = row.row(align=True)
    bind_row.enabled = active is not None and getattr(active, "type", "") == "ARMATURE"
    bind_row.operator("redengine.animgraph_bind_active_armature", text="Bind Active")
    row.operator("redengine.animgraph_clear_armature_binding", text="Clear")
    if armature is None:
        box.label(text="Bind an armature to preview", icon="INFO")


def draw_binding(node, context, layout):
    owner = rig_binding.binding_tree(getattr(node, "id_data", None))
    draw_binding_box(layout, owner, context, armature=bound_armature(node))


def draw_validation(layout, result) -> None:
    """A Validation box with the blocking issues and warnings, when there are any"""
    if not result.blocking and not result.warnings:
        return
    box = layout.box()
    box.label(text="Validation")
    for message in result.blocking:
        box.label(text=message, icon="ERROR")
    for message in result.warnings:
        box.label(text=message, icon="INFO")


def draw_preview(node, layout, *, evaluate_operator: str, restore_operator: str):
    box = layout.box()
    box.label(text="Runtime Preview", icon="PLAY")
    row = box.row(align=True)
    row.enabled = bound_armature(node) is not None
    row.operator(evaluate_operator, text="Evaluate Chain", icon="PLAY")
    row.operator(restore_operator, text="Restore Pose", icon="LOOP_BACK")
