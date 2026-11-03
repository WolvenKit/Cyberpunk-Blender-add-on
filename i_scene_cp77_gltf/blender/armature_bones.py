from __future__ import annotations

from ..animation.domain.rig.naming import bone_name_candidates
from ..redSpace.contracts import (
    RIG_SPACE_CONTRACT_CURRENT,
    SUPPORTED_RIG_SPACE_CONTRACTS,
)

READ_RIG_REQUIRED_DATA_KEYS = (
    "boneNames",
    "boneParentIndexes",
    "cp77_source_rig_file",
)


def armature_bone_names(obj) -> tuple[str, ...]:
    """Return logical names resolvable against the armature's live pose"""
    pose = getattr(obj, "pose", None)
    bones = getattr(pose, "bones", None) if pose is not None else None
    if bones is None:
        data = getattr(obj, "data", None)
        bones = getattr(data, "bones", None) if data is not None else None
    if bones is None:
        return ()

    result = []
    seen = set()
    for bone in bones:
        for candidate in bone_name_candidates(getattr(bone, "name", "")):
            if candidate and candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
    return tuple(result)


def armature_bone_parent_map(obj) -> dict[str, str]:
    """Return live hierarchy names, including the supported plug/slot aliases"""
    pose = getattr(obj, "pose", None)
    bones = getattr(pose, "bones", None) if pose is not None else None
    if bones is None:
        data = getattr(obj, "data", None)
        bones = getattr(data, "bones", None) if data is not None else None
    if bones is None:
        return {}

    result = {}
    for bone in bones:
        names = tuple(bone_name_candidates(getattr(bone, "name", "")))
        parent = getattr(bone, "parent", None)
        parent_names = (
            tuple(bone_name_candidates(getattr(parent, "name", "")))
            if parent is not None
            else ()
        )
        for index, name in enumerate(names):
            result[name] = (
                parent_names[min(index, len(parent_names) - 1)] if parent_names else ""
            )
    return result


def is_read_rig_armature(obj) -> bool:
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return False
    data = getattr(obj, "data", None)
    return data is not None and all(
        data.get(key) is not None for key in READ_RIG_REQUIRED_DATA_KEYS
    )


def rig_space_contract(armature):
    data = getattr(armature, "data", None)
    if data is None:
        return RIG_SPACE_CONTRACT_CURRENT
    stored = data.get("cp77_rig_space_contract")
    if stored in SUPPORTED_RIG_SPACE_CONTRACTS:
        return stored
    return RIG_SPACE_CONTRACT_CURRENT


def resolve_pose_bone(obj, name: str):
    pose = getattr(obj, "pose", None)
    if pose is None:
        return None
    for candidate in bone_name_candidates(name):
        bone = pose.bones.get(candidate)
        if bone is not None:
            return bone
    return None


def resolve_data_bone(obj, name: str):
    data = getattr(obj, "data", None)
    bones = getattr(data, "bones", None) if data is not None else None
    if bones is None:
        return None
    for candidate in bone_name_candidates(name):
        bone = bones.get(candidate)
        if bone is not None:
            return bone
    return None


def resolve_bone_name(obj, name: str) -> str:
    bone = resolve_pose_bone(obj, name)
    if bone is None:
        bone = resolve_data_bone(obj, name)
    return bone.name if bone is not None else ""


def bone_by_aliases(obj, aliases) -> str:
    """The armature bone named by the first matching alias, or "" when none matches"""
    if obj is None or getattr(obj, "type", "") != "ARMATURE":
        return ""
    bones = obj.data.bones
    for alias in aliases:
        if bones.get(alias) is not None:
            return alias
    names = {bone.name.casefold(): bone.name for bone in bones}
    for alias in aliases:
        match = names.get(alias.casefold())
        if match:
            return match
    return ""


def bone_names_equivalent(obj, left, right) -> bool:
    left_name = resolve_bone_name(obj, left)
    right_name = resolve_bone_name(obj, right)
    return bool(left_name and right_name and left_name == right_name)


def with_ancestor_bones(armature, names) -> set[str]:
    """names plus the name of every ancestor of the pose bones they name"""
    result = set(names)
    pose_bones = getattr(getattr(armature, "pose", None), "bones", None)
    if pose_bones is None:
        return result
    for name in tuple(names):
        bone = pose_bones.get(name)
        while bone is not None and getattr(bone, "parent", None) is not None:
            bone = bone.parent
            result.add(str(bone.name))
    return result
