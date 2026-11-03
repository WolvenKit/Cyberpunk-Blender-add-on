from __future__ import annotations

from ...domain.animgraph.math_expression import compile_node_expression
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .base import PoseOpHandler, resolve_tracks


class MathExpressionPoseHandler(PoseOpHandler):
    node_types = ("animAnimNode_MathExpressionPose",)

    def map_data(self, context, program_node, node_type, data):
        resolve_tracks(context, data, ("outputFloatTrack",))
        expression, bindings = compile_node_expression(data)
        mapped = []
        for binding in bindings:
            socket = dict(binding.socket)
            if binding.kind == "float":
                socket["inputFloatTrack"] = context.resolve_structured_track(
                    index_name(
                        socket.get("inputFloatTrack"),
                        "animNamedTrackIndex",
                        allow_text=True,
                    ),
                    required=False,
                )
            mapped.append((binding.name, binding.kind, socket))
        context.values.expression_plans[str(program_node.handle)] = (
            expression,
            tuple(mapped),
        )
        return data

    def evaluate(self, context, op):
        target = op.data["outputFloatTrack"]
        if target not in op.track_values:
            return op.child
        plan = context.values.expression_plans[op.handle]
        expression, _bindings = plan
        if expression.return_type != "scalar":
            return op.child
        op.track_values[target] = expression.evaluate_scalar(
            context.values.expression_inputs(plan, set(), track_values=op.track_values)
        )
        evaluation = PoseOpEvaluation((), (target,))
        return evaluation
