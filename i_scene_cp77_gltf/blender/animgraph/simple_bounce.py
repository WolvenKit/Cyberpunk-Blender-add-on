from __future__ import annotations

from typing import Any

from ...animation.model.animgraph import indices, simple_bounce
from ...animation.model.animgraph.indices import index_name
from .access import (
    clear_collection,
    get_attr,
    node_property_map,
    property_bool,
    property_float,
    property_string,
)


def capture_import_state(node: Any, data: dict) -> None:
    normalized = simple_bounce.normalize_data(data)
    data.clear()
    data.update(normalized)

    transforms = getattr(node, "red_simple_bounce_transform_outputs", None)
    tracks = getattr(node, "red_simple_bounce_track_outputs", None)
    if transforms is None or tracks is None:
        return
    clear_collection(transforms)
    clear_collection(tracks)
    for raw in normalized.get("transformOutputs", ()) or ():
        item = transforms.add()
        item.target_transform = index_name(
            raw.get("targetTransform"), "animTransformIndex", allow_text=False
        )
        item.parent_transform = index_name(
            raw.get("parentTransform"), "animTransformIndex", allow_text=False
        )
        item.expanded = True
        for raw_entry in raw.get("channelEntries", ()) or ():
            entry = item.channel_entries.add()
            entry.transform_channel = str(
                raw_entry.get("transformChannel", "PosX") or "PosX"
            )
            entry.multiplier = float(raw_entry.get("multiplier", 1.0))
    for raw in normalized.get("trackOutputs", ()) or ():
        item = tracks.add()
        item.target_track = index_name(
            raw.get("targetTrack"), "animNamedTrackIndex", allow_text=False
        )
        item.multiplier = float(raw.get("multiplier", 1.0))
        item.expanded = True


def seed_authored_state(node: Any) -> None:
    transforms = getattr(node, "red_simple_bounce_transform_outputs", None)
    tracks = getattr(node, "red_simple_bounce_track_outputs", None)
    if transforms is not None:
        clear_collection(transforms)
    if tracks is not None:
        clear_collection(tracks)


def transform_outputs_data(node: Any) -> list[dict]:
    result = []
    for item in getattr(node, "red_simple_bounce_transform_outputs", ()) or ():
        entries = [
            simple_bounce.channel_entry(entry.transform_channel, entry.multiplier)
            for entry in getattr(item, "channel_entries", ()) or ()
        ]
        result.append(
            simple_bounce.transform_output(
                str(getattr(item, "target_transform", "") or ""),
                str(getattr(item, "parent_transform", "") or ""),
                entries,
            )
        )
    return result


def track_outputs_data(node: Any) -> list[dict]:
    return [
        simple_bounce.track_output(
            str(getattr(item, "target_track", "") or ""),
            float(getattr(item, "multiplier", 1.0)),
        )
        for item in getattr(node, "red_simple_bounce_track_outputs", ()) or ()
    ]


def canonicalize_node_data(node: Any, data: dict) -> dict:
    if str(get_attr(node, "red_type", "") or "") != simple_bounce.RED_TYPE:
        return data
    out = dict(data)
    out["transformOutputs"] = transform_outputs_data(node)
    out["trackOutputs"] = track_outputs_data(node)
    out["areChannelsResaved"] = 1
    return simple_bounce.canonicalize_for_export(out)


def validation_data(node: Any) -> dict:
    properties = node_property_map(node)
    data = simple_bounce.authored_defaults()
    data["startTransform"] = indices.transform_index(
        property_string(properties, "startTransform")
    )
    data["endTransform"] = indices.transform_index(
        property_string(properties, "endTransform")
    )
    data["outputDriverTrack"] = indices.track_index(
        property_string(properties, "outputDriverTrack")
    )
    data["multiplier"] = property_float(properties, "multiplier", 1.0)
    data["negativeMultiplier"] = property_float(properties, "negativeMultiplier", 1.0)
    data["smoothStep"] = property_float(properties, "smoothStep", 1.0)
    data["offset"] = property_float(properties, "offset", 0.0)
    data["delay"] = property_float(properties, "delay", 0.0)
    data["debug"] = int(property_bool(properties, "debug", False))
    data["transformOutputs"] = transform_outputs_data(node)
    data["trackOutputs"] = track_outputs_data(node)
    return simple_bounce.canonicalize_for_export(data)


def runtime_data(node: Any) -> dict:
    properties = node_property_map(node)
    return {
        "startTransform": property_string(properties, "startTransform"),
        "endTransform": property_string(properties, "endTransform"),
        "multiplier": property_float(properties, "multiplier", 1.0),
        "negativeMultiplier": property_float(properties, "negativeMultiplier", 1.0),
        "smoothStep": property_float(properties, "smoothStep", 1.0),
        "offset": property_float(properties, "offset", 0.0),
        "delay": property_float(properties, "delay", 0.0),
        "debug": property_bool(properties, "debug", False),
        "outputDriverTrack": property_string(properties, "outputDriverTrack"),
        "transformOutputs": [
            {
                "targetTransform": index_name(
                    item.get("targetTransform"), "animTransformIndex", allow_text=False
                ),
                "parentTransform": index_name(
                    item.get("parentTransform"), "animTransformIndex", allow_text=False
                ),
                "channelEntries": [
                    {
                        "transformChannel": str(entry.get("transformChannel", "PosX")),
                        "multiplier": float(entry.get("multiplier", 1.0)),
                    }
                    for entry in item.get("channelEntries", ()) or ()
                ],
            }
            for item in transform_outputs_data(node)
        ],
        "trackOutputs": [
            {
                "targetTrack": index_name(
                    item.get("targetTrack"), "animNamedTrackIndex", allow_text=False
                ),
                "multiplier": float(item.get("multiplier", 1.0)),
            }
            for item in track_outputs_data(node)
        ],
    }
