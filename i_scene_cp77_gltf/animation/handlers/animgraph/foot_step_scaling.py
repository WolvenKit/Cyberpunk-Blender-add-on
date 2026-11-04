from __future__ import annotations

from ...domain.animgraph.foot_step_scaling import evaluate_foot_step_scaling
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler


class FootStepScalingHandler(PoseOpHandler):
    node_types = ("animAnimNode_FootStepScaling",)
    bone_fields = ("hipsIndex", "leftFootIKIndex", "rightFootIKIndex")
    uses_tracks = False

    def map_data(self, context, program_node, node_type, data):
        data = super().map_data(context, program_node, node_type, data)
        for key in ("leftFootIKIndex", "rightFootIKIndex"):
            # Each leg is solved from the foot's grandparent, below its great-grandparent.
            bone = data[key]
            for _depth in range(3):
                bone = context.host.bone_parent(bone) if bone is not None else None
                if bone is not None:
                    context.required_bones.add(bone)
        return data

    def evaluate(self, context, op):
        speed = (
            context.values.linked("float", op.handle, "inputSpeed", 1.0)
            if op.data.get("hasInputSpeed")
            else 1.0
        )
        weight = (
            context.values.linked("float", op.handle, "weight", 1.0)
            if op.data.get("hasWeight")
            else 1.0
        )
        written = evaluate_foot_step_scaling(
            op.pose,
            op.child.parent_map,
            context._reference_model_pose(op.child),
            op.data,
            float(speed),
            float(weight),
            model_space=op.child.model_space,
        )
        evaluation = PoseOpEvaluation(written, ())
        return evaluation
