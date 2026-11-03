from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ....assetio.values import coerce_float
from . import indices
from .indices import index_name
from .validation import ValidationResult

RED_TYPE = "animAnimNode_SimpleBounce"
TRANSFORM_OUTPUT_TYPE = "animSimpleBounceTransformOutput"
CHANNEL_ENTRY_TYPE = "animSimpleBounceTransformOutput_ChannelEntry"
TRACK_OUTPUT_TYPE = "animSimpleBounceTrackOutput"
TRANSFORM_CHANNELS = (
    "PosX",
    "PosY",
    "PosZ",
    "RotX",
    "RotY",
    "RotZ",
    "ScaleX",
    "ScaleY",
    "ScaleZ",
)
LEGACY_AXIS_TO_CHANNEL = {
    "X_Axis": "PosX",
    "Y_Axis": "PosY",
    "Z_Axis": "PosZ",
    1: "PosX",
    2: "PosY",
    4: "PosZ",
}


def _channel(value: Any, default: str = "PosX") -> str:
    text = str(value or default)
    return text if text in TRANSFORM_CHANNELS else default


def channel_entry(channel: str = "PosX", multiplier: float = 1.0) -> dict:
    return {
        "$type": CHANNEL_ENTRY_TYPE,
        "transformChannel": _channel(channel),
        "multiplier": coerce_float(multiplier, 1.0, unwrap=False),
    }


def transform_output(
    target: str = "",
    parent: str = "",
    entries: Sequence[Mapping[str, Any]] | None = None,
    *,
    seed_default: bool = True,
) -> dict:
    raw_entries = (
        (channel_entry(),) if entries is None and seed_default else (entries or ())
    )
    normalized_entries = [
        channel_entry(
            entry.get("transformChannel", "PosX"), entry.get("multiplier", 1.0)
        )
        for entry in raw_entries
        if isinstance(entry, Mapping)
    ]
    first = normalized_entries[0] if normalized_entries else channel_entry()
    return {
        "$type": TRANSFORM_OUTPUT_TYPE,
        "targetTransform": indices.transform_index(target),
        "parentTransform": indices.transform_index(parent),
        "targetTransformChannel": first["transformChannel"],
        "multiplier": first["multiplier"],
        "channelEntries": normalized_entries,
    }


def track_output(target: str = "", multiplier: float = 1.0) -> dict:
    return {
        "$type": TRACK_OUTPUT_TYPE,
        "targetTrack": indices.track_index(target),
        "multiplier": coerce_float(multiplier, 1.0, unwrap=False),
    }


def _legacy_top_level_migration(data: dict) -> None:
    outputs = data.get("transformOutputs")
    if not isinstance(outputs, list):
        outputs = []
        data["transformOutputs"] = outputs

    if "targetTransform" in data:
        while len(outputs) < 1:
            outputs.append({})
        outputs[0]["targetTransform"] = copy.deepcopy(data.get("targetTransform"))
    if "targetTransformAxis" in data:
        while len(outputs) < 1:
            outputs.append({})
        raw_axis = data.get("targetTransformAxis")
        outputs[0]["targetTransformChannel"] = LEGACY_AXIS_TO_CHANNEL.get(
            raw_axis, "PosX"
        )

    tracks = data.get("trackOutputs")
    if not isinstance(tracks, list):
        tracks = []
        data["trackOutputs"] = tracks
    if "outputAngleTrack" in data:
        while len(tracks) < 1:
            tracks.append({})
        tracks[0]["targetTrack"] = copy.deepcopy(data.get("outputAngleTrack"))
        tracks[0]["multiplier"] = -1.0


def normalize_data(data: Any) -> dict:
    if not isinstance(data, dict):
        raise TypeError("SimpleBounce data must be an object")
    if str(data.get("$type", "")) != RED_TYPE:
        return dict(data)

    # Imported AnimGraph pose links can reference a deeply nested graph.  A
    # recursive deepcopy of the whole node is both unnecessary and can exceed
    # Python's recursion limit.  Normalize only the owned mutable fields.
    out = dict(data)
    raw_outputs = data.get("transformOutputs")
    if isinstance(raw_outputs, list):
        out["transformOutputs"] = [
            {
                **raw,
                "channelEntries": [
                    dict(entry) if isinstance(entry, dict) else entry
                    for entry in (raw.get("channelEntries", ()) or ())
                ],
            }
            if isinstance(raw, dict)
            else raw
            for raw in raw_outputs
        ]
    raw_tracks = data.get("trackOutputs")
    if isinstance(raw_tracks, list):
        out["trackOutputs"] = [
            dict(raw) if isinstance(raw, dict) else raw for raw in raw_tracks
        ]
    if isinstance(data.get("inputLink"), dict):
        out["inputLink"] = dict(data["inputLink"])
    _legacy_top_level_migration(out)
    resaved = bool(out.get("areChannelsResaved", False))

    normalized_outputs = []
    for raw in out.get("transformOutputs", ()) or ():
        item = raw if isinstance(raw, dict) else {}
        target = index_name(
            item.get("targetTransform"), "animTransformIndex", allow_text=False
        )
        parent = index_name(
            item.get("parentTransform"), "animTransformIndex", allow_text=False
        )
        if not resaved:
            entries = [
                channel_entry(
                    item.get("targetTransformChannel", "PosX"),
                    item.get("multiplier", 1.0),
                )
            ]
        else:
            entries = []
            for entry in item.get("channelEntries", ()) or ():
                if isinstance(entry, dict):
                    entries.append(
                        channel_entry(
                            entry.get("transformChannel", "PosX"),
                            entry.get("multiplier", 1.0),
                        )
                    )
        normalized_outputs.append(
            transform_output(target, parent, entries, seed_default=False)
        )

    normalized_tracks = []
    for raw in out.get("trackOutputs", ()) or ():
        item = raw if isinstance(raw, dict) else {}
        normalized_tracks.append(
            track_output(
                index_name(
                    item.get("targetTrack"), "animNamedTrackIndex", allow_text=False
                ),
                item.get("multiplier", 1.0),
            )
        )

    out["areChannelsResaved"] = 1
    out["startTransform"] = indices.transform_index(
        index_name(out.get("startTransform"), "animTransformIndex", allow_text=False)
    )
    out["endTransform"] = indices.transform_index(
        index_name(out.get("endTransform"), "animTransformIndex", allow_text=False)
    )
    out["outputDriverTrack"] = indices.track_index(
        index_name(
            out.get("outputDriverTrack"), "animNamedTrackIndex", allow_text=False
        )
    )
    out["multiplier"] = coerce_float(out.get("multiplier"), 1.0, unwrap=False)
    out["negativeMultiplier"] = coerce_float(
        out.get("negativeMultiplier"), 1.0, unwrap=False
    )
    out["smoothStep"] = coerce_float(out.get("smoothStep"), 1.0, unwrap=False)
    out["offset"] = coerce_float(out.get("offset"), 0.0, unwrap=False)
    out["delay"] = coerce_float(out.get("delay"), 0.0, unwrap=False)
    out["debug"] = int(bool(out.get("debug", 0)))
    out["transformOutputs"] = normalized_outputs
    out["trackOutputs"] = normalized_tracks
    link = out.get("inputLink") if isinstance(out.get("inputLink"), dict) else {}
    link["$type"] = "animPoseLink"
    link.setdefault("node", None)
    out["inputLink"] = link
    for obsolete in ("targetTransform", "targetTransformAxis", "outputAngleTrack"):
        out.pop(obsolete, None)
    return out


def canonicalize_for_export(data: Any) -> dict:
    out = normalize_data(data)
    if str(out.get("$type", "")) != RED_TYPE:
        return out
    out["$type"] = RED_TYPE
    out["areChannelsResaved"] = 1
    return out


def authored_defaults() -> dict:
    return canonicalize_for_export(
        {
            "$type": RED_TYPE,
            "id": 4294967295,
            "poseInfoLogger": None,
            "visAxes": 0,
            "visMask": None,
            "visNames": 0,
            "visPostPose": 0,
            "visPostPoseColor": {
                "$type": "Color",
                "Alpha": 0,
                "Blue": 0,
                "Green": 0,
                "Red": 0,
            },
            "visPrePose": 0,
            "visPrePoseColor": {
                "$type": "Color",
                "Alpha": 0,
                "Blue": 0,
                "Green": 0,
                "Red": 0,
            },
            "visRigPartMask": indices.cname("None"),
            "visWhenActive": 0,
            "inputLink": {"$type": "animPoseLink", "node": None},
            "areChannelsResaved": 1,
            "debug": 0,
            "startTransform": indices.transform_index("None"),
            "endTransform": indices.transform_index("None"),
            "multiplier": 1.0,
            "negativeMultiplier": 1.0,
            "smoothStep": 1.0,
            "offset": 0.0,
            "delay": 0.0,
            "transformOutputs": [],
            "trackOutputs": [],
            "outputDriverTrack": indices.track_index("None"),
        }
    )


def validate_data(
    data: Any,
    *,
    rig_names: Iterable[str] | None = None,
    rig_parents: Mapping[str, str] | None = None,
    track_names: Iterable[str] | None = None,
) -> ValidationResult:
    blocking = []
    warnings = []
    try:
        normalized = normalize_data(data)
    except (TypeError, ValueError) as exc:
        return ValidationResult((str(exc),), ())
    if normalized.get("$type") != RED_TYPE:
        return ValidationResult(("not a SimpleBounce data object",), ())

    start = index_name(
        normalized.get("startTransform"), "animTransformIndex", allow_text=False
    )
    end = index_name(
        normalized.get("endTransform"), "animTransformIndex", allow_text=False
    )
    if not start:
        blocking.append("start transform is not set")
    if not end:
        blocking.append("end transform is not set")
    if start and end and start == end:
        warnings.append(
            "start and end transforms are identical; the signed driver will remain zero"
        )

    input_link = normalized.get("inputLink")
    if not isinstance(input_link, dict) or input_link.get("$type") != "animPoseLink":
        blocking.append("inputLink is not an animPoseLink")

    smooth = coerce_float(normalized.get("smoothStep"), 1.0, unwrap=False)
    delay = coerce_float(normalized.get("delay"), 0.0, unwrap=False)
    if smooth < 0.0:
        warnings.append(
            "negative smoothStep disables the quadratic region and behaves linearly"
        )
    if delay < 0.0:
        warnings.append(
            "negative delay expands the active region and adds its magnitude before multiplication"
        )

    outputs = normalized.get("transformOutputs", ()) or ()
    tracks = normalized.get("trackOutputs", ()) or ()
    driver_track = index_name(
        normalized.get("outputDriverTrack"), "animNamedTrackIndex", allow_text=False
    )
    if not outputs and not tracks and not driver_track:
        warnings.append("node has no transform, track, or driver output")
    if len(outputs) > 4:
        warnings.append(
            "node has more than four transform outputs; REDengine static-command storage supports four"
        )
    if len(tracks) > 2:
        warnings.append(
            "node has more than two track outputs; REDengine static-command storage supports two"
        )

    rig_set = {str(name) for name in rig_names} if rig_names is not None else None
    track_set = {str(name) for name in track_names} if track_names is not None else None
    writes = {}
    for index, item in enumerate(outputs):
        target = index_name(
            item.get("targetTransform"), "animTransformIndex", allow_text=False
        )
        parent = index_name(
            item.get("parentTransform"), "animTransformIndex", allow_text=False
        )
        if not target:
            blocking.append(f"transform output {index} target is not set")
        elif rig_set is not None and target not in rig_set:
            blocking.append(
                f"transform output {index} target is absent from the bound rig: {target}"
            )
        if parent and rig_set is not None and parent not in rig_set:
            blocking.append(
                f"transform output {index} parent is absent from the bound rig: {parent}"
            )
        if (
            not parent
            and rig_parents is not None
            and target
            and not str(rig_parents.get(target, "") or "")
        ):
            blocking.append(
                f"transform output {index} targets a root transform without an explicit parent: {target}"
            )
        entries = item.get("channelEntries", ()) or ()
        if not entries:
            blocking.append(f"transform output {index} has no channel entries")
        seen = set()
        for entry_index, entry in enumerate(entries):
            channel = (
                str(entry.get("transformChannel", "") or "")
                if isinstance(entry, dict)
                else ""
            )
            if channel not in TRANSFORM_CHANNELS:
                blocking.append(
                    f"transform output {index} channel {entry_index} is invalid: {channel or '<empty>'}"
                )
                continue
            try:
                float(entry.get("multiplier", 1.0))
            except (TypeError, ValueError):
                blocking.append(
                    f"transform output {index} channel {entry_index} multiplier is not numeric"
                )
            if channel in seen:
                warnings.append(
                    f"transform output {index} writes {channel} more than once; the last entry wins"
                )
            seen.add(channel)
            key = (target, channel)
            if target and key in writes:
                warnings.append(
                    f"{target}.{channel} is written by transform outputs {writes[key]} and {index}; later writes win"
                )
            writes[key] = index

    output_track_names = []
    for index, item in enumerate(tracks):
        target = index_name(
            item.get("targetTrack"), "animNamedTrackIndex", allow_text=False
        )
        if not target:
            blocking.append(f"track output {index} target is not set")
        elif track_set is not None and target not in track_set:
            blocking.append(
                f"track output {index} target is absent from the bound rig: {target}"
            )
        try:
            float(item.get("multiplier", 1.0))
        except (TypeError, ValueError):
            blocking.append(f"track output {index} multiplier is not numeric")
        if target in output_track_names:
            warnings.append(
                f"track {target} is written more than once; the last output wins"
            )
        if target:
            output_track_names.append(target)
    if driver_track and track_set is not None and driver_track not in track_set:
        blocking.append(
            f"output driver track is absent from the bound rig: {driver_track}"
        )
    if driver_track and driver_track in output_track_names:
        warnings.append(
            f"outputDriverTrack {driver_track} also appears in trackOutputs; the raw signed driver overwrites the processed value"
        )

    if rig_set is not None:
        for label, name in (("start", start), ("end", end)):
            if name and name not in rig_set:
                blocking.append(
                    f"{label} transform is absent from the bound rig: {name}"
                )

    return ValidationResult(tuple(blocking), tuple(warnings))
