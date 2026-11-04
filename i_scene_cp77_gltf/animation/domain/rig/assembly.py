import json
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from ....assetio.cache import store_bounded
from ....assetio.paths import local_path_key
from ....assetio.transform_values import parse_wkit_trs
from ....assetio.values import json_array, json_object
from ....bartmoss.hierarchy import parent_first_order
from ...model.rig.data import RigData
from .masks import remap_rig_part_indices
from .naming import merged_bone_name

METARIG_PART_LEDGER_KEY = "cp77_metarig_part_ledger"
METARIG_PART_OVERRIDES_KEY = "cp77_metarig_part_overrides"
METARIG_USER_ADDITIONS_KEY = "cp77_metarig_user_additions"
METARIG_REMOVED_PARTS_KEY = "cp77_metarig_removed_parts"
METARIG_REMOVED_SLOTS_KEY = "cp77_metarig_removed_slots"


@dataclass(frozen=True, slots=True)
class BonePlan:
    names: tuple[str, ...]
    parents: tuple[int, ...]
    order: tuple[int, ...]
    added: frozenset[str]
    removed: frozenset[str]


def plan_bones(names, parents, existing, owned):
    names = tuple(str(name) for name in names)
    parents = tuple(int(index) for index in parents)
    if len(names) != len(parents) or not names:
        raise ValueError("A rig needs one parent index per bone")
    if any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Rig bone names must be nonempty and unique")
    if any(index < -1 or index >= len(names) for index in parents):
        raise ValueError("Rig parent index is outside the bone table")
    order = parent_first_order(parents)
    existing, owned, wanted = set(existing), set(owned), set(names)
    collisions = (wanted & existing) - owned
    if collisions:
        raise ValueError(
            "Rig part conflicts with user bones: " + ", ".join(sorted(collisions)[:8])
        )
    return BonePlan(
        names,
        parents,
        order,
        frozenset(wanted - existing),
        frozenset((owned & existing) - wanted),
    )


def normalized_part_path(path) -> str:
    return os.path.normpath(str(path or "")) if path else ""


def part_path_key(path) -> str:
    value = normalized_part_path(path)
    return local_path_key(value) if value else ""


def metarig_ledger_signature(ledger) -> str:
    return json.dumps(ledger, separators=(",", ":"), sort_keys=True)


def metarig_imported_sources(ledger) -> tuple[str, ...]:
    """Source rig paths of the imported parts, in ledger order"""
    return tuple(
        entry["source_path"]
        for entry in ledger
        if not entry["user_addition"] and entry["source_path"]
    )


def metarig_part_role(path, index, *, user_addition=False) -> str:
    if index == 0 and not user_addition:
        return "Base"
    name = os.path.basename(path).casefold()
    if "deformation" in name:
        return "Deformation"
    if "dangle" in name:
        return "Dangle"
    if user_addition:
        return "Added"
    return f"Part {index}"


@dataclass(frozen=True, slots=True)
class MetaRigUserEdits:
    """The user's MetaRig part edits as stored"""

    overrides: dict
    additions: list
    removed_parts: list
    removed_slots: list

    @classmethod
    def decode(cls, overrides, additions, removed_parts, removed_slots):
        return cls(
            json_object(overrides),
            json_array(additions),
            json_array(removed_parts),
            json_array(removed_slots),
        )

    def encoded(self) -> dict[str, str]:
        return {
            METARIG_PART_OVERRIDES_KEY: json.dumps(
                self.overrides, separators=(",", ":")
            ),
            METARIG_USER_ADDITIONS_KEY: json.dumps(
                self.additions, separators=(",", ":")
            ),
            METARIG_REMOVED_PARTS_KEY: json.dumps(
                self.removed_parts, separators=(",", ":")
            ),
            METARIG_REMOVED_SLOTS_KEY: json.dumps(
                self.removed_slots, separators=(",", ":")
            ),
        }


def resolve_metarig_part_ledger(
    source_paths, edits: MetaRigUserEdits
) -> tuple[dict, ...]:
    """The active parts"""
    source_paths = tuple(str(path or "") for path in source_paths if path)
    overrides = {
        local_path_key(str(key)): str(value)
        for key, value in edits.overrides.items()
        if value
    }
    removed_parts = {
        local_path_key(str(value)) for value in edits.removed_parts if value
    }
    removed_slots = {
        int(value)
        for value in edits.removed_slots
        if isinstance(value, (int, str)) and str(value).lstrip("-").isdigit()
    }

    ledger = []
    for index, source_path in enumerate(source_paths):
        source_key = local_path_key(source_path)
        if index != 0 and (source_key in removed_parts or index in removed_slots):
            continue
        replacement = overrides.get(source_key) or overrides.get(str(index)) or ""
        ledger.append(
            {
                "source_path": source_path,
                "path": replacement or source_path,
                "user_addition": False,
            }
        )

    seen = {local_path_key(entry["path"]) for entry in ledger}
    for addition in edits.additions:
        path = str(addition or "")
        key = local_path_key(path)
        if not path or key in seen:
            continue
        ledger.append({"source_path": "", "path": path, "user_addition": True})
        seen.add(key)
    return tuple(ledger)


def decode_metarig_part_ledger(payload) -> tuple[dict, ...]:
    """The stored ledger's valid entries, with paths normalised and the user-addition flag resolved"""
    entries = []
    for value in json_array(payload):
        if not isinstance(value, dict):
            continue
        active_path = normalized_part_path(value.get("path"))
        if not active_path:
            continue
        source_path = normalized_part_path(value.get("source_path"))
        user_addition = bool(value.get("user_addition", not source_path))
        entries.append(
            {
                "source_path": "" if user_addition else (source_path or active_path),
                "path": active_path,
                "user_addition": user_addition,
            }
        )
    return tuple(entries)


def apply_metarig_user_edit(
    edits: MetaRigUserEdits,
    operation,
    *,
    source_path="",
    old_path="",
    new_path="",
    user_addition=False,
) -> MetaRigUserEdits:
    """The edits after a user ADD, REPLACE or REMOVE, so resolve_metarig_part_ledger reproduces it"""
    overrides = dict(edits.overrides)
    additions = list(edits.additions)
    removed_parts = {part_path_key(value) for value in edits.removed_parts if value}
    source_key = part_path_key(source_path)
    old_key = part_path_key(old_path)
    addition_index = next(
        (
            position
            for position, value in enumerate(additions)
            if part_path_key(value) == old_key
        ),
        None,
    )
    if operation == "ADD":
        if part_path_key(new_path) not in {part_path_key(value) for value in additions}:
            additions.append(normalized_part_path(new_path))
    elif operation == "REPLACE":
        if user_addition or addition_index is not None:
            if addition_index is None:
                additions.append(normalized_part_path(new_path))
            else:
                additions[addition_index] = normalized_part_path(new_path)
        elif source_key:
            overrides[source_key] = normalized_part_path(new_path)
            removed_parts.discard(source_key)
    elif operation == "REMOVE":
        if user_addition or addition_index is not None:
            if addition_index is not None:
                additions.pop(addition_index)
        elif source_key:
            overrides.pop(source_key, None)
            removed_parts.add(source_key)
    return MetaRigUserEdits(overrides, additions, sorted(removed_parts), [])


_MERGED_RIG_DATA_CACHE = {}


def _identity_trs() -> dict:
    return {
        "Translation": {"X": 0.0, "Y": 0.0, "Z": 0.0},
        "Rotation": {"i": 0.0, "j": 0.0, "k": 0.0, "r": 1.0},
        "Scale": {"X": 1.0, "Y": 1.0, "Z": 1.0},
    }


def _rig_apose_ls(rig_data) -> list[dict]:
    # Use the A-pose only when it covers the complete bone set.
    if len(rig_data.apose_ls) == len(rig_data.bone_names):
        return rig_data.apose_ls
    return rig_data.bone_transforms


def _precise_meta_pose_ls(rig_datas, meta_bone_names: list[str]):
    """Resolve the local A-pose transform for every merged-rig bone"""
    first_transform_by_name = {}
    for rig_data in rig_datas:
        source_ls = _rig_apose_ls(rig_data)
        source_count = len(source_ls)
        seen_in_rig = set()
        for source_index, raw_name in enumerate(rig_data.bone_names):
            if source_index >= source_count:
                break
            name = merged_bone_name(raw_name)
            if not name or name in seen_in_rig:
                continue
            seen_in_rig.add(name)
            transform = source_ls[source_index]
            if transform is not None and name not in first_transform_by_name:
                first_transform_by_name[name] = transform
    return [
        transform
        if (transform := first_transform_by_name.get(name)) is not None
        else _identity_trs()
        for name in meta_bone_names
    ]


def _merge_rig_data_into_state(
    rig_data,
    rig_order,
    names,
    index_by_meta_name,
    transforms,
    parents,
    track_names,
    track_index_by_name,
    reference_tracks,
    parts,
    bone_sources,
    rig_bone_mappings,
    rig_track_mappings,
):
    """Merge one rig's bones and tracks into the shared state"""
    source_ls = _rig_apose_ls(rig_data)
    source_names = rig_data.bone_names
    source_meta_names = [merged_bone_name(name) for name in source_names]
    parent_indices = (
        rig_data.parent_indices.tolist()
        if hasattr(rig_data.parent_indices, "tolist")
        else list(rig_data.parent_indices)
    )

    bone_mapping = [-1] * len(source_names)
    for bone_index, raw_bone_name in enumerate(source_names):
        bone_name = source_meta_names[bone_index]
        existing_index = index_by_meta_name.get(bone_name)
        if existing_index is not None:
            bone_mapping[bone_index] = existing_index
            continue

        source_parent = (
            int(parent_indices[bone_index]) if bone_index < len(parent_indices) else -1
        )
        if 0 <= source_parent < len(source_names):
            parent_name = source_meta_names[source_parent]
            merged_parent = index_by_meta_name.get(parent_name, -1)
        else:
            parent_name = ""
            merged_parent = -1

        merged_index = len(names)
        index_by_meta_name[bone_name] = merged_index
        names.append(bone_name)
        transforms.append(
            source_ls[bone_index]
            if bone_index < len(source_ls) and source_ls[bone_index]
            else _identity_trs()
        )
        parents.append(merged_parent)
        bone_mapping[bone_index] = merged_index
        bone_sources[bone_name] = {
            "rig_order": rig_order,
            "rig_name": rig_data.rig_name,
            "source_index": bone_index,
            "source_name": raw_bone_name,
            "meta_name": bone_name,
            "parent_meta_name": parent_name,
        }

    # The part's meta mapping omits source bone zero while the MetaRig retains it.
    # Preserve the full source-to-meta map here and expose the
    # exact runtime mapping separately.
    rig_bone_mappings.append(
        {
            "rig_name": rig_data.rig_name,
            "all": bone_mapping,
            "runtime": [
                (source_index, target_index)
                for source_index, target_index in enumerate(bone_mapping)
                if source_index != 0 and target_index >= 0
            ],
        }
    )

    track_mapping = []
    for track_index, track_name in enumerate(rig_data.track_names):
        existing_index = track_index_by_name.get(track_name)
        if existing_index is None:
            existing_index = len(track_names)
            track_index_by_name[track_name] = existing_index
            track_names.append(track_name)
            reference_tracks.append(
                rig_data.reference_tracks[track_index]
                if track_index < len(rig_data.reference_tracks)
                else 0.0
            )
        track_mapping.append((track_index, existing_index))
    rig_track_mappings.append({"rig_name": rig_data.rig_name, "runtime": track_mapping})

    if rig_data.parts:
        for source_part in rig_data.parts:
            if isinstance(source_part, dict):
                parts.append(remap_rig_part_indices(source_part, bone_mapping))


def merge_rig_datas(rig_datas, merged_name: str, return_metadata: bool = False):
    """Build the merged rig topology and its local A-pose"""
    if not rig_datas:
        return (None, {}) if return_metadata else None
    rig_datas = list(rig_datas)
    source_ids = tuple(id(rig_data) for rig_data in rig_datas)
    cache_key = (merged_name, source_ids)
    cached = _MERGED_RIG_DATA_CACHE.get(cache_key)
    if cached is not None:
        cached_sources, cached_merged, cached_metadata = cached
        if len(cached_sources) == len(rig_datas) and all(
            a is b for a, b in zip(cached_sources, rig_datas)
        ):
            return (
                (cached_merged, cached_metadata) if return_metadata else cached_merged
            )

    names: list[str] = []
    index_by_meta_name: dict[str, int] = {}
    transforms: list[dict] = []
    parents: list[int] = []
    track_names: list[str] = []
    track_index_by_name: dict[str, int] = {}
    reference_tracks: list[Any] = []
    parts: list[Any] = []
    bone_sources: dict[str, dict] = {}
    rig_bone_mappings: list[dict] = []
    rig_track_mappings: list[dict] = []
    tags: list[str] = []
    seen_tags: set[str] = set()

    base_rig = rig_datas[0]
    for rig_data in rig_datas:
        for tag in getattr(rig_data, "tags", ()) or ():
            tag = str(tag or "")
            if tag and tag != "None" and tag not in seen_tags:
                seen_tags.add(tag)
                tags.append(tag)
    for rig_order, rig_data in enumerate(rig_datas):
        _merge_rig_data_into_state(
            rig_data,
            rig_order,
            names,
            index_by_meta_name,
            transforms,
            parents,
            track_names,
            track_index_by_name,
            reference_tracks,
            parts,
            bone_sources,
            rig_bone_mappings,
            rig_track_mappings,
        )

    for index, name in enumerate(names):
        parent_name = bone_sources[name]["parent_meta_name"]
        parents[index] = index_by_meta_name.get(parent_name, -1)
    plan_bones(names, parents, (), ())

    # Resolve local transforms after the first-wins topology and mappings are complete.
    transforms = _precise_meta_pose_ls(rig_datas, names)

    q, t, s = parse_wkit_trs(transforms, len(names), quaternion_order="xyzw")
    merged = RigData(
        num_bones=len(names),
        parent_indices=np.asarray(parents, dtype=np.int16),
        bone_names=names,
        track_names=track_names,
        ls_q=q,
        ls_t=t,
        ls_s=s,
        rig_name=merged_name,
        disable_connect=True,
        tags=tags,
        apose_ls=list(transforms),
        bone_transforms=list(transforms),
        parts=parts,
        rig_extra_tracks=list(base_rig.rig_extra_tracks),
        reference_tracks=reference_tracks,
        cooking_platform=base_rig.cooking_platform,
        distance_category_to_lod_map=list(base_rig.distance_category_to_lod_map),
        ik_setups=list(base_rig.ik_setups),
        level_of_detail_start_indices=list(base_rig.level_of_detail_start_indices),
        ragdoll_desc=list(base_rig.ragdoll_desc),
        ragdoll_names=list(base_rig.ragdoll_names),
    )
    metadata = {
        "bone_sources": bone_sources,
        "bone_index_by_name": dict(index_by_meta_name),
        "rig_bone_mappings": rig_bone_mappings,
        "rig_track_mappings": rig_track_mappings,
        "rig_order": [rig_data.rig_name for rig_data in rig_datas],
    }
    store_bounded(
        _MERGED_RIG_DATA_CACHE,
        cache_key,
        (tuple(rig_datas), merged, metadata),
        limit=32,
    )
    return (merged, metadata) if return_metadata else merged
