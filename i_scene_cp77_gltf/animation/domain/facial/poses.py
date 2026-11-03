from __future__ import annotations

import numpy as np


def part_pose_bone_indices(part, num_bones: int) -> tuple[int, ...]:
    """Sorted rig bone indices that any main or corrective pose of the part moves"""
    indices = set()
    for poses in (part.main_poses, part.corrective_poses):
        if poses.num_poses > 0:
            indices.update(poses.pose_bones.tolist())
    return tuple(index for index in sorted(indices) if index < num_bones)


def main_pose_deltas(
    part, pose_index: int, num_bones: int
) -> tuple[np.ndarray, np.ndarray]:
    """Per-bone local rotations (xyzw) and translations of a main pose at full weight"""
    bone_quats = np.zeros((num_bones, 4), dtype=np.float32)
    bone_quats[:, 3] = 1.0
    bone_trans = np.zeros((num_bones, 3), dtype=np.float32)
    target_pose = int(part.ib_row_ptr[pose_index + 1]) - 1
    start = int(part.main_poses.row_ptr[target_pose])
    end = int(part.main_poses.row_ptr[target_pose + 1])
    if end > start:
        bones = part.main_poses.pose_bones[start:end].astype(int)
        bone_quats[bones] = part.main_poses.pose_quats[start:end]
        bone_trans[bones] = part.main_poses.pose_trans[start:end]
    return bone_quats, bone_trans
