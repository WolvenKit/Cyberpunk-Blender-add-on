from __future__ import annotations

from ...animation.domain.facial.poses import main_pose_deltas, part_pose_bone_indices
from ...blender.facial.session import FacialSession
from ...blender.pose import apply_bound_red_local_deltas


def _snapshot_pose(session: FacialSession) -> dict:
    snapshot = {}
    for name, pose_bone in session.used_pose_bone_map.items():
        if pose_bone is not None:
            snapshot[name] = (pose_bone.matrix_basis.copy(), pose_bone.rotation_mode)
    return snapshot


def _restore_pose(session: FacialSession) -> None:
    for name, (matrix_basis, rotation_mode) in session.preview_snapshot.items():
        pose_bone = session.used_pose_bone_map.get(name)
        if pose_bone is not None:
            pose_bone.matrix_basis = matrix_basis
            pose_bone.rotation_mode = rotation_mode


def _reset_bones(session: FacialSession, names) -> None:
    for name in names:
        pose_bone = session.used_pose_bone_map.get(name)
        if pose_bone is not None:
            pose_bone.matrix_basis.identity()


def apply_main_pose(
    session: FacialSession, part_name: str, pose_index: int
) -> tuple[bool, str]:
    part = getattr(session.setup, part_name, None)
    if part is None:
        return False, f"Unknown part '{part_name}'"
    if pose_index < 0 or pose_index >= part.num_main_poses:
        return False, f"Pose index {pose_index} is outside '{part_name}'"
    if not session.preview_snapshot:
        session.preview_snapshot = _snapshot_pose(session)
    num_bones = session.rig.num_bones
    _reset_bones(
        session,
        (
            str(session.rig.bone_names[index])
            for index in part_pose_bone_indices(part, num_bones)
        ),
    )
    bone_quats, bone_trans = main_pose_deltas(part, pose_index, num_bones)
    written = apply_bound_red_local_deltas(
        session.armature,
        session.used_pose_bones,
        session.used_bone_indices,
        bone_quats,
        bone_trans,
        session.used_pose_collection_indices,
    )
    session.active_pose = (part_name, pose_index)
    track_name = session.track_names[int(part.main_tracks[pose_index])]
    return (
        True,
        f"Preview: {part_name}[{pose_index}] '{track_name}' — {written} bone(s)",
    )


def clear_preview(session: FacialSession) -> tuple[bool, str]:
    if session.preview_snapshot:
        _restore_pose(session)
        message = "Preview cleared — pose restored"
    else:
        _reset_bones(session, session.used_bone_names)
        message = "Preview cleared — bones reset to rest"
    session.preview_snapshot.clear()
    session.active_pose = None
    return True, message
