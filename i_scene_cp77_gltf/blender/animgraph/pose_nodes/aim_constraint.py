from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....animation.domain.animgraph.aim_constraint import evaluate_aim_constraint
from ....animation.model.animgraph import aim_constraint
from ...action_metadata import armature_track_names
from .. import aim_constraint as aim_constraint_adapter
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


def _node_type(data: Mapping[str, Any]) -> str:
    return str(data.get("$type", aim_constraint.RED_TYPE) or aim_constraint.RED_TYPE)


@register_pose_node_handler(*aim_constraint.AIM_TYPES)
class AimConstraintHandler(PoseNodeHandler):
    label = "AimConstraint"

    def spec(self, node, tree):
        return NodeSpec(
            aim_constraint_adapter.runtime_data(node),
            aim_constraint_adapter.validation_data(node),
        )

    def bone_names(self, spec):
        data = spec.data
        names = {text(data, "transformIndex"), text(data, "targetTransform")}
        if _node_type(data) == aim_constraint.RED_TYPE:
            up_data = data.get("upTransform", {}) or {}
            names.add(text(up_data, "transformIndex"))
            names.add(text(up_data, "inputTransformIndex"))
        else:
            names.add(text(data, "upTransform"))
        return names

    def track_names(self, spec):
        return float_track_requested(spec.data, "weightMode", "weightFloatTrack")

    def executable(self, spec, index, binding, *, validate_schema):
        validation = aim_constraint.validate_data(spec.validation_data)
        binding_ready = all(
            binding.has_bone(name) for name in self.bone_names(spec) if name
        )
        if (
            spec.data.get("$type", aim_constraint.RED_TYPE) != aim_constraint.RED_TYPE
            and text(spec.data, "weightMode") == "FloatTrack"
        ):
            binding_ready = binding_ready and binding.has_track(
                text(spec.data, "weightFloatTrack")
            )
        check_schema(self.label, validation, index, validate_schema)
        return binding_ready

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_aim_constraint(
            state,
            tracks,
            plan.parent_map,
            spec.data,
            reference_pose_ms=plan.reference_pose_ms,
        )
        written = (evaluation.constrained,) if evaluation.applied else ()
        return NodeEvaluation(
            written, (), int(str(spec.data.get("weightMode", "")) == "FloatTrack")
        )

    def node_validation(self, node, armature):
        return aim_constraint.validate_data(
            aim_constraint_adapter.validation_data(node),
            rig_names=rig_binding.bound_rig_names(getattr(node, "id_data", None))
            or None,
            track_names=armature_track_names(armature) or None,
        )
