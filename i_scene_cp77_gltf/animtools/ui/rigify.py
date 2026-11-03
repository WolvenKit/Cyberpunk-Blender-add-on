from __future__ import annotations

from ...animation.domain.rigify.controls import (
    LIMBS,
    TORSO_SELECTION,
    limb_descriptor,
    limb_fk_bones,
    limb_selection,
)
from ...animation.domain.rigify.mapping import get_rigify_coll_prop
from ...blender.animation_context import active_armature
from ...core.log import get_logger, log_once
from ..blender.rigify.forward import forward_sync_enabled
from ..blender.rigify.pairing import find_pair, rig_id, rig_ui_operator

_LOG = get_logger(__name__)


def _draw_live_sync(layout, source, rig) -> None:
    row = layout.row(align=True)
    row.scale_y = 1.15
    following = forward_sync_enabled(source)
    op = row.operator(
        "cp77.set_rigify_live_sync",
        text="Cyberpunk Follows Rigify" if following else "Cyberpunk Plays Own Action",
        icon="LINKED" if following else "UNLINKED",
        depress=following,
    )
    op.enabled = not following
    op.source_name = source.name
    op.rigify_name = rig.name


def _draw_active_switcher(layout, context, source, rig) -> None:
    obj = active_armature(context)
    row = layout.row(align=True)
    if obj is not rig:
        op = row.operator(
            "cp77.activate_linked_rig",
            text=f"Activate Rigify Rig '{rig.name}'",
            icon="ARMATURE_DATA",
        )
        op.target_name = rig.name
    if obj is not source:
        op = row.operator(
            "cp77.activate_linked_rig",
            text=f"Activate Source '{source.name}'",
            icon="OUTLINER_OB_ARMATURE",
        )
        op.target_name = source.name


def _draw_collections(layout, rig) -> None:
    arm = rig.data
    cols = list(getattr(arm, "collections", []) or [])
    if not cols:
        return
    header, panel = layout.panel("cp77_rigify_collections", default_closed=False)
    header.label(text="Bone Collections")
    if not panel:
        return

    rows: dict[int, list] = {}
    for c in cols:
        row_id = get_rigify_coll_prop(c, "rigify_ui_row", 0)
        if row_id > 0:
            rows.setdefault(row_id, []).append(c)
    if not rows:
        rows = {1: cols}

    for row_id in sorted(rows):
        r = panel.row(align=True)
        for c in rows[row_id]:
            title = get_rigify_coll_prop(c, "rigify_ui_title", "") or c.name
            sub = r.row(align=True)
            sub.active = getattr(c, "is_visible_ancestors", True)
            sub.prop(c, "is_visible", toggle=True, text=title, translate=False)


def _draw_limb_block(
    layout,
    rig,
    rig_identifier: str,
    label: str,
    side: str,
    *,
    is_leg: bool,
    selected_names: set,
) -> None:
    if not (selected_names & limb_selection(side, is_leg=is_leg)):
        return

    desc = limb_descriptor(side, is_leg=is_leg)
    prop_bone_name = desc["prop_bone"]
    prop_bone = rig.pose.bones.get(prop_bone_name)
    if prop_bone is None:
        return

    header, panel = layout.panel(
        f"cp77_rigify_limb_{label.replace(' ', '_')}", default_closed=False
    )
    header.label(text=label, icon="CON_KINEMATIC")
    if not panel:
        return

    if "FK_limb_follow" in prop_bone:
        panel.prop(prop_bone, '["FK_limb_follow"]', text="FK Limb Follow", slider=True)
    if "IK_FK" in prop_bone:
        panel.prop(prop_bone, '["IK_FK"]', text="IK-FK", slider=True)
    if "IK_Stretch" in prop_bone:
        panel.prop(prop_bone, '["IK_Stretch"]', text="IK Stretch", slider=True)

    snap_generic = rig_ui_operator(rig_identifier, "generic_snap")
    snap_ik2fk = rig_ui_operator(rig_identifier, "limb_ik2fk")
    leg_roll = rig_ui_operator(rig_identifier, "leg_roll_ik2fk") if is_leg else None
    toggle_pole = rig_ui_operator(rig_identifier, "limb_toggle_pole")

    if snap_generic is not None:
        op = panel.operator(snap_generic, text="FK → IK", icon="SNAP_ON")
        op.output_bones = limb_fk_bones(side, is_leg=is_leg)
        op.input_bones = desc["ik_bones"]
        op.ctrl_bones = desc["ctrl_bones"]

    if snap_ik2fk is not None:
        op = panel.operator(snap_ik2fk, text="IK → FK", icon="SNAP_ON")
        for key, value in desc.items():
            setattr(op, key, value)

    if is_leg and leg_roll is not None:
        op = panel.operator(leg_roll, text="IK → FK with Roll", icon="SNAP_ON")
        for key, value in desc.items():
            setattr(op, key, value)
        op.heel_control = f"foot_heel_ik.{side}"

    if toggle_pole is not None and "pole_vector" in prop_bone:
        row = panel.row(align=True)
        op = row.operator(toggle_pole, text="", icon="FORCE_MAGNETIC")
        op.prop_bone = desc["prop_bone"]
        op.ik_bones = desc["ik_bones"]
        op.ctrl_bones = desc["ctrl_bones"]
        op.extra_ctrls = desc["extra_ctrls"]
        row.prop(
            prop_bone,
            '["pole_vector"]',
            text="Pole On" if prop_bone["pole_vector"] else "Pole Off",
            toggle=True,
        )


def _draw_torso_block(layout, rig, selected_names: set) -> None:
    torso = rig.pose.bones.get("torso")
    head = rig.pose.bones.get("head")
    if not (selected_names & TORSO_SELECTION):
        return

    header, panel = layout.panel("cp77_rigify_torso", default_closed=False)
    header.label(text="Torso / Head", icon="OUTLINER_OB_ARMATURE")
    if not panel:
        return

    if torso is not None and "torso_parent" in torso:
        panel.prop(torso, '["torso_parent"]', text="Torso Parent")
    if head is not None:
        if "neck_follow" in head:
            panel.prop(head, '["neck_follow"]', text="Neck Follow", slider=True)
        if "head_follow" in head:
            panel.prop(head, '["head_follow"]', text="Head Follow", slider=True)


def draw_rigify_controls(layout, context) -> None:
    obj = active_armature(context)
    if obj is None or obj.type != "ARMATURE":
        return

    source, rig = find_pair(obj)
    if source is None or rig is None:
        return

    box = layout.box()
    box.label(text="Rigify Controls", icon="POSE_HLT")

    _draw_live_sync(box, source, rig)

    if obj is not rig and obj is not source:
        _draw_active_switcher(box, context, source, rig)
        return

    _draw_active_switcher(box, context, source, rig)

    if obj is rig:
        if obj.mode != "POSE":
            box.label(text="Enter Pose Mode for IK/FK")
            _draw_collections(box, rig)
            return

        rig_identifier = rig_id(source, rig)
        if not rig_identifier:
            box.label(text="Regenerate the Rigify rig", icon="ERROR")
            return

        selected = set()
        try:
            for pb in context.selected_pose_bones or ():
                selected.add(pb.name)
            if context.active_pose_bone is not None:
                selected.add(context.active_pose_bone.name)
        except AttributeError as error:
            log_once(
                _LOG,
                "DEBUG",
                ("draw_rigify_controls", type(error).__name__),
                "draw rigify controls: fell back after %s",
                error,
                exc_info=True,
            )

        if not selected:
            box.label(text="Select a control bone")
        else:
            for label, _kind, side, is_leg in LIMBS:
                _draw_limb_block(
                    box,
                    rig,
                    rig_identifier,
                    label,
                    side,
                    is_leg=is_leg,
                    selected_names=selected,
                )
            _draw_torso_block(box, rig, selected)

        _draw_collections(box, rig)
    else:
        box.label(text="Switch to the Rigify rig for IK/FK")
        _draw_collections(box, rig)
