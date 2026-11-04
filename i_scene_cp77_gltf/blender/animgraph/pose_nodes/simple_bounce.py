from __future__ import annotations

from ....animation.domain.animgraph.simple_bounce import evaluate_simple_bounce
from ....animation.model.animgraph import simple_bounce
from ...action_metadata import armature_track_names
from .. import rig_binding
from .. import simple_bounce as simple_bounce_adapter
from .base import NodeEvaluation, NodeSpec, PoseNodeHandler, check_schema, text
from .registry import register_pose_node_handler


@register_pose_node_handler(simple_bounce.RED_TYPE)
class SimpleBounceHandler(PoseNodeHandler):
    label = "SimpleBounce"

    def spec(self, node, tree):
        return NodeSpec(
            simple_bounce_adapter.runtime_data(node),
            simple_bounce_adapter.validation_data(node),
        )

    def bone_names(self, spec):
        data = spec.data
        names = {text(data, "startTransform"), text(data, "endTransform")}
        for output in data.get("transformOutputs", ()) or ():
            names.add(text(output, "targetTransform"))
            parent = text(output, "parentTransform")
            if parent:
                names.add(parent)
        return names

    def track_names(self, spec):
        return {
            name
            for output in spec.data.get("trackOutputs", ()) or ()
            if (name := text(output, "targetTrack"))
        }

    def optional_track_names(self, spec):
        driver = text(spec.data, "outputDriverTrack")
        return {driver} if driver else set()

    def executable(self, spec, index, binding, *, validate_schema):
        validation = simple_bounce.validate_data(spec.validation_data)
        required_bones = {
            text(spec.data, "startTransform"),
            text(spec.data, "endTransform"),
        }
        required_bones.update(
            text(output, "targetTransform")
            for output in spec.data.get("transformOutputs", ()) or ()
        )
        required_tracks = {
            text(output, "targetTrack")
            for output in spec.data.get("trackOutputs", ()) or ()
        }
        check_schema(self.label, validation, index, validate_schema)
        return all(binding.has_bone(name) for name in required_bones) and all(
            binding.has_track(name) for name in required_tracks
        )

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_simple_bounce(state, tracks, plan.parent_map, spec.data)
        return NodeEvaluation(evaluation.transforms_written, evaluation.tracks_written)

    def node_validation(self, node, armature):
        tree = getattr(node, "id_data", None)
        bound = armature is not None
        return simple_bounce.validate_data(
            simple_bounce_adapter.validation_data(node),
            rig_names=rig_binding.bound_rig_names(tree) if bound else None,
            rig_parents=rig_binding.bound_rig_parent_map(tree) if bound else None,
            track_names=armature_track_names(armature) if bound else None,
        )
