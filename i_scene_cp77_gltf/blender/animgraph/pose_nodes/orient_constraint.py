from __future__ import annotations

from ....animation.domain.animgraph.orient_constraint import evaluate_orient_constraint
from ....animation.domain.animgraph.pose_program import pure_pose_op_data
from ..property_codec import encode_node_properties
from .base import (
    NodeEvaluation,
    NodeSpec,
    PoseNodeHandler,
    PosePreviewError,
    float_track_requested,
    text,
)
from .registry import register_pose_node_handler

RED_TYPE = "animAnimNode_OrientConstraint"


def _inputs(spec):
    return tuple(spec.data.get("inputWeightedTransforms", ()) or ())


@register_pose_node_handler(RED_TYPE)
class OrientConstraintHandler(PoseNodeHandler):
    label = "OrientConstraint"

    def spec(self, node, tree):
        return NodeSpec(pure_pose_op_data(RED_TYPE, encode_node_properties(node)))

    def bone_names(self, spec):
        names = {text(spec.data, "transformIndex")}
        names.update(text(entry, "transform") for entry in _inputs(spec))
        return names

    def track_names(self, spec):
        return float_track_requested(spec.data, "weightMode", "weightFloatTrack")

    def executable(self, spec, index, binding, *, validate_schema):
        entries = _inputs(spec)
        target = text(spec.data, "transformIndex")
        if not entries or not target:
            raise PosePreviewError(
                f"OrientConstraint chain node {index + 1}: missing target or input transforms"
            )
        mode = str(spec.data.get("weightMode", "Static") or "Static")
        if mode not in {"Static", "FloatTrack"}:
            raise PosePreviewError(
                f"OrientConstraint chain node {index + 1}: unsupported weight mode {mode!r}"
            )
        required = (target, *(text(entry, "transform") for entry in entries))
        binding_ready = all(binding.has_bone(name) for name in required)
        if mode == "FloatTrack":
            binding_ready = binding_ready and binding.has_track(
                text(spec.data, "weightFloatTrack")
            )
        return binding_ready

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_orient_constraint(
            state, tracks, plan.parent_map, spec.data
        )
        return NodeEvaluation(
            evaluation.transforms_written,
            (),
            int(text(spec.data, "weightMode") == "FloatTrack"),
        )
