from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import bpy

from . import generate_rigs as _gr
from .generate_rigs import get_rigify_coll_prop


def _limb_descriptor(prefix: str, side: str, *, is_leg: bool) -> Dict[str, str]:
    """Build the argument bundle for one rigify limb (matches rig_ui.py output)."""
    if is_leg:
        base = ('thigh', 'shin', 'foot')
        extra = f'["foot_heel_ik.{side}", "foot_spin_ik.{side}"]'
    else:
        base = ('upper_arm', 'forearm', 'hand')
        extra = '[]'
    a, b, c = base
    fk = f'["{a}_fk.{side}", "{b}_fk.{side}", "{c}_fk.{side}"]'
    ik_mch = f'["{a}_ik.{side}", "MCH-{b}_ik.{side}", "MCH-{a}_ik_target.{side}"]'
    ik_ctrl = (f'["{a}_ik.{side}", "{a}_ik_target.{side}", "{c}_ik.{side}", '
               f'"foot_heel_ik.{side}", "foot_spin_ik.{side}"]') if is_leg else (
        f'["{a}_ik.{side}", "{a}_ik_target.{side}", "{c}_ik.{side}"]')
    return {
        'prop_bone': f'{a}_parent.{side}',
        'fk_bones': fk,
        'ik_bones': ik_mch,
        'ctrl_bones': ik_ctrl,
        'tail_bones': '[]',
        'extra_ctrls': extra,
        }


def _limb_selection_set(prefix: str, side: str, *, is_leg: bool) -> set:
    """Bones whose selection should reveal this limb's controls."""
    if is_leg:
        base = ('thigh', 'shin', 'foot')
        extras = {f'foot_heel_ik.{side}', f'foot_spin_ik.{side}', f'toe.{side}'}
    else:
        base = ('upper_arm', 'forearm', 'hand')
        extras = set()
    result = set()
    for b in base:
        for suffix in ('_fk', '_ik', '_tweak', ''):
            result.add(f'{b}{suffix}.{side}')
        result.add(f'{b}_parent.{side}')
        result.add(f'{b}_ik_target.{side}')
    result.update(extras)
    return result


LIMBS: List[Tuple[str, str, str, bool]] = [
    ('Arm L', 'arm', 'L', False),
    ('Arm R', 'arm', 'R', False),
    ('Leg L', 'leg', 'L', True),
    ('Leg R', 'leg', 'R', True),
    ]


def _rigify_op(rig_id: str, suffix: str) -> Optional[str]:
    """Return the rig-id-suffixed bl_idname if that operator is registered."""
    idname = f'pose.rigify_{suffix}_{rig_id}'
    attr = idname.split('.', 1)[1]
    return idname if hasattr(bpy.ops.pose, attr) else None


# Drawing helpers.

def _draw_direction_toggle(layout, source, rig, current_direction: str) -> None:
    row = layout.row(align=True)
    row.scale_y = 1.15
    forward = current_direction == _gr.DIRECTION_FORWARD
    op = row.operator(
            'cp77.toggle_constraint_direction',
            text='Rigify → Source' if forward else 'Source → Rigify',
            depress=True,
            )
    op.source_name = source.name
    op.rigify_name = rig.name


def _draw_active_switcher(layout, context, source, rig) -> None:
    obj = context.active_object
    row = layout.row(align=True)
    if obj is not rig:
        op = row.operator(
                'cp77.activate_linked_rig',
                text=f"Activate Rigify Rig '{rig.name}'",
                icon='ARMATURE_DATA',
                )
        op.target_name = rig.name
    if obj is not source:
        op = row.operator(
                'cp77.activate_linked_rig',
                text=f"Activate Source '{source.name}'",
                icon='OUTLINER_OB_ARMATURE',
                )
        op.target_name = source.name


def _draw_collections(layout, rig) -> None:
    arm = rig.data
    cols = list(getattr(arm, 'collections', []) or [])
    if not cols:
        return
    header, panel = layout.panel('cp77_rigify_collections', default_closed=False)
    header.label(text='Bone Collections')
    if not panel:
        return

    rows: Dict[int, List] = {}
    for c in cols:
        row_id = get_rigify_coll_prop(c, 'rigify_ui_row', 0)
        if row_id > 0:
            rows.setdefault(row_id, []).append(c)
    if not rows:
        rows = {1: cols}

    for row_id in sorted(rows.keys()):
        r = panel.row(align=True)
        for c in rows[row_id]:
            title = get_rigify_coll_prop(c, 'rigify_ui_title', '') or c.name
            sub = r.row(align=True)
            sub.active = getattr(c, 'is_visible_ancestors', True)
            sub.prop(c, 'is_visible', toggle=True, text=title, translate=False)


def _draw_limb_block(
        layout, rig, rig_id: str, label: str, side: str,
        *, is_leg: bool, selected_names: set,
        ) -> None:
    sel_set = _limb_selection_set('', side, is_leg=is_leg)
    if not (selected_names & sel_set):
        return

    desc = _limb_descriptor('', side, is_leg=is_leg)
    prop_bone_name = desc['prop_bone']
    prop_bone = rig.pose.bones.get(prop_bone_name)
    if prop_bone is None:
        return

    header, panel = layout.panel(
        f'cp77_rigify_limb_{label.replace(" ", "_")}',
        default_closed=False
        )
    header.label(text=label, icon='CON_KINEMATIC')
    if not panel:
        return

    if 'FK_limb_follow' in prop_bone.keys():
        panel.prop(prop_bone, '["FK_limb_follow"]', text='FK Limb Follow', slider=True)
    if 'IK_FK' in prop_bone.keys():
        panel.prop(prop_bone, '["IK_FK"]', text='IK-FK', slider=True)
    if 'IK_Stretch' in prop_bone.keys():
        panel.prop(prop_bone, '["IK_Stretch"]', text='IK Stretch', slider=True)

    snap_generic = _rigify_op(rig_id, 'generic_snap')
    snap_ik2fk = _rigify_op(rig_id, 'limb_ik2fk')
    leg_roll = _rigify_op(rig_id, 'leg_roll_ik2fk') if is_leg else None
    toggle_pole = _rigify_op(rig_id, 'limb_toggle_pole')

    if snap_generic is not None:
        op = panel.operator(snap_generic, text='FK → IK', icon='SNAP_ON')
        a, b, c = ('thigh', 'shin', 'foot') if is_leg else ('upper_arm', 'forearm', 'hand')
        op.output_bones = f'["{a}_fk.{side}", "{b}_fk.{side}", "{c}_fk.{side}"]'
        op.input_bones = desc['ik_bones']
        op.ctrl_bones = desc['ctrl_bones']

    if snap_ik2fk is not None:
        op = panel.operator(snap_ik2fk, text='IK → FK', icon='SNAP_ON')
        for key, value in desc.items():
            setattr(op, key, value)

    if is_leg and leg_roll is not None:
        op = panel.operator(leg_roll, text='IK → FK with Roll', icon='SNAP_ON')
        for key, value in desc.items():
            setattr(op, key, value)
        op.heel_control = f'foot_heel_ik.{side}'

    if toggle_pole is not None and 'pole_vector' in prop_bone.keys():
        row = panel.row(align=True)
        op = row.operator(toggle_pole, text='', icon='FORCE_MAGNETIC')
        op.prop_bone = desc['prop_bone']
        op.ik_bones = desc['ik_bones']
        op.ctrl_bones = desc['ctrl_bones']
        op.extra_ctrls = desc['extra_ctrls']
        row.prop(
                prop_bone, '["pole_vector"]',
                text='Pole On' if prop_bone['pole_vector'] else 'Pole Off',
                toggle=True,
                )


def _draw_torso_block(layout, rig, selected_names: set) -> None:
    torso = rig.pose.bones.get('torso')
    head = rig.pose.bones.get('head')
    sel = {'torso', 'chest', 'hips', 'spine_fk', 'spine_fk.001', 'spine_fk.002',
           'spine_fk.003', 'pelvis_fk', 'tweak_pelvis', 'tweak_spine', 'head', 'neck'}
    if not (selected_names & sel):
        return

    header, panel = layout.panel('cp77_rigify_torso', default_closed=False)
    header.label(text='Torso / Head', icon='OUTLINER_OB_ARMATURE')
    if not panel:
        return

    if torso is not None and 'torso_parent' in torso.keys():
        panel.prop(torso, '["torso_parent"]', text='Torso Parent')
    if head is not None:
        if 'neck_follow' in head.keys():
            panel.prop(head, '["neck_follow"]', text='Neck Follow', slider=True)
        if 'head_follow' in head.keys():
            panel.prop(head, '["head_follow"]', text='Head Follow', slider=True)


def draw_rigify_controls(layout, context) -> None:
    """Insert the Rigify control block into the panel layout if applicable."""
    obj = context.active_object
    if obj is None or obj.type != 'ARMATURE':
        return

    source, rig = _gr.find_pair(obj)
    if source is None or rig is None:
        return

    box = layout.box()
    box.label(text='Rigify Controls', icon='POSE_HLT')

    direction = _gr.get_constraint_direction(source)
    _draw_direction_toggle(box, source, rig, direction)

    if obj is not rig and obj is not source:
        _draw_active_switcher(box, context, source, rig)
        return

    _draw_active_switcher(box, context, source, rig)

    if obj is rig:
        if obj.mode != 'POSE':
            box.label(text='Enter Pose Mode to access IK/FK controls')
            _draw_collections(box, rig)
            return

        rig_id = rig.data.get('rig_id') or source.data.get('cp77_rig_id', '')
        if not rig_id:
            box.label(text="Missing 'rig_id' on Rigify rig — regenerate", icon='ERROR')
            return

        selected = set()
        try:
            for pb in (context.selected_pose_bones or ()):
                selected.add(pb.name)
            if context.active_pose_bone is not None:
                selected.add(context.active_pose_bone.name)
        except AttributeError:
            pass

        if not selected:
            box.label(text='Select a control bone to expose its options')
        else:
            for label, _kind, side, is_leg in LIMBS:
                _draw_limb_block(
                    box, rig, rig_id, label, side,
                    is_leg=is_leg, selected_names=selected
                    )
            _draw_torso_block(box, rig, selected)

        _draw_collections(box, rig)
    else:
        box.label(text='Source rig is active — switch to Rigify rig for IK/FK')
        _draw_collections(box, rig)
