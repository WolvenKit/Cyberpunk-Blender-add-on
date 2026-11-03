from __future__ import annotations

from collections.abc import Mapping

from ....assetio.values import cname_or_empty, resource_path_text
from .topology import (
    GraphTopologyError,
    PreviewBoundary,
    resolve,
    static_condition_result,
)


def slot_data(node_type, node):
    return {
        "slotName": cname_or_empty(node.get("name")),
        "slotType": node_type,
        "dynamicInputSupported": False,
    }


def graph_slot_conditions_data(
    node_type, node, index, *, visual_tags, available_animations, rig_tags, parent_tags
):
    """A GraphSlotConditions slot with each condition's result and the first one that matches"""
    selected_index = -1
    selected_condition_type = ""
    selected_condition_value = ""
    selected_graph = ""
    condition_results = []
    try:
        for condition_index, entry in enumerate(node.get("conditions") or ()):
            if not isinstance(entry, Mapping):
                continue
            condition_ref = entry.get("condition")
            graph_path = resource_path_text(entry.get("graph"))
            if condition_ref is None:
                condition_results.append(
                    {
                        "index": condition_index,
                        "conditionType": "<null>",
                        "conditionValue": "",
                        "matched": False,
                        "graph": graph_path,
                    }
                )
                continue
            condition = resolve(condition_ref, index)
            condition_type = (
                str((condition or {}).get("$type", "") or "")
                if isinstance(condition, Mapping)
                else ""
            )
            value = ""
            if isinstance(condition, Mapping):
                value = cname_or_empty(
                    condition.get(
                        "tag",
                        condition.get(
                            "visualTag",
                            condition.get("animationName", condition.get("animTag")),
                        ),
                    )
                )
            matched = static_condition_result(
                condition_ref,
                index,
                visual_tags=visual_tags,
                available_animations=available_animations,
                rig_tags=rig_tags,
                parent_tags=parent_tags,
            )
            condition_results.append(
                {
                    "index": condition_index,
                    "conditionType": condition_type or "<unknown>",
                    "conditionValue": value,
                    "matched": bool(matched),
                    "graph": graph_path,
                }
            )
            if matched:
                selected_index = condition_index
                selected_condition_type = condition_type
                selected_condition_value = value
                selected_graph = graph_path
                break
    except GraphTopologyError as error:
        raise PreviewBoundary(str(error)) from error
    return {
        **slot_data(node_type, node),
        "conditionResults": tuple(condition_results),
        "selectedConditionIndex": selected_index,
        "selectedConditionType": selected_condition_type,
        "selectedConditionValue": selected_condition_value,
        "selectedGraph": selected_graph,
        "injectedGraphEvaluated": False,
    }
