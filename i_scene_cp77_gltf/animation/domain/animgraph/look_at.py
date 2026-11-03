from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ....assetio.values import cname_or_empty
from ....bartmoss.look_at import (
    direction_angles,
    direction_delta,
    interpolate_direction,
    rotate_direction,
    unit_direction,
)
from ....bartmoss.quaternion import rotate_vector_scalar_xyzw
from ....bartmoss.scalar import all_finite
from .curve_points import sample_curve
from .pose_space import frame_model_transform


def _curve(value: Any) -> Mapping[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    elements = []
    for raw in value.get("Elements", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        try:
            point = float(raw.get("Point", 0.0) or 0.0)
            sample = float(raw.get("Value", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        elements.append((point, sample))
    return {
        "interpolationType": str(value.get("InterpolationType", "Linear") or "Linear"),
        "linkType": str(value.get("LinkType", "ESLT_Normal") or "ESLT_Normal"),
        "elements": tuple(elements),
    }


def normalize_look_at_controller(node: Mapping[str, Any]) -> Mapping[str, Any]:
    parts = []
    for raw in node.get("orderedBodyParts", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        parts.append(
            {
                "partName": cname_or_empty(raw.get("partName")),
                "defaultPositionBoneName": cname_or_empty(
                    raw.get("defaultPositionBoneName")
                ),
            }
        )

    settings = []
    for raw in node.get("stateMachinesSettings", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        settings.append(
            {
                "partName": cname_or_empty(raw.get("partName")),
                "partAlias": cname_or_empty(raw.get("partAlias")),
                "sphereAttachmentBone": cname_or_empty(raw.get("sphereAttachmentBone")),
                "sphereRadius": float(raw.get("sphereRadius", 0.0) or 0.0),
                "followingSpeedFactor": float(
                    raw.get("followingSpeedFactor", 1.0) or 0.0
                ),
                "followingSpeedByAngleCurve": _curve(
                    raw.get("followingSpeedByAngleCurve")
                ),
                "enableFloatTrack": cname_or_empty(raw.get("enableFloatTrack")),
                "eyesOverrideFloatTrack": cname_or_empty(
                    raw.get("eyesOverrideFloatTrack")
                ),
                "transitionSpeedMultiplier": float(
                    raw.get("transitionSpeedMultiplier", 1.0) or 0.0
                ),
                "blendWeightPowFactor": float(
                    raw.get("blendWeightPowFactor", 1.0) or 0.0
                ),
                "coneLimitReached": cname_or_empty(raw.get("coneLimitReached")),
                "allowToBlendBehindBack": bool(
                    raw.get("allowToBlendBehindBack", False)
                ),
            }
        )

    dependencies = []
    for raw in node.get("bodyPartsDependencies", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        dependencies.append(
            {
                "masterPart": cname_or_empty(raw.get("masterPart")),
                "slavePart": cname_or_empty(raw.get("slavePart")),
                "angle": float(raw.get("angle", 10.0) or 0.0),
                "speedToTargetFactor": float(
                    raw.get("speedToTargetFactor", 1.0) or 0.0
                ),
                "speedToTargetByAngleCurve": _curve(
                    raw.get("speedToTargetByAngleCurve")
                ),
                "verticalPullSpeedFactor": float(
                    raw.get("verticalPullSpeedFactor", 1.0) or 0.0
                ),
                "verticalPullSpeedByAngleCurve": _curve(
                    raw.get("verticalPullSpeedByAngleCurve")
                ),
                "horizontalPullSpeedFactor": float(
                    raw.get("horizontalPullSpeedFactor", 1.0) or 0.0
                ),
                "horizontalPullSpeedByAngleCurve": _curve(
                    raw.get("horizontalPullSpeedByAngleCurve")
                ),
                "pullScaleBySquareSizeFactor": float(
                    raw.get("pullScaleBySquareSizeFactor", 1.0) or 0.0
                ),
                "pullScaleBySquareSizeCurve": _curve(
                    raw.get("pullScaleBySquareSizeCurve")
                ),
                "innerSquareScale": float(raw.get("innerSquareScale", 0.5) or 0.0),
            }
        )

    substep = float(node.get("substepTime", 0.01))
    if not math.isfinite(substep) or substep <= 0.0:
        raise ValueError("LookAtController substepTime must be positive")
    return {
        "orderedBodyParts": tuple(parts),
        "stateMachinesSettings": tuple(settings),
        "bodyPartsDependencies": tuple(dependencies),
        "substepTime": substep,
        "isFacial": bool(node.get("isFacial", False)),
        "hasOffsetLink": bool(
            isinstance(node.get("E3_HACK_offset"), Mapping)
            and isinstance(node.get("E3_HACK_offset", {}).get("node"), Mapping)
        ),
    }


@dataclass(frozen=True)
class LookAtRequest:
    part: str
    target: tuple[float, float, float]
    transition_speed: float = 60.0
    out_transition_speed: float = 60.0
    priority: int = 0
    soft_limit: float = 360.0
    suppress: float = 0.0
    mode: int = 0

    def __post_init__(self):
        values = (
            *self.target,
            self.transition_speed,
            self.out_transition_speed,
            self.soft_limit,
            self.suppress,
        )
        if len(self.target) != 3 or not all_finite(values):
            raise ValueError(
                "Look-at request requires finite target coordinates and parameters"
            )
        if (
            min(self.transition_speed, self.out_transition_speed) <= 0
            or not 0 <= self.soft_limit <= 360
        ):
            raise ValueError(
                "Look-at speeds must be positive and soft limit must be between 0 and 360 degrees"
            )


@dataclass
class PartState:
    selected: str = ""
    elapsed: float = 1.0
    duration: float = 1.0
    direction: tuple = (0.0, 1.0, 0.0)
    distance: float = 0.0
    active_weight: float = 0.0
    suppress: float = 0.0
    mode: int = 0
    previous: tuple | None = None
    following: dict = field(default_factory=dict)
    out_speed: float = 60.0
    initialized: bool = False


@dataclass
class LookAtControllerState:
    time_remainder: float = 0.0
    time_dilation_factor: float = 1.0
    was_enabled_previous_frame: bool = False
    service_requests: dict[str, LookAtRequest] = field(default_factory=dict)
    parts: dict[str, PartState] = field(default_factory=dict)
    transition_serial: int = 0
    transition_duration: float = 0.0
    transition_pitch: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.service_requests) or any(
            part.active_weight > 0 or part.selected for part in self.parts.values()
        )

    def clear(self) -> None:
        self.service_requests.clear()
        self.parts.clear()
        self.time_remainder = 0.0
        self.time_dilation_factor = 1.0
        self.was_enabled_previous_frame = False
        self.transition_serial = 0
        self.transition_duration = self.transition_pitch = 0.0


def inactive_graph_inputs(data: Mapping[str, Any]) -> dict[tuple[str, str], Any]:
    values: dict[tuple[str, str], Any] = {}
    for raw in data.get("orderedBodyParts", ()) or ():
        part = str(raw.get("partName", "") or "")
        if not part:
            continue
        values[(part, "isEnabled")] = False
        values[(part, "target")] = (0.0, 0.0, 0.0)
        values[(part, "rawTarget")] = (0.0, 0.0, 0.0)
        values[(part, "distance")] = 0.0
        values[(part, "suppress")] = 0.0
        values[(part, "mode")] = 0
        values[(part, "blendWeight")] = 0.0
    values[("Eyes", "isEnabled")] = False
    if bool(data.get("isFacial", False)):
        values[("lookAt", "lookAtTransitionDuration")] = 0.0
        values[("lookAt", "lookAtTransitionPitch")] = 0.0
    return values


def advance_controller(
    state: LookAtControllerState,
    data: Mapping[str, Any],
    raw_dt: float,
    graph_dt: float,
    *,
    pose=None,
    parent_map=None,
    tracks=None,
    model_space=False,
    eyes_enabled=1.0,
) -> dict[tuple[str, str], Any]:
    if not all_finite((raw_dt, graph_dt)) or min(raw_dt, graph_dt) < 0:
        raise ValueError("Look-at update intervals must be finite and nonnegative")
    state.time_dilation_factor = (
        float(graph_dt) / float(raw_dt) if raw_dt > 1e-6 else 0.0
    )
    if not state.enabled:
        state.time_remainder = 0.0
        state.was_enabled_previous_frame = False
        return inactive_graph_inputs(data)
    if data.get("bodyPartsDependencies"):
        raise ValueError(
            "Active look-at body-part followers are not available in this facial controller"
        )
    if pose is None:
        raise ValueError("Active look-at service requests require a sampled pose")
    tracks = tracks if tracks is not None else {}
    parent_map = parent_map or {}
    settings = {
        item["partName"]: item for item in data.get("stateMachinesSettings", ())
    }
    aliases = {item.get("partAlias"): name for name, item in settings.items()}
    requests = {}
    for key, request in state.service_requests.items():
        if not isinstance(request, LookAtRequest):
            raise ValueError("Look-at service requests must be LookAtRequest values")
        part = aliases.get(request.part, request.part)
        if part not in settings:
            raise ValueError(f"Look-at request names an unknown part: {request.part}")
        requests.setdefault(part, []).append((key, request))
    state.time_remainder += raw_dt
    substep = float(data["substepTime"])
    count = int(state.time_remainder / substep)
    state.time_remainder -= count * substep
    intervals = ([0.0] if not state.was_enabled_previous_frame else []) + [
        substep * state.time_dilation_factor
    ] * min(count, 3)
    output = inactive_graph_inputs(data)
    cache = {}
    for part_info in data.get("orderedBodyParts", ()):
        name = part_info["partName"]
        config = settings.get(name)
        if config is None:
            raise ValueError(f"Active look-at part {name} has no state machine")
        sphere_name, default_name = (
            config["sphereAttachmentBone"],
            part_info["defaultPositionBoneName"],
        )
        if sphere_name not in pose or default_name not in pose:
            raise ValueError(
                f"Look-at {name} requires bones {sphere_name!r} and {default_name!r}"
            )
        sphere = frame_model_transform(
            sphere_name, pose, parent_map, model_space, cache
        )
        default = frame_model_transform(
            default_name, pose, parent_map, model_space, cache
        )
        center, rotation = sphere.translation, sphere.rotation_xyzw
        inverse = (-rotation[0], -rotation[1], -rotation[2], rotation[3])

        def to_sphere(point):
            difference = tuple(a - b for a, b in zip(point, center))
            return unit_direction(
                rotate_vector_scalar_xyzw(inverse, difference)
            ), math.sqrt(sum(v * v for v in difference))

        default_direction, default_distance = to_sphere(default.translation)
        part = state.parts.setdefault(name, PartState())
        if not part.initialized:
            part.direction, part.distance = default_direction, default_distance
            part.initialized = True
        candidates = requests.get(name, ())
        selected, request = (
            min(reversed(candidates), key=lambda item: item[1].priority)
            if candidates
            else ("", None)
        )
        soft_reached = False
        for dt in intervals:
            targets = {}
            live_keys = {key for key, _ in candidates}
            part.following = {
                key: value for key, value in part.following.items() if key in live_keys
            }
            for key, candidate in candidates:
                direction, distance = to_sphere(candidate.target)
                prior = part.following.get(key)
                if prior is not None:
                    old, behind, delay = prior
                    pitch, yaw = direction_delta(old, direction)
                    angle = math.hypot(pitch, yaw)
                    new_behind = angle > 270.0
                    if behind and not new_behind:
                        delay = 5.0
                    if new_behind and delay > 0:
                        direction = rotate_direction(
                            (0.0, 1.0, 0.0),
                            direction_angles(direction)[0],
                            direction_angles(old)[1],
                        )
                        pitch, yaw = direction_delta(old, direction)
                        angle = math.hypot(pitch, yaw)
                    curve = config.get("followingSpeedByAngleCurve", {})
                    curve = dict(
                        curve,
                        elements=[
                            {"Point": p, "Value": v}
                            for p, v in curve.get("elements", ())
                        ],
                    )
                    speed = config["followingSpeedFactor"] * sample_curve(curve, angle)
                    direction = (
                        interpolate_direction(
                            old, direction, min(1.0, dt * speed / angle)
                        )
                        if angle > 1e-9
                        else direction
                    )
                    behind, delay = new_behind, max(0.0, delay - dt)
                else:
                    behind, delay = False, 0.0
                part.following[key] = (direction, behind, delay)
                pitch, yaw = direction_angles(direction)
                limit = candidate.soft_limit * 0.5
                limited = abs(pitch) > limit or abs(yaw) > limit
                if limited:
                    direction = rotate_direction(
                        (0.0, 1.0, 0.0),
                        max(-limit, min(limit, pitch)),
                        max(-limit, min(limit, yaw)),
                    )
                targets[key] = direction, distance, limited
            destination, distance, soft_reached = (
                targets[selected]
                if request
                else (default_direction, default_distance, False)
            )
            if part.selected != selected:
                part.previous = (
                    part.direction,
                    part.distance,
                    part.active_weight,
                    part.suppress,
                    part.mode,
                )
                pitch, yaw = direction_delta(part.direction, destination)
                speed = (
                    request.transition_speed if request else part.out_speed
                ) * config["transitionSpeedMultiplier"]
                if speed <= 0:
                    raise ValueError(
                        "Look-at transition speed multiplier must be positive"
                    )
                part.duration = max(30.0, math.hypot(pitch, yaw)) / speed
                part.elapsed = 0.0
                part.selected = selected
                if request:
                    part.out_speed = request.out_transition_speed
                state.transition_serial += 1
                state.transition_duration, state.transition_pitch = part.duration, pitch
            part.elapsed = min(part.duration, part.elapsed + dt)
            t = part.elapsed / part.duration
            weight = t * t * t * (10.0 + t * (-15.0 + 6.0 * t))
            previous = part.previous
            if previous is None or weight == 1:
                part.direction, part.distance = destination, distance
                part.active_weight, part.suppress = (
                    float(bool(request)),
                    request.suppress if request else 0.0,
                )
                part.mode = request.mode if request else part.mode
                part.previous = None
            else:
                part.direction = interpolate_direction(previous[0], destination, weight)
                part.distance = previous[1] + weight * (distance - previous[1])
                part.active_weight = previous[2] + weight * (
                    float(bool(request)) - previous[2]
                )
                part.suppress = previous[3] + weight * (
                    (request.suppress if request else 0.0) - previous[3]
                )
                part.mode = (
                    (request.mode if request else part.mode)
                    if weight >= 0.5
                    else previous[4]
                )
        enable = float(tracks.get(config.get("enableFloatTrack", ""), 1.0))
        if name == "Eyes" and data.get("isFacial"):
            enable = min(
                float(eyes_enabled),
                1.0 - float(tracks.get(config.get("eyesOverrideFloatTrack", ""), 0.0)),
            )
        enable = max(0.0, min(1.0, enable))
        direction = interpolate_direction(default_direction, part.direction, enable)

        def to_model(value):
            rotated = rotate_vector_scalar_xyzw(
                rotation, tuple(v * part.distance for v in unit_direction(value))
            )
            return tuple(a + b for a, b in zip(center, rotated))

        output[(name, "isEnabled")] = bool(candidates) or part.active_weight > 0
        output[(name, "target")] = to_model(direction)
        output[(name, "rawTarget")] = to_model(part.direction)
        output[(name, "distance")] = part.distance
        output[(name, "suppress")] = part.suppress * enable
        output[(name, "mode")] = part.mode
        output[(name, "blendWeight")] = (
            1.0 - (1.0 - part.active_weight * enable) ** config["blendWeightPowFactor"]
        )
        status_track = config.get("coneLimitReached", "")
        if status_track in tracks:
            tracks[status_track] = float(
                int(tracks[status_track])
                | 2
                | (4 if soft_reached else 0)
                | (8 if part.elapsed < part.duration else 0)
            )
    if data.get("isFacial"):
        output[("lookAt", "lookAtTransitionDuration")] = state.transition_duration
        output[("lookAt", "lookAtTransitionPitch")] = state.transition_pitch
    state.was_enabled_previous_frame = state.enabled
    return output
