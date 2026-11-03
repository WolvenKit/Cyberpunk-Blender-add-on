from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ....assetio.values import cname_or_empty


def normalize_facial_mixer(node: Mapping[str, Any]) -> Mapping[str, Any]:
    definitions = []
    for raw in node.get("lookAtDefinitions", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        definitions.append(
            {
                "animations": tuple(
                    name
                    for name in (
                        cname_or_empty(value)
                        for value in raw.get("animations", ()) or ()
                    )
                    if name
                ),
                "animDelay": float(raw.get("animDelay", 0.0) or 0.0),
                "minTransitionDuration": float(
                    raw.get("minTransitionDuration", 1.0) or 0.0
                ),
                "playAnimProbability": min(
                    1.0, max(0.0, float(raw.get("playAnimProbability", 1.0) or 0.0))
                ),
            }
        )
    definitions.sort(key=lambda item: item["minTransitionDuration"])
    return {
        "lookAtDefinitions": tuple(definitions),
        "debug": bool(node.get("debug", False)),
    }


@dataclass
class FacialMixerState:
    facial_idle_weight: float = 0.0
    scene_idle_active: bool = False
    scene_non_idle_active: bool = False
    active_layers: list[Any] = field(default_factory=list)
    look_at_animation: Any | None = None
    new_look_at_requested_update_id: int = 0
    look_at_delay: float = 0.0
    look_at_delay_adjust: float = 0.0
    update_id: int = 0
    pending_look_at: bool = True
    random_source: Any = field(default_factory=random.Random)

    def notify_look_at(self) -> None:
        self.pending_look_at = True
        self.look_at_delay_adjust = 0.0

    def clear(self) -> None:
        self.facial_idle_weight = 0.0
        self.scene_idle_active = False
        self.scene_non_idle_active = False
        self.active_layers.clear()
        self.look_at_animation = None
        self.new_look_at_requested_update_id = 0
        self.look_at_delay = 0.0
        self.look_at_delay_adjust = 0.0
        self.update_id = 0
        self.pending_look_at = True


@dataclass
class BlinkAnimation:
    name: str
    duration: float
    time: float = 0.0
    speed: float = 1.0


def advance_mixer(
    state: FacialMixerState,
    raw_dt: float,
    *,
    data=None,
    tracks=None,
    transition_duration=0.0,
    transition_pitch=0.0,
    animation_duration=None,
    sample_tracks=None,
) -> dict[str, float]:
    dt = max(0.0, float(raw_dt))
    if state.scene_idle_active or state.scene_non_idle_active:
        state.facial_idle_weight = min(1.0, state.facial_idle_weight + dt)
    else:
        state.facial_idle_weight = max(0.0, state.facial_idle_weight - dt)
    state.scene_non_idle_active = False
    if state.active_layers:
        raise ValueError(
            "FacialMixerSlot service-event layers require scene animation requests"
        )
    values = dict(tracks or {})
    blink_names = ("eye_l_blink", "eye_r_blink")
    definitions = (data or {}).get("lookAtDefinitions", ())
    if not definitions or not all(name in values for name in blink_names):
        return values
    state.update_id += 1
    if state.pending_look_at:
        state.new_look_at_requested_update_id = state.update_id + 2
        state.pending_look_at = False
    current = state.look_at_animation
    if (
        state.update_id == state.new_look_at_requested_update_id
        and transition_duration > 0
    ):
        if current is None or current.time >= current.duration:
            for definition in definitions:
                if transition_duration < definition["minTransitionDuration"]:
                    names = definition["animations"]
                    if (
                        names
                        and state.random_source.random()
                        < definition["playAnimProbability"]
                    ):
                        name = state.random_source.choice(names)
                        duration = (
                            float(animation_duration(name))
                            if animation_duration
                            else 0.0
                        )
                        if duration > 0:
                            current = BlinkAnimation(
                                name, duration, speed=duration / transition_duration
                            )
                            state.look_at_animation = current
                            state.look_at_delay = max(
                                0.0,
                                definition["animDelay"] * transition_duration
                                - max(0.0, transition_pitch) * 0.05
                                - state.look_at_delay_adjust,
                            )
                    break
    if current is not None and current.time < current.duration:
        if state.look_at_delay <= 0:
            current.time += dt * current.speed
        else:
            state.look_at_delay -= dt
        if (
            state.look_at_delay <= 0
            and current.time < current.duration
            and sample_tracks
        ):
            sampled = sample_tracks(current.name, current.time)
            for name in blink_names:
                value = float(sampled.get(name, 0.0))
                values[name] = max(values[name] + value, value)
    state.look_at_delay_adjust += dt
    return values
