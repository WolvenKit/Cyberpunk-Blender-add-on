from __future__ import annotations

import logging

import bpy

from ....animation.domain.rigify.mapping import FINGER_ROOTS
from ....blender.context import safe_mode_switch
from ....blender.identity import rna_identity, rna_is_live
from ....blender.operator_results import require_finished
from ....blender.selection import select_objects
from ....blender.transactions import (
    snapshot_datablocks,
    track_collection_state,
    track_created_since,
    track_mutation,
    track_object_state,
)
from .metarig import link_to_source_collections
from .state import RigifyStage


def _track_metarig_targets(meta) -> None:
    data = meta.data
    state = (data.rigify_target_rig, data.rigify_widgets_collection)

    def restore():
        if not rna_is_live(data):
            return
        target, widgets = state
        data.rigify_target_rig = target if rna_is_live(target) else None
        data.rigify_widgets_collection = widgets if rna_is_live(widgets) else None

    track_mutation(
        ("rigify-metarig-targets", rna_identity(data)),
        restore,
        label="Rigify metarig targets",
    )


class GeneratedRigBuilder(RigifyStage):
    def generate(self, existing_rig: bpy.types.Object | None = None) -> None:
        self.log("Generating Rigify rig")
        track_object_state(self.meta, label="Rigify metarig")
        # A metarig kept from an earlier generation is hidden, and Pose Mode needs it shown.
        self.meta.hide_viewport = False
        self.meta.hide_set(False)
        select_objects(self.meta)
        safe_mode_switch("POSE")

        if not hasattr(bpy.ops.pose, "rigify_generate"):
            raise RuntimeError(
                "Rigify addon not enabled (pose.rigify_generate missing)."
            )

        _track_metarig_targets(self.meta)
        if existing_rig is not None and existing_rig.type == "ARMATURE":
            track_object_state(existing_rig, label="Rigify rig")
            for collection in existing_rig.users_collection:
                track_collection_state(collection, label="Rigify rig collections")
            self.meta.data.rigify_target_rig = existing_rig
            self.log("Updating existing rig '%s' in place", existing_rig.name)

        objs_before = set(bpy.data.objects)
        datablocks_before = snapshot_datablocks()
        try:
            result = bpy.ops.pose.rigify_generate()
        finally:
            track_created_since(datablocks_before)
        require_finished(result, "Rigify generation")

        if existing_rig is not None and existing_rig.name in bpy.data.objects:
            self.rig = existing_rig
        else:
            new_objs = [
                o for o in (set(bpy.data.objects) - objs_before) if o.type == "ARMATURE"
            ]
            self.rig = new_objs[0] if new_objs else None

        if not self.rig:
            raise RuntimeError("Rigify generation failed to produce an armature")
        self.log("Generated '%s'", self.rig.name)

        # Keep generated rig collection membership aligned with the source.
        for collection in (*self.rig.users_collection, *self.source_collections):
            track_collection_state(collection, label="Rigify rig collections")
        if not self.source_collections:
            track_collection_state(
                self.context.scene.collection, label="Rigify rig collections"
            )
        for coll in list(self.rig.users_collection):
            try:
                coll.objects.unlink(self.rig)
            except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
                self.log(
                    "Could not unlink '%s' from '%s': %s",
                    self.rig.name,
                    coll.name,
                    error,
                    level=logging.WARNING,
                    exc_info=True,
                )
        link_to_source_collections(self.session, self.rig)

        self._post_process_rigify()

    def _post_process_rigify(self) -> None:
        select_objects(self.rig)
        safe_mode_switch("POSE")
        # CP77 joints do not stretch; IK limbs keep their bone lengths.
        for b in self.rig.pose.bones:
            if "IK_Stretch" in b:
                b["IK_Stretch"] = 0.0
        self._twist_finger_roots()

    def _twist_finger_roots(self) -> None:
        """Let each finger's first control twist its segment, as the later controls do theirs"""
        safe_mode_switch("EDIT")
        edit_bones = self.rig.data.edit_bones
        for name in FINGER_ROOTS:
            stretch = edit_bones.get(f"MCH-{name}")
            control = edit_bones.get(name)
            if stretch is None or control is None:
                continue
            stretch.use_connect = False
            stretch.parent = control
        safe_mode_switch("POSE")
