from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import (
    axis_angle_scalar_xyzw,
    multiply_scalar_xyzw,
    rotate_vector_unit_scalar_xyzw,
)
from ....bartmoss.vector3 import cross3, dot3, length3, normalized3, sub3
from ...model.animgraph.constants import AXIS_VECTORS
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform
from .topology import has_link


def look_at_node_data(node_type, node):
    def angle(key, default):
        return float(node.get(key, default) if node.get(key) is not None else default)

    return {
        "transform": index_name(
            node.get("transform"), "animTransformIndex", allow_text=True
        ),
        "forwardAxis": str(node.get("forwardAxis", "X") or "X"),
        "useLimits": bool(node.get("useLimits", False)),
        "limitAxis": str(node.get("limitAxis", "X") or "X"),
        "limitAngle": angle("limitAngle", 90.0),
        "hasTargetNode": has_link(node, "targetNode"),
        "hasWeightNode": has_link(node, "weightNode"),
    }


def _axis(name: str):
    return AXIS_VECTORS.get(str(name or "X"), AXIS_VECTORS["X"])


def evaluate_look_at_node(
    pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    data: Mapping,
    target_ms,
    weight: float,
    *,
    model_space: bool = False,
) -> tuple[str, ...]:
    """Apply LookAt in place and return the bones written"""
    bone = str(data.get("transform", "") or "")
    parent = str(parent_map.get(bone, "") or "")
    if weight <= 0.0 or bone not in pose or parent not in pose:
        return ()
    cache: dict = {}
    parent_ms = frame_model_transform(parent, pose, parent_map, model_space, cache)
    bone_ms = compose(parent_ms, pose[bone])
    aim = normalized3(
        sub3(tuple(float(value) for value in target_ms[:3]), bone_ms.translation)
    )
    if data.get("useLimits"):
        # The aim is kept within the limit angle of the parent's limit axis.
        limit = normalized3(
            rotate_vector_unit_scalar_xyzw(
                parent_ms.rotation_xyzw, _axis(data.get("limitAxis"))
            )
        )
        limit_angle = math.radians(float(data.get("limitAngle", 90.0)))
        if dot3(aim, limit) < math.cos(limit_angle):
            swing = cross3(limit, aim)
            if length3(swing) > 1e-9:
                aim = rotate_vector_unit_scalar_xyzw(
                    axis_angle_scalar_xyzw(normalized3(swing), limit_angle), limit
                )
    forward = normalized3(
        rotate_vector_unit_scalar_xyzw(
            bone_ms.rotation_xyzw, _axis(data.get("forwardAxis"))
        )
    )
    turn_axis = cross3(forward, aim)
    if length3(turn_axis) <= 1e-9:
        return ()
    angle = math.acos(max(-1.0, min(1.0, dot3(aim, forward)))) * float(weight)
    turn = axis_angle_scalar_xyzw(normalized3(turn_axis), angle)
    turned = QsTransform.from_components(
        bone_ms.translation,
        multiply_scalar_xyzw(turn, bone_ms.rotation_xyzw),
        bone_ms.scale,
    )
    pose[bone] = relative_to(parent_ms, turned)
    return (bone,)
