from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ...model.animgraph.indices import index_name
from ...model.animgraph.point_constraint import normalize_data
from . import source_channels
from .pose_space import frame_model_transform, model_transform


@dataclass(frozen=True)
class PointConstraintEvaluation:
    applied: bool
    target: str
    inputs: tuple[str, ...]
    constraint_weight: float
    normalized_weights: tuple[float, ...]
    target_model_translation: tuple[float, float, float]
    reason: str = ""


def _with_translation(value: QsTransform, translation) -> QsTransform:
    return QsTransform.from_components(
        tuple(float(v) for v in translation[:3]),
        value.rotation_xyzw,
        value.scale,
    )


def evaluate_point_constraint(
    local_pose: MutableMapping[str, QsTransform],
    tracks: Mapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> PointConstraintEvaluation:
    target = str(data.get("transformIndex", "") or "")
    entries = tuple(data.get("inputWeightedTransforms", ()) or ())
    inputs = tuple(str(entry.get("transform", "") or "") for entry in entries)

    for name in inputs:
        if name not in local_pose:
            return PointConstraintEvaluation(
                False,
                target,
                inputs,
                0.0,
                (),
                (0.0, 0.0, 0.0),
                f"input transform is absent from the pose: {name or '<empty>'}",
            )
    if target not in local_pose:
        return PointConstraintEvaluation(
            False,
            target,
            inputs,
            0.0,
            (),
            (0.0, 0.0, 0.0),
            f"constrained transform is absent from the pose: {target or '<empty>'}",
        )
    if not entries:
        return PointConstraintEvaluation(
            False, target, inputs, 0.0, (), (0.0, 0.0, 0.0)
        )

    weight_mode = str(data.get("weightMode", "Static") or "Static")
    weight_track = str(data.get("weightFloatTrack", "") or "")
    if weight_mode == "FloatTrack" and weight_track not in tracks:
        return PointConstraintEvaluation(
            False,
            target,
            inputs,
            0.0,
            (),
            (0.0, 0.0, 0.0),
            f"weight track is absent from the pose: {weight_track or '<empty>'}",
        )

    constraint_weight = source_channels.constraint_weight(
        weight_mode,
        float(data.get("weight", 1.0)),
        weight_track,
        tracks,
    )

    weights = data["preprocessedWeights"]
    if model_space and weight_mode == "Static" and constraint_weight == 1.0:
        tx = ty = tz = 0.0
        for name, blend_weight in zip(inputs, weights):
            px, py, pz = local_pose[name].translation
            tx += px * blend_weight
            ty += py * blend_weight
            tz += pz * blend_weight
        current = local_pose[target]
        target_translation = (tx, ty, tz)
        local_pose[target] = QsTransform(
            target_translation, current.rotation_xyzw, current.scale
        )
        return PointConstraintEvaluation(
            True, target, inputs, constraint_weight, weights, target_translation
        )

    cache: dict[str, QsTransform] = {}
    target_ms = np.zeros(3, dtype=np.float64)
    for name, weight in zip(inputs, weights):
        value_ms = frame_model_transform(
            name, local_pose, parent_map, model_space, cache
        )
        target_ms += np.asarray(value_ms.translation, dtype=np.float64) * weight

    if not (constraint_weight > 0.0) or math.isnan(constraint_weight):
        return PointConstraintEvaluation(
            False,
            target,
            inputs,
            constraint_weight,
            weights,
            tuple(float(v) for v in target_ms),
        )

    target_local = local_pose[target]
    parent = "" if model_space else str(parent_map.get(target, "") or "")
    if parent:
        parent_ms = model_transform(parent, local_pose, parent_map, cache)
        current_ms = compose(parent_ms, target_local)
        if constraint_weight < 1.0:
            translation = (
                np.asarray(current_ms.translation, dtype=np.float64)
                * (1.0 - constraint_weight)
                + target_ms * constraint_weight
            )
        else:
            translation = target_ms
        local_pose[target] = relative_to(
            parent_ms, _with_translation(current_ms, translation)
        )
    else:
        translation = (
            target_ms * constraint_weight if constraint_weight < 1.0 else target_ms
        )
        local_pose[target] = _with_translation(target_local, translation)

    return PointConstraintEvaluation(
        True,
        target,
        inputs,
        constraint_weight,
        weights,
        tuple(float(v) for v in target_ms),
    )


def point_constraint_data(node_type, node):
    normalized = normalize_data(dict(node))
    return {
        "inputWeightedTransforms": tuple(
            {
                "transform": index_name(
                    raw.get("transform"), "animTransformIndex", allow_text=True
                ),
                "weight": float(raw.get("weight", 1.0) or 0.0),
            }
            for raw in normalized.get("inputWeightedTransforms", ()) or ()
            if isinstance(raw, Mapping)
        ),
        "transformIndex": index_name(
            normalized.get("transformIndex"), "animTransformIndex", allow_text=True
        ),
        "weightMode": str(normalized.get("weightMode", "Static") or "Static"),
        "weight": float(normalized.get("weight", 1.0) or 0.0),
        "weightFloatTrack": index_name(
            normalized.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
    }
