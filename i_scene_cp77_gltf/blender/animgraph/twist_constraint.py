from __future__ import annotations

from typing import Any

from ...animation.model.animgraph import twist_constraint
from .access import node_property_map, property_float, property_string
from .property_codec import encode_node_property


def runtime_data(node: Any) -> dict[str, Any]:
    properties = node_property_map(node)
    raw_outputs = []
    outputs_property = properties.get("outputs")
    if outputs_property is not None:
        encoded = encode_node_property(outputs_property)
        if isinstance(encoded, list):
            raw_outputs = encoded

    # The schema migrates these top-level properties into output zero.
    if not raw_outputs and any(
        key in properties
        for key in (
            "positiveScale",
            "negativeScale",
            "twistAxis",
            "twistedTransform",
            "outputAngleTrack",
        )
    ):
        raw_outputs = [
            {
                "positiveScale": property_float(properties, "positiveScale", 1.0),
                "negativeScale": property_float(properties, "negativeScale", 1.0),
                "twistAxis": property_string(properties, "twistAxis", "X"),
                "twistedTransform": {
                    "$type": "animTransformIndex",
                    "name": {
                        "$type": "CName",
                        "$storage": "string",
                        "$value": property_string(properties, "twistedTransform"),
                    },
                },
                "outputAngleTrack": {
                    "$type": "animNamedTrackIndex",
                    "name": {
                        "$type": "CName",
                        "$storage": "string",
                        "$value": property_string(properties, "outputAngleTrack"),
                    },
                },
            }
        ]

    return {
        "frontAxis": twist_constraint.normalize_axis(
            property_string(properties, "frontAxis", "X")
        ),
        "transformA": property_string(properties, "transformA"),
        "transformB": property_string(properties, "transformB"),
        "outputs": [twist_constraint.runtime_output(output) for output in raw_outputs],
    }
