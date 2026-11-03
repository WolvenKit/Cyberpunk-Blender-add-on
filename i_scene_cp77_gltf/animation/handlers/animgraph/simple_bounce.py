from __future__ import annotations

from ...domain.animgraph.simple_bounce import evaluate_simple_bounce
from .base import PoseOpHandler, resolve_bones, resolve_tracks


class SimpleBounceHandler(PoseOpHandler):
    node_types = ("animAnimNode_SimpleBounce",)

    def map_data(self, context, program_node, node_type, data):
        resolve_bones(context, data, ("startTransform", "endTransform"))
        outputs = []
        for raw in data.get("transformOutputs", ()):
            item = dict(raw)
            resolve_bones(context, item, ("targetTransform", "parentTransform"))
            channel_ops = tuple(
                (
                    str(entry.get("transformChannel", "PosX") or "PosX"),
                    float(entry.get("multiplier", 1.0)),
                )
                for entry in (item.get("channelEntries", ()) or ())
            )
            item["_channelOps"] = channel_ops
            item["_translationOnly"] = bool(channel_ops) and all(
                channel in {"PosX", "PosY", "PosZ"}
                for channel, _multiplier in channel_ops
            )
            outputs.append(item)
        data["transformOutputs"] = tuple(outputs)
        track_outputs = []
        for raw in data.get("trackOutputs", ()):
            item = dict(raw)
            resolve_tracks(context, item, ("targetTrack",), optional=True)
            item["multiplier"] = float(item.get("multiplier", 1.0))
            track_outputs.append(item)
        data["trackOutputs"] = tuple(track_outputs)
        resolve_tracks(context, data, ("outputDriverTrack",), optional=True)
        data["_driverParams"] = (
            float(data.get("multiplier", 1.0)),
            float(data.get("negativeMultiplier", 1.0)),
            float(data.get("smoothStep", 1.0)),
            float(data.get("offset", 0.0)),
            float(data.get("delay", 0.0)),
        )
        data["_usesTracks"] = bool(
            data.get("trackOutputs", ()) or str(data.get("outputDriverTrack", "") or "")
        )
        return data

    def evaluate(self, context, op):
        evaluation = evaluate_simple_bounce(
            op.pose,
            op.track_values,
            op.child.parent_map,
            op.data,
            model_space=op.child.model_space,
        )
        return evaluation
