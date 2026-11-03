from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any

from ....assetio.values import handle_id
from . import indices
from .indices import index_name
from .validation import ValidationResult

RED_TYPE = "animAnimNode_DirectConnConstraint"
SOURCE_CHANNEL_TYPE = "animAnimNodeSourceChannel_TransformQsTransform"
CHANNEL_GROUPS = (
    ("position", ("posX", "posY", "posZ")),
    ("rotation", ("rotX", "rotY", "rotZ")),
    ("scale", ("scaleX", "scaleY", "scaleZ")),
)
CHANNEL_FIELDS = tuple(field for _name, fields in CHANNEL_GROUPS for field in fields)


def transform_index_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    resolved = index_name(value, "animTransformIndex", allow_text=False)
    if resolved:
        return resolved
    if value.get("$type") == SOURCE_CHANNEL_TYPE:
        return transform_index_name(value.get("transformIndex"))
    data = value.get("Data")
    if isinstance(data, dict):
        return transform_index_name(data)
    return ""


def legacy_source_name(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    return transform_index_name(data.get("sourceTransform"))


def current_source_name(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    return transform_index_name(data.get("sourceTransformIndex"))


def effective_source_name(data: Any) -> str:
    """The source a resaved constraint reads"""
    if not isinstance(data, dict):
        return ""
    return current_source_name(data) or legacy_source_name(data)


def canonicalize_for_export(data: dict, *, source_handle_id: str) -> dict:
    if not isinstance(data, dict):
        raise TypeError("DirectConnConstraint data must be an object")
    if str(data.get("$type", "")) != RED_TYPE:
        return dict(data)

    # Do not recursively copy resolved pose-link graphs.  Only the source
    # wrapper and link wrappers below are mutated by canonicalization.
    out = dict(data)
    source_index = indices.transform_index(effective_source_name(out))
    # A resaved constraint ignores the legacy channel: an imported one, or none, stays as it was, and only a new
    # channel gets the source.
    wrapper = out.get("sourceTransform")
    if wrapper is not None:
        wrapper = dict(wrapper) if isinstance(wrapper, dict) else {}
        handle_value = handle_id(wrapper) or str(source_handle_id or "")
        payload = (
            dict(wrapper.get("Data")) if isinstance(wrapper.get("Data"), dict) else {}
        )
        payload["$type"] = SOURCE_CHANNEL_TYPE
        if not transform_index_name(payload.get("transformIndex")):
            payload["transformIndex"] = copy.deepcopy(source_index)
        wrapper = {"HandleId": handle_value, "Data": payload}

    out["sourceTransform"] = wrapper
    out["sourceTransformIndex"] = copy.deepcopy(source_index)
    out["isSourceTransformResaved"] = 1
    out["transformIndex"] = indices.transform_index(
        transform_index_name(out.get("transformIndex"))
    )
    out["weight"] = float(out.get("weight", 1.0) or 0.0)
    for field in CHANNEL_FIELDS:
        out[field] = int(bool(out.get(field, 0)))
    for field, link_type in (
        ("inputLink", "animPoseLink"),
        ("weightNode", "animFloatLink"),
    ):
        wrapper_value = out.get(field)
        if not isinstance(wrapper_value, dict):
            wrapper_value = {}
        else:
            wrapper_value = dict(wrapper_value)
        wrapper_value["$type"] = link_type
        wrapper_value.setdefault("node", None)
        out[field] = wrapper_value
    return out


def authored_defaults(*, source_handle_id: str) -> dict:
    data = {
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
        "sourceTransform": {
            "HandleId": str(source_handle_id or ""),
            "Data": {
                "$type": SOURCE_CHANNEL_TYPE,
                "transformIndex": indices.transform_index("None"),
            },
        },
        "isSourceTransformResaved": 1,
        "sourceTransformIndex": indices.transform_index("None"),
        "transformIndex": indices.transform_index("None"),
        "weight": 1.0,
        "weightNode": {"$type": "animFloatLink", "node": None},
    }
    for field in CHANNEL_FIELDS:
        data[field] = 0
    return data


def validate_data(
    data: Any,
    *,
    rig_names: Iterable[str] | None = None,
    rig_parents: Mapping[str, str] | None = None,
) -> ValidationResult:
    blocking = []
    warnings = []
    if not isinstance(data, dict) or data.get("$type") != RED_TYPE:
        return ValidationResult(("not a DirectConnConstraint data object",), ())

    source = effective_source_name(data)
    target = transform_index_name(data.get("transformIndex"))
    if not source:
        blocking.append("source transform is not set")
    if not target:
        blocking.append("target transform is not set")

    source_wrapper = data.get("sourceTransform")
    if source_wrapper is not None:
        source_payload = (
            source_wrapper.get("Data") if isinstance(source_wrapper, dict) else None
        )
        if (
            not isinstance(source_payload, dict)
            or source_payload.get("$type") != SOURCE_CHANNEL_TYPE
        ):
            blocking.append(
                "sourceTransform is not a TransformQsTransform source channel"
            )
        if isinstance(source_wrapper, dict) and not source_wrapper.get("HandleId"):
            blocking.append("sourceTransform owned payload lacks a HandleId")

    input_link = data.get("inputLink")
    if not isinstance(input_link, dict) or input_link.get("$type") != "animPoseLink":
        blocking.append("inputLink is not an animPoseLink")
    weight_link = data.get("weightNode")
    if not isinstance(weight_link, dict) or weight_link.get("$type") != "animFloatLink":
        blocking.append("weightNode is not an animFloatLink")

    enabled = tuple(field for field in CHANNEL_FIELDS if bool(data.get(field)))
    if not enabled:
        warnings.append("no transform channels are enabled")
    if source and target and source == target:
        warnings.append("source and target transforms are identical")

    weight = data.get("weight", 1.0)
    try:
        weight_value = float(weight)
    except (TypeError, ValueError):
        blocking.append("weight is not numeric")
        weight_value = 1.0
    dynamic_weight = bool(isinstance(weight_link, dict) and weight_link.get("node"))
    if dynamic_weight:
        warnings.append(
            "dynamic weight range is not statically guaranteed to remain between 0 and 1"
        )

    for group_name, fields in CHANNEL_GROUPS:
        selected = [field for field in fields if bool(data.get(field))]
        if selected and len(selected) != 3:
            if group_name == "rotation":
                warnings.append(
                    "partial rotation uses Euler component replacement rather than quaternion interpolation"
                )
            elif weight_value != 1.0 or dynamic_weight:
                warnings.append(
                    f"partial {group_name} channels multiply source components by weight instead of interpolating from the target"
                )

    if rig_names is not None:
        names = {str(name) for name in rig_names}
        if source and source not in names:
            blocking.append(f"source transform is absent from the bound rig: {source}")
        if target and target not in names:
            blocking.append(f"target transform is absent from the bound rig: {target}")

    if rig_parents is not None and source and target:
        source_parent = str(rig_parents.get(source, "") or "")
        target_parent = str(rig_parents.get(target, "") or "")
        if source_parent != target_parent:
            warnings.append(
                "source and target have different parents; DirectConn performs no hierarchy-space compensation"
            )

    return ValidationResult(tuple(blocking), tuple(warnings))
