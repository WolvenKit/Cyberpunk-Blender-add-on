from __future__ import annotations

import math

import numpy as np

from ...animation.domain.clip.root_motion import (
    choose_motion_format,
    motion_frame_sequence,
    motion_summary,
    root_motion_reference,
    root_motion_samples,
)
from ...animation.model.clip.metadata import FPS, SOURCE_CHANNELS_SNAPSHOT_KEY
from ...blender.action_metadata import (
    action_frame_range,
    load_json_snapshot,
    resolve_action_binding,
    store_json_snapshot,
)
from ...blender.animation_context import (
    active_armature,
    track_action_curves,
    track_animation_data,
    track_id_properties,
    track_pose,
    track_scene_frames,
)
from ...blender.armature import inheritance_issue
from ...blender.bake import sample_pose_matrices, write_pose_bone_samples
from ...blender.keyframes import (
    action_slot_identity,
    assign_action_with_slot,
    curve_key_frames,
    get_action_fcurves,
    remove_fcurves,
)
from ...blender.operator_results import OperationResult
from ...blender.transactions import transactional
from ...core.log import get_logger
from ...redSpace.contracts import SOURCE_REST_SPACE_CONTRACT
from ..blender.root_motion_targets import motion_targets, target_bone_name
from ..model.requests import RootMotionEditOptions, RootMotionRequest

_LOG = get_logger(__name__)
_TRANSFORM_PROPERTIES = (
    "location",
    "rotation_quaternion",
    "rotation_euler",
    "rotation_axis_angle",
    "scale",
)
_VERBS = {
    "extract": "extracted",
    "integrate": "baked into pose",
    "remove": "cleared",
    "ZERO": "rebased",
    "SCALE": "adjusted",
    "GENERATE": "created",
    "FILTER": "filtered",
    "SMOOTH": "smoothed",
    "format": "format updated",
}


def animated_armature(context):
    armature = active_armature(context)
    if armature is None or not armature.pose or not len(armature.pose.bones):
        return None
    if not armature.animation_data or armature.animation_data.action is None:
        return None
    return armature


def motion_request(context, armature):
    """Snapshot the root motion settings for armature with its resolved bones and action frame range"""
    if getattr(getattr(context, "screen", None), "is_animation_playing", False):
        raise ValueError("Pause playback before editing motion.")
    data = context.scene.rm_data
    action = armature.animation_data.action
    root_name, source_name = motion_targets(armature, data.root, data.source)
    start, end = action_frame_range(action)
    return (
        RootMotionRequest(
            root_bone=root_name,
            source_bone=source_name,
            step=max(1, int(data.step)),
            translation_axes=tuple(data.translation_axes),
            rotation_mode=str(data.rotation_mode),
            export_type=str(data.export_type),
            preserve_pose=bool(data.preserve_pose),
        ),
        start,
        end,
    )


def edit_options(context) -> RootMotionEditOptions:
    data = context.scene.rm_data
    return RootMotionEditOptions(
        scale=tuple(data.travel_scale),
        direction=float(data.direction),
        turn_scale=float(data.turn_scale),
        displacement=tuple(data.displacement),
        turn=float(data.turn),
        smooth_radius=float(data.smooth_radius),
    )


def _transform_paths(bones):
    return {bone.path_from_id(prop) for bone in bones for prop in _TRANSFORM_PROPERTIES}


def _validate_setup(armature, request, operation):
    root = armature.pose.bones.get(request.root_bone)
    if root is None or root.parent is not None:
        raise ValueError("Choose a top-level root bone.")
    source = armature.pose.bones.get(request.source_bone)
    if operation == "extract" and (source is None or source == root):
        raise ValueError("Choose a motion source bone other than the root.")
    compensate = operation in {"extract", "integrate"} or (
        request.preserve_pose
        and operation in {"ZERO", "SCALE", "GENERATE", "FILTER", "SMOOTH"}
    )
    affected = (root, *root.children) if compensate else (root,)
    for bone in affected:
        data = bone.bone
        if bone.parent is not None and data.use_connect:
            raise ValueError(
                f"Root child {bone.name!r} is connected; it must allow translation for pose compensation."
            )
        if inheritance_issue(data):
            raise ValueError(
                f"Bone {bone.name!r} uses unsupported transform inheritance."
            )
    subtree = (root, *root.children_recursive)
    for bone in subtree if compensate else affected:
        if any(not item.mute and item.influence != 0.0 for item in bone.constraints):
            raise ValueError(
                f"Bake constraints on bone {bone.name!r} before transferring root motion."
            )
    action = armature.animation_data.action
    if str(action.get("animationType", "Normal")) != "Normal":
        raise ValueError("Select a normal action for root motion.")
    if len(action.layers) > 1:
        raise ValueError(
            "Bake the action to one layer before transferring root motion."
        )
    if armature.animation_data.use_tweak_mode:
        raise ValueError("Exit NLA tweak mode before transferring root motion.")
    subtree_paths = _transform_paths(subtree if compensate else affected)
    if any(
        not curve.mute and curve.data_path in subtree_paths
        for curve in armature.animation_data.drivers
    ):
        raise ValueError("Bake pose drivers before transferring root motion.")
    paths = _transform_paths(affected)
    for curve in get_action_fcurves(action, armature) or ():
        if curve.data_path in paths and (
            len(curve.modifiers) or len(curve.sampled_points)
        ):
            raise ValueError(
                "Bake affected curve modifiers and sampled curves to keyframes before transferring root motion."
            )
    return root, source, affected, subtree_paths


def _root_reference(action, armature, root):
    binding = resolve_action_binding(action, armature)
    names = tuple(str(name) for name in binding.skin.get("boneNames", ()))
    reference_from_pose, neutral_reference = root_motion_reference(
        np.asarray(root.bone.matrix_local, dtype=np.float64),
        names,
        root_name=root.name,
        first_joint_target=target_bone_name(armature, names[0]) if names else "",
        num_extra_joints=int(action.get("numExtraJoints", 0)),
        parents=binding.skin.get("boneParentIndexes") or (),
        source_rest=binding.source_rest,
        source_rest_contract=SOURCE_REST_SPACE_CONTRACT,
    )
    return reference_from_pose, neutral_reference, binding


def _invalidate_source_channels(action, armature, binding, affected):
    snapshot = load_json_snapshot(action, SOURCE_CHANNELS_SNAPSHOT_KEY)
    if not snapshot:
        return
    names = tuple(str(name) for name in binding.skin.get("boneNames", ()))
    changed = {bone.name for bone in affected}
    indices = {
        index
        for index, name in enumerate(names)
        if target_bone_name(armature, name) in changed
    }
    snapshot["channels"] = [
        channel
        for channel in snapshot.get("channels", ())
        if int(channel.get("jointIndex", -1)) not in indices
    ]
    store_json_snapshot(action, SOURCE_CHANNELS_SNAPSHOT_KEY, snapshot)


def _motion_report(details) -> str:
    travel = ", ".join(f"{value:.3f}" for value in details["displacement"])
    turn = (
        f"{math.degrees(details['turn']):.1f}°"
        if details["turn"] is not None
        else "Full rotation"
    )
    return "\n".join(
        (
            f"{details['duration']:.3f} s · {details['distance']:.3f} m travelled",
            f"Mean speed: {details['speed']:.3f} m/s",
            f"XYZ: {travel} m",
            f"Turn: {turn}",
            f"Start: {details['start_offset']:.3f} m / {math.degrees(details['start_angle']):.1f}°",
        )
    )


@transactional("Root motion")
def run_root_motion(context, armature, request, start, end, operation, options=None):
    action = armature.animation_data.action
    data = armature.animation_data
    scene = context.scene
    original_time = (int(scene.frame_current), float(scene.frame_subframe))
    original_settings = {
        name: getattr(data, name)
        for name in ("use_nla", "action_blend_type", "action_influence")
    }

    def restore_context():
        for name, value in original_settings.items():
            setattr(data, name, value)
        scene.frame_set(original_time[0], subframe=original_time[1])

    try:
        root, source, affected, subtree_paths = _validate_setup(
            armature, request, operation
        )
        reference_from_pose, neutral_reference, binding = _root_reference(
            action, armature, root
        )
        paths = _transform_paths(affected)
        track_animation_data(armature, label="root motion Action blending")
        track_scene_frames(scene, label="root motion frame")
        track_pose(armature, label="root motion pose")
        track_id_properties(action, label="root motion metadata")
        track_action_curves(action, armature, paths, label="root motion curves")
        sample_paths = set(subtree_paths)
        if operation == "extract":
            ancestor = source
            while ancestor is not None:
                sample_paths.update(_transform_paths((ancestor,)))
                ancestor = ancestor.parent
        curves = [
            curve
            for curve in get_action_fcurves(action, armature) or ()
            if curve.data_path in sample_paths
        ]
        key_frames = (
            np.concatenate([curve_key_frames(curve) for curve in curves])
            if curves
            else ()
        )
        requested_type = (
            str(action.get("rootMotionType", "Unknown"))
            if request.export_type == "AUTO"
            else request.export_type
        )
        dense = (
            len(affected) > 1
            or operation in {"inspect", "format"}
            or requested_type.endswith(("EveryFrame", "AllFrames"))
        )
        frames = motion_frame_sequence(
            start, end, 1 if dense else request.step, key_frames
        )
        data.use_nla = False
        data.action_blend_type = "REPLACE"
        data.action_influence = 1.0
        names = tuple(
            dict.fromkeys(
                [bone.name for bone in affected]
                + ([source.name] if operation == "extract" else [])
            )
        )
        sampled = sample_pose_matrices(context, armature, names, frames)
        samples, motion = root_motion_samples(
            root.name,
            np.asarray(root.bone.matrix_local, dtype=np.float64),
            tuple(
                (child.name, np.asarray(child.bone.matrix_local, dtype=np.float64))
                for child in affected[1:]
            ),
            sampled,
            reference_from_pose,
            neutral_reference,
            source_name=source.name if source is not None else "",
            translation_axes=request.translation_axes,
            rotation_mode=request.rotation_mode,
            operation=operation,
            frames=frames,
            edit_options=options.as_kwargs() if options is not None else {},
        )
        summary = motion_summary(motion, frames)
        if operation == "inspect":
            restore_context()
            return OperationResult(
                True,
                "Motion checked",
                details={**summary, "report": _motion_report(summary)},
            )
        output_type = (
            "None"
            if operation in {"integrate", "remove"}
            else choose_motion_format(
                motion,
                str(action.get("rootMotionType", "Unknown")),
                request.export_type,
            )
        )
        if operation != "format":
            remove_fcurves(action, armature, lambda curve: curve.data_path in paths)
            for bone in affected:
                bone.rotation_mode = "QUATERNION"
            write_pose_bone_samples(
                action, armature, frames, samples, interpolation="LINEAR"
            )
            action["cp77_direct_anim_duration_seconds"] = float(end - start) / FPS
            action["cp77_direct_anim_frame_count"] = int(np.ceil(end - start)) + 1
            _invalidate_source_channels(action, armature, binding, affected)
        action["rootMotionType"] = output_type
        context.view_layer.update()
        restore_context()
    except Exception as error:
        _LOG.error(
            "Root motion %s failed on '%s': %s",
            operation,
            action.name,
            error,
            exc_info=True,
        )
        return OperationResult(False, f"Root motion failed: {error}", "ERROR")
    return OperationResult(
        True,
        f"Root motion {_VERBS[operation]}",
        details={
            **summary,
            "frames": len(frames),
            "bones": len(affected),
            "format": output_type,
            "report": _motion_report(summary),
        },
    )


def select_root_curves(armature, request):
    root = armature.pose.bones.get(request.root_bone)
    if root is None:
        return OperationResult(False, "Choose a root bone.", "ERROR")
    paths = _transform_paths((root,))
    for bone in armature.pose.bones:
        bone.select = bone.name == root.name
    armature.data.bones.active = root.bone
    count = 0
    for curve in get_action_fcurves(armature.animation_data.action, armature) or ():
        selected = curve.data_path in paths
        curve.select = selected
        if selected:
            curve.hide = False
            if curve.group is not None:
                curve.group.show_expanded = True
            count += 1
        for point in curve.keyframe_points:
            point.select_control_point = selected
            point.select_left_handle = selected
            point.select_right_handle = selected
    return OperationResult(True, f"Selected {count} root curves")


@transactional("Action duplicate")
def duplicate_action(armature) -> OperationResult:
    """Assign an editable copy of the armature's action, keeping the slot and source metadata"""
    track_animation_data(armature, label="duplicated Action")
    action = armature.animation_data.action
    identifier, handle = action_slot_identity(armature.animation_data)
    duplicate = action.copy()
    duplicate.name = f"{action.name}_motion"
    duplicate.use_fake_user = True
    assign_action_with_slot(
        armature, duplicate, slot_identifier=identifier, slot_handle=handle
    )
    return OperationResult(True, details={"action": duplicate})
