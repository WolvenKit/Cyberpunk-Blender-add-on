from __future__ import annotations

from dataclasses import dataclass

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
    pitch: float = 0.0
    is_vowel: bool = False
    is_bilabial: bool = False
    is_labiodental: bool = False
    is_sibilant: bool = False
    is_tongue_only: bool = False
    is_lip_heavy: bool = False
    is_obstruent_nasal: bool = False
    lexically_stressed: bool = False
    stress_level: int = 0
    word_prominent: bool = True
    prev_is_pause: bool = False
    prev_is_vowel: bool = False
    word_index: int = -1
    prev_pause_end: float = float('-inf')
    next_pause_start: float = float('inf')
    original_start: float = -1.0
    original_end: float = -1.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def apex(self) -> float:
        return self.original_start if self.original_start >= 0 else self.start

    @property
    def sustain_end(self) -> float:
        if self.original_start >= 0 and self.original_end >= 0:
            orig_dur = self.original_end - self.original_start
            return self.original_start + 0.75 * orig_dur
        return self.start + 0.75 * self.duration

    @property
    def onset_duration(self) -> float:
        if self.phoneme in ('M', 'P', 'B'):
            return 0.18 if self.prev_is_pause else 0.155
        elif self.phoneme == 'F':
            return 0.16 if self.prev_is_pause else 0.14
        elif self.is_lip_heavy:
            return 0.15
        else:
            return 0.12

    @property
    def decay_duration(self) -> float:
        return 0.15 if self.is_lip_heavy else 0.12
