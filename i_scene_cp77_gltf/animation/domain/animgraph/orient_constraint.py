from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

import numpy as np

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import slerp_scalar_xyzw, slerp_xyzw
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, model_transform
from .source_channels import constraint_weight


def preprocess_orient_weights(
    entries: Sequence[Mapping[str, Any]],
) -> tuple[float, ...]:
    if len(entries) <= 1:
        return ()
    total = sum(float(entry.get("weight", 1.0)) for entry in entries)
    result = [0.0] * (len(entries) - 1)
    if total <= 0.0:
        return tuple(result)
    inv_total = 1.0 / total
    denominator = 1.0
    for index in range(len(entries) - 2, -1, -1):
        weight = float(entries[index + 1].get("weight", 1.0)) * inv_total
        result[index] = weight / denominator if denominator != 0.0 else 0.0
        denominator *= 1.0 - result[index]
    return tuple(result)


def evaluate_orient_constraint(
    local_pose: MutableMapping[str, QsTransform],
    tracks: Mapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> PoseOpEvaluation:
    target = str(data.get("transformIndex", "") or "")
    entries = tuple(data.get("inputWeightedTransforms", ()) or ())
    if target not in local_pose:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"constrained transform is absent from the pose: {target or '<empty>'}",
        )
    if not entries:
        return PoseOpEvaluation(
            (), applied=False, reason="OrientConstraint has no input transforms"
        )
    names = tuple(str(entry.get("transform", "") or "") for entry in entries)
    missing = next((name for name in names if name not in local_pose), "")
    if missing:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"input transform is absent from the pose: {missing}",
        )
    mode = str(data.get("weightMode", "Static") or "Static")
    track = str(data.get("weightFloatTrack", "") or "")
    try:
        weight = constraint_weight(mode, float(data.get("weight", 1.0)), track, tracks)
    except (KeyError, ValueError) as exc:
        return PoseOpEvaluation((), applied=False, reason=str(exc))
    if not weight > 0.0:
        return PoseOpEvaluation((), applied=False, reason="nonpositive weight")

    try:
        quaternions = [
            (
                frame_model_transform(name, local_pose, parent_map, model_space)
            ).rotation_xyzw
            for name in names
        ]
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transform ancestor is absent from the pose: {name or '<empty>'}",
        )
    blend_weights = data["preprocessedWeights"]
    if (
        model_space
        and bool(data.get("_fastModelStaticPair", False))
        and len(quaternions) == 2
    ):
        target_rotation = slerp_scalar_xyzw(
            quaternions[0], quaternions[1], blend_weights[0]
        )
        current = local_pose[target]
        local_pose[target] = QsTransform(
            current.translation, target_rotation, current.scale
        )
        return PoseOpEvaluation((target,))
    target_rotation = np.asarray(quaternions[0], dtype=np.float64)
    for quat, blend_weight in zip(quaternions[1:], blend_weights):
        target_rotation = slerp_xyzw(target_rotation, quat, blend_weight)

    parent = "" if model_space else str(parent_map.get(target, "") or "")
    if parent:
        parent_ms = model_transform(parent, local_pose, parent_map, {})
        current_ms = compose(parent_ms, local_pose[target])
        rotation = (
            slerp_xyzw(current_ms.rotation_xyzw, target_rotation, weight)
            if weight < 1.0
            else target_rotation
        )
        local_pose[target] = relative_to(
            parent_ms,
            QsTransform.from_components(
                current_ms.translation, rotation, current_ms.scale
            ),
        )
    else:
        rotation = (
            slerp_xyzw((0.0, 0.0, 0.0, 1.0), target_rotation, weight)
            if weight < 1.0
            else target_rotation
        )
        current = local_pose[target]
        local_pose[target] = QsTransform.from_components(
            current.translation, rotation, current.scale
        )
    return PoseOpEvaluation((target,))


def orient_constraint_data(node_type, node):
    entries = []
    for raw in node.get("inputWeightedTransforms") or ():
        if not isinstance(raw, Mapping):
            continue
        entries.append(
            {
                "transform": index_name(
                    raw.get("transform"), "animTransformIndex", allow_text=True
                ),
                "weight": float(raw.get("weight", 1.0) or 0.0),
            }
        )
    return {
        "inputWeightedTransforms": tuple(entries),
        "transformIndex": index_name(
            node.get("transformIndex"), "animTransformIndex", allow_text=True
        ),
        "weightMode": str(node.get("weightMode", "Static") or "Static"),
        "weight": float(node.get("weight", 1.0) or 0.0),
        "weightFloatTrack": index_name(
            node.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
    }
