from __future__ import annotations

from ...domain.animgraph.direct_conn import evaluate_float_track_direct_conn
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler


class FloatTrackDirectConnConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_FloatTrackDirectConnConstraint",)
    bone_fields = ("transformIndex",)
    track_fields = ("floatTrackIndex",)
    uses_tracks = True

    def evaluate(self, context, op):
        target = str(op.data.get("transformIndex", "") or "")
        track = str(op.data.get("floatTrackIndex", "") or "")
        weight = (
            context.values.linked(
                "float",
                op.handle,
                "weightNode",
                float(op.data.get("weight", 1.0) or 0.0),
            )
            if op.data.get("hasWeightNode")
            else float(op.data.get("weight", 1.0) or 0.0)
        )
        mul_factor = (
            context.values.linked(
                "float",
                op.handle,
                "mulFactorNode",
                float(op.data.get("mulFactor", 1.0) or 0.0),
            )
            if op.data.get("hasMulFactorNode")
            else float(op.data.get("mulFactor", 1.0) or 0.0)
        )
        if target not in op.pose or track not in op.track_values:
            return op.child
        direct = evaluate_float_track_direct_conn(
            op.pose[target],
            op.track_values[track],
            str(op.data.get("channel", "PosX") or "PosX"),
            mul_factor,
            weight,
        )
        if not direct.applied and weight > 0.0:
            raise ValueError(
                f"FloatTrackDirectConn {op.handle or op.program_node.path}: unsupported channel "
                f"{str(op.data.get('channel', '') or '')!r}"
            )
        if direct.applied:
            op.pose[target] = direct.transform
        evaluation = PoseOpEvaluation((target,) if direct.applied else (), ())
        return evaluation
