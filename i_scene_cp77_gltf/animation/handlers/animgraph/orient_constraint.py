from __future__ import annotations

from ...domain.animgraph.orient_constraint import (
    evaluate_orient_constraint,
    preprocess_orient_weights,
)
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class OrientConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_OrientConstraint",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("transformIndex",))
        entries = []
        for raw in data.get("inputWeightedTransforms", ()):
            item = dict(raw)
            resolve_bones(context, item, ("transform",))
            entries.append(item)
        data["inputWeightedTransforms"] = tuple(entries)
        data["preprocessedWeights"] = preprocess_orient_weights(
            data["inputWeightedTransforms"]
        )
        data["_fastModelStaticPair"] = bool(
            str(data.get("weightMode", "Static") or "Static") == "Static"
            and float(data.get("weight", 1.0) or 0.0) == 1.0
            and len(data["inputWeightedTransforms"]) == 2
            and len(data["preprocessedWeights"]) == 1
        )
        resolve_tracks(context, data, ("weightFloatTrack",), optional=True)
        data["_usesTracks"] = (
            str(data.get("weightMode", "Static") or "Static") == "FloatTrack"
        )
        return data

    def evaluate(self, context, op):
        evaluation = evaluate_orient_constraint(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            model_space=op.child.model_space,
        )
        return evaluation
