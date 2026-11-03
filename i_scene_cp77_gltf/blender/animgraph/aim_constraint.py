from __future__ import annotations

import copy
import json
from typing import Any

from ...animation.model.animgraph import aim_constraint, indices
from ...animation.model.animgraph.indices import index_name
from ...animation.model.animgraph.source_channels import STATIC_VECTOR_TYPE
from ...assetio.values import handle_id
from ...core.log import get_logger, log_once
from .access import (
    get_attr,
    get_idprop,
    node_property_map,
    node_property_string,
    property_float,
    property_string,
    property_vector,
)
from .owned_handles import allocate_owned_handle_ids, copied_wrapper_data

_LOG = get_logger(__name__)

LEGACY_TARGETS_KEY = "red_aim_constraint_target_transforms_json"
UP_SOURCE_KEY = "red_aim_constraint_up_transform_json"
UP_TYPE_KEY = "red_aim_constraint_up_transform_type"


def _load_json_idprop(node: Any, key: str, default):
    try:
        value = json.loads(str(get_idprop(node, key, "") or ""))
    except (TypeError, ValueError):
        return copy.deepcopy(default)
    return value


def capture_import_state(node: Any, data: dict) -> None:
    node_type = str((data or {}).get("$type", "") or "")
    legacy_targets = (
        copy.deepcopy(data.get("targetTransforms", []))
        if isinstance(data, dict)
        else []
    )
    up_wrapper = (
        copy.deepcopy(data.get("upTransform")) if isinstance(data, dict) else None
    )
    normalized = aim_constraint.normalize_data(data)
    data.clear()
    data.update(normalized)
    if node_type != aim_constraint.RED_TYPE:
        return
    try:
        node[LEGACY_TARGETS_KEY] = json.dumps(
            legacy_targets,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        node[UP_SOURCE_KEY] = json.dumps(
            up_wrapper,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        node[UP_TYPE_KEY] = aim_constraint.up_channel_type(up_wrapper)
        payload = aim_constraint.up_channel_data(up_wrapper)
        names = aim_constraint.up_transform_names(up_wrapper)
        node.red_aim_up_transform = names[0] if names else ""
        node.red_aim_up_anchor_transform = (
            index_name(
                payload.get("inputTransformIndex"),
                "animTransformIndex",
                allow_text=False,
            )
            if aim_constraint.up_channel_type(up_wrapper)
            == aim_constraint.ORIENTATION_VECTOR_TYPE
            else ""
        )
        vector_payload = (
            payload.get("data")
            if aim_constraint.up_channel_type(up_wrapper) == STATIC_VECTOR_TYPE
            else payload.get("up")
        )
        node.red_aim_up_vector = aim_constraint.vector_components(
            vector_payload, (0.0, 1.0, 0.0)
        )
        node.red_aim_up_channel_type = (
            aim_constraint.up_channel_type(up_wrapper)
            or aim_constraint.TRANSFORM_VECTOR_TYPE
        )
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("capture_import_state", type(error).__name__),
            "capture import state: fell back after %s",
            error,
            exc_info=True,
        )


def seed_authored_state(node: Any) -> None:
    if str(get_attr(node, "red_type", "") or "") != aim_constraint.RED_TYPE:
        return
    up_wrapper = {
        "HandleId": "",
        "Data": {
            "$type": aim_constraint.TRANSFORM_VECTOR_TYPE,
            "transformIndex": indices.transform_index("None"),
        },
    }
    try:
        node[LEGACY_TARGETS_KEY] = "[]"
        node[UP_SOURCE_KEY] = json.dumps(
            up_wrapper,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        node[UP_TYPE_KEY] = aim_constraint.TRANSFORM_VECTOR_TYPE
        node.red_aim_up_transform = ""
        node.red_aim_up_anchor_transform = ""
        node.red_aim_up_vector = (0.0, 1.0, 0.0)
        node.red_aim_up_channel_type = aim_constraint.TRANSFORM_VECTOR_TYPE
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("seed_authored_state", type(error).__name__),
            "seed authored state: fell back after %s",
            error,
            exc_info=True,
        )


def _up_wrapper(node: Any) -> dict | None:
    original = _load_json_idprop(node, UP_SOURCE_KEY, None)
    wrapper = copy.deepcopy(original) if isinstance(original, dict) else {}
    payload = copied_wrapper_data(wrapper)
    channel_type = str(
        getattr(node, "red_aim_up_channel_type", "")
        or get_idprop(node, UP_TYPE_KEY, "")
        or payload.get("$type", "")
        or aim_constraint.TRANSFORM_VECTOR_TYPE
    )
    name = str(getattr(node, "red_aim_up_transform", "") or "")
    if channel_type in (
        aim_constraint.TRANSFORM_VECTOR_TYPE,
        aim_constraint.REFERENCE_TRANSFORM_VECTOR_TYPE,
    ):
        payload = {
            "$type": channel_type,
            "transformIndex": indices.transform_index(name),
        }
    elif channel_type == aim_constraint.ORIENTATION_VECTOR_TYPE:
        payload = {
            "$type": channel_type,
            "transformIndex": indices.transform_index(name),
            "inputTransformIndex": indices.transform_index(
                str(getattr(node, "red_aim_up_anchor_transform", "") or "")
            ),
            "up": aim_constraint.vector3(
                tuple(getattr(node, "red_aim_up_vector", (0.0, 1.0, 0.0)))
            ),
        }
    elif channel_type == STATIC_VECTOR_TYPE:
        value = tuple(getattr(node, "red_aim_up_vector", (0.0, 1.0, 0.0)))
        existing = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        payload = {
            "$type": channel_type,
            "data": {
                "$type": str(existing.get("$type", "Vector4") or "Vector4"),
                "X": float(value[0]),
                "Y": float(value[1]),
                "Z": float(value[2]),
                "W": float(existing.get("W", 1.0) or 0.0),
            },
        }
    else:
        payload = {"$type": channel_type}
    handle = handle_id(wrapper)
    if not handle:
        handle = allocate_owned_handle_ids(node, 1)[0]
    return {"HandleId": handle, "Data": payload}


def canonicalize_node_data(node: Any, data: dict) -> dict:
    node_type = str(get_attr(node, "red_type", "") or "")
    if node_type not in aim_constraint.AIM_TYPES:
        return data
    if node_type != aim_constraint.RED_TYPE:
        return aim_constraint.canonicalize_for_export(dict(data))
    out = dict(data)
    target = node_property_string(node, "targetTransform")
    out["targetTransform"] = indices.transform_index(target)
    # A resaved constraint aims at targetTransform; the legacy array goes back as it was imported.
    legacy = _load_json_idprop(node, LEGACY_TARGETS_KEY, [])
    out["targetTransforms"] = legacy if isinstance(legacy, list) else []
    out["upTransform"] = _up_wrapper(node)
    out["areSourceChannelsResaved"] = 1
    return aim_constraint.canonicalize_for_export(out)


def validation_data(node: Any) -> dict:
    properties = node_property_map(node)
    node_type = str(get_attr(node, "red_type", "") or "")
    if node_type not in aim_constraint.AIM_TYPES:
        node_type = aim_constraint.RED_TYPE
    data = aim_constraint.authored_defaults(node_type)
    data["targetTransform"] = indices.transform_index(
        property_string(properties, "targetTransform")
    )
    data["transformIndex"] = indices.transform_index(
        property_string(properties, "transformIndex")
    )
    data["forwardAxisLS"] = aim_constraint.vector3(
        property_vector(properties, "forwardAxisLS", (1.0, 0.0, 0.0))
    )
    data["upAxisLS"] = aim_constraint.vector3(
        property_vector(properties, "upAxisLS", (0.0, 1.0, 0.0))
    )
    data["weightMode"] = property_string(properties, "weightMode") or "Static"
    data["weight"] = property_float(properties, "weight", 1.0)
    data["weightFloatTrack"] = indices.track_index(
        property_string(properties, "weightFloatTrack")
    )
    if node_type == aim_constraint.RED_TYPE:
        data["upTransform"] = _up_wrapper(node)
    else:
        data["upTransform"] = indices.transform_index(
            property_string(properties, "upTransform")
        )
        if node_type == aim_constraint.OBJECT_ROTATION_UP_TYPE:
            data["upTransformVector"] = aim_constraint.vector3(
                property_vector(properties, "upTransformVector", (0.0, 1.0, 0.0))
            )
    return aim_constraint.canonicalize_for_export(data)


def runtime_data(node: Any) -> dict:
    validation = validation_data(node)
    node_type = str(
        validation.get("$type", aim_constraint.RED_TYPE) or aim_constraint.RED_TYPE
    )
    result = {
        "$type": node_type,
        "targetTransform": index_name(
            validation.get("targetTransform"), "animTransformIndex", allow_text=False
        ),
        "transformIndex": index_name(
            validation.get("transformIndex"), "animTransformIndex", allow_text=False
        ),
        "forwardAxisLS": aim_constraint.vector_components(
            validation.get("forwardAxisLS"),
            (1.0, 0.0, 0.0),
        ),
        "upAxisLS": aim_constraint.vector_components(
            validation.get("upAxisLS"),
            (0.0, 1.0, 0.0),
        ),
        "weightMode": str(validation.get("weightMode", "Static") or "Static"),
        "weight": float(validation.get("weight", 1.0)),
        "weightFloatTrack": index_name(
            validation.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=False
        ),
    }
    if node_type == aim_constraint.RED_TYPE:
        up = aim_constraint.up_channel_data(validation.get("upTransform"))
        runtime_up = {"$type": str(up.get("$type", "") or "")}
        if runtime_up["$type"] in (
            aim_constraint.TRANSFORM_VECTOR_TYPE,
            aim_constraint.REFERENCE_TRANSFORM_VECTOR_TYPE,
        ):
            runtime_up["transformIndex"] = index_name(
                up.get("transformIndex"), "animTransformIndex", allow_text=False
            )
        elif runtime_up["$type"] == aim_constraint.ORIENTATION_VECTOR_TYPE:
            runtime_up.update(
                {
                    "transformIndex": index_name(
                        up.get("transformIndex"), "animTransformIndex", allow_text=False
                    ),
                    "inputTransformIndex": index_name(
                        up.get("inputTransformIndex"),
                        "animTransformIndex",
                        allow_text=False,
                    ),
                    "up": aim_constraint.vector_components(
                        up.get("up"),
                        (0.0, 1.0, 0.0),
                    ),
                }
            )
        elif runtime_up["$type"] == STATIC_VECTOR_TYPE:
            runtime_up["data"] = aim_constraint.vector_components(
                up.get("data"),
                (0.0, 0.0, 0.0),
            )
        result["upTransform"] = runtime_up
    else:
        result["upTransform"] = index_name(
            validation.get("upTransform"), "animTransformIndex", allow_text=False
        )
        if node_type == aim_constraint.OBJECT_ROTATION_UP_TYPE:
            result["upTransformVector"] = aim_constraint.vector_components(
                validation.get("upTransformVector"),
                (0.0, 1.0, 0.0),
            )
    return result
