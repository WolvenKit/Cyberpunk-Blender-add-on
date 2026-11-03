from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....assetio.values import coerce_float
from .indices import index_name

RED_TYPE = "animAnimNode_TwistConstraint"
AXES = ("X", "Y", "Z", "NegativeX", "NegativeY", "NegativeZ")


def normalize_axis(value: Any, default: str = "X") -> str:
    text = str(value or default)
    return text if text in AXES else default


def runtime_output(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    positive = coerce_float(raw.get("positiveScale", 1.0), 1.0, unwrap=False)
    negative = coerce_float(raw.get("negativeScale", 1.0), 1.0, unwrap=False)
    return {
        "positiveScale": positive,
        "negativeScale": negative,
        "twistAxis": normalize_axis(raw.get("twistAxis"), "X"),
        "twistedTransform": index_name(
            raw.get("twistedTransform"), "animTransformIndex", allow_text=True
        ),
        "outputAngleTrack": index_name(
            raw.get("outputAngleTrack"), "animNamedTrackIndex", allow_text=True
        ),
    }
