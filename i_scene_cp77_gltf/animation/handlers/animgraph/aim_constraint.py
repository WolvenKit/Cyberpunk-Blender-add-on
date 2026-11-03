from __future__ import annotations

from collections.abc import Mapping

from ....bartmoss.geometry import orthonormal_axes
from ...domain.animgraph.aim_constraint import AXES_ERRORS, evaluate_aim_constraint
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class AimConstraintHandler(PoseOpHandler):
    node_types = (
        "animAnimNode_AimConstraint",
        "animAnimNode_AimConstraint_ObjectUp",
        "animAnimNode_AimConstraint_ObjectRotationUp",
    )

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("targetTransform", "transformIndex"))
        if node_type == "animAnimNode_AimConstraint":
            up = dict(data.get("upTransform") or {})
            resolve_bones(
                context, up, ("transformIndex", "inputTransformIndex"), optional=True
            )
            data["upTransform"] = up
        else:
            resolve_bones(context, data, ("upTransform",))
        try:
            forward, up_axis, right = orthonormal_axes(
                data.get("forwardAxisLS", (1.0, 0.0, 0.0)),
                data.get("upAxisLS", (0.0, 1.0, 0.0)),
            )
            data["_orthonormalAxes"] = (
                tuple(float(v) for v in forward),
                tuple(float(v) for v in up_axis),
                tuple(float(v) for v in right),
            )
        except ValueError as exc:
            data["_orthonormalAxes"] = None
            data["_orthonormalAxesError"] = AXES_ERRORS.get(str(exc), str(exc))
        if node_type == "animAnimNode_AimConstraint_ObjectRotationUp":
            up_vector = data.get("upTransformVector", (0.0, 1.0, 0.0))
            if isinstance(up_vector, Mapping):
                data["_upTransformVector"] = (
                    float(up_vector.get("X", 0.0)),
                    float(up_vector.get("Y", 1.0)),
                    float(up_vector.get("Z", 0.0)),
                )
            else:
                data["_upTransformVector"] = tuple(float(v) for v in up_vector[:3])
        resolve_tracks(context, data, ("weightFloatTrack",), optional=True)
        data["_usesTracks"] = (
            str(data.get("weightMode", "Static") or "Static") == "FloatTrack"
        )
        return data

    def evaluate(self, context, op):
        reference_pose_ms = (
            None
            if op.child.model_space
            and op.node_type
            in {
                "animAnimNode_AimConstraint_ObjectUp",
                "animAnimNode_AimConstraint_ObjectRotationUp",
            }
            else context._reference_model_pose(op.child)
        )
        evaluation = evaluate_aim_constraint(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            reference_pose_ms=reference_pose_ms,
            model_space=op.child.model_space,
        )
        return evaluation
