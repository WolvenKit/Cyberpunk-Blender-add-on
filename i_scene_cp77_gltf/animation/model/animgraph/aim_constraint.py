from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any

from ....assetio.values import handle_data
from . import indices
from .indices import index_name
from .source_channels import (
    ANIM_FEATURE_VECTOR_TYPE,
    ORIENTATION_VECTOR_TYPE,
    REFERENCE_TRANSFORM_VECTOR_TYPE,
    SOCKET_VECTOR_TYPE,
    TRANSFORM_VECTOR_TYPE,
    VECTOR_TYPES,
)
from .validation import ValidationResult

RED_TYPE = "animAnimNode_AimConstraint"
OBJECT_UP_TYPE = "animAnimNode_AimConstraint_ObjectUp"
OBJECT_ROTATION_UP_TYPE = "animAnimNode_AimConstraint_ObjectRotationUp"
AIM_TYPES = frozenset((RED_TYPE, OBJECT_UP_TYPE, OBJECT_ROTATION_UP_TYPE))
WEIGHT_MODES = frozenset(("Static", "FloatTrack"))


def vector3(value=(0.0, 0.0, 0.0)) -> dict:
    values = tuple(value or ())
    return {
        "$type": "Vector3",
        "X": float(values[0]) if len(values) > 0 else 0.0,
        "Y": float(values[1]) if len(values) > 1 else 0.0,
        "Z": float(values[2]) if len(values) > 2 else 0.0,
    }


def vector_components(
    value: Any, default=(0.0, 0.0, 0.0)
) -> tuple[float, float, float]:
    if isinstance(value, Mapping):
        try:
            return (
                float(value.get("X", default[0])),
                float(value.get("Y", default[1])),
                float(value.get("Z", default[2])),
            )
        except (TypeError, ValueError):
            return tuple(float(v) for v in default)
    if isinstance(value, (tuple, list)):
        try:
            return tuple(
                float(value[index]) if index < len(value) else float(default[index])
                for index in range(3)
            )
        except (TypeError, ValueError):
            return tuple(float(v) for v in default)
    return tuple(float(v) for v in default)


def legacy_target_name(data: Mapping[str, Any]) -> str:
    targets = tuple(data.get("targetTransforms", ()) or ())
    if not targets:
        return ""
    weighted = handle_data(targets[0])
    channel = handle_data(weighted.get("channel"))
    if str(channel.get("$type", "") or "") != TRANSFORM_VECTOR_TYPE:
        return ""
    return index_name(
        channel.get("transformIndex"), "animTransformIndex", allow_text=False
    )


def up_channel_data(value: Any) -> dict:
    payload = copy.deepcopy(dict(handle_data(value))) if handle_data(value) else {}
    channel_type = str(payload.get("$type", "") or "")
    if channel_type in (TRANSFORM_VECTOR_TYPE, REFERENCE_TRANSFORM_VECTOR_TYPE):
        return {
            "$type": channel_type,
            "transformIndex": indices.transform_index(
                index_name(
                    payload.get("transformIndex"),
                    "animTransformIndex",
                    allow_text=False,
                )
            ),
        }
    if channel_type == ORIENTATION_VECTOR_TYPE:
        return {
            "$type": channel_type,
            "transformIndex": indices.transform_index(
                index_name(
                    payload.get("transformIndex"),
                    "animTransformIndex",
                    allow_text=False,
                )
            ),
            "inputTransformIndex": indices.transform_index(
                index_name(
                    payload.get("inputTransformIndex"),
                    "animTransformIndex",
                    allow_text=False,
                )
            ),
            "up": vector3(vector_components(payload.get("up"), (0.0, 1.0, 0.0))),
        }
    return payload


def up_channel_type(value: Any) -> str:
    return str(handle_data(value).get("$type", "") or "")


def up_transform_names(value: Any) -> tuple[str, ...]:
    data = up_channel_data(value)
    channel_type = str(data.get("$type", "") or "")
    if channel_type in (TRANSFORM_VECTOR_TYPE, REFERENCE_TRANSFORM_VECTOR_TYPE):
        name = index_name(
            data.get("transformIndex"), "animTransformIndex", allow_text=False
        )
        return (name,) if name else ()
    if channel_type == ORIENTATION_VECTOR_TYPE:
        names = (
            index_name(
                data.get("transformIndex"), "animTransformIndex", allow_text=False
            ),
            index_name(
                data.get("inputTransformIndex"), "animTransformIndex", allow_text=False
            ),
        )
        return tuple(name for name in names if name)
    return ()


def _sanitized_axes(
    forward: Any,
    up: Any,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    forward_value = vector_components(forward, (1.0, 0.0, 0.0))
    up_value = vector_components(up, (0.0, 1.0, 0.0))
    if sum(component * component for component in forward_value) <= 1e-12:
        forward_value = (1.0, 0.0, 0.0)
    if sum(component * component for component in up_value) <= 1e-12:
        up_value = (0.0, 1.0, 0.0)
    return forward_value, up_value


def _normalize_common(out: dict) -> dict:
    out["targetTransform"] = indices.transform_index(
        index_name(out.get("targetTransform"), "animTransformIndex", allow_text=False)
    )
    out["transformIndex"] = indices.transform_index(
        index_name(out.get("transformIndex"), "animTransformIndex", allow_text=False)
    )
    forward, up = _sanitized_axes(out.get("forwardAxisLS"), out.get("upAxisLS"))
    out["forwardAxisLS"] = vector3(forward)
    out["upAxisLS"] = vector3(up)
    out["weight"] = float(out.get("weight", 1.0) or 0.0)
    out["weightFloatTrack"] = indices.track_index(
        index_name(out.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False)
    )
    mode = str(out.get("weightMode", "") or "")
    if mode not in WEIGHT_MODES:
        mode = (
            "FloatTrack"
            if index_name(
                out["weightFloatTrack"], "animNamedTrackIndex", allow_text=False
            )
            else "Static"
        )
    out["weightMode"] = mode
    link = out.get("inputLink") if isinstance(out.get("inputLink"), dict) else {}
    link["$type"] = "animPoseLink"
    link.setdefault("node", None)
    out["inputLink"] = link
    return out


def normalize_data(data: Any) -> dict:
    if not isinstance(data, dict):
        raise TypeError("AimConstraint data must be an object")
    node_type = str(data.get("$type", "") or "")
    if node_type not in AIM_TYPES:
        return dict(data)

    # Imported pose links can resolve into a deeply nested graph.  AimConstraint
    # normalization only changes owned top-level fields, so keep graph links by
    # reference and clone the small wrappers that are actually mutated.
    out = dict(data)
    if isinstance(data.get("inputLink"), dict):
        out["inputLink"] = dict(data["inputLink"])
    out = _normalize_common(out)
    if node_type == RED_TYPE:
        was_resaved = bool(out.get("areSourceChannelsResaved", False))
        current_target = index_name(
            out.get("targetTransform"), "animTransformIndex", allow_text=False
        )
        target = current_target if was_resaved else legacy_target_name(out)
        out["targetTransform"] = indices.transform_index(target)
        out["upTransform"] = (
            copy.deepcopy(out.get("upTransform"))
            if isinstance(out.get("upTransform"), Mapping)
            else None
        )
        if not was_resaved:
            out["weightMode"] = (
                "FloatTrack"
                if index_name(
                    out.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False
                )
                else "Static"
            )
        out["areSourceChannelsResaved"] = 1
    else:
        out["upTransform"] = indices.transform_index(
            index_name(out.get("upTransform"), "animTransformIndex", allow_text=False)
        )
        if node_type == OBJECT_ROTATION_UP_TYPE:
            out["upTransformVector"] = vector3(
                vector_components(out.get("upTransformVector"), (0.0, 1.0, 0.0))
            )
    return out


def canonicalize_for_export(data: Any) -> dict:
    out = normalize_data(data)
    if out.get("$type") == RED_TYPE:
        out["areSourceChannelsResaved"] = 1
    return out


def _base_defaults(node_type: str) -> dict:
    data = {
        "$type": node_type,
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
        "targetTransform": indices.transform_index("None"),
        "upTransform": indices.transform_index("None"),
        "transformIndex": indices.transform_index("None"),
        "forwardAxisLS": vector3((1.0, 0.0, 0.0)),
        "upAxisLS": vector3((0.0, 1.0, 0.0)),
        "weightMode": "Static",
        "weight": 1.0,
        "weightFloatTrack": indices.track_index("None"),
    }
    if node_type == RED_TYPE:
        data.update(
            {
                "areSourceChannelsResaved": 1,
                "targetTransforms": [],
                "upTransform": {
                    "HandleId": "",
                    "Data": {
                        "$type": TRANSFORM_VECTOR_TYPE,
                        "transformIndex": indices.transform_index("None"),
                    },
                },
            }
        )
    elif node_type == OBJECT_ROTATION_UP_TYPE:
        data["upTransformVector"] = vector3((0.0, 1.0, 0.0))
    return data


def authored_defaults(node_type: str = RED_TYPE) -> dict:
    if node_type not in AIM_TYPES:
        raise ValueError(f"unsupported AimConstraint type: {node_type}")
    return canonicalize_for_export(_base_defaults(node_type))


def _axis_cross_squared(forward, up) -> float:
    cross = (
        forward[1] * up[2] - forward[2] * up[1],
        forward[2] * up[0] - forward[0] * up[2],
        forward[0] * up[1] - forward[1] * up[0],
    )
    return sum(component * component for component in cross)


def validate_data(
    data: Any,
    *,
    rig_names: Iterable[str] | None = None,
    track_names: Iterable[str] | None = None,
) -> ValidationResult:
    blocking: list[str] = []
    warnings: list[str] = []
    try:
        normalized = normalize_data(data)
    except (TypeError, ValueError) as exc:
        return ValidationResult((str(exc),), ())
    node_type = str(normalized.get("$type", "") or "")
    if node_type not in AIM_TYPES:
        return ValidationResult(("not an AimConstraint data object",), ())

    constrained = index_name(
        normalized.get("transformIndex"), "animTransformIndex", allow_text=False
    )
    target = index_name(
        normalized.get("targetTransform"), "animTransformIndex", allow_text=False
    )
    if not constrained:
        blocking.append("constrained transform is not set")
    if not target:
        blocking.append("target transform is not set")

    if node_type == RED_TYPE:
        up_type = up_channel_type(normalized.get("upTransform"))
        up_names = up_transform_names(normalized.get("upTransform"))
        if not up_type:
            blocking.append("up source channel is not set")
        elif up_type not in VECTOR_TYPES:
            blocking.append(f"unsupported AimConstraint up source channel: {up_type}")
        elif (
            up_type
            in (
                TRANSFORM_VECTOR_TYPE,
                REFERENCE_TRANSFORM_VECTOR_TYPE,
                ORIENTATION_VECTOR_TYPE,
            )
            and not up_names
        ):
            blocking.append("up transform is not set")
        elif up_type in (SOCKET_VECTOR_TYPE, ANIM_FEATURE_VECTOR_TYPE):
            warnings.append(
                f"{up_type} evaluates to the zero point and normally leaves AimConstraint inactive"
            )
        if up_type == ORIENTATION_VECTOR_TYPE:
            up_vector = vector_components(
                up_channel_data(normalized.get("upTransform")).get("up"),
                (0.0, 1.0, 0.0),
            )
            if sum(value * value for value in up_vector) <= 1e-12:
                blocking.append("OrientationVector up direction is zero")
    else:
        up_name = index_name(
            normalized.get("upTransform"), "animTransformIndex", allow_text=False
        )
        up_names = (up_name,) if up_name else ()
        if not up_name:
            blocking.append("up transform is not set")
        if node_type == OBJECT_ROTATION_UP_TYPE:
            up_vector = vector_components(
                normalized.get("upTransformVector"), (0.0, 1.0, 0.0)
            )
            if sum(value * value for value in up_vector) <= 1e-12:
                blocking.append("upTransformVector is zero")

    forward = vector_components(normalized.get("forwardAxisLS"), (1.0, 0.0, 0.0))
    up_axis = vector_components(normalized.get("upAxisLS"), (0.0, 1.0, 0.0))
    if _axis_cross_squared(forward, up_axis) <= 1e-12:
        warnings.append(
            "forwardAxisLS and upAxisLS are parallel; runtime evaluation is a no-op"
        )

    mode = str(normalized.get("weightMode", "") or "")
    track = index_name(
        normalized.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False
    )
    if mode not in WEIGHT_MODES:
        blocking.append(f"unsupported constraint weight mode: {mode or '<empty>'}")
    if mode == "FloatTrack" and not track:
        blocking.append("FloatTrack weight mode requires weightFloatTrack")
    static_weight = float(normalized.get("weight", 1.0) or 0.0)
    if mode == "Static" and static_weight <= 0.0:
        warnings.append("nonpositive static constraint weight disables the node")
    if mode == "Static" and static_weight > 1.0:
        warnings.append("constraint weights greater than one use direct assignment")
    if constrained and constrained == target:
        warnings.append("constrained and target transforms are identical")
    if constrained and constrained in up_names:
        warnings.append("the constrained transform is also the up source")

    if rig_names is not None:
        names = {str(name) for name in rig_names}
        for label, name in (("constrained", constrained), ("target", target)):
            if name and name not in names:
                blocking.append(
                    f"{label} transform is absent from the bound rig: {name}"
                )
        for name in up_names:
            if name not in names:
                blocking.append(
                    f"up source transform is absent from the bound rig: {name}"
                )
    if track_names is not None and mode == "FloatTrack" and track:
        if track not in {str(name) for name in track_names}:
            blocking.append(f"weight track is absent from the bound rig: {track}")

    return ValidationResult(tuple(blocking), tuple(warnings))
