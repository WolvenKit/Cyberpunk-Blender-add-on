from __future__ import annotations

import numpy as np

from ....bartmoss.scalar import sin_squared_ease
from ...model.jali.events import PhonemeEvent

DEFAULT_TIMING = {
    "onset": 0.12,  # seconds of ramp-in before the apex
    "onset_lip_heavy": 0.15,
    "decay": 0.12,  # seconds of ramp-out after the sustain
    "decay_lip_heavy": 0.15,
    "apex": 0.0,  # apex position as a fraction of the phoneme's original span
    "sustain": 0.75,  # sustain end as a fraction of the phoneme's original span
}


class DominanceBlender:
    def __init__(self, fps: float = 30.0, timing=None):
        self.fps = fps
        # Calibrated envelope timing; None/empty keeps the original JALI constants exactly.
        self.timing = {**DEFAULT_TIMING, **timing} if timing else None

    def _bounds(self, event):
        is_lip_heavy = getattr(event, "is_lip_heavy", False)
        if self.timing is None:
            natural_onset = 0.15 if is_lip_heavy else 0.12
            natural_decay = 0.15 if is_lip_heavy else 0.12
            t_apex = event.apex
            t_sustain_end = event.sustain_end
        else:
            timing = self.timing
            natural_onset = (
                timing["onset_lip_heavy"] if is_lip_heavy else timing["onset"]
            )
            natural_decay = (
                timing["decay_lip_heavy"] if is_lip_heavy else timing["decay"]
            )
            if event.original_start >= 0 and event.original_end >= 0:
                span_start, span = (
                    event.original_start,
                    event.original_end - event.original_start,
                )
            else:
                span_start, span = event.start, event.duration
            t_apex = span_start + timing["apex"] * span
            t_sustain_end = max(t_apex, span_start + timing["sustain"] * span)
        natural_onset_start = t_apex - natural_onset
        t_onset_start = min(natural_onset_start, event.start)
        natural_decay_end = t_sustain_end + natural_decay
        t_decay_end = max(natural_decay_end, event.end)
        prev_pause_end = getattr(event, "prev_pause_end", float("-inf"))
        next_pause_start = getattr(event, "next_pause_start", float("inf"))
        t_onset_start = max(t_onset_start, prev_pause_end)
        t_decay_end = min(t_decay_end, next_pause_start)
        return t_onset_start, t_apex, t_sustain_end, t_decay_end

    def compute_dominance_curve(
        self, event: PhonemeEvent, times: np.ndarray
    ) -> np.ndarray:
        t_onset_start, t_apex, t_sustain_end, t_decay_end = self._bounds(event)
        onset_dur = max(t_apex - t_onset_start, 0.001)
        decay_dur = max(t_decay_end - t_sustain_end, 0.001)
        envelope = np.zeros_like(times)
        onset_mask = (times >= t_onset_start) & (times < t_apex)
        if onset_mask.any():
            progress = (times[onset_mask] - t_onset_start) / onset_dur
            envelope[onset_mask] = sin_squared_ease(progress)
        sustain_mask = (times >= t_apex) & (times <= t_sustain_end)
        envelope[sustain_mask] = 1.0
        decay_mask = (times > t_sustain_end) & (times <= t_decay_end)
        if decay_mask.any():
            progress = (times[decay_mask] - t_sustain_end) / decay_dur
            envelope[decay_mask] = np.cos(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2
        return envelope * event.dominance

    def _frame_times(self, duration: float) -> np.ndarray:
        return np.linspace(0, duration, int(duration * self.fps) + 1, dtype=np.float32)

    def _event_dominance(
        self, event: PhonemeEvent, times: np.ndarray
    ) -> tuple[slice, np.ndarray]:
        """The frames event can influence, as a slice of times, and its dominance over them"""
        onset, apex, sustain, decay = self._bounds(event)
        # Include every possible mask, including pause-truncated envelopes.
        left = np.searchsorted(
            times, np.float32(min(onset, apex, sustain)), side="left"
        )
        right = np.searchsorted(
            times, np.float32(max(apex, sustain, decay)), side="right"
        )
        span = slice(left, right)
        return span, self.compute_dominance_curve(event, times[span])

    def blend_event_values(
        self,
        events: list[PhonemeEvent],
        values: np.ndarray,
        duration: float,
        fallback: np.ndarray,
    ) -> np.ndarray:
        """Dominance-weighted average of one value row per event"""
        values = np.asarray(values, dtype=np.float64)
        times = self._frame_times(duration)
        weighted = np.zeros((len(times), values.shape[1]), dtype=np.float64)
        dominance_sum = np.zeros(len(times), dtype=np.float64)
        for event, row in zip(events, values):
            span, dominance = self._event_dominance(event, times)
            weighted[span] += dominance[:, None] * row[None, :]
            dominance_sum[span] += dominance
        blended = weighted / (dominance_sum[:, None] + 1e-08)
        blended[dominance_sum < 1e-06] = np.asarray(fallback, dtype=np.float64)
        return blended
