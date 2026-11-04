from __future__ import annotations

import logging
import math
from copy import copy

import numpy as np

from ....bartmoss.curve import centered_convolve
from ....core.log import get_logger
from ...domain.jali.acoustic import AcousticAnalyzer
from ...domain.jali.bridge import JALIToCp77Bridge, viseme_timing
from ...domain.jali.capability import dependency_status, parselmouth
from ...domain.jali.coarticulation import CoarticulationEngine
from ...domain.jali.curves import DominanceBlender

_LOG = get_logger(__name__)


class JALIAnimationPipeline:
    def __init__(self, rig, setup, fps: float = 30.0):
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Frame rate must be finite and positive")
        self.rig = rig
        self.setup = setup
        self.fps = fps
        self.coarticulator = CoarticulationEngine()
        self.blender = DominanceBlender(fps=fps, timing=viseme_timing())
        self.bridge = JALIToCp77Bridge()
        self.used_viseme_targets = False
        # What the last generate_animation call had to approximate, for the caller to report.
        self.warnings: list[str] = []

    def generate_animation(
        self, phoneme_events: list, audio_path: str | None = None
    ) -> np.ndarray:
        if not phoneme_events:
            raise ValueError("No phoneme events provided")
        if any(
            not math.isfinite(event.start)
            or not math.isfinite(event.end)
            or event.end < event.start
            for event in phoneme_events
        ):
            raise ValueError("Phoneme intervals must be finite and ordered")
        phoneme_events = [copy(event) for event in phoneme_events]
        self.warnings = []
        duration = phoneme_events[-1].end + 0.5
        unique = set(
            e.phoneme for e in phoneme_events if e.phoneme not in ("SIL", "SP")
        )
        has_real_phonemes = len(unique) > 2
        track_names = [
            str(n) if not isinstance(n, dict) else n.get("$value", "")
            for n in self.rig.track_names
        ]
        num_tracks = len(track_names)
        reference_tracks = getattr(self.rig, "reference_tracks", None)
        self.used_viseme_targets = has_real_phonemes
        if has_real_phonemes:
            events = self._articulate(phoneme_events, audio_path)
            _LOG.debug("Stage 3: Calibrated viseme targets (dominance blending)...")
            tracks = self.bridge.viseme_tracks(
                events,
                duration,
                self.blender,
                track_names,
                reference_tracks=reference_tracks,
            )
        else:
            ja_curve, li_curve = self._curves_from_audio(
                phoneme_events, audio_path, duration
            )
            _LOG.debug("Stage 4: JALI  -> CP77 track mapping...")
            tracks = self.bridge.jali_to_tracks(
                ja_curve,
                li_curve,
                track_names,
                reference_tracks=reference_tracks,
            )
        non_zero = int(np.sum(np.max(np.abs(tracks), axis=0) > 0.001))
        _LOG.info(
            "JALI processing complete: active_tracks=%d/%d frames=%d",
            non_zero,
            num_tracks,
            tracks.shape[0],
        )
        return tracks

    def _articulate(self, events, audio_path):
        _LOG.debug("Mode: Phoneme-based (dominance blending)")
        _LOG.debug("Stage 1: Co-articulation...")
        events = self.coarticulator.apply_rules(events)
        if audio_path:
            _LOG.debug("Stage 2: Acoustic modulation...")
            try:
                analyzer = AcousticAnalyzer(audio_path)
                events = analyzer.modulate_events(events)
            except (ImportError, OSError, RuntimeError, ValueError) as error:
                self.warnings.append(
                    f"Acoustic analysis failed, so jaw and lip intensities are not shaped by the audio ({error})"
                )
            else:
                self.warnings.extend(analyzer.warnings)
        return events

    def _curves_from_audio(self, events, audio_path, duration):
        _LOG.debug("Mode: Acoustic-only (amplitude/pitch)")
        num_frames = int(duration * self.fps) + 1
        times = np.linspace(0, duration, num_frames, dtype=np.float32)
        sounding = np.zeros(num_frames, dtype=bool)
        for ev in events:
            if ev.phoneme not in ("SIL", "SP"):
                s = max(0, int(ev.start * self.fps))
                e = min(int(ev.end * self.fps) + 1, num_frames)
                sounding[s:e] = True
        ja = np.zeros(num_frames, dtype=np.float32)
        li = np.zeros(num_frames, dtype=np.float32)
        if not audio_path:
            ja[sounding] = 0.4
            return (ja, li)
        if not dependency_status().parselmouth:
            self.warnings.append(
                "parselmouth is unavailable, so the jaw opens uniformly wherever there is sound"
            )
            ja[sounding] = 0.4
            return (ja, li)
        sound = parselmouth.Sound(audio_path)
        intensity = sound.to_intensity(time_step=0.01)
        pitch = sound.to_pitch(time_step=0.01)
        int_vals, pitch_vals = ([], [])
        samples = [
            (intensity.get_value(float(t)), pitch.get_value_at_time(float(t)))
            for t in times[sounding]
        ]
        for iv, pv in samples:
            if not math.isnan(iv):
                int_vals.append(iv)
            if not math.isnan(pv) and pv > 0:
                pitch_vals.append(pv)
        int_mean = np.mean(int_vals) if int_vals else 60.0
        int_std = max(np.std(int_vals), 1.0) if int_vals else 10.0
        pitch_mean = np.mean(pitch_vals) if pitch_vals else 150.0
        pitch_std = max(np.std(pitch_vals), 10.0) if pitch_vals else 50.0
        _LOG.debug("Intensity: mean=%.1f std=%.1f", int_mean, int_std)
        _LOG.debug("Pitch: mean=%.1f std=%.1f", pitch_mean, pitch_std)
        for i, (iv, pv) in zip(np.flatnonzero(sounding), samples):
            if not math.isnan(iv):
                z = (iv - int_mean) / int_std
                ja[i] = float(np.clip(0.3 + 0.35 * z, 0.05, 1.0))
            else:
                ja[i] = 0.3
            if not math.isnan(pv) and pv > 0:
                z = (pv - pitch_mean) / pitch_std
                li[i] = float(np.clip(0.3 * z, -0.8, 0.8))
        kernel = np.ones(5) / 5.0
        ja = centered_convolve(ja, kernel).astype(np.float32)
        li = centered_convolve(li, kernel).astype(np.float32)
        ja[~sounding] = 0.0
        li[~sounding] = 0.0
        if _LOG.isEnabledFor(logging.DEBUG):
            if np.any(sounding):
                _LOG.debug(
                    "JA range: %.3f – %.3f",
                    ja[sounding].min(),
                    ja[sounding].max(),
                )
                _LOG.debug(
                    "LI range: %.3f – %.3f",
                    li[sounding].min(),
                    li[sounding].max(),
                )
            else:
                _LOG.debug("JALI ranges unavailable: no sounding frames")
        return (ja, li)
