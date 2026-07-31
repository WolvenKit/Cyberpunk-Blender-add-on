from __future__ import annotations

import os
from collections.abc import Iterable

try:
    import bpy
except ImportError:
    bpy = None

from ..redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT, RIG_SPACE_CONTRACT_DIRECT

READ_RIG_REQUIRED_DATA_KEYS = (
    "boneNames",
    "boneParentIndexes",
    "source_rig_file",
)
_SUPPORTED_RIG_CONTRACTS = {
    RIG_SPACE_CONTRACT_CURRENT,
    RIG_SPACE_CONTRACT_DIRECT,
}


def plain_strings(values) -> list[str]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        return []
    result = []
    for value in values:
        if isinstance(value, str):
            result.append(value)
        elif hasattr(value, "get"):
            result.append(str(value.get("$value", "")))
        else:
            result.append(str(value))
    return result


def merged_bone_name(name: str) -> str:
    value = str(name or "")
    return f"{value[:-5]}_slot" if value.endswith("_plug") else value


def source_bone_name(name: str) -> str:
    value = str(name or "")
    return f"{value[:-5]}_plug" if value.endswith("_slot") else value


def bone_name_candidates(name: str):
    value = str(name or "")
    if not value:
        return
    yield value
    merged = merged_bone_name(value)
    if merged != value:
        yield merged
    source = source_bone_name(value)
    if source != value and source != merged:
        yield source


def is_read_rig_armature(obj) -> bool:
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return False
    data = getattr(obj, "data", None)
    return data is not None and all(data.get(key) is not None for key in READ_RIG_REQUIRED_DATA_KEYS)


def rig_space_contract(armature):
    data = getattr(armature, "data", None)
    if data is None:
        return RIG_SPACE_CONTRACT_CURRENT
    stored = data.get("cp77_rig_space_contract")
    if stored in _SUPPORTED_RIG_CONTRACTS:
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


def bone_names_equivalent(obj, left, right) -> bool:
    left_name = resolve_bone_name(obj, left)
    right_name = resolve_bone_name(obj, right)
    return bool(left_name and right_name and left_name == right_name)


def read_rig_source_path(obj) -> str:
    data = getattr(obj, "data", None)
    if data is None:
        return ""
    raw = data.get("source_rig_file") or data.get("source") or ""
    if not isinstance(raw, str):
        return ""
    candidates = [part.strip() for part in raw.split(";") if part.strip()]
    if len(candidates) != 1:
        return ""
    path = candidates[0]
    path = bpy.path.abspath(path) if bpy is not None else os.path.abspath(path)
    return path if os.path.isfile(path) else ""


def resolve_rig_path(obj, explicit_path: str = "") -> str:
    if explicit_path:
        path = (
            bpy.path.abspath(explicit_path)
            if bpy is not None
            else os.path.abspath(explicit_path)
        )
        return path if os.path.isfile(path) else ""
    return read_rig_source_path(obj)


def read_rig_bone_names(obj) -> list[str]:
    data = getattr(obj, "data", None)
    if data is None:
        return []
    names = plain_strings(data.get("boneNames", ()))
    if names:
        return names
    pose = getattr(obj, "pose", None)
    return [bone.name for bone in pose.bones] if pose is not None else []


def read_rig_parent_indices(obj) -> list[int]:
    data = getattr(obj, "data", None)
    if data is None:
        return []
    try:
        return [int(value) for value in data.get("boneParentIndexes", ())]
    except (TypeError, ValueError):
        return []


def validate_rig_armature(obj, rig, *, used_bone_names=None) -> list[str]:
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return ["<armature>"]
    required = (
        used_bone_names
        if used_bone_names is not None
        else getattr(rig, "bone_names", ())
    )
    return [str(name) for name in required if resolve_pose_bone(obj, str(name)) is None]


def ensure_float_idproperty(owner, name: str, value: float) -> bool:
    value = float(value)
    current = owner.get(name)
    if isinstance(current, float):
        owner[name] = value
        return False
    if current is not None:
        try:
            del owner[name]
        except Exception:
            pass
    owner[name] = value
    return True


def configure_float_idproperty(
    owner,
    name: str,
    value: float,
    *,
    default: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    soft_minimum: float | None = None,
    soft_maximum: float | None = None,
    description: str | None = None,
    subtype: str | None = None,
    overwrite_ui: bool = True,
) -> bool:
    created = ensure_float_idproperty(owner, name, value)
    if not overwrite_ui and not created:
        return created
    kwargs = {}
    if default is not None:
        kwargs["default"] = float(default)
    if minimum is not None:
        kwargs["min"] = float(minimum)
    if maximum is not None:
        kwargs["max"] = float(maximum)
    if soft_minimum is not None:
        kwargs["soft_min"] = float(soft_minimum)
    if soft_maximum is not None:
        kwargs["soft_max"] = float(soft_maximum)
    if description is not None:
        kwargs["description"] = description
    if subtype is not None:
        kwargs["subtype"] = subtype
    if kwargs:
        owner.id_properties_ui(name).update(**kwargs)
    return created
