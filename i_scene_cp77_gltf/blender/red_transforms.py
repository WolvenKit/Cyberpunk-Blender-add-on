from __future__ import annotations

from mathutils import Matrix, Quaternion, Vector

from ..assetio.transform_values import (
    quaternion_wxyz_from_wkit,
    vector3_from_data,
    world_position_from_data,
)

POSITION_KEYS = ("Position", "Translation", "relativePosition")
ROTATION_KEYS = ("Orientation", "Rotation", "relativeRotation")


def red_quaternion(value):
    return Quaternion(quaternion_wxyz_from_wkit(value))


def transform_field(transform, keys):
    if type(transform) is not dict:
        return {}
    for key in keys:
        value = transform.get(key)
        if type(value) is dict:
            return value
    return {}


def transform_position(transform, keys=POSITION_KEYS):
    return Vector(world_position_from_data(transform_field(transform, keys)))


def transform_scale(transform):
    scale = (
        transform.get("Scale") or transform.get("scale")
        if type(transform) is dict
        else None
    )
    return Vector(
        vector3_from_data(scale, (1.0, 1.0, 1.0))
        if type(scale) is dict
        else (1.0, 1.0, 1.0)
    )


def transform_matrix(
    transform, pos_keys=POSITION_KEYS, rot_keys=ROTATION_KEYS, scale=None
):
    if type(transform) is not dict:
        return Matrix.Identity(4)
    return Matrix.LocRotScale(
        transform_position(transform, pos_keys),
        red_quaternion(transform_field(transform, rot_keys)),
        scale if scale is not None else transform_scale(transform),
    )
