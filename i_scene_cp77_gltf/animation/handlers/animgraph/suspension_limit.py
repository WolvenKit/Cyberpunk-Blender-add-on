from __future__ import annotations

from ...domain.animgraph.suspension_limit import evaluate_suspension_limit
from .base import PoseOpHandler


class SuspensionLimitHandler(PoseOpHandler):
    node_types = ("animAnimNode_SuspensionLimit",)
    bone_fields = ("constrainedTransform",)
    track_fields = ("radiusTrack", "deviationTrack")

    def evaluate(self, context, op):
        evaluation = evaluate_suspension_limit(
            op.pose, op.child.reference_pose, op.track_values, op.data
        )
        return evaluation
