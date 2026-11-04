from __future__ import annotations

from ...domain.animgraph.cone_limit import evaluate_cone_limit
from ...domain.animgraph.curve_points import sample_curve
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class ConeLimitHandler(PoseOpHandler):
    node_types = ("animAnimNode_ConeLimit",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("coneTransform", "constrainedTransform"))
        data["limitTracks"] = tuple(
            context.resolve_structured_track(track, required=False) if track else ""
            for track in data.get("limitTracks", ())
        )
        resolve_tracks(context, data, ("coneLimitReached",), optional=True)
        data["_usesTracks"] = any(data.get("limitTracks", ())) or bool(
            data.get("coneLimitReached")
        )
        return data

    def evaluate(self, context, op):
        limits = []
        for position, default in enumerate(op.data["limits"]):
            value = float(default)
            if op.data["limitLinks"][position]:
                value = min(
                    180.0,
                    max(
                        0.0,
                        context.values.linked(
                            "float", op.handle, f"limit{position + 1}Link", value
                        ),
                    ),
                )
            track = op.data["limitTracks"][position]
            if track and track in op.track_values:
                value = min(180.0, max(0.0, float(op.track_values[track])))
            limits.append(value)
        offset = (
            context.values.linked(
                "vector", op.handle, "coneOffsetMsLink", op.data["coneOffsetMs"]
            )
            if op.data.get("hasConeOffsetLink")
            else op.data["coneOffsetMs"]
        )
        evaluation, reached = evaluate_cone_limit(
            op.pose,
            op.child.parent_map,
            op.data,
            limits,
            offset,
            model_space=op.child.model_space,
            sample_curve=sample_curve,
        )
        reached_track = str(op.data.get("coneLimitReached", "") or "")
        if reached and reached_track in op.track_values:
            # The track holds look-at status flags; LimitReached is bit 1.
            op.track_values[reached_track] = float(
                int(op.track_values[reached_track]) | 1
            )
            evaluation = PoseOpEvaluation(
                evaluation.transforms_written, (reached_track,)
            )
        return evaluation
