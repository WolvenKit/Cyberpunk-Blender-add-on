from __future__ import annotations

import copy
import math

from ....assetio.values import json_object, plain_value
from ....core.log import get_logger

_LOG = get_logger(__name__)

FPS = 30.0
ANIMATION_EXTRAS_SNAPSHOT_KEY = "cp77_animation_extras_json"
SKIN_EXTRAS_SNAPSHOT_KEY = "cp77_skin_extras_json"
SOURCE_REST_SNAPSHOT_KEY = "cp77_animation_source_rest_json"
SOURCE_CHANNELS_SNAPSHOT_KEY = "cp77_animation_source_channels_json"
SOURCE_NAME_KEY = "cp77_animation_source_name"
IMPORTED_NAME_KEY = "cp77_animation_imported_name"
TRACKS_IMPORTED_KEY = "cp77_animation_tracks_imported"
TRACK_CURVES_SNAPSHOT_KEY = "cp77_animation_track_curves_json"

ANIMATION_SCHEMA = {"type": "wkit.cp2077.gltf.anims", "version": 5}
ANIMATION_TYPES = frozenset(
    {
        "Normal",
        "AdditiveFromRefPose",
        "AdditiveFromFirstFrame",
        "Additive",
        "AdditiveWithoutFirstFrame",
    }
)
ROOT_MOTION_TYPES = frozenset(
    {
        "Unknown",
        "None",
        "TransformLinearSparseFrames",
        "TransformSplineSparseFrames",
        "TransformLinearEveryFrame",
        "TranslationPlaneWithYawAllFrames",
        "TranslationWithYawAllFrames",
    }
)
OPTIMIZATION_HINT_DEFAULTS = {
    "preferSIMD": False,
    "maxRotationCompression": 1,
    "simdQuantizationBits": 0,
}
ACTION_DEFAULTS = {
    "schema": ANIMATION_SCHEMA,
    "animationType": "Normal",
    "rootMotionType": "Unknown",
    "frameClamping": False,
    "frameClampingStartFrame": -1,
    "frameClampingEndFrame": -1,
    "numExtraJoints": 0,
    "numExtraTracks": 0,
    "constTrackKeys": [],
    "trackKeys": [],
    "fallbackFrameIndices": [],
    "optimizationHints": OPTIMIZATION_HINT_DEFAULTS,
}
ANIMATION_EXTRAS_DEFAULTS = {
    **ACTION_DEFAULTS,
    "animEvents": None,
}
ACTION_FIELDS = tuple(ACTION_DEFAULTS) + ("animEvents",)


def track_payload_duration(extras) -> float:
    """Return the final timestamp carried by scalar animation keys"""
    return max(
        (
            float(entry["time"])
            for name in ("trackKeys", "constTrackKeys")
            for entry in extras.get(name, ())
        ),
        default=0.0,
    )


class AnimationMetadataError(ValueError):
    pass


def indexed_strings(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if value is not None and hasattr(value, "keys"):
        keys = list(value.keys())
        try:
            keys.sort(key=lambda key: int(key))
        except (TypeError, ValueError):
            keys.sort(key=str)
        return [str(value[key]) for key in keys]
    return []


def _metadata_error(error_type, message):
    raise error_type(message)


def _is_integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _validate_track_entries(entries, label: str, error_type) -> None:
    if not isinstance(entries, list):
        _metadata_error(error_type, f"{label} must be a list.")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            _metadata_error(error_type, f"{label}[{index}] must be an object.")
        if not ("trackIndex" in entry and "time" in entry and "value" in entry):
            missing = {"trackIndex", "time", "value"} - entry.keys()
            _metadata_error(
                error_type,
                f"{label}[{index}] is missing: {', '.join(sorted(missing))}.",
            )
        if not _is_integer(entry["trackIndex"]):
            _metadata_error(
                error_type, f"{label}[{index}].trackIndex must be an integer."
            )
        if not 0 <= entry["trackIndex"] <= 0xFFFF:
            _metadata_error(
                error_type,
                f"{label}[{index}].trackIndex must fit an unsigned 16-bit integer.",
            )
        for key in ("time", "value"):
            value = entry[key]
            if not _is_finite_number(value):
                _metadata_error(
                    error_type, f"{label}[{index}].{key} must be finite numeric data."
                )
        if float(entry["time"]) < 0.0:
            _metadata_error(error_type, f"{label}[{index}].time cannot be negative.")


def _validate_optional_string(value, label: str, error_type) -> None:
    if value is not None and not isinstance(value, str):
        _metadata_error(error_type, f"{label} must be a string or null.")


def _validate_event_payload(event, label: str, error_type) -> None:
    for key in ("type", "eventName", "startFrame", "durationInFrames"):
        if key not in event:
            _metadata_error(error_type, f"{label} is missing {key}.")
    for key in ("type", "eventName"):
        if not isinstance(event[key], str):
            _metadata_error(error_type, f"{label}.{key} must be a string.")
    for key in ("startFrame", "durationInFrames"):
        value = event[key]
        if not _is_integer(value) or not 0 <= value <= 0xFFFFFFFF:
            _metadata_error(
                error_type,
                f"{label}.{key} must fit an unsigned 32-bit integer.",
            )
    if event["startFrame"] + event["durationInFrames"] > 0xFFFFFFFF:
        _metadata_error(error_type, f"{label} end frame exceeds unsigned 32-bit range.")

    sequence_shift = event.get("sequenceShift")
    if sequence_shift is not None and (
        not _is_integer(sequence_shift) or not 0 <= sequence_shift <= 0xFFFFFFFF
    ):
        _metadata_error(
            error_type,
            f"{label}.sequenceShift must fit an unsigned 32-bit integer or be null.",
        )

    for key in ("breakAllLoopsOnStop", "isQuest"):
        value = event.get(key)
        if value is not None and not isinstance(value, bool):
            _metadata_error(error_type, f"{label}.{key} must be a boolean or null.")

    for key in (
        "metadataContext",
        "onlyPlayOn",
        "dontPlayOn",
        "playerGenderAlt",
        "emitterName",
        "effectName",
        "actionName",
        "boneName",
        "facialAnimName",
        "leg",
        "footPhase",
        "voContext",
        "side",
        "customEvent",
    ):
        _validate_optional_string(event.get(key), f"{label}.{key}", error_type)

    event_value = event.get("eventValue")
    if event_value is not None and not _is_finite_number(event_value):
        _metadata_error(
            error_type, f"{label}.eventValue must be finite numeric data or null."
        )

    switches = event.get("switches")
    if switches is not None:
        if not isinstance(switches, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in switches.items()
        ):
            _metadata_error(
                error_type,
                f"{label}.switches must be a string-to-string object or null.",
            )

    params = event.get("params")
    if params is not None:
        if not isinstance(params, dict) or any(
            not isinstance(key, str) or not _is_finite_number(value)
            for key, value in params.items()
        ):
            _metadata_error(
                error_type,
                f"{label}.params must map strings to finite numeric values or be null.",
            )

    dynamic_params = event.get("dynamicParams")
    if dynamic_params is not None and (
        not isinstance(dynamic_params, list)
        or any(not isinstance(value, str) for value in dynamic_params)
    ):
        _metadata_error(
            error_type, f"{label}.dynamicParams must be a string list or null."
        )

    param_curves = event.get("paramCurves")
    if param_curves is not None:
        if not isinstance(param_curves, list):
            _metadata_error(error_type, f"{label}.paramCurves must be a list or null.")
        for index, curve in enumerate(param_curves):
            curve_label = f"{label}.paramCurves[{index}]"
            if not isinstance(curve, dict):
                _metadata_error(error_type, f"{curve_label} must be an object.")
            for key in ("name", "enterCurveType", "exitCurveType"):
                if not isinstance(curve.get(key), str):
                    _metadata_error(
                        error_type, f"{curve_label}.{key} must be a string."
                    )
            for key in ("value", "enterCurveTime", "exitCurveTime"):
                if not _is_finite_number(curve.get(key)):
                    _metadata_error(
                        error_type, f"{curve_label}.{key} must be finite numeric data."
                    )

    workspot_actions = event.get("workspotActions")
    if workspot_actions is not None:
        if not isinstance(workspot_actions, list):
            _metadata_error(
                error_type, f"{label}.workspotActions must be a list or null."
            )
        valid_action_types = {
            "EquipItemToSlot",
            "EquipPropToSlot",
            "EquipInventoryWeapon",
            "UnequipFromSlot",
            "UnequipProp",
            "UnequipItem",
        }
        for index, action in enumerate(workspot_actions):
            action_label = f"{label}.workspotActions[{index}]"
            if not isinstance(action, dict):
                _metadata_error(error_type, f"{action_label} must be an object.")
            action_type = action.get("actionType")
            if action_type not in valid_action_types:
                _metadata_error(
                    error_type,
                    f"{action_label}.actionType is not supported by WolvenKit schema v5.",
                )
            for key in (
                "item",
                "itemSlot",
                "itemId",
                "attachMethod",
                "weaponType",
                "fallbackItem",
                "fallbackSlot",
            ):
                _validate_optional_string(
                    action.get(key), f"{action_label}.{key}", error_type
                )
            keep_equipped = action.get("keepEquippedAfterExit")
            if keep_equipped is not None and not isinstance(keep_equipped, bool):
                _metadata_error(
                    error_type,
                    f"{action_label}.keepEquippedAfterExit must be a boolean or null.",
                )
            for key in (
                "offsetPosX",
                "offsetPosY",
                "offsetPosZ",
                "offsetRotI",
                "offsetRotJ",
                "offsetRotK",
                "offsetRotR",
            ):
                value = action.get(key)
                if value is not None and not _is_finite_number(value):
                    _metadata_error(
                        error_type,
                        f"{action_label}.{key} must be finite numeric data or null.",
                    )


def validate_animation_extras(
    extras,
    *,
    label: str = "Animation extras",
    error_type=AnimationMetadataError,
    compatible_schema: bool = False,
) -> None:
    if not isinstance(extras, dict):
        _metadata_error(error_type, f"{label} must be an object.")

    missing = [key for key in ANIMATION_EXTRAS_DEFAULTS if key not in extras]
    if missing:
        _metadata_error(error_type, f"{label} is missing: {', '.join(missing)}.")

    schema = extras["schema"]
    if not isinstance(schema, dict):
        _metadata_error(error_type, f"{label}.schema must be an object.")
    if schema.get("type") != ANIMATION_SCHEMA["type"]:
        _metadata_error(
            error_type, f"{label}.schema.type is not a CP77 animation schema."
        )
    version = schema.get("version")
    if compatible_schema:
        if not _is_integer(version) or version < 1:
            _metadata_error(
                error_type,
                f"{label}.schema.version must be a positive integer.",
            )
    elif not _is_integer(version) or version != ANIMATION_SCHEMA["version"]:
        _metadata_error(
            error_type,
            f"{label}.schema.version must be exactly {ANIMATION_SCHEMA['version']}.",
        )

    if extras["animationType"] not in ANIMATION_TYPES:
        _metadata_error(
            error_type,
            f"{label}.animationType is not a supported animation type.",
        )
    if extras["rootMotionType"] not in ROOT_MOTION_TYPES:
        _metadata_error(
            error_type,
            f"{label}.rootMotionType is not a supported root motion type.",
        )
    if not isinstance(extras["frameClamping"], bool):
        _metadata_error(error_type, f"{label}.frameClamping must be a boolean.")
    for key in (
        "frameClampingStartFrame",
        "frameClampingEndFrame",
        "numExtraJoints",
        "numExtraTracks",
    ):
        if not _is_integer(extras[key]):
            _metadata_error(error_type, f"{label}.{key} must be an integer.")
    for key in ("frameClampingStartFrame", "frameClampingEndFrame"):
        if not -0x80 <= extras[key] <= 0x7F:
            _metadata_error(
                error_type,
                f"{label}.{key} must fit WolvenKit's signed 8-bit frame field.",
            )
    for key in ("numExtraJoints", "numExtraTracks"):
        if not 0 <= extras[key] <= 0xFF:
            _metadata_error(
                error_type, f"{label}.{key} must fit an unsigned 8-bit integer."
            )

    _validate_track_entries(extras["trackKeys"], f"{label}.trackKeys", error_type)
    _validate_track_entries(
        extras["constTrackKeys"], f"{label}.constTrackKeys", error_type
    )

    fallback = extras["fallbackFrameIndices"]
    if not isinstance(fallback, list) or any(
        not _is_integer(value) for value in fallback
    ):
        _metadata_error(
            error_type, f"{label}.fallbackFrameIndices must be an integer list."
        )
    if any(not 0 <= value <= 0xFFFF for value in fallback):
        _metadata_error(
            error_type,
            f"{label}.fallbackFrameIndices values must fit unsigned 16-bit integers.",
        )

    hints = extras["optimizationHints"]
    if not isinstance(hints, dict):
        _metadata_error(error_type, f"{label}.optimizationHints must be an object.")
    for key in OPTIMIZATION_HINT_DEFAULTS:
        if key not in hints:
            _metadata_error(error_type, f"{label}.optimizationHints is missing {key}.")
    if not isinstance(hints["preferSIMD"], bool):
        _metadata_error(
            error_type, f"{label}.optimizationHints.preferSIMD must be a boolean."
        )
    if not _is_integer(hints["maxRotationCompression"]) or hints[
        "maxRotationCompression"
    ] not in {0, 1}:
        _metadata_error(
            error_type,
            f"{label}.optimizationHints.maxRotationCompression must be 0 or 1.",
        )
    if (
        not _is_integer(hints["simdQuantizationBits"])
        or not 0 <= hints["simdQuantizationBits"] <= 0xFFFF
    ):
        _metadata_error(
            error_type,
            f"{label}.optimizationHints.simdQuantizationBits must fit an unsigned 16-bit integer.",
        )

    events = extras["animEvents"]
    if events is not None and not isinstance(events, list):
        _metadata_error(error_type, f"{label}.animEvents must be a list or null.")
    if isinstance(events, list):
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                _metadata_error(
                    error_type, f"{label}.animEvents[{index}] must be an object."
                )
            _validate_event_payload(event, f"{label}.animEvents[{index}]", error_type)


def normalize_animation_extras(
    extras,
    *,
    label: str = "Animation extras",
    error_type=AnimationMetadataError,
    require_schema: bool = False,
    compatible_schema: bool = False,
) -> dict:
    """Return extras in the current schema, filling documented defaults"""
    if extras is None:
        if require_schema:
            _metadata_error(error_type, f"{label} is missing.")
        extras = {}
    if not isinstance(extras, dict):
        _metadata_error(error_type, f"{label} must be an object.")

    normalized = plain_value(extras)
    schema = normalized.get("schema")
    if schema is None:
        if require_schema:
            _metadata_error(error_type, f"{label}.schema is missing.")
        normalized["schema"] = copy.deepcopy(ANIMATION_SCHEMA)

    for key, default in ANIMATION_EXTRAS_DEFAULTS.items():
        if key not in normalized:
            normalized[key] = copy.deepcopy(default)

    hints = normalized.get("optimizationHints")
    if isinstance(hints, dict):
        for key, default in OPTIMIZATION_HINT_DEFAULTS.items():
            if key not in hints:
                hints[key] = copy.deepcopy(default)

    validate_animation_extras(
        normalized,
        label=label,
        error_type=error_type,
        compatible_schema=compatible_schema,
    )
    if compatible_schema:
        normalized["schema"] = copy.deepcopy(ANIMATION_SCHEMA)
    return normalized


def decode_json_snapshot(payload) -> dict:
    """A stored snapshot as a dict, empty for a missing, malformed or non-object payload"""
    if not payload:
        return {}
    if isinstance(payload, dict):
        return plain_value(payload)
    return json_object(payload)


def optimization_hint(hints, key: str, default=None):
    if hints is None:
        return default
    try:
        return hints.get(key, default) if hasattr(hints, "get") else hints[key]
    except (KeyError, TypeError):
        return default


def prefers_simd(hints) -> bool:
    return bool(optimization_hint(hints, "preferSIMD", False))


def with_simd_preference(hints, prefer_simd: bool) -> dict:
    return {
        "preferSIMD": bool(prefer_simd),
        "maxRotationCompression": optimization_hint(hints, "maxRotationCompression", 0),
        "simdQuantizationBits": optimization_hint(hints, "simdQuantizationBits", 0),
    }


def source_channel_index(snapshot) -> dict[tuple[int, str], dict]:
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        return {}
    channels = snapshot.get("channels")
    if not isinstance(channels, list):
        return {}
    result = {}
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        try:
            key = (int(channel["jointIndex"]), str(channel["path"]))
        except (KeyError, TypeError, ValueError):
            continue
        if key not in result:
            result[key] = channel
    return result
