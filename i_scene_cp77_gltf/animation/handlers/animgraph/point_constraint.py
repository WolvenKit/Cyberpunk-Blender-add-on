from __future__ import annotations

from ...domain.animgraph.point_constraint import evaluate_point_constraint
from ...model.animgraph.point_constraint import preprocess_weights
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class PointConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_PointConstraint",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("transformIndex",))
        entries = []
        for raw in data.get("inputWeightedTransforms", ()):
            item = dict(raw)
            resolve_bones(context, item, ("transform",))
            entries.append(item)
        data["inputWeightedTransforms"] = tuple(entries)
        data["preprocessedWeights"] = tuple(
            preprocess_weights(data["inputWeightedTransforms"])
        )
        resolve_tracks(context, data, ("weightFloatTrack",), optional=True)
        data["_usesTracks"] = (
            str(data.get("weightMode", "Static") or "Static") == "FloatTrack"
        )
        return data

    def evaluate(self, context, op):
        evaluation = evaluate_point_constraint(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            model_space=op.child.model_space,
        )
        return evaluation
