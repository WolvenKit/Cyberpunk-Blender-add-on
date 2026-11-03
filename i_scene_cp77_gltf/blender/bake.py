from __future__ import annotations

import numpy as np

from ..animation.domain.clip.bake import (
    PoseBoneSamples,
    rotation_width,
    stabilize_rotations,
)
from .keyframes import ensure_fcurve, replace_fcurve_keyframes


def _rotation_path(pose_bone) -> str:
    mode = str(pose_bone.rotation_mode)
    if mode == "QUATERNION":
        return "rotation_quaternion"
    if mode == "AXIS_ANGLE":
        return "rotation_axis_angle"
    return "rotation_euler"


def _rotation_values(pose_bone, data_path: str):
    if data_path == "rotation_quaternion":
        return pose_bone.rotation_quaternion
    if data_path == "rotation_axis_angle":
        return pose_bone.rotation_axis_angle
    return pose_bone.rotation_euler


def sample_pose_bones(
    scene,
    armature,
    bone_names,
    frames,
    before_sample=None,
    rotation_path_override: str | None = None,
):
    frames = np.asarray(frames, dtype=np.float64)
    bones = []
    for name in bone_names:
        bone = armature.pose.bones.get(str(name))
        if bone is not None:
            bones.append(bone)
    samples = []
    for bone in bones:
        data_path = rotation_path_override or _rotation_path(bone)
        samples.append(
            PoseBoneSamples(
                bone.name,
                np.empty((len(frames), 3), dtype=np.float64),
                np.empty((len(frames), rotation_width(data_path)), dtype=np.float64),
                np.empty((len(frames), 3), dtype=np.float64),
                data_path,
            )
        )
    for frame_index, frame in enumerate(frames):
        whole_frame = int(np.floor(frame))
        scene.frame_set(whole_frame, subframe=float(frame - whole_frame))
        if before_sample is not None:
            before_sample(float(frame))
        for bone, sample in zip(bones, samples):
            sample.locations[frame_index] = bone.location
            sample.rotations[frame_index] = _rotation_values(bone, sample.rotation_path)
            sample.scales[frame_index] = bone.scale
    for sample in samples:
        sample.rotations = stabilize_rotations(sample.rotations, sample.rotation_path)
    return samples


def write_vector_channels(
    action,
    id_data,
    data_path: str,
    frames,
    values,
    *,
    group_name: str = "",
    interpolation: str = "BEZIER",
    replace_range=None,
    replace_frames: bool = False,
    collapse_constant: bool = False,
) -> int:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("values must have shape [frames, components]")
    written = 0
    for component in range(values.shape[1]):
        curve = ensure_fcurve(action, id_data, data_path, component, group_name)
        written += replace_fcurve_keyframes(
            curve,
            frames,
            values[:, component],
            interpolation,
            replace_range=replace_range,
            replace_frames=replace_frames,
            collapse_constant=collapse_constant,
        )
    return written


def write_pose_bone_samples(
    action,
    armature,
    frames,
    samples,
    *,
    interpolation: str = "BEZIER",
    replace_range=None,
    replace_frames: bool = False,
    collapse_constant: bool = False,
    include_location: bool = True,
    include_rotation: bool = True,
    include_scale: bool = True,
) -> int:
    written = 0
    for sample in samples:
        prefix = armature.pose.bones[sample.bone_name].path_from_id()
        if include_location:
            written += write_vector_channels(
                action,
                armature,
                f"{prefix}.location",
                frames,
                sample.locations,
                group_name=sample.bone_name,
                interpolation=interpolation,
                replace_range=replace_range,
                replace_frames=replace_frames,
                collapse_constant=collapse_constant,
            )
        if include_rotation:
            written += write_vector_channels(
                action,
                armature,
                f"{prefix}.{sample.rotation_path}",
                frames,
                sample.rotations,
                group_name=sample.bone_name,
                interpolation=interpolation,
                replace_range=replace_range,
                replace_frames=replace_frames,
                collapse_constant=collapse_constant,
            )
        if include_scale:
            written += write_vector_channels(
                action,
                armature,
                f"{prefix}.scale",
                frames,
                sample.scales,
                group_name=sample.bone_name,
                interpolation=interpolation,
                replace_range=replace_range,
                replace_frames=replace_frames,
                collapse_constant=collapse_constant,
            )
    return written


def sample_pose_matrices(context, armature, names, frames) -> dict[str, np.ndarray]:
    """Evaluated model-space matrices of the named pose bones at each (sub)frame"""
    depsgraph = context.evaluated_depsgraph_get()
    matrices = {name: np.empty((len(frames), 4, 4), dtype=np.float64) for name in names}
    for index, frame in enumerate(frames):
        whole = int(np.floor(frame))
        context.scene.frame_set(whole, subframe=float(frame - whole))
        evaluated = armature.evaluated_get(depsgraph)
        for name in names:
            matrices[name][index] = np.asarray(
                evaluated.pose.bones[name].matrix, dtype=np.float64
            )
    return matrices
