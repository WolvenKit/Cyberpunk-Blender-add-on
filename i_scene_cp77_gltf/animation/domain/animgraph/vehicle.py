from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping, Sequence

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import multiply_scalar_xyzw
from ....redSpace.euler import CHANNEL_INDEX, euler_from_xyzw
from ...model.animgraph.indices import index_name
from .curve_points import sample_curve
from .topology import has_link


def apply_additional_float_tracks(
    tracks: MutableMapping[str, float],
    container: Mapping | None,
    time_seconds: float,
) -> tuple[str, ...]:
    if not isinstance(container, Mapping):
        return ()
    overwrite = bool(container.get("overwriteExistingValues", False))
    written = []
    for entry in container.get("entries") or ():
        if not isinstance(entry, Mapping):
            continue
        info = (
            entry.get("trackInfo")
            if isinstance(entry.get("trackInfo"), Mapping)
            else {}
        )
        raw_name = info.get("name", "")
        if isinstance(raw_name, Mapping):
            raw_name = raw_name.get("$value", raw_name.get("value", ""))
        name = str(raw_name or "")
        if not name or name == "None":
            continue
        if name in tracks and not overwrite:
            continue
        reference = float(info.get("referenceValue", 0.0) or 0.0)
        tracks[name] = sample_curve(entry.get("values"), time_seconds, reference)
        written.append(name)
    return tuple(written)


def apply_float_track_modifier(
    tracks: MutableMapping[str, float],
    *,
    target: str,
    operation: str,
    input_track: str = "",
    input_value: float = 0.0,
) -> bool:
    if target not in tracks:
        return False
    first = float(tracks[target])
    second = (
        float(tracks[input_track])
        if input_track and input_track in tracks
        else float(input_value)
    )
    op = str(operation or "Override")
    if op == "Override":
        result = second
    elif op == "Multiply":
        result = first * second
    elif op == "Add":
        result = first + second
    elif op == "Subtract":
        result = first - second
    elif op == "SubtractSwapped":
        result = second - first
    elif op == "WeightComplement":
        result = 1.0 - second
    else:
        raise ValueError(f"unsupported float-track operation {op!r}")
    tracks[target] = float(result)
    return True


def transform_channel_value(transform: QsTransform, channel: str) -> float:
    channel = str(channel or "")
    if channel in {"PosX", "PosY", "PosZ"}:
        return float(transform.translation[{"PosX": 0, "PosY": 1, "PosZ": 2}[channel]])
    if channel in {"RotX", "RotY", "RotZ"}:
        return float(euler_from_xyzw(transform.rotation_xyzw)[CHANNEL_INDEX[channel]])
    if channel in {"ScaleX", "ScaleY", "ScaleZ"}:
        return float(transform.scale[{"ScaleX": 0, "ScaleY": 1, "ScaleZ": 2}[channel]])
    raise ValueError(f"unsupported transform channel {channel!r}")


def apply_transform_to_track(
    tracks: MutableMapping[str, float],
    transform: QsTransform,
    *,
    target_track: str,
    channel: str,
    mul_factor: float,
    weight: float,
) -> bool:
    if not target_track:
        return False
    sampled = transform_channel_value(transform, channel) * float(mul_factor)
    current = float(tracks.get(target_track, 0.0))
    w = float(weight)
    tracks[target_track] = current + (sampled - current) * w
    return True


def _axis_quaternion(axis: str, degrees: float) -> tuple[float, float, float, float]:
    half = math.radians(float(degrees)) * 0.5
    imaginary = math.sin(half)
    real = math.cos(half)
    axis = str(axis or "X_Axis")
    if axis in {"X", "X_Axis"}:
        return (imaginary, 0.0, 0.0, real)
    if axis in {"Y", "Y_Axis"}:
        return (0.0, imaginary, 0.0, real)
    if axis in {"Z", "Z_Axis"}:
        return (0.0, 0.0, imaginary, real)
    raise ValueError(f"unsupported transform axis {axis!r}")


def resolve_rotate_angle(
    previous_angle: float,
    *,
    linked_angle: float | None,
    scale: float,
    bias_angle: float,
    min_angle: float,
    max_angle: float,
    clamp_rotation: bool,
    incremental: bool,
    dt: float,
) -> float:
    if linked_angle is None:
        angle = float(bias_angle)
    elif incremental:
        angle = float(previous_angle) + float(linked_angle) * float(scale) * float(dt)
    else:
        angle = float(linked_angle) * float(scale) + float(bias_angle)
    if clamp_rotation:
        return min(max(angle, float(min_angle)), float(max_angle))
    angle = math.fmod(angle, 360.0)
    return angle + 360.0 if angle < 0.0 else angle


def rotate_bone_local(transform: QsTransform, axis: str, degrees: float) -> QsTransform:
    rotation = multiply_scalar_xyzw(
        transform.rotation_xyzw, _axis_quaternion(axis, degrees)
    )
    return QsTransform.from_components(transform.translation, rotation, transform.scale)


def rotate_bone_model(
    pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    bone: str,
    axis: str,
    degrees: float,
) -> bool:
    if bone not in pose:
        return False
    chain = []
    current = bone
    seen = set()
    while current and current in pose and current not in seen:
        seen.add(current)
        chain.append(current)
        current = str(parent_map.get(current, "") or "")
    model = QsTransform.identity()
    for name in reversed(chain):
        model = compose(model, pose[name])
    rotated_model = QsTransform.from_components(
        model.translation,
        multiply_scalar_xyzw(_axis_quaternion(axis, degrees), model.rotation_xyzw),
        model.scale,
    )
    parent = str(parent_map.get(bone, "") or "")
    if not parent or parent not in pose:
        pose[bone] = rotated_model
        return True
    parent_chain = []
    current = parent
    seen.clear()
    while current and current in pose and current not in seen:
        seen.add(current)
        parent_chain.append(current)
        current = str(parent_map.get(current, "") or "")
    parent_model = QsTransform.identity()
    for name in reversed(parent_chain):
        parent_model = compose(parent_model, pose[name])
    pose[bone] = relative_to(parent_model, rotated_model)
    return True


def resolve_translation(
    previous: Sequence[float],
    *,
    linked_translation: Sequence[float] | None,
    scale: Sequence[float],
    bias: Sequence[float],
    incremental: bool,
    dt: float,
) -> tuple[float, float, float]:
    if linked_translation is None:
        return tuple(float(bias[index]) for index in range(3))
    if incremental:
        return tuple(
            float(previous[index])
            + float(linked_translation[index]) * float(scale[index]) * float(dt)
            for index in range(3)
        )
    return tuple(
        float(linked_translation[index]) * float(scale[index]) + float(bias[index])
        for index in range(3)
    )


def apply_translation(
    transform: QsTransform, translation: Sequence[float]
) -> QsTransform:
    return QsTransform.from_components(
        tuple(
            float(transform.translation[i]) + float(translation[i]) for i in range(3)
        ),
        transform.rotation_xyzw,
        transform.scale,
    )


def rotate_bone_data(node_type, node):
    return {
        "bone": index_name(node.get("bone"), "animTransformIndex", allow_text=True),
        "axis": str(node.get("axis", "X_Axis") or "X_Axis"),
        "scale": float(node.get("scale", 1.0) or 0.0),
        "biasAngle": float(node.get("biasAngle", 0.0) or 0.0),
        "minAngle": float(
            node.get("minAngle", -90.0) if node.get("minAngle") is not None else -90.0
        ),
        "maxAngle": float(
            node.get("maxAngle", 90.0) if node.get("maxAngle") is not None else 90.0
        ),
        "clampRotation": bool(node.get("clampRotation", False)),
        "useIncrementalMode": bool(node.get("useIncrementalMode", False)),
        "resetOnActivation": bool(node.get("resetOnActivation", True)),
        "inModelSpace": bool(node.get("inModelSpace", False)),
        "hasAngleNode": has_link(node, "angleNode"),
        "hasMinValueNode": has_link(node, "minValueNode"),
        "hasMaxValueNode": has_link(node, "maxValueNode"),
    }


def translate_bone_data(node_type, node):
    return {
        "bone": index_name(node.get("bone"), "animTransformIndex", allow_text=True),
        "scale": node.get("scale") or {},
        "biasValue": node.get("biasValue") or {},
        "useIncrementalMode": bool(node.get("useIncrementalMode", False)),
        "resetOnActivation": bool(node.get("resetOnActivation", True)),
        "hasInputTranslation": has_link(node, "inputTranslation"),
    }
