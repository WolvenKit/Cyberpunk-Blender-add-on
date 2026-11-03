from __future__ import annotations

from ....animation.domain.animgraph.point_constraint import evaluate_point_constraint
from ....animation.model.animgraph import point_constraint
from ...action_metadata import armature_track_names
from .. import point_constraint as point_constraint_adapter
from .. import rig_binding
from .base import (
    NodeEvaluation,
    NodeSpec,
    PoseNodeHandler,
    check_schema,
    float_track_requested,
    text,
)
from .registry import register_pose_node_handler


@register_pose_node_handler(point_constraint.RED_TYPE)
class PointConstraintHandler(PoseNodeHandler):
    label = "PointConstraint"

    def spec(self, node, tree):
        return NodeSpec(
            point_constraint_adapter.runtime_data(node),
            point_constraint_adapter.validation_data(node),
        )

    def bone_names(self, spec):
        names = {text(spec.data, "transformIndex")}
        names.update(
            text(entry, "transform")
            for entry in spec.data.get("inputWeightedTransforms", ()) or ()
        )
        return names

    def track_names(self, spec):
        return float_track_requested(spec.data, "weightMode", "weightFloatTrack")

    def executable(self, spec, index, binding, *, validate_schema):
        validation = point_constraint.validate_data(spec.validation_data)
        binding_ready = all(binding.has_bone(name) for name in self.bone_names(spec))
        if text(spec.data, "weightMode") == "FloatTrack":
            binding_ready = binding_ready and binding.has_track(
                text(spec.data, "weightFloatTrack")
            )
        check_schema(self.label, validation, index, validate_schema)
        return binding_ready

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_point_constraint(
            state, tracks, plan.parent_map, spec.data
        )
        written = (evaluation.target,) if evaluation.applied else ()
        return NodeEvaluation(
            written, (), int(str(spec.data.get("weightMode", "")) == "FloatTrack")
        )

    def node_validation(self, node, armature):
        return point_constraint.validate_data(
            point_constraint_adapter.validation_data(node),
            rig_names=rig_binding.bound_rig_names(getattr(node, "id_data", None))
            or None,
            track_names=armature_track_names(armature) or None,
        )
