from __future__ import annotations

import math

from ....assetio.transform_values import vector3_from_data
from ....assetio.values import coerce_float
from ...model.vehicle.camera import (
    DEFAULT_TPP_CAMERA_PARAMS_RECORD,
    TPP_CAMERA_DISTANCES,
    TPP_CAMERA_FALLBACK_PRESET,
    TPP_CAMERA_HEIGHTS,
    TPP_CAMERA_PARAM_DEFAULTS,
    TPP_CAMERA_PRESET_DEFAULTS,
)


def _vector3(value, fallback):
    try:
        result = list(vector3_from_data(value, fallback))
    except (TypeError, ValueError):
        return list(fallback)
    return (
        result
        if all(math.isfinite(component) for component in result)
        else list(fallback)
    )


def _number(fields, key, fallback):
    return coerce_float(fields.get(key, fallback), fallback, unwrap=False)


def _preset(fields):
    height = str(fields.get("height", "") or "")
    distance = str(fields.get("distance", "") or "")
    if height not in TPP_CAMERA_HEIGHTS or distance not in TPP_CAMERA_DISTANCES:
        return None
    defaults = TPP_CAMERA_PRESET_DEFAULTS
    boom = _number(fields, "baseBoomLength", defaults["baseBoomLength"]) + _number(
        fields, "boomLengthOffset", defaults["boomLengthOffset"]
    )
    return {
        "height": height,
        "distance": distance,
        "look_at_offset": _vector3(
            fields.get("lookAtOffset"), defaults["lookAtOffset"]
        ),
        "pitch": _number(
            fields, "defaultRotationPitch", defaults["defaultRotationPitch"]
        ),
        "boom_length": max(boom, 0.1),
    }


def _fallback_preset():
    preset = TPP_CAMERA_FALLBACK_PRESET
    return {
        "height": preset["height"],
        "distance": preset["distance"],
        "look_at_offset": list(preset["lookAtOffset"]),
        "pitch": float(preset["defaultRotationPitch"]),
        "boom_length": float(preset["boomLength"]),
    }


def _params(fields):
    fields = fields if isinstance(fields, dict) else {}
    result = {}
    for key, default in TPP_CAMERA_PARAM_DEFAULTS.items():
        if isinstance(default, bool):
            value = fields.get(key, default)
            result[key] = (
                value
                if isinstance(value, bool)
                else str(value).lower() in {"true", "1"}
            )
        else:
            result[key] = _number(fields, key, default)
    return result


def default_tpp_camera():
    """The camera of a vehicle without game data"""
    return {"params": _params({}), "presets": [_fallback_preset()]}


def resolve_tpp_camera(database, vehicle_fields, record_id):
    """The record's third-person camera parameters and presets"""
    params_reference = (
        vehicle_fields.get("tppCameraParams") or DEFAULT_TPP_CAMERA_PARAMS_RECORD
    )
    params = _params(database.link_fields(params_reference, record_id))
    presets = []
    for reference in vehicle_fields.get("tppCameraPresets") or ():
        fields = database.link_fields(reference, record_id)
        preset = _preset(fields) if fields else None
        if preset is not None and not any(
            item["height"] == preset["height"]
            and item["distance"] == preset["distance"]
            for item in presets
        ):
            presets.append(preset)
    return {"params": params, "presets": presets or [_fallback_preset()]}


def tpp_camera_preset(camera, height, distance):
    """The preset for a height and distance, the same distance at another height, or the first preset"""
    presets = list((camera or {}).get("presets") or ()) or [_fallback_preset()]
    for preset in presets:
        if preset["height"] == height and preset["distance"] == distance:
            return preset
    for preset in presets:
        if preset["distance"] == distance:
            return preset
    return presets[0]
