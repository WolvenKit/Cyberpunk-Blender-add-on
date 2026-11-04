from __future__ import annotations

from copy import deepcopy

SKIN_FIELDS = ("rigPath", "boneNames", "boneParentIndexes", "trackNames")
ANIMATION_FIELDS = (
    "schema",
    "animationType",
    "rootMotionType",
    "frameClamping",
    "frameClampingStartFrame",
    "frameClampingEndFrame",
    "numExtraJoints",
    "numExtraTracks",
    "constTrackKeys",
    "trackKeys",
    "fallbackFrameIndices",
    "optimizationHints",
    "animEvents",
)
EVENT_FIELDS = (
    "type",
    "eventName",
    "startFrame",
    "durationInFrames",
    "switches",
    "params",
    "paramCurves",
    "dynamicParams",
    "metadataContext",
    "onlyPlayOn",
    "dontPlayOn",
    "playerGenderAlt",
    "emitterName",
    "effectName",
    "sequenceShift",
    "breakAllLoopsOnStop",
    "eventValue",
    "actionName",
    "boneName",
    "facialAnimName",
    "leg",
    "footPhase",
    "voContext",
    "isQuest",
    "side",
    "customEvent",
    "workspotActions",
)
WORKSPOT_FIELDS = (
    "actionType",
    "item",
    "itemSlot",
    "itemId",
    "attachMethod",
    "offsetPosX",
    "offsetPosY",
    "offsetPosZ",
    "offsetRotI",
    "offsetRotJ",
    "offsetRotK",
    "offsetRotR",
    "weaponType",
    "keepEquippedAfterExit",
    "fallbackItem",
    "fallbackSlot",
)


def _fields(value, names):
    return {name: deepcopy(value[name]) for name in names if name in value}


def skin_extras_for_export(extras):
    """Retain only the skin identity fields consumed by WolvenKit and the plugin"""
    return _fields(extras or {}, SKIN_FIELDS)


def animation_extras_for_export(extras):
    """Serialize WolvenKit schema v5 metadata without Blender authoring properties"""
    result = _fields(
        extras,
        (
            name
            for name in ANIMATION_FIELDS
            if name not in {"trackKeys", "constTrackKeys", "animEvents"}
        ),
    )
    result["schema"] = _fields(result["schema"], ("type", "version"))
    result["optimizationHints"] = _fields(
        result["optimizationHints"],
        ("preferSIMD", "maxRotationCompression", "simdQuantizationBits"),
    )
    for name in ("trackKeys", "constTrackKeys"):
        result[name] = [
            {
                "trackIndex": entry["trackIndex"],
                "time": entry["time"],
                "value": entry["value"],
            }
            for entry in extras[name]
        ]
    result["animEvents"] = None
    if extras.get("animEvents") is not None:
        events = []
        for source in extras["animEvents"]:
            event = _fields(source, EVENT_FIELDS)
            if event.get("paramCurves") is not None:
                event["paramCurves"] = [
                    _fields(
                        curve,
                        (
                            "name",
                            "value",
                            "enterCurveType",
                            "enterCurveTime",
                            "exitCurveType",
                            "exitCurveTime",
                        ),
                    )
                    for curve in event["paramCurves"]
                ]
            if event.get("workspotActions") is not None:
                event["workspotActions"] = [
                    _fields(action, WORKSPOT_FIELDS)
                    for action in event["workspotActions"]
                ]
            events.append(event)
        result["animEvents"] = events
    return result
