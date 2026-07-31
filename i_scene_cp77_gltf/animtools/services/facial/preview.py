from __future__ import annotations

from typing import Tuple

import numpy as np

from ....animation.blender_pose import apply_bound_red_local_deltas
from .session import FacialSession


def _part(session: FacialSession, part_name: str):
    return getattr(session.setup, part_name, None)


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


def _part_bone_names(session: FacialSession, part) -> tuple[str, ...]:
    indices = set()
    for poses in (part.main_poses, part.corrective_poses):
        if poses.num_poses > 0:
            indices.update(poses.pose_bones.tolist())
    return tuple(
        str(session.rig.bone_names[index])
        for index in sorted(indices)
        if index < session.rig.num_bones
    )


def _reset_bones(session: FacialSession, names) -> None:
    for name in names:
        pose_bone = session.used_pose_bone_map.get(name)
        if pose_bone is not None:
            pose_bone.matrix_basis.identity()


def _tag_redraw(context) -> None:
    screen = getattr(context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def apply_pose(session: FacialSession, part_name: str, pose_index: int, context) -> Tuple[bool, str]:
    part = _part(session, part_name)
    if part is None:
        return False, f"Unknown part '{part_name}'"
    if pose_index < 0 or pose_index >= part.num_main_poses:
        return False, f"Pose index {pose_index} is outside '{part_name}'"
    if not session.preview_snapshot:
        session.preview_snapshot = _snapshot_pose(session)
    _reset_bones(session, _part_bone_names(session, part))
    bone_quats = np.zeros((session.rig.num_bones, 4), dtype=np.float32)
    bone_quats[:, 3] = 1.0
    bone_trans = np.zeros((session.rig.num_bones, 3), dtype=np.float32)
    target_pose = int(part.ib_row_ptr[pose_index + 1]) - 1
    start = int(part.main_poses.row_ptr[target_pose])
    end = int(part.main_poses.row_ptr[target_pose + 1])
    if end > start:
        bones = part.main_poses.pose_bones[start:end].astype(int)
        bone_quats[bones] = part.main_poses.pose_quats[start:end]
        bone_trans[bones] = part.main_poses.pose_trans[start:end]
    written = apply_bound_red_local_deltas(
        session.armature,
        session.used_pose_bones,
        session.used_bone_indices,
        bone_quats,
        bone_trans,
    )
    session.active_pose = (part_name, pose_index)
    _tag_redraw(context)
    track_name = session.track_names[int(part.main_tracks[pose_index])]
    return True, f"Preview: {part_name}[{pose_index}] '{track_name}' — {written} bone(s)"


def clear_preview(session: FacialSession, context) -> Tuple[bool, str]:
    if session.preview_snapshot:
        _restore_pose(session)
        message = "Preview cleared — pose restored"
    else:
        _reset_bones(session, session.used_bone_names)
        message = "Preview cleared — bones reset to rest"
    session.preview_snapshot.clear()
    session.active_pose = None
    _tag_redraw(context)
    return True, message


def has_preview(session: FacialSession | None) -> bool:
    return bool(session and session.has_preview)
