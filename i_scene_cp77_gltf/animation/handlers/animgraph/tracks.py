from __future__ import annotations

from collections.abc import Mapping

from ...domain.animgraph.vehicle import (
    apply_additional_float_tracks,
    apply_float_track_modifier,
    apply_transform_to_track,
)
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler, resolve_tracks


class TrackSetterHandler(PoseOpHandler):
    node_types = ("animAnimNode_TrackSetter",)
    track_fields = ("track",)

    def evaluate(self, context, op):
        target = op.data["track"]
        if target not in op.track_values or not op.data["hasValue"]:
            return op.child
        op.track_values[target] = context.values.linked(
            "float", op.handle, "value", 0.0
        )
        evaluation = PoseOpEvaluation((), (target,))
        return evaluation


class AdditionalFloatTrackHandler(PoseOpHandler):
    node_types = ("animAnimNode_AdditionalFloatTrack",)

    def map_data(self, context, program_node, node_type, data):
        container = (
            data.get("additionalTracks")
            if isinstance(data.get("additionalTracks"), Mapping)
            else {}
        )
        for entry in container.get("entries", ()) or ():
            if not isinstance(entry, Mapping):
                continue
            info = (
                entry.get("trackInfo")
                if isinstance(entry.get("trackInfo"), Mapping)
                else {}
            )
            raw_name = info.get("name", "")
            if isinstance(raw_name, Mapping):
                raw_name = raw_name.get("$value", raw_name.get("value", ""))
            name = str(raw_name or "")
            if name and name != "None":
                context.required_tracks.add(name)
        data["_usesTracks"] = True
        return data

    def evaluate(self, context, op):
        values = {
            name: float(snapshot.value)
            for name, snapshot in op.tracks.items()
            if bool(snapshot.existed) or name in context._stack_track_names
        }
        current_time = float(
            context._additional_track_times.get(op.handle, 0.0)
        ) + float(context._current_raw_dt)
        written = apply_additional_float_tracks(
            values, op.data.get("additionalTracks"), current_time
        )
        context._additional_track_times[op.handle] = current_time
        for name in written:
            op.track_values[name] = float(values[name])
        evaluation = PoseOpEvaluation((), tuple(written))
        return evaluation


class FloatTrackModifierHandler(PoseOpHandler):
    node_types = (
        "animAnimNode_FloatTrackModifier",
        "animAnimNode_FloatTrackModifierMarkUnstable",
    )
    track_fields = ("floatTrack",)
    uses_tracks = True

    def map_data(self, context, program_node, node_type, data):
        data = super().map_data(context, program_node, node_type, data)
        resolve_tracks(context, data, ("inputFloatTrack",), optional=True)
        return data

    def evaluate(self, context, op):
        target = str(op.data.get("floatTrack", "") or "")
        input_track = str(op.data.get("inputFloatTrack", "") or "")
        input_value = (
            context.values.linked("float", op.handle, "floatInputNode", 0.0)
            if op.data.get("hasFloatInputNode")
            else 0.0
        )
        applied = apply_float_track_modifier(
            op.track_values,
            target=target,
            operation=str(op.data.get("operationType", "Override") or "Override"),
            input_track=input_track,
            input_value=input_value,
        )
        evaluation = PoseOpEvaluation(
            (),
            (target,) if applied else (),
            applied,
            "target track is absent" if not applied else "",
        )
        return evaluation


class TransformToTrackHandler(PoseOpHandler):
    node_types = ("animAnimNode_TransformToTrack",)
    bone_fields = ("transformIndex",)
    track_fields = ("floatTrackIndex",)
    uses_tracks = True

    def evaluate(self, context, op):
        target_bone = str(op.data.get("transformIndex", "") or "")
        target_track = str(op.data.get("floatTrackIndex", "") or "")
        weight = (
            context.values.linked(
                "float",
                op.handle,
                "weightNode",
                float(op.data.get("weight", 1.0) or 0.0),
            )
            if op.data.get("hasWeightNode")
            else float(op.data.get("weight", 1.0) or 0.0)
        )
        mul_factor = (
            context.values.linked(
                "float",
                op.handle,
                "mulFactorNode",
                float(op.data.get("mulFactor", 1.0) or 0.0),
            )
            if op.data.get("hasMulFactorNode")
            else float(op.data.get("mulFactor", 1.0) or 0.0)
        )
        if target_bone not in op.pose or target_track not in op.track_values:
            return op.child
        applied = apply_transform_to_track(
            op.track_values,
            op.pose[target_bone],
            target_track=target_track,
            channel=str(op.data.get("channel", "PosX") or "PosX"),
            mul_factor=mul_factor,
            weight=weight,
        )
        evaluation = PoseOpEvaluation(
            (),
            (target_track,) if applied else (),
            applied,
            "target track is absent" if not applied else "",
        )
        return evaluation
