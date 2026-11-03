from __future__ import annotations

import math

import numpy as np

from .quaternion import (
    IDENTITY_XYZW,
    axis_angle_scalar_xyzw,
    multiply_scalar_xyzw,
    rotate_vector_unit_scalar_xyzw,
    shortest_rotation_scalar_xyzw,
    slerp_scalar_xyzw,
)
from .vector3 import (
    add3,
    cross3,
    dot3,
    is_parallel3,
    normalized3,
    scale3,
    split_by_normal3,
    sub3,
)

Bone = tuple[
    tuple[float, float, float], tuple[float, float, float, float]
]


def _partial(rotation, weight: float):
    return (
        slerp_scalar_xyzw(IDENTITY_XYZW, rotation, weight) if weight < 1.0 else rotation
    )


def _rotate_about(bone: Bone, pivot, rotation) -> Bone:
    position, orientation = bone
    return (
        add3(pivot, rotate_vector_unit_scalar_xyzw(rotation, sub3(position, pivot))),
        multiply_scalar_xyzw(rotation, orientation),
    )


def solve_two_bone_ik(
    first: Bone,
    second: Bone,
    end: Bone,
    *,
    hinge_axis_local,
    target,
    pole=None,
    end_rotation=None,
    weight: float = 1.0,
    twist_deg: float = 0.0,
    cos_max_hinge: float = -1.0,
    cos_min_hinge: float = 1.0,
    gains: tuple[float, float, float] = (1.0, 1.0, 1.0),
    end_offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    enforce_position: bool = True,
) -> tuple[Bone, Bone, Bone]:
    """Model-space positions and rotations of first, second and end bones reaching target"""
    first_gain, second_gain, end_gain = (float(gain) for gain in gains)
    if not enforce_position:
        if end_rotation is not None:
            end = (end[0], slerp_scalar_xyzw(end[1], end_rotation, weight * end_gain))
        return first, second, end
    first_pos = first[0]
    target = tuple(float(v) for v in target[:3])
    second_pos, second_rot = second
    end_pos = add3(end[0], rotate_vector_unit_scalar_xyzw(end[1], end_offset))

    first_to_second = sub3(second_pos, first_pos)
    second_to_end = sub3(end_pos, second_pos)
    first_to_target = sub3(target, first_pos)
    hinge_axis = normalized3(
        rotate_vector_unit_scalar_xyzw(second_rot, hinge_axis_local)
    )

    first_second_in, first_second_out = split_by_normal3(hinge_axis, first_to_second)
    second_end_in, second_end_out = split_by_normal3(hinge_axis, second_to_end)
    out_of_plane = sub3(first_second_out, second_end_out)
    target_in_plane_sq = dot3(first_to_target, first_to_target) - dot3(
        out_of_plane, out_of_plane
    )
    first_second_sq = dot3(first_second_in, first_second_in)
    second_end_sq = dot3(second_end_in, second_end_in)
    denominator = -2.0 * math.sqrt(first_second_sq) * math.sqrt(second_end_sq)
    law = (
        (target_in_plane_sq - first_second_sq - second_end_sq) / denominator
        if denominator != 0.0
        else cos_min_hinge
    )
    desired_hinge = math.acos(max(cos_max_hinge, min(cos_min_hinge, law)))
    current_hinge = math.acos(
        max(
            -1.0,
            min(
                1.0,
                dot3(
                    scale3(normalized3(first_second_in), -1.0),
                    normalized3(second_end_in),
                ),
            ),
        )
    )

    # Hinge pass: the second bone (and the end below it) turn about the hinge.
    hinge_rotation = axis_angle_scalar_xyzw(
        hinge_axis, (desired_hinge - current_hinge) * weight * second_gain
    )
    second = (second_pos, multiply_scalar_xyzw(hinge_rotation, second_rot))
    end = _rotate_about(end, second_pos, hinge_rotation)

    # Swing pass: the whole chain turns about the first bone so the end points at the target.
    first_to_target_n = normalized3(first_to_target)
    tip = add3(end[0], rotate_vector_unit_scalar_xyzw(end[1], end_offset))
    swing = _partial(
        shortest_rotation_scalar_xyzw(
            normalized3(sub3(tip, first_pos)), first_to_target_n
        ),
        weight * first_gain,
    )
    chain = [_rotate_about(bone, first_pos, swing) for bone in (first, second, end)]

    if pole is not None:
        pole_n = normalized3(sub3(tuple(float(v) for v in pole[:3]), first_pos))
        if not is_parallel3(first_to_target_n, pole_n):
            first_to_second_n = normalized3(sub3(chain[1][0], chain[0][0]))
            if not is_parallel3(first_to_target_n, first_to_second_n):
                vec_a, _ = split_by_normal3(first_to_target_n, first_to_second_n)
            else:
                axis = normalized3(
                    rotate_vector_unit_scalar_xyzw(chain[1][1], hinge_axis_local)
                )
                vec_a = cross3(axis, first_to_target_n)
            vec_b, _ = split_by_normal3(first_to_target_n, pole_n)
            pole_fix = _partial(
                shortest_rotation_scalar_xyzw(normalized3(vec_a), normalized3(vec_b)),
                weight,
            )
            chain = [_rotate_about(bone, first_pos, pole_fix) for bone in chain]

    if abs(float(twist_deg)) > 0.0:
        twist = axis_angle_scalar_xyzw(
            first_to_target_n, math.radians(float(twist_deg))
        )
        chain = [_rotate_about(bone, first_pos, twist) for bone in chain]

    if end_rotation is not None:
        chain[2] = (
            chain[2][0],
            slerp_scalar_xyzw(chain[2][1], end_rotation, weight * end_gain),
        )
    return chain[0], chain[1], chain[2]


def two_bone_middle_positions(
    root, goal, first_length: float, second_length: float, bend
) -> np.ndarray:
    """Middle joint positions of two-bone chains reaching from root toward goal, bent toward bend"""
    root = np.asarray(root, dtype=np.float64)
    reach = np.asarray(goal, dtype=np.float64) - root
    distance = np.linalg.norm(reach, axis=-1)
    axis = reach / np.maximum(distance, 1e-12)[..., None]
    distance = np.clip(
        distance,
        abs(first_length - second_length) + 1e-9,
        first_length + second_length - 1e-9,
    )
    along = (first_length**2 + distance**2 - second_length**2) / (
        2.0 * first_length * distance
    )
    along = np.clip(along, -1.0, 1.0)
    side = np.asarray(bend, dtype=np.float64)
    side = side - np.sum(side * axis, axis=-1)[..., None] * axis
    side = side / np.maximum(np.linalg.norm(side, axis=-1), 1e-12)[..., None]
    return root + first_length * (
        along[..., None] * axis + np.sqrt(1.0 - along**2)[..., None] * side
    )
