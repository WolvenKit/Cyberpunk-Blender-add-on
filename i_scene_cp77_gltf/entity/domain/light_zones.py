from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...assetio.paths import depot_path_key
from ...assetio.values import color_bytes, field_float
from ...bartmoss.scalar import clamp01
from .lights import light_starts_off, vehicle_light_types

ZONES = ("Zero", "One", "Two", "Three")
# The light components that name a materialZone (gameLightComponent and those that extend it).
ZONED_LIGHT_COMPONENT_TYPES = frozenset({"gameLightComponent", "vehicleLightComponent"})
# The material templates whose vertex colour red picks one of the four zones.
LIGHT_ZONE_TEMPLATES = frozenset(
    depot_path_key(path)
    for path in (
        "base\\materials\\lights_interactive.mt",
        "base\\materials\\vehicle_lights.mt",
    )
)


@dataclass(frozen=True)
class ZoneLight:
    """What a light component sets on one light zone of its mesh's materials"""

    zone: int
    color: tuple[float, float, float]
    strength: float
    starts_on: bool
    device: bool = True
    light_types: int = 0

    @property
    def level(self) -> float:
        """The strength the zone glows with at the start"""
        return self.strength if self.starts_on else 0.0


def zone_color_property(zone: int) -> str:
    return f"cp77_light_zone_color_{zone}"


def zone_strength_property(zone: int) -> str:
    return f"cp77_light_zone_strength_{zone}"


def zone_level_property(zone: int) -> str:
    return f"cp77_light_zone_level_{zone}"


def zone_starts_on_property(zone: int) -> str:
    return f"cp77_light_zone_starts_on_{zone}"


def zone_light_type_property(zone: int) -> str:
    """The key of the vehicleELightType flags of the vehicle lights that drive a zone"""
    return f"cp77_light_zone_light_type_{zone}"


def uses_light_zones(material_template) -> bool:
    return depot_path_key(material_template) in LIGHT_ZONE_TEMPLATES


def is_emissive_only(component: Mapping) -> bool:
    return bool(component.get("emissiveOnly"))


def zone_color(component: Mapping) -> tuple[float, float, float]:
    """The colour a light component's zone glows in"""
    emissive = component.get("emissiveColor")
    separate = component.get("allowSeparateEmissiveColor") and any(
        color_bytes(emissive, 0.0, 4)
    )
    color = emissive if separate else component.get("color")
    return tuple(clamp01(value / 255.0) for value in color_bytes(color))


def zone_light(component: Mapping, *, destroyed: bool = False) -> ZoneLight | None:
    """The zone a game or vehicle light component drives on its mesh, or None"""
    if component.get("$type") not in ZONED_LIGHT_COMPONENT_TYPES or not component.get(
        "isEnabled", 1
    ):
        return None
    zone = component.get("materialZone", ZONES[0])
    if zone not in ZONES:
        return None
    device = component.get("$type") != "vehicleLightComponent"
    return ZoneLight(
        zone=ZONES.index(zone),
        color=zone_color(component),
        strength=max(0.0, field_float(component, "onStrength", 1.0)),
        starts_on=device and not light_starts_off(component),
        device=device,
        light_types=0
        if device or destroyed
        else vehicle_light_types(component.get("lightType")),
    )
