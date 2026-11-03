from __future__ import annotations

from ...domain.animgraph.twist_constraint import evaluate_twist_constraint
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class TwistConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_TwistConstraint",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("transformA", "transformB"))
        outputs = []
        for raw in data.get("outputs", ()):
            item = dict(raw)
            resolve_bones(context, item, ("twistedTransform",))
            resolve_tracks(context, item, ("outputAngleTrack",), optional=True)
            outputs.append(item)
        data["outputs"] = tuple(outputs)
        data["_usesTracks"] = any(
            str(item.get("outputAngleTrack", "") or "")
            for item in (data.get("outputs", ()) or ())
        )
        return data

    def evaluate(self, context, op):
        evaluation = evaluate_twist_constraint(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            reference_pose_ms=None
            if op.child.model_space
            else context._reference_model_pose(op.child),
            model_space=op.child.model_space,
        )
        return evaluation
