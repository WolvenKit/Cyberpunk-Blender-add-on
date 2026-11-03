from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from .topology import PreviewBoundary

WORKSPOT_FEATURE = "UpdateWorkspot"

FLAG_PAUSED = 1 << 1
FLAG_LOOPED = 1 << 4


@dataclass(frozen=True)
class WorkspotInputs:
    animation: str = ""
    record_id: int = 0
    update_counter: int = 0
    blend_time: float = 0.0
    forced_blend_in: float = 0.0
    force_anim_time: float = 0.0
    flags: int = 0
    time_scale: float = 1.0
    start_time: float | None = None

    @property
    def looped(self) -> bool:
        return bool(self.flags & FLAG_LOOPED)

    @property
    def paused(self) -> bool:
        return bool(self.flags & FLAG_PAUSED)


@dataclass
class WorkspotRecord:
    animation: str = ""
    record_id: int | None = None
    playback_counter: object = None
    time_scale: float = 1.0
    start_time: float = 0.0
    current_time: float = 0.0
    blend_time: float = 0.0
    looped: bool = False


@dataclass
class WorkspotHubState:
    clock: float = 0.0
    current: WorkspotRecord = field(default_factory=WorkspotRecord)
    next: WorkspotRecord = field(default_factory=WorkspotRecord)
    blend_weight: float = -1.0
    last_animation: str = ""
    implicit_counter: int = 0


def workspot_inputs(feature_values, cname_text) -> WorkspotInputs:
    """Preview feature values of the UpdateWorkspot group as hub inputs"""

    def value(name, default):
        return feature_values.get((WORKSPOT_FEATURE, name), default)

    start = value("animationStartTime", None)
    return WorkspotInputs(
        animation=cname_text(value("animName", "")),
        record_id=int(value("recordID", 0) or 0),
        update_counter=int(value("updateCounter", 0) or 0),
        blend_time=float(value("animBlendTime", 0.0) or 0.0),
        forced_blend_in=float(value("forcedBlendIn", 0.0) or 0.0),
        force_anim_time=float(value("forceAnimTime", 0.0) or 0.0),
        flags=int(value("boolsAsFlags", 0) or 0),
        time_scale=float(value("timeScale", 1.0)),
        start_time=None if start is None else float(start),
    )


def workspot_blending(weight: float) -> bool:
    """Whether the hub is cross-fading from its current to its next record"""
    return 0.0 <= weight < 1.0


def _activate(
    record: WorkspotRecord, inputs: WorkspotInputs, clock: float, counter
) -> None:
    record.animation = inputs.animation
    record.record_id = inputs.record_id
    record.playback_counter = counter
    record.time_scale = inputs.time_scale
    record.current_time = inputs.force_anim_time
    if inputs.start_time is not None:
        record.start_time = inputs.start_time
    elif inputs.time_scale != 0.0:
        record.start_time = clock - inputs.force_anim_time / inputs.time_scale
    else:
        record.start_time = clock
    record.blend_time = inputs.blend_time
    record.looped = inputs.looped


def _update(
    record: WorkspotRecord, inputs: WorkspotInputs, clock: float, duration: float
) -> None:
    if inputs.paused:
        record.start_time = clock - record.current_time
        return
    time = record.time_scale * (clock - record.start_time)
    if record.looped:
        record.current_time = (
            math.fmod(time, duration) if time > duration > 0.0 else time
        )
    else:
        record.current_time = min(time, duration)


def advance_workspot_hub(
    state: WorkspotHubState, inputs: WorkspotInputs, dt: float, duration_of
) -> None:
    """One hub update. duration_of(animation) is the clip length, or None when it is unavailable"""
    state.clock += max(0.0, float(dt))
    if inputs.animation != state.last_animation:
        state.implicit_counter += 1
        state.last_animation = inputs.animation
    counter = (inputs.update_counter, state.implicit_counter)

    current_duration = (
        duration_of(state.current.animation) if state.current.animation else None
    )
    if current_duration is not None:
        _update(state.current, inputs, state.clock, current_duration)
    next_duration = duration_of(state.next.animation) if state.next.animation else None
    if workspot_blending(state.blend_weight) and next_duration is not None:
        _update(state.next, inputs, state.clock, next_duration)

    if current_duration is None and inputs.animation:
        _activate(state.next, inputs, state.clock, counter)
        state.current = replace(state.next)
        state.blend_weight = -1.0
    else:
        same_playback = (
            state.next.record_id == inputs.record_id
            and state.next.playback_counter == counter
        )
        can_continue = (
            inputs.looped
            and state.current.animation == inputs.animation
            and state.next.time_scale == inputs.time_scale
        )
        if not (same_playback or can_continue):
            if inputs.forced_blend_in > 0.0:
                state.current.blend_time = state.next.blend_time = (
                    inputs.forced_blend_in
                )
            if state.blend_weight > 0.5:
                state.current = replace(state.next)
            _activate(state.next, inputs, state.clock, counter)
            state.blend_weight = 0.0

    if workspot_blending(state.blend_weight):
        blend_time = state.current.blend_time
        both_valid = (
            duration_of(state.current.animation) if state.current.animation else None
        ) is not None and (
            duration_of(state.next.animation) if state.next.animation else None
        ) is not None
        if blend_time > 0.0 and both_valid:
            state.blend_weight = min(
                1.0, max(0.0, (state.clock - state.next.start_time) / blend_time)
            )
        else:
            state.blend_weight = 1.0
    if state.blend_weight >= 1.0:
        state.current = replace(state.next)
        state.next.start_time = 0.0
        state.blend_weight = -1.0


def workspot_hub_data(node):
    if any(
        isinstance(link, Mapping) and link.get("node")
        for link in node.get("additionalLinks") or ()
    ):
        raise PreviewBoundary(
            "WorkspotHub additional workspot links are not implemented by Graph preview"
        )
    return {}
