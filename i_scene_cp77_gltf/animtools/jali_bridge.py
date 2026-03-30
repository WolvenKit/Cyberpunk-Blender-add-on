from __future__ import annotations
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

try:
    import bpy
    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from .constants import (
    ENV_FACE_ENVELOPE as IDX_FACE_ENVELOPE,
    ENV_UPPER_FACE as IDX_UPPER_FACE,
    ENV_LOWER_FACE as IDX_LOWER_FACE,
    ENV_ANTI_STRETCH as IDX_ANTI_STRETCH,
    ENV_LIPSYNC_ENVELOPE as IDX_LIPSYNC_ENVELOPE,
    ENV_LIPSYNC_LEFT as IDX_LIPSYNC_LEFT_ENV,
    ENV_LIPSYNC_RIGHT as IDX_LIPSYNC_RIGHT_ENV,
    ENV_JALI_JAW as IDX_JALI_JAW,
    ENV_JALI_LIPS as IDX_JALI_LIPS,
    ENV_MUZZLE_LIPS as IDX_MUZZLE_LIPS,
    ENV_MUZZLE_EYES as IDX_MUZZLE_EYES,
    ENV_MUZZLE_BROWS as IDX_MUZZLE_BROWS,
    ENV_MUZZLE_EYE_DIRS as IDX_MUZZLE_EYE_DIRS,
    TONGUE_MID_BASE_L as IDX_TONGUE_BASE_L,
    TONGUE_MID_BASE_R as IDX_TONGUE_BASE_R,
    TONGUE_MID_BASE_DN as IDX_TONGUE_BASE_DN,
    TONGUE_MID_BASE_UP as IDX_TONGUE_BASE_UP,
    TONGUE_MID_BASE_FWD as IDX_TONGUE_BASE_FWD,
    TONGUE_MID_BASE_FRONT as IDX_TONGUE_BASE_FRONT,
    TONGUE_MID_BASE_BACK as IDX_TONGUE_BASE_BACK,
    TONGUE_MID_FWD as IDX_TONGUE_FWD,
    TONGUE_MID_LIFT as IDX_TONGUE_LIFT,
    TONGUE_MID_TIP_L as IDX_TONGUE_TIP_L,
    TONGUE_MID_TIP_R as IDX_TONGUE_TIP_R,
    TONGUE_MID_TIP_DN as IDX_TONGUE_TIP_DN,
    TONGUE_MID_TIP_UP as IDX_TONGUE_TIP_UP,
    TONGUE_MID_TWIST_L as IDX_TONGUE_TWIST_L,
    TONGUE_MID_TWIST_R as IDX_TONGUE_TWIST_R,
    TONGUE_MID_THICK as IDX_TONGUE_THICK,
    )

def build_jali_track_mappings() -> List[Dict]:
    """Build comprehensive JALI → CP77 track mappings"""
    mappings = []

    mappings.append(
            {
                'track_name': 'jaw_mid_open',
                'ja_range': (0.0, 1.0),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: ja
                }
            )

    mappings.append(
            {
                'track_name': 'jaw_mid_close',
                'ja_range': (0.0, 0.15),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (0.15 - ja) / 0.15) * 0.6
                }
            )

    mappings.append(
            {
                'track_name': 'jaw_mid_clench',
                'ja_range': (0.0, 0.1),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, (0.1 - ja) / 0.1) * max(0, 1.0 - abs(li) / 0.3) * 0.4
                }
            )

    mappings.append(
            {
                'track_name': 'jaw_mid_shift_fwd',
                'ja_range': (0.05, 0.3),
                'li_range': (-0.6, 0.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.05) / 0.25) * max(0, -li / 0.6) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'lips_apart_up',
                'ja_range': (0.25, 1.0),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.25) / 0.75) * 0.7
                }
            )

    mappings.append(
            {
                'track_name': 'lips_apart_dn',
                'ja_range': (0.2, 1.0),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.2) / 0.8) * 0.85
                }
            )

    mappings.append(
            {
                'track_name': 'lips_together_up',
                'ja_range': (0.0, 0.12),
                'li_range': (-0.4, 0.4),
                'weight_func': lambda ja, li: max(0, (0.12 - ja) / 0.12) * max(0, 1.0 - abs(li) / 0.4)
                }
            )

    mappings.append(
            {
                'track_name': 'lips_together_dn',
                'ja_range': (0.0, 0.12),
                'li_range': (-0.4, 0.4),
                'weight_func': lambda ja, li: max(0, (0.12 - ja) / 0.12) * max(0, 1.0 - abs(li) / 0.4)
                }
            )

    mappings.append(
            {
                'track_name': 'lips_tighten_up',
                'ja_range': (0.0, 0.15),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, (0.15 - ja) / 0.15) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'lips_tighten_dn',
                'ja_range': (0.0, 0.15),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, (0.15 - ja) / 0.15) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_purse',
                'ja_range': (0.0, 0.7),
                'li_range': (-1.0, -0.15),
                'weight_func': lambda ja, li: max(0, (-li - 0.15) / 0.85) * (1.0 - ja * 0.4)
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_purse',
                'ja_range': (0.0, 0.7),
                'li_range': (-1.0, -0.15),
                'weight_func': lambda ja, li: max(0, (-li - 0.15) / 0.85) * (1.0 - ja * 0.4)
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_funnel',
                'ja_range': (0.0, 0.8),
                'li_range': (-1.0, -0.35),
                'weight_func': lambda ja, li: max(0, (-li - 0.35) / 0.65) * 0.75
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_funnel',
                'ja_range': (0.0, 0.8),
                'li_range': (-1.0, -0.35),
                'weight_func': lambda ja, li: max(0, (-li - 0.35) / 0.65) * 0.75
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_corner_wide',
                'ja_range': (0.0, 0.75),
                'li_range': (0.15, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.15) / 0.85) * (1.0 - ja * 0.35)
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_corner_wide',
                'ja_range': (0.0, 0.75),
                'li_range': (0.15, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.15) / 0.85) * (1.0 - ja * 0.35)
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_corner_stretch',
                'ja_range': (0.0, 0.6),
                'li_range': (0.25, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.25) / 0.75) * 0.75
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_corner_stretch',
                'ja_range': (0.0, 0.6),
                'li_range': (0.25, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.25) / 0.75) * 0.75
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_stretch',
                'ja_range': (0.0, 0.5),
                'li_range': (0.35, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.35) / 0.65) * 0.6
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_stretch',
                'ja_range': (0.0, 0.5),
                'li_range': (0.35, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.35) / 0.65) * 0.6
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_corner_up',
                'ja_range': (0.0, 0.8),
                'li_range': (0.3, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.3) / 0.7) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_corner_up',
                'ja_range': (0.0, 0.8),
                'li_range': (0.3, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.3) / 0.7) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_corner_dn',
                'ja_range': (0.4, 1.0),
                'li_range': (-0.5, 0.2),
                'weight_func': lambda ja, li: max(0, (ja - 0.4) / 0.6) * max(0, (0.2 - li) / 0.7) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_corner_dn',
                'ja_range': (0.4, 1.0),
                'li_range': (-0.5, 0.2),
                'weight_func': lambda ja, li: max(0, (ja - 0.4) / 0.6) * max(0, (0.2 - li) / 0.7) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_upper_raise',
                'ja_range': (0.0, 0.7),
                'li_range': (0.2, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.2) / 0.8) * 0.45
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_upper_raise',
                'ja_range': (0.0, 0.7),
                'li_range': (0.2, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.2) / 0.8) * 0.45
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_lower_raise',
                'ja_range': (0.0, 0.25),
                'li_range': (-0.3, 0.4),
                'weight_func': lambda ja, li: max(0, min(1.0, ja / 0.15)) * max(0, (0.25 - ja) / 0.25) * 0.7
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_lower_raise',
                'ja_range': (0.0, 0.25),
                'li_range': (-0.3, 0.4),
                'weight_func': lambda ja, li: max(0, min(1.0, ja / 0.15)) * max(0, (0.25 - ja) / 0.25) * 0.7
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_pull',
                'ja_range': (0.0, 0.6),
                'li_range': (0.4, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.4) / 0.6) * 0.4
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_pull',
                'ja_range': (0.0, 0.6),
                'li_range': (0.4, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.4) / 0.6) * 0.4
                }
            )

    mappings.append(
            {
                'track_name': 'lips_suck_up',
                'ja_range': (0.0, 0.2),
                'li_range': (-0.4, 0.2),
                'weight_func': lambda ja, li: max(0, (0.2 - ja) / 0.2) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'lips_suck_dn',
                'ja_range': (0.05, 0.2),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, (ja - 0.05) / 0.15) * max(0, (0.2 - ja) / 0.15) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'lips_puff_up',
                'ja_range': (0.0, 0.5),
                'li_range': (-0.7, -0.2),
                'weight_func': lambda ja, li: max(0, (-li - 0.2) / 0.5) * (1.0 - ja) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'lips_puff_dn',
                'ja_range': (0.0, 0.5),
                'li_range': (-0.7, -0.2),
                'weight_func': lambda ja, li: max(0, (-li - 0.2) / 0.5) * (1.0 - ja) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'lips_chin_raise',
                'ja_range': (0.0, 0.35),
                'li_range': (-0.5, 0.5),
                'weight_func': lambda ja, li: max(0, (0.35 - ja) / 0.35) * 0.35
                }
            )

    mappings.append(
            {
                'track_name': 'cheek_l_suck',
                'ja_range': (0.0, 0.4),
                'li_range': (0.3, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.3) / 0.7) * (1.0 - ja * 2) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'cheek_r_suck',
                'ja_range': (0.0, 0.4),
                'li_range': (0.3, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.3) / 0.7) * (1.0 - ja * 2) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'cheek_l_puff',
                'ja_range': (0.0, 0.5),
                'li_range': (-0.8, -0.15),
                'weight_func': lambda ja, li: max(0, (-li - 0.15) / 0.65) * (1.0 - ja) * 0.35
                }
            )

    mappings.append(
            {
                'track_name': 'cheek_r_puff',
                'ja_range': (0.0, 0.5),
                'li_range': (-0.8, -0.15),
                'weight_func': lambda ja, li: max(0, (-li - 0.15) / 0.65) * (1.0 - ja) * 0.35
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_fwd',
                'ja_range': (0.08, 0.4),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, min(1.0, (ja - 0.08) / 0.32)) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_lift',
                'ja_range': (0.08, 0.5),
                'li_range': (-0.4, 0.4),
                'weight_func': lambda ja, li: max(0, min(1.0, (ja - 0.08) / 0.42)) * 0.6
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_tip_up',
                'ja_range': (0.1, 0.45),
                'li_range': (-0.4, 0.4),
                'weight_func': lambda ja, li: max(0, min(1.0, (ja - 0.1) / 0.35)) * 0.55
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_tip_dn',
                'ja_range': (0.5, 1.0),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.3
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_base_up',
                'ja_range': (0.3, 0.6),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, (ja - 0.3) / 0.3) * max(0, (0.6 - ja) / 0.3) * 0.5
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_base_front',
                'ja_range': (0.15, 0.5),
                'li_range': (-0.4, 0.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.15) / 0.35) * max(0, -li / 0.4) * 0.4
                }
            )

    mappings.append(
            {
                'track_name': 'tongue_mid_base_back',
                'ja_range': (0.3, 0.7),
                'li_range': (-0.3, 0.3),
                'weight_func': lambda ja, li: max(0, (ja - 0.3) / 0.4) * 0.35
                }
            )

    mappings.append(
            {
                'track_name': 'lips_l_nasolabialDeepener',
                'ja_range': (0.0, 0.9),
                'li_range': (0.25, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.25) / 0.75) * 0.4
                }
            )

    mappings.append(
            {
                'track_name': 'lips_r_nasolabialDeepener',
                'ja_range': (0.0, 0.9),
                'li_range': (0.25, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.25) / 0.75) * 0.4
                }
            )

    mappings.append(
            {
                'track_name': 'nose_l_snear',
                'ja_range': (0.0, 0.6),
                'li_range': (0.35, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.35) / 0.65) * 0.25
                }
            )

    mappings.append(
            {
                'track_name': 'nose_r_snear',
                'ja_range': (0.0, 0.6),
                'li_range': (0.35, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.35) / 0.65) * 0.25
                }
            )

    mappings.append(
            {
                'track_name': 'nose_l_compress',
                'ja_range': (0.0, 0.4),
                'li_range': (-0.7, -0.2),
                'weight_func': lambda ja, li: max(0, (-li - 0.2) / 0.5) * 0.2
                }
            )

    mappings.append(
            {
                'track_name': 'nose_r_compress',
                'ja_range': (0.0, 0.4),
                'li_range': (-0.7, -0.2),
                'weight_func': lambda ja, li: max(0, (-li - 0.2) / 0.5) * 0.2
                }
            )

    mappings.append(
            {
                'track_name': 'neck_throat_adamsApple_up',
                'ja_range': (0.0, 0.2),
                'li_range': (-0.5, 0.5),
                'weight_func': lambda ja, li: max(0, (0.2 - ja) / 0.2) * 0.15
                }
            )

    mappings.append(
            {
                'track_name': 'neck_throat_compress',
                'ja_range': (0.0, 0.3),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (0.3 - ja) / 0.3) * 0.1
                }
            )

    mappings.append(
            {
                'track_name': 'eye_l_brows_raise_out',
                'ja_range': (0.5, 1.0),
                'li_range': (0.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.5) / 0.5) * max(0, li) * 0.25
                }
            )

    mappings.append(
            {
                'track_name': 'eye_r_brows_raise_out',
                'ja_range': (0.5, 1.0),
                'li_range': (0.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.5) / 0.5) * max(0, li) * 0.25
                }
            )

    mappings.append(
            {
                'track_name': 'eye_l_brows_raise_in',
                'ja_range': (0.6, 1.0),
                'li_range': (0.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.6) / 0.4) * max(0, li) * 0.2
                }
            )

    mappings.append(
            {
                'track_name': 'eye_r_brows_raise_in',
                'ja_range': (0.6, 1.0),
                'li_range': (0.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.6) / 0.4) * max(0, li) * 0.2
                }
            )

    mappings.append(
            {
                'track_name': 'eye_l_widen',
                'ja_range': (0.55, 1.0),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.55) / 0.45) * 0.2
                }
            )

    mappings.append(
            {
                'track_name': 'eye_r_widen',
                'ja_range': (0.55, 1.0),
                'li_range': (-1.0, 1.0),
                'weight_func': lambda ja, li: max(0, (ja - 0.55) / 0.45) * 0.2
                }
            )

    mappings.append(
            {
                'track_name': 'eye_l_oculi_squint_outer_lower',
                'ja_range': (0.0, 0.4),
                'li_range': (0.25, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.25) / 0.75) * max(0, (0.4 - ja) / 0.4) * 0.35
                }
            )

    mappings.append(
            {
                'track_name': 'eye_r_oculi_squint_outer_lower',
                'ja_range': (0.0, 0.4),
                'li_range': (0.25, 1.0),
                'weight_func': lambda ja, li: max(0, (li - 0.25) / 0.75) * max(0, (0.4 - ja) / 0.4) * 0.35
                }
            )

    mappings.append(
            {
                'track_name': 'lips_mid_shift_up',
                'ja_range': (0.0, 0.3),
                'li_range': (-0.5, 0.5),
                'weight_func': lambda ja, li: max(0, (0.3 - ja) / 0.3) * 0.15
                }
            )

    mappings.append(
            {
                'track_name': 'lips_mid_shift_dn',
                'ja_range': (0.4, 1.0),
                'li_range': (-0.5, 0.5),
                'weight_func': lambda ja, li: max(0, (ja - 0.4) / 0.6) * 0.15
                }
            )

    return mappings

BILABIALS = frozenset({'M', 'B', 'P'})
LABIODENTALS = frozenset({'F', 'V'})
SIBILANTS = frozenset({'S', 'Z', 'SH', 'ZH', 'CH', 'JH'})
DENTALS = frozenset({'TH', 'DH'})
ALVEOLARS = frozenset({'T', 'D', 'N', 'L'})
VELARS = frozenset({'K', 'G', 'NG'})
GLIDES = frozenset({'W', 'Y', 'R'})
ROUNDED_VOWELS = frozenset({'UW', 'OW', 'OY', 'AO', 'AW'})
WIDE_VOWELS = frozenset({'IY', 'EY', 'AE', 'EH', 'IH'})

def get_phoneme_track_overrides() -> Dict[str, Dict[str, float]]:
    """Get phoneme-specific track overrides"""
    overrides = {}

    for phoneme in BILABIALS:
        overrides[phoneme] = {
            'lips_together_up': 1.0,
            'lips_together_dn': 1.0,
            'lips_tighten_up': 0.8,
            'lips_tighten_dn': 0.8,
            'jaw_mid_open': 0.0,
            'jaw_mid_close': 0.6,
            'lips_apart_up': 0.0,
            'lips_apart_dn': 0.0,
            }

    for phoneme in LABIODENTALS:
        overrides[phoneme] = {
            'lips_l_lower_raise': 0.9,
            'lips_r_lower_raise': 0.9,
            'lips_suck_dn': 0.6,
            'jaw_mid_open': 0.08,
            'lips_apart_up': 0.2,
            'lips_apart_dn': 0.15,
            }

    for phoneme in {'S', 'Z'}:
        overrides[phoneme] = {
            'jaw_mid_open': 0.05,
            'lips_l_corner_stretch': 0.8,
            'lips_r_corner_stretch': 0.8,
            'lips_l_stretch': 0.6,
            'lips_r_stretch': 0.6,
            'lips_apart_up': 0.15,
            'lips_apart_dn': 0.15,
            }

    for phoneme in {'SH', 'ZH', 'CH', 'JH'}:
        overrides[phoneme] = {
            'jaw_mid_open': 0.12,
            'lips_l_purse': 0.6,
            'lips_r_purse': 0.6,
            'lips_l_funnel': 0.4,
            'lips_r_funnel': 0.4,
            'lips_apart_up': 0.2,
            'lips_apart_dn': 0.2,
            }

    for phoneme in DENTALS:
        overrides[phoneme] = {
            'tongue_mid_fwd': 0.85,
            'tongue_mid_tip_up': 0.5,
            'jaw_mid_open': 0.12,
            'lips_apart_up': 0.25,
            'lips_apart_dn': 0.25,
            }

    for phoneme in {'T', 'D'}:
        overrides[phoneme] = {
            'tongue_mid_lift': 0.75,
            'tongue_mid_tip_up': 0.7,
            'jaw_mid_open': 0.1,
            }

    overrides['N'] = {
        'tongue_mid_lift': 0.7,
        'tongue_mid_tip_up': 0.6,
        'jaw_mid_open': 0.08,
        'lips_together_up': 0.0,
        'lips_together_dn': 0.0,
        }

    overrides['L'] = {
        'tongue_mid_lift': 0.85,
        'tongue_mid_tip_up': 0.8,
        'jaw_mid_open': 0.25,
        'lips_apart_up': 0.3,
        'lips_apart_dn': 0.35,
        }

    for phoneme in VELARS:
        overrides[phoneme] = {
            'tongue_mid_base_up': 0.7,
            'tongue_mid_base_back': 0.5,
            'jaw_mid_open': 0.35,
            }

    overrides['W'] = {
        'lips_l_purse': 0.95,
        'lips_r_purse': 0.95,
        'lips_l_funnel': 0.8,
        'lips_r_funnel': 0.8,
        'jaw_mid_open': 0.1,
        'lips_apart_up': 0.15,
        'lips_apart_dn': 0.15,
        }

    overrides['R'] = {
        'lips_l_purse': 0.5,
        'lips_r_purse': 0.5,
        'lips_l_funnel': 0.4,
        'lips_r_funnel': 0.4,
        'tongue_mid_base_up': 0.4,
        'jaw_mid_open': 0.2,
        }

    overrides['Y'] = {
        'lips_l_corner_wide': 0.5,
        'lips_r_corner_wide': 0.5,
        'jaw_mid_open': 0.15,
        }

    overrides['HH'] = {
        'jaw_mid_open': 0.4,
        'lips_apart_up': 0.4,
        'lips_apart_dn': 0.5,
        }

    return overrides

class JALIToCp77Bridge:
    """Maps JALI (JA, LI) field to CP77 LipsyncPoseOutput tracks"""
    LIPSYNC_POSE_SUFFIX = 'LipsyncPoseOutput'

    def __init__(self):
        self.mappings = build_jali_track_mappings()
        self.phoneme_overrides = get_phoneme_track_overrides()
        self._track_name_set = {m['track_name'] for m in self.mappings}

    def _get_lipsync_track_name(self, base_name: str) -> str:
        return f"{base_name}{self.LIPSYNC_POSE_SUFFIX}"

    def jali_to_tracks(
            self,
            ja_curve: np.ndarray,
            li_curve: np.ndarray,
            track_names: List[str]
            ) -> np.ndarray:
        num_frames = len(ja_curve)
        num_tracks = len(track_names)

        track_map = {name: i for i, name in enumerate(track_names)}
        tracks = np.zeros((num_frames, num_tracks), dtype=np.float32)

        if IDX_JALI_JAW < num_tracks:
            tracks[:, IDX_JALI_JAW] = np.clip(ja_curve, 0.0, 1.0)
        if IDX_JALI_LIPS < num_tracks:
            tracks[:, IDX_JALI_LIPS] = np.clip(li_curve + 1.0, 0.0, 2.0)

        if IDX_LIPSYNC_ENVELOPE < num_tracks:
            tracks[:, IDX_LIPSYNC_ENVELOPE] = 1.0

        if IDX_FACE_ENVELOPE < num_tracks:
            tracks[:, IDX_FACE_ENVELOPE] = 1.0

        if IDX_LOWER_FACE < num_tracks:
            tracks[:, IDX_LOWER_FACE] = 1.0

        ja_clipped = np.clip(ja_curve, 0.0, 1.0)
        li_clipped = np.clip(li_curve, -1.0, 1.0)

        for mapping in self.mappings:
            base_name = mapping['track_name']
            lipsync_track_name = self._get_lipsync_track_name(base_name)
            track_idx = track_map.get(lipsync_track_name)

            if track_idx is None:
                track_idx = track_map.get(base_name)
                if track_idx is None:
                    continue

            try:
                weight_func = mapping['weight_func']
                for frame in range(num_frames):
                    ja = float(ja_clipped[frame])
                    li = float(li_clipped[frame])
                    weight = float(weight_func(ja, li))
                    weight = max(0.0, min(1.0, weight))

                    if weight > tracks[frame, track_idx]:
                        tracks[frame, track_idx] = weight
            except Exception:
                pass

        return tracks

    def add_phoneme_overrides(
            self,
            tracks: np.ndarray,
            phoneme_events: List,
            track_names: List[str],
            fps: float
            ) -> np.ndarray:
        track_map = {name: i for i, name in enumerate(track_names)}
        num_frames = tracks.shape[0]

        for event in phoneme_events:
            phoneme = event.phoneme.rstrip('012')

            if phoneme not in self.phoneme_overrides:
                continue

            overrides = self.phoneme_overrides[phoneme]

            start_frame = int(event.start * fps)
            end_frame = int(event.end * fps)

            start_frame = max(0, min(start_frame, num_frames - 1))
            end_frame = max(start_frame + 1, min(end_frame, num_frames))

            if start_frame >= end_frame:
                continue

            for base_name, target_weight in overrides.items():
                lipsync_track_name = self._get_lipsync_track_name(base_name)
                idx = track_map.get(lipsync_track_name)

                if idx is None:
                    idx = track_map.get(base_name)
                    if idx is None:
                        continue

                current_max = np.max(tracks[start_frame:end_frame, idx])

                if target_weight == 0.0:
                    tracks[start_frame:end_frame, idx] = 0.0
                elif target_weight > current_max:
                    tracks[start_frame:end_frame, idx] = target_weight
                else:
                    tracks[start_frame:end_frame, idx] = np.maximum(
                            tracks[start_frame:end_frame, idx],
                            target_weight
                            )

        return tracks

class JALIAnimationPipeline:
    def __init__(self, rig, setup, fps: float = 30.0):
        self.rig = rig
        self.setup = setup
        self.fps = fps

        from .jali_core import CoarticulationEngine, DominanceBlender, MotionCurveGenerator

        self.coarticulator = CoarticulationEngine()
        self.blender = DominanceBlender(fps=fps, tau=0.070)
        self.curve_gen = MotionCurveGenerator(fps=fps)
        self.bridge = JALIToCp77Bridge()

    def generate_animation(
            self,
            phoneme_events: List,
            audio_path: Optional[str] = None
            ) -> np.ndarray:
        if not phoneme_events:
            raise ValueError("No phoneme events provided")

        duration = phoneme_events[-1].end + 0.5

        unique = set(e.phoneme for e in phoneme_events
                     if e.phoneme not in ('SIL', 'SP'))
        has_real_phonemes = len(unique) > 2

        if has_real_phonemes:
            ja_curve, li_curve = self._curves_from_phonemes(
                phoneme_events, audio_path, duration)
        else:
            ja_curve, li_curve = self._curves_from_audio(
                phoneme_events, audio_path, duration)

        track_names = [str(n) if not isinstance(n, dict) else n.get('$value', '')
                       for n in self.rig.track_names]

        tracks = self.bridge.jali_to_tracks(ja_curve, li_curve, track_names)

        num_tracks = len(track_names)
        for i in range(154, min(240, num_tracks)):
            tracks[:, i] = 1.0

        if has_real_phonemes:
            tracks = self.bridge.add_phoneme_overrides(
                    tracks, phoneme_events, track_names, self.fps)

        return tracks

    def _curves_from_phonemes(self, events, audio_path, duration):
        events = self.coarticulator.apply_rules(events)

        if audio_path:
            from .jali_core import AcousticAnalyzer
            try:
                analyzer = AcousticAnalyzer(audio_path)
                events = analyzer.modulate_events(events)
            except Exception as e:
                pass

        _times, ja, li = self.blender.blend_jali_parameters(events, duration)
        return ja, li

    def _curves_from_audio(self, events, audio_path, duration):
        import math

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
            return ja, li

        from .jali_core import PARSELMOUTH_AVAILABLE
        if not PARSELMOUTH_AVAILABLE:
            ja[sounding] = 0.4
            return ja, li

        import parselmouth
        from parselmouth.praat import call

        sound = parselmouth.Sound(audio_path)
        intensity = sound.to_intensity(time_step=0.01)
        pitch = sound.to_pitch(time_step=0.01)

        int_vals, pitch_vals = [], []
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

        return ja, li

def keyframe_tracks(
        armature_obj,
        rig,
        tracks: np.ndarray,
        start_frame: int = 1,
        threshold: float = 0.005,
        ):
    """Keyframe JALI track weights onto the armature's custom properties."""
    if not BPY_AVAILABLE:
        raise ImportError("Blender not available")

    from .animtools import _assign_action
    from .tracks import get_action_fcurves, _bulk_set_keyframes

    if not armature_obj.animation_data:
        armature_obj.animation_data_create()

    action = armature_obj.animation_data.action
    if action is None:
        action = bpy.data.actions.new(name="JALI_Lipsync")
        action.use_fake_user = True
        _assign_action(armature_obj.animation_data, action)

    fcurves = get_action_fcurves(action)
    if fcurves is None and hasattr(action, 'layers'):
        try:
            if len(action.layers) == 0:
                action.layers.new(name="Layer")
            layer = action.layers[0]
            if len(layer.strips) == 0:
                layer.strips.new(type='KEYFRAME')
            strip = layer.strips[0]
            if len(strip.channelbags) == 0 and hasattr(action, 'slots'):
                slot = None
                if len(action.slots) > 0:
                    slot = action.slots[0]
                else:
                    slot = action.slots.new(name=action.name, id_type='OBJECT')
                strip.channelbags.new(slot=slot)
                adt = armature_obj.animation_data
                if hasattr(adt, 'action_slot'):
                    adt.action_slot = slot
            fcurves = get_action_fcurves(action)
        except Exception as e:
            pass

    if fcurves is None:
        return 0

    track_names = [str(n) if not isinstance(n, dict) else n.get('$value', '')
                   for n in rig.track_names]

    num_frames = tracks.shape[0]
    tracks_keyed = 0

    for track_idx, name in enumerate(track_names):
        if not name:
            continue

        values = tracks[:, track_idx]
        if float(np.max(np.abs(values))) < 0.001:
            continue

        data_path = f'["{name}"]'

        fc = fcurves.find(data_path=data_path)
        if fc is not None:
            fc.keyframe_points.clear()
            fcurves.remove(fc)
        fc = fcurves.new(data_path=data_path)

        frames = []
        vals = []
        prev = None
        for i in range(num_frames):
            v = float(values[i])
            if i == 0 or i == num_frames - 1:
                frames.append(float(start_frame + i))
                vals.append(v)
                prev = v
            elif prev is None or abs(v - prev) > threshold:
                frames.append(float(start_frame + i))
                vals.append(v)
                prev = v

        if frames:
            _bulk_set_keyframes(fc, frames, vals, interpolation='LINEAR')
            tracks_keyed += 1

    return tracks_keyed