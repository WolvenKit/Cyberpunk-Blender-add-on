from __future__ import annotations

from ...domain.animgraph.set_bone_orientation import evaluate_set_bone_orientation
from .base import PoseOpHandler


class SetBoneOrientationHandler(PoseOpHandler):
    node_types = ("animAnimNode_SetBoneOrientation",)
    bone_fields = ("bone",)
    uses_tracks = False

    def evaluate(self, context, op):
        orientation = (
            context.values.linked(
                "quaternion", op.handle, "orientationMs", (0.0, 0.0, 0.0, 1.0)
            )
            if op.data.get("hasOrientation")
            else None
        )
        evaluation = evaluate_set_bone_orientation(
            op.pose,
            op.child.parent_map,
            op.data["bone"],
            orientation,
            model_space=op.child.model_space,
        )
        return evaluation
