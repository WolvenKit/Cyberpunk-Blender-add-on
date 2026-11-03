from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import inverse_rotate_vector_xyzw
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, model_transform
from .source_channels import constraint_weight


@dataclass(frozen=True)
class SimpleSplineEvaluation:
    applied: bool
    constrained: str
    progress: float
    model_translation: tuple[float, float, float]
    reason: str = ""


def evaluate_simple_spline(
    local_pose: MutableMapping[str, QsTransform],
    tracks: Mapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> SimpleSplineEvaluation:
    """Apply simple-spline translation semantics"""
    start = str(data.get("startTransform", "") or "")
    middle = str(data.get("middleTransform", "") or "")
    end = str(data.get("endTransform", "") or "")
    constrained = str(data.get("constrainedTransform", "") or "")
    for role, name in (
        ("start transform", start),
        ("middle transform", middle),
        ("end transform", end),
        ("constrained transform", constrained),
    ):
        if name not in local_pose:
            return SimpleSplineEvaluation(
                False,
                constrained,
                0.0,
                (0.0, 0.0, 0.0),
                f"{role} is absent from the pose: {name or '<empty>'}",
            )

    progress_mode = str(data.get("progressMode", "Static") or "Static")
    progress_track = str(data.get("progressTrack", "") or "")
    if progress_mode == "FloatTrack" and progress_track not in tracks:
        return SimpleSplineEvaluation(
            False,
            constrained,
            0.0,
            (0.0, 0.0, 0.0),
            f"progress track is absent from the pose: {progress_track or '<empty>'}",
        )
    progress = constraint_weight(
        progress_mode,
        float(data.get("defaultProgress", 0.0)),
        progress_track,
        tracks,
    )
    if model_space and progress_mode == "Static":
        sx, sy, sz = local_pose[start].translation
        mx, my, mz = local_pose[middle].translation
        ex, ey, ez = local_pose[end].translation
        inverse = 1.0 - progress
        first = inverse * inverse
        second = 2.0 * inverse * progress
        third = progress * progress
        final_translation = (
            first * sx + second * mx + third * ex,
            first * sy + second * my + third * ey,
            first * sz + second * mz + third * ez,
        )
        current = local_pose[constrained]
        local_pose[constrained] = QsTransform(
            final_translation, current.rotation_xyzw, current.scale
        )
        return SimpleSplineEvaluation(
            True, constrained, progress, final_translation, ""
        )

    cache: dict[str, QsTransform] = {}
    start_position = np.asarray(
        (
            frame_model_transform(start, local_pose, parent_map, model_space, cache)
        ).translation,
        dtype=np.float64,
    )
    middle_position = np.asarray(
        (
            frame_model_transform(middle, local_pose, parent_map, model_space, cache)
        ).translation,
        dtype=np.float64,
    )
    end_position = np.asarray(
        (
            frame_model_transform(end, local_pose, parent_map, model_space, cache)
        ).translation,
        dtype=np.float64,
    )
    inverse = 1.0 - progress
    final_ms = (
        inverse * inverse * start_position
        + 2.0 * inverse * progress * middle_position
        + progress * progress * end_position
    )

    parent = "" if model_space else str(parent_map.get(constrained, "") or "")
    if parent:
        parent_ms = model_transform(parent, local_pose, parent_map, cache)
        # The position is inverse-rotated without dividing by the parent's scale, unlike relative_to().
        final_translation = inverse_rotate_vector_xyzw(
            parent_ms.rotation_xyzw,
            final_ms - np.asarray(parent_ms.translation, dtype=np.float64),
        )
    else:
        final_translation = final_ms

    current = local_pose[constrained]
    local_pose[constrained] = QsTransform.from_components(
        final_translation,
        current.rotation_xyzw,
        current.scale,
    )
    return SimpleSplineEvaluation(
        True,
        constrained,
        progress,
        tuple(float(value) for value in final_ms),
        "",
    )


def simple_spline_data(node_type, node):
    return {
        "startTransform": index_name(
            node.get("startTransform"), "animTransformIndex", allow_text=True
        ),
        "middleTransform": index_name(
            node.get("middleTransform"), "animTransformIndex", allow_text=True
        ),
        "endTransform": index_name(
            node.get("endTransform"), "animTransformIndex", allow_text=True
        ),
        "constrainedTransform": index_name(
            node.get("constrainedTransform"), "animTransformIndex", allow_text=True
        ),
        "progressMode": str(node.get("progressMode", "Static") or "Static"),
        "defaultProgress": float(node.get("defaultProgress", 0.0) or 0.0),
        "progressTrack": index_name(
            node.get("progressTrack"), "animNamedTrackIndex", allow_text=True
        ),
    }
