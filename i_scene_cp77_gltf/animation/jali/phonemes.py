from __future__ import annotations

from typing import Dict

from .model import JALIViseme

DENTALS = frozenset({"TH", "DH"})
ALVEOLARS = frozenset({"T", "D", "N", "L"})
VELARS = frozenset({"K", "G", "NG"})
GLIDES = frozenset({"W", "Y", "R"})
ROUNDED_VOWELS = frozenset({"UW", "OW", "OY", "AO", "AW"})
WIDE_VOWELS = frozenset({"IY", "EY", "AE", "EH", "IH"})

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

PHONEME_TO_VISEME = {
    'AE': 'AAA', 'EY': 'AAA',
    'AA': 'AHH', 'AO': 'AHH', 'AY': 'AHH', 'AW': 'AHH',
    'UW': 'UUU', 'W': 'UUU',
    'R': 'RRR',
    'D': 'TTH', 'T': 'TTH',
    'F': 'FFF', 'V': 'FFF',
    'UH': 'EHH', 'EH': 'EHH', 'HH': 'EHH',
    'OW': 'OHH', 'OY': 'OHH',
    'IY': 'IEE', 'IH': 'IEE', 'Y': 'IEE',
    'S': 'SSS', 'Z': 'SSS',
    'SH': 'SSH', 'ZH': 'SSH', 'CH': 'SSH', 'JH': 'SSH',
    'M': 'MMM', 'B': 'MMM', 'P': 'MMM',
    'AX': 'AHH', 'IX': 'AHH',
    'AH': 'AHH',
    'ER': 'RRR',
    'TH': 'TTH', 'DH': 'TTH',
    'L': 'LNTD', 'N': 'LNTD',
    'K': 'GK', 'G': 'GK', 'NG': 'GK',
    }

def _get_viseme(phoneme: str) -> str:

    return PHONEME_TO_VISEME.get(phoneme.rstrip('012'), phoneme)
