from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from ....bartmoss.qs_transform import QsTransform, relative_to
from ....bartmoss.quaternion import (
    multiply_scalar_xyzw,
    multiply_unit_xyzw,
    rotate_vector_unit_scalar_xyzw,
    rotate_vector_xyzw,
    shortest_rotation_scalar_xyzw,
    shortest_rotation_xyzw,
    slerp_xyzw,
)
from ....bartmoss.vector3 import cross3, dot3, normalize3_with_length
from ...model.animgraph import aim_constraint
from ...model.animgraph.aim_constraint import normalize_data, vector_components
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, model_transform
from .source_channels import constraint_weight, evaluate_vector, vector_channel_data

AXES_ERRORS = {
    "Axes must be nonzero": "AimConstraint axes must be nonzero",
    "Axes are parallel": "AimConstraint axes are parallel",
}


@dataclass(frozen=True)
class AimConstraintEvaluation:
    applied: bool
    constrained: str
    target: str
    up_source: str
    weight: float
    reason: str = ""


def _object_aim_rotation_scalar(
    constrained_ms: QsTransform,
    target_ms: QsTransform,
    up_transform: QsTransform,
    node_type: str,
    data: Mapping[str, Any],
):
    px, py, pz = constrained_ms.translation
    tx, ty, tz = target_ms.translation
    aim, aim_length = normalize3_with_length((tx - px, ty - py, tz - pz))
    if aim_length <= 1e-12:
        return None, "degenerate aim/up vector"

    if node_type == aim_constraint.OBJECT_UP_TYPE:
        ux, uy, uz = up_transform.translation
        up_direction = (ux - px, uy - py, uz - pz)
    else:
        up_direction = rotate_vector_unit_scalar_xyzw(
            up_transform.rotation_xyzw, data["_upTransformVector"]
        )

    up_direction, up_length = normalize3_with_length(up_direction)
    if up_length <= 1e-12:
        return None, "degenerate aim/up vector"
    projection = dot3(aim, up_direction)
    corrected_up, corrected_length = normalize3_with_length(
        (
            up_direction[0] - aim[0] * projection,
            up_direction[1] - aim[1] * projection,
            up_direction[2] - aim[2] * projection,
        )
    )
    if corrected_length <= 1e-12:
        return None, "parallel aim/up vector"
    output_right = cross3(aim, corrected_up)

    axes = data["_orthonormalAxes"]
    if axes is None:
        return None, data["_orthonormalAxesError"]
    global_forward, global_up = axes[0], axes[1]
    quat_u = shortest_rotation_scalar_xyzw(
        global_forward,
        aim,
        (-output_right[0], -output_right[1], -output_right[2]),
    )
    rotated_global_up = rotate_vector_unit_scalar_xyzw(quat_u, global_up)
    quat_v = shortest_rotation_scalar_xyzw(rotated_global_up, corrected_up, aim)
    return multiply_scalar_xyzw(quat_v, quat_u), ""


def _constraint_weight(data: Mapping[str, Any], tracks: Mapping[str, float]) -> float:
    if (
        data.get("$type", aim_constraint.RED_TYPE) == aim_constraint.RED_TYPE
        and data.get("weightMode") == "FloatTrack"
        and str(data.get("weightFloatTrack", "") or "") not in tracks
    ):
        return float(data.get("weight", 1.0))
    return constraint_weight(
        str(data.get("weightMode", "Static") or "Static"),
        float(data.get("weight", 1.0)),
        str(data.get("weightFloatTrack", "") or ""),
        tracks,
    )


def _standard_up_position(
    local_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    up_data: Mapping[str, Any],
    cache: dict[str, QsTransform],
    reference_pose_ms: Mapping[str, QsTransform] | None,
    model_space: bool,
) -> tuple[np.ndarray, str]:
    evaluation = evaluate_vector(
        up_data,
        local_pose,
        parent_map,
        reference_pose_ms=reference_pose_ms,
        cache=cache,
        model_space=model_space,
    )
    return np.asarray(evaluation.value, dtype=np.float64), evaluation.source


def _up_position(
    local_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    constrained_ms: QsTransform,
    cache: dict[str, QsTransform],
    reference_pose_ms: Mapping[str, QsTransform] | None,
    model_space: bool,
) -> tuple[np.ndarray, str]:
    node_type = str(
        data.get("$type", aim_constraint.RED_TYPE) or aim_constraint.RED_TYPE
    )
    if node_type == aim_constraint.RED_TYPE:
        return _standard_up_position(
            local_pose,
            parent_map,
            data.get("upTransform", {}) or {},
            cache,
            reference_pose_ms,
            model_space,
        )

    up_name = str(data.get("upTransform", "") or "")
    if up_name not in local_pose:
        raise KeyError(up_name)
    up_transform = frame_model_transform(
        up_name, local_pose, parent_map, model_space, cache
    )
    if node_type == aim_constraint.OBJECT_UP_TYPE:
        return np.asarray(up_transform.translation, dtype=np.float64), up_name
    if node_type == aim_constraint.OBJECT_ROTATION_UP_TYPE:
        up_vector = np.asarray(
            data.get("upTransformVector", (0.0, 1.0, 0.0)),
            dtype=np.float64,
        )
        value = np.asarray(
            constrained_ms.translation, dtype=np.float64
        ) + rotate_vector_xyzw(
            up_transform.rotation_xyzw,
            up_vector,
        )
        return value, up_name
    raise ValueError(f"Unsupported AimConstraint type: {node_type}")


def evaluate_aim_constraint(
    local_pose: MutableMapping[str, QsTransform],
    tracks: Mapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
    reference_pose_ms: Mapping[str, QsTransform] | None = None,
) -> AimConstraintEvaluation:
    node_type = str(
        data.get("$type", aim_constraint.RED_TYPE) or aim_constraint.RED_TYPE
    )
    if node_type not in aim_constraint.AIM_TYPES:
        raise ValueError(f"Unsupported AimConstraint type: {node_type}")
    constrained = str(data.get("transformIndex", "") or "")
    target = str(data.get("targetTransform", "") or "")
    if constrained not in local_pose:
        return AimConstraintEvaluation(
            False,
            constrained,
            target,
            "",
            0.0,
            f"constrained transform is absent from the pose: {constrained or '<empty>'}",
        )
    if target not in local_pose:
        return AimConstraintEvaluation(
            False,
            constrained,
            target,
            "",
            0.0,
            f"target transform is absent from the pose: {target or '<empty>'}",
        )
    try:
        weight = _constraint_weight(data, tracks)
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return AimConstraintEvaluation(
            False,
            constrained,
            target,
            "",
            0.0,
            f"weight track is absent from the pose: {name or '<empty>'}",
        )
    if not (weight > 0.0) or math.isnan(weight):
        return AimConstraintEvaluation(
            False,
            constrained,
            target,
            "",
            weight,
            "nonpositive weight",
        )

    cache: dict[str, QsTransform] = {}
    try:
        constrained_ms = frame_model_transform(
            constrained, local_pose, parent_map, model_space, cache
        )
        target_ms = frame_model_transform(
            target, local_pose, parent_map, model_space, cache
        )
        if model_space and node_type in {
            aim_constraint.OBJECT_UP_TYPE,
            aim_constraint.OBJECT_ROTATION_UP_TYPE,
        }:
            up_name = str(data.get("upTransform", "") or "")
            if up_name not in local_pose:
                raise KeyError(up_name)
            final_rotation, scalar_reason = _object_aim_rotation_scalar(
                constrained_ms, target_ms, local_pose[up_name], node_type, data
            )
            if final_rotation is None:
                return AimConstraintEvaluation(
                    False, constrained, target, up_name, weight, scalar_reason
                )
        else:
            up_position, up_name = _up_position(
                local_pose,
                parent_map,
                data,
                constrained_ms,
                cache,
                reference_pose_ms,
                model_space,
            )
            position = np.asarray(constrained_ms.translation, dtype=np.float64)
            aim = np.asarray(target_ms.translation, dtype=np.float64) - position
            up_direction = up_position - position
            aim_length = float(np.linalg.norm(aim))
            up_length = float(np.linalg.norm(up_direction))
            if aim_length <= 1e-12 or up_length <= 1e-12:
                return AimConstraintEvaluation(
                    False,
                    constrained,
                    target,
                    up_name,
                    weight,
                    "degenerate aim/up vector",
                )
            aim /= aim_length
            up_direction /= up_length
            corrected_up = up_direction - aim * float(np.dot(aim, up_direction))
            corrected_length = float(np.linalg.norm(corrected_up))
            if corrected_length <= 1e-12:
                return AimConstraintEvaluation(
                    False,
                    constrained,
                    target,
                    up_name,
                    weight,
                    "parallel aim/up vector",
                )
            corrected_up /= corrected_length
            output_right = np.cross(aim, corrected_up)

            axes = data["_orthonormalAxes"]
            if axes is None:
                return AimConstraintEvaluation(
                    False,
                    constrained,
                    target,
                    up_name,
                    weight,
                    data["_orthonormalAxesError"],
                )
            global_forward = np.asarray(axes[0], dtype=np.float64)
            global_up = np.asarray(axes[1], dtype=np.float64)
            quat_u = shortest_rotation_xyzw(global_forward, aim, -output_right)
            rotated_global_up = rotate_vector_xyzw(quat_u, global_up)
            quat_v = shortest_rotation_xyzw(rotated_global_up, corrected_up, aim)
            final_rotation = multiply_unit_xyzw(quat_v, quat_u)
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return AimConstraintEvaluation(
            False,
            constrained,
            target,
            name,
            weight,
            f"source transform is absent from the pose: {name or '<empty>'}",
        )

    parent = "" if model_space else str(parent_map.get(constrained, "") or "")
    local_value = local_pose[constrained]
    if parent:
        parent_ms = model_transform(parent, local_pose, parent_map, cache)
        rotation = (
            slerp_xyzw(constrained_ms.rotation_xyzw, final_rotation, weight)
            if weight < 1.0
            else final_rotation
        )
        output_ms = QsTransform.from_components(
            constrained_ms.translation,
            rotation,
            constrained_ms.scale,
        )
        local_pose[constrained] = relative_to(parent_ms, output_ms)
    else:
        rotation = (
            slerp_xyzw((0.0, 0.0, 0.0, 1.0), final_rotation, weight)
            if weight < 1.0
            else final_rotation
        )
        if (
            model_space
            and weight == 1.0
            and node_type
            in {aim_constraint.OBJECT_UP_TYPE, aim_constraint.OBJECT_ROTATION_UP_TYPE}
        ):
            local_pose[constrained] = QsTransform(
                local_value.translation,
                tuple(float(v) for v in rotation),
                local_value.scale,
            )
        else:
            local_pose[constrained] = QsTransform.from_components(
                local_value.translation,
                rotation,
                local_value.scale,
            )

    return AimConstraintEvaluation(True, constrained, target, up_name, weight)


def aim_constraint_data(node_type, node):
    normalized = normalize_data(dict(node))
    data = {
        "$type": node_type,
        "targetTransform": index_name(
            normalized.get("targetTransform"), "animTransformIndex", allow_text=True
        ),
        "transformIndex": index_name(
            normalized.get("transformIndex"), "animTransformIndex", allow_text=True
        ),
        "forwardAxisLS": vector_components(
            normalized.get("forwardAxisLS"), (1.0, 0.0, 0.0)
        ),
        "upAxisLS": vector_components(normalized.get("upAxisLS"), (0.0, 1.0, 0.0)),
        "weightMode": str(normalized.get("weightMode", "Static") or "Static"),
        "weight": float(normalized.get("weight", 1.0) or 0.0),
        "weightFloatTrack": index_name(
            normalized.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
    }
    if node_type == aim_constraint.RED_TYPE:
        data["upTransform"] = vector_channel_data(normalized.get("upTransform"))
    else:
        data["upTransform"] = index_name(
            normalized.get("upTransform"), "animTransformIndex", allow_text=True
        )
        if node_type == aim_constraint.OBJECT_ROTATION_UP_TYPE:
            data["upTransformVector"] = vector_components(
                normalized.get("upTransformVector"), (0.0, 1.0, 0.0)
            )
    return data
