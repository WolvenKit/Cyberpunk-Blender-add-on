from __future__ import annotations

from ....assetio.transform_values import qs_transform_from_data
from ....bartmoss.qs_transform import compose
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler


class AdditionalTransformHandler(PoseOpHandler):
    node_types = ("animAnimNode_AdditionalTransform",)

    def map_data(self, context, program_node, node_type, data):
        data["_usesTracks"] = False
        return data

    def evaluate(self, context, op):
        written = []
        for entry in op.data.get("entries", ()):
            name = entry["name"]
            if name not in op.pose:
                continue
            value = qs_transform_from_data(entry["value"])
            parent = entry["parent"]
            if op.child.model_space and parent in op.pose:
                value = compose(op.pose[parent], value)
            op.pose[name] = value
            written.append(name)
        evaluation = PoseOpEvaluation(tuple(written))
        return evaluation
