from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

NOT_CONSIDERED = "NotConsidered"
_LOOP_EPSILON = 0.01


@dataclass
class FootPhase:
    phase: str
    start: float
    end: float
    duration: float

    @property
    def looped(self) -> bool:
        return self.end < self.start


@dataclass(frozen=True)
class FootPhasePoint:
    time: float = 0.0
    duration: float = 1.0
    phase: str = NOT_CONSIDERED

    @property
    def progress(self) -> float:
        return self.time / self.duration if self.duration > 0.0 else 0.0


class FootPhaseTrack:
    def __init__(self, duration: float, events: Iterable[tuple[str, float, float]]):
        """events are (phase, start seconds, duration seconds) in clip order"""
        self.duration = float(duration)
        self.phases: list[FootPhase] = []
        for phase, start, length in events:
            if phase and phase != NOT_CONSIDERED:
                self.phases.append(
                    FootPhase(
                        phase, float(start), float(start) + float(length), float(length)
                    )
                )
        phases = self.phases
        if len(phases) > 2 and phases[0].phase == phases[-1].phase:
            first, last = phases[0], phases[-1]
            if (
                first.start < _LOOP_EPSILON
                and abs(last.end - self.duration) < _LOOP_EPSILON
            ):
                # The first phase wraps around the clip end.
                first.start = last.start
                if last.start + last.duration > self.duration:
                    last.duration = max(self.duration - last.start, 0.0)
                first.duration += last.duration
                phases.pop()
        for i in range(len(phases) - 1):
            current = phases[i]
            if (
                abs(current.end - phases[i + 1].start) > _LOOP_EPSILON
                or current.start < 0.0
                or (current.looped and i != 0)
            ):
                phases.clear()
                return
            if current.end > self.duration:
                current.end = self.duration
                current.duration = current.end - current.start
        phases.sort(key=lambda item: item.start)

    @property
    def ok(self) -> bool:
        return bool(self.phases)

    def sync_data(self, input_time: float) -> FootPhasePoint | None:
        """Phase and time into it at input_time"""
        phases = self.phases
        if not phases or self.duration <= 0.0:
            return None
        time = math.fmod(float(input_time), self.duration)
        end_index = 0
        first = phases[0]
        if first.looped:
            if first.start <= time:
                return FootPhasePoint(time - first.start, first.duration, first.phase)
            if time < first.end:
                return FootPhasePoint(
                    (self.duration - first.start) + time, first.duration, first.phase
                )
            end_index = 1
        for phase in reversed(phases[end_index:]):
            if phase.start <= time:
                return FootPhasePoint(time - phase.start, phase.duration, phase.phase)
        return None

    def sync_to_first(self, point: FootPhasePoint) -> float | None:
        """Time at the same progress through the first phase of the point's type"""
        phases = self.phases
        if not phases:
            return None
        start_index = 0
        first = phases[0]
        candidates = phases
        if first.looped:
            if first.phase == point.phase:
                return self._clamped(first.end + first.duration * point.progress)
            start_index = 1
        for phase in candidates[start_index:]:
            if phase.phase == point.phase:
                return self._clamped(phase.start + phase.duration * point.progress)
        return None

    def _clamped(self, value: float) -> float:
        # Past the clip end the result is -duration, which a clip's sync reads as its start.
        return 0.0 if value > self.duration else value


def foot_phase_synced_time(
    source: FootPhaseTrack | None,
    source_time: float,
    target: FootPhaseTrack | None,
) -> float:
    """Incoming clip time for animSyncMethodByFootPhase, or 0 when either clip has no usable phases"""
    if source is None or target is None:
        return 0.0
    point = source.sync_data(source_time)
    if point is None:
        return 0.0
    synced = target.sync_to_first(point)
    return 0.0 if synced is None else synced
