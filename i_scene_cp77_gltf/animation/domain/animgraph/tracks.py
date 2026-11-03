from __future__ import annotations

from ...model.animgraph.indices import index_name
from .topology import has_link


def track_setter_data(node_type, node):
    return {
        "track": index_name(node.get("track"), "animNamedTrackIndex", allow_text=True),
        "hasValue": has_link(node, "value"),
    }


def additional_float_track_data(node_type, node):
    return {"additionalTracks": node.get("additionalTracks") or {}}


def float_track_modifier_data(node_type, node):
    return {
        "floatTrack": index_name(
            node.get("floatTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "operationType": str(node.get("operationType", "Override") or "Override"),
        "inputFloatTrack": index_name(
            node.get("inputFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "hasFloatInputNode": has_link(node, "floatInputNode"),
    }


def transform_track_data(node_type, node):
    """TransformToTrack and FloatTrackDirectConnConstraint"""
    return {
        "floatTrackIndex": index_name(
            node.get("floatTrackIndex"), "animNamedTrackIndex", allow_text=True
        ),
        "transformIndex": index_name(
            node.get("transformIndex"), "animTransformIndex", allow_text=True
        ),
        "channel": str(node.get("channel", "PosX") or "PosX"),
        "mulFactor": float(node.get("mulFactor", 1.0) or 0.0),
        "weight": float(node.get("weight", 1.0) or 0.0),
        "hasWeightNode": has_link(node, "weightNode"),
        "hasMulFactorNode": has_link(node, "mulFactorNode"),
    }
