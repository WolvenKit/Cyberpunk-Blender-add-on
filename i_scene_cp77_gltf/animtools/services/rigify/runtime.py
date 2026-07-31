from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

import bpy
from mathutils import Matrix

from ....animation.rigify.mapping import (
    CP77_TO_METARIG,
    FORWARD_LIMITED_LOCATION_BONES,
    FORWARD_LOCATION_BONES,
    FORWARD_REST_ONLY_BONES,
    resolve_forward_target,
)


@dataclass(slots=True)
class ForwardSyncEntry:
    source_name: str
    target_name: str
    source_pose_bone: object
    target_rest: Matrix
    target_neutral: Optional[Matrix]
    depth: int
    copy_location: bool
    limited_location: bool
    rest_only: bool
    basis: Matrix = field(default_factory=lambda: Matrix.Identity(4))


@dataclass(slots=True)
class RigSyncRuntime:
    source: object
    rig: object
    entries: tuple[ForwardSyncEntry, ...]
    depth_ranges: tuple[tuple[int, int], ...]
    neutralized_controls: tuple[object, ...]
    source_data: object
    rig_data: object
    manual_sync: bool = False

    def valid(self) -> bool:
        if self.source is None or self.rig is None:
            return False
        if getattr(self.source, "type", None) != "ARMATURE":
            return False
        if getattr(self.rig, "type", None) != "ARMATURE":
            return False
        try:
            return (
                bpy.data.objects.get(self.source.name) is self.source
                and bpy.data.objects.get(self.rig.name) is self.rig
            )
        except Exception:
            return False

    def topology_changed(self, updates: Iterable[object]) -> bool:
        for value in updates:
            if value is self.source_data or value is self.rig_data:
                return True
        return self.source.data is not self.source_data or self.rig.data is not self.rig_data

    def matches_updates(self, updates: Iterable[object]) -> bool:
        updates = tuple(updates)
        if not updates:
            return True
        action = None
        animation_data = getattr(self.rig, "animation_data", None)
        if animation_data is not None:
            action = animation_data.action
        for value in updates:
            if any(value is candidate for candidate in (self.source, self.rig, self.source_data, self.rig_data, action)):
                return True
        return False


_RUNTIMES: dict[int, RigSyncRuntime] = {}


def object_key(obj) -> int:
    try:
        return int(obj.as_pointer())
    except Exception:
        return id(obj)


def bone_depth(source, bone_name: str) -> int:
    bone = source.data.bones.get(bone_name)
    depth = 0
    seen = set()
    while bone is not None and bone.parent is not None and bone.name not in seen:
        seen.add(bone.name)
        depth += 1
        bone = bone.parent
    return depth


def flat_to_matrix(values) -> Optional[Matrix]:
    try:
        flat = [float(value) for value in values]
    except Exception:
        return None
    if len(flat) != 16:
        return None
    return Matrix((flat[0:4], flat[4:8], flat[8:12], flat[12:16]))


def forward_neutral(source, source_name: str) -> Optional[Matrix]:
    return flat_to_matrix(source.data.get(f"cp77_forward_neutral_{source_name}", ()))


def compile_runtime(source, rig, neutralized_controls=()) -> RigSyncRuntime:
    rig_pose_names = set(rig.pose.bones.keys())
    entries = []
    for source_name, metarig_name in CP77_TO_METARIG.items():
        source_pose_bone = source.pose.bones.get(source_name)
        if source_pose_bone is None:
            continue
        depth = bone_depth(source, source_name)
        if source_name in FORWARD_REST_ONLY_BONES:
            entries.append(ForwardSyncEntry(
                source_name,
                "",
                source_pose_bone,
                Matrix.Identity(4),
                None,
                depth,
                False,
                False,
                True,
            ))
            continue
        target_name = resolve_forward_target(source_name, metarig_name, rig_pose_names)
        if target_name is None:
            continue
        target_bone = rig.data.bones.get(target_name)
        target_pose_bone = rig.pose.bones.get(target_name)
        if target_pose_bone is None:
            continue
        target_rest = (
            target_bone.matrix_local.copy()
            if target_bone is not None
            else target_pose_bone.bone.matrix_local.copy()
        )
        entries.append(ForwardSyncEntry(
            source_name,
            target_name,
            source_pose_bone,
            target_rest,
            forward_neutral(source, source_name),
            depth,
            source_name in FORWARD_LOCATION_BONES,
            source_name in FORWARD_LIMITED_LOCATION_BONES,
            False,
        ))
    entries.sort(key=lambda entry: entry.depth)
    ranges = []
    start = 0
    while start < len(entries):
        end = start + 1
        depth = entries[start].depth
        while end < len(entries) and entries[end].depth == depth:
            end += 1
        ranges.append((start, end))
        start = end
    return RigSyncRuntime(
        source,
        rig,
        tuple(entries),
        tuple(ranges),
        tuple(neutralized_controls),
        source.data,
        rig.data,
    )


def set_runtime(runtime: RigSyncRuntime) -> RigSyncRuntime:
    stale = [key for key, value in _RUNTIMES.items() if value.rig is runtime.rig]
    for key in stale:
        _RUNTIMES.pop(key, None)
    _RUNTIMES[object_key(runtime.source)] = runtime
    return runtime


def get_runtime(source) -> Optional[RigSyncRuntime]:
    return _RUNTIMES.get(object_key(source)) if source is not None else None


def remove_runtime(source) -> Optional[RigSyncRuntime]:
    return _RUNTIMES.pop(object_key(source), None) if source is not None else None


def runtimes() -> tuple[RigSyncRuntime, ...]:
    return tuple(_RUNTIMES.values())


def clear_runtimes() -> None:
    _RUNTIMES.clear()
