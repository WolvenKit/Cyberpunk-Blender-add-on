from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .constants import (
    ENV_FACE_ENVELOPE as IDX_FACE_ENVELOPE, ENV_JALI_JAW as IDX_JALI_JAW, ENV_JALI_LIPS as IDX_JALI_LIPS,
    ENV_LIPSYNC_ENVELOPE as IDX_LIPSYNC_ENVELOPE, ENV_LOWER_FACE as IDX_LOWER_FACE,
    ENV_MUZZLE_BROWS as IDX_MUZZLE_BROWS, ENV_MUZZLE_EYES as IDX_MUZZLE_EYES, ENV_MUZZLE_LIPS as IDX_MUZZLE_LIPS,
    ENV_UPPER_FACE as IDX_UPPER_FACE,
    )


def build_jali_track_mappings() -> List[Dict]:
    """Build JALI  -> CP77 track mappings calibrated against game lipsync data.

    Game lipsync.json shows JA slider range 0–0.43, LI range −0.09–0.48.
    LipsyncPoseOutput peaks: jaw_mid_open=0.45, corner_up=0.53, pull=0.32,
    together_dn=1.10, purse=0.22, funnel=0.05, suck_dn=0.48.

    Weight functions are calibrated so that at each phoneme's canonical
    JA/LI values from ARPABET_JALI_MAP, the output matches the game peak
    magnitude.
    """

    mappings = []
    def _m(name, fn):
        mappings.append({'track_name': name, 'weight_func': fn})

    # ── JAW ────────────────────────────────────────────────────────────
    # jaw_mid_open: game peak 0.45 at AA (ja=1.0)  -> scale 0.45
    _m('jaw_mid_open',    lambda ja, li: ja * 0.45)
    # jaw_mid_close: active when jaw near-closed (bilabials)
    _m('jaw_mid_close',   lambda ja, li: max(0, 1.0 - ja / 0.15) * 0.6)
    # jaw_mid_clench: clenched jaw, low lip activity
    _m('jaw_mid_clench',  lambda ja, li: max(0, 1.0 - ja / 0.1) * max(0, 1.0 - abs(li) / 0.3) * 0.4)
    # jaw_mid_shift_fwd: slight forward for some consonants
    _m('jaw_mid_shift_fwd', lambda ja, li: min(1, max(0, ja / 0.3)) * max(0, -li / 0.6) * 0.15)

    # ── LIP APERTURE ──────────────────────────────────────────────────
    # lips_apart: game doesn't use these in lipsync outputs, but gestures
    # show peaks 0.58 (yawn). Scale modestly.
    _m('lips_apart_up',   lambda ja, li: max(0, (ja - 0.2) / 0.8) * 0.5)
    _m('lips_apart_dn',   lambda ja, li: max(0, (ja - 0.15) / 0.85) * 0.6)

    # lips_together: game peak 1.10 at bilabial (ja=0, li=0)
    # Activated when jaw is nearly closed and lips aren't spread
    _m('lips_together_up', lambda ja, li: max(0, 1.0 - ja / 0.12) * max(0, 1.0 - abs(li) / 0.4) * 1.1)
    _m('lips_together_dn', lambda ja, li: max(0, 1.0 - ja / 0.12) * max(0, 1.0 - abs(li) / 0.4) * 1.1)

    # lips_tighten: game peak ~0.15 during pucker/closure
    _m('lips_tighten_up', lambda ja, li: max(0, 1.0 - ja / 0.15) * 0.15)
    _m('lips_tighten_dn', lambda ja, li: max(0, 1.0 - ja / 0.15) * 0.15)

    # ── LIP SPREAD / WIDE (LI > 0) ───────────────────────────────────
    # lips_l/r_corner_up: game peak 0.53 at IY (li=0.9)
    _m('lips_l_corner_up', lambda ja, li: max(0, li) * 0.59)
    _m('lips_r_corner_up', lambda ja, li: max(0, li) * 0.59)

    # lips_l/r_corner_wide: modest widening
    _m('lips_l_corner_wide', lambda ja, li: max(0, (li - 0.1) / 0.9) * (1.0 - ja * 0.3) * 0.2)
    _m('lips_r_corner_wide', lambda ja, li: max(0, (li - 0.1) / 0.9) * (1.0 - ja * 0.3) * 0.2)

    # lips_l/r_corner_stretch: game peak 0.10 at IY
    _m('lips_l_corner_stretch', lambda ja, li: max(0, li) * 0.11)
    _m('lips_r_corner_stretch', lambda ja, li: max(0, li) * 0.11)

    # lips_l/r_stretch: game peak 0.10
    _m('lips_l_stretch',  lambda ja, li: max(0, (li - 0.2) / 0.8) * 0.13)
    _m('lips_r_stretch',  lambda ja, li: max(0, (li - 0.2) / 0.8) * 0.13)

    # lips_l/r_pull: game peak 0.32 at IY
    _m('lips_l_pull',     lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.36)
    _m('lips_r_pull',     lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.36)

    # lips_l/r_upper_raise: game peak 0.08
    _m('lips_l_upper_raise', lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.09)
    _m('lips_r_upper_raise', lambda ja, li: max(0, (li - 0.1) / 0.9) * 0.09)

    # ── LIP PUCKER / ROUND (LI < 0) ──────────────────────────────────
    # lips_l/r_purse: game peak 0.22 at UW (li=−0.95)
    _m('lips_l_purse',    lambda ja, li: max(0, -li - 0.1) / 0.9 * (1.0 - ja * 0.3) * 0.24 if li < -0.1 else 0.0)
    _m('lips_r_purse',    lambda ja, li: max(0, -li - 0.1) / 0.9 * (1.0 - ja * 0.3) * 0.24 if li < -0.1 else 0.0)

    # lips_l/r_funnel: game peak 0.05 — very light rounding
    _m('lips_l_funnel',   lambda ja, li: max(0, -li - 0.3) / 0.7 * 0.07 if li < -0.3 else 0.0)
    _m('lips_r_funnel',   lambda ja, li: max(0, -li - 0.3) / 0.7 * 0.07 if li < -0.3 else 0.0)

    # lips_puff: minor cheek/lip inflation during pucker
    _m('lips_puff_up',    lambda ja, li: max(0, -li - 0.2) / 0.8 * (1.0 - ja) * 0.04)
    _m('lips_puff_dn',    lambda ja, li: max(0, -li - 0.2) / 0.8 * (1.0 - ja) * 0.04)

    # ── LIP CORNER VERTICAL ──────────────────────────────────────────
    # lips_l/r_corner_dn: game peak 0.10, active at high JA with neutral/neg LI
    _m('lips_l_corner_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * max(0, (0.3 - li) / 0.8) * 0.15)
    _m('lips_r_corner_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * max(0, (0.3 - li) / 0.8) * 0.15)

    # ── LIP SECONDARY ────────────────────────────────────────────────
    # lips_l/r_lower_raise: game peak 0.10 — for F/V (labiodental)
    _m('lips_l_lower_raise', lambda ja, li: min(1.0, ja / 0.15) * max(0, 1.0 - ja / 0.3) * 0.15)
    _m('lips_r_lower_raise', lambda ja, li: min(1.0, ja / 0.15) * max(0, 1.0 - ja / 0.3) * 0.15)

    # lips_suck_up: minor upper lip tuck
    _m('lips_suck_up',    lambda ja, li: max(0, 1.0 - ja / 0.2) * 0.08)
    # lips_suck_dn: game peak 0.48 — significant lower lip movement
    _m('lips_suck_dn',    lambda ja, li: min(1.0, ja / 0.1) * max(0, 1.0 - ja / 0.5) * 0.55)

    # lips_chin_raise: game peak 0.09 — very subtle
    _m('lips_chin_raise', lambda ja, li: max(0, 1.0 - ja / 0.4) * 0.09)

    # lips_mid_shift
    _m('lips_mid_shift_up', lambda ja, li: max(0, 1.0 - ja / 0.3) * 0.06)
    _m('lips_mid_shift_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * 0.06)

    # ── CHEEK ─────────────────────────────────────────────────────────
    _m('cheek_l_suck', lambda ja, li: max(0, li - 0.2) / 0.8 * max(0, 1.0 - ja * 2) * 0.15)
    _m('cheek_r_suck', lambda ja, li: max(0, li - 0.2) / 0.8 * max(0, 1.0 - ja * 2) * 0.15)
    _m('cheek_l_puff', lambda ja, li: max(0, -li - 0.15) / 0.85 * (1.0 - ja) * 0.1)
    _m('cheek_r_puff', lambda ja, li: max(0, -li - 0.15) / 0.85 * (1.0 - ja) * 0.1)

    # ── TONGUE ────────────────────────────────────────────────────────
    # tongue_mid_base_up: game peak 1.0 — major tongue movement
    _m('tongue_mid_base_up', lambda ja, li: min(1.0, max(0, ja / 0.5)) * 0.8)
    # tongue_mid_base_back: game peak 1.0
    _m('tongue_mid_base_back', lambda ja, li: min(1.0, max(0, ja / 0.4)) * 0.7)
    # tongue_mid_base_front
    _m('tongue_mid_base_front', lambda ja, li: max(0, ja / 0.4) * max(0, -li / 0.4) * 0.3)
    # tongue_mid_fwd: game peak 0.03 — barely moves
    _m('tongue_mid_fwd',  lambda ja, li: min(1.0, max(0, ja / 0.3)) * 0.03)
    # tongue_mid_lift: for alveolars
    _m('tongue_mid_lift', lambda ja, li: min(1.0, max(0, ja / 0.4)) * 0.5)
    # tongue_mid_tip_up: for alveolars
    _m('tongue_mid_tip_up', lambda ja, li: min(1.0, max(0, ja / 0.35)) * 0.45)
    # tongue_mid_tip_dn: game peak 0.24
    _m('tongue_mid_tip_dn', lambda ja, li: max(0, (ja - 0.3) / 0.7) * 0.24)

    # ── NOSE / NASOLABIAL ─────────────────────────────────────────────
    _m('lips_l_nasolabialDeepener', lambda ja, li: max(0, li - 0.15) / 0.85 * 0.15)
    _m('lips_r_nasolabialDeepener', lambda ja, li: max(0, li - 0.15) / 0.85 * 0.15)
    _m('nose_l_snear',    lambda ja, li: max(0, li - 0.2) / 0.8 * 0.06)
    _m('nose_r_snear',    lambda ja, li: max(0, li - 0.2) / 0.8 * 0.06)
    _m('nose_l_compress', lambda ja, li: max(0, -li - 0.2) / 0.8 * 0.08)
    _m('nose_r_compress', lambda ja, li: max(0, -li - 0.2) / 0.8 * 0.08)

    # ── NECK / THROAT ─────────────────────────────────────────────────
    # neck_throat_open: game peak 0.76 — major visible throat motion
    _m('neck_throat_open', lambda ja, li: ja * 0.76)
    # neck_throat_compress: game peak 0.39
    _m('neck_throat_compress', lambda ja, li: max(0, 1.0 - ja / 0.5) * 0.39)
    # neck_throat_adamsApple_up: game peak 0.21
    _m('neck_throat_adamsApple_up', lambda ja, li: max(0, 1.0 - ja / 0.3) * 0.21)
    # neck_throat_adamsApple_dn: game peak 0.76
    _m('neck_throat_adamsApple_dn', lambda ja, li: ja * 0.76)
    # neck_tighten: game peak 0.48 — active during jaw effort
    _m('neck_tighten',    lambda ja, li: ja * 0.48)
    # neck platysma: subtle
    _m('neck_l_platysma_flex', lambda ja, li: ja * 0.24)
    _m('neck_r_platysma_flex', lambda ja, li: ja * 0.24)
    _m('neck_l_stretch',  lambda ja, li: ja * 0.045)
    _m('neck_r_stretch',  lambda ja, li: ja * 0.045)

    # ── EYES / BROWS (speech emphasis) ────────────────────────────────
    # These are driven by jaw emphasis (loud/emphatic speech)
    _m('eye_l_brows_raise_out', lambda ja, li: max(0, (ja - 0.4) / 0.6) * 0.41)
    _m('eye_r_brows_raise_out', lambda ja, li: max(0, (ja - 0.4) / 0.6) * 0.41)
    _m('eye_l_brows_raise_in',  lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.41)
    _m('eye_r_brows_raise_in',  lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.41)
    _m('eye_l_widen', lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.2)
    _m('eye_r_widen', lambda ja, li: max(0, (ja - 0.5) / 0.5) * 0.2)
    _m('eye_l_oculi_squint_outer_lower', lambda ja, li: max(0, li - 0.15) / 0.85 * max(0, 1.0 - ja) * 0.4)
    _m('eye_r_oculi_squint_outer_lower', lambda ja, li: max(0, li - 0.15) / 0.85 * max(0, 1.0 - ja) * 0.4)

    return mappings

# Phoneme classification sets (should be imported from jali_core.py)
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
    """Phoneme-specific track overrides calibrated against game lipsync data.

    These override the JALI curve-based mappings for articulatory constraints
    that cannot be expressed as smooth JA/LI functions.

    Game data reference: lipsync.json, gestures.json peak values.
    """
    overrides = {}

    # Bilabials (M, B, P) — game shows together_dn peaks >1.0
    # Wide-lip tracks are explicitly cleared so the dominance blend
    # from surrounding vowels doesn't carry the wide shape through
    # the closure (e.g. "way be" — EY decay  -> B  -> IY rise must
    # have a clean reset at the bilabial).
    for phoneme in BILABIALS:
        overrides[phoneme] = {
            'lips_together_up': 1.0,
            'lips_together_dn': 1.1,      # game peak 1.10
            'lips_tighten_up': 0.15,
            'lips_tighten_dn': 0.15,
            'jaw_mid_open': 0.0,
            'jaw_mid_close': 0.56,         # game corners_up shows 0.56
            'lips_apart_up': 0.0,
            'lips_apart_dn': 0.0,
            'neck_tighten': 0.2,
            # Clear wide-lip influence during closure
            'lips_l_pull': 0.0,
            'lips_r_pull': 0.0,
            'lips_l_corner_up': 0.0,
            'lips_r_corner_up': 0.0,
            'lips_l_corner_stretch': 0.0,
            'lips_r_corner_stretch': 0.0,
            'lips_l_stretch': 0.0,
            'lips_r_stretch': 0.0,
        }

    # Labiodentals (F, V) — lower lip to teeth, also not wide
    for phoneme in LABIODENTALS:
        overrides[phoneme] = {
            'lips_l_lower_raise': 0.10,    # game peak 0.10
            'lips_r_lower_raise': 0.10,
            'lips_suck_dn': 0.45,          # game peak 0.48
            'jaw_mid_open': 0.08,
            'lips_apart_up': 0.15,
            'lips_apart_dn': 0.12,
            # Clear wide-lip influence
            'lips_l_pull': 0.0,
            'lips_r_pull': 0.0,
            'lips_l_corner_up': 0.0,
            'lips_r_corner_up': 0.0,
            'lips_l_corner_stretch': 0.0,
            'lips_r_corner_stretch': 0.0,
            'lips_l_stretch': 0.0,
            'lips_r_stretch': 0.0,
        }

    # Sibilants S, Z — narrow jaw, stretched
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

    # Postalveolar SH, ZH, CH, JH — slight pucker, lips rounded not wide
    for phoneme in {'SH', 'ZH', 'CH', 'JH'}:
        overrides[phoneme] = {
            'jaw_mid_open': 0.12,
            'lips_l_purse': 0.20,          # game peak 0.22
            'lips_r_purse': 0.20,
            'lips_l_funnel': 0.04,         # game peak 0.05
            'lips_r_funnel': 0.04,
            'lips_apart_up': 0.15,
            'lips_apart_dn': 0.15,
            # Clear wide-lip influence (puckered shape)
            'lips_l_pull': 0.0,
            'lips_r_pull': 0.0,
            'lips_l_corner_up': 0.0,
            'lips_r_corner_up': 0.0,
            'lips_l_corner_stretch': 0.0,
            'lips_r_corner_stretch': 0.0,
            'lips_l_stretch': 0.0,
            'lips_r_stretch': 0.0,
        }

    # Dentals (TH, DH) — tongue forward
    for phoneme in DENTALS:
        overrides[phoneme] = {
            'tongue_mid_fwd': 0.03,        # game peak 0.03
            'tongue_mid_tip_up': 0.22,     # game peak 0.22
            'jaw_mid_open': 0.12,
            'lips_apart_up': 0.20,
            'lips_apart_dn': 0.20,
        }

    # Alveolars T, D
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

    # Velars (K, G, NG) — tongue base
    for phoneme in VELARS:
        overrides[phoneme] = {
            'tongue_mid_base_up': 0.80,    # game peak 1.0
            'tongue_mid_base_back': 0.70,  # game peak 1.0
            'jaw_mid_open': 0.30,
        }

    # W — strong lip rounding
    overrides['W'] = {
        'lips_l_purse': 0.22,
        'lips_r_purse': 0.22,
        'lips_l_funnel': 0.05,
        'lips_r_funnel': 0.05,
        'jaw_mid_open': 0.10,
        'lips_apart_up': 0.12,
        'lips_apart_dn': 0.12,
    }

    # R — lip protrusion
    overrides['R'] = {
        'lips_l_purse': 0.15,
        'lips_r_purse': 0.15,
        'tongue_mid_base_up': 0.40,
        'jaw_mid_open': 0.20,
    }

    # Y — wide spread
    overrides['Y'] = {
        'lips_l_corner_wide': 0.20,
        'lips_r_corner_wide': 0.20,
        'jaw_mid_open': 0.15,
    }

    # HH — open, relaxed
    overrides['HH'] = {
        'jaw_mid_open': 0.35,
        'lips_apart_up': 0.35,
        'lips_apart_dn': 0.40,
        'neck_throat_open': 0.50,
    }

    return overrides


class JALIToCp77Bridge:
    """Maps JALI (JA, LI) field to CP77 LipsyncPoseOutput tracks

    The JALI field divides into regions:
        - JA (Jaw): Controls jaw_mid_open and related poses
        - LI (Lip): Controls lip shaping (wide/stretch vs purse/funnel)
        - Combined: Controls composite shapes

    The solver's apply_lipsync_poses() adds LipsyncPoseOutput values to main tracks:
        mainPose = clamp(mainPose + lipsyncPose, 0, 1)
    """

    # Suffix for lipsync pose output tracks
    LIPSYNC_POSE_SUFFIX = 'LipsyncPoseOutput'

    def __init__(self):
        """Initialize mapping tables"""
        self.mappings = build_jali_track_mappings()
        self.phoneme_overrides = get_phoneme_track_overrides()

        # Build track name lookup for faster access
        self._track_name_set = {m['track_name'] for m in self.mappings}

    def _get_lipsync_track_name(self, base_name: str) -> str:
        """Convert base track name to LipsyncPoseOutput track name

        Args:
            base_name: Base track name (e.g., 'jaw_mid_open')

        Returns:
            LipsyncPoseOutput track name (e.g., 'jaw_mid_openLipsyncPoseOutput')
        """
        return f"{base_name}{self.LIPSYNC_POSE_SUFFIX}"

    def jali_to_tracks(
            self,
            ja_curve: np.ndarray,
            li_curve: np.ndarray,
            track_names: List[str]
            ) -> np.ndarray:
        """Convert JALI curves to CP77 track weights

        Writes pose activations to LipsyncPoseOutput tracks
        The solver will add these to main tracks via apply_lipsync_poses().

        Args:
            ja_curve: Jaw curve over time (N,) - values in [0, 1]
            li_curve: Lip curve over time (N,) - values in [-1, 1]
            track_names: List of all track names from rig

        Returns:
            Track weights array (N, M) where M = len(track_names)
        """
        num_frames = len(ja_curve)
        num_tracks = len(track_names)

        # Create track name  -> index mapping
        track_map = {name: i for i, name in enumerate(track_names)}

        # Initialize track weights (all zeros)
        tracks = np.zeros((num_frames, num_tracks), dtype=np.float32)

        # jaliJaw (Track 7) - Direct from JA curve
        if IDX_JALI_JAW < num_tracks:
            tracks[:, IDX_JALI_JAW] = np.clip(ja_curve, 0.0, 1.0)
        # jaliLips (Track 8) - Transform LI from [-1,1] to [0,2] range
        # CP77 expects: 0=pucker, 1=neutral, 2=wide
        if IDX_JALI_LIPS < num_tracks:
            tracks[:, IDX_JALI_LIPS] = np.clip(li_curve + 1.0, 0.0, 2.0)

        # Enable lipsync envelope (required for lipsync poses to be applied)
        if IDX_LIPSYNC_ENVELOPE < num_tracks:
            tracks[:, IDX_LIPSYNC_ENVELOPE] = 1.0

        # Enable face envelope
        if IDX_FACE_ENVELOPE < num_tracks:
            tracks[:, IDX_FACE_ENVELOPE] = 1.0

        # Set lower face to full (for lipsync)
        if IDX_LOWER_FACE < num_tracks:
            tracks[:, IDX_LOWER_FACE] = 1.0

        # Game lipsync data shows these envelopes active during speech:
        # muzzleLips tracks lipSyncEnvelope, muzzleEyes ramps to 1.0
        if IDX_MUZZLE_LIPS < num_tracks:
            tracks[:, IDX_MUZZLE_LIPS] = 1.0
        if IDX_MUZZLE_EYES < num_tracks:
            tracks[:, IDX_MUZZLE_EYES] = 1.0
        if IDX_MUZZLE_BROWS < num_tracks:
            tracks[:, IDX_MUZZLE_BROWS] = 0.41  # game peak
        if IDX_UPPER_FACE < num_tracks:
            tracks[:, IDX_UPPER_FACE] = 0.25     # game peak

        # === Apply pose mappings to LipsyncPoseOutput tracks ===

        # Clip curves to valid ranges
        ja_clipped = np.clip(ja_curve, 0.0, 1.0)
        li_clipped = np.clip(li_curve, -1.0, 1.0)

        for mapping in self.mappings:
            base_name = mapping['track_name']

            # Get the LipsyncPoseOutput track name
            lipsync_track_name = self._get_lipsync_track_name(base_name)
            track_idx = track_map.get(lipsync_track_name)

            if track_idx is None:
                # Fallback: some tracks might not have LipsyncPoseOutput versions
                # (e.g., tongue tracks in some rigs) - try main track
                track_idx = track_map.get(base_name)
                if track_idx is None:
                    continue

            # Compute weights for all frames
            try:
                weight_func = mapping['weight_func']
                for frame in range(num_frames):
                    ja = float(ja_clipped[frame])
                    li = float(li_clipped[frame])
                    weight = float(weight_func(ja, li))
                    weight = max(0.0, min(1.5, weight))

                    # Max blend (take higher activation)
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
        """Add phoneme-specific overrides for precise articulations.

        Applies hard constraints from phoneme_overrides dictionary with
        smooth fade in / fade out so the values ramp into and out of
        their target instead of creating step changes at frame boundaries.

        Envelope shape: sin² rise  -> hold  -> cos² fall (trapezoidal).

        Args:
            tracks: Current track weights (N, M)
            phoneme_events: List of PhonemeEvent objects
            track_names: Track name list
            fps: Frames per second

        Returns:
            Modified tracks array
        """
        track_map = {name: i for i, name in enumerate(track_names)}
        num_frames = tracks.shape[0]

        # Fade duration: 60ms gives a smooth ramp at 24-60fps
        fade_seconds = 0.060
        fade_frames = max(1, int(round(fade_seconds * fps)))

        for event in phoneme_events:
            phoneme = event.phoneme.rstrip('012')

            if phoneme not in self.phoneme_overrides:
                continue

            overrides = self.phoneme_overrides[phoneme]

            start_frame = int(event.start * fps)
            end_frame = int(event.end * fps)

            start_frame = max(0, min(start_frame, num_frames - 1))
            end_frame = max(start_frame + 1, min(end_frame, num_frames))

            n = end_frame - start_frame
            if n <= 0:
                continue

            # Trapezoidal envelope: 0  -> 1 (sin²)  -> hold  -> 1  -> 0 (cos²)
            # fi must be small enough that fade-in and fade-out do not
            # overlap, otherwise both edges write 0 across the same
            # frames and the override has no effect on the middle.
            # Use (n - 1) // 2 to guarantee at least one full-strength
            # frame between the two ramps.
            fi = min(fade_frames, (n - 1) // 2)
            envelope = np.ones(n, dtype=np.float32)
            if fi > 0:
                ramp = np.sin(0.5 * np.pi * np.arange(fi, dtype=np.float32) / fi) ** 2
                envelope[:fi] = ramp
                envelope[-fi:] = ramp[::-1]

            for base_name, target_weight in overrides.items():
                lipsync_track_name = self._get_lipsync_track_name(base_name)
                idx = track_map.get(lipsync_track_name)
                if idx is None:
                    idx = track_map.get(base_name)
                    if idx is None:
                        continue

                current = tracks[start_frame:end_frame, idx]

                if target_weight == 0.0:
                    # Soft closure: blend current  -> 0  -> current via envelope.
                    # At env=1 (middle), value = 0 (forced closure).
                    # At env=0 (edges), value = current (no change).
                    tracks[start_frame:end_frame, idx] = current * (1.0 - envelope)
                else:
                    # Soft override: ramp toward target, max-blend with current.
                    # Existing higher values are preserved at all frames.
                    target_curve = envelope * target_weight
                    tracks[start_frame:end_frame, idx] = np.maximum(
                            current, target_curve)

        return tracks


class JALIAnimationPipeline:
    """Complete JALI  -> CP77 animation pipeline

    Workflow:
        1. Phoneme detection (external - Praat, MFA, etc.)
        2. Phoneme  -> JALI parameters (jali_core.py)
        3. Co-articulation rules (jali_core.py)
        4. Acoustic modulation (jali_core.py)
        5. Dominance blending  -> (JA, LI) curves (jali_core.py)
        6. JALI  -> CP77 track mapping (this module)
        7. Phoneme-specific overrides (this module)
        8. Track solver  -> In-between + Correctives (tracksolvers.py)
        9. Bone transform application (facial.py)
    """

    def __init__(self, rig, setup, fps: float = 30.0):
        """
        Args:
            rig: RigSkeleton from facial.py
            setup: FacialSetup from facial.py
            fps: Animation framerate
        """
        self.rig = rig
        self.setup = setup
        self.fps = fps

        # Initialize components
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
        """Generate track weight curves from phonemes.

        Two paths:
        - Real phoneme data (MFA, etc.): coarticulation  -> dominance blending
        - Acoustic-only (detector gives all AH/SIL): per-frame amplitude/pitch

        Returns an (N, M) array of per-frame track values.
        """
        if not phoneme_events:
            raise ValueError("No phoneme events provided")

        duration = phoneme_events[-1].end + 0.5

        # Detect if we have real phoneme variety or just AH/SIL from detector
        unique = set(e.phoneme for e in phoneme_events
                     if e.phoneme not in ('SIL', 'SP'))
        has_real_phonemes = len(unique) > 2

        if has_real_phonemes:
            ja_curve, li_curve = self._curves_from_phonemes(
                phoneme_events, audio_path, duration)
        else:
            ja_curve, li_curve = self._curves_from_audio(
                phoneme_events, audio_path, duration)

        # JALI  -> CP77 track mapping (writes to LipsyncPoseOutput tracks)
        print("[JALI] Stage 4: JALI  -> CP77 track mapping...")
        track_names = [str(n) if not isinstance(n, dict) else n.get('$value', '')
                       for n in self.rig.track_names]

        tracks = self.bridge.jali_to_tracks(ja_curve, li_curve, track_names)

        # Override tracks [154-239] at 1.0 (passthrough) per game data
        num_tracks = len(track_names)
        for i in range(154, min(240, num_tracks)):
            tracks[:, i] = 1.0

        # Phoneme-specific overrides only meaningful with real phonemes
        if has_real_phonemes:
            print("[JALI] Stage 5: Phoneme overrides...")
            tracks = self.bridge.add_phoneme_overrides(
                    tracks, phoneme_events, track_names, self.fps)

        non_zero = int(np.sum(np.max(np.abs(tracks), axis=0) > 0.001))
        print(f"[JALI] Complete — {non_zero}/{num_tracks} active tracks, "
              f"{tracks.shape[0]} frames")
        return tracks

    def _curves_from_phonemes(self, events, audio_path, duration):
        """Full JALI pipeline for real phoneme sequences."""
        print("[JALI] Mode: Phoneme-based (dominance blending)")

        print("[JALI] Stage 1: Co-articulation...")
        events = self.coarticulator.apply_rules(events)

        if audio_path:
            print("[JALI] Stage 2: Acoustic modulation...")
            from .jali_core import AcousticAnalyzer
            try:
                analyzer = AcousticAnalyzer(audio_path)
                events = analyzer.modulate_events(events)
            except Exception as e:
                print(f"[JALI] Warning: Acoustic analysis failed: {e}")

        print("[JALI] Stage 3: Dominance blending...")
        _times, ja, li = self.blender.blend_jali_parameters(events, duration)
        return ja, li

    def _curves_from_audio(self, events, audio_path, duration):
        """Per-frame amplitude/pitch curves for acoustic-only detection.

        Matches the old JALICurveGenerator approach: amplitude drives jaw
        opening, pitch deviation drives lip shape.
        """
        import math
        print("[JALI] Mode: Acoustic-only (amplitude/pitch)")

        num_frames = int(duration * self.fps) + 1
        times = np.linspace(0, duration, num_frames, dtype=np.float32)

        # Build sounding mask from events
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
            print("[JALI]   No parselmouth — uniform fallback")
            ja[sounding] = 0.4
            return ja, li

        import parselmouth
        from parselmouth.praat import call

        sound = parselmouth.Sound(audio_path)
        intensity = sound.to_intensity(time_step=0.01)
        pitch = sound.to_pitch(time_step=0.01)

        # Global stats for normalization
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

        print(f"[JALI]   Intensity: mean={int_mean:.1f} std={int_std:.1f}")
        print(f"[JALI]   Pitch: mean={pitch_mean:.1f} std={pitch_std:.1f}")

        # Per-frame: amplitude  -> JA, pitch deviation  -> LI
        for i, t in enumerate(times):
            if not sounding[i]:
                continue
            iv = intensity.get_value(float(t))
            pv = pitch.get_value_at_time(float(t))

            if not math.isnan(iv):
                z = (iv - int_mean) / int_std
                # Map: mean intensity  -> JA=0.3, loud  -> 0.65, quiet  -> 0.1
                ja[i] = float(np.clip(0.3 + 0.35 * z, 0.05, 1.0))
            else:
                ja[i] = 0.3

            if not math.isnan(pv) and pv > 0:
                z = (pv - pitch_mean) / pitch_std
                li[i] = float(np.clip(0.3 * z, -0.8, 0.8))

        # Smooth (5-frame moving average, preserves timing)
        kernel = np.ones(5) / 5.0
        ja = np.convolve(ja, kernel, mode='same').astype(np.float32)
        li = np.convolve(li, kernel, mode='same').astype(np.float32)
        ja[~sounding] = 0.0
        li[~sounding] = 0.0

        print(f"[JALI]   JA range: {ja[sounding].min():.3f} – {ja[sounding].max():.3f}")
        print(f"[JALI]   LI range: {li[sounding].min():.3f} – {li[sounding].max():.3f}")
        return ja, li


def keyframe_tracks(
        armature_obj,
        rig,
        tracks: np.ndarray,
        start_frame: int = 1,
        threshold: float = 0.005,
        ):
    """Keyframe JALI track weights onto the armature's custom properties.

    The properties already exist on the armature from rig binding.
    This creates an action (with proper 5.x slot) and inserts sparse
    keyframes so the real-time solver can read them on each frame.

    FCurves are placed in the "Track Keys" action group so that
    export_anim_tracks can find them and restore the correct
    trackIndex via the armature's trackNames dict.

    Args:
        armature_obj: Blender armature object
        rig: RigData with track_names
        tracks: (num_frames, num_tracks) weight array
        start_frame: First frame number
        threshold: Minimum change between keys to insert

    Returns:
        Number of tracks that received keyframes.
    """
    if not BPY_AVAILABLE:
        raise ImportError("Blender not available")

    from .animtools import _assign_action
    from .tracks import (
        get_action_fcurves,
        _bulk_set_keyframes,
        add_track_action_group,
    )

    #  Ensure action with proper 5.x slot 
    if not armature_obj.animation_data:
        armature_obj.animation_data_create()

    action = armature_obj.animation_data.action
    if action is None:
        action = bpy.data.actions.new(name="JALI_Lipsync")
        action.use_fake_user = True
        _assign_action(armature_obj.animation_data, action)

    # On Blender 5.x, a brand-new action has no layers.
    # get_action_fcurves needs layers[0].strips[0].channelbags[0].
    # Bootstrap the structure if missing.
    #
    # NOTE: get_action_fcurves MUST be called BEFORE add_track_action_group
    # because on 5.x it creates the channelbag where groups live.
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
            print(f"[JALI] Failed to init 5.x action structure: {e}")

    if fcurves is None:
        print("[JALI] ERROR: Cannot access action fcurves")
        return 0

    action_group = add_track_action_group(action)

    #  Build track name list 
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

        if action_group is not None:
            fc.group = action_group

        # Sparse keyframe extraction — only key on significant change
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

    print(f"[JALI] Keyframed {tracks_keyed} tracks ({num_frames} frames)")
    return tracks_keyed