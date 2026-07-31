from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

from .phonemes import BILABIALS, DENTALS, LABIODENTALS, VELARS

@lru_cache(maxsize=1)
def build_jali_track_mappings() -> List[Dict]:

    mappings = []

    def _m(name, fn):
        mappings.append({'track_name': name, 'weight_func': fn})

    _m('jaw_mid_open', lambda ja, li: ja * 0.45)

    _m('jaw_mid_close', lambda ja, li: max(0, 1.0 - ja / 0.15) * 0.6)

    _m('jaw_mid_clench', lambda ja, li: max(0, 1.0 - ja / 0.1) * max(0, 1.0 - abs(li) / 0.3) * 0.4)

    _m('jaw_mid_shift_fwd', lambda ja, li: min(1, max(0, ja / 0.3)) * max(0, -li / 0.6) * 0.15)

    _m('lips_apart_up', lambda ja, li: max(0, (ja - 0.2) / 0.8) * 0.5)
    _m('lips_apart_dn', lambda ja, li: max(0, (ja - 0.15) / 0.85) * 0.6)

    _m('lips_together_up', lambda ja, li: max(0, 1.0 - ja / 0.12) * max(0, 1.0 - abs(li) / 0.4) * 1.1)
    _m('lips_together_dn', lambda ja, li: max(0, 1.0 - ja / 0.12) * max(0, 1.0 - abs(li) / 0.4) * 1.1)

    _m('lips_tighten_up', lambda ja, li: max(0, 1.0 - ja / 0.15) * 0.15)
    _m('lips_tighten_dn', lambda ja, li: max(0, 1.0 - ja / 0.15) * 0.15)

    _m('lips_l_corner_up', lambda ja, li: max(0, li) * 0.59)
    _m('lips_r_corner_up', lambda ja, li: max(0, li) * 0.59)

    _m('lips_l_corner_wide', lambda ja, li: max(0, (li - 0.1) / 0.9) * (1.0 - ja * 0.3) * 0.2)
    _m('lips_r_corner_wide', lambda ja, li: max(0, (li - 0.1) / 0.9) * (1.0 - ja * 0.3) * 0.2)

    _m('lips_l_corner_stretch', lambda ja, li: max(0, li) * 0.11)
    _m('lips_r_corner_stretch', lambda ja, li: max(0, li) * 0.11)

    _m('lips_l_stretch', lambda ja, li: max(0, (li - 0.2) / 0.8) * 0.13)
    _m('lips_r_stretch', lambda ja, li: max(0, (li - 0.2) / 0.8) * 0.13)

    _m('lips_l_pull', lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.36)
    _m('lips_r_pull', lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.36)

    _m('lips_l_upper_raise', lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.09)
    _m('lips_r_upper_raise', lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.09)

    _m('lips_l_purse', lambda ja, li: max(0, -li - 0.1) / 0.9 * (1.0 - ja * 0.3) * 0.24 if li < -0.1 else 0.0)
    _m('lips_r_purse', lambda ja, li: max(0, -li - 0.1) / 0.9 * (1.0 - ja * 0.3) * 0.24 if li < -0.1 else 0.0)

    _m('lips_l_funnel', lambda ja, li: max(0, -li - 0.3) / 0.7 * 0.07 if li < -0.3 else 0.0)
    _m('lips_r_funnel', lambda ja, li: max(0, -li - 0.3) / 0.7 * 0.07 if li < -0.3 else 0.0)

    _m('lips_puff_up', lambda ja, li: max(0, -li - 0.2) / 0.8 * (1.0 - ja) * 0.04)
    _m('lips_puff_dn', lambda ja, li: max(0, -li - 0.2) / 0.8 * (1.0 - ja) * 0.04)

    _m('lips_l_corner_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * max(0, (0.3 - li) / 0.8) * 0.15)
    _m('lips_r_corner_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * max(0, (0.3 - li) / 0.8) * 0.15)

    _m('lips_l_lower_raise', lambda ja, li: min(1.0, ja / 0.15) * max(0, 1.0 - ja / 0.3) * 0.15)
    _m('lips_r_lower_raise', lambda ja, li: min(1.0, ja / 0.15) * max(0, 1.0 - ja / 0.3) * 0.15)

    _m('lips_suck_up', lambda ja, li: max(0, 1.0 - ja / 0.2) * 0.08)

    _m('lips_suck_dn', lambda ja, li: min(1.0, ja / 0.1) * max(0, 1.0 - ja / 0.5) * 0.55)

    _m('lips_chin_raise', lambda ja, li: max(0, 1.0 - ja / 0.4) * 0.09)

    _m('lips_mid_shift_up', lambda ja, li: max(0, 1.0 - ja / 0.3) * 0.06)
    _m('lips_mid_shift_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * 0.06)

    _m('cheek_l_suck', lambda ja, li: max(0, li - 0.2) / 0.8 * max(0, 1.0 - ja * 2) * 0.15)
    _m('cheek_r_suck', lambda ja, li: max(0, li - 0.2) / 0.8 * max(0, 1.0 - ja * 2) * 0.15)
    _m('cheek_l_puff', lambda ja, li: max(0, -li - 0.15) / 0.85 * (1.0 - ja) * 0.1)
    _m('cheek_r_puff', lambda ja, li: max(0, -li - 0.15) / 0.85 * (1.0 - ja) * 0.1)

    _m('tongue_mid_base_up', lambda ja, li: min(1.0, max(0, ja / 0.5)) * 0.8)

    _m('tongue_mid_base_back', lambda ja, li: min(1.0, max(0, ja / 0.4)) * 0.7)

    _m('tongue_mid_base_front', lambda ja, li: max(0, ja / 0.4) * max(0, -li / 0.4) * 0.3)

    _m('tongue_mid_fwd', lambda ja, li: min(1.0, max(0, ja / 0.3)) * 0.03)

    _m('tongue_mid_lift', lambda ja, li: min(1.0, max(0, ja / 0.4)) * 0.5)

    _m('tongue_mid_tip_up', lambda ja, li: min(1.0, max(0, ja / 0.35)) * 0.45)

    _m('tongue_mid_tip_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * 0.24)

    _m('lips_l_nasolabialDeepener', lambda ja, li: max(0, li - 0.15) / 0.85 * 0.15)
    _m('lips_r_nasolabialDeepener', lambda ja, li: max(0, li - 0.15) / 0.85 * 0.15)
    _m('nose_l_snear', lambda ja, li: max(0, li - 0.2) / 0.8 * 0.06)
    _m('nose_r_snear', lambda ja, li: max(0, li - 0.2) / 0.8 * 0.06)
    _m('nose_l_compress', lambda ja, li: max(0, -li - 0.2) / 0.8 * 0.08)
    _m('nose_r_compress', lambda ja, li: max(0, -li - 0.2) / 0.8 * 0.08)

    _m('neck_throat_open', lambda ja, li: ja * 0.76)

    _m('neck_throat_compress', lambda ja, li: max(0, 1.0 - ja / 0.5) * 0.39)

    _m('neck_throat_adamsApple_up', lambda ja, li: max(0, 1.0 - ja / 0.3) * 0.21)

    _m('neck_throat_adamsApple_dn', lambda ja, li: ja * 0.76)

    _m('neck_tighten', lambda ja, li: ja * 0.48)

    _m('neck_l_platysma_flex', lambda ja, li: ja * 0.24)
    _m('neck_r_platysma_flex', lambda ja, li: ja * 0.24)
    _m('neck_l_stretch', lambda ja, li: ja * 0.045)
    _m('neck_r_stretch', lambda ja, li: ja * 0.045)

    _m('eye_l_brows_raise_out', lambda ja, li: max(0, (ja - 0.4) / 0.6) * 0.41)
    _m('eye_r_brows_raise_out', lambda ja, li: max(0, (ja - 0.4) / 0.6) * 0.41)
    _m('eye_l_brows_raise_in', lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.41)
    _m('eye_r_brows_raise_in', lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.41)
    _m('eye_l_widen', lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.2)
    _m('eye_r_widen', lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.2)
    _m('eye_l_oculi_squint_outer_lower', lambda ja, li: max(0, li - 0.15) / 0.85 * max(0, 1.0 - ja) * 0.4)
    _m('eye_r_oculi_squint_outer_lower', lambda ja, li: max(0, li - 0.15) / 0.85 * max(0, 1.0 - ja) * 0.4)

    return mappings

@lru_cache(maxsize=1)
def get_phoneme_track_overrides() -> Dict[str, Dict[str, float]]:

    overrides = {}

    for phoneme in BILABIALS:
        overrides[phoneme] = {
            'lips_together_up': 1.0,
            'lips_together_dn': 1.1,
            'lips_tighten_up': 0.15,
            'lips_tighten_dn': 0.15,
            'jaw_mid_open': 0.0,
            'jaw_mid_close': 0.56,
            'lips_apart_up': 0.0,
            'lips_apart_dn': 0.0,
            'neck_tighten': 0.2,

            'lips_l_pull': 0.0,
            'lips_r_pull': 0.0,
            'lips_l_corner_up': 0.0,
            'lips_r_corner_up': 0.0,
            'lips_l_corner_stretch': 0.0,
            'lips_r_corner_stretch': 0.0,
            'lips_l_stretch': 0.0,
            'lips_r_stretch': 0.0,
            }

    for phoneme in LABIODENTALS:
        overrides[phoneme] = {
            'lips_l_lower_raise': 0.10,
            'lips_r_lower_raise': 0.10,
            'lips_suck_dn': 0.45,
            'jaw_mid_open': 0.08,
            'lips_apart_up': 0.15,
            'lips_apart_dn': 0.12,

            'lips_l_pull': 0.0,
            'lips_r_pull': 0.0,
            'lips_l_corner_up': 0.0,
            'lips_r_corner_up': 0.0,
            'lips_l_corner_stretch': 0.0,
            'lips_r_corner_stretch': 0.0,
            'lips_l_stretch': 0.0,
            'lips_r_stretch': 0.0,
            }

    for phoneme in {'S', 'Z'}:
        overrides[phoneme] = {
            'jaw_mid_open': 0.05,
            'lips_l_corner_stretch': 0.10,
            'lips_r_corner_stretch': 0.10,
            'lips_l_stretch': 0.10,
            'lips_r_stretch': 0.10,
            'lips_apart_up': 0.10,
            'lips_apart_dn': 0.10,
            }

    for phoneme in {'SH', 'ZH', 'CH', 'JH'}:
        overrides[phoneme] = {
            'jaw_mid_open': 0.12,
            'lips_l_purse': 0.20,
            'lips_r_purse': 0.20,
            'lips_l_funnel': 0.04,
            'lips_r_funnel': 0.04,
            'lips_apart_up': 0.15,
            'lips_apart_dn': 0.15,

            'lips_l_pull': 0.0,
            'lips_r_pull': 0.0,
            'lips_l_corner_up': 0.0,
            'lips_r_corner_up': 0.0,
            'lips_l_corner_stretch': 0.0,
            'lips_r_corner_stretch': 0.0,
            'lips_l_stretch': 0.0,
            'lips_r_stretch': 0.0,
            }

    for phoneme in DENTALS:
        overrides[phoneme] = {
            'tongue_mid_fwd': 0.03,
            'tongue_mid_tip_up': 0.22,
            'jaw_mid_open': 0.12,
            'lips_apart_up': 0.20,
            'lips_apart_dn': 0.20,
            }

    for phoneme in {'T', 'D'}:
        overrides[phoneme] = {
            'tongue_mid_lift': 0.50,
            'tongue_mid_tip_up': 0.45,
            'jaw_mid_open': 0.10,
            }

    overrides['N'] = {
        'tongue_mid_lift': 0.45,
        'tongue_mid_tip_up': 0.40,
        'jaw_mid_open': 0.08,
        }

    overrides['L'] = {
        'tongue_mid_lift': 0.50,
        'tongue_mid_tip_up': 0.45,
        'jaw_mid_open': 0.25,
        'lips_apart_up': 0.25,
        'lips_apart_dn': 0.30,
        }

    for phoneme in VELARS:
        overrides[phoneme] = {
            'tongue_mid_base_up': 0.80,
            'tongue_mid_base_back': 0.70,
            'jaw_mid_open': 0.30,
            }

    overrides['W'] = {
        'lips_l_purse': 0.22,
        'lips_r_purse': 0.22,
        'lips_l_funnel': 0.05,
        'lips_r_funnel': 0.05,
        'jaw_mid_open': 0.10,
        'lips_apart_up': 0.12,
        'lips_apart_dn': 0.12,
        }

    overrides['R'] = {
        'lips_l_purse': 0.15,
        'lips_r_purse': 0.15,
        'tongue_mid_base_up': 0.40,
        'jaw_mid_open': 0.20,
        }

    overrides['Y'] = {
        'lips_l_corner_wide': 0.20,
        'lips_r_corner_wide': 0.20,
        'jaw_mid_open': 0.15,
        }

    overrides['HH'] = {
        'jaw_mid_open': 0.35,
        'lips_apart_up': 0.35,
        'lips_apart_dn': 0.40,
        'neck_throat_open': 0.50,
        }

    return overrides
