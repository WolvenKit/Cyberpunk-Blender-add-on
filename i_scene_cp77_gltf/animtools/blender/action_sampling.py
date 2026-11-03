from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...animation.model.clip.binding import track_name_from_property_path
from ...animation.model.clip.metadata import indexed_strings
from ...bartmoss.qs_transform import QsTransform
from ...blender.action_metadata import action_skin_extras, armature_track_names
from ...blender.keyframes import action_curve_map


@dataclass(frozen=True, slots=True)
class BoneCurveBinding:
    name: str
    location: tuple[Any | None, Any | None, Any | None]
    rotation: tuple[Any | None, Any | None, Any | None, Any | None]
    scale: tuple[Any | None, Any | None, Any | None]


@dataclass(frozen=True, slots=True)
class ActionSamplingPlan:
    action: Any
    bones: tuple[BoneCurveBinding, ...]
    bone_names: frozenset[str]
    tracks: dict[str, Any]


def _compile_curve_component(curve):
    """A constant for single-key curves without active modifiers, the curve itself otherwise"""
    if curve is None or bool(getattr(curve, "mute", False)):
        return None
    modifiers = tuple(getattr(curve, "modifiers", ()))
    if not any(not bool(getattr(modifier, "mute", False)) for modifier in modifiers):
        points = getattr(curve, "keyframe_points", ())
        if len(points) == 1:
            return float(points[0].co[1])
    return curve


def _curve_tuple(curve_map, path: str, width: int):
    return tuple(
        _compile_curve_component(curve_map.get((path, index))) for index in range(width)
    )


def _has_component(components) -> bool:
    return any(component is not None for component in components)


def component_value(component, default: float, frame: float) -> float:
    if component is None:
        return float(default)
    if isinstance(component, (float, int)):
        return float(component)
    return float(component.evaluate(frame))


def compile_action_plan(action, armature) -> ActionSamplingPlan:
    curves = action_curve_map(action, armature)
    bindings = []
    for pose_bone in armature.pose.bones:
        location = _curve_tuple(curves, pose_bone.path_from_id("location"), 3)
        rotation = _curve_tuple(
            curves, pose_bone.path_from_id("rotation_quaternion"), 4
        )
        scale = _curve_tuple(curves, pose_bone.path_from_id("scale"), 3)
        if not (
            _has_component(location)
            or _has_component(rotation)
            or _has_component(scale)
        ):
            continue
        bindings.append(BoneCurveBinding(pose_bone.name, location, rotation, scale))

    known_tracks = set(armature_track_names(armature))
    known_tracks.update(indexed_strings(armature.data.get("trackNames")))
    known_tracks.update(
        indexed_strings(action_skin_extras(action, armature).get("trackNames"))
    )
    track_curves = {}
    for (data_path, array_index), curve in curves.items():
        if array_index != 0:
            continue
        component = _compile_curve_component(curve)
        if component is None:
            continue
        name = track_name_from_property_path(data_path)
        if name is None or (known_tracks and name not in known_tracks):
            continue
        track_curves.setdefault(name, component)

    names = frozenset(binding.name for binding in bindings)
    return ActionSamplingPlan(action, tuple(bindings), names, track_curves)


def _evaluate_components(components, defaults, frame: float):
    return [
        component_value(component, default, frame)
        for component, default in zip(components, defaults)
    ]


def sample_bone(binding: BoneCurveBinding, frame: float) -> QsTransform:
    location = _evaluate_components(binding.location, (0.0, 0.0, 0.0), frame)
    rotation_wxyz = _evaluate_components(binding.rotation, (1.0, 0.0, 0.0, 0.0), frame)
    scale = _evaluate_components(binding.scale, (1.0, 1.0, 1.0), frame)
    return QsTransform.from_components(
        location,
        (rotation_wxyz[1], rotation_wxyz[2], rotation_wxyz[3], rotation_wxyz[0]),
        scale,
    )
