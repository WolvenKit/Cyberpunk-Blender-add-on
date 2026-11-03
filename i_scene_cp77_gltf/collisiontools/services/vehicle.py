import json

import bpy
from mathutils import Vector

from ...bartmoss.hierarchy import parent_depth
from ...bartmoss.vehicle import vehicle_axle_geometry
from ...blender.armature_bones import bone_by_aliases
from ...blender.collections import collection_parent_map
from ...blender.operator_results import OperationResult
from ...blender.physics.vehicle_geometry import (
    WHEEL_FIELDS,
    aggregate_bounds,
    body_bounds_objects,
    bone_is_descendant_of,
    entity_collection_for_object,
    object_attachment_name,
    object_targets_rig,
    projected_bounds,
    projected_dimensions,
    vehicle_frame_world,
    vehicle_local_position,
    wheel_objects,
)
from ...blender.selection import selected_meshes
from ...core.log import get_logger, log_once
from ..blender.vehicle_authoring_state import ensure_axle_authoring
from ..blender.vehicle_config import validate_vehicle, wheel_centers

_LOG = get_logger(__name__)


_RIG_WHEEL_BONE_ALIASES = {
    "front_left": ("wheel_front_left", "wheel_fl", "front_left_wheel"),
    "front_right": ("wheel_front_right", "wheel_fr", "front_right_wheel"),
    "rear_left": ("wheel_back_left", "wheel_rear_left", "wheel_bl", "rear_left_wheel"),
    "rear_right": (
        "wheel_back_right",
        "wheel_rear_right",
        "wheel_br",
        "rear_right_wheel",
    ),
}

_RIG_SUSPENSION_BONE_ALIASES = {
    "front_left": ("suspension_front_left", "suspension_fl"),
    "front_right": ("suspension_front_right", "suspension_fr"),
    "rear_left": ("suspension_back_left", "suspension_rear_left", "suspension_bl"),
    "rear_right": ("suspension_back_right", "suspension_rear_right", "suspension_br"),
}

_RIG_WHEEL_RADIUS_TRACKS = {
    "front_left": "veh_rad_w_f_l",
    "front_right": "veh_rad_w_f_r",
    "rear_left": "veh_rad_w_b_l",
    "rear_right": "veh_rad_w_b_r",
}


def _descendant_wheel_bone(rig, suspension_name):
    suspension = rig.data.bones.get(suspension_name) if suspension_name else None
    if suspension is None:
        return ""
    candidates = [
        bone
        for bone in rig.data.bones
        if bone_is_descendant_of(bone, suspension) and "wheel" in bone.name.casefold()
    ]
    if not candidates:
        return ""
    depth_cache = {}
    candidates.sort(
        key=lambda bone: (parent_depth(bone, depth_cache), bone.name.casefold())
    )
    return candidates[0].name


def _resolve_rig_bones(rig):
    suspension = {
        field: bone_by_aliases(rig, aliases)
        for field, aliases in _RIG_SUSPENSION_BONE_ALIASES.items()
    }
    wheels = {}
    for field, aliases in _RIG_WHEEL_BONE_ALIASES.items():
        wheel_name = bone_by_aliases(rig, aliases)
        if not wheel_name:
            wheel_name = _descendant_wheel_bone(rig, suspension[field])
        wheels[field] = wheel_name
    return wheels, suspension


def _is_visible_object(obj, view_layer=None):
    if obj.hide_viewport or obj.hide_render:
        return False
    try:
        return obj.visible_get(view_layer=view_layer)
    except (AttributeError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_is_visible_object 1", type(error).__name__),
            "is visible object: fell back after %s",
            error,
            exc_info=True,
        )
        try:
            return not obj.hide_get()
        except (AttributeError, RuntimeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_is_visible_object 2", type(error).__name__),
                "is visible object: fell back after %s",
                error,
                exc_info=True,
            )
            return True


def _resolve_rig_visuals(context, rig, wheel_bones):
    direct = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH" and object_targets_rig(obj, rig)
    ]
    parent_map = collection_parent_map()
    candidate_scores = {}
    candidate_collections = {}
    for obj in direct:
        collection = entity_collection_for_object(obj, parent_map)
        if collection is None:
            continue
        pointer = collection.as_pointer()
        score = 1000 if _is_visible_object(obj, context.view_layer) else 1
        candidate_scores[pointer] = candidate_scores.get(pointer, 0) + score
        candidate_collections[pointer] = collection

    if candidate_scores:
        appearance_collection = candidate_collections[
            max(candidate_scores, key=candidate_scores.get)
        ]
    else:
        appearance_collection = None
    if appearance_collection is not None:
        objects = [
            obj for obj in appearance_collection.all_objects if obj.type == "MESH"
        ]
    else:
        objects = direct

    wheel_groups = {field: [] for field, _label in WHEEL_FIELDS}
    bone_to_field = {
        name.casefold(): field for field, name in wheel_bones.items() if name
    }
    related = []
    for obj in objects:
        if not _is_visible_object(obj, context.view_layer):
            continue
        related.append(obj)
        attachment = object_attachment_name(obj, rig).casefold()
        field = bone_to_field.get(attachment)
        if field:
            wheel_groups[field].append(obj)

    return appearance_collection, related, wheel_groups


def _rig_track_map(rig):
    if rig is None or rig.type != "ARMATURE":
        return {}
    names = list(rig.data.get("trackNames", ()) or rig.get("trackNames", ()))
    values = list(rig.data.get("referenceTracks", ()) or rig.get("referenceTracks", ()))
    return {
        str(name): float(values[index])
        for index, name in enumerate(names)
        if index < len(values)
    }


def _infer_forward_axis(rig, wheel_bones):
    positions = {}
    for field, bone_name in wheel_bones.items():
        bone = rig.data.bones.get(bone_name) if bone_name else None
        if bone is None:
            return "POS_X"
        positions[field] = bone.head_local.copy()
    front = (positions["front_left"] + positions["front_right"]) * 0.5
    rear = (positions["rear_left"] + positions["rear_right"]) * 0.5
    vector = front - rear
    if abs(vector.x) >= abs(vector.y):
        return "POS_X" if vector.x >= 0.0 else "NEG_X"
    return "POS_Y" if vector.y >= 0.0 else "NEG_Y"


def _classify_wheels(vehicle, wheels):
    if len(wheels) != 4:
        raise ValueError("Select exactly four wheel meshes")
    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    positions = {
        wheel: frame_inverse @ wheel.matrix_world.translation for wheel in wheels
    }
    front = sorted(wheels, key=lambda obj: positions[obj].y, reverse=True)[:2]
    rear = [obj for obj in wheels if obj not in front]
    front.sort(key=lambda obj: positions[obj].x)
    rear.sort(key=lambda obj: positions[obj].x)
    return front[0], front[1], rear[0], rear[1]


def _resolved_group_objects(vehicle):
    try:
        groups = json.loads(vehicle.resolved_wheel_groups or "{}")
    except (TypeError, ValueError):
        groups = {}
    return {
        field: [
            obj
            for name in groups.get(field, ())
            if (obj := bpy.data.objects.get(name)) is not None
        ]
        for field, _label in WHEEL_FIELDS
    }


def _representative_wheel(objects):
    if not objects:
        return None
    return min(
        objects,
        key=lambda obj: (
            0 if "tire" in str(obj.get("componentName", obj.name)).casefold() else 1,
            obj.name.casefold(),
        ),
    )


def setup_vehicle_from_rig(context, rig):
    if rig is None or rig.type != "ARMATURE":
        raise ValueError("Select the imported vehicle MetaRig")
    wheel_bones, suspension_bones = _resolve_rig_bones(rig)
    missing = [label for field, label in WHEEL_FIELDS if not wheel_bones[field]]
    if missing:
        raise ValueError(
            "The selected rig is missing wheel bones: " + ", ".join(missing)
        )

    vehicle = context.scene.physx_vehicle
    vehicle.enabled = True
    vehicle.source_mode = "RIG"
    vehicle.rig = rig
    vehicle.forward_axis = _infer_forward_axis(rig, wheel_bones)
    for field, _label in WHEEL_FIELDS:
        setattr(vehicle, f"{field}_bone", wheel_bones[field])
        setattr(vehicle, f"{field}_suspension_bone", suspension_bones[field])

    appearance_collection, related, wheel_groups = _resolve_rig_visuals(
        context,
        rig,
        wheel_bones,
    )
    vehicle.appearance_collection = appearance_collection
    vehicle.resolved_object_names = json.dumps(
        [obj.name for obj in related], separators=(",", ":")
    )
    vehicle.resolved_wheel_groups = json.dumps(
        {
            field: [obj.name for obj in wheel_groups[field]]
            for field, _label in WHEEL_FIELDS
        },
        separators=(",", ":"),
    )
    vehicle.resolved_visual_count = len(related)
    vehicle.resolved_wheel_visual_count = sum(
        len(group) for group in wheel_groups.values()
    )
    for field, _label in WHEEL_FIELDS:
        setattr(vehicle, field, _representative_wheel(wheel_groups[field]))

    autofit_vehicle(vehicle, context=context)
    appearance_name = (
        str(
            appearance_collection.get("appearanceName", "")
            or appearance_collection.name
        )
        if appearance_collection is not None
        else "unresolved appearance"
    )
    vehicle.source_summary = (
        f"{rig.name}: {appearance_name}; {len(related)} visual meshes; "
        f"{vehicle.resolved_wheel_visual_count} wheel/tire meshes"
    )
    return vehicle.source_summary


def _autofit_vehicle_from_rig(vehicle, context=None):
    rig = vehicle.rig
    if rig is None or rig.type != "ARMATURE":
        raise ValueError("Assign the imported vehicle MetaRig")
    wheel_bones = {
        field: getattr(vehicle, f"{field}_bone", "") for field, _label in WHEEL_FIELDS
    }
    if any(
        not name or rig.data.bones.get(name) is None for name in wheel_bones.values()
    ):
        raise ValueError("Resolve the four vehicle wheel bones before fitting")

    if context is not None:
        appearance_collection, related, wheel_groups = _resolve_rig_visuals(
            context,
            rig,
            wheel_bones,
        )
        vehicle.appearance_collection = appearance_collection
        vehicle.resolved_object_names = json.dumps(
            [obj.name for obj in related], separators=(",", ":")
        )
        vehicle.resolved_wheel_groups = json.dumps(
            {
                field: [obj.name for obj in wheel_groups[field]]
                for field, _label in WHEEL_FIELDS
            },
            separators=(",", ":"),
        )
        vehicle.resolved_visual_count = len(related)
        vehicle.resolved_wheel_visual_count = sum(
            len(group) for group in wheel_groups.values()
        )
    else:
        try:
            related_names = json.loads(vehicle.resolved_object_names or "[]")
        except (TypeError, ValueError):
            related_names = ()
        related = [
            obj
            for name in related_names
            if (obj := bpy.data.objects.get(name)) is not None
        ]
        wheel_groups = _resolved_group_objects(vehicle)

    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    track_map = _rig_track_map(rig)
    track_radii = [
        track_map.get(_RIG_WHEEL_RADIUS_TRACKS[field], 0.0)
        for field, _label in WHEEL_FIELDS
    ]
    valid_track_radii = [value for value in track_radii if value > 0.001]

    wheel_dimensions = []
    for field, _label in WHEEL_FIELDS:
        bounds = aggregate_bounds(wheel_groups.get(field, ()), frame_inverse)
        if bounds is not None:
            wheel_dimensions.append(bounds[1] - bounds[0])
    if valid_track_radii:
        vehicle.wheel_radius = sum(valid_track_radii) / len(valid_track_radii)
    elif wheel_dimensions:
        vehicle.wheel_radius = max(
            sum(max(size.y, size.z) * 0.5 for size in wheel_dimensions)
            / len(wheel_dimensions),
            0.01,
        )
    if wheel_dimensions:
        vehicle.wheel_width = max(
            sum(size.x for size in wheel_dimensions) / len(wheel_dimensions),
            0.01,
        )

    body_objects = body_bounds_objects(related, rig, wheel_bones)
    chassis_bounds = aggregate_bounds(body_objects, frame_inverse)
    centers_without_offset = wheel_centers(
        vehicle,
        frame_inverse,
        Vector((0.0, 0.0, 0.0)),
    )
    if any(center is None for center in centers_without_offset):
        raise ValueError("Could not resolve wheel centers from the selected rig")
    fl, fr, rl, rr = centers_without_offset
    geometry = vehicle_axle_geometry(centers_without_offset)
    wheelbase = geometry.wheelbase
    track_width = 0.5 * (geometry.front_track + geometry.rear_track)

    if chassis_bounds is None:
        radius = max(float(vehicle.wheel_radius), 0.01)
        half_length = wheelbase * 0.5 + radius * 1.25
        half_width = track_width * 0.5 + radius * 0.45
        chassis_min = Vector((-half_width, -half_length, -radius * 0.35))
        chassis_max = Vector((half_width, half_length, max(radius * 2.2, 0.8)))
    else:
        chassis_min, chassis_max = chassis_bounds
    chassis_dims = chassis_max - chassis_min
    vehicle.chassis_shape_offset = (
        (chassis_min.x + chassis_max.x) * 0.5,
        (chassis_min.y + chassis_max.y) * 0.5,
        (chassis_min.z + chassis_max.z) * 0.5,
    )
    vehicle.chassis_dims = tuple(max(value, 0.01) for value in chassis_dims)
    vehicle.chassis_cm_offset = (
        0.0,
        0.0,
        chassis_min.z + chassis_dims.z * vehicle.com_height_ratio,
    )
    vehicle.wheelbase = wheelbase
    vehicle.track_width = track_width


def autofit_vehicle(vehicle, context=None):
    if vehicle.source_mode == "RIG":
        _autofit_vehicle_from_rig(vehicle, context=context)
        return
    errors, _warnings = validate_vehicle(vehicle)
    assignment_errors = [
        error
        for error in errors
        if "Assign" in error or "must be a mesh" in error or "different object" in error
    ]
    if assignment_errors:
        raise ValueError("; ".join(assignment_errors))
    frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    chassis_min, chassis_max = projected_bounds(vehicle.chassis, frame_inverse)
    chassis_dims = chassis_max - chassis_min
    vehicle.chassis_shape_offset = (
        (chassis_min.x + chassis_max.x) * 0.5,
        (chassis_min.y + chassis_max.y) * 0.5,
        (chassis_min.z + chassis_max.z) * 0.5,
    )
    vehicle.chassis_dims = (
        max(chassis_dims.x, 0.01),
        max(chassis_dims.y, 0.01),
        max(chassis_dims.z, 0.01),
    )

    dimensions = [
        projected_dimensions(wheel, frame_inverse) for wheel in wheel_objects(vehicle)
    ]
    vehicle.wheel_radius = max(
        sum(max(size.y, size.z) * 0.5 for size in dimensions) / 4.0, 0.01
    )
    vehicle.wheel_width = max(sum(size.x for size in dimensions) / 4.0, 0.01)

    shape_offset = Vector(vehicle.chassis_shape_offset)
    centers = [
        vehicle_local_position(vehicle, wheel, frame_inverse, shape_offset)
        for wheel in wheel_objects(vehicle)
    ]
    vehicle.chassis_cm_offset = (
        0.0,
        0.0,
        chassis_min.z + chassis_dims.z * vehicle.com_height_ratio,
    )
    geometry = vehicle_axle_geometry(centers)
    vehicle.wheelbase = geometry.wheelbase
    vehicle.track_width = 0.5 * (geometry.front_track + geometry.rear_track)


def setup_vehicle_selection(context):

    try:
        summary = setup_vehicle_from_rig(context, context.active_object)
        vehicle = context.scene.physx_vehicle
        vehicle.axle_authoring_initialized = False
        ensure_axle_authoring(vehicle)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(summary)


def setup_vehicle_manual(context):

    vehicle = context.scene.physx_vehicle
    chassis = context.active_object
    meshes = selected_meshes(context)
    if chassis is None or chassis.type != "MESH":
        return OperationResult.cancelled("Make the chassis mesh active")
    wheels = [obj for obj in meshes if obj != chassis]
    if len(wheels) != 4:
        return OperationResult.cancelled(
            "Select the chassis and exactly four wheel meshes"
        )
    vehicle.enabled = True
    vehicle.source_mode = "MANUAL"
    vehicle.chassis = chassis
    try:
        fl, fr, rl, rr = _classify_wheels(vehicle, wheels)
        vehicle.front_left = fl
        vehicle.front_right = fr
        vehicle.rear_left = rl
        vehicle.rear_right = rr
        autofit_vehicle(vehicle, context=context)
        vehicle.axle_authoring_initialized = False
        ensure_axle_authoring(vehicle)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished("Vehicle references and dimensions configured")


def autofit_vehicle_configuration(context):

    try:
        vehicle = context.scene.physx_vehicle
        if vehicle.source_mode == "RIG":
            summary = setup_vehicle_from_rig(context, vehicle.rig)
            return OperationResult.finished(summary)
        autofit_vehicle(vehicle, context=context)
        vehicle.axle_authoring_initialized = False
        ensure_axle_authoring(vehicle)
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished("Vehicle dimensions fitted from assigned meshes")


def validate_vehicle_configuration(context):

    errors, warnings = validate_vehicle(context.scene.physx_vehicle)
    if errors:
        return OperationResult.cancelled("; ".join(errors))
    message = "Vehicle configuration is valid"
    if warnings:
        return OperationResult.finished(message + "; " + "; ".join(warnings), "WARNING")
    return OperationResult.finished(message)
