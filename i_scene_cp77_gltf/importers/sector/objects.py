from __future__ import annotations

import json
import math

import bpy

from ...bartmoss.matrix import flatten_matrix
from ...blender.keyframes import get_action_fcurves
from ...blender.naming import fit_id_name
from ...blender.transactions import track_created_datablock

_IDPROP_INT_MIN = -(1 << 31)
_IDPROP_INT_MAX = (1 << 31) - 1


def new_collection(name):
    return track_created_datablock("collections", bpy.data.collections.new(name))


def new_empty(name, collection, display_size=0.25):
    obj = track_created_datablock(
        "objects", bpy.data.objects.new(fit_id_name(name), None)
    )
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = display_size
    collection.objects.link(obj)
    return obj


def copy_object(old_obj, color=None, hide_armature=True):
    obj = track_created_datablock("objects", old_obj.copy())
    if color is not None:
        obj.color = color
    if hide_armature and getattr(obj, "type", None) == "ARMATURE":
        obj.hide_viewport = True
        obj.hide_render = True
    return obj


def collection_instance_object(
    name, collection, target_collection, matrix=None, color=None
):
    obj = track_created_datablock(
        "objects", bpy.data.objects.new(fit_id_name(name), None)
    )
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.25
    obj.instance_type = "COLLECTION"
    obj.instance_collection = collection
    if color is not None:
        obj.color = color
    target_collection.objects.link(obj)
    if matrix is not None:
        obj.matrix_world = matrix
        obj["cp77_matrix"] = flatten_matrix(matrix).tolist()
    return obj


def animate_rotation_root(
    rotation_root, axis_name, full_rotation_time, reverse_direction
):
    axis_index = {"X": 0, "Y": 1, "Z": 2}.get(str(axis_name).upper(), 2)
    seconds = max(float(full_rotation_time or 0.0), 1.0 / 24.0)
    fps = float(bpy.context.scene.render.fps) / max(
        float(bpy.context.scene.render.fps_base), 1e-8
    )
    end_frame = 1 + max(1, round(seconds * fps))
    direction = -1.0 if bool(reverse_direction) else 1.0

    rotation_root.rotation_mode = "XYZ"
    rotation_root.rotation_euler = (0.0, 0.0, 0.0)
    rotation_root.keyframe_insert("rotation_euler", index=axis_index, frame=1)
    rotation_root.rotation_euler[axis_index] = direction * math.tau
    rotation_root.keyframe_insert("rotation_euler", index=axis_index, frame=end_frame)

    action = (
        rotation_root.animation_data.action if rotation_root.animation_data else None
    )
    fcurves = get_action_fcurves(action, rotation_root) if action is not None else None
    for fcurve in fcurves or ():
        if fcurve.data_path != "rotation_euler" or fcurve.array_index != axis_index:
            continue
        for point in fcurve.keyframe_points:
            point.interpolation = "LINEAR"
        if not any(modifier.type == "CYCLES" for modifier in fcurve.modifiers):
            modifier = fcurve.modifiers.new(type="CYCLES")
            modifier.mode_before = "REPEAT"
            modifier.mode_after = "REPEAT"


def _id_property_safe_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if _IDPROP_INT_MIN <= value <= _IDPROP_INT_MAX:
            return value
        return str(value)
    if isinstance(value, dict):
        return {str(key): _id_property_safe_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        return [_id_property_safe_value(item) for item in value]
    return value


def _assign_prepared_id_property(obj, key, value):
    try:
        obj[key] = value
        return
    except (OverflowError, TypeError, ValueError):
        pass
    try:
        obj[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except (OverflowError, TypeError, ValueError):
        obj[key] = str(value)


def _assign_id_property(obj, key, value):
    safe_value = _id_property_safe_value(value)
    try:
        obj[key] = safe_value
        return
    except (OverflowError, TypeError, ValueError):
        pass

    try:
        obj[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except (OverflowError, TypeError, ValueError):
        obj[key] = str(value)


def assign_id_properties(obj, **kwargs):
    for key, value in kwargs.items():
        _assign_id_property(obj, key, value)


def node_records(node, sector_name):
    """The records each placement of node keeps for export"""
    records = [
        ("cp77_node_type", node.source_node_type),
        ("nodeIndex", node.index),
        ("cp77_sector_name", sector_name),
    ]
    if node.inner_index >= 0:
        records.append(("cp77_instance_index", node.inner_index))
    return tuple(records)


def _static_node_property_values(node, sector_name):
    data = node.data
    ntype = node.node_type
    values = list(node_records(node, sector_name))
    if "debugName" in data:
        values.append(("debugName", data["debugName"]["$value"]))
    if "sourcePrefabHash" in data:
        values.append(("sourcePrefabHash", data["sourcePrefabHash"]))
    if ntype == "worldAISpotNode":
        if data["spot"]:
            values.append(
                (
                    "cp77_workspot",
                    data["spot"]["Data"]["resource"]["DepotPath"]["$value"],
                )
            )
        else:
            values.append(("cp77_workspot", "None"))
        if data["markings"]:
            values.append(("markings", data["markings"][0]["$value"]))
    if "entityTemplate" in data:
        values.append(
            (
                "entityTemplate",
                data["entityTemplate"]["DepotPath"]["$value"],
            )
        )

    if "appearanceName" in data:
        appearance_name = data["appearanceName"]["$value"]
    elif "meshAppearance" in data:
        appearance_name = data["meshAppearance"]["$value"]
    else:
        appearance_name = ""
    values.append(("appearanceName", appearance_name))
    return tuple((key, _id_property_safe_value(value)) for key, value in values)


class NodePropertyAssigner:
    """Gives a placement of a parsed node the node's records and settings"""

    __slots__ = ("_cache",)

    def __init__(self):
        self._cache = {}

    def __call__(self, obj, node, sector_name, **kwargs):
        key = (id(node), sector_name)
        cached = self._cache.get(key)
        if cached is None or cached[0] is not node:
            cached = (node, _static_node_property_values(node, sector_name))
            self._cache[key] = cached
        for property_name, value in cached[1]:
            _assign_prepared_id_property(obj, property_name, value)
        assign_id_properties(obj, **kwargs)
