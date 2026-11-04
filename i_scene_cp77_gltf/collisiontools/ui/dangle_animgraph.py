from ...blender.animgraph import presenters
from ...blender.animgraph.property_codec import property_by_key
from ...blender.animgraph.property_ui import (
    draw_property_row,
    draw_scalar_target,
)


def draw_dangle_particle_node(owner, layout):
    col = layout.column(align=True)
    bone = owner.get("red_dangle_bone", "") if hasattr(owner, "get") else ""

    head = col.box()
    head.label(text="Dangle Particle", icon="PARTICLE_POINT")
    if bone:
        head.label(text=bone, icon="BONE_DATA")

    sim_keys = ("isFree", "mass", "damping", "pullForceFactor", "projectionType")
    cap_keys = (
        "collisionCapsuleRadius",
        "collisionCapsuleHeightExtent",
        "collisionCapsuleAxisLS",
    )
    debug_keys = ("isDebugEnabled",)
    shown = {"bone", "strand", "strandIndex", "sourceIndex"}

    sim_box = col.box()
    sim_box.label(text="Simulation", icon="PHYSICS")
    for key in sim_keys:
        item = property_by_key(owner, key)
        if item is not None:
            draw_scalar_target(item, sim_box, item.label or item.key)
            shown.add(key)

    cap_items = [
        item for key in cap_keys if (item := property_by_key(owner, key)) is not None
    ]
    if cap_items:
        cap_box = col.box()
        cap_box.label(text="Collision Capsule", icon="MESH_CAPSULE")
        for item in cap_items:
            draw_scalar_target(item, cap_box, item.label or item.key)
            shown.add(item.key)

    dbg_items = [
        item for key in debug_keys if (item := property_by_key(owner, key)) is not None
    ]
    if dbg_items:
        dbg_box = col.box()
        dbg_box.label(text="Debug", icon="TOOL_SETTINGS")
        for item in dbg_items:
            draw_scalar_target(item, dbg_box, item.label or item.key)
            shown.add(item.key)

    props = getattr(owner, "red_properties", None)
    other = [item for item in props or [] if item.key not in shown]
    if other:
        other_box = col.box()
        other_box.label(text="Other Particle Fields", icon="PROPERTIES")
        for item in other:
            draw_property_row(owner, other_box, item, -1)


def draw_dangle_cone_constraint_node(owner, layout):
    col = layout.column(align=True)
    bone_a = owner.get("red_constraint_bone_a", "") if hasattr(owner, "get") else ""
    bone_b = owner.get("red_constraint_bone_b", "") if hasattr(owner, "get") else ""

    head = col.box()
    head.label(text="Dangle Cone Constraint", icon="MESH_CONE")
    row = head.row(align=True)
    row.label(text=f"Attachment: {bone_a or '-'}")
    row.label(text=f"Constrained: {bone_b or '-'}")

    shown = {"constraintHandle", "sourceIndex", "attachmentBone", "constrainedBone"}
    geometry_keys = (
        "constraintType",
        "halfOfMaxApertureAngle",
        "projectionType",
        "coneTransformLS",
        "collisionCapsuleRadius",
        "collisionCapsuleHeightExtent",
    )
    debug_keys = ("isDebugEnabled",)

    geom_items = [
        item
        for key in geometry_keys
        if (item := property_by_key(owner, key)) is not None
    ]
    if geom_items:
        geom_box = col.box()
        geom_box.label(text="Cone Parameters", icon="MESH_CONE")
        for item in geom_items:
            draw_property_row(owner, geom_box, item, -1)
            shown.add(item.key)

    dbg_items = [
        item for key in debug_keys if (item := property_by_key(owner, key)) is not None
    ]
    if dbg_items:
        dbg_box = col.box()
        dbg_box.label(text="Debug", icon="TOOL_SETTINGS")
        for item in dbg_items:
            draw_scalar_target(item, dbg_box, item.label or item.key)
            shown.add(item.key)

    props = getattr(owner, "red_properties", None)
    other = [item for item in props or [] if item.key not in shown]
    if other:
        other_box = col.box()
        other_box.label(text="Other Constraint Fields", icon="PROPERTIES")
        for item in other:
            draw_property_row(owner, other_box, item, -1)


def draw_dangle_node(node, context, layout):
    presenter_id = presenters.node_presenter_id(node)
    if presenter_id == presenters.PRESENTER_DANGLE_PARTICLE:
        draw_dangle_particle_node(node, layout)
        return
    if presenter_id == presenters.PRESENTER_DANGLE_CONE:
        draw_dangle_cone_constraint_node(node, layout)
