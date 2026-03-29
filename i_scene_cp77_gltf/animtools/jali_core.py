from __future__ import annotations
import numpy as np
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field

try:
    import parselmouth
    from parselmouth.praat import call

    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False


@dataclass
class JALIViseme:
    jaw: float
    lip: float
    dominance: float


@dataclass
class PhonemeEvent:
    phoneme: str
    start: float
    end: float

    jaw: float = 0.5
    lip: float = 0.0
    dominance: float = 0.5

    amplitude: float = 1.0
    pitch: float = 0.0

    is_vowel: bool = False
    is_bilabial: bool = False
    is_labiodental: bool = False
    is_sibilant: bool = False
    is_tongue_only: bool = False
    is_lip_heavy: bool = False
    is_obstruent_nasal: bool = False
    lexically_stressed: bool = False
    word_prominent: bool = True

    prev_is_pause: bool = False
    prev_is_vowel: bool = False

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def apex(self) -> float:
        return self.start + self.onset_duration

    @property
    def sustain_end(self) -> float:
        return self.start + 0.75 * self.duration

    @property
    def onset_duration(self) -> float:
        if self.phoneme in ('M', 'P', 'B'):
            return 0.180 if self.prev_is_pause else 0.155
        elif self.phoneme == 'F':
            return 0.160 if self.prev_is_pause else 0.140
        elif self.is_lip_heavy:
            return 0.150
        else:
            return 0.120

    @property
    def decay_duration(self) -> float:
        return 0.150 if self.is_lip_heavy else 0.120


ARPABET_JALI_MAP: Dict[str, JALIViseme] = {
    'SIL': JALIViseme(0.0, 0.0, 0.0),
    'SP': JALIViseme(0.0, 0.0, 0.0),

    'M': JALIViseme(0.0, 0.0, 1.0),
    'B': JALIViseme(0.0, 0.0, 1.0),
    'P': JALIViseme(0.0, 0.0, 1.0),

    'F': JALIViseme(0.1, 0.1, 0.95),
    'V': JALIViseme(0.1, 0.1, 0.95),

    'S': JALIViseme(0.05, 0.4, 0.85),
    'Z': JALIViseme(0.05, 0.4, 0.85),
    'SH': JALIViseme(0.15, -0.3, 0.85),
    'ZH': JALIViseme(0.15, -0.3, 0.85),
    'CH': JALIViseme(0.15, -0.2, 0.85),
    'JH': JALIViseme(0.15, -0.2, 0.85),

    'TH': JALIViseme(0.15, 0.0, 0.75),
    'DH': JALIViseme(0.15, 0.0, 0.75),

    'T': JALIViseme(0.1, 0.0, 0.7),
    'D': JALIViseme(0.1, 0.0, 0.7),
    'N': JALIViseme(0.1, 0.0, 0.7),
    'L': JALIViseme(0.3, 0.0, 0.6),
    'K': JALIViseme(0.4, 0.0, 0.6),
    'G': JALIViseme(0.4, 0.0, 0.6),
    'NG': JALIViseme(0.4, 0.0, 0.6),

    'W': JALIViseme(0.1, -0.9, 0.95),
    'R': JALIViseme(0.2, -0.5, 0.7),
    'Y': JALIViseme(0.1, 0.5, 0.6),
    'HH': JALIViseme(0.4, 0.0, 0.2),

    'AA': JALIViseme(1.0, 0.0, 0.15),
    'AE': JALIViseme(0.9, 0.4, 0.15),
    'AH': JALIViseme(0.6, 0.0, 0.1),
    'AO': JALIViseme(0.8, -0.5, 0.2),

    'EH': JALIViseme(0.5, 0.5, 0.1),
    'ER': JALIViseme(0.4, -0.3, 0.2),
    'IH': JALIViseme(0.3, 0.6, 0.1),
    'UH': JALIViseme(0.3, -0.4, 0.2),

    'IY': JALIViseme(0.15, 0.9, 0.2),
    'UW': JALIViseme(0.2, -0.95, 0.4),

    'AW': JALIViseme(0.85, -0.6, 0.3),
    'AY': JALIViseme(0.9, 0.5, 0.25),
    'EY': JALIViseme(0.5, 0.6, 0.2),
    'OW': JALIViseme(0.6, -0.8, 0.4),
    'OY': JALIViseme(0.7, -0.6, 0.35),

    'AX': JALIViseme(0.4, 0.0, 0.05),
    'IX': JALIViseme(0.3, 0.3, 0.05),
    }

BILABIALS = frozenset({'M', 'B', 'P'})
LABIODENTALS = frozenset({'F', 'V'})
SIBILANTS = frozenset({'S', 'Z', 'SH', 'ZH', 'CH', 'JH'})
TONGUE_ONLY = frozenset({'L', 'N', 'T', 'D', 'K', 'G', 'NG'})
LIP_HEAVY = frozenset({'UW', 'OW', 'OY', 'W', 'SH', 'ZH', 'CH', 'JH'})
OBSTRUENTS_NASALS = frozenset({'D', 'T', 'G', 'K', 'F', 'V', 'P', 'B', 'M', 'N', 'NG'})
VOWELS = frozenset(
        {'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY',
         'IH', 'IY', 'OW', 'OY', 'UH', 'UW', 'AX', 'IX'}
        )
PAUSES = frozenset({'SIL', 'SP', '.', ',', '!', '?', ';', ':'})


class DominanceBlender:
    def __init__(self, fps: float = 30.0, tau: float = 0.070):
        self.fps = fps
        self.tau = tau

    def compute_dominance_curve(self, event: PhonemeEvent, times: np.ndarray) -> np.ndarray:
        t_apex = event.apex
        dt = np.abs(times - t_apex)

        envelope = event.dominance * np.exp(-dt / self.tau)

        mask = (times >= event.start) & (times <= event.end)
        return envelope * mask

    def blend_jali_parameters(
            self,
            events: List[PhonemeEvent],
            duration: float
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

        eps = 1e-8
        jaw_curve = jaw_weighted / (dominance_sum + eps)
        lip_curve = lip_weighted / (dominance_sum + eps)

        no_influence = dominance_sum < 1e-6
        jaw_curve[no_influence] = 0.3
        lip_curve[no_influence] = 0.0

        return times, jaw_curve.astype(np.float32), lip_curve.astype(np.float32)


class CoarticulationEngine:
    def apply_rules(self, events: List[PhonemeEvent]) -> List[PhonemeEvent]:
        if not events:
            return events

        for event in events:
            self._classify_phoneme(event)

        self._set_context(events)

        self._merge_duplicates(events)
        self._extend_lip_heavy(events)
        self._override_lip_shapes(events)
        self._apply_tongue_only(events)
        self._apply_obstruent_rules(events)
        self._apply_anticipation(events)
        self._enforce_constraints(events)
        self._apply_stress_amplitude(events)

        return events

    @staticmethod
    def _classify_phoneme(event: PhonemeEvent):
        p = event.phoneme.rstrip('012')

        event.is_vowel = p in VOWELS
        event.is_bilabial = p in BILABIALS
        event.is_labiodental = p in LABIODENTALS
        event.is_sibilant = p in SIBILANTS
        event.is_tongue_only = p in TONGUE_ONLY
        event.is_lip_heavy = p in LIP_HEAVY
        event.is_obstruent_nasal = p in OBSTRUENTS_NASALS

        if event.phoneme and event.phoneme[-1] in '12':
            event.lexically_stressed = True
            event.phoneme = p

    @staticmethod
    def _set_context(events: List[PhonemeEvent]):
        for i, event in enumerate(events):
            if i == 0:
                event.prev_is_pause = True
                event.prev_is_vowel = False
            else:
                prev = events[i - 1]
                event.prev_is_pause = prev.phoneme in PAUSES
                event.prev_is_vowel = prev.is_vowel

    @staticmethod
    def _merge_duplicates(events: List[PhonemeEvent]):
        i = 0
        while i < len(events) - 1:
            if events[i].phoneme == events[i + 1].phoneme:
                events[i].end = events[i + 1].end
                events.pop(i + 1)
            else:
                i += 1

    @staticmethod
    def _extend_lip_heavy(events: List[PhonemeEvent]):
        for i, event in enumerate(events):
            if event.is_lip_heavy:
                ext = 0.150
                if i > 0:
                    event.start = max(events[i - 1].end, event.start - ext)
                if i < len(events) - 1:
                    event.end = min(events[i + 1].start, event.end + ext)

    @staticmethod
    def _override_lip_shapes(events: List[PhonemeEvent]):
        for i, event in enumerate(events):
            if event.is_lip_heavy:
                if i > 0:
                    prev = events[i - 1]
                    if not (prev.is_bilabial or prev.is_labiodental):
                        prev.lip = event.lip * 0.5

                if i < len(events) - 1:
                    nxt = events[i + 1]
                    if not (nxt.is_bilabial or nxt.is_labiodental):
                        nxt.lip = event.lip * 0.3

    @staticmethod
    def _apply_tongue_only(events: List[PhonemeEvent]):
        for i, event in enumerate(events):
            if event.is_tongue_only:
                if i > 0 and i < len(events) - 1:
                    event.lip = (events[i - 1].lip + events[i + 1].lip) * 0.5
                elif i > 0:
                    event.lip = events[i - 1].lip
                elif i < len(events) - 1:
                    event.lip = events[i + 1].lip

    @staticmethod
    def _apply_obstruent_rules(events: List[PhonemeEvent]):
        for event in events:
            if event.is_obstruent_nasal and not event.is_sibilant:
                if event.duration < 0.033:
                    event.jaw = 0.0

    @staticmethod
    def _apply_anticipation(events: List[PhonemeEvent]):
        pass

    @staticmethod
    def _enforce_constraints(events: List[PhonemeEvent]):
        for event in events:
            if event.is_bilabial:
                event.jaw = 0.0
                event.lip = 0.0
                event.dominance = max(event.dominance, 1.0)

            elif event.is_labiodental:
                event.jaw = min(event.jaw, 0.1)
                event.dominance = max(event.dominance, 0.95)

            elif event.is_sibilant:
                event.jaw = min(event.jaw, 0.15)

    @staticmethod
    def _apply_stress_amplitude(events: List[PhonemeEvent]):
        for event in events:
            if event.lexically_stressed and event.is_vowel:
                event.amplitude = 0.9
                event.jaw = min(event.jaw * 1.1, 1.0)
            elif not event.word_prominent:
                event.amplitude = 0.3
                event.jaw *= 0.7
            else:
                event.amplitude = 0.6


class AcousticAnalyzer:
    def __init__(self, audio_path: str):
        if not PARSELMOUTH_AVAILABLE:
            raise ImportError("Install parselmouth: pip install praat-parselmouth")

        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()
        self.pitch = self.sound.to_pitch()
        self.intensity = self.sound.to_intensity()

        self._compute_statistics()

    def _compute_statistics(self):
        times = np.linspace(0, self.duration, int(self.duration * 100))

        intensities = []
        pitches = []
        hf_intensities = []

        for t in times:
            i = self.intensity.get_value(t)
            p = self.pitch.get_value_at_time(t)

            if not math.isnan(i):
                intensities.append(i)
            if not math.isnan(p) and p > 0:
                pitches.append(p)

        self.intensity_mean = np.mean(intensities) if intensities else 60.0
        self.intensity_std = np.std(intensities) if intensities else 10.0
        self.pitch_mean = np.mean(pitches) if pitches else 150.0
        self.pitch_std = np.std(pitches) if pitches else 50.0

        try:
            self.hf_sound = call(self.sound, "Filter (pass Hann band)", 8000, 20000, 100)
            self.hf_intensity = self.hf_sound.to_intensity()

            hf_vals = []
            for t in times:
                hf = self.hf_intensity.get_value(t)
                if not math.isnan(hf):
                    hf_vals.append(hf)

            self.hf_mean = np.mean(hf_vals) if hf_vals else 30.0
            self.hf_std = np.std(hf_vals) if hf_vals else 10.0
        except:
            self.hf_intensity = None
            self.hf_mean = 30.0
            self.hf_std = 10.0

    def get_amplitude_factor(self, time: float) -> float:
        try:
            intensity = self.intensity.get_value(time)
            if math.isnan(intensity):
                return 1.0

            z = (intensity - self.intensity_mean) / (self.intensity_std + 1e-6)
            return float(np.clip(1.0 + 0.5 * z, 0.1, 1.5))
        except:
            return 1.0

    def get_pitch_factor(self, time: float) -> float:
        try:
            p = self.pitch.get_value_at_time(time)
            if math.isnan(p) or p <= 0:
                return 0.0

            z = (p - self.pitch_mean) / (self.pitch_std + 1e-6)
            return float(0.25 * np.clip(z, -2.0, 2.0))
        except:
            return 0.0

    def get_hf_intensity_factor(self, time: float) -> float:
        if self.hf_intensity is None:
            return 0.0

        try:
            hf = self.hf_intensity.get_value(time)
            if math.isnan(hf):
                return 0.0

            z = (hf - self.hf_mean) / (self.hf_std + 1e-6)
            return float(np.clip(1.0 + 0.5 * z, 0.1, 1.5))
        except:
            return 0.0

    def modulate_events(self, events: List[PhonemeEvent]) -> List[PhonemeEvent]:
        for event in events:
            t_mid = (event.start + event.end) * 0.5

            event.amplitude = self.get_amplitude_factor(t_mid)
            event.jaw *= event.amplitude

            if event.is_vowel:
                pitch_factor = self.get_pitch_factor(t_mid)
                event.pitch = pitch_factor
                event.lip *= (1.0 + abs(pitch_factor))
            elif event.is_sibilant or event.phoneme in OBSTRUENTS_NASALS:
                hf_factor = self.get_hf_intensity_factor(t_mid)
                event.lip *= hf_factor

        return events


class MotionCurveGenerator:
    def __init__(self, fps: float = 30.0):
        self.fps = fps

    def generate_curve(self, event: PhonemeEvent, times: np.ndarray) -> np.ndarray:
        t_start = event.start
        t_apex = event.apex
        t_sustain_end = event.sustain_end
        t_end = event.end

        curve = np.zeros_like(times, dtype=np.float32)

        onset_mask = (times >= t_start) & (times < t_apex)
        if onset_mask.any():
            t_rel = (times[onset_mask] - t_start) / max(event.onset_duration, 0.001)
            curve[onset_mask] = np.sin(0.5 * np.pi * np.clip(t_rel, 0, 1)) ** 2

        sustain_mask = (times >= t_apex) & (times <= t_sustain_end)
        curve[sustain_mask] = 1.0

        decay_mask = (times > t_sustain_end) & (times <= t_end)
        if decay_mask.any():
            t_rel = (t_end - times[decay_mask]) / max(event.decay_duration, 0.001)
            curve[decay_mask] = np.sin(0.5 * np.pi * np.clip(t_rel, 0, 1)) ** 2

        return curve


def create_phoneme_event(
        phoneme: str,
        start: float,
        end: float,
        lexically_stressed: bool = False
        ) -> PhonemeEvent:
    clean = phoneme.rstrip('012')
    jali = ARPABET_JALI_MAP.get(clean, JALIViseme(0.3, 0.0, 0.5))

    stressed = lexically_stressed or (phoneme[-1] in '12' if phoneme else False)

    return PhonemeEvent(
            phoneme=clean,
            start=start,
            end=end,
            jaw=jali.jaw,
            lip=jali.lip,
            dominance=jali.dominance,
            lexically_stressed=stressed
            )


class AcousticPhonemeDetector:
    def detect_phonemes(self, audio_path: str) -> List[PhonemeEvent]:
        if not PARSELMOUTH_AVAILABLE:
            raise ImportError("JALI requires parselmouth: pip install praat-parselmouth")

        sound = parselmouth.Sound(audio_path)
        intensity = sound.to_intensity()
        tg = call(
            intensity, "To TextGrid (silences)",
            -25, 0.1, 0.1, "silent", "sounding"
            )
        num_intervals = call(tg, "Get number of intervals", 1)

        events: List[PhonemeEvent] = []
        for i in range(1, num_intervals + 1):
            label = call(tg, "Get label of interval", 1, i)
            start = call(tg, "Get start time of interval", 1, i)
            end = call(tg, "Get end time of interval", 1, i)

            phoneme = 'AH' if label == "sounding" else 'SIL'
            events.append(create_phoneme_event(phoneme, start, end))

        return events


class TranscriptAligner:
    def __init__(self, audio_path: str, transcript: str):
        self.audio_path = audio_path
        self.transcript = transcript

    def align_phonemes(self) -> List[PhonemeEvent]:
        detector = AcousticPhonemeDetector()
        return detector.detect_phonemes(self.audio_path)