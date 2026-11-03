from __future__ import annotations

from ...domain.animgraph.rotation_limit import evaluate_rotation_limit
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler


class RotationLimitHandler(PoseOpHandler):
    node_types = ("animAnimNode_RotationLimit",)
    bone_fields = ("constrainedTransform",)

    def evaluate(self, context, op):
        bone = str(op.data.get("constrainedTransform", "") or "")
        if bone not in op.pose:
            return op.child
        weight = (
            context.values.linked("float", op.handle, "weightLink", 1.0)
            if op.data.get("hasWeightLink")
            else 1.0
        )
        op.pose[bone] = evaluate_rotation_limit(op.pose[bone], op.data, weight)
        evaluation = PoseOpEvaluation((bone,), ())
        return evaluation
