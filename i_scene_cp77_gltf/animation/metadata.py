from __future__ import annotations

import copy
import json

from .values import plain_value

FPS = 30.0
ANIMATION_EXTRAS_SNAPSHOT_KEY = "cp77_animation_extras_json"
SKIN_EXTRAS_SNAPSHOT_KEY = "cp77_skin_extras_json"
SOURCE_REST_SNAPSHOT_KEY = "cp77_animation_source_rest_json"

ANIMATION_SCHEMA = {"type": "wkit.cp2077.gltf.anims", "version": 5}
MINIMUM_LEGACY_ANIMATION_SCHEMA_VERSION = 1
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


def _validate_track_entries(entries, label: str, error_type) -> None:
    if not isinstance(entries, list):
        _metadata_error(error_type, f"{label} must be a list.")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            _metadata_error(error_type, f"{label}[{index}] must be an object.")
        missing = {"trackIndex", "time", "value"} - set(entry)
        if missing:
            _metadata_error(
                error_type,
                f"{label}[{index}] is missing: {', '.join(sorted(missing))}.",
            )
        if not _is_integer(entry["trackIndex"]):
            _metadata_error(error_type, f"{label}[{index}].trackIndex must be an integer.")
        if entry["trackIndex"] < 0:
            _metadata_error(error_type, f"{label}[{index}].trackIndex cannot be negative.")
        for key in ("time", "value"):
            value = entry[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                _metadata_error(error_type, f"{label}[{index}].{key} must be numeric.")


def validate_animation_extras(
    extras,
    *,
    label: str = "Animation extras",
    error_type=AnimationMetadataError,
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
        _metadata_error(error_type, f"{label}.schema.type is not a CP77 animation schema.")
    version = schema.get("version")
    if not _is_integer(version) or version < ANIMATION_SCHEMA["version"]:
        _metadata_error(
            error_type,
            f"{label}.schema.version must be an integer of at least {ANIMATION_SCHEMA['version']}.",
        )

    for key in ("animationType", "rootMotionType"):
        if not isinstance(extras[key], str):
            _metadata_error(error_type, f"{label}.{key} must be a string.")
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
    if extras["numExtraJoints"] < 0 or extras["numExtraTracks"] < 0:
        _metadata_error(error_type, f"{label} extra joint and track counts cannot be negative.")

    _validate_track_entries(extras["trackKeys"], f"{label}.trackKeys", error_type)
    _validate_track_entries(extras["constTrackKeys"], f"{label}.constTrackKeys", error_type)

    fallback = extras["fallbackFrameIndices"]
    if not isinstance(fallback, list) or any(not _is_integer(value) for value in fallback):
        _metadata_error(error_type, f"{label}.fallbackFrameIndices must be an integer list.")
    if any(value < 0 for value in fallback):
        _metadata_error(error_type, f"{label}.fallbackFrameIndices cannot contain negatives.")

    hints = extras["optimizationHints"]
    if not isinstance(hints, dict):
        _metadata_error(error_type, f"{label}.optimizationHints must be an object.")
    for key in OPTIMIZATION_HINT_DEFAULTS:
        if key not in hints:
            _metadata_error(error_type, f"{label}.optimizationHints is missing {key}.")
    if not isinstance(hints["preferSIMD"], bool):
        _metadata_error(error_type, f"{label}.optimizationHints.preferSIMD must be a boolean.")
    for key in ("maxRotationCompression", "simdQuantizationBits"):
        if not _is_integer(hints[key]):
            _metadata_error(error_type, f"{label}.optimizationHints.{key} must be an integer.")
        if hints[key] < 0:
            _metadata_error(error_type, f"{label}.optimizationHints.{key} cannot be negative.")

    events = extras["animEvents"]
    if events is not None and not isinstance(events, list):
        _metadata_error(error_type, f"{label}.animEvents must be a list or null.")
    if isinstance(events, list) and any(not isinstance(event, dict) for event in events):
        _metadata_error(error_type, f"{label}.animEvents entries must be objects.")


def normalize_animation_extras(
    extras,
    *,
    label: str = "Animation extras",
    error_type=AnimationMetadataError,
) -> dict:
    if extras is None:
        extras = {}
    if not isinstance(extras, dict):
        _metadata_error(error_type, f"{label} must be an object.")

    normalized = plain_value(copy.deepcopy(extras))
    for key, default in ANIMATION_EXTRAS_DEFAULTS.items():
        if key not in normalized:
            normalized[key] = copy.deepcopy(default)

    schema = normalized.get("schema")
    if isinstance(schema, dict):
        schema.setdefault("type", ANIMATION_SCHEMA["type"])
        schema.setdefault("version", ANIMATION_SCHEMA["version"])
        version = schema.get("version")
        if (
            schema.get("type") == ANIMATION_SCHEMA["type"]
            and _is_integer(version)
            and MINIMUM_LEGACY_ANIMATION_SCHEMA_VERSION
            <= version
            < ANIMATION_SCHEMA["version"]
        ):
            schema["version"] = ANIMATION_SCHEMA["version"]

    hints = normalized.get("optimizationHints")
    if isinstance(hints, dict):
        for key, default in OPTIMIZATION_HINT_DEFAULTS.items():
            hints.setdefault(key, copy.deepcopy(default))

    validate_animation_extras(normalized, label=label, error_type=error_type)
    return normalized


def store_json_snapshot(owner, key: str, value) -> None:
    owner[key] = json.dumps(
        plain_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def load_json_snapshot(owner, key: str) -> dict:
    payload = owner.get(key) if owner is not None else None
    if not payload:
        return {}
    if isinstance(payload, dict):
        return plain_value(payload)
    try:
        value = json.loads(str(payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def ensure_action_defaults(action) -> None:
    for key, default in ACTION_DEFAULTS.items():
        if key not in action:
            action[key] = copy.deepcopy(default)

    action["schema"] = copy.deepcopy(ANIMATION_SCHEMA)

    hints = plain_value(action.get("optimizationHints"))
    if not isinstance(hints, dict):
        action["optimizationHints"] = copy.deepcopy(OPTIMIZATION_HINT_DEFAULTS)
    else:
        for key, default in OPTIMIZATION_HINT_DEFAULTS.items():
            hints.setdefault(key, copy.deepcopy(default))
        action["optimizationHints"] = hints


def apply_action_extras(action, extras, *, load_events=True) -> None:
    normalized = normalize_animation_extras(
        extras,
        label=f"Animation {getattr(action, 'name', '<unnamed>')!r} extras",
    )
    store_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY, normalized)
    for key, default in ACTION_DEFAULTS.items():
        action[key] = copy.deepcopy(normalized.get(key, default))

    events = normalized["animEvents"]
    if events is None:
        if "animEvents" in action:
            del action["animEvents"]
    else:
        action["animEvents"] = copy.deepcopy(events)

    if load_events:
        try:
            from .events import load_events_to_collection
            load_events_to_collection(action)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            print(f"[CP77] Could not load animation events for {action.name!r}: {error}")


def apply_skin_extras(armature, extras) -> None:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return
    if not isinstance(extras, dict):
        return
    store_json_snapshot(armature, SKIN_EXTRAS_SNAPSHOT_KEY, extras)
    rig_path = extras.get("rigPath")
    if rig_path is not None:
        armature["rigPath"] = plain_value(rig_path)
    bone_names = extras.get("boneNames")
    if bone_names:
        armature["boneNames"] = [str(value) for value in bone_names]
    parent_indices = extras.get("boneParentIndexes")
    if parent_indices:
        armature["boneParentIndexes"] = [int(value) for value in parent_indices]
    track_names = extras.get("trackNames")
    if track_names is not None:
        armature["trackNames"] = {
            str(index): str(name) for index, name in enumerate(track_names)
        }


def store_action_source(action, *, skin=None, source_rest=None) -> None:
    if isinstance(skin, dict):
        store_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY, skin)
    if isinstance(source_rest, dict):
        store_json_snapshot(action, SOURCE_REST_SNAPSHOT_KEY, source_rest)


def armature_track_names(armature) -> list[str]:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return []
    for owner in (armature, getattr(armature, "data", None)):
        if owner is None:
            continue
        names = indexed_strings(owner.get("trackNames"))
        if names:
            return names
    return []


def armature_skin_extras(armature) -> dict:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return {}
    skin = load_json_snapshot(armature, SKIN_EXTRAS_SNAPSHOT_KEY)
    skin.setdefault("rigPath", str(armature.get("rigPath", "")))
    bone_names = indexed_strings(armature.get("boneNames"))
    if bone_names:
        skin.setdefault("boneNames", bone_names)
    parents = armature.get("boneParentIndexes")
    if parents is not None:
        skin.setdefault("boneParentIndexes", [int(value) for value in parents])
    track_names = armature_track_names(armature)
    if track_names:
        skin.setdefault("trackNames", track_names)
    return skin


def action_skin_extras(action, armature=None) -> dict:
    snapshot = load_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY)
    return snapshot if snapshot else armature_skin_extras(armature)


def armature_source_rest(armature) -> dict:
    return load_json_snapshot(armature, SOURCE_REST_SNAPSHOT_KEY)


def action_source_rest(action, armature=None) -> dict:
    snapshot = load_json_snapshot(action, SOURCE_REST_SNAPSHOT_KEY)
    return snapshot if snapshot else armature_source_rest(armature)


def action_track_names(action, armature=None, skin=None) -> list[str]:
    source = skin if isinstance(skin, dict) else action_skin_extras(action, armature)
    if isinstance(source, dict) and "trackNames" in source:
        return indexed_strings(source.get("trackNames"))
    return armature_track_names(armature)
