from __future__ import annotations

from typing import Optional

import bpy

from ....animation.rigify.mapping import set_rigify_coll_prop
from ....blender.context import safe_mode_switch
from ....blender.selection import select_objects
from .state import RigifyStage
from .sync import neutralize_rigify_controls


class GeneratedRigBuilder(RigifyStage):
    def generate(self, existing_rig: Optional[bpy.types.Object] = None) -> None:
        self.log('Generating Rigify rig', 'STEP')
        select_objects(self.meta)
        safe_mode_switch('POSE')

        if existing_rig is not None and existing_rig.type == 'ARMATURE':
            self.session.rig_original_collections = tuple(existing_rig.users_collection)
            self.meta.data.rigify_target_rig = existing_rig
            self.log(f"Updating existing rig '{existing_rig.name}' in place")

        if not hasattr(bpy.ops.pose, 'rigify_generate'):
            raise RuntimeError('Rigify addon not enabled (pose.rigify_generate missing).')

        objs_before = set(bpy.data.objects)
        bpy.ops.pose.rigify_generate()

        if existing_rig is not None and existing_rig.name in bpy.data.objects:
            self.rig = existing_rig
        else:
            new_objs = [o for o in (set(bpy.data.objects) - objs_before) if o.type == 'ARMATURE']
            self.rig = new_objs[0] if new_objs else None

        if not self.rig:
            raise RuntimeError('Rigify generation failed to produce an armature')
        self.session.created_rig = existing_rig is None or self.rig is not existing_rig
        self.log(f"Generated '{self.rig.name}'")

        # Keep generated rig collection membership aligned with the source.
        for coll in list(self.rig.users_collection):
            try:
                coll.objects.unlink(self.rig)
            except (ReferenceError, RuntimeError, TypeError, ValueError):
                pass
        if self.source_collections:
            for coll in self.source_collections:
                try:
                    coll.objects.link(self.rig)
                except Exception:
                    pass
        else:
            self.context.scene.collection.objects.link(self.rig)

        self._post_process_rigify()

    def _post_process_rigify(self) -> None:
        select_objects(self.rig)
        safe_mode_switch('POSE')
        for b in self.rig.pose.bones:
            if 'IK_Stretch' in b.keys():
                b['IK_Stretch'] = 0.0
        self.stats['neutralized_controls'] = neutralize_rigify_controls(self.rig)

        safe_mode_switch('EDIT')
        arm = self.rig.data
        fk = arm.collections.get('FK') or arm.collections.new('FK')
        ik = arm.collections.get('IK') or arm.collections.new('IK')
        tw = arm.collections.get('Tweak') or arm.collections.new('Tweak')
        set_rigify_coll_prop(fk, 'rigify_color_set_id', 5)
        set_rigify_coll_prop(fk, 'rigify_ui_row', 8)
        set_rigify_coll_prop(ik, 'rigify_color_set_id', 2)
        set_rigify_coll_prop(ik, 'rigify_ui_row', 8)
        set_rigify_coll_prop(tw, 'rigify_color_set_id', 4)
        set_rigify_coll_prop(tw, 'rigify_ui_row', 9)

        for b in arm.edit_bones:
            nl = b.name.lower()
            if '_fk' in nl:
                target = fk
            elif '_ik' in nl and '_parent' not in nl:
                target = ik
            elif 'tweak' in nl:
                target = tw
            else:
                target = None
            if target is None:
                continue
            for c in tuple(b.collections):
                c.unassign(b)
            target.assign(b)
            self.stats[f'{target.name.lower()}_controls'] += 1

        safe_mode_switch('POSE')
