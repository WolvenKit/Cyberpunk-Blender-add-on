from __future__ import annotations

import logging

import bpy
from mathutils import Vector

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

# Rigify sizes the hand IK widget to the hand bone, which is short on Cyberpunk rigs; it is drawn this share of the
# forearm instead.
HAND_IK_WIDGET_SHARE = 0.45
_SWING_TWIST = ("SWING_TWIST_X", "SWING_TWIST_Y", "SWING_TWIST_Z")
# Rigify's finger rig curls each knuckle after the first through the rotation of its _drv bone.
_CURL_DRIVER_PATHS = ('_drv.L"].rotation_euler', '_drv.R"].rotation_euler')


def _bone_users(rig) -> dict:
    """Bone name -> names of the bones that use it as a constraint target, parent, shape transform or driver input"""
    users = {}
    for pose_bone in rig.pose.bones:
        for constraint in pose_bone.constraints:
            if getattr(constraint, "target", None) == rig and constraint.subtarget:
                users.setdefault(constraint.subtarget, set()).add(pose_bone.name)
        for used in (pose_bone.parent, pose_bone.custom_shape_transform):
            if used is not None:
                users.setdefault(used.name, set()).add(pose_bone.name)
    for fcurve in rig.animation_data.drivers if rig.animation_data else ():
        path = fcurve.data_path
        owner = path.split('"')[1] if path.startswith("pose.bones[") else ""
        for variable in fcurve.driver.variables:
            for target in variable.targets:
                if target.id != rig:
                    continue
                for used in (target.bone_target, *target.data_path.split('"')[1:2]):
                    if used:
                        users.setdefault(used, set()).add(owner)
    return users


def _shown_size(pose_bone) -> float:
    """The largest extent the bone's custom shape is drawn at"""
    corners = [Vector(corner) for corner in pose_bone.custom_shape.bound_box]
    extent = max(
        max(corner[axis] for corner in corners)
        - min(corner[axis] for corner in corners)
        for axis in range(3)
    )
    length = pose_bone.bone.length if pose_bone.use_custom_shape_bone_size else 1.0
    return (
        extent * length * max(abs(value) for value in pose_bone.custom_shape_scale_xyz)
    )


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
        self._drop_tweak_controls()
        self._size_hand_ik_widgets()
        self._curl_fingers_from_masters()

    def _drop_tweak_controls(self) -> None:
        """Remove the tweak controls only deform bones follow, as the Cyberpunk rig follows the ORG bones"""
        rig = self.rig
        users = _bone_users(rig)
        removable = {
            bone.name
            for collection in rig.data.collections_all
            if collection.name.endswith("(Tweak)")
            for bone in collection.bones
        }
        # Rigify places tweaks through mechanism bones of their own.
        removable |= {
            bone.name
            for bone in rig.data.bones
            if bone.name.startswith("MCH-") and "_tweak" in bone.name
        }
        # A tweak anything but a deform bone or another removed tweak uses stays, as the torso's do for the spine.
        while True:
            kept = {
                name
                for name in removable
                if any(
                    not user.startswith("DEF-") and user not in removable
                    for user in users.get(name, ())
                )
            }
            if not kept:
                break
            removable -= kept
        if not removable:
            return
        for pose_bone in rig.pose.bones:
            for constraint in tuple(pose_bone.constraints):
                if (
                    getattr(constraint, "target", None) == rig
                    and constraint.subtarget in removable
                ):
                    pose_bone.constraints.remove(constraint)
        safe_mode_switch("EDIT")
        edit_bones = rig.data.edit_bones
        for name in removable:
            edit_bone = edit_bones.get(name)
            if edit_bone is not None:
                edit_bones.remove(edit_bone)
        safe_mode_switch("POSE")
        for collection in tuple(rig.data.collections_all):
            if (
                collection.name.endswith("(Tweak)")
                and not collection.bones
                and not collection.children
            ):
                rig.data.collections.remove(collection)
        self.log("Removed %d tweak controls", len(removable))

    def _size_hand_ik_widgets(self) -> None:
        """Draw each hand's IK widget at a share of its forearm"""
        for side in ("L", "R"):
            control = self.rig.pose.bones.get(f"hand_ik.{side}")
            forearm = self.rig.data.bones.get(f"ORG-forearm.{side}")
            if control is None or forearm is None or control.custom_shape is None:
                continue
            size = _shown_size(control)
            if size <= 0.0:
                continue
            factor = HAND_IK_WIDGET_SHARE * forearm.length / size
            if factor > 1.0:
                control.custom_shape_scale_xyz = [
                    value * factor for value in control.custom_shape_scale_xyz
                ]

    def _curl_fingers_from_masters(self) -> None:
        """Let a finger master's rotation about the bend axis curl every knuckle, as its Y scale does"""
        animation_data = self.rig.animation_data
        for fcurve in animation_data.drivers if animation_data else ():
            if not fcurve.data_path.endswith(_CURL_DRIVER_PATHS):
                continue
            driver = fcurve.driver
            variables = driver.variables
            scale = variables.get("sy")
            if scale is None or variables.get("rx") is not None:
                continue
            master = scale.targets[0].data_path.split('"')[1:2]
            if not master:
                continue
            axis = fcurve.array_index
            curl = variables.new()
            curl.name = "rx"
            curl.type = "TRANSFORMS"
            target = curl.targets[0]
            target.id = self.rig
            target.bone_target = master[0]
            target.transform_type = ("ROT_X", "ROT_Y", "ROT_Z")[axis]
            target.transform_space = "LOCAL_SPACE"
            target.rotation_mode = _SWING_TWIST[axis]
            driver.expression = f"{driver.expression} + rx"

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
