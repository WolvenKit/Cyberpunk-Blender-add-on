from __future__ import annotations

import math
from dataclasses import dataclass

from mathutils import Matrix, Vector

from ...bartmoss.curve import piecewise_linear_value
from ...bartmoss.vehicle import steer_angle
from ...blender.physics.vehicle_geometry import bone_is_descendant_of
from ...blender.pose import apply_model_space_matrices
from ...physics.model.vehicle.rig import (
    BRAKE_BONE_KEYWORDS,
    STEERING_WHEEL_BONE_ALIASES,
    STEERING_WHEEL_TURN_DEGREES,
    SWINGARM_BONE_KEYWORD,
)


@dataclass(frozen=True, slots=True)
class RigCorner:
    field: str
    wheel: str
    suspension: str
    brakes: tuple[str, ...]
    swingarms: tuple[str, ...]
    steered: bool


@dataclass(slots=True)
class VehicleRigDrive:
    rig: object
    corners: tuple[RigCorner, ...]
    steering_wheel: str
    up: Vector
    axle: Vector
    order: tuple[str, ...]
    rest: dict
    rest_basis: dict


def _role_children(suspension, wheel_name):
    brakes = []
    swingarms = []
    for child in suspension.children:
        if child.name == wheel_name:
            continue
        name = child.name.casefold()
        if SWINGARM_BONE_KEYWORD in name:
            swingarms.append(child.name)
        elif any(keyword in name for keyword in BRAKE_BONE_KEYWORDS):
            brakes.append(child.name)
    return tuple(brakes), tuple(swingarms)


def capture_vehicle_rig(rig, wheel_bones, suspension_bones, basis, steered_fields):
    """Records the bones the vehicle preview poses and their current pose as the rest pose"""
    pose_bones = rig.pose.bones
    corners = []
    for field, wheel_name in wheel_bones.items():
        wheel = pose_bones.get(wheel_name) if wheel_name else None
        if wheel is None:
            raise ValueError(
                f"The rig does not define the {field.replace('_', ' ')} wheel bone"
            )
        suspension_name = suspension_bones.get(field, "")
        suspension = pose_bones.get(suspension_name) if suspension_name else None
        if suspension is None or not bone_is_descendant_of(wheel, suspension):
            corners.append(
                RigCorner(field, wheel_name, "", (), (), field in steered_fields)
            )
            continue
        brakes, swingarms = _role_children(suspension, wheel_name)
        corners.append(
            RigCorner(
                field,
                wheel_name,
                suspension_name,
                brakes,
                swingarms,
                field in steered_fields,
            )
        )
    steering_wheel = next(
        (
            name
            for name in STEERING_WHEEL_BONE_ALIASES
            if pose_bones.get(name) is not None
        ),
        "",
    )
    names = {steering_wheel} if steering_wheel else set()
    for corner in corners:
        names.update((corner.wheel, *corner.brakes, *corner.swingarms))
        if corner.suspension:
            names.add(corner.suspension)
    order = tuple(
        sorted(names, key=lambda name: (len(pose_bones[name].parent_recursive), name))
    )
    rotation = basis.to_3x3()
    return VehicleRigDrive(
        rig=rig,
        corners=tuple(corners),
        steering_wheel=steering_wheel,
        up=(rotation @ Vector((0.0, 0.0, 1.0))).normalized(),
        axle=(rotation @ Vector((1.0, 0.0, 0.0))).normalized(),
        order=order,
        rest={name: pose_bones[name].matrix.copy() for name in order},
        rest_basis={name: pose_bones[name].matrix_basis.copy() for name in order},
    )


def _swingarm_matrix(rest, yaw, travel):
    matrix = rest.copy()
    matrix.translation = (yaw @ rest.translation) + travel
    return matrix


def pose_vehicle_rig(drive, wheel_targets, max_steer):
    """Poses the rig from wheel matrices and returns the steering input shown"""
    matrices = {}
    steer_angles = []
    for corner in drive.corners:
        target = wheel_targets.get(corner.field)
        if target is None:
            continue
        rest_wheel = drive.rest[corner.wheel]
        turn = (
            target.to_3x3().normalized()
            @ rest_wheel.to_3x3().normalized().inverted_safe()
        )
        angle = steer_angle(drive.axle, turn @ drive.axle, drive.up)
        if corner.steered:
            steer_angles.append(angle)
        matrices[corner.wheel] = target
        if not corner.suspension:
            continue
        pivot = drive.rest[corner.suspension].translation
        yaw = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle, 4, drive.up)
            @ Matrix.Translation(-pivot)
        )
        travel = drive.up * (target.translation - yaw @ rest_wheel.translation).dot(
            drive.up
        )
        lift = Matrix.Translation(travel)
        matrices[corner.suspension] = yaw @ drive.rest[corner.suspension]
        for name in corner.brakes:
            matrices[name] = lift @ yaw @ drive.rest[name]
        for name in corner.swingarms:
            matrices[name] = _swingarm_matrix(drive.rest[name], yaw, travel)
    steering_input = 0.0
    if steer_angles and max_steer > 1.0e-6:
        # A turn to the right is a negative rotation about up; the steering input is positive to the right.
        steering_input = max(
            -1.0, min(1.0, -(sum(steer_angles) / len(steer_angles)) / max_steer)
        )
    if drive.steering_wheel:
        degrees = piecewise_linear_value(STEERING_WHEEL_TURN_DEGREES, steering_input)
        matrices[drive.steering_wheel] = drive.rest[
            drive.steering_wheel
        ] @ Matrix.Rotation(math.radians(degrees), 4, "Y")
    pose_bones = drive.rig.pose.bones
    apply_model_space_matrices(
        [pose_bones[name] for name in drive.order if name in matrices], matrices
    )
    return steering_input


def restore_vehicle_rig(drive):
    pose_bones = drive.rig.pose.bones
    for name, basis in drive.rest_basis.items():
        pose_bone = pose_bones.get(name)
        if pose_bone is not None:
            pose_bone.matrix_basis = basis.copy()
