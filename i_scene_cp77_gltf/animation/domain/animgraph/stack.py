from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

from ....assetio.values import cname_text
from ....bartmoss.qs_transform import (
    QsTransform,
    compose,
    relative_to,
    translation_only,
    without_translation,
)
from ...model.animgraph.frames import TrackStackScope, TransformStackScope
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, model_transform


@dataclass(frozen=True)
class StackEvaluation:
    names: tuple[str, ...]
    applied: bool = True
    reason: str = ""


def _materialized_flags(
    scope: TransformStackScope | TrackStackScope,
) -> tuple[bool, ...]:
    if len(scope.materialized) == len(scope.names):
        return scope.materialized
    return (True,) * len(scope.names)


def _active_materialized_names(
    scopes: Sequence[TransformStackScope | TrackStackScope],
) -> set[str]:
    return {
        name
        for scope in scopes
        for name, materialized in zip(scope.names, _materialized_flags(scope))
        if materialized
    }


def _shrink_scopes(
    scopes, data: Mapping[str, Any]
) -> tuple[tuple, tuple[str, ...], list[str]]:
    """Remove removeCount names from the innermost scopes outward"""
    remaining = max(0, int(data.get("removeCount", 0) or 0))
    mutable_scopes = list(scopes)
    removed: list[str] = []
    materialized_removed: list[str] = []
    while remaining > 0 and mutable_scopes:
        scope = mutable_scopes.pop()
        flags = _materialized_flags(scope)
        take = min(remaining, len(scope.names))
        removed_slice = scope.names[-take:]
        flags_slice = flags[-take:]
        removed.extend(reversed(removed_slice))
        materialized_removed.extend(
            name
            for name, visible in zip(reversed(removed_slice), reversed(flags_slice))
            if visible
        )
        remaining -= take
        if take < len(scope.names):
            remaining_names = scope.names[:-take]
            remaining_flags = flags[:-take]
            mutable_scopes.append(
                type(scope)(
                    scope.tag,
                    remaining_names,
                    () if all(remaining_flags) else remaining_flags,
                )
            )
    return tuple(mutable_scopes), tuple(reversed(removed)), materialized_removed


def extender_size(node_type: str, node: Mapping[str, Any]) -> int:
    """How many transforms or tracks a stack extender adds (its arrays are padded to this on load)"""
    if node_type == "animAnimNode_StackTracksExtender":
        return len(tuple(node.get("newTracks", ()) or ()))
    return max(
        len(tuple(node.get(name, ()) or ()))
        for name in ("transformInfos", "snapTargetBones", "snapToReferenceValues")
    )


def paired_remove_counts(items: Sequence[tuple[str, bool, str, int]]) -> dict[str, int]:
    """Each shrinker's remove count, from the extender it pairs with"""
    waiting_extenders: list[tuple[str, int]] = []
    waiting_shrinkers: list[tuple[str, str]] = []
    counts: dict[str, int] = {}
    for handle, is_extender, tag, size in items:
        if not tag:
            if not is_extender:
                counts[handle] = 0
            continue
        if is_extender:
            match = next(
                (i for i, (_h, other) in enumerate(waiting_shrinkers) if other == tag),
                None,
            )
            if match is None:
                waiting_extenders.append((tag, size))
            else:
                counts[waiting_shrinkers.pop(match)[0]] = size
        else:
            match = next(
                (
                    i
                    for i, (other, _size) in enumerate(waiting_extenders)
                    if other == tag
                ),
                None,
            )
            if match is None:
                waiting_shrinkers.append((handle, tag))
                counts[handle] = 0
            else:
                counts[handle] = waiting_extenders.pop(match)[1]
    return counts


def _name(value: Any) -> str:
    text = cname_text(value, "")
    return "" if text in {"", "None"} else text


def _at(values: Sequence[Any], index: int, default: Any) -> Any:
    return values[index] if index < len(values) else default


def normalize_transform_extender(node: Mapping[str, Any]) -> dict[str, Any]:
    infos = tuple(node.get("transformInfos", ()) or ())
    snap_methods = tuple(node.get("snapMethods", ()) or ())
    snap_refs = tuple(node.get("snapToReferenceValues", ()) or ())
    snap_targets = tuple(node.get("snapTargetBones", ()) or ())
    offset_refs = tuple(node.get("offsetToReferenceValues", ()) or ())
    offset_spaces = tuple(node.get("offsetSpaceBones", ()) or ())
    offsets = tuple(node.get("offsets", ()) or ())
    entries = []
    # Arrays shorter than the extender size leave the remaining transforms unnamed.
    for index in range(extender_size("animAnimNode_StackTransformsExtender", node)):
        info = _at(infos, index, {})
        info = info if isinstance(info, Mapping) else {}
        entries.append(
            {
                "name": _name(info.get("name")),
                "parent": _name(info.get("parentName")),
                "referenceTransformLs": info.get("referenceTransformLs") or {},
                "snapMethod": str(
                    _at(snap_methods, index, "NoSnapping") or "NoSnapping"
                ),
                "snapToReference": bool(_at(snap_refs, index, False)),
                "snapTargetBone": index_name(
                    _at(snap_targets, index, {}), "animTransformIndex", allow_text=True
                ),
                "offsetToReference": bool(_at(offset_refs, index, False)),
                "offsetSpaceBone": index_name(
                    _at(offset_spaces, index, {}), "animTransformIndex", allow_text=True
                ),
                "offset": _at(offsets, index, {}) or {},
            }
        )
    return {"tag": _name(node.get("tag")), "entries": tuple(entries)}


def normalize_transform_shrinker(node: Mapping[str, Any]) -> dict[str, Any]:
    return {"tag": _name(node.get("tag")), "removeCount": 0}


def normalize_track_extender(node: Mapping[str, Any]) -> dict[str, Any]:
    entries = []
    for item in node.get("newTracks", ()) or ():
        if not isinstance(item, Mapping):
            continue
        entries.append(
            {
                "name": _name(item.get("name")),
                "referenceValue": float(item.get("referenceValue", 0.0) or 0.0),
            }
        )
    return {"tag": _name(node.get("tag")), "entries": tuple(entries)}


def normalize_track_shrinker(node: Mapping[str, Any]) -> dict[str, Any]:
    return {"tag": _name(node.get("tag")), "removeCount": 0}


def extend_transforms(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: MutableMapping[str, str],
    reference_pose_ls: MutableMapping[str, QsTransform],
    scopes: Sequence[TransformStackScope],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> tuple[tuple[TransformStackScope, ...], StackEvaluation]:
    tag = str(data.get("tag", "") or "")
    entries = tuple(data.get("entries", ()) or ())

    names = tuple(str(entry.get("name", "") or "") for entry in entries)
    if any(not name for name in names):
        return tuple(scopes), StackEvaluation(
            (), False, "StackTransformsExtender contains an unnamed transform"
        )
    if len(set(names)) != len(names):
        return tuple(scopes), StackEvaluation(
            (), False, "StackTransformsExtender contains duplicate transform names"
        )
    active_stack_names = _active_materialized_names(scopes)
    occupied_stack = next(
        (name for name in names if name in local_pose and name in active_stack_names),
        "",
    )
    if occupied_stack:
        return tuple(scopes), StackEvaluation(
            (),
            False,
            f"stack transform already exists in active stack: {occupied_stack}",
        )

    # Stack transforms are appended even when their names also exist in the base rig. Transform-index
    # resolution keeps the base-rig transform, so such entries are present but shadowed.
    materialized = tuple(name not in local_pose for name in names)

    available = set(local_pose)
    for entry, name in zip(entries, names):
        parent = str(entry.get("parent", "") or "")
        if not parent or parent not in available:
            return tuple(scopes), StackEvaluation(
                (), False, f"stack transform parent is absent: {parent or '<empty>'}"
            )
        available.add(name)

    # Stack entries extend the rig and reference namespace before their values are sampled. A pose keyed by
    # name cannot hold a base and a stack transform of one name, so a shadowed entry only occupies its slot.
    for entry, name, visible in zip(entries, names, materialized):
        if not visible:
            continue
        parent_map[name] = str(entry.get("parent", "") or "")
        reference_pose_ls[name] = entry["_referenceQs"]
        reference_local = reference_pose_ls[name]
        local_pose[name] = (
            compose(local_pose[parent_map[name]], reference_local)
            if model_space
            else reference_local
        )

    reference_ms_cache: dict[str, QsTransform] = {}
    for entry, name, visible in zip(entries, names, materialized):
        if not visible:
            continue
        parent = parent_map[name]
        current = local_pose[name]
        snap_method = str(entry.get("snapMethod", "NoSnapping") or "NoSnapping")
        source = str(entry.get("snapTargetBone", "") or "")
        if snap_method != "NoSnapping" and source in local_pose:
            try:
                snap_ms = (
                    model_transform(
                        source, reference_pose_ls, parent_map, reference_ms_cache
                    )
                    if bool(entry.get("snapToReference", False))
                    else (
                        frame_model_transform(
                            source, local_pose, parent_map, model_space
                        )
                    )
                )
                snap_local = (
                    snap_ms
                    if model_space
                    else relative_to(
                        model_transform(parent, local_pose, parent_map, {}), snap_ms
                    )
                )
            except (KeyError, ValueError):
                snap_local = None
            if snap_local is not None:
                if snap_method == "WholeTransform":
                    current = snap_local
                elif snap_method == "TranslationOnly":
                    current = QsTransform.from_components(
                        snap_local.translation, current.rotation_xyzw, current.scale
                    )
                elif snap_method == "RotationOnly":
                    current = QsTransform.from_components(
                        current.translation, snap_local.rotation_xyzw, current.scale
                    )
                else:
                    return tuple(scopes), StackEvaluation(
                        names, False, f"unsupported stack snap method: {snap_method}"
                    )
                local_pose[name] = current

        offset_space = str(entry.get("offsetSpaceBone", "") or "")
        if offset_space in local_pose:
            try:
                offset_space_ms = (
                    model_transform(
                        offset_space, reference_pose_ls, parent_map, reference_ms_cache
                    )
                    if bool(entry.get("offsetToReference", False))
                    else (
                        frame_model_transform(
                            offset_space, local_pose, parent_map, model_space
                        )
                    )
                )
                current_ms = frame_model_transform(
                    name, local_pose, parent_map, model_space
                )
            except (KeyError, ValueError):
                continue
            current_offset_space = relative_to(offset_space_ms, current_ms)
            offset = entry["_offsetQs"]
            translation_part = compose(translation_only(offset), current_offset_space)
            rotation_scale_part = compose(
                without_translation(offset), without_translation(current_offset_space)
            )
            combined = QsTransform.from_components(
                translation_part.translation,
                rotation_scale_part.rotation_xyzw,
                rotation_scale_part.scale,
            )
            result_ms = compose(offset_space_ms, combined)
            local_pose[name] = (
                result_ms
                if model_space
                else relative_to(
                    model_transform(parent, local_pose, parent_map, {}), result_ms
                )
            )

    scope_flags = () if all(materialized) else materialized
    return tuple(scopes) + (
        TransformStackScope(tag, names, scope_flags),
    ), StackEvaluation(names)


def shrink_transforms(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: MutableMapping[str, str],
    reference_pose_ls: MutableMapping[str, QsTransform],
    scopes: Sequence[TransformStackScope],
    data: Mapping[str, Any],
) -> tuple[tuple[TransformStackScope, ...], StackEvaluation]:
    remaining_scopes, removed, materialized_removed = _shrink_scopes(scopes, data)
    for name in materialized_removed:
        local_pose.pop(name, None)
        parent_map.pop(name, None)
        reference_pose_ls.pop(name, None)
    return remaining_scopes, StackEvaluation(removed)


def extend_tracks(
    tracks: MutableMapping[str, float],
    reference_tracks: MutableMapping[str, float],
    scopes: Sequence[TrackStackScope],
    data: Mapping[str, Any],
) -> tuple[tuple[TrackStackScope, ...], StackEvaluation]:
    tag = str(data.get("tag", "") or "")
    entries = tuple(data.get("entries", ()) or ())
    names = tuple(str(entry.get("name", "") or "") for entry in entries)
    if any(not name for name in names):
        return tuple(scopes), StackEvaluation(
            (), False, "StackTracksExtender contains an unnamed track"
        )
    if len(set(names)) != len(names):
        return tuple(scopes), StackEvaluation(
            (), False, "StackTracksExtender contains duplicate track names"
        )
    active_stack_names = _active_materialized_names(scopes)
    occupied_stack = next(
        (name for name in names if name in tracks and name in active_stack_names), ""
    )
    if occupied_stack:
        return tuple(scopes), StackEvaluation(
            (), False, f"stack track already exists in active stack: {occupied_stack}"
        )
    materialized = tuple(name not in tracks for name in names)
    for entry, name, visible in zip(entries, names, materialized):
        if not visible:
            continue
        value = float(entry.get("referenceValue", 0.0) or 0.0)
        reference_tracks[name] = value
        tracks[name] = value
    scope_flags = () if all(materialized) else materialized
    return tuple(scopes) + (TrackStackScope(tag, names, scope_flags),), StackEvaluation(
        names
    )


def shrink_tracks(
    tracks: MutableMapping[str, float],
    reference_tracks: MutableMapping[str, float],
    scopes: Sequence[TrackStackScope],
    data: Mapping[str, Any],
) -> tuple[tuple[TrackStackScope, ...], StackEvaluation]:
    remaining_scopes, removed, materialized_removed = _shrink_scopes(scopes, data)
    for name in materialized_removed:
        tracks.pop(name, None)
        reference_tracks.pop(name, None)
    return remaining_scopes, StackEvaluation(removed)
