from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .headers import patch_2_5_header
from .transform_values import vector4_entry
from .values import float32_entry, resource_path_entry

Box = tuple[tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True, slots=True)
class SectorDescriptor:
    """A sector for a streaming block"""

    depot_path: str
    category: str
    streaming_box: Box
    level: int = 0


def streaming_box(
    placements: Iterable[tuple[tuple[float, float, float], float]],
) -> Box:
    """The box around every (position, streaming distance) placement grown by its own distance"""
    corners = [
        (
            tuple(float(axis) - float(distance) for axis in position),
            tuple(float(axis) + float(distance) for axis in position),
        )
        for position, distance in placements
    ]
    if not corners:
        raise ValueError("A streaming box needs at least one placement.")
    return (
        tuple(min(low[axis] for low, _ in corners) for axis in range(3)),
        tuple(max(high[axis] for _, high in corners) for axis in range(3)),
    )


def _vector4(point: Sequence[float]) -> dict:
    return vector4_entry(*(float32_entry(value) for value in point), 1)


def _block_index() -> dict:
    """Cell 0 of the base group, which the game gives the sectors that sit in no cell of the world grid"""
    return {"$type": "worldStreamingBlockIndex", "oup": "Base", "rldGridCell": 0}


def _descriptor_entry(descriptor: SectorDescriptor) -> dict:
    low, high = descriptor.streaming_box
    return {
        "$type": "worldStreamingSectorDescriptor",
        "blockIndex": _block_index(),
        "category": descriptor.category,
        "data": resource_path_entry(descriptor.depot_path, "Soft"),
        "level": descriptor.level,
        "numNodeRanges": 1,
        "questPrefabNodeRef": {"$type": "NodeRef", "$storage": "uint64", "$value": "0"},
        "streamingBox": {"$type": "Box", "Max": _vector4(high), "Min": _vector4(low)},
        "variants": [],
    }


def streaming_block_document(
    descriptors: Sequence[SectorDescriptor], *, archive_file_name: str
) -> dict:
    """A .streamingblock document in WolvenKit's JSON form that lists descriptors"""
    return {
        "Header": patch_2_5_header(archive_file_name),
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "worldStreamingBlock",
                "cookingPlatform": "PLATFORM_PC",
                "descriptors": [
                    _descriptor_entry(descriptor) for descriptor in descriptors
                ],
                "index": _block_index(),
            },
            "EmbeddedFiles": [],
        },
    }
