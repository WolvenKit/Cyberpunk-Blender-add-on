from __future__ import annotations

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
        return None
    if not armature.animation_data or armature.animation_data.action is None:
        return None
    return armature


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
