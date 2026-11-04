from __future__ import annotations

from ...domain.animgraph.translation_limit import evaluate_translation_limit
from .base import PoseOpHandler


class TranslationLimitHandler(PoseOpHandler):
    node_types = ("animAnimNode_TranslationLimit",)
    bone_fields = ("constrainedTransform", "parentTransform")
    uses_tracks = False

    def evaluate(self, context, op):
        evaluation = evaluate_translation_limit(
            op.pose, op.child.parent_map, op.data, model_space=op.child.model_space
        )
        return evaluation
