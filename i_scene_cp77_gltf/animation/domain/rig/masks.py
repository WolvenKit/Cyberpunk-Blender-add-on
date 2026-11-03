from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping, Sequence

RIG_PART_MASKS_KEY = "cp77_rig_part_masks_json"
RIG_PART_ROTATION_MS_KEY = "cp77_rig_part_rotation_ms_json"


def _cname(value) -> str:
    if isinstance(value, Mapping):
        value = value.get("$value")
    text = str(value or "")
    return "" if text == "None" else text


def engine_part_mask(
    part: Mapping, bone_names: Sequence[str], parent_indices: Sequence[int]
) -> dict[int, float]:
    """A rig part's bone weights, rebuilt from its serialized definition"""
    index_of = {str(name): i for i, name in enumerate(bone_names)}
    children: list[list[int]] = [[] for _ in bone_names]
    for child, parent in enumerate(parent_indices):
        try:
            parent = int(parent)
        except (TypeError, ValueError):
            continue
        if 0 <= parent < len(children) and parent != child:
            children[parent].append(child)
    mask: dict[int, float] = {}

    def fill_descendants(start: int, weight: float) -> None:
        stack = [start]
        while stack:
            current = stack.pop()
            if current not in mask:
                mask[current] = weight
            stack.extend(reversed(children[current]))

    def fill_tree(tree: Mapping) -> None:
        root = index_of.get(_cname(tree.get("rootBone")))
        if root is None:
            return
        weight = float(
            tree.get("weight", 1.0) if tree.get("weight") is not None else 1.0
        )
        for subtree in tree.get("subtreesToChange", ()) or ():
            if isinstance(subtree, Mapping):
                fill_tree(subtree)
        fill_descendants(root, weight)

    for single in part.get("singleBones", ()) or ():
        if isinstance(single, Mapping):
            index = index_of.get(_cname(single.get("bone")))
            if index is not None and index not in mask:
                mask[index] = float(
                    single.get("weight", 1.0)
                    if single.get("weight") is not None
                    else 1.0
                )
    for tree in part.get("treeBones", ()) or ():
        if isinstance(tree, Mapping):
            fill_tree(tree)
    return dict(sorted(mask.items()))


def rig_part_rotation_ms_by_name(
    parts, bone_names: Sequence[str]
) -> dict[str, list[str]]:
    """Bones each part blends with model-space rotation, in rig order"""
    index_of = {str(name): i for i, name in enumerate(bone_names)}
    result: dict[str, list[str]] = {}
    for part in parts or ():
        if not isinstance(part, Mapping):
            continue
        part_name = _cname(part.get("name"))
        if not part_name or part_name in result:
            continue
        indices = {
            index_of[_cname(name)]
            for name in part.get("bonesWithRotationInModelSpace", ()) or ()
            if _cname(name) in index_of
        }
        result[part_name] = [str(bone_names[i]) for i in sorted(indices)]
    return result


def remap_rig_part_indices(source_part: Mapping, bone_mapping: Sequence[int]) -> dict:
    part = copy.deepcopy(dict(source_part))
    remapped_mask = []
    for entry in part.get("mask", ()) or ():
        if not isinstance(entry, Mapping):
            continue
        try:
            source_index = int(entry.get("index", -1))
        except (TypeError, ValueError):
            continue
        if not 0 <= source_index < len(bone_mapping):
            continue
        target_index = int(bone_mapping[source_index])
        if target_index < 0:
            continue
        remapped_entry = dict(entry)
        remapped_entry["index"] = target_index
        remapped_mask.append(remapped_entry)
    part["mask"] = remapped_mask

    remapped_rot_ms = []
    for source_index in part.get("maskRotMS", ()) or ():
        try:
            source_index = int(source_index)
        except (TypeError, ValueError):
            continue
        if not 0 <= source_index < len(bone_mapping):
            continue
        target_index = int(bone_mapping[source_index])
        if target_index >= 0:
            remapped_rot_ms.append(target_index)
    part["maskRotMS"] = remapped_rot_ms
    return part


def rig_part_masks_by_bone_name(
    parts, bone_names: Sequence[str], parent_indices: Sequence[int] | None = None
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for part in parts or ():
        if not isinstance(part, Mapping):
            continue
        name_value = part.get("name")
        if isinstance(name_value, Mapping):
            part_name = name_value.get("$value")
        else:
            part_name = name_value
        if not isinstance(part_name, str) or not part_name or part_name in result:
            continue
        weights: dict[str, float] = {}
        for entry in part.get("mask", ()) or ():
            if not isinstance(entry, Mapping):
                continue
            try:
                index = int(entry.get("index", -1))
                weight = float(entry.get("weight", 0.0))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(bone_names) and math.isfinite(weight):
                weights[str(bone_names[index])] = weight
        if not weights and parent_indices is not None:
            # Cooked rigs do not serialize the mask; rebuild it from the part definition.
            weights = {
                str(bone_names[index]): weight
                for index, weight in engine_part_mask(
                    part, bone_names, parent_indices
                ).items()
                if math.isfinite(weight)
            }
        result[part_name] = weights
    return result


def encode_rig_part_rotation_ms(rotation_ms: Mapping[str, Sequence[str]]) -> str:
    """The stored text of each part's model-space rotation bones"""
    return json.dumps(
        {
            str(name): [str(bone) for bone in bones]
            for name, bones in rotation_ms.items()
            if name
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_rig_part_rotation_ms(raw) -> dict[str, list[str]]:
    if not raw:
        return {}
    try:
        payload = raw if isinstance(raw, Mapping) else json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return {
        str(name): [str(bone) for bone in bones]
        for name, bones in payload.items()
        if isinstance(bones, (list, tuple))
    }


def encode_rig_part_masks(masks: Mapping[str, Mapping[str, float]]) -> str:
    """The stored text of the part masks"""
    payload = {}
    for part_name, weights in masks.items():
        if not part_name:
            continue
        stored_weights = {}
        for bone_name, weight in weights.items():
            try:
                value = float(weight)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                stored_weights[str(bone_name)] = value
        payload[str(part_name)] = stored_weights
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_rig_part_masks(raw) -> dict[str, dict[str, float]]:
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        payload = raw
    else:
        try:
            payload = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    if not isinstance(payload, Mapping):
        return {}

    result: dict[str, dict[str, float]] = {}
    for part_name, values in payload.items():
        if not isinstance(values, Mapping):
            continue
        weights: dict[str, float] = {}
        for bone_name, weight in values.items():
            try:
                value = float(weight)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                weights[str(bone_name)] = value
        result[str(part_name)] = weights
    return result
