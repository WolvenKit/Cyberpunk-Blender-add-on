from __future__ import annotations

import bpy

from ....animation.rigify.mapping import DIRECTION_FORWARD
from ....blender.context import safe_mode_switch
from .state import RigifyStage
from .sync import disable_forward_sync, enable_forward_sync


class RigifyBindingService(RigifyStage):
    def bind_forward_constraints(self) -> None:
        self.log('Binding forward matrix-basis sync (rigify → source)', 'STEP')
        n = enable_forward_sync(self.source, self.rig, recapture_neutral=True)
        self.stats['source_sync_bones'] = n
        safe_mode_switch('OBJECT')

    def link_metadata(self) -> None:
        self.source.data['cp77_metarig']     = self.meta.name
        self.source.data['cp77_rigify_rig']  = self.rig.name
        self.source.data['cp77_rig_id']      = self.rig.data.get('rig_id', '')
        self.source.data['cp77_constraint_direction'] = DIRECTION_FORWARD
        self.meta.data['cp77_source_rig']    = self.source.name
        self.rig.data['cp77_source_rig']     = self.source.name

    def hide_metarig(self) -> None:
        try:
            self.meta.hide_set(True)
            self.meta.hide_viewport = True
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            pass

    def cleanup_on_failure(self) -> None:
        disable_forward_sync(self.source)
        if self.rig is not None and not self.session.created_rig:
            self._restore_existing_rig_collections()
        for obj, created in (
            (self.rig, self.session.created_rig),
            (self.meta, self.session.created_meta),
        ):
            if not created:
                continue
            try:
                if obj and obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
            except (ReferenceError, RuntimeError, TypeError, ValueError):
                pass

    def _restore_existing_rig_collections(self) -> None:
        try:
            current = tuple(self.rig.users_collection)
            original = self.session.rig_original_collections
            for collection in current:
                if collection not in original:
                    collection.objects.unlink(self.rig)
            for collection in original:
                if collection not in current:
                    collection.objects.link(self.rig)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            pass
