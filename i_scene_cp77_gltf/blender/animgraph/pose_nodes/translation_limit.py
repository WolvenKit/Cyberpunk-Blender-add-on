from __future__ import annotations

from ....animation.domain.animgraph.pose_program import pure_pose_op_data
from ....animation.domain.animgraph.translation_limit import evaluate_translation_limit
from ..property_codec import encode_node_properties
from .base import NodeEvaluation, NodeSpec, PoseNodeHandler, PosePreviewError, text
from .registry import register_pose_node_handler

RED_TYPE = "animAnimNode_TranslationLimit"


@register_pose_node_handler(RED_TYPE)
class TranslationLimitHandler(PoseNodeHandler):
    label = "TranslationLimit"

    def spec(self, node, tree):
        return NodeSpec(pure_pose_op_data(RED_TYPE, encode_node_properties(node)))

    def bone_names(self, spec):
        return {text(spec.data, "constrainedTransform")}

    def optional_bone_names(self, spec):
        return {text(spec.data, "parentTransform")}

    def executable(self, spec, index, binding, *, validate_schema):
        target = text(spec.data, "constrainedTransform")
        if not target:
            raise PosePreviewError(
                f"TranslationLimit chain node {index + 1}: missing constrainedTransform"
            )
        return binding.has_bone(target)

    def evaluate(self, spec, plan, state, tracks):
        return NodeEvaluation(
            evaluate_translation_limit(
                state, plan.parent_map, spec.data
            ).transforms_written
        )
