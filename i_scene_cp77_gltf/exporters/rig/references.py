from __future__ import annotations

import copy
from dataclasses import dataclass

from ...assetio.values import cname_entry, cname_text

_IK_BONE_KEYS = ("firstBone", "secondBone", "endBone")
_RAGDOLL_SIDES = ("Parent", "Child")


@dataclass(frozen=True)
class _BoneMap:
    export_index: dict[int, int]
    export_names: tuple[str, ...]
    renamed: dict[str, str]
    deleted: frozenset[str]
    children: dict[str, tuple[str, ...]]
    parents: dict[str, str]

    def name(self, source_name: str) -> str | None:
        if source_name in self.deleted:
            return None
        return self.renamed.get(source_name, source_name)


def _bone_map(source_names, source_parents, export_names, source_indices) -> _BoneMap:
    export_index = {
        source_index: export_index
        for export_index, source_index in enumerate(source_indices)
        if source_index is not None
    }
    children: dict[str, list[str]] = {}
    parents = {}
    for index, name in enumerate(source_names):
        parent = source_parents[index] if index < len(source_parents) else -1
        if isinstance(parent, int) and 0 <= parent < len(source_names):
            children.setdefault(source_names[parent], []).append(name)
            parents[name] = source_names[parent]
    return _BoneMap(
        export_index=export_index,
        export_names=tuple(export_names),
        renamed={
            source_names[source_index]: export_names[export_index]
            for source_index, export_index in export_index.items()
        },
        deleted=frozenset(
            name for index, name in enumerate(source_names) if index not in export_index
        ),
        children={name: tuple(values) for name, values in children.items()},
        parents=parents,
    )


def _remap_ik_setups(root: dict, bones: _BoneMap, dropped: list[str]) -> None:
    setups = root.get("ikSetups")
    if not isinstance(setups, list):
        return
    kept = []
    for setup in setups:
        data = setup.get("Data") if isinstance(setup, dict) else None
        if not isinstance(data, dict):
            kept.append(setup)
            continue
        indices = {
            key: bones.export_index.get(data[key + "Idx"])
            for key in _IK_BONE_KEYS
            if isinstance(data.get(key + "Idx"), int)
        }
        if any(index is None for index in indices.values()):
            dropped.append(f"IK setup '{cname_text(data.get('name'))}'")
            continue
        for key, index in indices.items():
            data[key + "Idx"] = index
            if isinstance(data.get(key), dict):
                data[key]["$value"] = bones.export_names[index]
        kept.append(setup)
    root["ikSetups"] = kept


def _ragdoll_body_kept(description, bones: _BoneMap) -> bool:
    for side in _RAGDOLL_SIDES:
        index = description.get(f"{side}AnimIndex")
        if isinstance(index, int) and index >= 0 and index not in bones.export_index:
            return False
    return True


def _surviving_parent_body(body: int, parents: list, kept: list) -> int:
    parent = parents[body]
    for _step in range(len(parents)):
        if not isinstance(parent, int) or parent < 0 or parent >= len(parents):
            return -1
        if kept[parent]:
            return parent
        parent = parents[parent]
    return -1


def _remap_ragdoll(root: dict, bones: _BoneMap, dropped: list[str]) -> None:
    bodies = root.get("ragdollDesc")
    if not isinstance(bodies, list) or not bodies:
        return
    names = root.get("ragdollNames")
    names = names if isinstance(names, list) else []
    kept = [_ragdoll_body_kept(description, bones) for description in bodies]
    parents = [description.get("ParentBodyIndex") for description in bodies]
    new_index = {}
    for body, keep in enumerate(kept):
        if keep:
            new_index[body] = len(new_index)
    kept_bodies, kept_names = [], []
    for body, description in enumerate(bodies):
        pair = names[body] if body < len(names) else None
        if not kept[body]:
            dropped.append(f"ragdoll body {body}")
            continue
        for side in _RAGDOLL_SIDES:
            index = description.get(f"{side}AnimIndex")
            if not isinstance(index, int) or index < 0:
                continue
            exported = bones.export_index[index]
            description[f"{side}AnimIndex"] = exported
            if isinstance(pair, dict) and isinstance(pair.get(f"{side}AnimName"), dict):
                pair[f"{side}AnimName"]["$value"] = bones.export_names[exported]
        if isinstance(parents[body], int):
            parent = _surviving_parent_body(body, parents, kept)
            description["ParentBodyIndex"] = new_index[parent] if parent >= 0 else -1
        kept_bodies.append(description)
        if pair is not None:
            kept_names.append(pair)
    root["ragdollDesc"] = kept_bodies
    if names:
        root["ragdollNames"] = kept_names


def _surviving_tops(name: str, bones: _BoneMap) -> list[str]:
    tops = []
    pending = list(reversed(bones.children.get(name, ())))
    while pending:
        child = pending.pop()
        if bones.name(child) is None:
            pending.extend(reversed(bones.children.get(child, ())))
        else:
            tops.append(child)
    return tops


def _descends_from(name: str, ancestor: str, bones: _BoneMap) -> bool:
    current = bones.parents.get(name)
    for _step in range(len(bones.parents) + 1):
        if current is None:
            return False
        if current == ancestor:
            return True
        current = bones.parents.get(current)
    return False


def _remap_trees(trees, bones: _BoneMap) -> list[tuple[str, dict]]:
    result = []
    for tree in trees if isinstance(trees, list) else ():
        if not isinstance(tree, dict):
            continue
        source = cname_text(tree.get("rootBone"))
        nested = _remap_trees(tree.get("subtreesToChange"), bones)
        renamed = bones.name(source)
        if renamed is not None:
            tree["rootBone"] = cname_entry(renamed, tree.get("rootBone"))
            tree["subtreesToChange"] = [subtree for _name, subtree in nested]
            result.append((source, tree))
            continue
        replacements = []
        for child in _surviving_tops(source, bones):
            replacement = copy.deepcopy(tree)
            replacement["rootBone"] = cname_entry(
                bones.name(child), tree.get("rootBone")
            )
            replacement["subtreesToChange"] = []
            replacements.append((child, replacement))
        for nested_source, subtree in nested:
            owner = next(
                (
                    replacement
                    for child, replacement in replacements
                    if _descends_from(nested_source, child, bones)
                ),
                None,
            )
            if owner is None:
                result.append((nested_source, subtree))
            else:
                owner["subtreesToChange"].append(subtree)
        result.extend(replacements)
    return result


def _renamed_entries(entries, bones: _BoneMap, key: str | None = None) -> list:
    kept = []
    for entry in entries:
        value = entry.get(key) if key and isinstance(entry, dict) else entry
        renamed = bones.name(cname_text(value)) if isinstance(value, dict) else None
        if isinstance(value, dict) and renamed is None:
            continue
        if isinstance(value, dict):
            value["$value"] = renamed
        kept.append(entry)
    return kept


def _remapped_indices(values, bones: _BoneMap, key: str | None = None) -> list:
    kept = []
    for entry in values:
        index = entry.get(key) if key and isinstance(entry, dict) else entry
        if not isinstance(index, int):
            kept.append(entry)
            continue
        exported = bones.export_index.get(index)
        if exported is None:
            continue
        if key:
            entry[key] = exported
            kept.append(entry)
        else:
            kept.append(exported)
    return kept


def _remap_part(part: dict, bones: _BoneMap) -> None:
    if isinstance(part.get("singleBones"), list):
        part["singleBones"] = _renamed_entries(part["singleBones"], bones, "bone")
    if isinstance(part.get("treeBones"), list):
        part["treeBones"] = [
            tree for _name, tree in _remap_trees(part["treeBones"], bones)
        ]
    if isinstance(part.get("bonesWithRotationInModelSpace"), list):
        part["bonesWithRotationInModelSpace"] = _renamed_entries(
            part["bonesWithRotationInModelSpace"], bones
        )
    if isinstance(part.get("mask"), list):
        part["mask"] = _remapped_indices(part["mask"], bones, "index")
    if isinstance(part.get("maskRotMS"), list):
        part["maskRotMS"] = _remapped_indices(part["maskRotMS"], bones)


def _remap_animated_flags(root: dict, source_indices) -> None:
    flags = root.get("areBonesAnimated")
    if not isinstance(flags, list) or not flags:
        return
    added = True if isinstance(flags[0], bool) else 1
    root["areBonesAnimated"] = [
        flags[index] if index is not None and index < len(flags) else added
        for index in source_indices
    ]


def _remap_trajectory(root: dict, bones: _BoneMap) -> None:
    value = root.get("trajectoryBoneName")
    if isinstance(value, dict):
        renamed = bones.name(cname_text(value))
        value["$value"] = renamed if renamed is not None else "None"


def _remap_lods(root: dict, lod_ranks) -> None:
    # Each LOD evaluates the first N bones: it keeps the source bones it had and gains the new bones ranked inside it.
    counts = root.get("levelOfDetailStartIndices")
    if isinstance(counts, list) and counts:
        root["levelOfDetailStartIndices"] = [
            sum(1 for rank in lod_ranks if rank is not None and rank < int(count))
            for count in counts
        ]


def remap_bone_references(
    root: dict, source_names, source_parents, export_names, source_indices, lod_ranks
) -> list[str]:
    bones = _bone_map(source_names, source_parents, export_names, source_indices)
    dropped: list[str] = []
    _remap_ik_setups(root, bones, dropped)
    _remap_ragdoll(root, bones, dropped)
    for part in root.get("parts") or ():
        if isinstance(part, dict):
            _remap_part(part, bones)
    _remap_animated_flags(root, source_indices)
    _remap_trajectory(root, bones)
    _remap_lods(root, lod_ranks)
    return dropped
