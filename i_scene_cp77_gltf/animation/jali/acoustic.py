from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from .capability import call, dependency_status, parselmouth
from .events import create_phoneme_event
from .model import PhonemeEvent

class AcousticAnalyzer:

    def __init__(self, audio_path: str):
        if not dependency_status().parselmouth:
            raise ImportError('Install parselmouth: pip install praat-parselmouth')
        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()
        self.pitch = self.sound.to_pitch()
        self.intensity = self.sound.to_intensity()
        try:
            self.hf_sound = call(self.sound, 'Filter (pass Hann band)', 8000, 20000, 100)
            self.hf_intensity = self.hf_sound.to_intensity()
        except Exception:
            self.hf_intensity = None

    @staticmethod
    def _bucket(z: float, low: Tuple[float, float], mid: Tuple[float, float], high: Tuple[float, float]) -> float:
        if z <= -1.0:
            return (low[0] + low[1]) * 0.5
        elif z >= 1.0:
            return (high[0] + high[1]) * 0.5
        else:
            t = (z + 1.0) * 0.5
            return mid[0] + t * (mid[1] - mid[0])

    def modulate_events(self, events: List[PhonemeEvent]) -> List[PhonemeEvent]:
        PLOSIVES = frozenset({'P', 'B', 'D', 'T', 'G', 'K'})
        FRICATIVES = frozenset({'S', 'Z', 'SH', 'ZH', 'F', 'V', 'TH', 'DH'})
        vowel_intensities, vowel_pitches = ([], [])
        fric_plos_hf = []
        for ev in events:
            p = ev.phoneme.rstrip('012')
            t_mid = (ev.start + ev.end) * 0.5
            if ev.is_vowel and ev.lexically_stressed:
                vol = self.intensity.get_value(t_mid)
                f0 = self.pitch.get_value_at_time(t_mid)
                if not math.isnan(vol):
                    vowel_intensities.append(vol)
                if not math.isnan(f0) and f0 > 0:
                    vowel_pitches.append(f0)
            elif (p in FRICATIVES or p in PLOSIVES) and self.hf_intensity is not None:
                hf = self.hf_intensity.get_value(t_mid)
                if not math.isnan(hf):
                    fric_plos_hf.append(hf)
        v_int_mean = np.mean(vowel_intensities) if vowel_intensities else 60.0
        v_int_std = max(np.std(vowel_intensities), 1.0) if vowel_intensities else 10.0
        v_p_mean = np.mean(vowel_pitches) if vowel_pitches else 150.0
        v_p_std = max(np.std(vowel_pitches), 10.0) if vowel_pitches else 50.0
        hf_mean = np.mean(fric_plos_hf) if fric_plos_hf else 30.0
        hf_std = max(np.std(fric_plos_hf), 1.0) if fric_plos_hf else 10.0
        stressed_vowel_indices = {i for i, ev in enumerate(events) if ev.is_vowel and ev.lexically_stressed}
        adjacent_to_stressed = set()
        for idx in stressed_vowel_indices:
            if idx > 0:
                adjacent_to_stressed.add(idx - 1)
            if idx < len(events) - 1:
                adjacent_to_stressed.add(idx + 1)
        MID_INTENSITY = 0.45
        for i, event in enumerate(events):
            t_mid = (event.start + event.end) * 0.5
            p = event.phoneme.rstrip('012')
            if event.is_vowel and event.lexically_stressed:
                vol = self.intensity.get_value(t_mid)
                f0 = self.pitch.get_value_at_time(t_mid)
                z_int = 0.0
                if not math.isnan(vol):
                    z_int = (vol - v_int_mean) / (v_int_std + 1e-06)
                    ja_intensity = self._bucket(z_int, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9))
                    event.jaw *= ja_intensity / MID_INTENSITY
                    event.jaw = min(event.jaw, 1.0)
                if not math.isnan(f0) and f0 > 0:
                    z_pitch = (f0 - v_p_mean) / (v_p_std + 1e-06)
                    z_combined = max(z_int, z_pitch)
                    li_intensity = self._bucket(z_combined, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9))
                    scale = li_intensity / MID_INTENSITY
                    event.lip *= scale
                    event.lip = max(-1.0, min(1.0, event.lip))
            elif (p in FRICATIVES or p in PLOSIVES) and i in adjacent_to_stressed:
                if self.hf_intensity is not None:
                    hf = self.hf_intensity.get_value(t_mid)
                    if not math.isnan(hf):
                        z_hf = (hf - hf_mean) / (hf_std + 1e-06)
                        hf_intensity = self._bucket(z_hf, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9))
                        scale = hf_intensity / MID_INTENSITY
                        event.lip *= scale
                        event.lip = max(-1.0, min(1.0, event.lip))
        return events

    def get_amplitude_factor(self, time: float) -> float:
        try:
            intensity = self.intensity.get_value(time)
            if math.isnan(intensity):
                return 0.5
            return float(np.clip((intensity - 50.0) / 40.0, 0.0, 1.5))
        except Exception:
            return 0.5

    def get_pitch_factor(self, time: float) -> float:
        try:
            p = self.pitch.get_value_at_time(time)
            if math.isnan(p) or p <= 0:
                return 0.0
            return float(np.clip((p - 150) / 200, -0.5, 0.5))
        except Exception:
            return 0.0

class AcousticPhonemeDetector:

    def __init__(self, audio_path: str):
        if not dependency_status().parselmouth:
            raise ImportError('Install parselmouth: pip install praat-parselmouth')
        self.audio_path = audio_path
        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()

    def detect_phonemes(self) -> List[PhonemeEvent]:
        intensity = self.sound.to_intensity()
        textgrid = call(intensity, 'To TextGrid (silences)', -25, 0.1, 0.05, 'silent', 'sounding')
        events: List[PhonemeEvent] = []
        num_intervals = call(textgrid, 'Get number of intervals', 1)
        for i in range(1, num_intervals + 1):
            label = call(textgrid, 'Get label of interval', 1, i)
            start = call(textgrid, 'Get start time of interval', 1, i)
            end = call(textgrid, 'Get end time of interval', 1, i)
            if label == 'silent':
                if end - start > 0.05:
                    events.append(create_phoneme_event('SIL', start, end))
                continue
            if end - start > 0.08:
                phoneme = self._classify_vowel(start, end)
            else:
                phoneme = self._classify_consonant(start, end)
            events.append(create_phoneme_event(phoneme, start, end))
        return events

    def _classify_vowel(self, start: float, end: float) -> str:
        t = (start + end) * 0.5
        try:
            formant = self.sound.to_formant_burg()
            f1 = call(formant, 'Get value at time', 1, t, 'Hertz', 'Linear')
            f2 = call(formant, 'Get value at time', 2, t, 'Hertz', 'Linear')
            if f1 > 700:
                return 'AA' if f2 < 1200 else 'AE'
            elif f1 > 500:
                return 'UH' if f2 < 1400 else 'EH'
            else:
                return 'UW' if f2 < 1800 else 'IY'
        except Exception:
            pass
        return 'AH'

    def _classify_consonant(self, start: float, end: float) -> str:
        import math
        t_mid = (start + end) * 0.5
        try:
            hf_sound = call(self.sound, 'Filter (pass Hann band)', 4000, 20000, 100)
            hf_intensity = hf_sound.to_intensity(minimum_pitch=50, time_step=0.001)
            hf_val = call(hf_intensity, 'Get value at time', t_mid, 'Cubic')
            overall = self.sound.to_intensity()
            overall_val = call(overall, 'Get value at time', t_mid, 'Cubic')
            if math.isnan(hf_val):
                hf_val = 0.0
            if math.isnan(overall_val):
                overall_val = 0.0
            if hf_val > overall_val - 15:
                return 'S'
            if overall_val < 40:
                return 'M'
        except Exception:
            pass
        return 'T'
