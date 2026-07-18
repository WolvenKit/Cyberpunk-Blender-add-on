from __future__ import annotations

import os
from collections.abc import Iterable

import numpy as np

try:
    import bpy
    from bpy_extras import anim_utils
except ImportError:
    bpy = None
    anim_utils = None

from .rig_utils import merged_rig_bone_name

READ_RIG_REQUIRED_DATA_KEYS = (
    "boneNames",
    "boneParentIndexes",
    "source_rig_file",
)


def _plain_strings(values) -> list[str]:
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


def is_read_rig_armature(obj) -> bool:
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return False
    data = getattr(obj, "data", None)
    return data is not None and all(data.get(key) is not None for key in READ_RIG_REQUIRED_DATA_KEYS)


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
        path = bpy.path.abspath(explicit_path) if bpy is not None else os.path.abspath(explicit_path)
        return path if os.path.isfile(path) else ""
    return read_rig_source_path(obj)


def read_rig_bone_names(obj) -> list[str]:
    data = getattr(obj, "data", None)
    if data is None:
        return []
    names = _plain_strings(data.get("boneNames", ()))
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


def resolve_pose_bone(obj, name: str):
    pose = getattr(obj, "pose", None)
    if pose is None:
        return None
    source_name = str(name)
    bone = pose.bones.get(source_name)
    if bone is not None:
        return bone
    target_name = merged_rig_bone_name(source_name)
    return pose.bones.get(target_name) if target_name != source_name else None


def validate_rig_armature(obj, rig, *, used_bone_names=None) -> list[str]:
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return ["<armature>"]
    required = used_bone_names if used_bone_names is not None else getattr(rig, "bone_names", ())
    return [str(name) for name in required if resolve_pose_bone(obj, str(name)) is None]


def ensure_float_idproperty(owner, name: str, value: float) -> bool:
    """Ensure a scalar IDProperty is float. Return True when newly created/retyped."""
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
    """Create/retype a float property and optionally configure its UI metadata."""
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


def get_action_slot(action, id_data=None, *, create: bool = False):
    """Resolve the Blender 5 action slot used by id_data."""
    if action is None:
        return None
    slots = action.slots
    animation_data = getattr(id_data, "animation_data", None) if id_data is not None else None
    if animation_data is not None and animation_data.action is action:
        assigned = animation_data.action_slot
        if assigned is not None:
            return assigned
        suitable = animation_data.action_suitable_slots
        if suitable:
            animation_data.action_slot = suitable[0]
            return suitable[0]
    if len(slots):
        return slots[0]
    if not create:
        return None
    id_type = getattr(id_data, "id_type", "OBJECT") if id_data is not None else "OBJECT"
    name = getattr(id_data, "name", action.name)
    try:
        slot = slots.new(id_type=id_type, name=name)
    except TypeError:
        slot = slots.new(id_type=id_type)
    if animation_data is not None and animation_data.action is action:
        animation_data.action_slot = slot
    return slot


def assign_action_with_slot(id_data, action):
    """Assign an action and bind its canonical Blender 5 slot."""
    animation_data = id_data.animation_data_create()
    animation_data.action = action
    slot = get_action_slot(action, id_data, create=True)
    if slot is not None:
        animation_data.action_slot = slot
    return animation_data


def get_action_channelbag(action, id_data=None, *, create: bool = False):
    if action is None or anim_utils is None:
        return None
    slot = get_action_slot(action, id_data, create=create)
    if slot is None:
        return None
    if create:
        return anim_utils.action_ensure_channelbag_for_slot(action, slot)
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                if channelbag.slot is slot:
                    return channelbag
    return None


def get_action_fcurves(action, id_data=None, *, create: bool = False):
    channelbag = get_action_channelbag(action, id_data, create=create)
    return channelbag.fcurves if channelbag is not None else None


def get_action_groups(action, id_data=None, *, create: bool = False):
    channelbag = get_action_channelbag(action, id_data, create=create)
    return channelbag.groups if channelbag is not None else None


def ensure_fcurve(action, id_data, data_path: str, index: int, group_name: str = ""):
    fcurves = get_action_fcurves(action, id_data, create=True)
    if fcurves is None:
        raise RuntimeError(f"Unable to resolve FCurves for action {action.name!r}")
    return fcurves.ensure(data_path, index=index, group_name=group_name)


def bulk_set_keyframes(
    fcurve,
    frames,
    values,
    interpolation: str | None = None,
    *,
    collapse_constant: bool = False,
    update: bool = False,
) -> int:
    frames = np.asarray(frames, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    count = len(frames)
    if count == 0:
        return 0
    if collapse_constant and count > 1 and np.all(np.abs(values - values[0]) <= 1e-10):
        frames = frames[:1]
        values = values[:1]
        count = 1
    points = fcurve.keyframe_points
    points.add(count)
    coordinates = np.empty(count * 2, dtype=np.float64)
    coordinates[0::2] = frames
    coordinates[1::2] = values
    points.foreach_set("co", coordinates)
    if interpolation is not None:
        blender_interpolation = "CONSTANT" if interpolation == "STEP" else interpolation
        try:
            enum_value = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items[blender_interpolation].value
            points.foreach_set("interpolation", np.full(count, enum_value, dtype=np.int32))
        except (AttributeError, KeyError, TypeError, RuntimeError):
            for point in points:
                point.interpolation = blender_interpolation
    if update:
        fcurve.update()
    return count


def round_keyframes(frames):
    """Round to nearest frame; exact halves resolve toward the lower frame."""
    frames = np.asarray(frames, dtype=np.float64)
    lower = np.floor(frames)
    upper = np.ceil(frames)
    return np.where((upper - frames) < (frames - lower), upper, lower)
