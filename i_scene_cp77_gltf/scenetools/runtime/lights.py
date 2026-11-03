from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import bpy
from bpy.app.handlers import persistent

from ...blender.identity import rna_is_live
from ...entity.domain.light_zones import (
    ZONES,
    zone_light_type_property,
    zone_starts_on_property,
)
from ...entity.domain.lights import (
    LightGroup,
    is_destroyed_vehicle_appearance,
    light_group,
    light_starts_off,
    vehicle_light_groups,
    vehicle_light_types,
)
from ...importers.common.light_channel_semantics import (
    LC_CHANNEL1,
    LC_CHANNEL_WORLD,
    LC_CHARACTER,
    decode_light_channel,
    mapped_light_channel,
)
from ...importers.common.vehicle_light_preview import is_vehicle_light_object
from ...importers.entity.policy import LIGHT_COMPONENT_TYPES
from .sectors import scene_sectors
from .vehicle_lights import vehicle_light_collections

SECTOR_LIGHT_NODE = "worldStaticLightNode"
_VEHICLE_LIGHT = "vehicleLightComponent"
# Vehicle lights follow the vehicle switches and take no group.
_ENTITY_LIGHTS = LIGHT_COMPONENT_TYPES - {_VEHICLE_LIGHT}
# The channel flag each Light Channel choice narrows the rows to; All narrows nothing.
CHANNEL_FILTER_BITS = {
    "WORLD": LC_CHANNEL_WORLD,
    "CHARACTER": LC_CHARACTER,
    **{f"CHANNEL_{number}": LC_CHANNEL1 << (number - 1) for number in range(1, 9)},
}

_INDEX = None
_OBJECT_COUNT = -1
# Whether the file holds lights the Lights rows show, and the object count that was found at.
_HOLDS_LIGHTS = False
_HOLDS_LIGHTS_COUNT = -1
# The last sector light_sector found: (scene and light session ids, object and collection counts), then the sector.
_LIGHT_SECTOR = [None, None]


@dataclass(frozen=True, slots=True)
class LightMember:
    """A Blender light the Lights rows act on"""

    obj: bpy.types.Object
    group: LightGroup
    channel: int
    starts_off: bool


@dataclass(frozen=True, slots=True)
class VehicleLight:
    """A vehicle's Blender light the vehicle switches act on"""

    samples: tuple
    types: int
    enabled: bool


@dataclass(frozen=True)
class LightPreview:
    """What the Lights rows show"""

    shown: frozenset
    brightness: dict
    channel: int
    devices_on: bool
    vehicles_on: frozenset

    def shows(self, member) -> bool:
        return member.group in self.shown and (
            not self.channel or bool(member.channel & self.channel)
        )

    def lit(self, member) -> bool:
        return self.devices_on or not member.starts_off

    def factor(self, member) -> float:
        return float(self.brightness.get(member.group, 1.0))

    @property
    def at_rest(self) -> bool:
        """Whether the rows show every light as its import leaves it"""
        return (
            self.shown >= frozenset(LightGroup)
            and all(value == 1.0 for value in self.brightness.values())
            and not self.channel
            and not self.devices_on
            and not self.vehicles_on
        )


class LightIndex:
    """The file's imported lights and light zones by group"""

    def __init__(self, members, zones, vehicle_lights, vehicle_zones):
        grouped = defaultdict(list)
        samples = defaultdict(list)
        for member in members:
            grouped[member.group].append(member)
            light = (
                member.obj.parent if member.obj.get("cp77_light_proxy") else member.obj
            )
            samples[light.as_pointer()].append(member)
        self._groups = {
            group: tuple(grouped[group]) for group in LightGroup if grouped[group]
        }
        self._samples = {pointer: tuple(found) for pointer, found in samples.items()}
        self.starting_off = tuple(member for member in members if member.starts_off)
        self.zones = zones
        self.vehicle_lights = vehicle_lights
        self.vehicle_zones = vehicle_zones
        types = 0
        for light in vehicle_lights:
            types |= light.types
        for _zone, zone_types, _objects in vehicle_zones:
            types |= zone_types
        # The vehicle groups that hold lights or light zones, in the order the rows show them.
        self.vehicle_groups = vehicle_light_groups(types)

    def __bool__(self):
        return bool(self._groups or self.zones)

    @property
    def groups(self) -> tuple[LightGroup, ...]:
        """The groups that hold lights, in the order the rows show them"""
        return tuple(self._groups)

    @property
    def switched(self) -> bool:
        """Whether the device switch has anything to switch"""
        return bool(self.starting_off or self.zones)

    def members(self, group) -> tuple[LightMember, ...]:
        return self._groups.get(group, ())

    def every_member(self) -> tuple[LightMember, ...]:
        return tuple(member for members in self._groups.values() for member in members)

    def samples(self, light) -> tuple[LightMember, ...]:
        """The members of a light"""
        return self._samples.get(light.as_pointer(), ())


def _member(obj):
    """The member an imported light makes, or None for a light the rows leave alone"""
    if not obj.get("cp77_component_enabled", True):
        return None
    if obj.get("cp77_node_type") == SECTOR_LIGHT_NODE:
        from_entity = False
    elif obj.get("cp77_type") in _ENTITY_LIGHTS:
        # An entity light records its component's type; a sector light records its node's.
        from_entity = True
    else:
        return None
    channel = mapped_light_channel(decode_light_channel(obj.get("lightChannel", 0))[0])
    return LightMember(
        obj,
        light_group(obj, from_entity=from_entity),
        channel,
        from_entity and light_starts_off(obj),
    )


def _built_index():
    collections = vehicle_light_collections()
    vehicles = {
        obj.as_pointer() for collection in collections for obj in collection.all_objects
    }
    # A destroyed vehicle's lights never light, so the vehicle switches leave them out.
    destroyed = {
        obj.as_pointer()
        for collection in collections
        if is_destroyed_vehicle_appearance(collection.get("appearanceName"))
        for obj in collection.all_objects
    }
    starts_on_names = tuple(zone_starts_on_property(zone) for zone in range(len(ZONES)))
    types_names = tuple(zone_light_type_property(zone) for zone in range(len(ZONES)))
    primaries, proxies, zones = {}, [], defaultdict(list)
    vehicle_lights, vehicle_zones = {}, defaultdict(list)
    for obj in bpy.data.objects:
        kind = obj.type
        if kind == "LIGHT":
            if obj.get("cp77_light_proxy"):
                proxies.append(obj)
            elif is_vehicle_light_object(obj):
                if obj.as_pointer() not in destroyed:
                    vehicle_lights[obj.as_pointer()] = [obj]
            else:
                member = _member(obj)
                if member is not None:
                    primaries[obj.as_pointer()] = member
        elif kind == "MESH":
            if obj.as_pointer() in vehicles:
                for zone, name in enumerate(types_names):
                    types = obj.get(name)
                    if types is not None:
                        vehicle_zones[(zone, int(types))].append(obj)
            else:
                for zone, name in enumerate(starts_on_names):
                    if obj.get(name, True) is False:
                        zones[zone].append(obj)
    members = list(primaries.values())
    for proxy in proxies:
        # A capsule light's samples follow their light.
        parent = proxy.parent.as_pointer() if proxy.parent is not None else None
        primary = primaries.get(parent)
        if primary is not None:
            members.append(
                LightMember(proxy, primary.group, primary.channel, primary.starts_off)
            )
        elif parent in vehicle_lights:
            vehicle_lights[parent].append(proxy)
    return LightIndex(
        members,
        tuple((zone, tuple(objects)) for zone, objects in sorted(zones.items())),
        tuple(
            VehicleLight(
                tuple(samples),
                vehicle_light_types(samples[0].get("lightType")),
                bool(samples[0].get("cp77_component_enabled", True)),
            )
            for samples in vehicle_lights.values()
        ),
        tuple(
            (zone, types, tuple(objects))
            for (zone, types), objects in sorted(vehicle_zones.items())
        ),
    )


def _holds_lights():
    """Whether _built_index would find a light or a light zone for the rows, stopping at the first"""
    starts_on_names = tuple(zone_starts_on_property(zone) for zone in range(len(ZONES)))
    vehicles = None
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            if (
                not obj.get("cp77_light_proxy")
                and not is_vehicle_light_object(obj)
                and _member(obj) is not None
            ):
                return True
        elif obj.type == "MESH" and any(
            obj.get(name, True) is False for name in starts_on_names
        ):
            if vehicles is None:
                vehicles = {
                    part.as_pointer()
                    for collection in vehicle_light_collections()
                    for part in collection.all_objects
                }
            if obj.as_pointer() not in vehicles:
                return True
    return False


@persistent
def clear_light_index(_unused=None):
    global _INDEX, _OBJECT_COUNT, _HOLDS_LIGHTS_COUNT
    _INDEX, _OBJECT_COUNT, _HOLDS_LIGHTS_COUNT = None, -1, -1
    _LIGHT_SECTOR[:] = (None, None)


def light_index() -> LightIndex:
    """The file's lights by group"""
    global _INDEX, _OBJECT_COUNT
    count = len(bpy.data.objects)
    if _INDEX is None or count != _OBJECT_COUNT:
        _INDEX, _OBJECT_COUNT = _built_index(), count
    return _INDEX


def holds_lights() -> bool:
    """Whether the light index holds anything, without building it"""
    global _HOLDS_LIGHTS, _HOLDS_LIGHTS_COUNT
    count = len(bpy.data.objects)
    if _INDEX is not None and count == _OBJECT_COUNT:
        return bool(_INDEX)
    if count != _HOLDS_LIGHTS_COUNT:
        _HOLDS_LIGHTS, _HOLDS_LIGHTS_COUNT = _holds_lights(), count
    return _HOLDS_LIGHTS


def act_on_lights(action):
    """action run on the light index, retried on a fresh index if a light was removed"""
    try:
        return action(light_index())
    except ReferenceError:
        clear_light_index()
        return action(light_index())


def active_sector_light(context):
    """The sector light the active object is, or None"""
    obj = getattr(context, "active_object", None)
    if obj is not None and obj.get("cp77_light_proxy"):
        obj = obj.parent
    if (
        obj is None
        or obj.type != "LIGHT"
        or obj.get("cp77_node_type") != SECTOR_LIGHT_NODE
    ):
        return None
    return obj


def light_sector(scene, light):
    """The imported sector of a sector light, or None"""
    key = (
        scene.session_uid,
        light.session_uid,
        len(bpy.data.objects),
        len(bpy.data.collections),
    )
    found = _LIGHT_SECTOR[1]
    if _LIGHT_SECTOR[0] == key and (found is None or rna_is_live(found)):
        return found
    name = light.get("cp77_sector_name")
    # Each collection's own objects: all_objects builds a cache of the whole tree, seconds for a big sector, after
    # every change to it.
    found = next(
        (
            sector
            for sector in scene_sectors(scene).imported
            if sector.get("cp77_sector_name") == name
            and any(
                light.name in collection.objects
                for collection in (sector, *sector.children_recursive)
            )
        ),
        None,
    )
    _LIGHT_SECTOR[:] = (key, found)
    return found
