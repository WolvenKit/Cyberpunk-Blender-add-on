from __future__ import annotations
from typing import FrozenSet

WEIGHT_THRESHOLD: float = 0.001
"""Minimum weight to consider non-zero"""

NUM_ENVELOPE_TRACKS: int = 13

# Primary envelope tracks
ENV_FACE_ENVELOPE: int = 0       # faceEnvelope 
ENV_UPPER_FACE: int = 1          # upperFace
ENV_LOWER_FACE: int = 2          # lowerFace
ENV_ANTI_STRETCH: int = 3        # antiStretch
ENV_LIPSYNC_ENVELOPE: int = 4    # lipSyncEnvelope
ENV_LIPSYNC_LEFT: int = 5        # lipSyncLeftEnvelope
ENV_LIPSYNC_RIGHT: int = 6       # lipSyncRightEnvelope 

# JALI control tracks
ENV_JALI_JAW: int = 7            # jaliJaw
ENV_JALI_LIPS: int = 8           # jaliLips

# Muzzle envelope tracks
ENV_MUZZLE_LIPS: int = 9         # muzzleLips
ENV_MUZZLE_EYES: int = 10        # muzzleEyes
ENV_MUZZLE_BROWS: int = 11       # muzzleBrows
ENV_MUZZLE_EYE_DIRS: int = 12    # muzzleEyeDirections 

LIPSYNC_OVERRIDE_OFFSET: int = 140
"""AnimOverrideWeight tracks start at this index"""

LIPSYNC_POSE_OFFSET: int = 240
"""LipsyncPoseOutput tracks start at this index"""

WRINKLE_START_DEFAULT: int = 381
"""Default starting index for wrinkle tracks"""

INFLUENCE_LINEAR: int = 0
"""Linear influence: weight = min(w, 1 - sum)"""

INFLUENCE_EXPONENTIAL: int = 1
"""Exponential influence: weight *= (1 - sum²)"""

INFLUENCE_ORGANIC: int = 2
"""Organic influence: weight *= (1 - sum)²"""


CORRECTIVE_INFLUENCE_BY_SPEED: int = 1
"""Flag: Corrective influenced by animation speed"""

CORRECTIVE_INFLUENCE_LINEAR_CORRECTION: int = 2
"""Flag: Use linear correction formula"""

TONGUE_MID_BASE_L: int = 138
TONGUE_MID_BASE_R: int = 139
TONGUE_MID_BASE_DN: int = 140
TONGUE_MID_BASE_UP: int = 141
TONGUE_MID_BASE_FWD: int = 142
TONGUE_MID_BASE_FRONT: int = 143
TONGUE_MID_BASE_BACK: int = 144
TONGUE_MID_FWD: int = 145
TONGUE_MID_LIFT: int = 146
TONGUE_MID_TIP_L: int = 147
TONGUE_MID_TIP_R: int = 148
TONGUE_MID_TIP_DN: int = 149
TONGUE_MID_TIP_UP: int = 150
TONGUE_MID_TWIST_L: int = 151
TONGUE_MID_TWIST_R: int = 152
TONGUE_MID_THICK: int = 153

# =============================================================================
# PHONEME CLASSIFICATION SETS
# Based on JALI Paper Figure 10 phoneme categories
# Reference: Edwards et al. "JALI" SIGGRAPH 2016
# =============================================================================

BILABIALS: FrozenSet[str] = frozenset({'M', 'B', 'P'})
"""Bilabials MUST close lips (Paper §4.2 Constraint 1)"""

LABIODENTALS: FrozenSet[str] = frozenset({'F', 'V'})
"""Labiodentals MUST achieve lip-teeth contact (Paper §4.2 Constraint 2)"""

SIBILANTS: FrozenSet[str] = frozenset({'S', 'Z', 'SH', 'ZH', 'CH', 'JH'})
"""Sibilants narrow jaw greatly (Paper §4.2 Constraint 3)"""

DENTALS: FrozenSet[str] = frozenset({'TH', 'DH'})
"""Dental fricatives - tongue between teeth"""

ALVEOLARS: FrozenSet[str] = frozenset({'T', 'D', 'N', 'L'})
"""Alveolar consonants - tongue to alveolar ridge"""

VELARS: FrozenSet[str] = frozenset({'K', 'G', 'NG'})
"""Velar consonants - back of tongue to soft palate"""

GLIDES: FrozenSet[str] = frozenset({'W', 'Y', 'R'})
"""Glide/approximant consonants"""

TONGUE_ONLY: FrozenSet[str] = frozenset({'L', 'N', 'T', 'D', 'K', 'G', 'NG'})
"""Tongue-only have no lip influence (Paper §4.2 Rule 5)"""

LIP_HEAVY: FrozenSet[str] = frozenset({'UW', 'OW', 'OY', 'W', 'SH', 'ZH', 'CH', 'JH'})
"""Lip-heavy start early and end late (Paper §4.2 Rule 2)"""

OBSTRUENTS_NASALS: FrozenSet[str] = frozenset({
    'D', 'T', 'G', 'K', 'F', 'V', 'P', 'B', 'M', 'N', 'NG'
})
"""Obstruents and nasals (Paper §4.2 Rules 6-7)"""

VOWELS: FrozenSet[str] = frozenset({
    'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY',
    'IH', 'IY', 'OW', 'OY', 'UH', 'UW', 'AX', 'IX'
})
"""All vowel phonemes (Arpabet)"""

ROUNDED_VOWELS: FrozenSet[str] = frozenset({'UW', 'OW', 'OY', 'AO', 'AW'})
"""Rounded vowels - lip protrusion"""

WIDE_VOWELS: FrozenSet[str] = frozenset({'IY', 'EY', 'AE', 'EH', 'IH'})
"""Wide vowels - lip stretching"""

PAUSES: FrozenSet[str] = frozenset({'SIL', 'SP', '.', ',', '!', '?', ';', ':'})
"""Pause/silence markers"""

JALI_DEFAULT_ONSET_MS: float = 120.0
"""Default onset time in milliseconds (Paper §4.2)"""

JALI_DEFAULT_DECAY_MS: float = 120.0
"""Default decay time in milliseconds (Paper §4.2)"""

JALI_LIP_HEAVY_ONSET_MS: float = 150.0
"""Extended onset for lip-heavy phonemes (Paper §4.2)"""

JALI_LIP_HEAVY_DECAY_MS: float = 150.0
"""Extended decay for lip-heavy phonemes (Paper §4.2)"""

JALI_SUSTAIN_RATIO: float = 0.75
"""Apex sustained to 75% of phoneme duration (Paper §4.2)"""

JALI_DEFAULT_TAU: float = 0.070
"""Dominance blending time constant (60-80ms per paper)"""

LIPSYNC_POSE_SUFFIX: str = 'LipsyncPoseOutput'
"""Suffix for lipsync pose output track names"""

__all__ = [
    # Thresholds
    'WEIGHT_THRESHOLD',
    
    # Envelope track indices
    'NUM_ENVELOPE_TRACKS',
    'ENV_FACE_ENVELOPE', 'ENV_UPPER_FACE', 'ENV_LOWER_FACE', 'ENV_ANTI_STRETCH',
    'ENV_LIPSYNC_ENVELOPE', 'ENV_LIPSYNC_LEFT', 'ENV_LIPSYNC_RIGHT',
    'ENV_JALI_JAW', 'ENV_JALI_LIPS',
    'ENV_MUZZLE_LIPS', 'ENV_MUZZLE_EYES', 'ENV_MUZZLE_BROWS', 'ENV_MUZZLE_EYE_DIRS',
    
    # Track offsets
    'LIPSYNC_OVERRIDE_OFFSET', 'LIPSYNC_POSE_OFFSET', 'WRINKLE_START_DEFAULT',
    
    # Influence types
    'INFLUENCE_LINEAR', 'INFLUENCE_EXPONENTIAL', 'INFLUENCE_ORGANIC',
    
    # Corrective flags
    'CORRECTIVE_INFLUENCE_BY_SPEED', 'CORRECTIVE_INFLUENCE_LINEAR_CORRECTION',
    
    # Tongue indices
    'TONGUE_MID_BASE_L', 'TONGUE_MID_BASE_R', 'TONGUE_MID_BASE_DN',
    'TONGUE_MID_BASE_UP', 'TONGUE_MID_BASE_FWD', 'TONGUE_MID_BASE_FRONT',
    'TONGUE_MID_BASE_BACK', 'TONGUE_MID_FWD', 'TONGUE_MID_LIFT',
    'TONGUE_MID_TIP_L', 'TONGUE_MID_TIP_R', 'TONGUE_MID_TIP_DN',
    'TONGUE_MID_TIP_UP', 'TONGUE_MID_TWIST_L', 'TONGUE_MID_TWIST_R',
    'TONGUE_MID_THICK',
    
    # Phoneme sets
    'BILABIALS', 'LABIODENTALS', 'SIBILANTS', 'DENTALS', 'ALVEOLARS',
    'VELARS', 'GLIDES', 'TONGUE_ONLY', 'LIP_HEAVY', 'OBSTRUENTS_NASALS',
    'VOWELS', 'ROUNDED_VOWELS', 'WIDE_VOWELS', 'PAUSES',
    
    # JALI timing
    'JALI_DEFAULT_ONSET_MS', 'JALI_DEFAULT_DECAY_MS',
    'JALI_LIP_HEAVY_ONSET_MS', 'JALI_LIP_HEAVY_DECAY_MS',
    'JALI_SUSTAIN_RATIO', 'JALI_DEFAULT_TAU',
    
    # Track naming
    'LIPSYNC_POSE_SUFFIX',
]