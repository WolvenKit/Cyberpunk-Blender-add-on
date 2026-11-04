from __future__ import annotations

from ...domain.animgraph.simple_spline import evaluate_simple_spline
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class SimpleSplineHandler(PoseOpHandler):
    node_types = ("animAnimNode_SimpleSpline",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(
            context,
            data,
            (
                "startTransform",
                "middleTransform",
                "endTransform",
                "constrainedTransform",
            ),
        )
        resolve_tracks(context, data, ("progressTrack",), optional=True)
        data["_usesTracks"] = (
            str(data.get("progressMode", "Static") or "Static") == "FloatTrack"
        )
        return data

    def evaluate(self, context, op):
        evaluation = evaluate_simple_spline(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            model_space=op.child.model_space,
        )
        return evaluation
