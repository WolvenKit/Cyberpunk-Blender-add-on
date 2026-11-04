from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import shortest_rotation_xyzw
from ...model.animgraph.aim_constraint import vector_components
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, model_transform
from .topology import has_link


def _value_by_phi(phi: float, v1: float, v2: float, v3: float, v4: float) -> float:
    """The value at phi of an ellipse in polar form through the four per-quadrant values"""
    half = 0.5 * math.pi
    if -math.pi <= phi < -half:
        a, b, phi = v1, v2, phi + math.pi
    elif -half <= phi < 0.0:
        a, b, phi = v2, v3, phi + half
    elif 0.0 <= phi < half:
        a, b = v3, v4
    else:
        a, b, phi = v4, v1, phi - half
    if a == b:
        return a
    if a == 0.0 or b == 0.0:
        return 0.0
    ratio = b / a
    eccentricity = 1.0 - ratio * ratio
    cosine = math.cos(phi)
    return b / math.sqrt(1.0 - eccentricity * cosine * cosine)


def _cone_height(radius: float, paraboloid_radius: float, limit_angle: float) -> float:
    if abs(limit_angle - 0.5 * math.pi) < 1e-38:
        return 0.0
    if radius < paraboloid_radius:
        return (radius * radius + paraboloid_radius * paraboloid_radius) / (
            2.0 * paraboloid_radius * math.tan(limit_angle)
        )
    return radius / math.tan(limit_angle)


def evaluate_cone_limit(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    limits: Sequence[float],
    cone_offset_ms: Sequence[float],
    *,
    model_space: bool = False,
    sample_curve=None,
) -> tuple[PoseOpEvaluation, bool]:
    """Keep a bone's position inside a ConeLimit's elliptic cone and return (evaluation, limit_reached)"""
    cone = str(data.get("coneTransform", "") or "")
    target = str(data.get("constrainedTransform", "") or "")
    if cone not in local_pose or target not in local_pose:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason="cone or constrained transform is absent from the pose",
        ), False
    try:
        cone_ms = frame_model_transform(cone, local_pose, parent_map, model_space)
        parent = "" if model_space else str(parent_map.get(target, "") or "")
        if not model_space and not parent:
            # A root bone is measured against the first transform of the pose.
            parent = next(iter(local_pose))
        parent_ms = (
            model_transform(parent, local_pose, parent_map, {})
            if parent and parent != target
            else None
        )
    except KeyError as exc:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transform ancestor is absent from the pose: {exc.args[0] if exc.args else ''}",
        ), False
    adjust = QsTransform.from_components(
        (0.0, 0.0, 0.0),
        shortest_rotation_xyzw((0.0, 1.0, 0.0), data.get("coneAxis", (0.0, 1.0, 0.0))),
        (1.0, 1.0, 1.0),
    )
    cone_ms = compose(cone_ms, adjust)
    tx, ty, tz = cone_ms.translation
    ox, oy, oz = (float(v) for v in tuple(cone_offset_ms)[:3])
    cone_ms = QsTransform.from_components(
        (tx + ox, ty + oy, tz + oz), cone_ms.rotation_xyzw, cone_ms.scale
    )
    constrained_ms = (
        local_pose[target]
        if model_space
        else (
            compose(parent_ms, local_pose[target])
            if parent_ms is not None
            else local_pose[target]
        )
    )
    in_cone = relative_to(cone_ms, constrained_ms)
    px, py, pz = in_cone.translation
    phi = max(-math.pi, min(math.pi, math.atan2(pz, px)))
    radius = math.hypot(px, pz)
    radii = data.get("paraboloidRadii", (0.0, 0.0, 0.0, 0.0))
    paraboloid = _value_by_phi(phi, *(max(0.0, float(v)) for v in radii))
    limit_angle = math.radians(_value_by_phi(phi, *(float(v) for v in limits)))
    if not (limit_angle > 1.17549435e-38 and math.pi - limit_angle > 1.17549435e-38):
        return PoseOpEvaluation((), applied=False, reason="nonpositive weight"), False
    height = _cone_height(radius, paraboloid, limit_angle)
    if py >= height:
        return PoseOpEvaluation((target,)), False
    distance = height - py
    eased = (
        float(sample_curve(data.get("marginEaseOutCurve"), distance, 0.0))
        if sample_curve is not None
        else 0.0
    )
    adjusted = QsTransform.from_components(
        (px, height - eased, pz), in_cone.rotation_xyzw, in_cone.scale
    )
    adjusted_ms = compose(cone_ms, adjusted)
    if model_space:
        local_pose[target] = adjusted_ms
    else:
        local_pose[target] = (
            relative_to(parent_ms, adjusted_ms)
            if parent_ms is not None
            else adjusted_ms
        )
    return PoseOpEvaluation((target,)), True


def cone_limit_data(node_type, node):
    return {
        "coneTransform": index_name(
            node.get("coneTransform"), "animTransformIndex", allow_text=True
        ),
        "constrainedTransform": index_name(
            node.get("constrainedTransform"), "animTransformIndex", allow_text=True
        ),
        "coneAxis": vector_components(node.get("coneAxisLs"), (0.0, 1.0, 0.0)),
        "coneOffsetMs": vector_components(node.get("coneOffsetMs"), (0.0, 0.0, 0.0)),
        "hasConeOffsetLink": has_link(node, "coneOffsetMsLink"),
        "marginEaseOutCurve": node.get("marginEaseOutCurve")
        if isinstance(node.get("marginEaseOutCurve"), Mapping)
        else None,
        "limits": tuple(float(node.get(f"limit{i}", 0.0) or 0.0) for i in range(1, 5)),
        "limitLinks": tuple(has_link(node, f"limit{i}Link") for i in range(1, 5)),
        "limitTracks": tuple(
            
                index_name(
                    node.get(f"limit{i}FloatTrack"),
                    "animNamedTrackIndex",
                    allow_text=True,
                )
                for i in range(1, 5)
            
        ),
        "paraboloidRadii": tuple(
            max(0.0, float(node.get(f"paraboloidRadius{i}", 0.0) or 0.0))
            for i in range(1, 5)
        ),
        "coneLimitReached": index_name(
            node.get("coneLimitReached"), "animNamedTrackIndex", allow_text=True
        ),
    }
