from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .metadata import (
    ANIMATION_EXTRAS_SNAPSHOT_KEY,
    action_skin_extras,
    action_source_rest,
    action_track_names,
    load_json_snapshot,
)


@dataclass(frozen=True)
class TrackBinding:
    names: tuple[str, ...]
    index_by_name: Mapping[str, int]
    index_by_path: Mapping[str, int]

    def name(self, index: int) -> str:
        return self.names[index] if 0 <= index < len(self.names) else f"T{index:02d}"

    def data_path(self, index: int) -> str:
        return f'["{self.name(index)}"]'


@dataclass(frozen=True)
class ActionBinding:
    extras: dict
    skin: dict
    source_rest: dict
    tracks: TrackBinding


def create_track_binding(names) -> TrackBinding:
    resolved = tuple(str(name) for name in names)
    index_by_name = {name: index for index, name in enumerate(resolved)}
    index_by_path = {f'["{name}"]': index for index, name in enumerate(resolved)}
    return TrackBinding(
        names=resolved,
        index_by_name=MappingProxyType(index_by_name),
        index_by_path=MappingProxyType(index_by_path),
    )


def resolve_track_binding(action=None, armature=None, skin=None) -> TrackBinding:
    return create_track_binding(action_track_names(action, armature, skin))


def resolve_action_binding(action, armature=None) -> ActionBinding:
    skin = action_skin_extras(action, armature)
    return ActionBinding(
        extras=load_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY),
        skin=skin,
        source_rest=action_source_rest(action, armature),
        tracks=resolve_track_binding(action, armature, skin),
    )
