from __future__ import annotations
from typing import List, Tuple
import numpy as np
from .model import PhonemeEvent

class DominanceBlender:

    def __init__(self, fps: float=30.0, tau: float=0.07):
        self.fps = fps

    def compute_dominance_curve(self, event: PhonemeEvent, times: np.ndarray) -> np.ndarray:
        is_lip_heavy = getattr(event, 'is_lip_heavy', False)
        natural_onset = 0.15 if is_lip_heavy else 0.12
        natural_decay = 0.15 if is_lip_heavy else 0.12
        t_apex = event.apex
        t_sustain_end = event.sustain_end
        natural_onset_start = t_apex - natural_onset
        t_onset_start = min(natural_onset_start, event.start)
        natural_decay_end = t_sustain_end + natural_decay
        t_decay_end = max(natural_decay_end, event.end)
        prev_pause_end = getattr(event, 'prev_pause_end', float('-inf'))
        next_pause_start = getattr(event, 'next_pause_start', float('inf'))
        if t_onset_start < prev_pause_end:
            t_onset_start = prev_pause_end
        if t_decay_end > next_pause_start:
            t_decay_end = next_pause_start
        onset_dur = max(t_apex - t_onset_start, 0.001)
        decay_dur = max(t_decay_end - t_sustain_end, 0.001)
        envelope = np.zeros_like(times)
        onset_mask = (times >= t_onset_start) & (times < t_apex)
        if onset_mask.any():
            progress = (times[onset_mask] - t_onset_start) / onset_dur
            envelope[onset_mask] = np.sin(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2
        sustain_mask = (times >= t_apex) & (times <= t_sustain_end)
        envelope[sustain_mask] = 1.0
        decay_mask = (times > t_sustain_end) & (times <= t_decay_end)
        if decay_mask.any():
            progress = (times[decay_mask] - t_sustain_end) / decay_dur
            envelope[decay_mask] = np.cos(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2
        return envelope * event.dominance

    def blend_jali_parameters(
            self, events: List[PhonemeEvent], duration: float
            ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        num_frames = int(duration * self.fps) + 1
        times = np.linspace(0, duration, num_frames, dtype=np.float32)
        jaw_weighted = np.zeros(num_frames, dtype=np.float64)
        lip_weighted = np.zeros(num_frames, dtype=np.float64)
        dominance_sum = np.zeros(num_frames, dtype=np.float64)
        for event in events:
            D = self.compute_dominance_curve(event, times)
            jaw_weighted += event.jaw * D
            lip_weighted += event.lip * D
            dominance_sum += D
        eps = 1e-08
        jaw_curve = jaw_weighted / (dominance_sum + eps)
        lip_curve = lip_weighted / (dominance_sum + eps)
        no_influence = dominance_sum < 1e-06
        jaw_curve[no_influence] = 0.0
        lip_curve[no_influence] = 0.0
        return (times, jaw_curve.astype(np.float32), lip_curve.astype(np.float32))
