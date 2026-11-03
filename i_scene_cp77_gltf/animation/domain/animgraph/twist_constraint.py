from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

from ....bartmoss.qs_transform import QsTransform, relative_to
from ....bartmoss.quaternion import (
    axis_angle_scalar_xyzw,
    multiply_unit_scalar_xyzw,
    rotate_vector_scalar_xyzw,
    shortest_rotation_scalar_xyzw,
)
from ...model.animgraph.constants import AXIS_VECTORS
from ...model.animgraph.indices import index_name
from ...model.animgraph.twist_constraint import normalize_axis, runtime_output
from .pose_space import frame_model_transform

_ORTHOGONAL = {
    "X": "Z",
    "Y": "Z",
    "Z": "X",
    "NegativeX": "NegativeZ",
    "NegativeY": "NegativeZ",
    "NegativeZ": "NegativeX",
}


@dataclass(frozen=True)
class TwistConstraintEvaluation:
    applied: bool
    angle: float
    transforms_written: tuple[str, ...]
    tracks_written: tuple[str, ...]


def twist_between_orientations(
    orientation_a: Sequence[float],
    orientation_b: Sequence[float],
    front_axis: Any,
) -> float:
    front_name = normalize_axis(front_axis)
    front = AXIS_VECTORS[front_name]
    side = AXIS_VECTORS[_ORTHOGONAL[front_name]]
    a_front = rotate_vector_scalar_xyzw(orientation_a, front)
    b_front = rotate_vector_scalar_xyzw(orientation_b, front)
    a_side = rotate_vector_scalar_xyzw(orientation_a, side)
    b_side = rotate_vector_scalar_xyzw(orientation_b, side)
    aligned_b_side = rotate_vector_scalar_xyzw(
        shortest_rotation_scalar_xyzw(b_front, a_front), b_side
    )
    cross = (
        a_side[1] * aligned_b_side[2] - a_side[2] * aligned_b_side[1],
        a_side[2] * aligned_b_side[0] - a_side[0] * aligned_b_side[2],
        a_side[0] * aligned_b_side[1] - a_side[1] * aligned_b_side[0],
    )
    numerator = a_front[0] * cross[0] + a_front[1] * cross[1] + a_front[2] * cross[2]
    denominator = (
        a_side[0] * aligned_b_side[0]
        + a_side[1] * aligned_b_side[1]
        + a_side[2] * aligned_b_side[2]
    )
    return math.atan2(numerator, denominator)


def evaluate_twist_constraint(
    local_pose: MutableMapping[str, QsTransform],
    tracks: MutableMapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    reference_pose_ms: Mapping[str, QsTransform] | None = None,
    model_space: bool = False,
) -> TwistConstraintEvaluation:
    transform_a = str(data.get("transformA", "") or "")
    transform_b = str(data.get("transformB", "") or "")
    if transform_a not in local_pose or transform_b not in local_pose:
        return TwistConstraintEvaluation(False, 0.0, (), ())

    cache: dict[str, QsTransform] = {}
    a_model = frame_model_transform(
        transform_a, local_pose, parent_map, model_space, cache
    )
    b_model = frame_model_transform(
        transform_b, local_pose, parent_map, model_space, cache
    )
    angle = twist_between_orientations(
        a_model.rotation_xyzw, b_model.rotation_xyzw, data.get("frontAxis", "X")
    )
    transforms_written: list[str] = []
    tracks_written: list[str] = []
    references = reference_pose_ms or {}

    for raw_output in data.get("outputs", ()) or ():
        output = raw_output if isinstance(raw_output, Mapping) else {}
        scale = float(
            output.get("negativeScale", 1.0)
            if angle < 0.0
            else output.get("positiveScale", 1.0)
        )
        twist = angle * scale
        track = str(output.get("outputAngleTrack", "") or "")
        if track and track in tracks:
            tracks[track] = twist
            tracks_written.append(track)

        target = str(output.get("twistedTransform", "") or "")
        if not target or target not in local_pose:
            continue
        parent = str(parent_map.get(target, "") or "")
        if model_space:
            reference_rotation = (
                local_pose[parent].rotation_xyzw
                if parent and parent in local_pose
                else (0.0, 0.0, 0.0, 1.0)
            )
        else:
            reference_rotation = local_pose[target].rotation_xyzw
            if target in references:
                reference_local = (
                    relative_to(references[parent], references[target])
                    if parent and parent in references
                    else references[target]
                )
                reference_rotation = reference_local.rotation_xyzw
        rotation = multiply_unit_scalar_xyzw(
            reference_rotation,
            axis_angle_scalar_xyzw(
                AXIS_VECTORS[normalize_axis(output.get("twistAxis", "X"))], twist
            ),
        )
        current = local_pose[target]
        local_pose[target] = QsTransform(current.translation, rotation, current.scale)
        transforms_written.append(target)

    return TwistConstraintEvaluation(
        bool(transforms_written or tracks_written),
        angle,
        tuple(transforms_written),
        tuple(tracks_written),
    )


def twist_constraint_data(node_type, node):
    return {
        "transformA": index_name(
            node.get("transformA"), "animTransformIndex", allow_text=True
        ),
        "transformB": index_name(
            node.get("transformB"), "animTransformIndex", allow_text=True
        ),
        "frontAxis": normalize_axis(node.get("frontAxis"), "X"),
        "outputs": tuple(runtime_output(raw) for raw in node.get("outputs", ()) or ()),
    }
