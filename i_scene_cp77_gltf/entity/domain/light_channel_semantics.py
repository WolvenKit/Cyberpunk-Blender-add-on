from __future__ import annotations

import re

from ...assetio.values import unwrapped
from ...bartmoss.clipping import bounds_intersect

LC_DEFAULT_ALL = 0
LC_CHANNEL1 = 1 << 0
LC_CHANNEL2 = 1 << 1
LC_CHANNEL3 = 1 << 2
LC_CHANNEL4 = 1 << 3
LC_CHANNEL5 = 1 << 4
LC_CHANNEL6 = 1 << 5
LC_CHANNEL7 = 1 << 6
LC_CHANNEL8 = 1 << 7
LC_CHANNEL_WORLD = 1 << 8
LC_CHARACTER = 1 << 9
LC_PLAYER = 1 << 10
LC_AUTOMATED = 1 << 15
LC_SPATIAL_MASK = (1 << 8) - 1
LC_SUPPORTED_MASK = (
    LC_SPATIAL_MASK | LC_CHANNEL_WORLD | LC_CHARACTER | LC_PLAYER | LC_AUTOMATED
)

_CHANNEL_BITS = {
    "LC_Channel1": LC_CHANNEL1,
    "LC_Channel2": LC_CHANNEL2,
    "LC_Channel3": LC_CHANNEL3,
    "LC_Channel4": LC_CHANNEL4,
    "LC_Channel5": LC_CHANNEL5,
    "LC_Channel6": LC_CHANNEL6,
    "LC_Channel7": LC_CHANNEL7,
    "LC_Channel8": LC_CHANNEL8,
    "LC_ChannelWorld": LC_CHANNEL_WORLD,
    "LC_World": LC_CHANNEL_WORLD,
    "LC_Character": LC_CHARACTER,
    "LC_Player": LC_PLAYER,
    "LC_Automated": LC_AUTOMATED,
}

_CANONICAL_NAMES = (
    (LC_CHANNEL1, "LC_Channel1"),
    (LC_CHANNEL2, "LC_Channel2"),
    (LC_CHANNEL3, "LC_Channel3"),
    (LC_CHANNEL4, "LC_Channel4"),
    (LC_CHANNEL5, "LC_Channel5"),
    (LC_CHANNEL6, "LC_Channel6"),
    (LC_CHANNEL7, "LC_Channel7"),
    (LC_CHANNEL8, "LC_Channel8"),
    (LC_CHANNEL_WORLD, "LC_ChannelWorld"),
    (LC_CHARACTER, "LC_Character"),
    (LC_PLAYER, "LC_Player"),
    (LC_AUTOMATED, "LC_Automated"),
)


def decode_light_channel(value):
    value = unwrapped(value, ("$value", "value"))
    if value is None:
        return 0, ()
    if isinstance(value, bool):
        return int(value), ()
    if isinstance(value, int):
        return int(value) & 0xFFFF, ()
    if isinstance(value, float) and value.is_integer():
        return int(value) & 0xFFFF, ()

    text = str(value).strip()
    if not text or text in {"None", "LC_DefaultAll"}:
        return 0, ()
    try:
        return int(text, 0) & 0xFFFF, ()
    except ValueError:
        pass

    mask = 0
    unknown = []
    for token in re.split(r"\s*(?:,|\||\+)\s*", text):
        if not token:
            continue
        bit = _CHANNEL_BITS.get(token)
        if bit is None:
            unknown.append(token)
            continue
        mask |= bit
    return mask & 0xFFFF, tuple(unknown)


def mapped_light_channel(mask):
    mask = int(mask) & 0xFFFF
    return LC_CHANNEL_WORLD if mask == LC_DEFAULT_ALL else mask


def is_automated_channel(mask, component=True):
    mask = int(mask) & 0xFFFF
    return mask == LC_AUTOMATED or (bool(component) and mask == LC_CHANNEL1)


def canonical_channel_names(mask, *, map_default=False):
    mask = int(mask) & 0xFFFF
    if map_default:
        mask = mapped_light_channel(mask)
    if mask == 0:
        return ("LC_DefaultAll",)
    names = [name for bit, name in _CANONICAL_NAMES if mask & bit]
    unknown = mask & ~LC_SUPPORTED_MASK
    if unknown:
        names.append(f"0x{unknown:04X}")
    return tuple(names)


def light_channel_text(mask):
    """mask as WolvenKit writes the bitfield"""
    mask = int(mask) & 0xFFFF
    return ", ".join(canonical_channel_names(mask)) if mask else "0"


def assign_runtime_volume_channels(volumes):
    runtime = [0 for _ in volumes]
    for index, volume in enumerate(volumes):
        authored = int(volume["authored_mask"]) & 0xFFFF
        if not is_automated_channel(authored, volume.get("component", False)):
            continue

        non_touching = LC_SPATIAL_MASK
        current_bounds = volume["bounds"]
        for other_index, other in enumerate(volumes):
            if other_index == index:
                continue
            if not bounds_intersect(current_bounds, other["bounds"], 0.0):
                continue
            other_mask = runtime[other_index] or int(other["authored_mask"])
            non_touching &= (~other_mask) & LC_SPATIAL_MASK

        if (non_touching & authored) == 0:
            free = non_touching & LC_SPATIAL_MASK
            runtime[index] = free & -free if free else 0

    return tuple(
        (runtime[index] or int(volume["authored_mask"])) & 0xFFFF
        for index, volume in enumerate(volumes)
    )


def effective_component_light_channel(authored_mask, light_bounds, volumes):
    authored_mask = int(authored_mask) & 0xFFFF
    if not is_automated_channel(authored_mask, True):
        return mapped_light_channel(authored_mask), "AUTHORED"

    for volume in volumes:
        if not volume.get("component", False):
            continue
        if not bounds_intersect(volume["bounds"], light_bounds, 0.0):
            continue
        effective = int(volume.get("effective_mask", volume["authored_mask"])) & 0xFFFF
        if effective:
            return effective, "COMPONENT_VOLUME"
    return mapped_light_channel(authored_mask), "AUTOMATED_UNRESOLVED"
