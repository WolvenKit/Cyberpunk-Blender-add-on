from __future__ import annotations

from .model import JALIViseme, PhonemeEvent
from .phonemes import ARPABET_JALI_MAP

def create_phoneme_event(phoneme: str, start: float, end: float, lexically_stressed: bool=False) -> PhonemeEvent:
    stress_level = 0
    if phoneme:
        last = phoneme[-1]
        if last == '1':
            stress_level = 2
        elif last == '2':
            stress_level = 1
    clean = phoneme.rstrip('012')
    jali = ARPABET_JALI_MAP.get(clean, JALIViseme(0.3, 0.0, 0.5))
    stressed = lexically_stressed or stress_level > 0
    return PhonemeEvent(
            phoneme=clean,
            start=start,
            end=end,
            jaw=jali.jaw,
            lip=jali.lip,
            dominance=jali.dominance,
            lexically_stressed=stressed,
            stress_level=stress_level,
            )
