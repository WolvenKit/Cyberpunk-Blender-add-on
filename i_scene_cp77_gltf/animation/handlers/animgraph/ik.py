from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...domain.animgraph.ik import (
    add_ik_request,
    evaluate_ik2,
    evaluate_ik2_constraint,
    read_ik_request,
)
from ...domain.animgraph.source_channels import evaluate_vector
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class AddIkRequestHandler(PoseOpHandler):
    node_types = ("animAnimNode_AddIkRequest",)
    bone_fields = ("targetBone", "poleTargetBone")
    uses_tracks = False

    def evaluate(self, context, op):
        op.ik_targets = add_ik_request(
            op.ik_targets,
            op.data,
            op.pose,
            op.child.parent_map,
            model_space=op.child.model_space,
        )
        evaluation = PoseOpEvaluation((), ())
        return evaluation


class ReadIkRequestHandler(PoseOpHandler):
    node_types = ("animAnimNode_ReadIkRequest",)
    bone_fields = ("outTransform",)
    uses_tracks = False

    def evaluate(self, context, op):
        bone = str(op.data.get("outTransform", "") or "")
        written = read_ik_request(
            op.pose,
            op.child.parent_map,
            op.ik_targets,
            str(op.data.get("ikChain", "") or ""),
            bone,
            model_space=op.child.model_space,
        )
        evaluation = PoseOpEvaluation((bone,) if written else (), ())
        return evaluation


class Ik2ConstraintHandler(PoseOpHandler):
    node_types = ("animAnimNode_Ik2Constraint",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("firstBone", "secondBone", "endBone"))
        parent = context.host.bone_parent(data["firstBone"])
        if parent is not None:
            # The solver starts from the first bone's model-space parent.
            context.required_bones.add(parent)
        for key in ("inputTarget", "inputPoleVector"):
            channel = data.get(key)
            if isinstance(channel, Mapping):
                channel = dict(channel)
                for field in ("transformIndex", "inputTransformIndex"):
                    if field in channel:
                        channel[field] = context.resolve_structured_bone(
                            str(channel.get(field, "") or ""), required=False
                        )
                data[key] = channel
        resolve_tracks(context, data, ("weightFloatTrack",), optional=True)
        data["_usesTracks"] = bool(str(data.get("weightFloatTrack", "") or ""))
        return data

    def evaluate(self, context, op):
        weight = float(op.data.get("weight", 1.0))
        if op.data.get("hasWeightNode"):
            weight = min(
                1.0,
                max(
                    0.0, context.values.linked("float", op.handle, "weightNode", weight)
                ),
            )
        weight_track = str(op.data.get("weightFloatTrack", "") or "")
        if weight_track and weight_track in op.track_values:
            weight = min(1.0, max(0.0, float(op.track_values[weight_track])))
        twist = (
            context.values.linked(
                "float", op.handle, "twistNode", float(op.data.get("twistValue", 0.0))
            )
            if op.data.get("hasTwistNode")
            else float(op.data.get("twistValue", 0.0))
        )
        reference_ms = None
        channels = []
        cache: dict[str, Any] = {}
        for key in ("inputTarget", "inputPoleVector"):
            channel = op.data.get(key)
            if not isinstance(channel, Mapping):
                channels.append(None)
                continue
            if (
                reference_ms is None
                and channel.get("$type")
                == "animAnimNodeSourceChannel_ReferenceTransformVector"
            ):
                reference_ms = context._reference_model_pose(op.child)
            try:
                channels.append(
                    evaluate_vector(
                        channel,
                        op.pose,
                        op.child.parent_map,
                        reference_pose_ms=reference_ms,
                        cache=cache,
                        model_space=op.child.model_space,
                    ).value
                )
            except KeyError:
                # An unresolved transform index reads as the origin.
                channels.append((0.0, 0.0, 0.0))
        written = evaluate_ik2_constraint(
            op.pose,
            op.child.parent_map,
            op.data,
            channels[0],
            channels[1],
            weight,
            twist,
            model_space=op.child.model_space,
        )
        evaluation = PoseOpEvaluation(written, ())
        return evaluation


class Ik2Handler(PoseOpHandler):
    node_types = ("animAnimNode_Ik2",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("firstBone", "secondBone", "endBone"))
        resolve_bones(context, data, ("bone",), optional=True)
        parent = context.host.bone_parent(data["firstBone"])
        if parent is not None:
            # The solver starts from the first bone's model-space parent.
            context.required_bones.add(parent)
        resolve_tracks(context, data, ("floatTrack",), optional=True)
        data["_usesTracks"] = bool(str(data.get("floatTrack", "") or ""))
        return data

    def evaluate(self, context, op):
        # The weight comes from its node, else from its float track, else it is 0.
        if op.data.get("hasWeightNode"):
            weight = context.values.linked("float", op.handle, "weightNode", 0.0)
        else:
            track = str(op.data.get("floatTrack", "") or "")
            weight = float(op.track_values.get(track, 0.0)) if track else 0.0
        target = (
            context.values.linked(
                "vector", op.handle, "endTargetPositionNode", (0.0, 0.0, 0.0)
            )
            if op.data.get("hasEndTargetPositionNode")
            else None
        )
        rotation = (
            context.values.linked(
                "quaternion",
                op.handle,
                "endTargetOrientationNode",
                (0.0, 0.0, 0.0, 1.0),
            )
            if op.data.get("hasEndTargetOrientationNode")
            else None
        )
        written = evaluate_ik2(
            op.pose,
            op.child.parent_map,
            op.data,
            weight,
            target,
            rotation,
            model_space=op.child.model_space,
        )
        return PoseOpEvaluation(written, ())
