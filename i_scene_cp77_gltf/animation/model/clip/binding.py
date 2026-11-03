from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class TrackBinding:
    names: tuple[str, ...]
    index_by_name: Mapping[str, int]
    index_by_path: Mapping[str, int]

    def name(self, index: int) -> str:
        return self.names[index] if 0 <= index < len(self.names) else f"T{index:02d}"

    def data_path(self, index: int) -> str:
        return track_property_path(self.name(index))


@dataclass(frozen=True)
class ActionBinding:
    extras: dict
    skin: dict
    source_rest: dict
    tracks: TrackBinding


def track_property_path(name: str) -> str:
    """Quote a scalar property name for Blender's RNA path syntax"""
    return "[" + json.dumps(str(name), ensure_ascii=False) + "]"


def track_name_from_property_path(data_path: str) -> str | None:
    """Inverse of track_property_path, or None for any other RNA path"""
    if not data_path.startswith("["):
        return None
    try:
        value = ast.literal_eval(data_path)
    except (SyntaxError, ValueError):
        return None
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    return None


def create_track_binding(names) -> TrackBinding:
    resolved = tuple(str(name) for name in names)
    index_by_name = {name: index for index, name in enumerate(resolved)}
    index_by_path = {
        track_property_path(name): index for index, name in enumerate(resolved)
    }
    return TrackBinding(
        names=resolved,
        index_by_name=MappingProxyType(index_by_name),
        index_by_path=MappingProxyType(index_by_path),
    )
