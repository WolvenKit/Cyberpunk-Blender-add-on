from __future__ import annotations

from ....animation.domain.animgraph.simple_spline import evaluate_simple_spline
from ....animation.model.animgraph import simple_spline
from ..access import node_property_map, property_float, property_string
from .base import (
    NodeEvaluation,
    NodeSpec,
    PoseNodeHandler,
    PosePreviewError,
    float_track_requested,
    text,
)
from .registry import register_pose_node_handler

_TRANSFORM_KEYS = (
    "startTransform",
    "middleTransform",
    "endTransform",
    "constrainedTransform",
)


@register_pose_node_handler(simple_spline.RED_TYPE)
class SimpleSplineHandler(PoseNodeHandler):
    label = "SimpleSpline"

    def spec(self, node, tree):
        properties = node_property_map(node)
        return NodeSpec(
            {
                "startTransform": property_string(properties, "startTransform"),
                "middleTransform": property_string(properties, "middleTransform"),
                "endTransform": property_string(properties, "endTransform"),
                "constrainedTransform": property_string(
                    properties, "constrainedTransform"
                ),
                "progressMode": property_string(properties, "progressMode") or "Static",
                "defaultProgress": property_float(properties, "defaultProgress", 0.0),
                "progressTrack": property_string(properties, "progressTrack"),
            }
        )

    def bone_names(self, spec):
        return {text(spec.data, key) for key in _TRANSFORM_KEYS}

    def track_names(self, spec):
        return float_track_requested(spec.data, "progressMode", "progressTrack")

    def executable(self, spec, index, binding, *, validate_schema):
        required = tuple(text(spec.data, key) for key in _TRANSFORM_KEYS)
        if not all(required):
            raise PosePreviewError(
                f"SimpleSpline chain node {index + 1}: missing required transform"
            )
        mode = str(spec.data.get("progressMode", "Static") or "Static")
        if mode not in {"Static", "FloatTrack"}:
            raise PosePreviewError(
                f"SimpleSpline chain node {index + 1}: unsupported progress mode {mode!r}"
            )
        if mode == "FloatTrack" and not text(spec.data, "progressTrack"):
            raise PosePreviewError(
                f"SimpleSpline chain node {index + 1}: FloatTrack mode has no progress track"
            )
        binding_ready = all(binding.has_bone(name) for name in required)
        if mode == "FloatTrack":
            binding_ready = binding_ready and binding.has_track(
                text(spec.data, "progressTrack")
            )
        return binding_ready

    def evaluate(self, spec, plan, state, tracks):
        evaluation = evaluate_simple_spline(state, tracks, plan.parent_map, spec.data)
        written = (evaluation.constrained,) if evaluation.applied else ()
        return NodeEvaluation(
            written, (), int(spec.data.get("progressMode") == "FloatTrack")
        )
