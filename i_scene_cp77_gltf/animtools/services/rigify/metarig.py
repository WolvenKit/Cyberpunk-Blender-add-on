from __future__ import annotations

from mathutils import Color, Vector

from ....animation.rigify.mapping import (
    CHAINS,
    COLLECTIONS,
    COLOR_SETS,
    CP77_TO_METARIG,
    RIGIFY_TYPES,
    SELECT_COLOR,
    set_rigify_coll_prop,
)
from ....blender.context import safe_mode_switch
from ....blender.selection import select_objects
from .fingers import FingerChainBuilder
from .state import RigifyStage


class MetarigBuilder(RigifyStage):
    def create(self) -> None:
        self.log('Creating metarig', 'STEP')
        src = self.source
        meta_obj = src.copy()
        meta_obj.data = src.data.copy()
        meta_obj.animation_data_clear()
        meta_obj.name = f"{src.name}_metarig"
        meta_obj.data.name = meta_obj.name

        if self.source_collections:
            for c in self.source_collections:
                try:
                    c.objects.link(meta_obj)
                except Exception:
                    pass
        else:
            self.context.scene.collection.objects.link(meta_obj)

        self.meta = meta_obj
        self.session.created_meta = True
        select_objects(self.meta)

    def prepare(self) -> None:
        self.log('Preparing metarig', 'STEP')
        select_objects(self.meta)
        arm = self.meta.data

        safe_mode_switch('EDIT')
        eb = arm.edit_bones
        self._prune_deform_bones(eb)
        self._rename_bones(eb)
        self._build_chains(eb)
        self._build_spine_branch(eb)
        self._orient_root_bone(eb)
        FingerChainBuilder(self.session).build(eb)
        self._build_foot_chains(eb)
        self._reparent_weapons(eb)
        self._configure_colors(arm)
        self._configure_collections(arm, eb)

        safe_mode_switch('POSE')
        self._assign_rigify_types()
        self._configure_limb_parameters()
        self._strip_custom_shapes()

        safe_mode_switch('OBJECT')

    def _prune_deform_bones(self, eb) -> None:
        allowed = set(CP77_TO_METARIG.keys())
        to_remove = [b for b in eb if b.name not in allowed]
        for b in to_remove:
            eb.remove(b)

        self.stats['pruned_unmapped'] = len(to_remove)
        if to_remove:
            self.log(f"Pruned {len(to_remove)} unmapped source bones from metarig")

    def _rename_bones(self, eb) -> None:
        TEMP = '__CP77T__'
        present = {b.name: b for b in eb}
        rename_map = {cp77: meta for cp77, meta in CP77_TO_METARIG.items() if cp77 in present}

        for cp77 in rename_map:
            present[cp77].name = TEMP + rename_map[cp77]

        present = {b.name: b for b in eb}
        for cp77, meta in rename_map.items():
            tagged = TEMP + meta
            if tagged in present:
                present[tagged].name = meta

        self.stats['renamed'] = len(rename_map)

    def _build_chains(self, eb) -> None:
        present = {b.name: b for b in eb}
        for chain in CHAINS:
            if not all(n in present for n in chain):
                continue
            for parent_name, child_name in zip(chain[:-1], chain[1:]):
                parent, child = present[parent_name], present[child_name]
                child.parent = parent
                parent.tail = child.head.copy()
                child.use_connect = True

    def _build_spine_branch(self, eb) -> None:
        present = {b.name: b for b in eb}
        chest = present.get('spine.003')
        neck = present.get('spine.004')
        if chest is None or neck is None:
            return

        chest_axis = neck.head - chest.head
        if chest_axis.length <= 1e-5:
            return

        chest.tail = neck.head.copy()
        neck.parent = chest
        neck.use_connect = False

        for shoulder_name in ('shoulder.L', 'shoulder.R'):
            shoulder = present.get(shoulder_name)
            if shoulder is not None:
                shoulder.parent = chest
                shoulder.use_connect = False

        left = present.get('shoulder.L')
        right = present.get('shoulder.R')
        if left is None or right is None:
            self.stats['spine3_branch_aimed'] = 1
            return

        shoulder_axis = right.head - left.head
        if shoulder_axis.length <= 1e-5:
            self.stats['spine3_branch_aimed'] = 1
            return

        roll_ref = shoulder_axis.cross(chest_axis)
        if roll_ref.length <= 1e-5:
            self.stats['spine3_branch_aimed'] = 1
            return
        roll_ref.normalize()

        aligned = 0
        for name in ('pelvis', 'spine', 'spine.001', 'spine.002', 'spine.003'):
            bone = present.get(name)
            if bone is None:
                continue
            axis = bone.tail - bone.head
            if axis.length <= 1e-5:
                continue
            projected = roll_ref - axis.normalized() * roll_ref.dot(axis.normalized())
            if projected.length <= 1e-5:
                continue
            bone.align_roll(projected.normalized())
            aligned += 1

        self.stats['spine3_branch_aimed'] = 1
        self.stats['basic_spine_rolls_aligned'] = aligned

    def _orient_root_bone(self, eb) -> None:
        present = {b.name: b for b in eb}
        root = present.get('root')
        if root is None:
            return

        root.parent = None
        root.use_connect = False

        pelvis = present.get('pelvis')
        spine = present.get('spine')
        chest = present.get('spine.003')
        neck = present.get('spine.004')

        up = None
        if chest is not None and neck is not None:
            up = neck.head - chest.head
        if (up is None or up.length <= 1e-5) and pelvis is not None and spine is not None:
            up = spine.head - pelvis.head
        if up is None or up.length <= 1e-5:
            up = Vector((0.0, 0.0, 1.0))
        up.normalize()

        length = (root.tail - root.head).length
        if length <= 1e-4:
            if pelvis is not None:
                length = max((pelvis.head - root.head).length * 0.35, 0.20)
            else:
                length = 0.20
        root.tail = root.head + up * length

        left = present.get('shoulder.L')
        right = present.get('shoulder.R')
        if left is not None and right is not None:
            shoulder_axis = right.head - left.head
            if shoulder_axis.length > 1e-5:
                forward = shoulder_axis.cross(up)
                if forward.length > 1e-5:
                    root.align_roll(forward.normalized())
                    self.stats['root_bone_oriented'] = 1
                    return

        self.stats['root_bone_oriented'] = 1








    def _build_foot_chains(self, eb) -> None:
        present = {b.name: b for b in eb}
        for side in ('.L', '.R'):
            foot = present.get(f'foot{side}')
            heel = present.get(f'heel{side}')
            toe  = present.get(f'toe{side}')
            if not (foot and heel and toe):
                continue

            foot_head = foot.head.copy()
            heel_head = heel.head.copy()
            toe_head = toe.head.copy()

            heel.parent = foot
            heel.use_connect = False
            heel.head = heel_head

            toe.parent = foot
            foot.tail = toe_head
            toe.use_connect = True

            heel_axis = toe_head - heel_head
            if heel_axis.length <= 1e-4:
                heel_axis = foot_head - heel_head
            if heel_axis.length > 1e-4:
                heel.tail = heel_head + heel_axis.normalized() * min(max(heel_axis.length * 0.5, 0.04), 0.10)

            toe_forward = toe_head - heel_head
            if toe_forward.length <= 1e-4:
                toe_forward = toe_head - foot_head
            if toe_forward.length <= 1e-4:
                toe_forward = foot.tail - foot.head

            if toe_forward.length > 1e-4:
                toe_len = min(max(toe_forward.length * 0.45, 0.06), 0.12)
                toe.tail = toe.head + toe_forward.normalized() * toe_len

    def _reparent_weapons(self, eb) -> None:
        present = {b.name: b for b in eb}
        for side in ('L', 'R'):
            weapon = present.get(f'weapon.{side}')
            hand   = present.get(f'hand.{side}')
            if not (weapon and hand):
                continue
            weapon.parent = hand
            weapon.use_connect = False
            if (weapon.tail - weapon.head).length < 1e-4:
                offset = (hand.tail - hand.head)
                weapon.tail = weapon.head + (offset * 0.5 if offset.length > 1e-4
                                             else (0.0, 0.05, 0.0))

    def _configure_colors(self, arm) -> None:
        if not hasattr(arm, 'rigify_colors'):
            return
        while arm.rigify_colors:
            arm.rigify_colors.remove(arm.rigify_colors[0])
        for name, active, normal in COLOR_SETS:
            c = arm.rigify_colors.add()
            c.name = name
            c.active = Color(active)
            c.normal = Color(normal)
            c.select = Color(SELECT_COLOR)
            c.standard_colors_lock = True

    def _configure_collections(self, arm, eb) -> None:
        if not hasattr(arm, 'collections'):
            return
        while arm.collections:
            arm.collections.remove(arm.collections[0])
        present = {b.name: b for b in eb}
        for name, (members, row, color_id) in COLLECTIONS.items():
            coll = arm.collections.new(name=name)
            set_rigify_coll_prop(coll, 'rigify_ui_row', row)
            set_rigify_coll_prop(coll, 'rigify_color_set_id', color_id)
            for bn in members:
                b = present.get(bn)
                if b is not None:
                    coll.assign(b)

    def _assign_rigify_types(self) -> None:
        pb = {b.name: b for b in self.meta.pose.bones}
        for name, rtype in RIGIFY_TYPES.items():
            target = pb.get(name)
            if target is not None:
                target.rigify_type = rtype

    def _configure_limb_parameters(self) -> None:
        pb = {b.name: b for b in self.meta.pose.bones}
        for side in ('L', 'R'):
            for limb in (f'thigh.{side}', f'upper_arm.{side}'):
                b = pb.get(limb)
                if b is None:
                    continue
                params = b.rigify_parameters
                params.rotation_axis = 'automatic'
                params.segments = 2
                params.limb_uniform_scale = True
                if params.foot_pivot_type and params.foot_pivot_type == 'ANKLE_TOE':
                    params.extra_ik_toe = True
                    params.ik_local_location = True

            for finger in ('thumb.01', 'f_index.01', 'f_middle.01', 'f_ring.01', 'f_pinky.01'):
                b = pb.get(f'{finger}.{side}')
                if b is not None:
                    # Roll alignment leaves flexion on the primary rotation axis.
                    b.rigify_parameters.primary_rotation_axis = 'automatic'

    def _strip_custom_shapes(self) -> None:
        for b in self.meta.pose.bones:
            b.custom_shape = None
