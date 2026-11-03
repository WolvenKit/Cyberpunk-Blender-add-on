from __future__ import annotations

import copy
import hashlib
import math
import random
from collections.abc import Mapping
from enum import Enum
from typing import Any

from ...assetio.values import (
    COLOR_CHANNELS,
    coerce_float,
    coerce_int,
    color_bytes,
    field_float,
    float32_entry,
)

BLENDER_EXPOSURE_RANGE = (-32.0, 32.0)
# How far a stored number may stray from its node's and still count as the same setting.
LIGHT_SETTING_TOLERANCE = 1e-6
_FLICKER_SETTINGS = ("flickerStrength", "flickerPeriod")


# Smallest radius, then the largest for a light that lights the scene and for one that does not.
LIGHT_RADIUS_LIMITS = (0.01, 60.0, 300.0)
LIGHT_ATTENUATION_CLAMP_DEFAULT = 96.0


def effective_light_radius(radius, scene_diffuse=True, scene_specular=True):
    minimum, scene_maximum, nonscene_maximum = LIGHT_RADIUS_LIMITS
    maximum = (
        scene_maximum
        if bool(scene_diffuse) or bool(scene_specular)
        else nonscene_maximum
    )
    return max(minimum, min(float(radius), maximum))


def effective_shadow_angle(data):
    shadow_angle = float(data.get("shadowAngle", -1.0) or -1.0)
    if shadow_angle > 0.0:
        return shadow_angle
    return float(data.get("outerAngle", 45.0) or 45.0)


def local_shadows_enabled(data):
    if not bool(data.get("enableLocalShadows", False)):
        return False
    light_type = str(data.get("type", "LT_Point"))
    if light_type == "LT_Spot":
        supported = True
    elif light_type == "LT_Area":
        supported = str(data.get("areaShape", "ALS_Capsule")) == "ALS_Capsule" and bool(
            data.get("spotCapsule", False)
        )
    else:
        supported = False
    return supported and effective_shadow_angle(data) < 175.0


def clamp_blender_exposure(ev):
    value = float(ev)
    if not math.isfinite(value):
        return 0.0
    minimum, maximum = BLENDER_EXPOSURE_RANGE
    return max(minimum, min(maximum, value))


def flicker_multipliers(strength, count, seed_value):
    strength = max(0.0, min(1.0, float(strength)))
    count = max(0, int(count))
    if strength <= 0.0 or count <= 0:
        return ()
    seed_bytes = str(seed_value).encode("utf-8", errors="replace")
    seed = int.from_bytes(hashlib.blake2b(seed_bytes, digest_size=8).digest(), "little")
    rng = random.Random(seed)
    values = [1.0 - 0.5 * strength]
    values.extend(1.0 - rng.uniform(0.0, strength) for _ in range(count))
    return tuple(values)


def light_contributions(data, *, static_node=False):
    """The light's diffuse, specular, volume and transmission factors, by those names"""
    specular = (
        0.0
        if data.get("noSpecular", 0)
        else max(float(data.get("sceneSpecular", 1.0) or 0.0), 0.0)
    )
    volume = max(float(data.get("scaleVolFog", 0.0) or 0.0), 0.0) / 100.0
    if (
        not static_node
        and not data.get("useInFog", 0)
        or static_node
        and "useInFog" in data
        and not data.get("useInFog", 0)
    ):
        volume = 0.0
    return {
        "diffuse": max(float(data.get("sceneDiffuse", 1.0) or 0.0), 0.0),
        "specular": specular
        * max(float(data.get("sceneSpecularScale", 100.0) or 0.0), 0.0)
        / 100.0,
        "volume": volume,
        "transmission": 1.0 if data.get("useInTransparents", 1) else 0.0,
    }


class LightGroup(str, Enum):
    """What a light does in the game"""

    WORLD = "WORLD"
    CHARACTERS = "CHARACTERS"
    FOG_GI = "FOG_GI"
    REFLECTIONS = "REFLECTIONS"
    DEVICES = "DEVICES"


def light_starts_off(settings: Mapping[str, Any]) -> bool:
    """Whether a light component starts switched off (turnOnByDefault 0), waiting for its device"""
    return not coerce_int(settings.get("turnOnByDefault", 1), 1)


def light_group(settings: Mapping[str, Any], *, from_entity: bool) -> LightGroup:
    """The group of a light with these game settings"""
    if str(settings.get("lightChannel", "")).strip() == "LC_Character":
        return LightGroup.CHARACTERS
    if not coerce_float(settings.get("sceneDiffuse", 1.0), 1.0):
        if not coerce_float(settings.get("sceneSpecularScale", 100.0), 100.0):
            return LightGroup.FOG_GI
        return LightGroup.REFLECTIONS
    if from_entity and light_starts_off(settings):
        return LightGroup.DEVICES
    return LightGroup.WORLD


def static_light_flicker_seed(sector_name, node_index, instance_index) -> str:
    """What a sector light's flicker is drawn from"""
    return f"{sector_name}:{node_index}:{instance_index}"


def static_light_settings(data: Mapping) -> dict:
    """The game settings of a sector light that its light keeps once imported or edited"""
    flicker = data.get("flicker") if isinstance(data.get("flicker"), Mapping) else {}
    return {
        "intensity": field_float(data, "intensity", 0.0),
        "EV": field_float(data, "EV", 0.0),
        "color": tuple(int(value) for value in color_bytes(data.get("color"), count=4)),
        "temperature": field_float(data, "temperature", -1.0),
        "radius": field_float(data, "radius", 5.0),
        "innerAngle": field_float(data, "innerAngle", 0.0),
        "outerAngle": field_float(data, "outerAngle", 0.0),
        "lightChannel": str(data.get("lightChannel", "")),
        "enableLocalShadows": bool(data.get("enableLocalShadows", 0)),
        "flickerStrength": field_float(flicker, "flickerStrength", 0.0),
        "flickerPeriod": field_float(flicker, "flickerPeriod", 0.0),
    }


def _setting_changed(stored, expected) -> bool:
    if isinstance(expected, bool):
        return bool(stored) != expected
    if isinstance(expected, float):
        value = coerce_float(stored, math.nan)
        return not math.isclose(
            value,
            expected,
            rel_tol=LIGHT_SETTING_TOLERANCE,
            abs_tol=LIGHT_SETTING_TOLERANCE,
        )
    if isinstance(expected, tuple):
        # Blender's ID property arrays are sequences without __iter__.
        values = (
            tuple(stored)
            if hasattr(stored, "__len__") and not isinstance(stored, str)
            else ()
        )
        return (
            tuple(coerce_int(value, -1) for value in values) != expected[: len(values)]
        )
    return str(stored) != expected


def light_settings_changed(light: Mapping, settings: Mapping) -> bool:
    """Whether a light keeps a setting that differs from settings"""
    return any(
        key in light and _setting_changed(light[key], expected)
        for key, expected in settings.items()
    )


def edited_light_data(data: Mapping, light: Mapping) -> dict:
    """A copy of a sector light's node Data with the light's changed game settings written over it"""
    edited = copy.deepcopy(dict(data))
    for key, expected in static_light_settings(data).items():
        if key not in light or not _setting_changed(light[key], expected):
            continue
        value = light[key]
        if key == "color":
            color = (
                dict(edited["color"])
                if isinstance(edited.get("color"), Mapping)
                else {"$type": "Color"}
            )
            color.update(
                {
                    channel: coerce_int(item, 255)
                    for channel, item in zip(COLOR_CHANNELS, tuple(value))
                }
            )
            edited["color"] = color
        elif key in _FLICKER_SETTINGS:
            flicker = (
                dict(edited["flicker"])
                if isinstance(edited.get("flicker"), Mapping)
                else {"$type": "rendSLightFlickering"}
            )
            flicker[key] = float32_entry(coerce_float(value))
            edited["flicker"] = flicker
        elif isinstance(expected, bool):
            edited[key] = int(bool(value))
        elif isinstance(expected, float):
            edited[key] = float32_entry(coerce_float(value))
        else:
            edited[key] = str(value)
    return edited


# The game's vehicleELightType flags; Default and Blinkers name several.
VEHICLE_LIGHT_TYPES = {
    "Head": 1,
    "Brake": 2,
    "LeftBlinker": 4,
    "RightBlinker": 8,
    "Reverse": 16,
    "Interior": 32,
    "Utility": 64,
    "Default": 47,
    "Blinkers": 12,
}


def vehicle_light_types(value) -> int:
    """The vehicleELightType flags of a vehicle light's lightType"""
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    types = 0
    for name in text.split(","):
        types |= VEHICLE_LIGHT_TYPES.get(name.strip(), 0)
    return types


class VehicleLightGroup(str, Enum):
    """A row of the vehicle switches, in the order the rows show them"""

    HEAD = "HEAD"
    HIGH_BEAM = "HIGH_BEAM"
    BRAKE = "BRAKE"
    LEFT_BLINKER = "LEFT_BLINKER"
    RIGHT_BLINKER = "RIGHT_BLINKER"
    REVERSE = "REVERSE"
    INTERIOR = "INTERIOR"
    UTILITY = "UTILITY"


# The vehicleELightType flag each group switches; High Beam switches the Head lights in their high-beam geometry.
VEHICLE_GROUP_TYPES = {
    VehicleLightGroup.HEAD: VEHICLE_LIGHT_TYPES["Head"],
    VehicleLightGroup.HIGH_BEAM: VEHICLE_LIGHT_TYPES["Head"],
    VehicleLightGroup.BRAKE: VEHICLE_LIGHT_TYPES["Brake"],
    VehicleLightGroup.LEFT_BLINKER: VEHICLE_LIGHT_TYPES["LeftBlinker"],
    VehicleLightGroup.RIGHT_BLINKER: VEHICLE_LIGHT_TYPES["RightBlinker"],
    VehicleLightGroup.REVERSE: VEHICLE_LIGHT_TYPES["Reverse"],
    VehicleLightGroup.INTERIOR: VEHICLE_LIGHT_TYPES["Interior"],
    VehicleLightGroup.UTILITY: VEHICLE_LIGHT_TYPES["Utility"],
}


def vehicle_light_groups(types: int) -> tuple[VehicleLightGroup, ...]:
    """The groups a vehicle light or light zone with the vehicleELightType flags types belongs to"""
    return tuple(
        group for group in VehicleLightGroup if types & VEHICLE_GROUP_TYPES[group]
    )


def is_destroyed_vehicle_appearance(name) -> bool:
    """Whether a vehicle entity appearance shows the vehicle destroyed"""
    return "burnt" in str(name or "").lower()


# The strength a Head light and the zones it drives shine at in high beam, in place of its onStrength.
HIGH_BEAM_STRENGTH = 1.0


def high_beam_energy(base_energy, on_strength) -> float:
    """A Head light's energy in high beam"""
    on_strength = coerce_float(on_strength, 1.0)
    return (
        base_energy * HIGH_BEAM_STRENGTH / on_strength
        if on_strength > 0.0
        else base_energy
    )


def vehicle_light_lit(types: int, on) -> bool:
    """Whether a vehicle light or light zone of types is on while the groups on are"""
    return any(types & VEHICLE_GROUP_TYPES[group] for group in on)
