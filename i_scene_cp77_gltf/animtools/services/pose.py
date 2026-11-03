from __future__ import annotations

<<<<<<< Updated upstream
import os

import bpy

from ...animation.bones import ANIMATION_BONE_SET
from ...animation.rig import RigRepository
from ...assetio.documents import DocumentSession
from ...blender.animation_context import active_armature
from ...blender.armature import apply_bone_from_matrix, build_apose_matrices, model_space_matrices_cached
from ...blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ..model import OperationResult


def insert_pose_keyframes(context, *, frame_all: bool, step: int = 1) -> OperationResult:
=======
from ...animation.domain.rig.assembly import merge_rig_datas
from ...animation.model.clip.bones import ANIMATION_BONE_SET
from ...animation.services.rig.repository import load_rigs
from ...blender.animation_context import (
    active_armature,
    track_action_curves,
    track_pose,
)
from ...blender.armature import (
    apply_bind_matrices,
    build_apose_matrices,
    model_space_matrices_cached,
)
from ...blender.context import (
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.operator_results import OperationResult
from ...blender.pose import insert_channel_keys, keying_set_channels, reset_pose_bones
from ...blender.rig_metadata import source_rig_paths
from ...blender.skinning import move_skinned_rest_shapes
from ...blender.transactions import transactional
from ...core.log import get_logger

_LOG = get_logger(__name__)
_POSE_KEYING_SET = "WholeCharacterSelected"


@transactional("Pose keyframing")
def insert_pose_keyframes(context, *, frame_all: bool) -> OperationResult:
>>>>>>> Stashed changes
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    original_mode = context.mode
    if original_mode != "POSE":
        try:
<<<<<<< Updated upstream
            bpy.ops.object.mode_set(mode="POSE")
        except (RuntimeError, TypeError, ValueError) as exc:
            return OperationResult(False, f"Failed to switch to pose mode: {exc}", "ERROR")
    try:
        if not frame_all:
            bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
            return OperationResult(True, "Keyframe inserted at current frame.")
        if not armature.animation_data or not armature.animation_data.action:
            return OperationResult(False, "Armature has no animation data or action.", "ERROR")
        action = armature.animation_data.action
        start, end = map(int, action.frame_range)
        original_frame = context.scene.frame_current
        count = 0
        try:
            for frame in range(start, end + 1, max(1, int(step))):
                context.scene.frame_set(frame)
                bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
                count += 1
        finally:
            context.scene.frame_set(original_frame)
        return OperationResult(True, f"Inserted keyframes at {count} frames.", details={"count": count})
    except (RuntimeError, ReferenceError, TypeError, ValueError) as exc:
=======
            safe_mode_switch("POSE")
        except RuntimeError as exc:
            return OperationResult(
                False, f"Failed to switch to pose mode: {exc}", "ERROR"
            )
    try:
        scene = context.scene
        if frame_all and (
            not armature.animation_data or not armature.animation_data.action
        ):
            return OperationResult(
                False, "Armature has no animation data or action.", "ERROR"
            )
        # The Whole Character keying set decides which channels a pose keyframe holds.
        channels = keying_set_channels(context, _POSE_KEYING_SET)
        # Keying nothing is no failure: Only Insert Needed skips unchanged channels, as Blender's own keying does.
        if not frame_all:
            insert_channel_keys(
                context, channels, scene.frame_current + scene.frame_subframe
            )
            return OperationResult(True, "Keyframe inserted at current frame.")
        action = armature.animation_data.action
        track_action_curves(action, armature, label="pose keyframes")
        start, end = map(int, action.frame_range)
        original_frame = scene.frame_current
        count = 0
        try:
            for frame in range(start, end + 1):
                scene.frame_set(frame)
                insert_channel_keys(context, channels, frame)
                count += 1
        finally:
            scene.frame_set(original_frame)
        return OperationResult(
            True, f"Inserted keyframes at {count} frames.", details={"count": count}
        )
    except (RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        _LOG.error(
            "Pose keyframe insertion failed: armature=%s error=%s",
            armature.name,
            exc,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return OperationResult(False, f"Keyframe insertion failed: {exc}", "ERROR")
    finally:
        if context.mode != original_mode:
            safe_mode_switch(original_mode)


<<<<<<< Updated upstream
def load_bind_pose(armature, *, use_tpose: bool) -> OperationResult:
    armature_data = armature.data
    filepath = armature_data.get("source_rig_file", "")
    if not filepath or ";" in filepath or not os.path.isfile(filepath):
        return OperationResult(False, f"Invalid single-rig JSON source: {filepath}", "ERROR")
    with DocumentSession() as documents:
        rig = RigRepository(documents).load(filepath, required=True)
    matrices = (
        list(model_space_matrices_cached(rig.bone_transforms, rig.parent_indices))
        if use_tpose
        else build_apose_matrices(rig.apose_ms, rig.apose_ls, rig.bone_names, rig.parent_indices)
    )
    pose_name = "T-Pose" if use_tpose else "A-Pose"
    if not matrices:
        return OperationResult(False, f"No complete {pose_name} found in {rig.rig_name}", "ERROR")

=======
def _bind_matrices(armature, rigs, *, use_tpose: bool):
    """The rig used for the bind pose and its model-space bind matrices, or an error message"""
    source = str(armature.data.get("cp77_source_rig_file", ""))
    if (
        len(rigs) > 1
        or source.startswith("metarig:")
        or armature.get("cp77_rig_merge_order")
    ):
        rig, metadata = merge_rig_datas(rigs, armature.name, return_metadata=True)
        transforms = rig.bone_transforms
        if use_tpose:
            transforms = []
            for name in rig.bone_names:
                owner = metadata["bone_sources"][name]
                source_rig = rigs[owner["rig_order"]]
                index = owner["source_index"]
                if index >= len(source_rig.bone_transforms):
                    return (
                        rig,
                        None,
                        f"No complete T-Pose found in {source_rig.rig_name}",
                    )
                transforms.append(source_rig.bone_transforms[index])
    else:
        rig = rigs[0]
        transforms = rig.bone_transforms
    matrices = (
        list(model_space_matrices_cached(transforms, rig.parent_indices))
        if use_tpose
        else build_apose_matrices(
            rig.apose_ms, rig.apose_ls, rig.bone_names, rig.parent_indices
        )
    )
    return rig, matrices, ""


@transactional("Bind pose")
def load_bind_pose(armature, *, use_tpose: bool) -> OperationResult:
    armature_data = armature.data
    paths = source_rig_paths(armature)
    if not paths:
        return OperationResult(
            False, "Armature has no source rig JSON metadata.", "ERROR"
        )
    rig, matrices, error = _bind_matrices(
        armature, load_rigs(paths), use_tpose=use_tpose
    )
    if error:
        return OperationResult(False, error, "ERROR")
    pose_name = "T-Pose" if use_tpose else "A-Pose"
    if not matrices or len(matrices) != len(rig.bone_names):
        return OperationResult(
            False, f"No complete {pose_name} found in {rig.rig_name}", "ERROR"
        )
    missing = [name for name in rig.bone_names if armature_data.bones.get(name) is None]
    if missing:
        return OperationResult(
            False,
            f"Armature is missing {len(missing)} rig bones",
            "ERROR",
            details={"missing_bones": tuple(missing)},
        )

    track_pose(armature, label="bind pose")
    switching = armature_data.get("cp77_t_pose") != use_tpose
    previous_rest = {
        bone.name: bone.matrix_local.copy() for bone in armature_data.bones
    }
>>>>>>> Stashed changes
    store_current_context()
    try:
        safe_mode_switch("EDIT")
        edit_bones = armature_data.edit_bones
<<<<<<< Updated upstream
        bone_map = {index: edit_bones.get(name) for index, name in enumerate(rig.bone_names)}
        missing = [rig.bone_names[index] for index, bone in bone_map.items() if bone is None]
        if missing:
            return OperationResult(
                False,
                f"Armature is missing {len(missing)} rig bones",
                "ERROR",
                details={"missing_bones": tuple(missing)},
            )
        for index, matrix in enumerate(matrices):
            apply_bone_from_matrix(index, matrix, bone_map, rig.parent_indices, matrices)
        armature_data["T-Pose"] = use_tpose
    finally:
        restore_previous_context()

    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis.identity()
=======
        original = {
            bone.name: (bone.head.copy(), bone.tail.copy(), bone.roll)
            for bone in edit_bones
        }
        bone_map = {
            index: edit_bones.get(name) for index, name in enumerate(rig.bone_names)
        }
        try:
            apply_bind_matrices(
                bone_map, matrices, rig.parent_indices, skip_identity=use_tpose
            )
        except Exception:
            for name, (head, tail, roll) in original.items():
                bone = edit_bones.get(name)
                if bone is not None:
                    bone.head, bone.tail, bone.roll = head, tail, roll
            raise
        armature_data["cp77_t_pose"] = use_tpose
    finally:
        restore_previous_context()

    reset_pose_bones(armature)
    if switching:
        # The meshes are authored in the A-pose: the T-pose skins them forward, the A-pose undoes that exactly.
        rest = {bone.name: bone.matrix_local.copy() for bone in armature_data.bones}
        if use_tpose:
            move_skinned_rest_shapes(armature, previous_rest, rest)
        else:
            move_skinned_rest_shapes(armature, rest, previous_rest, inverse=True)
>>>>>>> Stashed changes
    return OperationResult(True, f"{pose_name} loaded")


def set_extra_bones_hidden(context, hidden: bool) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature object.", "ERROR")
    affected = 0
    for pose_bone in armature.pose.bones:
        should_change = not hidden or pose_bone.name not in ANIMATION_BONE_SET
        if should_change:
            pose_bone.hide = hidden
            affected += 1
    armature.update_tag()
    if hidden:
<<<<<<< Updated upstream
        armature["deformBonesHidden"] = True
        return OperationResult(True, f"Hidden {affected} extra bones", details={"count": affected})
    if "deformBonesHidden" in armature:
        del armature["deformBonesHidden"]
    return OperationResult(True, f"Unhidden {affected} bones", details={"count": affected})
=======
        armature["cp77_deform_bones_hidden"] = True
        return OperationResult(
            True, f"Hidden {affected} extra bones", details={"count": affected}
        )
    if "cp77_deform_bones_hidden" in armature:
        del armature["cp77_deform_bones_hidden"]
    return OperationResult(
        True, f"Unhidden {affected} bones", details={"count": affected}
    )
>>>>>>> Stashed changes
