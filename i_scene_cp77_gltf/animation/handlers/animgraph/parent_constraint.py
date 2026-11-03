from __future__ import annotations

from ...domain.animgraph.parent_constraint import (
    evaluate_multiple_parent_constraint,
    evaluate_parent_constraint,
)
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class ParentConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_ParentConstraint",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("transformIndex", "parentTransformIndex"))
        resolve_tracks(context, data, ("weightFloatTrack",), optional=True)
        data["_usesTracks"] = bool(str(data.get("weightFloatTrack", "") or ""))
        return data

    def evaluate(self, context, op):
        weight = (
            context.values.linked("float", op.handle, "weightNode", op.data["weight"])
            if op.data.get("hasWeightNode")
            else op.data["weight"]
        )
        track = str(op.data.get("weightFloatTrack", "") or "")
        if track in op.track_values:
            # A resolved weight track overrides the node or static weight, unclamped.
            weight = op.track_values[track]
        evaluation = evaluate_parent_constraint(
            op.pose,
            op.child.parent_map,
            op.child.reference_pose,
            op.data,
            weight,
            offset_translation=(
                context.values.linked(
                    "vector", op.handle, "offsetTranslationLS", (0.0, 0.0, 0.0)
                )
                if op.data.get("hasOffsetTranslation")
                else None
            ),
            offset_euler=(
                context.values.linked(
                    "vector", op.handle, "offsetEulerRotationLS", (0.0, 0.0, 0.0)
                )
                if op.data.get("hasOffsetRotation")
                else None
            ),
            model_space=op.child.model_space,
        )
        return evaluation


class MultipleParentConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_MultipleParentConstraint",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("transformIndex",))
        infos = []
        for raw in data.get("parentsTransforms", ()):
            item = dict(raw)
            resolve_bones(context, item, ("parentTransform",))
            resolve_tracks(context, item, ("parentTrackWeight",), optional=True)
            infos.append(item)
        data["parentsTransforms"] = tuple(infos)
        resolve_tracks(context, data, ("weightFloatTrack",), optional=True)
        data["_usesTracks"] = str(
            data.get("weightMode", "Static") or "Static"
        ) == "FloatTrack" or any(
            str(item.get("parentWeightMode", "Static") or "Static") == "FloatTrack"
            for item in data.get("parentsTransforms", ()) or ()
        )
        return data

    def evaluate(self, context, op):
        evaluation = evaluate_multiple_parent_constraint(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            model_space=op.child.model_space,
        )
        return evaluation
