from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ....core.log import debug_exception, get_logger
from ...model.jali.events import PhonemeEvent
from .capability import call, dependency_status, parselmouth
from .events import create_phoneme_event

_LOG = get_logger(__name__)


class AcousticAnalysisError(RuntimeError):
    """Praat could not measure any segment of the audio"""


def _describe(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


@dataclass
class _Tally:
    fallback: str
    attempts: int = 0
    failures: int = 0
    first_error: str = ""


class MeasurementFailures:
    """Counts the Praat measurements that failed during one analysis"""

    WARNING_RATIO = 0.05

    def __init__(self):
        self._tallies: dict[str, _Tally] = {}

    def record(
        self, measurement: str, fallback: str, error: BaseException | None = None
    ) -> None:
        tally = self._tallies.setdefault(measurement, _Tally(fallback))
        tally.attempts += 1
        if error is not None:
            tally.failures += 1
            tally.first_error = tally.first_error or _describe(error)

    def every_attempt_failed(self) -> bool:
        return bool(self._tallies) and all(
            tally.failures == tally.attempts for tally in self._tallies.values()
        )

    def first_error(self) -> str:
        return next(
            (
                tally.first_error
                for tally in self._tallies.values()
                if tally.first_error
            ),
            "",
        )

    def warnings(self) -> list[str]:
        return [
            f"Praat {measurement} failed for {tally.failures} of {tally.attempts} segments, so {tally.fallback} "
            f"({tally.first_error})"
            for measurement, tally in self._tallies.items()
            if tally.failures > tally.attempts * self.WARNING_RATIO
        ]


class AcousticAnalyzer:
    def __init__(self, audio_path: str):
        if not dependency_status().parselmouth:
            raise ImportError(
                f"parselmouth didn't load: {dependency_status().parselmouth_error}"
            )
        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()
        self.pitch = self.sound.to_pitch()
        self.intensity = self.sound.to_intensity()
        self.warnings: list[str] = []
        try:
            self.hf_sound = call(
                self.sound, "Filter (pass Hann band)", 8000, 20000, 100
            )
            self.hf_intensity = self.hf_sound.to_intensity()
        except Exception as error:
            debug_exception(_LOG, "Praat high-frequency intensity details")
            self.hf_intensity = None
            self.warnings.append(
                "Praat high-frequency analysis failed, so fricatives and plosives next to stressed vowels are not "
                f"shaped by the audio ({_describe(error)})"
            )

    @staticmethod
    def _bucket(
        z: float,
        low: tuple[float, float],
        mid: tuple[float, float],
        high: tuple[float, float],
    ) -> float:
        if z <= -1.0:
            return (low[0] + low[1]) * 0.5
        elif z >= 1.0:
            return (high[0] + high[1]) * 0.5
        else:
            t = (z + 1.0) * 0.5
            return mid[0] + t * (mid[1] - mid[0])

    def modulate_events(self, events: list[PhonemeEvent]) -> list[PhonemeEvent]:
        PLOSIVES = frozenset({"P", "B", "D", "T", "G", "K"})
        FRICATIVES = frozenset({"S", "Z", "SH", "ZH", "F", "V", "TH", "DH"})
        vowel_intensities, vowel_pitches = ([], [])
        fric_plos_hf = []
        for ev in events:
            p = ev.phoneme.rstrip("012")
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
        stressed_vowel_indices = {
            i for i, ev in enumerate(events) if ev.is_vowel and ev.lexically_stressed
        }
        adjacent_to_stressed = set()
        for idx in stressed_vowel_indices:
            if idx > 0:
                adjacent_to_stressed.add(idx - 1)
            if idx < len(events) - 1:
                adjacent_to_stressed.add(idx + 1)
        MID_INTENSITY = 0.45
        for i, event in enumerate(events):
            t_mid = (event.start + event.end) * 0.5
            p = event.phoneme.rstrip("012")
            if event.is_vowel and event.lexically_stressed:
                vol = self.intensity.get_value(t_mid)
                f0 = self.pitch.get_value_at_time(t_mid)
                z_int = 0.0
                if not math.isnan(vol):
                    z_int = (vol - v_int_mean) / (v_int_std + 1e-06)
                    ja_intensity = self._bucket(
                        z_int, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9)
                    )
                    event.jaw *= ja_intensity / MID_INTENSITY
                    event.jaw = min(event.jaw, 1.0)
                if not math.isnan(f0) and f0 > 0:
                    z_pitch = (f0 - v_p_mean) / (v_p_std + 1e-06)
                    z_combined = max(z_int, z_pitch)
                    li_intensity = self._bucket(
                        z_combined, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9)
                    )
                    scale = li_intensity / MID_INTENSITY
                    event.lip *= scale
                    event.lip = max(-1.0, min(1.0, event.lip))
            elif (p in FRICATIVES or p in PLOSIVES) and i in adjacent_to_stressed:
                if self.hf_intensity is not None:
                    hf = self.hf_intensity.get_value(t_mid)
                    if not math.isnan(hf):
                        z_hf = (hf - hf_mean) / (hf_std + 1e-06)
                        hf_intensity = self._bucket(
                            z_hf, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9)
                        )
                        scale = hf_intensity / MID_INTENSITY
                        event.lip *= scale
                        event.lip = max(-1.0, min(1.0, event.lip))
        return events


_FORMANT = ("formant analysis", "those vowels use the neutral AH viseme")
_SIBILANCE = ("sibilance analysis", "those consonants use the T viseme")


class AcousticPhonemeDetector:
    def __init__(self, audio_path: str):
        if not dependency_status().parselmouth:
            raise ImportError(
                f"parselmouth didn't load: {dependency_status().parselmouth_error}"
            )
        self.audio_path = audio_path
        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()
        self._analysis_cache = {}
        self.failures = MeasurementFailures()

    def warnings(self) -> list[str]:
        return self.failures.warnings()

    def _analysis(self, key, factory):
        if key not in self._analysis_cache:
            self._analysis_cache[key] = factory()
        return self._analysis_cache[key]

    def detect_phonemes(self) -> list[PhonemeEvent]:
        intensity = self._analysis("intensity", self.sound.to_intensity)
        textgrid = call(
            intensity, "To TextGrid (silences)", -25, 0.1, 0.05, "silent", "sounding"
        )
        events: list[PhonemeEvent] = []
        num_intervals = call(textgrid, "Get number of intervals", 1)
        for i in range(1, num_intervals + 1):
            label = call(textgrid, "Get label of interval", 1, i)
            start = call(textgrid, "Get start time of interval", 1, i)
            end = call(textgrid, "Get end time of interval", 1, i)
            if label == "silent":
                if end - start > 0.05:
                    events.append(create_phoneme_event("SIL", start, end))
                continue
            if end - start > 0.08:
                phoneme = self._classify_vowel(start, end)
            else:
                phoneme = self._classify_consonant(start, end)
            events.append(create_phoneme_event(phoneme, start, end))
        if self.failures.every_attempt_failed():
            raise AcousticAnalysisError(
                f"Praat could not analyse any sounding segment of {self.audio_path} ({self.failures.first_error()})"
            )
        return events

    def _classify_vowel(self, start: float, end: float) -> str:
        t = (start + end) * 0.5
        try:
            formant = self._analysis("formant", self.sound.to_formant_burg)
            f1 = call(formant, "Get value at time", 1, t, "Hertz", "Linear")
            f2 = call(formant, "Get value at time", 2, t, "Hertz", "Linear")
        except Exception as error:
            debug_exception(_LOG, "Praat formant sample details")
            self.failures.record(*_FORMANT, error)
            return "AH"
        self.failures.record(*_FORMANT)
        if f1 > 700:
            return "AA" if f2 < 1200 else "AE"
        elif f1 > 500:
            return "UH" if f2 < 1400 else "EH"
        else:
            return "UW" if f2 < 1800 else "IY"

    def _classify_consonant(self, start: float, end: float) -> str:
        t_mid = (start + end) * 0.5
        try:
            hf_intensity = self._analysis(
                "high_frequency",
                lambda: call(
                    self.sound, "Filter (pass Hann band)", 4000, 20000, 100
                ).to_intensity(minimum_pitch=50, time_step=0.001),
            )
            hf_val = call(hf_intensity, "Get value at time", t_mid, "Cubic")
            overall = self._analysis("intensity", self.sound.to_intensity)
            overall_val = call(overall, "Get value at time", t_mid, "Cubic")
        except Exception as error:
            debug_exception(_LOG, "Praat sibilance sample details")
            self.failures.record(*_SIBILANCE, error)
            return "T"
        self.failures.record(*_SIBILANCE)
        if math.isnan(hf_val):
            hf_val = 0.0
        if math.isnan(overall_val):
            overall_val = 0.0
        if hf_val > overall_val - 15:
            return "S"
        if overall_val < 40:
            return "M"
        return "T"
