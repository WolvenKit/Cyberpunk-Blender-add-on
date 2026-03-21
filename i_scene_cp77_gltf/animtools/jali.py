import math
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

try:
    import parselmouth
    from parselmouth.praat import call

    JALI_DEPS_INSTALLED = True
except ImportError:
    JALI_DEPS_INSTALLED = False


@dataclass
class JALIViseme:
    jaw: float
    lip: float
    dominance: float


@dataclass
class PhonemeEvent:
    label: str
    start: float
    end: float
    viseme: JALIViseme
    power: float = 1.0
    ja_value: float = 0.0
    li_value: float = 0.0
    onset: float = 0.120
    offset: float = 0.120
    lexical_stress: int = 0
    word_prominence: float = 1.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def is_vowel(self) -> bool:
        return self.label in {'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY', 'IH', 'IY', 'OW', 'OY', 'UH', 'UW'}

    @property
    def is_bilabial(self) -> bool:
        return self.label in {'M', 'B', 'P'}

    @property
    def is_labiodental(self) -> bool:
        return self.label in {'F', 'V'}

    @property
    def is_sibilant(self) -> bool:
        return self.label in {'S', 'Z', 'SH', 'ZH', 'CH', 'JH'}

    @property
    def is_obstruent(self) -> bool:
        return self.label in {'B', 'D', 'G', 'P', 'T', 'K', 'F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH', 'CH', 'JH'}

    @property
    def is_nasal(self) -> bool:
        return self.label in {'M', 'N', 'NG'}

    @property
    def is_lip_heavy(self) -> bool:
        return self.label in {'UW', 'OW', 'OY', 'W', 'SH', 'ZH', 'CH', 'JH'}

    @property
    def is_tongue_only(self) -> bool:
        return self.label in {'L', 'N', 'T', 'D', 'K', 'G', 'NG'}


PHONEME_JALI_MAP = {
    'SIL': JALIViseme(0.0, 0.0, 0.0),
    'SP': JALIViseme(0.0, 0.0, 0.0),
    'M': JALIViseme(0.0, 0.0, 1.0),
    'B': JALIViseme(0.0, 0.0, 1.0),
    'P': JALIViseme(0.0, 0.0, 1.0),
    'F': JALIViseme(0.1, 0.2, 0.9),
    'V': JALIViseme(0.1, 0.2, 0.9),
    'S': JALIViseme(0.05, 0.3, 0.8),
    'Z': JALIViseme(0.05, 0.3, 0.8),
    'CH': JALIViseme(0.2, 0.5, 0.8),
    'SH': JALIViseme(0.2, 0.5, 0.8),
    'TH': JALIViseme(0.15, 0.0, 0.7),
    'DH': JALIViseme(0.15, 0.0, 0.7),
    'L': JALIViseme(0.3, 0.0, 0.6),
    'T': JALIViseme(0.1, 0.2, 0.7),
    'D': JALIViseme(0.1, 0.2, 0.7),
    'N': JALIViseme(0.1, 0.2, 0.7),
    'K': JALIViseme(0.4, 0.2, 0.5),
    'G': JALIViseme(0.4, 0.2, 0.5),
    'NG': JALIViseme(0.4, 0.2, 0.5),
    'HH': JALIViseme(0.4, 0.0, 0.1),
    'W': JALIViseme(0.1, -0.8, 0.9),
    'R': JALIViseme(0.2, -0.5, 0.7),
    'Y': JALIViseme(0.1, 0.4, 0.6),
    'AA': JALIViseme(1.0, 0.0, 0.1),
    'AE': JALIViseme(0.9, 0.3, 0.1),
    'AH': JALIViseme(0.6, 0.0, 0.1),
    'AO': JALIViseme(0.8, -0.4, 0.2),
    'AW': JALIViseme(0.9, -0.6, 0.3),
    'AY': JALIViseme(0.9, 0.4, 0.2),
    'EH': JALIViseme(0.5, 0.4, 0.1),
    'ER': JALIViseme(0.4, -0.2, 0.2),
    'EY': JALIViseme(0.5, 0.5, 0.2),
    'IH': JALIViseme(0.3, 0.5, 0.1),
    'IY': JALIViseme(0.1, 0.8, 0.2),
    'OW': JALIViseme(0.7, -0.7, 0.3),
    'OY': JALIViseme(0.8, -0.5, 0.3),
    'UH': JALIViseme(0.3, -0.4, 0.2),
    'UW': JALIViseme(0.2, -0.9, 0.4),
    }


class AcousticPhonemeDetector:
    def detect_phonemes(self, audio_path: str) -> List[PhonemeEvent]:
        if not JALI_DEPS_INSTALLED:
            raise ImportError("JALI requires 'parselmouth' and 'numpy'.")

        sound = parselmouth.Sound(audio_path)
        intensity = sound.to_intensity()
        tg = call(intensity, "To TextGrid (silences)", -25, 0.1, 0.1, "silent", "sounding")
        num_intervals = call(tg, "Get number of intervals", 1)

        events = []
        for i in range(1, num_intervals + 1):
            label = call(tg, "Get label of interval", 1, i)
            start = call(tg, "Get start time of interval", 1, i)
            end = call(tg, "Get end time of interval", 1, i)

            if label == "sounding":
                events.append(PhonemeEvent('AH', start, end, PHONEME_JALI_MAP['AH']))
            else:
                events.append(PhonemeEvent('SIL', start, end, PHONEME_JALI_MAP['SIL']))
        return events


class TranscriptAligner:
    """Placeholder for forced transcript alignment if added later."""

    def __init__(self, audio_path: str, transcript: str):
        self.audio_path = audio_path
        self.transcript = transcript

    def align_phonemes(self) -> List[PhonemeEvent]:
        detector = AcousticPhonemeDetector()
        return detector.detect_phonemes(self.audio_path)


class CoarticulationEngine:
    def __init__(self, fps: float):
        self.fps = fps
        self.frame_duration = 1.0 / fps

    def apply_coarticulation(self, phonemes: List[PhonemeEvent]) -> List[PhonemeEvent]:
        self._apply_constraints(phonemes)
        self._apply_conventions(phonemes)
        self._apply_habits(phonemes)
        return phonemes

    def _apply_constraints(self, phonemes: List[PhonemeEvent]):
        for p in phonemes:
            if p.is_bilabial:
                p.li_value = 1.0
                p.ja_value = 0.0
                p.power = max(p.power, 0.9)
            elif p.is_labiodental:
                p.li_value = 0.8
                p.ja_value = 0.1
            elif p.is_sibilant:
                p.ja_value = min(p.ja_value, 0.1)

    def _apply_conventions(self, phonemes: List[PhonemeEvent]):
        for p in phonemes:
            if p.is_vowel and p.lexical_stress >= 1:
                p.power = min(1.0, p.power * 1.3)
                p.ja_value = min(1.0, p.ja_value * 1.2)
                p.li_value = min(1.0, p.li_value * 1.1)
            elif p.word_prominence < 0.6:
                p.power *= 0.6
                p.ja_value *= 0.7
                p.li_value *= 0.8

    def _apply_habits(self, phonemes: List[PhonemeEvent]):
        n = len(phonemes)
        for i in range(n):
            p = phonemes[i]
            prev = phonemes[i - 1] if i > 0 else None
            next_p = phonemes[i + 1] if i < n - 1 else None

            if p.is_lip_heavy:
                p.onset = 0.180
                p.offset = 0.180
                if prev and not prev.is_bilabial and not prev.is_labiodental:
                    p.start = max(prev.start, p.start - 0.08)

            if p.is_tongue_only:
                if prev and prev.is_lip_heavy:
                    p.li_value = prev.li_value
                elif next_p and next_p.is_lip_heavy:
                    p.li_value = next_p.li_value

            if (p.is_obstruent or p.is_nasal) and not p.is_sibilant:
                has_similar = (prev and (prev.is_obstruent or prev.is_nasal)) or \
                              (next_p and (next_p.is_obstruent or next_p.is_nasal))
                if not has_similar and p.duration < self.frame_duration:
                    pass
            elif (p.is_obstruent or p.is_nasal) and p.duration >= self.frame_duration:
                if not p.is_sibilant:
                    p.ja_value = min(p.ja_value, 0.3)


class JALIAudioAnalyzer:
    def compute_jali_values(self, audio_path: str, phonemes: List[PhonemeEvent]):
        if not JALI_DEPS_INSTALLED:
            return

        sound = parselmouth.Sound(audio_path)
        pitch = sound.to_pitch(time_step=0.01)
        intensity = sound.to_intensity(time_step=0.01)
        sound_hf = call(sound, "Filter (pass Hann band)", 8000, 20000, 100)
        intensity_hf = sound_hf.to_intensity(time_step=0.01)

        vowels = [p for p in phonemes if p.is_vowel and p.lexical_stress >= 1]
        fricatives = [p for p in phonemes if p.is_sibilant or p.is_labiodental]

        self._compute_vowel_jali(vowels, pitch, intensity)
        self._compute_fricative_jali(fricatives, intensity_hf)

    def _compute_vowel_jali(self, vowels: List[PhonemeEvent], pitch, intensity):
        if not vowels:
            return

        intensities, pitches = [], []
        for v in vowels:
            mid_t = (v.start + v.end) / 2
            vol = intensity.get_value(mid_t)
            f0 = pitch.get_value_at_time(mid_t)
            if not math.isnan(vol): intensities.append(vol)
            if not math.isnan(f0): pitches.append(f0)

        if not intensities or not pitches:
            return

        mean_int = sum(intensities) / len(intensities)
        std_int = (sum((x - mean_int) ** 2 for x in intensities) / len(intensities)) ** 0.5
        mean_pitch = sum(pitches) / len(pitches)
        std_pitch = (sum((x - mean_pitch) ** 2 for x in pitches) / len(pitches)) ** 0.5

        for v in vowels:
            mid_t = (v.start + v.end) / 2
            vol = intensity.get_value(mid_t)
            f0 = pitch.get_value_at_time(mid_t)

            if math.isnan(vol) or math.isnan(f0):
                continue

            if vol <= mean_int - std_int:
                v.ja_value = np.random.uniform(0.1, 0.2)
            elif vol >= mean_int + std_int:
                v.ja_value = np.random.uniform(0.7, 0.9)
            else:
                v.ja_value = np.random.uniform(0.3, 0.6)

            int_high = vol >= mean_int + std_int
            int_low = vol <= mean_int - std_int
            pitch_high = f0 >= mean_pitch + std_pitch
            pitch_low = f0 <= mean_pitch - std_pitch

            if (int_high and pitch_high) or (int_low and pitch_low):
                v.li_value = np.random.uniform(0.7, 0.9) if int_high else np.random.uniform(0.1, 0.2)
            else:
                v.li_value = np.random.uniform(0.3, 0.6)

    def _compute_fricative_jali(self, fricatives: List[PhonemeEvent], intensity_hf):
        if not fricatives:
            return

        hf_intensities = []
        for f in fricatives:
            mid_t = (f.start + f.end) / 2
            hf_vol = intensity_hf.get_value(mid_t)
            if not math.isnan(hf_vol):
                hf_intensities.append(hf_vol)

        if not hf_intensities:
            return

        mean_hf = sum(hf_intensities) / len(hf_intensities)
        std_hf = (sum((x - mean_hf) ** 2 for x in hf_intensities) / len(hf_intensities)) ** 0.5

        for f in fricatives:
            mid_t = (f.start + f.end) / 2
            hf_vol = intensity_hf.get_value(mid_t)
            if math.isnan(hf_vol):
                continue
            if hf_vol <= mean_hf - std_hf:
                f.li_value = np.random.uniform(0.1, 0.2)
            elif hf_vol >= mean_hf + std_hf:
                f.li_value = np.random.uniform(0.7, 0.9)
            else:
                f.li_value = np.random.uniform(0.3, 0.6)