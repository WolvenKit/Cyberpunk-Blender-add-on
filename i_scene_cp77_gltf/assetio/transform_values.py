from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from ..bartmoss.qs_transform import QsTransform
from .values import coerce_float


def parse_wkit_trs(
    records,
    count: int | None = None,
    *,
    quaternion_order: str = "xyzw",
    normalize_rotations: bool = True,
):
    records = records or ()
    size = len(records) if count is None else int(count)
    quaternions = np.zeros((size, 4), dtype=np.float32)
    translations = np.zeros((size, 3), dtype=np.float32)
    scales = np.ones((size, 3), dtype=np.float32)
    if quaternion_order == "xyzw":
        identity_index = 3
        component_keys = ("i", "j", "k", "r")
    elif quaternion_order == "wxyz":
        identity_index = 0
        component_keys = ("r", "i", "j", "k")
    else:
        raise ValueError(f"Unsupported quaternion order: {quaternion_order}")
    quaternions[:, identity_index] = 1.0
    for index, transform in enumerate(records[:size]):
        if not transform:
            continue
        rotation = transform.get("Rotation", {})
        quaternions[index] = tuple(
            float(rotation.get(key, 1.0 if key == "r" else 0.0))
            for key in component_keys
        )
        translation = transform.get("Translation", {})
        translations[index] = (
            float(translation.get("X", 0.0)),
            float(translation.get("Y", 0.0)),
            float(translation.get("Z", 0.0)),
        )
        scale = transform.get("Scale", {})
        scales[index] = (
            float(scale.get("X", 1.0)),
            float(scale.get("Y", 1.0)),
            float(scale.get("Z", 1.0)),
        )
    if normalize_rotations:
        norms = np.linalg.norm(quaternions, axis=1, keepdims=True)
        np.divide(quaternions, np.where(norms > 0.0, norms, 1.0), out=quaternions)
    return quaternions, translations, scales


FIXED_POINT_SCALE = 131072.0


def _component(mapping, keys, default):
    """The first value among keys as a float, or default when none is set or it is not a number"""
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return coerce_float(value, default, unwrap=False, finite=False)
    return float(default)


_AXIS_KEYS = ("X", "x", "Y", "y", "Z", "z")


def _vector_fields(mapping):
    """The mapping holding a vector's components"""
    if not any(key in mapping for key in _AXIS_KEYS) and isinstance(
        mapping.get("Properties"), Mapping
    ):
        return mapping["Properties"]
    return mapping


def fixed_point_value(value: Any, default: float = 0.0) -> float:
    """A coordinate from its document form"""
    if isinstance(value, Mapping):
        if "Bits" in value:
            return float(value["Bits"]) / FIXED_POINT_SCALE
        value = value.get("$value", default)
    return coerce_float(value, default, unwrap=False, finite=False)


def fixed_point_bits(value: float) -> int:
    """The FixedPoint Bits of a coordinate"""
    return int(round(float(value) * FIXED_POINT_SCALE))


def world_transform_entry(position, orientation) -> dict:
    """A document WorldTransform"""
    return {
        "$type": "WorldTransform",
        "Orientation": encode_wkit_quaternion(orientation),
        "Position": {
            "$type": "WorldPosition",
            **{
                axis: {"$type": "FixedPoint", "Bits": fixed_point_bits(value)}
                for axis, value in zip("xyz", position)
            },
        },
    }


def world_position_from_data(
    value: Any, default=(0.0, 0.0, 0.0)
) -> tuple[float, float, float]:
    """A WorldPosition or Vector from its document form"""
    if not isinstance(value, Mapping):
        return tuple(float(component) for component in default)
    value = _vector_fields(value)
    result = []
    for index, keys in enumerate((("x", "X"), ("y", "Y"), ("z", "Z"))):
        component = next(
            (value[key] for key in keys if value.get(key) is not None), default[index]
        )
        result.append(fixed_point_value(component, default[index]))
    return tuple(result)


def quaternion_wxyz_from_wkit(value, default=(1.0, 0.0, 0.0, 0.0)):
    """(w, x, y, z) from a document Quaternion ({r, i, j, k}) or a Vector4-style one ({W, X, Y, Z})"""
    if not isinstance(value, Mapping):
        return tuple(float(component) for component in default)
    return (
        _component(value, ("r", "W"), default[0]),
        _component(value, ("i", "X"), default[1]),
        _component(value, ("j", "Y"), default[2]),
        _component(value, ("k", "Z"), default[3]),
    )


def quaternion_wxyz_from_ijkr(value, default=(1.0, 0.0, 0.0, 0.0)):
    if isinstance(value, dict):
        return quaternion_wxyz_from_wkit(value, default)
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return (float(value[3]), float(value[0]), float(value[1]), float(value[2]))
    return tuple(float(component) for component in default)


def quaternion_ijkr_from_wxyz(value):
    return (float(value[1]), float(value[2]), float(value[3]), float(value[0]))


def encode_wkit_quaternion(value, *, quaternion_order: str = "xyzw"):
    values = np.asarray(value)
    if quaternion_order == "xyzw":
        i, j, k, r = (float(component) for component in values)
    elif quaternion_order == "wxyz":
        r, i, j, k = (float(component) for component in values)
    else:
        raise ValueError(f"Unsupported quaternion order: {quaternion_order}")
    return {"$type": "Quaternion", "i": i, "j": j, "k": k, "r": r}


def encode_qs_transform(
    rotation,
    translation,
    scale,
    *,
    translation_w: float,
    scale_w: float,
    quaternion_order: str = "xyzw",
):
    rotation = np.asarray(rotation)
    translation = np.asarray(translation)
    scale = np.asarray(scale)
    return {
        "$type": "QsTransform",
        "Rotation": encode_wkit_quaternion(rotation, quaternion_order=quaternion_order),
        "Scale": vector4_entry(
            float(scale[0]), float(scale[1]), float(scale[2]), float(scale_w)
        ),
        "Translation": vector4_entry(
            float(translation[0]),
            float(translation[1]),
            float(translation[2]),
            float(translation_w),
        ),
    }


def vector3_entry(x, y, z) -> dict:
    """The document form of a Vector3 holding these components as they are"""
    return {"$type": "Vector3", "X": x, "Y": y, "Z": z}


def vector4_entry(x, y, z, w) -> dict:
    """The document form of a Vector4 holding these components as they are, in WolvenKit's field order"""
    return {"$type": "Vector4", "W": w, "X": x, "Y": y, "Z": z}


def vector3_from_data(
    value: Any, default=(0.0, 0.0, 0.0)
) -> tuple[float, float, float]:
    """A Vector3 from its document form or a sequence"""
    if isinstance(value, Mapping):
        value = _vector_fields(value)
        return (
            _component(value, ("X", "x"), default[0]),
            _component(value, ("Y", "y"), default[1]),
            _component(value, ("Z", "z"), default[2]),
        )
    if isinstance(value, (str, bytes)):
        return tuple(float(component) for component in default)
    try:
        items = tuple(value)
    except TypeError:
        items = ()
    return tuple(
        float(items[index]) if index < len(items) else float(default[index])
        for index in range(3)
    )


def qs_transform_from_data(value: Any) -> QsTransform:
    """A QsTransform from its document form, a QsTransform as it is, or identity"""
    if isinstance(value, QsTransform):
        return value
    if not isinstance(value, Mapping):
        return QsTransform.identity()
    translation = value.get("Translation", value.get("translation", (0.0, 0.0, 0.0)))
    rotation = value.get("Rotation", value.get("rotation", (0.0, 0.0, 0.0, 1.0)))
    scale = value.get("Scale", value.get("scale", (1.0, 1.0, 1.0)))
    if isinstance(scale, Mapping):
        scale = vector3_from_data(scale, (1.0, 1.0, 1.0))
    rotation = quaternion_ijkr_from_wxyz(quaternion_wxyz_from_ijkr(rotation))
    return QsTransform.from_components(vector3_from_data(translation), rotation, scale)
