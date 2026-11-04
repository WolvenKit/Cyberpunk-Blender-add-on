from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import normalize_xyzw
from ....redSpace.euler import euler_from_xyzw, xyzw_from_euler
from ...model.animgraph.indices import index_name
from .curve_points import sample_curve
from .topology import has_link


def normalize_smooth_clamp(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, Mapping) else {}
    return {
        "min": float(data.get("min", 0.0) or 0.0),
        "max": float(data.get("max", 0.0) or 0.0),
        "marginEaseOutCurve": data.get("marginEaseOutCurve")
        if isinstance(data.get("marginEaseOutCurve"), Mapping)
        else {},
    }


def smooth_float_clamp(value: float, data: Mapping[str, Any]) -> float:
    minimum = float(data.get("min", 0.0) or 0.0)
    maximum = float(data.get("max", 0.0) or 0.0)
    curve = (
        data.get("marginEaseOutCurve")
        if isinstance(data.get("marginEaseOutCurve"), Mapping)
        else None
    )
    value = float(value)
    if value < minimum:
        return minimum - sample_curve(curve, minimum - value, 0.0)
    if value > maximum:
        return maximum + sample_curve(curve, value - maximum, 0.0)
    return value


def evaluate_rotation_limit(
    transform: QsTransform, data: Mapping[str, Any], weight: float = 1.0
) -> QsTransform:
    weight = max(0.0, min(1.0, float(weight)))
    if weight <= 0.0:
        return transform
    # limitOnX/Y/Z clamp the EulerAngles Pitch/Roll/Yaw (degrees, about X/Y/Z).
    pitch, roll, yaw = euler_from_xyzw(transform.rotation_xyzw)
    pitch = smooth_float_clamp(pitch, data.get("limitOnX", {}))
    roll = smooth_float_clamp(roll, data.get("limitOnY", {}))
    yaw = smooth_float_clamp(yaw, data.get("limitOnZ", {}))
    limited = xyzw_from_euler(pitch, roll, yaw)
    if weight < 1.0:
        # A partial weight blends by normalized lerp, not slerp.
        current = np.asarray(transform.rotation_xyzw, dtype=np.float64)
        if float(np.dot(current, limited)) < 0.0:
            limited = -limited
        limited = normalize_xyzw(current + (limited - current) * weight)
    return QsTransform.from_components(transform.translation, limited, transform.scale)


def rotation_limit_data(node_type, node):
    return {
        "constrainedTransform": index_name(
            node.get("constrainedTransform"), "animTransformIndex", allow_text=True
        ),
        "limitOnX": normalize_smooth_clamp(node.get("limitOnX")),
        "limitOnY": normalize_smooth_clamp(node.get("limitOnY")),
        "limitOnZ": normalize_smooth_clamp(node.get("limitOnZ")),
        "useEyesLookAtBlendWeight": bool(node.get("useEyesLookAtBlendWeight", False)),
        "hasWeightLink": has_link(node, "weightLink"),
    }
