from __future__ import annotations

<<<<<<< Updated upstream
import numpy as np
from mathutils import Matrix, Vector

from ...animation.bake import frame_sequence, write_pose_bone_samples
from ...animation.keyframes import remove_bone_fcurves
from ...animation.root_motion import action_frame_range, identity_samples, pose_samples
from ..model import OperationResult, RootMotionRequest


def animated_armature(context):
    armature = getattr(context, "active_object", None)
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return None
    if not armature.pose or len(armature.pose.bones) < 2:
=======
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
>>>>>>> Stashed changes
        return None
    if not armature.animation_data or armature.animation_data.action is None:
        return None
    return armature


<<<<<<< Updated upstream
def default_request(context, armature=None) -> tuple[object | None, RootMotionRequest | None, int, int]:
    armature = armature or animated_armature(context)
    if armature is None:
        return None, None, 0, 0
    data = context.scene.rm_data
    if not data.root or data.root not in armature.pose.bones:
        data.root = next(iter(armature.pose.bones)).name
    if not data.hip or data.hip not in armature.pose.bones:
        data.hip = list(armature.pose.bones)[1].name if len(armature.pose.bones) > 1 else data.root
    start, end = action_frame_range(armature.animation_data.action)
    request = RootMotionRequest(
        root_bone=data.root,
        hip_bone=data.hip,
        step=max(1, int(data.step)),
        include_vertical=bool(data.do_vert),
        include_rotation=not bool(data.no_rot),
    )
    return armature, request, start, end


def extract_root_motion(context, armature, request: RootMotionRequest, start: int, end: int) -> OperationResult:
    try:
        frames = frame_sequence(start, end, request.step)
        hip, world_matrices, directions = _sample_hip(context, armature, request.hip_bone, frames)
        root = armature.pose.bones[request.root_bone]
        initial_world = world_matrices[0]
        initial_direction = directions[-1]
        inverse_armature = armature.matrix_world.to_3x3().inverted_safe()
        inverse_root_rest = root.bone.matrix_local.to_3x3().inverted_safe()

        locations = np.empty((len(frames), 3), dtype=np.float64)
        rotations = np.empty((len(frames), 4), dtype=np.float64)
        scales = np.ones((len(frames), 3), dtype=np.float64)
        remove_bone_fcurves(armature.animation_data.action, armature, request.hip_bone)
        for index, (frame, world_matrix) in enumerate(zip(frames, world_matrices)):
            context.scene.frame_set(int(frame))
            delta = world_matrix.translation - initial_world.translation
            if not request.include_vertical:
                delta.z = 0.0
            locations[index] = tuple(inverse_root_rest @ (inverse_armature @ delta))
            direction = (hip.head - hip.tail).copy()
            direction.z = 0.0
            rotations[index] = tuple(initial_direction.rotation_difference(direction))

        samples = pose_samples(request.root_bone, locations, rotations, scales)
        write_pose_bone_samples(
            armature.animation_data.action,
            armature,
            frames,
            (samples,),
            interpolation="BEZIER",
            replace_frames=True,
            include_rotation=request.include_rotation,
        )
        root.location = tuple(locations[-1])
        if request.include_rotation:
            root.rotation_mode = "QUATERNION"
            root.rotation_quaternion = tuple(samples.rotations[-1])
        root.scale = Vector((1.0, 1.0, 1.0))
        context.view_layer.update()
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Root motion failed: {exc}", "ERROR")
    return OperationResult(True, f"Root motion extracted ({len(frames)} frames)", details={"frames": len(frames)})


def integrate_root_motion(context, armature, request: RootMotionRequest, start: int, end: int) -> OperationResult:
    try:
        frames = frame_sequence(start, end, request.step)
        hip, world_matrices, _ = _sample_hip(context, armature, request.hip_bone, frames)
        root = armature.pose.bones[request.root_bone]
        action = armature.animation_data.action
        remove_bone_fcurves(action, armature, request.root_bone)
        remove_bone_fcurves(action, armature, request.hip_bone)

        locations = np.empty((len(frames), 3), dtype=np.float64)
        rotations = np.empty((len(frames), 4), dtype=np.float64)
        scales = np.empty((len(frames), 3), dtype=np.float64)
        for index, (frame, world_matrix) in enumerate(zip(frames, world_matrices)):
            context.scene.frame_set(int(frame))
            hip.matrix = _pose_matrix(armature, hip, world_matrix)
            locations[index] = tuple(hip.location)
            rotations[index] = tuple(hip.rotation_quaternion)
            scales[index] = tuple(hip.scale)

        write_pose_bone_samples(
            action,
            armature,
            frames,
            (pose_samples(request.hip_bone, locations, rotations, scales),),
            interpolation="BEZIER",
        )
        write_pose_bone_samples(
            action,
            armature,
            np.asarray((start, end), dtype=np.float64),
            (identity_samples(request.root_bone, 2),),
            interpolation="BEZIER",
        )
        _reset_root(root)
        context.view_layer.update()
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Integration failed: {exc}", "ERROR")
    return OperationResult(True, f"Motion integrated ({len(frames)} frames)", details={"frames": len(frames)})


def remove_root_motion(context, armature, root_bone: str) -> OperationResult:
    if root_bone not in armature.pose.bones:
        return OperationResult(False, f"Root bone '{root_bone}' missing", "ERROR")
    start, end = action_frame_range(armature.animation_data.action)
    action = armature.animation_data.action
    remove_bone_fcurves(action, armature, root_bone)
    frames = np.asarray((start, end), dtype=np.float64)
    write_pose_bone_samples(
        action,
        armature,
        frames,
        (identity_samples(root_bone, 2),),
        interpolation="BEZIER",
    )
    _reset_root(armature.pose.bones[root_bone])
    context.view_layer.update()
    return OperationResult(True, "Root motion removed (in-place)")


def _world_matrix(armature, bone):
    return armature.convert_space(
        pose_bone=bone,
        matrix=bone.matrix,
        from_space="POSE",
        to_space="WORLD",
    )


def _pose_matrix(armature, bone, matrix: Matrix):
    return armature.convert_space(
        pose_bone=bone,
        matrix=matrix,
        from_space="WORLD",
        to_space="POSE",
    )


def _sample_hip(context, armature, bone_name: str, frames):
    bone = armature.pose.bones.get(bone_name)
    if bone is None:
        raise ValueError(f"Bone '{bone_name}' not found")
    world_matrices = []
    directions = []
    for frame in frames:
        context.scene.frame_set(int(frame))
        world_matrices.append(_world_matrix(armature, bone).copy())
        direction = (bone.head - bone.tail).copy()
        direction.z = 0.0
        directions.append(direction)
    return bone, world_matrices, directions


def _reset_root(root) -> None:
    root.location = (0.0, 0.0, 0.0)
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    root.scale = (1.0, 1.0, 1.0)
=======
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
>>>>>>> Stashed changes
