from __future__ import annotations

from collections import deque

from mathutils import Matrix, Quaternion, Vector

from .actors import native_shape_definition
from .vehicle_chassis import vehicle_chassis_phys_objects

WHEEL_FIELDS = (
    ("front_left", "Front Left"),
    ("front_right", "Front Right"),
    ("rear_left", "Rear Left"),
    ("rear_right", "Rear Right"),
)

_BODY_BOUNDS_EXCLUSIONS = (
    "_shadow",
    "shadow_",
    "interaction_collider",
    "proxy",
)

_AXIS_VECTORS = {
    "POS_X": Vector((1.0, 0.0, 0.0)),
    "NEG_X": Vector((-1.0, 0.0, 0.0)),
    "POS_Y": Vector((0.0, 1.0, 0.0)),
    "NEG_Y": Vector((0.0, -1.0, 0.0)),
}

_BASIS_MATRICES = {}


def vehicle_root(vehicle):
    if vehicle.source_mode == "RIG":
        return vehicle.rig
    return vehicle.chassis


def rigid_world_matrix(obj):
    location = obj.matrix_world.to_translation()
    rotation = obj.matrix_world.to_quaternion().normalized()
    return Matrix.Translation(location) @ rotation.to_matrix().to_4x4()


def basis_matrix(vehicle):
    axis = vehicle.forward_axis
    basis = _BASIS_MATRICES.get(axis)
    if basis is None:
        forward = _AXIS_VECTORS[axis].normalized()
        up = Vector((0.0, 0.0, 1.0))
        right = forward.cross(up).normalized()
        basis = Matrix((right, forward, up)).transposed().to_4x4()
        _BASIS_MATRICES[axis] = basis
    return basis.copy()


def vehicle_frame_world(vehicle):
    root = vehicle_root(vehicle)
    if root is None:
        return Matrix.Identity(4)
    return rigid_world_matrix(root) @ basis_matrix(vehicle)


def vehicle_actor_world(vehicle):
    return vehicle_frame_world(vehicle) @ Matrix.Translation(
        Vector(vehicle.chassis_shape_offset)
    )


def object_points_in_frame(obj, frame_inverse):
    return [
        frame_inverse @ (obj.matrix_world @ Vector(corner)) for corner in obj.bound_box
    ]


def projected_bounds(obj, frame_inverse):
    points = object_points_in_frame(obj, frame_inverse)
    minimum = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    maximum = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    return minimum, maximum


def projected_dimensions(obj, frame_inverse):
    minimum, maximum = projected_bounds(obj, frame_inverse)
    return maximum - minimum


def aggregate_bounds(objects, frame_inverse):
    points = []
    for obj in objects:
        if obj is None or obj.type != "MESH":
            continue
        points.extend(object_points_in_frame(obj, frame_inverse))
    if not points:
        return None
    minimum = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    maximum = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    return minimum, maximum


def bone_is_descendant_of(bone, ancestor):
    parent = bone.parent if bone is not None else None
    while parent is not None:
        if parent == ancestor:
            return True
        parent = parent.parent
    return False


def rig_bone_world_matrix(rig, bone_name):
    if rig is None or rig.type != "ARMATURE" or not bone_name:
        return None
    bone = rig.data.bones.get(bone_name)
    if bone is None:
        return None
    return rig.matrix_world @ bone.matrix_local


def object_targets_rig(obj, rig):
    if obj is None or rig is None:
        return False
    if obj.parent == rig:
        return True
    for modifier in getattr(obj, "modifiers", ()):
        if modifier.type == "ARMATURE" and getattr(modifier, "object", None) == rig:
            return True
    for constraint in getattr(obj, "constraints", ()):
        if getattr(constraint, "target", None) == rig:
            return True
    return False


def object_attachment_name(obj, rig=None):
    for key in ("slotName", "cp77_skin_attachment_root_bone"):
        value = str(obj.get(key, "") or "")
        if value and value != "None":
            return value
    if rig is not None:
        for constraint in getattr(obj, "constraints", ()):
            if getattr(constraint, "target", None) == rig:
                subtarget = str(getattr(constraint, "subtarget", "") or "")
                if subtarget:
                    return subtarget
    return ""


def entity_collection_for_object(obj, parent_map):
    pending = deque(getattr(obj, "users_collection", ()))
    seen = set()
    while pending:
        collection = pending.popleft()
        pointer = collection.as_pointer()
        if pointer in seen:
            continue
        seen.add(pointer)
        if collection.get("cp77_entity_imported", False):
            return collection
        pending.extend(parent_map.get(pointer, ()))
    return None


def body_bounds_objects(objects, rig, wheel_bones):
    wheel_names = {name.casefold() for name in wheel_bones.values() if name}
    result = []
    for obj in objects:
        attachment = object_attachment_name(obj, rig).casefold()
        if attachment in wheel_names:
            continue
        label = " ".join(
            (
                obj.name,
                str(obj.get("componentName", "") or ""),
                str(obj.get("sourcePath", "") or ""),
            )
        ).casefold()
        if any(token in label for token in _BODY_BOUNDS_EXCLUSIONS):
            continue
        result.append(obj)
    return result


def vehicle_local_position(vehicle, obj, frame_inverse=None, shape_offset=None):
    if frame_inverse is None:
        frame_inverse = vehicle_frame_world(vehicle).inverted_safe()
    if shape_offset is None:
        shape_offset = Vector(vehicle.chassis_shape_offset)
    return frame_inverse @ obj.matrix_world.translation - shape_offset


def matrix_from_pose(pose):
    """The world matrix of a bridge pose (x, y, z, qx, qy, qz, qw)"""
    rotation = Quaternion((pose[6], pose[3], pose[4], pose[5])).normalized()
    return (
        Matrix.Translation(Vector((pose[0], pose[1], pose[2])))
        @ rotation.to_matrix().to_4x4()
    )


def pose_from_matrix(matrix):
    location = matrix.to_translation()
    rotation = matrix.to_quaternion().normalized()
    return [
        location.x,
        location.y,
        location.z,
        rotation.x,
        rotation.y,
        rotation.z,
        rotation.w,
    ]


def vehicle_chassis_shape_definitions(scene, vehicle, actor_frame_world):
    actors = vehicle_chassis_phys_objects(scene, getattr(vehicle, "rig", None))
    if not actors:
        return [], ()
    actor_inverse = actor_frame_world.inverted_safe()
    definitions = []
    for obj in actors:
        for shape in obj.physx.shapes:
            definition = native_shape_definition(shape)
            if definition is None:
                raise ValueError(f"{obj.name}: {shape.name} is not cooked")
            shape_matrix = (
                Matrix.Translation(Vector(shape.local_pos))
                @ shape.local_rot.to_matrix().to_4x4()
            )
            local_matrix = actor_inverse @ obj.matrix_world @ shape_matrix
            location, rotation, scale = local_matrix.decompose()
            if any(abs(float(value) - 1.0) > 1.0e-4 for value in scale):
                raise ValueError(
                    f"{obj.name}: vehicle chassis .phys actor has unsupported scale "
                    f"{tuple(round(float(value), 6) for value in scale)}"
                )
            definition["pos"] = [location.x, location.y, location.z]
            definition["rot"] = [rotation.x, rotation.y, rotation.z, rotation.w]
            definitions.append(definition)
    if not definitions:
        raise ValueError(
            "The loaded vehicle chassis .phys contains no usable collision shapes"
        )
    return definitions, actors


def wheel_objects(vehicle):
    return tuple(getattr(vehicle, field, None) for field, _label in WHEEL_FIELDS)
