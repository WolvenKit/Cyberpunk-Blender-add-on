from __future__ import annotations

import numpy as np

from ..redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT, RIG_SPACE_CONTRACT_DIRECT

try:
    from mathutils import Matrix
except ImportError:
    Matrix = None


def interpolate_matrix_trs(previous, current, factor):
    previous_location, previous_rotation, previous_scale = previous.decompose()
    current_location, current_rotation, current_scale = current.decompose()
    return Matrix.LocRotScale(
        previous_location.lerp(current_location, factor),
        previous_rotation.slerp(current_rotation, factor),
        previous_scale.lerp(current_scale, factor),
    )


def blend_matrix_trs(current, target, weight):
    if weight <= 0.0:
        return current.copy()
    if weight >= 1.0:
        return target.copy()
    return interpolate_matrix_trs(current, target, weight)


def interpolate_matrix_trs_components(previous, current, factor):
    previous_location, previous_rotation, previous_scale = previous.decompose()
    current_location, current_rotation, current_scale = current.decompose()
    return (
        previous_location.lerp(current_location, factor),
        previous_rotation.slerp(current_rotation, factor),
        previous_scale.lerp(current_scale, factor),
    )


def interpolate_matrix_components(previous, current, factor):
    return (
        previous.translation.lerp(current.translation, factor),
        previous.to_quaternion().slerp(current.to_quaternion(), factor),
    )


def model_matrix_to_basis_explicit(
    pose_bone,
    desired_matrix,
    *,
    parent_matrix=None,
    parent_matrix_local=None,
):
    bone = getattr(pose_bone, "bone", None)
    if bone is None or not hasattr(bone, "convert_local_to_pose"):
        return None
    if parent_matrix is None:
        return bone.convert_local_to_pose(desired_matrix, bone.matrix_local, invert=True)
    return bone.convert_local_to_pose(
        desired_matrix,
        bone.matrix_local,
        parent_matrix=parent_matrix,
        parent_matrix_local=parent_matrix_local,
        invert=True,
    )


def model_matrix_to_basis(pose_bone, desired_matrix, parent_matrix=None):
    parent = pose_bone.parent
    return model_matrix_to_basis_explicit(
        pose_bone,
        desired_matrix,
        parent_matrix=parent_matrix if parent is not None else None,
        parent_matrix_local=parent.bone.matrix_local if parent is not None else None,
    )


def apply_bound_red_local_deltas(
    arm_obj,
    pose_bones,
    bone_indices,
    rotations_xyzw,
    translations,
) -> int:
    contract = str(
        getattr(arm_obj, "data", {}).get(
            "cp77_rig_space_contract",
            RIG_SPACE_CONTRACT_CURRENT,
        )
    )
    if contract not in {RIG_SPACE_CONTRACT_CURRENT, RIG_SPACE_CONTRACT_DIRECT}:
        raise RuntimeError(f"Unsupported rig-space contract: {contract!r}")
    rotations = np.asarray(rotations_xyzw)
    translations = np.asarray(translations)
    current_space = contract == RIG_SPACE_CONTRACT_CURRENT
    written = 0
    for offset, bone_index in enumerate(bone_indices):
        index = int(bone_index)
        pose_bone = pose_bones[offset]
        if pose_bone is None:
            continue
        qx, qy, qz, qw = (float(value) for value in rotations[index])
        tx, ty, tz = (float(value) for value in translations[index])
        if current_space:
            tx, ty, tz = -tz, ty, tx
            qx, qy, qz = -qz, qy, qx
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = (qw, qx, qy, qz)
        pose_bone.location = (tx, ty, tz)
        written += 1
    return written
