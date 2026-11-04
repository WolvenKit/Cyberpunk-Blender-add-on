from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ....assetio.values import coerce_float, handle_data
from . import indices
from .indices import index_name
from .validation import ValidationResult

RED_TYPE = "animAnimNode_PointConstraint"
WEIGHTED_TRANSFORM_TYPE = "animAnimNode_PointConstraint_WeightedTransform"
TRANSFORM_VECTOR_TYPES = {
    "animAnimNodeSourceChannel_TransformVector",
    "animAnimNodeSourceChannel_ReferenceTransformVector",
}
WEIGHT_MODES = {"Static", "FloatTrack"}


def weighted_transform(name: str = "", weight: float = 1.0) -> dict:
    return {
        "$type": WEIGHTED_TRANSFORM_TYPE,
        "transform": indices.transform_index(name),
        "weight": coerce_float(weight, 1.0, unwrap=False),
    }


def preprocess_weights(entries: Sequence[Mapping[str, Any]]) -> list[float]:
    weights = [
        coerce_float(entry.get("weight"), 0.0, unwrap=False) for entry in entries
    ]
    total = sum(weights)
    if total > 0.0:
        inverse = 1.0 / total
        return [value * inverse for value in weights]
    return [0.0 for _value in weights]


def legacy_weighted_transform(wrapper: Any) -> dict:
    weighted = handle_data(wrapper)
    channel_wrapper = weighted.get("channel") if isinstance(weighted, Mapping) else None
    channel = handle_data(channel_wrapper)
    has_channel = bool(channel)
    channel_type = str(channel.get("$type", "") or "")
    name = (
        index_name(
            channel.get("transformIndex"), "animTransformIndex", allow_text=False
        )
        if channel_type in TRANSFORM_VECTOR_TYPES
        else ""
    )
    weight = weighted.get("weight", 0.0) if has_channel else 0.0
    return weighted_transform(name, weight)


def legacy_entries(data: Mapping[str, Any]) -> list[dict]:
    return [
        legacy_weighted_transform(wrapper)
        for wrapper in data.get("inputTransforms", ()) or ()
    ]


def current_entries(data: Mapping[str, Any]) -> list[dict]:
    result = []
    for raw in data.get("inputWeightedTransforms", ()) or ():
        item = raw if isinstance(raw, Mapping) else {}
        result.append(
            weighted_transform(
                index_name(
                    item.get("transform"), "animTransformIndex", allow_text=False
                ),
                item.get("weight", 1.0),
            )
        )
    return result


def normalize_data(data: Any) -> dict:
    if not isinstance(data, dict):
        raise TypeError("PointConstraint data must be an object")
    if str(data.get("$type", "")) != RED_TYPE:
        return dict(data)

    # Pose links may point into a deeply nested resolved graph.  This node only
    # mutates its own top-level fields, so avoid recursively copying the graph.
    out = dict(data)
    if isinstance(data.get("inputLink"), dict):
        out["inputLink"] = dict(data["inputLink"])
    was_resaved = bool(out.get("areSourceChannelsResaved", False))
    entries = current_entries(out) if was_resaved else legacy_entries(out)
    out["inputWeightedTransforms"] = entries
    out["preprocessedWeights"] = preprocess_weights(entries)
    out["areSourceChannelsResaved"] = 1
    out["transformIndex"] = indices.transform_index(
        index_name(out.get("transformIndex"), "animTransformIndex", allow_text=False)
    )
    out["weight"] = coerce_float(out.get("weight"), 1.0, unwrap=False)
    out["weightFloatTrack"] = indices.track_index(
        index_name(out.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False)
    )
    mode = str(out.get("weightMode", "") or "")
    if not was_resaved or mode not in WEIGHT_MODES:
        mode = (
            "FloatTrack"
            if index_name(
                out.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False
            )
            else "Static"
        )
    out["weightMode"] = mode
    link = out.get("inputLink") if isinstance(out.get("inputLink"), dict) else {}
    link["$type"] = "animPoseLink"
    link.setdefault("node", None)
    out["inputLink"] = link
    return out


def canonicalize_for_export(data: Any) -> dict:
    out = normalize_data(data)
    if out.get("$type") != RED_TYPE:
        return out
    out["$type"] = RED_TYPE
    out["areSourceChannelsResaved"] = 1
    out["preprocessedWeights"] = preprocess_weights(
        out.get("inputWeightedTransforms", ()) or ()
    )
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
            "areSourceChannelsResaved": 1,
            "inputTransforms": [],
            "preprocessedWeights": [],
            "inputWeightedTransforms": [],
            "transformIndex": indices.transform_index("None"),
            "weightMode": "Static",
            "weight": 1.0,
            "weightFloatTrack": indices.track_index("None"),
        }
    )


def validate_data(
    data: Any,
    *,
    rig_names: Iterable[str] | None = None,
    track_names: Iterable[str] | None = None,
) -> ValidationResult:
    blocking = []
    warnings = []
    raw_preprocessed = (
        tuple(data.get("preprocessedWeights", ()) or ())
        if isinstance(data, Mapping)
        else ()
    )
    raw_resaved = (
        bool(data.get("areSourceChannelsResaved", False))
        if isinstance(data, Mapping)
        else False
    )
    try:
        normalized = normalize_data(data)
    except (TypeError, ValueError) as exc:
        return ValidationResult((str(exc),), ())
    if normalized.get("$type") != RED_TYPE:
        return ValidationResult(("not a PointConstraint data object",), ())

    target = index_name(
        normalized.get("transformIndex"), "animTransformIndex", allow_text=False
    )
    if not target:
        blocking.append("constrained transform is not set")

    entries = normalized.get("inputWeightedTransforms", ()) or ()
    if not entries:
        blocking.append("no weighted input transforms are configured")
    input_names = []
    weights = []
    for index, entry in enumerate(entries):
        name = (
            index_name(entry.get("transform"), "animTransformIndex", allow_text=False)
            if isinstance(entry, Mapping)
            else ""
        )
        if not name:
            blocking.append(f"input transform {index + 1} is not set")
        input_names.append(name)
        weight = coerce_float(
            entry.get("weight") if isinstance(entry, Mapping) else None,
            0.0,
            unwrap=False,
        )
        weights.append(weight)
        if weight < 0.0:
            warnings.append(f"input transform {index + 1} has a negative weight")

    total = sum(weights)
    if entries and total <= 0.0:
        warnings.append(
            "input weights sum to zero or less; the weighted target position becomes the origin"
        )
    if len(set(name for name in input_names if name)) < len(
        [name for name in input_names if name]
    ):
        warnings.append(
            "duplicate input transforms are evaluated as separate weighted contributions"
        )
    if target and target in input_names:
        warnings.append("the constrained transform is also used as an input transform")

    mode = str(normalized.get("weightMode", "") or "")
    if mode not in WEIGHT_MODES:
        blocking.append(f"unsupported constraint weight mode: {mode or '<empty>'}")
    track = index_name(
        normalized.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False
    )
    if mode == "FloatTrack" and not track:
        blocking.append("FloatTrack weight mode requires weightFloatTrack")
    try:
        static_weight = float(normalized.get("weight", 1.0))
    except (TypeError, ValueError):
        blocking.append("constraint weight is not numeric")
        static_weight = 1.0
    if mode == "Static" and static_weight <= 0.0:
        warnings.append("nonpositive static constraint weight disables the node")
    if mode == "Static" and static_weight > 1.0:
        warnings.append(
            "constraint weights greater than one use direct assignment rather than extrapolation"
        )

    if rig_names is not None:
        names = {str(name) for name in rig_names}
        if target and target not in names:
            blocking.append(
                f"constrained transform is absent from the bound rig: {target}"
            )
        for name in input_names:
            if name and name not in names:
                blocking.append(f"input transform is absent from the bound rig: {name}")
    if track_names is not None and mode == "FloatTrack" and track:
        tracks = {str(name) for name in track_names}
        if track not in tracks:
            blocking.append(f"weight track is absent from the bound rig: {track}")

    expected = preprocess_weights(entries)
    if raw_resaved and (
        len(raw_preprocessed) != len(expected)
        or any(
            abs(coerce_float(a, 0.0, unwrap=False) - b) > 1e-6
            for a, b in zip(raw_preprocessed, expected)
        )
    ):
        warnings.append(
            "preprocessedWeights do not match the current input weights and will be regenerated"
        )

    return ValidationResult(tuple(blocking), tuple(warnings))
