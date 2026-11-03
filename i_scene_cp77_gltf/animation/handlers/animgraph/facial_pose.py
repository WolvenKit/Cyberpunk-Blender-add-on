from __future__ import annotations

from ...domain.animgraph.facial_pose import (
    evaluate_eyes_tracks,
    evaluate_set_bone_position,
    remap_track_range,
)
from ...domain.facial.graph import evaluate_facial_graph
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.frames import BranchFrame, TrackSnapshot
from .base import PoseOpHandler


class SermoHandler(PoseOpHandler):
    node_types = ("animAnimNode_Sermo",)

    def evaluate(self, context, op):
        if op.child.model_space:
            raise ValueError("Sermo requires a local-space input pose")
        if context._facial_binding is None:
            raise ValueError("Sermo has no bound facial solver")
        context._trace_facial_frame("sermo_input", op.child)
        solved_pose, solved_tracks = evaluate_facial_graph(
            context._facial_binding,
            op.pose,
            op.track_values,
            lod=context.host.settings.skeletal_lod,
        )
        op.tracks = dict(op.child.tracks)
        for name, value in solved_tracks.items():
            previous = op.tracks.get(
                name, TrackSnapshot(context.host.has_track(name), 0.0)
            )
            op.tracks[name] = TrackSnapshot(previous.existed, value)
        result = BranchFrame(
            solved_pose,
            op.tracks,
            op.child.parent_map,
            op.child.reference_pose,
            op.child.reference_tracks,
            op.child.transform_scopes,
            op.child.track_scopes,
            op.child.model_space,
            ik_targets=op.child.ik_targets,
        )
        context._trace_facial_frame("sermo_output", result)
        return result


class EyesTracksLookAtHandler(PoseOpHandler):
    node_types = ("animAnimNode_EyesTracksLookAt",)
    bone_fields = ("eyeTransform",)
    track_fields = ("leftTrack", "rightTrack", "upTrack", "downTrack")

    def evaluate(self, context, op):
        evaluation = evaluate_eyes_tracks(op.pose, op.track_values, op.data)
        return evaluation


class SetTrackRangeHandler(PoseOpHandler):
    node_types = ("animAnimNode_SetTrackRange",)
    track_fields = ("track",)

    def evaluate(self, context, op):
        target = op.data["track"]
        if target not in op.track_values:
            return op.child
        limits = [
            context.values.linked("float", op.handle, key + "Link", op.data[key])
            for key in ("min", "max", "oldMin", "oldMax")
        ]
        op.track_values[target] = remap_track_range(op.track_values[target], *limits)
        evaluation = PoseOpEvaluation((), (target,))
        return evaluation


class SetBonePositionHandler(PoseOpHandler):
    node_types = ("animAnimNode_SetBonePosition",)
    bone_fields = ("bone",)

    def evaluate(self, context, op):
        if not op.data["hasPosition"]:
            return op.child
        position = context.values.linked(
            "vector", op.handle, "positionMs", (0.0, 0.0, 0.0)
        )
        evaluation = evaluate_set_bone_position(
            op.pose,
            op.child.parent_map,
            op.data["bone"],
            position,
            model_space=op.child.model_space,
        )
        return evaluation
