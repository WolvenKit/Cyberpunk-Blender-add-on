from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import slerp_xyzw
from ....bartmoss.scalar import lerp
from ....redSpace.euler import (
    CHANNEL_INDEX,
    euler_from_xyzw,
    xyzw_from_euler,
)

_POSITION_FIELDS = ("posX", "posY", "posZ")
_ROTATION_FIELDS = ("rotX", "rotY", "rotZ")
_SCALE_FIELDS = ("scaleX", "scaleY", "scaleZ")


@dataclass(frozen=True)
class DirectConnEvaluation:
    transform: QsTransform
    applied: bool
    weight: float


@dataclass(frozen=True)
class FloatTrackDirectConnEvaluation:
    transform: QsTransform
    applied: bool
    weight: float


def evaluate_direct_conn(
    target: QsTransform,
    source: QsTransform,
    channels: Mapping[str, bool],
    weight: float,
) -> DirectConnEvaluation:
    """Apply direct-connection constraint semantics to one target transform"""
    weight = float(weight)
    if not weight > 0.0:
        return DirectConnEvaluation(target, False, weight)

    position_enabled = tuple(
        bool(channels.get(field, False)) for field in _POSITION_FIELDS
    )
    rotation_enabled = tuple(
        bool(channels.get(field, False)) for field in _ROTATION_FIELDS
    )
    scale_enabled = tuple(bool(channels.get(field, False)) for field in _SCALE_FIELDS)
    all_position = all(position_enabled)
    all_rotation = all(rotation_enabled)
    all_scale = all(scale_enabled)

    if all_position and all_rotation and all_scale:
        if weight < 1.0:
            translation = lerp(target.translation, source.translation, weight)
            rotation = slerp_xyzw(
                np.asarray(target.rotation_xyzw, dtype=np.float64),
                np.asarray(source.rotation_xyzw, dtype=np.float64),
                weight,
            )
            scale = lerp(target.scale, source.scale, weight)
            result = QsTransform.from_components(translation, rotation, scale)
        else:
            result = source
        return DirectConnEvaluation(result, True, weight)

    translation = np.asarray(target.translation, dtype=np.float64).copy()
    rotation = np.asarray(target.rotation_xyzw, dtype=np.float64).copy()
    scale = np.asarray(target.scale, dtype=np.float64).copy()
    applied = False

    if all_position:
        translation = (
            lerp(target.translation, source.translation, weight)
            if weight < 1.0
            else np.asarray(source.translation, dtype=np.float64).copy()
        )
        applied = True
    elif any(position_enabled):
        source_translation = np.asarray(source.translation, dtype=np.float64)
        for axis, enabled in enumerate(position_enabled):
            if enabled:
                translation[axis] = weight * source_translation[axis]
                applied = True

    if all_rotation:
        rotation = (
            slerp_xyzw(
                np.asarray(target.rotation_xyzw, dtype=np.float64),
                np.asarray(source.rotation_xyzw, dtype=np.float64),
                weight,
            )
            if weight < 1.0
            else np.asarray(source.rotation_xyzw, dtype=np.float64).copy()
        )
        applied = True
    elif any(rotation_enabled):
        target_euler = list(euler_from_xyzw(target.rotation_xyzw))
        source_euler = euler_from_xyzw(source.rotation_xyzw)
        for axis, enabled in enumerate(rotation_enabled):
            if enabled:
                target_euler[axis] = weight * source_euler[axis]
                applied = True
        rotation = np.asarray(xyzw_from_euler(*target_euler), dtype=np.float64)

    if all_scale:
        scale = (
            lerp(target.scale, source.scale, weight)
            if weight < 1.0
            else np.asarray(source.scale, dtype=np.float64).copy()
        )
        applied = True
    elif any(scale_enabled):
        source_scale = np.asarray(source.scale, dtype=np.float64)
        for axis, enabled in enumerate(scale_enabled):
            if enabled:
                scale[axis] = weight * source_scale[axis]
                applied = True

    return DirectConnEvaluation(
        QsTransform.from_components(translation, rotation, scale),
        applied,
        weight,
    )


def evaluate_float_track_direct_conn(
    target: QsTransform,
    track_value: float,
    channel: str,
    mul_factor: float,
    weight: float,
) -> FloatTrackDirectConnEvaluation:
    weight = float(weight)
    if not weight > 0.0:
        return FloatTrackDirectConnEvaluation(target, False, weight)

    value = float(track_value) * float(mul_factor)
    translation = np.asarray(target.translation, dtype=np.float64).copy()
    rotation = np.asarray(target.rotation_xyzw, dtype=np.float64).copy()
    scale = np.asarray(target.scale, dtype=np.float64).copy()
    channel = str(channel or "")

    if channel in {"PosX", "PosY", "PosZ"}:
        translation[{"PosX": 0, "PosY": 1, "PosZ": 2}[channel]] = value
    elif channel in {"RotX", "RotY", "RotZ"}:
        euler = list(euler_from_xyzw(target.rotation_xyzw))
        euler[CHANNEL_INDEX[channel]] = value
        rotation = np.asarray(xyzw_from_euler(*euler), dtype=np.float64)
    elif channel in {"ScaleX", "ScaleY", "ScaleZ"}:
        scale[{"ScaleX": 0, "ScaleY": 1, "ScaleZ": 2}[channel]] = value
    else:
        return FloatTrackDirectConnEvaluation(target, False, weight)

    modified = QsTransform.from_components(translation, rotation, scale)
    if weight < 1.0:
        modified = QsTransform.from_components(
            lerp(target.translation, modified.translation, weight),
            slerp_xyzw(
                np.asarray(target.rotation_xyzw, dtype=np.float64),
                np.asarray(modified.rotation_xyzw, dtype=np.float64),
                weight,
            ),
            lerp(target.scale, modified.scale, weight),
        )
    return FloatTrackDirectConnEvaluation(modified, True, weight)
