from __future__ import annotations

import copy
import json
from typing import Any

from ...animation.model.animgraph import indices, point_constraint
from ...animation.model.animgraph.indices import index_name
from ...assetio.values import json_array
from ...core.log import get_logger, log_once
from .access import (
    clear_collection,
    get_attr,
    get_idprop,
    node_property_map,
    property_float,
    property_string,
)

_LOG = get_logger(__name__)

LEGACY_INPUTS_KEY = "red_point_constraint_input_transforms_json"


def capture_import_state(node: Any, data: dict) -> None:
    legacy = (
        copy.deepcopy(data.get("inputTransforms", [])) if isinstance(data, dict) else []
    )
    normalized = point_constraint.normalize_data(data)
    data.clear()
    data.update(normalized)
    try:
        node[LEGACY_INPUTS_KEY] = json.dumps(
            legacy, ensure_ascii=False, separators=(",", ":")
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
    inputs = getattr(node, "red_point_constraint_inputs", None)
    if inputs is None:
        return
    clear_collection(inputs)
    for raw in normalized.get("inputWeightedTransforms", ()) or ():
        item = inputs.add()
        item.transform = index_name(
            raw.get("transform"), "animTransformIndex", allow_text=False
        )
        item.weight = float(raw.get("weight", 1.0))
        item.expanded = True


def seed_authored_state(node: Any) -> None:
    inputs = getattr(node, "red_point_constraint_inputs", None)
    if inputs is not None:
        clear_collection(inputs)
    try:
        node[LEGACY_INPUTS_KEY] = "[]"
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


def weighted_inputs_data(node: Any) -> list[dict]:
    return [
        point_constraint.weighted_transform(
            str(getattr(item, "transform", "") or ""),
            float(getattr(item, "weight", 1.0)),
        )
        for item in getattr(node, "red_point_constraint_inputs", ()) or ()
    ]


def canonicalize_node_data(node: Any, data: dict) -> dict:
    if str(get_attr(node, "red_type", "") or "") != point_constraint.RED_TYPE:
        return data
    out = dict(data)
    entries = weighted_inputs_data(node)
    out["inputWeightedTransforms"] = entries
    out["preprocessedWeights"] = point_constraint.preprocess_weights(entries)
    # A resaved constraint reads its weighted entries; the legacy list goes back as it was imported.
    out["inputTransforms"] = json_array(get_idprop(node, LEGACY_INPUTS_KEY, "[]"))
    out["areSourceChannelsResaved"] = 1
    return point_constraint.canonicalize_for_export(out)


def validation_data(node: Any) -> dict:
    properties = node_property_map(node)
    data = point_constraint.authored_defaults()
    entries = weighted_inputs_data(node)
    data["inputWeightedTransforms"] = entries
    data["preprocessedWeights"] = point_constraint.preprocess_weights(entries)
    data["transformIndex"] = indices.transform_index(
        property_string(properties, "transformIndex")
    )
    mode = property_string(properties, "weightMode") or "Static"
    data["weightMode"] = mode
    data["weight"] = property_float(properties, "weight", 1.0)
    data["weightFloatTrack"] = indices.track_index(
        property_string(properties, "weightFloatTrack")
    )
    return point_constraint.canonicalize_for_export(data)


def runtime_data(node: Any) -> dict:
    properties = node_property_map(node)
    entries = weighted_inputs_data(node)
    return {
        "inputWeightedTransforms": [
            {
                "transform": index_name(
                    item.get("transform"), "animTransformIndex", allow_text=False
                ),
                "weight": float(item.get("weight", 1.0)),
            }
            for item in entries
        ],
        "preprocessedWeights": point_constraint.preprocess_weights(entries),
        "transformIndex": property_string(properties, "transformIndex"),
        "weightMode": property_string(properties, "weightMode") or "Static",
        "weight": property_float(properties, "weight", 1.0),
        "weightFloatTrack": property_string(properties, "weightFloatTrack"),
    }
