from __future__ import annotations

import bpy

from ....blender.animation_context import track_id_properties, track_pose
from ....blender.animgraph import rig_binding
from ....blender.animgraph.chain import (
    apply_chain_execution,
    evaluate_chain_state,
    prepare_chain,
)
from ....blender.animgraph.pose_nodes.base import PosePreviewError
from ....blender.animgraph.pose_preview import decode_snapshot, encode_snapshot
from ....blender.identity import rna_identity, rna_is_live
from ....blender.operator_results import OperationResult
from ....blender.pose import apply_pose, capture_pose, capture_tracks, restore_tracks
from ....blender.transactions import track_mutation, transactional
from ....core.log import get_logger

_LOG = get_logger(__name__)
_PREVIEW_FIELDS = (
    "red_pose_preview_armature",
    "red_pose_preview_snapshot_json",
    "red_pose_preview_status",
    "red_pose_preview_node",
    "red_pose_preview_boundary",
)
_PREVIEW_ERRORS = (
    PosePreviewError,
    AttributeError,
    KeyError,
    ReferenceError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _track_binding_state(owner) -> None:
    state = {
        field: getattr(owner, field)
        for field in (*_PREVIEW_FIELDS, "red_bound_armature")
    }

    def restore():
        if not rna_is_live(owner):
            return
        for field, value in state.items():
            if field in {
                "red_pose_preview_armature",
                "red_bound_armature",
            } and not rna_is_live(value):
                value = None
            setattr(owner, field, value)

    track_mutation(
        ("animgraph-preview-state", rna_identity(owner)),
        restore,
        label="AnimGraph preview state",
    )


def _track_armature(armature) -> None:
    if armature is not None:
        track_pose(armature, label="AnimGraph preview pose")
        track_id_properties(armature, label="AnimGraph preview tracks")


def _clear_snapshot_fields(owner) -> None:
    owner.red_pose_preview_armature = None
    owner.red_pose_preview_snapshot_json = ""
    owner.red_pose_preview_status = ""
    owner.red_pose_preview_node = ""
    owner.red_pose_preview_boundary = ""


def _current_action_name(armature) -> str:
    animation_data = (
        getattr(armature, "animation_data", None) if armature is not None else None
    )
    action = (
        getattr(animation_data, "action", None) if animation_data is not None else None
    )
    return str(getattr(action, "name", "") or "")


def _current_frame() -> float:
    """The scene's time, subframe included"""
    scene = getattr(bpy.context, "scene", None)
    return float(getattr(scene, "frame_current", 0.0) or 0.0) + float(
        getattr(scene, "frame_subframe", 0.0) or 0.0
    )


def _update_view_layer() -> None:
    view_layer = getattr(bpy.context, "view_layer", None)
    if view_layer is not None:
        view_layer.update()


def _snapshot_armature(owner):
    armature = getattr(owner, "red_pose_preview_armature", None)
    if armature is not None:
        return armature
    raw = str(getattr(owner, "red_pose_preview_snapshot_json", "") or "")
    try:
        name = decode_snapshot(raw)[0]["armature"] if raw else ""
    except (TypeError, ValueError):
        return None
    return bpy.data.objects.get(name) if name else None


def _restore_snapshot(owner) -> tuple[int, int]:
    """Put back the pose captured by the last preview when it still matches the frame and Action"""
    raw = str(getattr(owner, "red_pose_preview_snapshot_json", "") or "")
    if not raw:
        _clear_snapshot_fields(owner)
        return 0, 0
    try:
        metadata_value, transforms, tracks = decode_snapshot(raw)
    except (TypeError, ValueError):
        _clear_snapshot_fields(owner)
        return 0, 0
    armature = getattr(owner, "red_pose_preview_armature", None)
    if armature is None:
        armature_name = metadata_value["armature"]
        armature = bpy.data.objects.get(armature_name) if armature_name else None
    snapshot_is_current = (
        armature is not None
        and abs(_current_frame() - float(metadata_value["frame"])) <= 1e-6
        and _current_action_name(armature) == str(metadata_value["action"] or "")
    )
    restored_bones = apply_pose(armature, transforms) if snapshot_is_current else 0
    restored_tracks = restore_tracks(armature, tracks) if snapshot_is_current else 0
    _clear_snapshot_fields(owner)
    if restored_bones or restored_tracks:
        _update_view_layer()
    return restored_bones, restored_tracks


def can_preview(tree) -> bool:
    return tree is not None and rig_binding.bound_armature(tree) is not None


def has_preview(tree) -> bool:
    owner = rig_binding.binding_tree(tree)
    return bool(getattr(owner, "red_pose_preview_snapshot_json", ""))


@transactional("AnimGraph pose preview restore")
def clear_preview(tree) -> OperationResult:
    owner = rig_binding.binding_tree(tree)
    if owner is None:
        return OperationResult.finished(
            "Restored 0 pose bone(s) and 0 track(s)",
            restored_bones=0,
            restored_tracks=0,
        )
    _track_binding_state(owner)
    _track_armature(_snapshot_armature(owner))
    bones, tracks = _restore_snapshot(owner)
    return OperationResult.finished(
        f"Restored {bones} pose bone(s) and {tracks} track(s)",
        restored_bones=bones,
        restored_tracks=tracks,
    )


@transactional("AnimGraph pose preview")
def evaluate_preview(tree, active_node) -> OperationResult:
    """Evaluate the pose chain ending at active_node onto the bound armature, keeping a restorable snapshot"""
    owner = rig_binding.binding_tree(tree)
    armature = rig_binding.bound_armature(owner)
    if armature is None:
        return OperationResult.cancelled(
            "Bind this AnimGraph to an armature before previewing"
        )
    _track_binding_state(owner)
    _track_armature(_snapshot_armature(owner))
    _track_armature(armature)
    try:
        _restore_snapshot(owner)
        plan = prepare_chain(owner, active_node, armature, validate=True)
        base_pose = capture_pose(armature, plan.required_bones)
        track_snapshot = capture_tracks(armature, plan.requested_tracks)
        owner.red_pose_preview_armature = armature
        owner.red_pose_preview_snapshot_json = encode_snapshot(
            armature,
            base_pose,
            track_snapshot,
            frame=_current_frame(),
            action_name=_current_action_name(armature),
        )
        owner.red_pose_preview_node = str(getattr(active_node, "name", "") or "")
        owner.red_pose_preview_boundary = plan.boundary
        execution = evaluate_chain_state(plan, armature)
        bone_count, track_count = apply_chain_execution(armature, plan, execution)
    except _PREVIEW_ERRORS as exc:
        return OperationResult.cancelled(str(exc), error=exc)

    status = (
        f"Pose preview: {len(plan.chain)} node(s), {bone_count} bone(s), "
        f"{track_count} track(s), {execution.dynamic_weights} dynamic weight(s)"
    )
    owner.red_pose_preview_status = status
    _update_view_layer()
    return OperationResult.finished(
        status,
        evaluated_nodes=len(plan.chain),
        written_bones=bone_count,
        written_tracks=track_count,
        boundary=plan.boundary,
        dynamic_weights=execution.dynamic_weights,
    )


@transactional("AnimGraph armature binding")
def bind_armature(tree, armature) -> OperationResult:
    """Clear any pose preview, then bind the tree to armature (None clears the binding)"""
    owner = rig_binding.binding_tree(tree)
    if owner is None:
        return OperationResult.cancelled("AnimGraph tree is required")
    _track_binding_state(owner)
    _track_armature(_snapshot_armature(owner))
    _restore_snapshot(owner)
    rig_binding.bind_armature(tree, armature)
    if armature is None:
        return OperationResult.finished()
    return OperationResult.finished(f"AnimGraph bound to {armature.name}")
