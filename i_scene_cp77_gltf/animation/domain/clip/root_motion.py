from __future__ import annotations

import numpy as np

from ....bartmoss.curve import sample_frame_grid
from ....bartmoss.quaternion import (
    continuous_wxyz,
    matrix_from_xyzw,
    normalize_sequence_xyzw,
    wxyz_from_xyzw,
)
from ....bartmoss.trs import compose_matrices, decompose_matrices
from ....redSpace.transforms import gltf_relative_to_blender
from ...model.clip.metadata import FPS, ROOT_MOTION_TYPES
from .bake import PoseBoneSamples


def pose_samples(bone_name, locations, rotations, scales):
    return PoseBoneSamples(
        bone_name,
        np.asarray(locations, dtype=np.float64),
        continuous_wxyz(rotations),
        np.asarray(scales, dtype=np.float64),
        "rotation_quaternion",
    )


def motion_frame_sequence(start, end, step=1, key_frames=()):
    step = max(1, int(step))
    keys = np.asarray(key_frames, dtype=np.float64)
    return sample_frame_grid(float(start) / step, float(end) / step, keys / step) * step


def extract_motion_matrices(
    source_matrices, *, translation_axes=(True, True, True), rotation_mode="YAW"
):
    matrices = np.asarray(source_matrices, dtype=np.float64)
    if matrices.ndim != 3 or matrices.shape[1:] != (4, 4) or not len(matrices):
        raise ValueError("Root motion requires a nonempty sequence of pose matrices.")
    if not np.all(np.isfinite(matrices)):
        raise ValueError("Root motion pose matrices must be finite.")
    positions, rotations, scales = decompose_matrices(matrices)
    if np.any(scales <= 1e-8):
        raise ValueError("The motion source has mirrored or singular scale.")
    if not np.allclose(
        matrices, compose_matrices(positions, rotations, scales), rtol=1e-5, atol=1e-6
    ):
        raise ValueError("The motion source contains shear or a non-affine transform.")
    motion = np.broadcast_to(np.eye(4), matrices.shape).copy()
    if rotation_mode != "NONE":
        axes = np.asarray([matrix_from_xyzw(value)[:3, :3] for value in rotations])
        delta = axes @ axes[0].T
        if rotation_mode == "FULL":
            motion[:, :3, :3] = delta
        elif rotation_mode == "YAW":
            motion[:, :3, :3] = yaw_matrices(motion_yaw(delta))
        else:
            raise ValueError("Choose a rotation mode.")
    motion[:, :3, 3] = positions - np.einsum(
        "nij,j->ni", motion[:, :3, :3], positions[0]
    )
    motion[:, np.flatnonzero(~np.asarray(translation_axes, dtype=bool)), 3] = 0.0
    motion[0] = np.eye(4)
    return motion


def compensated_child_basis(root_rest, child_rest, new_root_matrices, child_matrices):
    root_rest = np.asarray(root_rest, dtype=np.float64)
    child_rest = np.asarray(child_rest, dtype=np.float64)
    relative_rest = np.linalg.solve(root_rest, child_rest)
    relative_pose = np.linalg.solve(new_root_matrices, child_matrices)
    return np.linalg.solve(relative_rest, relative_pose)


def matrix_pose_samples(bone_name, matrices):
    matrices = np.asarray(matrices, dtype=np.float64)
    if not np.all(np.isfinite(matrices)):
        raise ValueError(f"Bone {bone_name!r} has non-finite motion transforms.")
    locations, rotations, scales = decompose_matrices(matrices)
    reconstructed = compose_matrices(locations, rotations, scales)
    if np.any(np.abs(scales) <= 1e-8) or not np.allclose(
        matrices, reconstructed, rtol=1e-5, atol=1e-6
    ):
        raise ValueError(
            f"Bone {bone_name!r} requires a singular or sheared pose that cannot be keyed as TRS."
        )
    return pose_samples(bone_name, locations, wxyz_from_xyzw(rotations), scales)


MOTION_EXPORT_ITEMS = (
    (
        "AUTO",
        "Keep / Auto",
        "Keep a compatible format; otherwise use linear transforms",
    ),
    (
        "TransformLinearSparseFrames",
        "Linear Transforms",
        "Sparse translation and full rotation",
    ),
    (
        "TransformSplineSparseFrames",
        "Spline Transforms",
        "Spline-compressed translation and full rotation",
    ),
    (
        "TransformLinearEveryFrame",
        "Full Transforms",
        "Translation and full rotation at every frame",
    ),
    (
        "TranslationWithYawAllFrames",
        "3D + Yaw",
        "XYZ translation and yaw at every frame",
    ),
    (
        "TranslationPlaneWithYawAllFrames",
        "2D + Yaw",
        "XY translation and yaw at every frame",
    ),
)


ROOT_MOTION_EXPORT_ITEMS = (
    (
        "CLIP",
        "Use Clip Settings",
        "Use each clip root-motion flag and export motion with linear transform storage",
    ),
    (
        "EXPORT",
        "Export Root Motion",
        "Store existing translation and rotation on the first rig joint as root motion",
    ),
    (
        "DISABLED",
        "Disable Root Motion",
        "Remove native root motion when WolvenKit imports these clips; keep root-bone animation as regular transforms",
    ),
)


def root_motion_type_for_export(existing, mode="CLIP", *, has_root_transforms):
    """Resolve clip intent to a WolvenKit encoding without changing the source action"""
    if mode not in {item[0] for item in ROOT_MOTION_EXPORT_ITEMS}:
        raise ValueError("Choose a supported root-motion export setting.")
    if existing not in ROOT_MOTION_TYPES:
        raise ValueError("The clip has an unsupported rootMotionType.")
    if mode == "DISABLED":
        return "None"
    if mode == "CLIP" and existing in {"Unknown", "None"}:
        return existing
    if not has_root_transforms:
        if mode == "CLIP":
            raise ValueError(
                "The clip declares root motion but has no translation or rotation on the first rig joint."
            )
        return "None"
    return "TransformLinearSparseFrames"


def _rigid_motion(matrices):
    matrices = np.asarray(matrices, dtype=np.float64)
    if matrices.ndim != 3 or matrices.shape[1:] != (4, 4) or not len(matrices):
        raise ValueError("Motion requires a nonempty sequence of transforms.")
    matrix_pose_samples("root", matrices)
    axes = matrices[:, :3, :3]
    if not np.allclose(np.swapaxes(axes, 1, 2) @ axes, np.eye(3), atol=1e-5) or np.any(
        np.linalg.det(axes) <= 0
    ):
        raise ValueError("Motion must contain rigid transforms with unit scale.")
    return matrices


def motion_yaw(rotations):
    rotations = np.asarray(rotations, dtype=np.float64)
    sine = rotations[:, 1, 0] - rotations[:, 0, 1]
    cosine = rotations[:, 0, 0] + rotations[:, 1, 1]
    if np.any(np.hypot(sine, cosine) <= 1e-8):
        raise ValueError("Heading is undefined at an inverted pose; use full rotation.")
    return np.unwrap(np.arctan2(sine, cosine))


def yaw_matrices(angles):
    angles = np.asarray(angles, dtype=np.float64).reshape(-1)
    result = np.broadcast_to(np.eye(3), (len(angles), 3, 3)).copy()
    c, s = np.cos(angles), np.sin(angles)
    result[:, 0, 0] = result[:, 1, 1] = c
    result[:, 0, 1] = -s
    result[:, 1, 0] = s
    return result


def validate_motion_format(matrices, format_name):
    if format_name not in {item[0] for item in MOTION_EXPORT_ITEMS[1:]}:
        raise ValueError("Choose a supported motion export format.")
    matrices = _rigid_motion(matrices)
    if format_name in {
        "TranslationWithYawAllFrames",
        "TranslationPlaneWithYawAllFrames",
    }:
        angles = motion_yaw(matrices[:, :3, :3])
        if not np.allclose(matrices[:, :3, :3], yaw_matrices(angles), atol=1e-5):
            raise ValueError(
                "This motion has pitch or roll. Use a full-transform format or Keep Channels with Yaw."
            )
    if format_name == "TranslationPlaneWithYawAllFrames" and not np.allclose(
        matrices[:, 2, 3], 0.0, atol=1e-5
    ):
        raise ValueError(
            "This motion has vertical travel. Use 3D storage or Keep Channels with Z disabled."
        )


def choose_motion_format(matrices, existing, requested="AUTO"):
    if requested != "AUTO":
        validate_motion_format(matrices, requested)
        return requested
    try:
        validate_motion_format(matrices, existing)
        return existing
    except ValueError:
        validate_motion_format(matrices, "TransformLinearSparseFrames")
        return "TransformLinearSparseFrames"


def edit_motion_matrices(
    matrices,
    frames,
    operation,
    *,
    translation_axes=(True, True, True),
    rotation_mode="YAW",
    scale=(1.0, 1.0, 1.0),
    direction=0.0,
    turn_scale=1.0,
    displacement=(0.0, 1.0, 0.0),
    turn=0.0,
    smooth_radius=3.0,
):
    source = _rigid_motion(matrices)
    result = source.copy()
    frames = np.asarray(frames, dtype=np.float64)
    if (
        frames.shape != (len(source),)
        or not np.all(np.isfinite(frames))
        or np.any(np.diff(frames) <= 0)
    ):
        raise ValueError("Motion sample times must be finite and increasing.")
    if rotation_mode not in {"NONE", "YAW", "FULL"}:
        raise ValueError("Choose a rotation mode.")
    axes = np.asarray(translation_axes, dtype=bool)
    if axes.shape != (3,):
        raise ValueError("Choose three translation channels.")
    if operation == "ZERO":
        result = np.linalg.solve(source[0], source)
    elif operation == "SCALE":
        scale = np.asarray(scale, dtype=np.float64)
        if (
            scale.shape != (3,)
            or not np.all(np.isfinite(scale))
            or not np.isfinite(direction)
            or not np.isfinite(turn_scale)
        ):
            raise ValueError("Travel and turn settings must be finite.")
        offset = (source[:, :3, 3] - source[0, :3, 3]) * scale
        result[:, :3, 3] = source[0, :3, 3] + offset @ yaw_matrices([direction])[0].T
        if turn_scale != 1.0:
            yaw = motion_yaw(source[:, :3, :3] @ source[0, :3, :3].T)
            if np.any(np.abs(np.diff(yaw) * turn_scale) >= np.pi):
                raise ValueError(
                    "The scaled turn exceeds 180 degrees between samples. Reduce Sample Step or Turn Scale."
                )
            result[:, :3, :3] = (
                yaw_matrices(yaw * (turn_scale - 1.0)) @ source[:, :3, :3]
            )
    elif operation == "GENERATE":
        displacement = np.asarray(displacement, dtype=np.float64)
        if (
            displacement.shape != (3,)
            or not np.all(np.isfinite(displacement))
            or not np.isfinite(turn)
        ):
            raise ValueError("Travel and turn must be finite.")
        duration = frames[-1] - frames[0]
        if duration <= 0:
            raise ValueError("Creating motion requires an action with a duration.")
        progress = (frames - frames[0]) / duration
        if np.any(np.abs(np.diff(progress) * turn) >= np.pi):
            raise ValueError(
                "The turn exceeds 180 degrees between samples. Reduce Sample Step or extend the action."
            )
        result[:, :3, 3] = source[0, :3, 3] + progress[:, None] * displacement
        result[:, :3, :3] = yaw_matrices(progress * turn) @ source[0, :3, :3]
    elif operation == "FILTER":
        result[:, np.flatnonzero(~axes), 3] = 0.0
        if rotation_mode == "NONE":
            result[:, :3, :3] = np.eye(3)
        elif rotation_mode == "YAW":
            result[:, :3, :3] = yaw_matrices(motion_yaw(source[:, :3, :3]))
    elif operation == "SMOOTH":
        if not np.isfinite(smooth_radius) or smooth_radius <= 0:
            raise ValueError("Smoothing radius must be positive.")
        positions, rotations, scales = decompose_matrices(source)
        yaw = motion_yaw(source[:, :3, :3]) if rotation_mode == "YAW" else None
        rotations = normalize_sequence_xyzw(rotations)
        for index in range(1, len(frames) - 1):
            first, last = np.searchsorted(
                frames, [frames[index] - smooth_radius, frames[index] + smooth_radius]
            )
            weights = np.maximum(
                0.0, 1.0 - np.abs(frames[first:last] - frames[index]) / smooth_radius
            )
            weights /= np.sum(weights)
            result[index, :3, 3][axes] = (weights @ positions[first:last])[axes]
            if rotation_mode == "YAW":
                correction = float(weights @ yaw[first:last] - yaw[index])
                result[index, :3, :3] = (
                    yaw_matrices([correction])[0] @ source[index, :3, :3]
                )
            elif rotation_mode == "FULL":
                window = rotations[first:last].copy()
                window[np.einsum("ij,j->i", window, rotations[index]) < 0] *= -1
                averaged = weights @ window
                averaged /= np.linalg.norm(averaged)
                result[index, :3, :3] = matrix_from_xyzw(averaged)[:3, :3]
    else:
        raise ValueError(f"Unknown motion edit: {operation}")
    return _rigid_motion(result)


def motion_summary(matrices, frames):
    matrices = _rigid_motion(matrices)
    duration = float(frames[-1] - frames[0]) / FPS
    positions = matrices[:, :3, 3]
    distance = float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum())
    try:
        yaw = motion_yaw(matrices[:, :3, :3])
        turn = float(yaw[-1] - yaw[0])
    except ValueError:
        turn = None
    return {
        "duration": duration,
        "distance": distance,
        "speed": distance / duration if duration > 0 else 0.0,
        "displacement": tuple(positions[-1] - positions[0]),
        "turn": turn,
        "start_offset": float(np.linalg.norm(positions[0])),
        "start_angle": float(
            np.arccos(np.clip((np.trace(matrices[0, :3, :3]) - 1.0) / 2.0, -1.0, 1.0))
        ),
    }


def root_motion_reference(
    rest,
    names,
    *,
    root_name: str,
    first_joint_target: str,
    num_extra_joints: int,
    parents=(),
    source_rest=None,
    source_rest_contract: str = "",
):
    """(reference_from_pose, neutral_reference) mapping the root bone's model matrix to motion space"""
    rest = np.asarray(rest, dtype=np.float64)
    if not names:
        return np.eye(4), rest
    if first_joint_target != root_name:
        raise ValueError(
            f"Root motion must target source joint 0 ({names[0]!r}) for this action."
        )
    if int(num_extra_joints) >= len(names):
        raise ValueError("The action has no base joint available for root motion.")
    if parents and int(parents[0]) != -1:
        raise ValueError("The action's source root is not a top-level joint.")
    reference_rest = rest
    if source_rest:
        if source_rest.get("space") != source_rest_contract or tuple(
            source_rest.get("boneNames", ())
        ) != tuple(names):
            raise ValueError(
                "The action's source rest-pose metadata does not match its skin."
            )
        matrices = np.asarray(source_rest.get("matrices"), dtype=np.float64).reshape(
            len(names), 4, 4
        )
        reference_rest = matrices[0]
    for matrix in (rest, reference_rest):
        axes = matrix[:3, :3]
        if (
            not np.all(np.isfinite(matrix))
            or not np.allclose(axes.T @ axes, np.eye(3), atol=1e-5)
            or np.linalg.det(axes) <= 0.0
        ):
            raise ValueError(
                "Root motion requires rigid, orientation-preserving root rest transforms."
            )
    reference_from_pose = reference_rest @ np.linalg.inv(rest)
    # The root bone's Blender model matrix when its glTF model transform is identity.
    neutral_reference = gltf_relative_to_blender(np.eye(4), is_root=True)
    return reference_from_pose, neutral_reference


def root_motion_samples(
    root_name,
    root_rest,
    child_rests,
    sampled,
    reference_from_pose,
    neutral_reference,
    *,
    source_name,
    translation_axes,
    rotation_mode,
    operation,
    frames,
    edit_options,
):
    """New basis samples for the root and its compensated children, and the resulting motion matrices"""
    root_rest = np.asarray(root_rest, dtype=np.float64)
    root_basis = np.linalg.solve(root_rest, sampled[root_name])
    root_state = matrix_pose_samples(root_name, root_basis)
    if not np.allclose(root_state.scales, 1.0, atol=1e-5):
        raise ValueError("Root motion requires unit root scale.")
    existing_motion = (
        reference_from_pose @ sampled[root_name] @ np.linalg.inv(neutral_reference)
    )
    if operation == "extract":
        source_reference = reference_from_pose @ sampled[source_name]
        motion = extract_motion_matrices(
            source_reference,
            translation_axes=translation_axes,
            rotation_mode=rotation_mode,
        )
        if rotation_mode == "NONE":
            motion[:, :3, :3] = existing_motion[:, :3, :3]
            motion[:, :3, 3] = source_reference[:, :3, 3] - np.einsum(
                "nij,j->ni", motion[:, :3, :3], source_reference[0, :3, 3]
            )
        for index, enabled in enumerate(translation_axes):
            if not enabled:
                motion[:, index, 3] = existing_motion[:, index, 3]
    elif operation in {"integrate", "remove"}:
        motion = np.broadcast_to(np.eye(4), existing_motion.shape).copy()
    elif operation in {"inspect", "format"}:
        return [], existing_motion
    else:
        motion = edit_motion_matrices(
            existing_motion,
            frames,
            operation,
            translation_axes=translation_axes,
            rotation_mode=rotation_mode,
            **edit_options,
        )
    new_root = np.linalg.solve(reference_from_pose, motion @ neutral_reference)
    samples = [matrix_pose_samples(root_name, np.linalg.solve(root_rest, new_root))]
    for child_name, child_rest in child_rests:
        basis = compensated_child_basis(
            root_rest,
            np.asarray(child_rest, dtype=np.float64),
            new_root,
            sampled[child_name],
        )
        samples.append(matrix_pose_samples(child_name, basis))
    return samples, motion
