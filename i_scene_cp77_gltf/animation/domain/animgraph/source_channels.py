from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from ....assetio.transform_values import vector3_from_data
from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import rotate_vector_xyzw
from ....bartmoss.scalar import clamp01
from ...model.animgraph.aim_constraint import up_channel_data, vector_components
from ...model.animgraph.indices import index_name
from ...model.animgraph.source_channels import (
    ANIM_FEATURE_VECTOR_TYPE,
    ORIENTATION_VECTOR_TYPE,
    REFERENCE_TRANSFORM_VECTOR_TYPE,
    SOCKET_VECTOR_TYPE,
    STATIC_VECTOR_TYPE,
    TRANSFORM_VECTOR_TYPE,
)
from .pose_space import frame_model_transform


@dataclass(frozen=True)
class SourceVectorEvaluation:
    value: tuple[float, float, float]
    source: str


def constraint_weight(
    mode: str,
    static_value: float,
    float_track: str,
    tracks: Mapping[str, float],
) -> float:
    if mode == "Static":
        return float(static_value)
    if mode == "FloatTrack":
        # An unresolved weight track falls back to the static weight.
        name = str(float_track or "")
        if name not in tracks:
            return float(static_value)
        return clamp01(tracks[name])
    raise ValueError(f"Unsupported constraint weight mode: {mode}")


def evaluate_vector(
    channel: Mapping[str, Any],
    local_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    *,
    reference_pose_ms: Mapping[str, QsTransform] | None = None,
    cache: dict[str, QsTransform] | None = None,
    model_space: bool = False,
) -> SourceVectorEvaluation:
    channel_type = str(channel.get("$type", "") or "")
    model_cache = cache if cache is not None else {}

    if channel_type == TRANSFORM_VECTOR_TYPE:
        name = str(channel.get("transformIndex", "") or "")
        if name not in local_pose:
            raise KeyError(name)
        value = (
            frame_model_transform(
                name, local_pose, parent_map, model_space, model_cache
            )
        ).translation
        return SourceVectorEvaluation(tuple(float(item) for item in value), name)

    if channel_type == REFERENCE_TRANSFORM_VECTOR_TYPE:
        name = str(channel.get("transformIndex", "") or "")
        if reference_pose_ms is None or name not in reference_pose_ms:
            raise KeyError(name)
        value = reference_pose_ms[name].translation
        return SourceVectorEvaluation(
            tuple(float(item) for item in value), f"reference:{name}"
        )

    if channel_type == ORIENTATION_VECTOR_TYPE:
        orientation_name = str(channel.get("transformIndex", "") or "")
        anchor_name = str(channel.get("inputTransformIndex", "") or "")
        if orientation_name not in local_pose:
            raise KeyError(orientation_name)
        if anchor_name not in local_pose:
            raise KeyError(anchor_name)
        orientation = frame_model_transform(
            orientation_name, local_pose, parent_map, model_space, model_cache
        )
        anchor = frame_model_transform(
            anchor_name, local_pose, parent_map, model_space, model_cache
        )
        direction = rotate_vector_xyzw(
            orientation.rotation_xyzw,
            np.asarray(
                vector3_from_data(channel.get("up"), (0.0, 1.0, 0.0)), dtype=np.float64
            ),
        )
        value = np.asarray(anchor.translation, dtype=np.float64) + direction
        return SourceVectorEvaluation(
            tuple(float(item) for item in value),
            f"{anchor_name}@{orientation_name}",
        )

    if channel_type == STATIC_VECTOR_TYPE:
        value = np.asarray(vector3_from_data(channel.get("data")), dtype=np.float64)
        return SourceVectorEvaluation(tuple(float(item) for item in value), "static")

    if channel_type in (SOCKET_VECTOR_TYPE, ANIM_FEATURE_VECTOR_TYPE):
        return SourceVectorEvaluation((0.0, 0.0, 0.0), channel_type)

    raise ValueError(f"Unsupported vector source channel: {channel_type or '<empty>'}")


def vector_channel_data(value: Any) -> Mapping[str, Any]:
    """A vector source channel's program data"""
    data = up_channel_data(value)
    node_type = str(data.get("$type", "") or "")
    if node_type in {TRANSFORM_VECTOR_TYPE, REFERENCE_TRANSFORM_VECTOR_TYPE}:
        return {
            "$type": node_type,
            "transformIndex": index_name(
                data.get("transformIndex"), "animTransformIndex", allow_text=True
            ),
        }
    if node_type == ORIENTATION_VECTOR_TYPE:
        return {
            "$type": node_type,
            "transformIndex": index_name(
                data.get("transformIndex"), "animTransformIndex", allow_text=True
            ),
            "inputTransformIndex": index_name(
                data.get("inputTransformIndex"), "animTransformIndex", allow_text=True
            ),
            "up": vector_components(data.get("up"), (0.0, 1.0, 0.0)),
        }
    return data
