from __future__ import annotations

import math
from typing import List, Optional

import numpy as np

from .acoustic import AcousticAnalyzer
from .bridge import JALIToCp77Bridge
from .capability import dependency_status, parselmouth
from .coarticulation import CoarticulationEngine
from .curves import DominanceBlender

class JALIAnimationPipeline:

    def __init__(self, rig, setup, fps: float=30.0):
        self.rig = rig
        self.setup = setup
        self.fps = fps
        self.coarticulator = CoarticulationEngine()
        self.blender = DominanceBlender(fps=fps, tau=0.07)
        self.bridge = JALIToCp77Bridge()

    def generate_animation(self, phoneme_events: List, audio_path: Optional[str]=None) -> np.ndarray:
        if not phoneme_events:
            raise ValueError('No phoneme events provided')
        duration = phoneme_events[-1].end + 0.5
        unique = set((e.phoneme for e in phoneme_events if e.phoneme not in ('SIL', 'SP')))
        has_real_phonemes = len(unique) > 2
        if has_real_phonemes:
            ja_curve, li_curve = self._curves_from_phonemes(phoneme_events, audio_path, duration)
        else:
            ja_curve, li_curve = self._curves_from_audio(phoneme_events, audio_path, duration)
        print('[JALI] Stage 4: JALI  -> CP77 track mapping...')
        track_names = [str(n) if not isinstance(n, dict) else n.get('$value', '') for n in self.rig.track_names]
        num_tracks = len(track_names)
        tracks = self.bridge.jali_to_tracks(ja_curve, li_curve, track_names)
        if has_real_phonemes:
            print('[JALI] Stage 5: Phoneme overrides...')
            tracks = self.bridge.add_phoneme_overrides(tracks, phoneme_events, track_names, self.fps)
        non_zero = int(np.sum(np.max(np.abs(tracks), axis=0) > 0.001))
        print(f'[JALI] Complete — {non_zero}/{num_tracks} active tracks, {tracks.shape[0]} frames')
        return tracks

    def _curves_from_phonemes(self, events, audio_path, duration):
        print('[JALI] Mode: Phoneme-based (dominance blending)')
        print('[JALI] Stage 1: Co-articulation...')
        events = self.coarticulator.apply_rules(events)
        if audio_path:
            print('[JALI] Stage 2: Acoustic modulation...')
            try:
                analyzer = AcousticAnalyzer(audio_path)
                events = analyzer.modulate_events(events)
            except (ImportError, OSError, RuntimeError, ValueError) as error:
                print(f'[JALI] Warning: Acoustic analysis failed: {error}')
        print('[JALI] Stage 3: Dominance blending...')
        _times, ja, li = self.blender.blend_jali_parameters(events, duration)
        return (ja, li)

    def _curves_from_audio(self, events, audio_path, duration):
        print('[JALI] Mode: Acoustic-only (amplitude/pitch)')
        num_frames = int(duration * self.fps) + 1
        times = np.linspace(0, duration, num_frames, dtype=np.float32)
        sounding = np.zeros(num_frames, dtype=bool)
        for ev in events:
            if ev.phoneme not in ('SIL', 'SP'):
                s = max(0, int(ev.start * self.fps))
                e = min(int(ev.end * self.fps) + 1, num_frames)
                sounding[s:e] = True
        ja = np.zeros(num_frames, dtype=np.float32)
        li = np.zeros(num_frames, dtype=np.float32)
        if not audio_path:
            ja[sounding] = 0.4
            return (ja, li)
        if not dependency_status().parselmouth:
            print('[JALI]   No parselmouth — uniform fallback')
            ja[sounding] = 0.4
            return (ja, li)
        sound = parselmouth.Sound(audio_path)
        intensity = sound.to_intensity(time_step=0.01)
        pitch = sound.to_pitch(time_step=0.01)
        int_vals, pitch_vals = ([], [])
        for t in times[sounding]:
            iv = intensity.get_value(float(t))
            pv = pitch.get_value_at_time(float(t))
            if not math.isnan(iv):
                int_vals.append(iv)
            if not math.isnan(pv) and pv > 0:
                pitch_vals.append(pv)
        int_mean = np.mean(int_vals) if int_vals else 60.0
        int_std = max(np.std(int_vals), 1.0) if int_vals else 10.0
        pitch_mean = np.mean(pitch_vals) if pitch_vals else 150.0
        pitch_std = max(np.std(pitch_vals), 10.0) if pitch_vals else 50.0
        print(f'[JALI]   Intensity: mean={int_mean:.1f} std={int_std:.1f}')
        print(f'[JALI]   Pitch: mean={pitch_mean:.1f} std={pitch_std:.1f}')
        for i, t in enumerate(times):
            if not sounding[i]:
                continue
            iv = intensity.get_value(float(t))
            pv = pitch.get_value_at_time(float(t))
            if not math.isnan(iv):
                z = (iv - int_mean) / int_std
                ja[i] = float(np.clip(0.3 + 0.35 * z, 0.05, 1.0))
            else:
                ja[i] = 0.3
            if not math.isnan(pv) and pv > 0:
                z = (pv - pitch_mean) / pitch_std
                li[i] = float(np.clip(0.3 * z, -0.8, 0.8))
        kernel = np.ones(5) / 5.0
        ja = np.convolve(ja, kernel, mode='same').astype(np.float32)
        li = np.convolve(li, kernel, mode='same').astype(np.float32)
        ja[~sounding] = 0.0
        li[~sounding] = 0.0
        print(f'[JALI]   JA range: {ja[sounding].min():.3f} – {ja[sounding].max():.3f}')
        print(f'[JALI]   LI range: {li[sounding].min():.3f} – {li[sounding].max():.3f}')
        return (ja, li)
