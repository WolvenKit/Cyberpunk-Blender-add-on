from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ....bartmoss.quaternion import IDENTITY_XYZW


@dataclass(frozen=True)
class TrackSnapshot:
    existed: bool
    value: float


@dataclass(frozen=True)
class BranchFrame:
    pose: Mapping[str, Any]
    tracks: Mapping[str, TrackSnapshot]
    parent_map: Mapping[str, str]
    reference_pose: Mapping[str, Any]
    reference_tracks: Mapping[str, float]
    transform_scopes: tuple[TransformStackScope, ...] = ()
    track_scopes: tuple[TrackStackScope, ...] = ()
    model_space: bool = False
    ik_targets: tuple[IkTarget, ...] = ()


@dataclass(frozen=True)
class IkTarget:
    chain: str
    priority: int = 0
    transition_in: float = 0.0
    transition_out: float = 0.0
    weight_position: float = 0.0
    weight_orientation: float = 0.0
    pole_weight: float = 0.0
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float, float] = IDENTITY_XYZW
    pole: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class TransformStackScope:
    tag: str
    names: tuple[str, ...]
    materialized: tuple[bool, ...] = ()


@dataclass(frozen=True)
class TrackStackScope:
    tag: str
    names: tuple[str, ...]
    materialized: tuple[bool, ...] = ()
