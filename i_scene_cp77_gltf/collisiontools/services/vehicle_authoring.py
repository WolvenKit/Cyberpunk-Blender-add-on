from __future__ import annotations

import json
import math
import os

import bpy

from ...assetio.atomic import atomic_write_text
from ...blender.armature_bones import bone_by_aliases
from ...blender.operator_results import OperationResult
from ...blender.physics.vehicle_geometry import (
    aggregate_bounds,
    body_bounds_objects,
    entity_collection_for_object,
    object_attachment_name,
    object_targets_rig,
    projected_dimensions,
    vehicle_frame_world,
)
from ...blender.selection import selected_meshes
from ...physics.domain.vehicle.gears import (
    PHYSX_MAX_FORWARD_GEARS,
    collection_gears,
    validate_gears,
)
from ...physics.domain.vehicle.tweakxl import build_tweakxl_yaml
from ...physics.services.vehicle_tweaks import project_resources_root
from ..blender.vehicle_authoring_state import (
    apply_authored_vehicle_values,
    ensure_axle_authoring,
)
from ..blender.vehicle_gears import (
    ensure_gear_collection,
    populate_default_gear_collection,
    populate_gear_collection,
)
from ..blender.vehicle_validation import resolved_game_config
from ..runtime.vehicle_preview import queue_vehicle_live_update
from .vehicle_resolver import imported_vehicle_record, project_source

_BIKE_BONES = {
    "front": ("wheel_front", "wheel_f", "front_wheel", "wheel_front_left"),
    "rear": ("wheel_back", "wheel_rear", "wheel_b", "rear_wheel", "wheel_back_left"),
}
_BIKE_SUSPENSION = {
    "front": ("suspension_front", "fork_front", "suspension_front_left"),
    "rear": ("suspension_back", "suspension_rear", "suspension_back_left"),
}


def _bike_related(rig, wheel_bones):
    direct = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH" and object_targets_rig(obj, rig)
    ]
    parent_map = {}
    for collection in bpy.data.collections:
        for child in collection.children:
            parent_map.setdefault(child.as_pointer(), []).append(collection)
    collection = None
    for obj in direct:
        collection = entity_collection_for_object(obj, parent_map)
        if collection is not None:
            break
    related = list(collection.all_objects) if collection is not None else direct
    related = [obj for obj in related if obj.type == "MESH"]
    groups = {"front": [], "rear": []}
    reverse = {name.casefold(): field for field, name in wheel_bones.items()}
    for obj in related:
        field = reverse.get(object_attachment_name(obj, rig).casefold())
        if field:
            groups[field].append(obj)
    return collection, related, groups


def _bike_frame_axis(rig, front_bone, rear_bone):
    front = rig.data.bones[front_bone].head_local
    rear = rig.data.bones[rear_bone].head_local
    delta = front - rear
    if abs(delta.x) >= abs(delta.y):
        return "POS_X" if delta.x >= 0.0 else "NEG_X"
    return "POS_Y" if delta.y >= 0.0 else "NEG_Y"


def _bike_fit(vehicle, related=(), groups=None):
    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    wheels = (vehicle.bike_front, vehicle.bike_rear)
    dimensions = []
    groups = groups or {}
    for field, wheel in zip(("front", "rear"), wheels):
        bounds = aggregate_bounds(groups.get(field, ()), frame_inverse)
        dimensions.append(
            (bounds[1] - bounds[0])
            if bounds
            else (projected_dimensions(wheel, frame_inverse) if wheel else None)
        )
    valid = [value for value in dimensions if value is not None]
    if valid:
        vehicle.wheel_radius = max(
            sum(max(value.y, value.z) * 0.5 for value in valid) / len(valid), 0.01
        )
        vehicle.wheel_width = max(sum(value.x for value in valid) / len(valid), 0.01)
    if vehicle.source_mode == "RIG":
        front = vehicle.rig.data.bones[vehicle.bike_front_bone].head_local
        rear = vehicle.rig.data.bones[vehicle.bike_rear_bone].head_local
        body = body_bounds_objects(
            related,
            vehicle.rig,
            {
                "front": vehicle.bike_front_bone,
                "rear": vehicle.bike_rear_bone,
            },
        )
        chassis_bounds = aggregate_bounds(body, frame_inverse)
    else:
        front = frame_inverse @ vehicle.bike_front.matrix_world.translation
        rear = frame_inverse @ vehicle.bike_rear.matrix_world.translation
        chassis_bounds = aggregate_bounds((vehicle.chassis,), frame_inverse)
    vehicle.wheelbase = (front - rear).length
    vehicle.track_width = 0.0
    if chassis_bounds:
        minimum, maximum = chassis_bounds
        size = maximum - minimum
        vehicle.chassis_shape_offset = tuple((minimum + maximum) * 0.5)
        vehicle.chassis_dims = tuple(max(value, 0.01) for value in size)


def setup_bike_selection(context):
    rig = context.active_object
    if rig is None or rig.type != "ARMATURE":
        return OperationResult.cancelled("Select the imported bike MetaRig")
    wheel_bones = {
        field: bone_by_aliases(rig, aliases) for field, aliases in _BIKE_BONES.items()
    }
    missing = [field for field, name in wheel_bones.items() if not name]
    if missing:
        return OperationResult.cancelled(
            "The selected rig is missing bike wheel bones: " + ", ".join(missing)
        )
    suspension = {
        field: bone_by_aliases(rig, aliases)
        for field, aliases in _BIKE_SUSPENSION.items()
    }
    collection, related, groups = _bike_related(rig, wheel_bones)
    vehicle = context.scene.physx_vehicle
    vehicle.enabled = True
    vehicle.source_mode = "RIG"
    vehicle.rig = rig
    vehicle.appearance_collection = collection
    vehicle.bike_front_bone = wheel_bones["front"]
    vehicle.bike_rear_bone = wheel_bones["rear"]
    vehicle.bike_front_suspension_bone = suspension["front"]
    vehicle.bike_rear_suspension_bone = suspension["rear"]
    vehicle.bike_front = groups["front"][0] if groups["front"] else None
    vehicle.bike_rear = groups["rear"][0] if groups["rear"] else None
    vehicle.forward_axis = _bike_frame_axis(
        rig, wheel_bones["front"], wheel_bones["rear"]
    )
    vehicle.resolved_object_names = json.dumps(
        [obj.name for obj in related], separators=(",", ":")
    )
    vehicle.resolved_wheel_groups = json.dumps(
        {field: [obj.name for obj in groups[field]] for field in ("front", "rear")},
        separators=(",", ":"),
    )
    vehicle.resolved_visual_count = len(related)
    vehicle.resolved_wheel_visual_count = sum(len(group) for group in groups.values())
    _bike_fit(vehicle, related, groups)
    vehicle.axle_authoring_initialized = False
    ensure_axle_authoring(vehicle)
    vehicle.source_summary = f"{rig.name}: bike; {len(related)} visual meshes; {vehicle.resolved_wheel_visual_count} wheel/tire meshes"
    return OperationResult.finished(vehicle.source_summary)


def setup_bike_manual(context):
    chassis = context.active_object
    meshes = selected_meshes(context)
    wheels = [obj for obj in meshes if obj != chassis]
    if chassis is None or chassis.type != "MESH" or len(wheels) != 2:
        return OperationResult.cancelled(
            "Select an active chassis mesh and exactly two wheel meshes"
        )
    vehicle = context.scene.physx_vehicle
    vehicle.enabled = True
    vehicle.source_mode = "MANUAL"
    vehicle.chassis = chassis
    frame_inverse = (vehicle_frame_world(vehicle)).inverted_safe()
    wheels.sort(
        key=lambda obj: (frame_inverse @ obj.matrix_world.translation).y, reverse=True
    )
    vehicle.bike_front, vehicle.bike_rear = wheels
    _bike_fit(vehicle)
    vehicle.axle_authoring_initialized = False
    ensure_axle_authoring(vehicle)
    return OperationResult.finished("Bike references and dimensions configured")


def refresh_bike(vehicle):
    if vehicle.source_mode == "RIG":
        wheel_bones = {"front": vehicle.bike_front_bone, "rear": vehicle.bike_rear_bone}
        collection, related, groups = _bike_related(vehicle.rig, wheel_bones)
        vehicle.appearance_collection = collection
        vehicle.resolved_object_names = json.dumps(
            [obj.name for obj in related], separators=(",", ":")
        )
        vehicle.resolved_wheel_groups = json.dumps(
            {field: [obj.name for obj in groups[field]] for field in ("front", "rear")},
            separators=(",", ":"),
        )
        vehicle.resolved_visual_count = len(related)
        vehicle.resolved_wheel_visual_count = sum(
            len(group) for group in groups.values()
        )
        vehicle.bike_front = groups["front"][0] if groups["front"] else None
        vehicle.bike_rear = groups["rear"][0] if groups["rear"] else None
        _bike_fit(vehicle, related, groups)
    else:
        _bike_fit(vehicle)


def reset_vehicle_gears(vehicle):
    try:
        config = (
            resolved_game_config(vehicle)
            if getattr(vehicle, "game_data_enabled", False)
            else {}
        )
        if config:
            populate_gear_collection(vehicle, config)
        else:
            populate_default_gear_collection(vehicle)
        queue_vehicle_live_update(vehicle.id_data)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(f"Restored {len(vehicle.gears) - 1} forward gears")


def add_vehicle_gear(vehicle):
    try:
        config = (
            resolved_game_config(vehicle)
            if getattr(vehicle, "game_data_enabled", False)
            else {}
        )
        ensure_gear_collection(vehicle, config)
        gears = validate_gears(collection_gears(vehicle), vehicle=vehicle)
        if len(gears) - 1 >= PHYSX_MAX_FORWARD_GEARS:
            raise ValueError(
                f"PhysX supports at most {PHYSX_MAX_FORWARD_GEARS} forward gears"
            )
        previous = gears[-1]
        max_engine_rpm = float(vehicle.engine_max_omega) * 60.0 / (2.0 * math.pi)
        item = vehicle.gears.add()
        item.ratio = max(float(previous.ratio) * 0.75, 0.05)
        item.max_speed = max(float(previous.max_speed) * 1.25, 0.1)
        item.min_speed = min(
            max(float(previous.min_speed) * 1.25, float(previous.max_speed) * 0.5),
            item.max_speed * 0.9,
        )
        item.torque_multiplier = 1.0
        item.min_engine_rpm = min(float(previous.min_engine_rpm), max_engine_rpm * 0.6)
        item.max_engine_rpm = min(
            max(float(previous.max_engine_rpm), 1.0), max_engine_rpm
        )
        if item.min_engine_rpm >= item.max_engine_rpm:
            item.min_engine_rpm = item.max_engine_rpm * 0.5
        item.source_record = ""
        vehicle.gear_index = len(vehicle.gears) - 1
        queue_vehicle_live_update(vehicle.id_data)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(f"Added forward gear {vehicle.gear_index}")


def remove_vehicle_gear(vehicle):
    try:
        config = (
            resolved_game_config(vehicle)
            if getattr(vehicle, "game_data_enabled", False)
            else {}
        )
        ensure_gear_collection(vehicle, config)
        if len(vehicle.gears) <= 2:
            raise ValueError(
                "The gearbox must retain reverse and at least one forward gear"
            )
        index = min(max(int(vehicle.gear_index), 0), len(vehicle.gears) - 1)
        if index == 0:
            raise ValueError("Reverse gear cannot be removed")
        vehicle.gears.remove(index)
        vehicle.gear_index = min(index, len(vehicle.gears) - 1)
        validate_gears(collection_gears(vehicle), vehicle=vehicle)
        queue_vehicle_live_update(vehicle.id_data)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished("Removed forward gear")


def move_vehicle_gear(vehicle, direction):
    try:
        config = (
            resolved_game_config(vehicle)
            if getattr(vehicle, "game_data_enabled", False)
            else {}
        )
        ensure_gear_collection(vehicle, config)
        index = min(max(int(vehicle.gear_index), 0), len(vehicle.gears) - 1)
        if index == 0:
            raise ValueError("Reverse gear is fixed at the start of the gearbox")
        step = -1 if direction == "UP" else 1
        target = index + step
        if target < 1 or target >= len(vehicle.gears):
            return OperationResult.finished("Gear is already at the end of the gearbox")
        vehicle.gears.move(index, target)
        vehicle.gear_index = target
        validate_gears(collection_gears(vehicle), vehicle=vehicle)
        queue_vehicle_live_update(vehicle.id_data)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(
        f"Moved forward gear to position {vehicle.gear_index}"
    )


def default_tweakxl_export_path(vehicle):
    """The project's TweakXL override file for record"""
    name = vehicle.tweakxl_record_id.rsplit(".", 1)[-1] + ".yaml"
    source = project_source(vehicle)
    resources = project_resources_root(source) if source else ""
    return os.path.join(resources, "r6", "tweaks", name) if resources else name


def export_vehicle_tweakxl(vehicle, filepath):
    try:
        base = (
            vehicle.tweakxl_base_record.strip()
            or vehicle.game_data_record
            or imported_vehicle_record(vehicle)
        )
        if not base:
            raise ValueError("Choose the vehicle the export is based on")
        folder = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(folder, exist_ok=True)
        source = (
            json.loads(vehicle.game_data_config or "{}")
            if vehicle.game_data_enabled
            else {}
        )
        config = apply_authored_vehicle_values(vehicle, source)
        text = build_tweakxl_yaml(
            vehicle.tweakxl_record_id,
            base,
            vehicle.vehicle_kind,
            config,
            add_to_vehicle_list=vehicle.tweakxl_add_to_vehicle_list,
        )
        atomic_write_text(filepath, text)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(f"Exported TweakXL vehicle data: {filepath}")
