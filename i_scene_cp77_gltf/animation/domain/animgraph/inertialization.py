from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ....bartmoss.dynamics import quintic_decay
from ....bartmoss.quaternion import product_rows_xyzw
from ....redSpace.euler import euler_from_xyzw, xyzw_from_euler
from ...model.animgraph.indices import index_name

CACHED_POSES = 2
_EPSILON = 1e-6


def normalize_float_clamp(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, Mapping) else {}
    return {
        "isActive": bool(data.get("isActive", False)),
        "min": float(data.get("min", 0.0) or 0.0),
        "max": float(data.get("max", 0.0) or 0.0),
    }


def _clamp(value: float, data: Mapping[str, Any]) -> float:
    if not data.get("isActive"):
        return value
    return min(max(value, float(data["min"])), float(data["max"]))


@dataclass
class InertializationState:
    cached: list = field(
        default_factory=list
    )  # oldest first: (translations, rotations, tracks)
    last_dt: float = 0.0
    current_dt: float = 0.0
    elapsed: float = 0.0
    in_progress: bool = False
    requested: bool = False
    duration: float = 0.0
    errors: dict = field(default_factory=dict)

    def reset(self) -> None:
        self.cached.clear()
        self.last_dt = self.current_dt = self.elapsed = self.duration = 0.0
        self.in_progress = self.requested = False
        self.errors = {}


def update(
    state: InertializationState, dt: float, requested: bool, request_duration: float
) -> None:
    """Track time steps and latch this frame's request"""
    state.last_dt = state.current_dt if state.cached else float(dt)
    state.current_dt = float(dt)
    if requested:
        # Default blend-override mode: a new request replaces the running one.
        state.duration = float(request_duration)
    state.requested = bool(requested)


def _velocity(pre: np.ndarray, value: np.ndarray, dt: float, safe: bool) -> np.ndarray:
    velocity = (value - pre) / dt if dt > 0.0 else np.zeros_like(value)
    if safe:
        velocity = np.where(velocity * value >= 0.0, 0.0, velocity)
    return velocity


def _initial_errors(
    state: InertializationState, translations, rotations, tracks, safe: bool
) -> None:
    (pre_t, pre_r, pre_k), (last_t, last_r, last_k) = state.cached[-2], state.cached[-1]
    n = min(len(pre_t), len(last_t), len(translations))
    m = min(len(pre_k), len(last_k), len(tracks))
    cur_t, cur_r = translations[:n], rotations[:n]
    dt = state.last_dt

    diff_last = last_t[:n] - cur_t
    diff_pre = pre_t[:n] - cur_t
    magnitude = np.linalg.norm(diff_last, axis=1)
    moving = magnitude > _EPSILON
    direction = np.zeros_like(diff_last)
    direction[moving] = diff_last[moving] / magnitude[moving, None]
    magnitude = np.where(moving, magnitude, 0.0)
    pre_moving = np.linalg.norm(diff_pre, axis=1) > _EPSILON
    pre_magnitude = np.where(
        moving & pre_moving, np.einsum("ij,ij->i", diff_pre, direction), 0.0
    )

    # Rotation error: diff = previous * conjugate(current), as axis and angle.
    conj = cur_r * np.array((-1.0, -1.0, -1.0, 1.0))

    identity = np.array((0.0, 0.0, 0.0, 1.0))
    same_last = np.all(np.abs(last_r[:n] - cur_r) <= _EPSILON, axis=1)
    same_pre = np.all(np.abs(pre_r[:n] - cur_r) <= _EPSILON, axis=1)
    diff_last_r = np.where(
        same_last[:, None], identity, product_rows_xyzw(last_r[:n], conj)
    )
    diff_pre_r = np.where(
        same_pre[:, None], identity, product_rows_xyzw(pre_r[:n], conj)
    )
    w = np.clip(diff_last_r[:, 3], -1.0, 1.0)
    angle = 2.0 * np.arccos(w)
    sine = np.sqrt(np.maximum(0.0, 1.0 - w * w))
    axis = np.tile(np.array((1.0, 0.0, 0.0)), (n, 1))
    turning = sine > _EPSILON
    axis[turning] = diff_last_r[turning, :3] / sine[turning, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        pre_angle = 2.0 * np.arctan(
            np.einsum("ij,ij->i", diff_pre_r[:, :3], axis) / diff_pre_r[:, 3]
        )
    pre_angle = np.where(np.isfinite(pre_angle), pre_angle, 0.0)

    diff_track = last_k[:m] - tracks[:m]
    diff_pre_track = pre_k[:m] - tracks[:m]
    track_error = np.where(np.abs(diff_track) > _EPSILON, diff_track, 0.0)
    pre_track = np.where(
        (np.abs(diff_track) > _EPSILON) & (np.abs(diff_pre_track) > _EPSILON),
        diff_pre_track,
        0.0,
    )

    state.errors = {
        "direction": direction,
        "translation": magnitude,
        "translation_velocity": _velocity(pre_magnitude, magnitude, dt, safe),
        "axis": axis,
        "angle": angle,
        "angle_velocity": _velocity(pre_angle, angle, dt, safe),
        "track": track_error,
        "track_velocity": _velocity(pre_track, track_error, dt, safe),
    }


def _blend_durations(
    duration: float, error: np.ndarray, velocity: np.ndarray, safe: bool
) -> np.ndarray:
    result = np.full(error.shape, float(duration))
    if safe:
        moving = np.abs(velocity) > _EPSILON
        with np.errstate(divide="ignore", invalid="ignore"):
            limit = np.where(
                moving, -5.0 * error / np.where(moving, velocity, 1.0), np.inf
            )
        result = np.minimum(result, limit)
    return result


def _apply(
    state: InertializationState, translations, rotations, tracks, data, names
) -> None:
    errors = state.errors
    safe = bool(data.get("safeMode", False))
    t = state.elapsed
    n = min(len(translations), len(errors["translation"]))
    m = min(len(tracks), len(errors["track"]))

    durations = _blend_durations(
        state.duration,
        errors["translation"][:n],
        errors["translation_velocity"][:n],
        safe,
    )
    active = t < durations
    if np.any(active):
        amount = quintic_decay(
            errors["translation"][:n],
            errors["translation_velocity"][:n],
            durations,
            t,
            safe,
        )
        translations[:n][active] += (
            errors["direction"][:n][active] * amount[active, None]
        )

    durations = _blend_durations(
        state.duration, errors["angle"][:n], errors["angle_velocity"][:n], safe
    )
    active = t < durations
    if np.any(active):
        amount = quintic_decay(
            errors["angle"][:n], errors["angle_velocity"][:n], durations, t, safe
        )
        half = 0.5 * amount[active]
        offset = np.concatenate(
            (errors["axis"][:n][active] * np.sin(half)[:, None], np.cos(half)[:, None]),
            axis=1,
        )
        current = rotations[:n][active]
        ox, oy, oz, ow = offset.T
        cx, cy, cz, cw = current.T
        rotations[np.flatnonzero(active)] = np.stack(
            (
                ow * cx + ox * cw + oy * cz - oz * cy,
                ow * cy - ox * cz + oy * cw + oz * cx,
                ow * cz + ox * cy - oy * cx + oz * cw,
                ow * cw - ox * cx - oy * cy - oz * cz,
            ),
            axis=1,
        )

    durations = _blend_durations(
        state.duration, errors["track"][:m], errors["track_velocity"][:m], safe
    )
    active = t < durations
    if np.any(active):
        amount = quintic_decay(
            errors["track"][:m], errors["track_velocity"][:m], durations, t, safe
        )
        tracks[:m][active] += amount[active]

    for limit in data.get("rotationLimits", ()) or ():
        name = str(limit.get("constrainedTransform", "") or "")
        if name not in names:
            continue
        index = names.index(name)
        pitch, roll, yaw = euler_from_xyzw(rotations[index])
        rotations[index] = xyzw_from_euler(
            _clamp(pitch, limit["limitOnX"]),
            _clamp(roll, limit["limitOnY"]),
            _clamp(yaw, limit["limitOnZ"]),
        )


def sample(
    state: InertializationState,
    translations: np.ndarray,
    rotations: np.ndarray,
    tracks: np.ndarray,
    data: Mapping[str, Any],
    names: Sequence[str] = (),
):
    """Sampling on arrays (rig order, already capped). Returns the arrays it modified"""
    norms = np.linalg.norm(rotations, axis=1, keepdims=True)
    rotations = np.where(
        norms > 1e-30,
        rotations / np.where(norms > 1e-30, norms, 1.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    while len(state.cached) < CACHED_POSES:
        state.cached.append((translations.copy(), rotations.copy(), tracks.copy()))
    if state.requested:
        state.elapsed = 0.0
        state.in_progress = True
        _initial_errors(
            state, translations, rotations, tracks, bool(data.get("safeMode", False))
        )
    if state.in_progress:
        state.elapsed += state.current_dt
        if state.elapsed >= state.duration:
            state.in_progress = False
        else:
            _apply(state, translations, rotations, tracks, data, list(names))
    state.cached.append((translations.copy(), rotations.copy(), tracks.copy()))
    del state.cached[:-CACHED_POSES]
    return translations, rotations, tracks


def inertialization_data(node):
    return {
        "safeMode": bool(node.get("safeMode", False)),
        "transformsCountUpperBound": int(node.get("transformsCountUpperBound", 0) or 0),
        "tracksCountUpperBound": int(node.get("tracksCountUpperBound", 0) or 0),
        "rotationLimits": tuple(
            {
                "constrainedTransform": index_name(
                    raw.get("constrainedTransform"),
                    "animTransformIndex",
                    allow_text=True,
                ),
                "limitOnX": normalize_float_clamp(raw.get("limitOnX")),
                "limitOnY": normalize_float_clamp(raw.get("limitOnY")),
                "limitOnZ": normalize_float_clamp(raw.get("limitOnZ")),
            }
            for raw in node.get("rotationLimits") or ()
            if isinstance(raw, Mapping)
        ),
    }
