from __future__ import annotations

from ....animation.domain.animgraph.pose_program import pure_pose_op_data
from ....animation.domain.animgraph.set_bone_transform import (
    evaluate_set_bone_transform,
)
from ..property_codec import encode_node_properties
from .base import NodeEvaluation, NodeSpec, PoseNodeHandler, PosePreviewError, text
from .registry import register_pose_node_handler

RED_TYPE = "animAnimNode_SetBoneTransform"
_SET_METHODS = {"NoSnapping", "WholeTransform", "TranslationOnly", "RotationOnly"}


def _entries(spec):
    return tuple(spec.data.get("entries", ()) or ())


@register_pose_node_handler(RED_TYPE)
class SetBoneTransformHandler(PoseNodeHandler):
    label = "SetBoneTransform"

    def spec(self, node, tree):
        return NodeSpec(pure_pose_op_data(RED_TYPE, encode_node_properties(node)))

    def bone_names(self, spec):
        return {text(entry, "transformToChange") for entry in _entries(spec)}

    def optional_bone_names(self, spec):
        names = set()
        for entry in _entries(spec):
            names.add(text(entry, "sourceBone"))
            names.add(text(entry, "offsetSpaceBone"))
        return names

    def executable(self, spec, index, binding, *, validate_schema):
        entries = _entries(spec)
        targets = tuple(text(entry, "transformToChange") for entry in entries)
        if any(not name for name in targets):
            raise PosePreviewError(
                f"SetBoneTransform chain node {index + 1}: missing transformToChange"
            )
        invalid = next(
            (
                text(entry, "setMethod")
                for entry in entries
                if str(entry.get("setMethod", "WholeTransform") or "WholeTransform")
                not in _SET_METHODS
            ),
            "",
        )
        if invalid:
            raise PosePreviewError(
                f"SetBoneTransform chain node {index + 1}: unsupported setMethod {invalid!r}"
            )
        return all(binding.has_bone(name) for name in targets)

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_set_bone_transform(
            state,
            plan.parent_map,
            plan.reference_pose_ms,
            spec.data.get("entries", ()) or (),
        )
        return NodeEvaluation(evaluation.transforms_written)
