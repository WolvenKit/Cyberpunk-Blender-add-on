from __future__ import annotations

from ....animation.domain.animgraph.twist_constraint import evaluate_twist_constraint
from ....animation.model.animgraph import twist_constraint
from .. import twist_constraint as twist_constraint_adapter
from .base import NodeEvaluation, NodeSpec, PoseNodeHandler, text
from .registry import register_pose_node_handler


@register_pose_node_handler(twist_constraint.RED_TYPE)
class TwistConstraintHandler(PoseNodeHandler):
    label = "TwistConstraint"

    def spec(self, node, tree):
        return NodeSpec(twist_constraint_adapter.runtime_data(node))

    def optional_bone_names(self, spec):
        names = {text(spec.data, "transformA"), text(spec.data, "transformB")}
        names.update(
            text(output, "twistedTransform")
            for output in spec.data.get("outputs", ()) or ()
        )
        return names

    def optional_track_names(self, spec):
        return {
            name
            for output in spec.data.get("outputs", ()) or ()
            if (name := text(output, "outputAngleTrack"))
        }

    def executable(self, spec, index, binding, *, validate_schema):
        return binding.has_bone(text(spec.data, "transformA")) and binding.has_bone(
            text(spec.data, "transformB")
        )

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_twist_constraint(
            state,
            tracks,
            plan.parent_map,
            spec.data,
            reference_pose_ms=plan.reference_pose_ms,
        )
        return NodeEvaluation(evaluation.transforms_written, evaluation.tracks_written)
