from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

try:
    import parselmouth
    from parselmouth.praat import call

    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False

try:
    import g2p_en
    G2P_AVAILABLE = True
except ImportError:
    G2P_AVAILABLE = False


@dataclass
class JALIViseme:
    """JALI viseme parameters for a phoneme

    Attributes:
        jaw: Vertical opening (0=closed, 1=max open)
        lip: Horizontal shaping (-1=pucker/round, 0=neutral, 1=wide/stretch)
        dominance: Co-articulation resistance (0=weak/vowel, 1=strong/consonant)
    """
    jaw: float
    lip: float
    dominance: float


@dataclass
class PhonemeEvent:
    """Timed phoneme with acoustic features

    Attributes:
        phoneme: Arpabet code (e.g., "AE", "B", "IY")
        start: Start time (seconds)
        end: End time (seconds)
    """
    phoneme: str
    start: float
    end: float

    # JALI parameters
    jaw: float = 0.5
    lip: float = 0.0
    dominance: float = 0.5

    # Acoustic modulation
    pitch: float = 0.0  # Paper §4.3: pitch deviation

    # Phoneme classification
    is_vowel: bool = False
    is_bilabial: bool = False
    is_labiodental: bool = False
    is_sibilant: bool = False
    is_tongue_only: bool = False
    is_lip_heavy: bool = False
    is_obstruent_nasal: bool = False
    lexically_stressed: bool = False
    stress_level: int = 0  # 0=unstressed, 1=secondary, 2=primary
    word_prominent: bool = True  # Paper §4.2: de-stressed words

    # Context (set by co-articulation engine)
    prev_is_pause: bool = False
    prev_is_vowel: bool = False
    word_index: int = -1  # Word boundary tracking for Rule 8

    # Pause boundary times — used to clamp onset/decay so phoneme
    # influence does not bleed across silence boundaries.
    prev_pause_end: float = float('-inf')
    next_pause_start: float = float('inf')

    # Natural phoneme bounds — preserved across coarticulation extensions.
    # `start` and `end` may be extended by Rule 2 (lip-heavy), but the
    # apex location and sustain duration must remain anchored to the
    # acoustic phoneme position.  Set to -1 means "not set".
    original_start: float = -1.0
    original_end: float = -1.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def apex(self) -> float:
        """Paper §4.2: apex coincides with beginning of the natural sound"""
        return self.original_start if self.original_start >= 0 else self.start

    @property
    def sustain_end(self) -> float:
        """Paper §4.2: apex sustained to 75% through phoneme."""
        if self.original_start >= 0 and self.original_end >= 0:
            orig_dur = self.original_end - self.original_start
            return self.original_start + 0.75 * orig_dur
        return self.start + 0.75 * self.duration

    @property
    def onset_duration(self) -> float:
        """Context-specific onset time BEFORE apex (paper §4.2).

        Paper: "onset begins 120ms before apex"
        Empirical: /m p b f/ after pause 137-240ms, after vowel 127-188ms
        """
        if self.phoneme in ('M', 'P', 'B'):
            return 0.180 if self.prev_is_pause else 0.155
        elif self.phoneme == 'F':
            return 0.160 if self.prev_is_pause else 0.140
        elif self.is_lip_heavy:
            return 0.150  # Paper: lip-protrusion extended
        else:
            return 0.120  # Default

    @property
    def decay_duration(self) -> float:
        """Paper §4.2: consistent 120ms decay, 150ms for lip-heavy"""
        return 0.150 if self.is_lip_heavy else 0.120


# PHONEME  -> JALI MAPPING (from paper Figure 4)

ARPABET_JALI_MAP: Dict[str, JALIViseme] = {
    # Silence
    'SIL': JALIViseme(0.0, 0.0, 0.0),
    'SP': JALIViseme(0.0, 0.0, 0.0),

    # CONSONANTS - High Dominance  

    # Bilabials - MUST close lips (paper §4.2, Constraint 1)
    'M': JALIViseme(0.0, 0.0, 1.0),  # MMM viseme
    'B': JALIViseme(0.0, 0.0, 1.0),
    'P': JALIViseme(0.0, 0.0, 1.0),

    # Labiodentals - MUST achieve lip-teeth (paper §4.2, Constraint 2)
    'F': JALIViseme(0.1, 0.1, 0.95),  # FFF viseme
    'V': JALIViseme(0.1, 0.1, 0.95),

    # Sibilants - narrow jaw (paper §4.2, Constraint 3)
    'S': JALIViseme(0.05, 0.4, 0.85),  # SSS viseme
    'Z': JALIViseme(0.05, 0.4, 0.85),
    'SH': JALIViseme(0.15, -0.3, 0.85),  # SSH viseme
    'ZH': JALIViseme(0.15, -0.3, 0.85),
    'CH': JALIViseme(0.15, -0.2, 0.85),
    'JH': JALIViseme(0.15, -0.2, 0.85),

    # Dentals
    'TH': JALIViseme(0.15, 0.0, 0.75),  # TTH viseme
    'DH': JALIViseme(0.15, 0.0, 0.75),

    # Tongue-only (paper §4.2, Rule 5: no lip influence)
    'T': JALIViseme(0.1, 0.0, 0.7),  # LNTD viseme
    'D': JALIViseme(0.1, 0.0, 0.7),
    'N': JALIViseme(0.1, 0.0, 0.7),
    'L': JALIViseme(0.3, 0.0, 0.6),
    'K': JALIViseme(0.4, 0.0, 0.6),  # GK viseme
    'G': JALIViseme(0.4, 0.0, 0.6),
    'NG': JALIViseme(0.4, 0.0, 0.6),

    # Glides and Liquids
    'W': JALIViseme(0.1, -0.9, 0.95),  # UUU viseme (lip-heavy)
    'R': JALIViseme(0.2, -0.5, 0.7),  # RRR viseme
    'Y': JALIViseme(0.1, 0.5, 0.6),
    'HH': JALIViseme(0.4, 0.0, 0.2),

    # VOWELS - Low Dominance  

    # Low vowels (max jaw) - AAA/AHH visemes
    'AA': JALIViseme(1.0, 0.0, 0.15),  # "father"
    'AE': JALIViseme(0.9, 0.4, 0.15),  # "cat" - AAA viseme
    'AH': JALIViseme(0.6, 0.0, 0.1),  # "but"
    'AO': JALIViseme(0.8, -0.5, 0.2),  # "caught"

    # Mid vowels - EHH viseme
    'EH': JALIViseme(0.5, 0.5, 0.1),  # "bed"
    'ER': JALIViseme(0.4, -0.3, 0.2),  # "bird"
    'IH': JALIViseme(0.3, 0.6, 0.1),  # "bit"
    'UH': JALIViseme(0.3, -0.4, 0.2),  # "book"

    # High vowels - IEE/UUU visemes
    'IY': JALIViseme(0.15, 0.9, 0.2),  # "beet" (max wide)
    'UW': JALIViseme(0.2, -0.95, 0.4),  # "boot" (max pucker, lip-heavy)

    # Diphthongs - OHH viseme for rounded
    'AW': JALIViseme(0.85, -0.6, 0.3),  # "cow"
    'AY': JALIViseme(0.9, 0.5, 0.25),  # "eye"
    'EY': JALIViseme(0.5, 0.6, 0.2),  # "bait"
    'OW': JALIViseme(0.6, -0.8, 0.4),  # "boat" (lip-heavy)
    'OY': JALIViseme(0.7, -0.6, 0.35),  # "boy" (lip-heavy)

    # Schwa
    'AX': JALIViseme(0.4, 0.0, 0.05),  # Schwa viseme
    'IX': JALIViseme(0.3, 0.3, 0.05),
    }

# Classification sets (from paper Figure 10)
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

# Phoneme  -> Viseme mapping (paper Figure 4)
# Many phonemes map to one viseme — duplicates are merged on VISEME
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
    """Map phoneme to viseme group (paper Figure 4)."""
    return PHONEME_TO_VISEME.get(phoneme.rstrip('012'), phoneme)

# DOMINANCE BLENDER (Paper §4.2)

class DominanceBlender:
    """Dominance-weighted temporal blending using the paper's speech
    motion curves (§4.2).

    Paper: "onset begins 120ms before apex, apex sustained in arc to
    75% of phoneme duration, then 120ms decay.  Lip-heavy: 150ms
    onset and offset."

    Each phoneme's curve extends beyond its own boundaries so that
    adjacent curves overlap — this is what prevents jitter.
    """

    def __init__(self, fps: float = 30.0, tau: float = 0.070):
        self.fps = fps

    def compute_dominance_curve(
            self,
            event: PhonemeEvent,
            times: np.ndarray,
            ) -> np.ndarray:
        """Paper §4.2 speech motion curve.

        Shape:  onset (sin²)  -> sustain (1.0)  -> decay (cos²)

        Apex and sustain end are anchored to the original phoneme bounds
        (event.apex == original_start, event.sustain_end == 75% of
        original_duration).  Onset and decay can extend beyond the
        natural bounds when Rule 2 (lip-heavy) extends event.start/end.

        For non-extended phonemes, this reduces to the standard 120ms
        pre-onset and 120ms post-sustain decay.
        """
        is_lip_heavy = getattr(event, 'is_lip_heavy', False)
        natural_onset = 0.150 if is_lip_heavy else 0.120
        natural_decay = 0.150 if is_lip_heavy else 0.120

        t_apex = event.apex                    # original_start (natural)
        t_sustain_end = event.sustain_end       # 75% of natural duration

        # Onset begins at natural pre-onset or at the extended start,
        # whichever is earlier.  This lets lip-heavy phonemes have a
        # longer anticipation window without losing the natural sustain.
        natural_onset_start = t_apex - natural_onset
        t_onset_start = min(natural_onset_start, event.start)

        # Decay ends at natural post-decay OR at the extended end,
        # whichever is later.  Same idea for hysteresis.
        natural_decay_end = t_sustain_end + natural_decay
        t_decay_end = max(natural_decay_end, event.end)

        # Clamp to pause boundaries.  Phoneme onsets and decays model
        # anticipatory and lingering articulation
        prev_pause_end = getattr(event, 'prev_pause_end', float('-inf'))
        next_pause_start = getattr(event, 'next_pause_start', float('inf'))
        if t_onset_start < prev_pause_end:
            t_onset_start = prev_pause_end
        if t_decay_end > next_pause_start:
            t_decay_end = next_pause_start

        onset_dur = max(t_apex - t_onset_start, 0.001)
        decay_dur = max(t_decay_end - t_sustain_end, 0.001)

        envelope = np.zeros_like(times)

        # Onset: sin² ramp from 0  -> 1
        onset_mask = (times >= t_onset_start) & (times < t_apex)
        if onset_mask.any():
            progress = (times[onset_mask] - t_onset_start) / onset_dur
            envelope[onset_mask] = np.sin(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2

        # Sustain: hold at 1.0 across the natural plateau
        sustain_mask = (times >= t_apex) & (times <= t_sustain_end)
        envelope[sustain_mask] = 1.0

        # Decay: cos² ramp from 1  -> 0
        decay_mask = (times > t_sustain_end) & (times <= t_decay_end)
        if decay_mask.any():
            progress = (times[decay_mask] - t_sustain_end) / decay_dur
            envelope[decay_mask] = np.cos(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2

        # Scale by dominance
        return envelope * event.dominance

    def blend_jali_parameters(
            self,
            events: List[PhonemeEvent],
            duration: float
            ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Blend JALI parameters using dominance weighting.

        JA(t) = Σ(JA_i × D_i(t)) / Σ(D_i(t))
        LI(t) = Σ(LI_i × D_i(t)) / Σ(D_i(t))
        """
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

        # Paper: ventriloquist singularity — neutral at rest
        no_influence = dominance_sum < 1e-6
        jaw_curve[no_influence] = 0.0
        lip_curve[no_influence] = 0.0

        return times, jaw_curve.astype(np.float32), lip_curve.astype(np.float32)


class CoarticulationEngine:
    """Applies nine co-articulation rules from paper

    Paper §4.2: "rules based on linguistic categorization divided into
    constraints, conventions and habits"
    """

    def apply_rules(self, events: List[PhonemeEvent]) -> List[PhonemeEvent]:
        """Apply all co-articulation rules

        Args:
            events: PhonemeEvents (modified in-place)

        Returns:
            Modified events list
        """
        if not events:
            return events

        # Snapshot original acoustic timing.  Coarticulation may extend
        # start/end (lip-heavy Rule 2, duplicate merge Rule 1), but apex
        # and sustain duration must stay anchored to the natural span.
        for event in events:
            if event.original_start < 0:
                event.original_start = event.start
            if event.original_end < 0:
                event.original_end = event.end

        # Set classification flags
        for event in events:
            self._classify_phoneme(event)

        # Set context info
        self._set_context(events)

        # Infer de-stressed words from per-word stress profile
        self._infer_word_prominence(events)

        # Apply rules in order
        self._substitute_pauses(events)    # Figure 10: pause substitution
        self._merge_duplicates(events)     # Rule 1
        self._extend_lip_heavy(events)     # Rule 2
        self._override_lip_shapes(events)  # Rules 3, 4
        self._apply_tongue_only(events)    # Rule 5
        self._apply_obstruent_rules(events)  # Rules 6, 7
        self._apply_anticipation(events)   # Rule 8
        self._enforce_constraints(events)  # Constraints 1-4
        self._apply_stress_amplitude(events)  # Conventions

        return events

    @staticmethod
    def _classify_phoneme(event: PhonemeEvent):
        """Set classification flags. Phoneme is already stripped of
        stress markers by create_phoneme_event."""
        p = event.phoneme

        event.is_vowel = p in VOWELS
        event.is_bilabial = p in BILABIALS
        event.is_labiodental = p in LABIODENTALS
        event.is_sibilant = p in SIBILANTS
        event.is_tongue_only = p in TONGUE_ONLY
        event.is_lip_heavy = p in LIP_HEAVY
        event.is_obstruent_nasal = p in OBSTRUENTS_NASALS

    @staticmethod
    def _set_context(events: List[PhonemeEvent]):
        """Set prev_is_pause / prev_is_vowel and pause boundary times.

        prev_pause_end / next_pause_start record the times of the
        nearest pause on each side, so that compute_dominance_curve
        can clamp onset/decay to those boundaries.  Phonemes that
        have no pause on a given side keep -inf / +inf, which means
        no clamp applies.
        """
        n = len(events)

        # First pass: prev/is-vowel flags and prev_pause_end (forward scan)
        last_pause_end = float('-inf')
        for i, event in enumerate(events):
            if i == 0:
                event.prev_is_pause = True
                event.prev_is_vowel = False
            else:
                prev = events[i - 1]
                event.prev_is_pause = prev.phoneme in PAUSES
                event.prev_is_vowel = prev.is_vowel

            event.prev_pause_end = last_pause_end
            if event.phoneme in PAUSES:
                last_pause_end = event.end

        # Second pass: next_pause_start (backward scan)
        next_pause_start = float('inf')
        for i in range(n - 1, -1, -1):
            event = events[i]
            event.next_pause_start = next_pause_start
            if event.phoneme in PAUSES:
                next_pause_start = event.start

    @staticmethod
    @staticmethod
    def _substitute_pauses(events: List[PhonemeEvent]):
        """Figure 10: Pause substitution.

        Paper Convention 3: "Pauses leave the mouth open"

        INTERIOR pauses (have non-pause neighbours on BOTH sides):
        Speech is about to resume, so the jaw is held slightly open
        (inherited from a neighbour) to avoid snapping shut between
        words.  Lip is forced to neutral so a vowel's wide/round
        shape doesn't carry through the silence.

        EXTERIOR pauses (leading or trailing silence with no
        non-pause neighbour on one side):
        The speaker is at rest — before utterance start or after
        utterance end.  Jaw and lip both relax to closed/neutral.
        Otherwise the trailing silence holds the mouth open
        indefinitely after the sentence ends.
        """
        n = len(events)
        for i, event in enumerate(events):
            if event.phoneme not in PAUSES:
                continue

            has_prev_speech = any(
                events[j].phoneme not in PAUSES for j in range(i))
            has_next_speech = any(
                events[j].phoneme not in PAUSES for j in range(i + 1, n))
            is_interior = has_prev_speech and has_next_speech

            if is_interior:
                # Inherit jaw from previous non-pause neighbour
                if i > 0 and events[i - 1].phoneme not in PAUSES:
                    event.jaw = events[i - 1].jaw
                elif i < n - 1 and events[i + 1].phoneme not in PAUSES:
                    event.jaw = events[i + 1].jaw

                event.lip = 0.0
                event.jaw = max(event.jaw * 0.7, 0.15)
                event.dominance = 0.05
            else:
                # Leading or trailing silence — speaker at rest
                event.jaw = 0.0
                event.lip = 0.0
                event.dominance = 0.05

    @staticmethod
    def _merge_duplicates(events: List[PhonemeEvent]):
        """Rule 1: Merge consecutive duplicate VISEMES (not phonemes).

        Paper Figure 10: if viseme(Pi) == viseme(Pi-1), merge.
        Ex: /p/ followed by /m/ are both viseme MMM  -> merge.
        Both `end` and `original_end` are extended so the merged
        viseme's natural sustain region covers the full combined span.
        """
        i = 0
        while i < len(events) - 1:
            if _get_viseme(events[i].phoneme) == _get_viseme(events[i + 1].phoneme):
                events[i].end = events[i + 1].end
                events[i].original_end = events[i + 1].original_end
                events.pop(i + 1)
            else:
                i += 1

    @staticmethod
    def _extend_lip_heavy(events: List[PhonemeEvent]):
        """Rule 2: Lip-heavy start early and end late.

        Paper walkthrough for "w UX t": w extends through next end,
        but UX and t still exist as separate articulatory events.
        The lip-heavy viseme's temporal influence expands, but
        neighboring phonemes keep their jaw and tongue contributions.

        Pauses act as hard boundaries — lip-heavy influence does not
        extend across silences, since the speaker has had time to
        relax during a pause.
        """
        for i, event in enumerate(events):
            if not event.is_lip_heavy:
                continue

            # Extend start to previous phoneme's start
            if i > 0:
                prev = events[i - 1]
                if (prev.phoneme not in PAUSES
                        and not (prev.is_bilabial or prev.is_labiodental)):
                    event.start = prev.start

            # Extend end to next phoneme's end
            if i < len(events) - 1:
                nxt = events[i + 1]
                if (nxt.phoneme not in PAUSES
                        and not (nxt.is_bilabial or nxt.is_labiodental)):
                    event.end = nxt.end

    @staticmethod
    def _override_lip_shapes(events: List[PhonemeEvent]):
        """Rules 3, 4: Lip-heavy override/combine with neighbors.

        Rule 3: Replace lip shape of non-bilabial/labiodental neighbors
        Rule 4: Simultaneously articulate with bilabial/labiodental neighbors

        Pauses are excluded — _substitute_pauses sets pause lip values
        explicitly (interior pauses get neutral, exterior pauses get
        rest position).  Overwriting them here would undo that.
        """
        for i, event in enumerate(events):
            if not event.is_lip_heavy:
                continue

            # Previous neighbor
            if i > 0:
                prev = events[i - 1]
                if (prev.phoneme not in PAUSES
                        and not (prev.is_bilabial or prev.is_labiodental)):
                    # Rule 3: replace lip shape entirely
                    prev.lip = event.lip
                # Rule 4: bilabials/labiodentals keep their own lip shape
                # (simultaneous articulation — no change needed)

            # Next neighbor
            if i < len(events) - 1:
                nxt = events[i + 1]
                if (nxt.phoneme not in PAUSES
                        and not (nxt.is_bilabial or nxt.is_labiodental)):
                    nxt.lip = event.lip

    @staticmethod
    def _apply_tongue_only(events: List[PhonemeEvent]):
        """Rule 5: Tongue-only have no lip influence.

        Paper: "the lips always take the shape of the visemes that
        surround them"

        Uses word_index to prevent cross-word lip bleeding.
        Within a word, looks forward first (anticipation), last
        phoneme in word looks back
        """
        n = len(events)
        for i, event in enumerate(events):
            if not event.is_tongue_only:
                continue

            wi = event.word_index
            lip_source = None

            # Is this the last phoneme in its word?
            is_last = (i == n - 1
                       or events[i + 1].word_index != wi
                       or events[i + 1].phoneme in PAUSES)

            if not is_last:
                # Look forward within same word
                for j in range(i + 1, n):
                    ej = events[j]
                    if ej.word_index != wi or ej.phoneme in PAUSES:
                        break
                    if not ej.is_tongue_only:
                        lip_source = ej.lip
                        break

            if lip_source is None:
                # Look backward within same word (or always for last-in-word)
                for j in range(i - 1, -1, -1):
                    ej = events[j]
                    if ej.word_index != wi or ej.phoneme in PAUSES:
                        break
                    if not ej.is_tongue_only:
                        lip_source = ej.lip
                        break

            if lip_source is not None:
                event.lip = lip_source

    @staticmethod
    def _apply_obstruent_rules(events: List[PhonemeEvent]):
        """Rules 6, 7: Obstruent/Nasal jaw behavior.

        Rule 6: < 1 frame, no similar neighbors  -> no jaw effect
        Rule 7: >= 1 frame  -> narrow jaw per viseme definition
        """
        n = len(events)
        for i, event in enumerate(events):
            if not event.is_obstruent_nasal or event.is_sibilant:
                continue

            has_similar = False
            if i > 0 and events[i - 1].is_obstruent_nasal:
                has_similar = True
            if i < n - 1 and events[i + 1].is_obstruent_nasal:
                has_similar = True

            if event.duration < 0.033 and not has_similar:
                # Rule 6: short, isolated  -> jaw from neighbors
                event.jaw = 0.0
            elif event.duration >= 0.033:
                # Rule 7: long enough  -> narrow jaw per viseme
                event.jaw = min(event.jaw, 0.3)

    @staticmethod
    def _apply_anticipation(events: List[PhonemeEvent]):
        """Rule 8: Articulatory anticipation within words.

        Paper: "targets look into the word for their shape, always
        anticipating, except that the last phoneme in a word looks back"

        Uses word_index to detect word boundaries
        """
        n = len(events)
        if n < 2:
            return

        for i in range(n):
            event = events[i]
            if event.is_tongue_only or event.phoneme in PAUSES:
                continue  # tongue-only already handled by Rule 5

            wi = event.word_index

            # Determine if this is the last phoneme in its word
            is_last_in_word = (i == n - 1
                               or events[i + 1].word_index != wi
                               or events[i + 1].phoneme in PAUSES)

            if is_last_in_word:
                # Last phoneme looks BACK for lip shape
                for j in range(i - 1, -1, -1):
                    if events[j].word_index != wi or events[j].phoneme in PAUSES:
                        break
                    if not events[j].is_tongue_only:
                        if events[j].is_lip_heavy:
                            event.lip = events[j].lip
                        break
            else:
                # All others look FORWARD (anticipation)
                for j in range(i + 1, n):
                    if events[j].word_index != wi or events[j].phoneme in PAUSES:
                        break
                    if not events[j].is_tongue_only and events[j].is_lip_heavy:
                        event.lip = events[j].lip * 0.6
                        break

    @staticmethod
    def _enforce_constraints(events: List[PhonemeEvent]):
        """Hard constraints from paper §4.2

        1. Bilabials MUST close lips
        2. Labiodentals MUST achieve lip-teeth contact
        3. Sibilants narrow jaw
        4. Non-nasal phonemes must open lips at some point
        """
        NASALS = frozenset({'M', 'N', 'NG'})

        for event in events:
            p = event.phoneme.rstrip('012')

            if event.is_bilabial:
                event.jaw = 0.0
                event.lip = 0.0
                event.dominance = max(event.dominance, 1.0)

            elif event.is_labiodental:
                event.jaw = min(event.jaw, 0.1)
                event.dominance = max(event.dominance, 0.95)

            elif event.is_sibilant:
                event.jaw = min(event.jaw, 0.15)

            # Constraint 4: non-nasal phonemes must open lips at some point.
            # Paper §3.2: the ventriloquist singularity at (JA=0, LI=0)
            # gives "slightly parted lips" for all non-bilabial phonemes.
            # If a non-nasal, non-bilabial lands at (0,0), its dominance
            # must be low so it doesn't override the neutral parted state.
            if p not in NASALS and p not in PAUSES:
                if not event.is_bilabial and event.jaw < 0.01 and abs(event.lip) < 0.01:
                    event.dominance = min(event.dominance, 0.1)

    @staticmethod
    def _infer_word_prominence(events: List[PhonemeEvent]):
        """Mark de-stressed words.

        Paper §4.2 Convention 2: "de-stressed words usually get
        weakly-articulated visemes for the length of the word."

        Heuristic: a word is de-stressed if none of its vowels carry
        primary stress (g2p_en marker '1').  Common function words
        like 'and', 'of', 'the', 'a' typically come from g2p_en with
        all unstressed vowels and benefit from this weakening.
        Content words almost always have at least one primary-stressed
        syllable, so they remain prominent.
        """
        if not events:
            return

        from collections import defaultdict
        word_groups: Dict[int, List[PhonemeEvent]] = defaultdict(list)
        for ev in events:
            if ev.word_index >= 0:
                word_groups[ev.word_index].append(ev)

        for group in word_groups.values():
            max_stress = 0
            for ev in group:
                if ev.is_vowel and ev.stress_level > max_stress:
                    max_stress = ev.stress_level

            # No primary stress in this word  -> de-stressed
            if max_stress < 2:
                for ev in group:
                    ev.word_prominent = False

    @staticmethod
    def _apply_stress_amplitude(events: List[PhonemeEvent]):
        """Paper §4.2 Conventions: graduated articulation from stress.

        Three-level Arpabet stress markers from g2p_en:
          2 (primary)    -> strong articulation (paper "high 9/10")
          1 (secondary)  -> normal articulation (paper "normal 6/10")
          0 (unstressed) -> weak articulation, schwa-like

        For events from the acoustic-only path (no g2p context, marked
        by word_index < 0), stress is UNKNOWN — we treat these as
        secondary so they get normal articulation rather than being
        weakened to schwa level.

        De-stressed function words get a further reduction (Convention 2:
        "weakly-articulated visemes for the length of the word") so they
        smear into surrounding content.

        """
        for event in events:
            if not event.is_vowel:
                continue

            # Acoustic-only events have no stress info  -> treat as normal
            stress_known = event.word_index >= 0
            effective_stress = event.stress_level if stress_known else 1

            if effective_stress == 2:
                event.jaw = min(event.jaw * 1.1, 1.0)
            elif effective_stress == 1:
                pass  # baseline values from JALI map
            else:
                event.jaw *= 0.6
                event.lip *= 0.7

            # Convention 2: de-stressed function word — further weakening
            if not event.word_prominent:
                event.jaw *= 0.7


class AcousticAnalyzer:
    """Paper §4.3: Audio-driven JALI modulation.

    Separates vowels, fricatives, and plosives.  Computes per-class
    statistics (mean, σ) from aligned segments, then uses the paper's
    bucketed rig settings (Tables 1-3)

    Only lexically stressed vowels are modulated, and fricatives/plosives
    only if adjacent to a stressed vowel — this keeps animation from
    being too erratic.
    """

    def __init__(self, audio_path: str):
        if not PARSELMOUTH_AVAILABLE:
            raise ImportError("Install parselmouth: pip install praat-parselmouth")

        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()
        self.pitch = self.sound.to_pitch()
        self.intensity = self.sound.to_intensity()

        # HF intensity (8-20kHz) for fricatives/plosives
        try:
            self.hf_sound = call(self.sound, "Filter (pass Hann band)", 8000, 20000, 100)
            self.hf_intensity = self.hf_sound.to_intensity()
        except Exception:
            self.hf_intensity = None

    @staticmethod
    def _bucket(z: float, low: Tuple[float, float], mid: Tuple[float, float],
                high: Tuple[float, float]) -> float:
        """Paper Tables 1-3: bucketed rig setting from z-score.

        Uses deterministic midpoints of each range
        The paper gives ranges; we pick the center for consistency.
        """
        if z <= -1.0:
            return (low[0] + low[1]) * 0.5
        elif z >= 1.0:
            return (high[0] + high[1]) * 0.5
        else:
            # Interpolate within mid range based on z position
            t = (z + 1.0) * 0.5  # map [-1,1]  -> [0,1]
            return mid[0] + t * (mid[1] - mid[0])

    def modulate_events(self, events: List[PhonemeEvent]) -> List[PhonemeEvent]:
        """Paper §4.3: Per-class acoustic modulation with stress gating."""
        PLOSIVES = frozenset({'P', 'B', 'D', 'T', 'G', 'K'})
        FRICATIVES = frozenset({'S', 'Z', 'SH', 'ZH', 'F', 'V', 'TH', 'DH'})

        # Compute per-class statistics from aligned events
        vowel_intensities, vowel_pitches = [], []
        fric_plos_hf = []

        for ev in events:
            p = ev.phoneme.rstrip('012')
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

        # Class means and stds
        v_int_mean = np.mean(vowel_intensities) if vowel_intensities else 60.0
        v_int_std = max(np.std(vowel_intensities), 1.0) if vowel_intensities else 10.0
        v_p_mean = np.mean(vowel_pitches) if vowel_pitches else 150.0
        v_p_std = max(np.std(vowel_pitches), 10.0) if vowel_pitches else 50.0
        hf_mean = np.mean(fric_plos_hf) if fric_plos_hf else 30.0
        hf_std = max(np.std(fric_plos_hf), 1.0) if fric_plos_hf else 10.0

        # identify which events to modulate
        stressed_vowel_indices = {i for i, ev in enumerate(events)
                                  if ev.is_vowel and ev.lexically_stressed}
        adjacent_to_stressed = set()
        for idx in stressed_vowel_indices:
            if idx > 0:
                adjacent_to_stressed.add(idx - 1)
            if idx < len(events) - 1:
                adjacent_to_stressed.add(idx + 1)

        # Paper Tables 1-2 give JA/LI "rig settings" (intensity of action).
        # These scale HOW MUCH jaw/lip action
        # Direction comes from the phoneme viseme (preserved from coarticulation).
        MID_INTENSITY = 0.45  # center of mid bucket (0.3, 0.6)

        for i, event in enumerate(events):
            t_mid = (event.start + event.end) * 0.5
            p = event.phoneme.rstrip('012')

            if event.is_vowel and event.lexically_stressed:
                vol = self.intensity.get_value(t_mid)
                f0 = self.pitch.get_value_at_time(t_mid)

                z_int = 0.0
                if not math.isnan(vol):
                    z_int = (vol - v_int_mean) / (v_int_std + 1e-6)
                    # Table 1: JA intensity from loudness — scale jaw target
                    ja_intensity = self._bucket(z_int, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9))
                    event.jaw *= ja_intensity / MID_INTENSITY
                    event.jaw = min(event.jaw, 1.0)

                if not math.isnan(f0) and f0 > 0:
                    z_pitch = (f0 - v_p_mean) / (v_p_std + 1e-6)
                    # Table 2: LI intensity from pitch+intensity
                    # Scale lip MAGNITUDE, preserve DIRECTION (pucker vs wide)
                    z_combined = max(z_int, z_pitch)
                    li_intensity = self._bucket(z_combined, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9))
                    scale = li_intensity / MID_INTENSITY
                    event.lip *= scale
                    event.lip = max(-1.0, min(1.0, event.lip))

            elif (p in FRICATIVES or p in PLOSIVES) and i in adjacent_to_stressed:
                if self.hf_intensity is not None:
                    hf = self.hf_intensity.get_value(t_mid)
                    if not math.isnan(hf):
                        z_hf = (hf - hf_mean) / (hf_std + 1e-6)
                        # Table 3: LI intensity from HF — scale lip magnitude
                        hf_intensity = self._bucket(z_hf, (0.1, 0.2), (0.3, 0.6), (0.7, 0.9))
                        scale = hf_intensity / MID_INTENSITY
                        event.lip *= scale
                        event.lip = max(-1.0, min(1.0, event.lip))

        return events

    # Keep simple accessors for acoustic-only fallback path
    def get_amplitude_factor(self, time: float) -> float:
        """Simple amplitude factor for acoustic-only mode."""
        try:
            intensity = self.intensity.get_value(time)
            if math.isnan(intensity):
                return 0.5
            return float(np.clip((intensity - 50.0) / 40.0, 0.0, 1.5))
        except Exception:
            return 0.5

    def get_pitch_factor(self, time: float) -> float:
        """Simple pitch deviation for acoustic-only mode."""
        try:
            p = self.pitch.get_value_at_time(time)
            if math.isnan(p) or p <= 0:
                return 0.0
            return float(np.clip((p - 150) / 200, -0.5, 0.5))
        except Exception:
            return 0.0


class MotionCurveGenerator:
    """Generate smooth motion curves with onset/arc/sustain/decay.

    Paper §4.2: "onset begins 120ms before apex, apex is sustained
    in an arc to 75% of phoneme, then 120ms decay"

    Apex = phoneme start (beginning of sound).
    Onset extends BEFORE apex. Decay extends AFTER sustain end.
    """

    def __init__(self, fps: float = 30.0):
        self.fps = fps

    def generate_curve(self, event: PhonemeEvent, times: np.ndarray) -> np.ndarray:
        """Generate temporal weight curve.

        Shape: sin²(onset)  -> sustain(1.0)  -> sin²(decay)
        """
        onset_dur = event.onset_duration
        decay_dur = event.decay_duration

        t_onset_start = event.start - onset_dur   # onset begins before
        t_apex = event.start                       # apex = sound start
        t_sustain_end = event.sustain_end           # 75% through
        t_decay_end = t_sustain_end + decay_dur

        curve = np.zeros_like(times, dtype=np.float32)

        # Onset: sin² ramp up (before phoneme start)
        onset_mask = (times >= t_onset_start) & (times < t_apex)
        if onset_mask.any() and onset_dur > 0:
            progress = (times[onset_mask] - t_onset_start) / onset_dur
            curve[onset_mask] = np.sin(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2

        # Sustain: hold at 1.0
        sustain_mask = (times >= t_apex) & (times <= t_sustain_end)
        curve[sustain_mask] = 1.0

        # Decay: sin² ramp down (after sustain)
        decay_mask = (times > t_sustain_end) & (times <= t_decay_end)
        if decay_mask.any() and decay_dur > 0:
            progress = (times[decay_mask] - t_sustain_end) / decay_dur
            curve[decay_mask] = np.cos(0.5 * np.pi * np.clip(progress, 0, 1)) ** 2

        return curve


def create_phoneme_event(
        phoneme: str,
        start: float,
        end: float,
        lexically_stressed: bool = False
        ) -> PhonemeEvent:
    """Create PhonemeEvent from phoneme string and timing.

    Extracts the Arpabet stress marker (0/1/2) from the phoneme string
    and stores it as stress_level (0=unstressed, 1=secondary, 2=primary).

    Args:
        phoneme: Arpabet phoneme code, optionally with stress marker
        start: Start time (seconds)
        end: End time (seconds)
        lexically_stressed: Override flag (used by acoustic-only path)

    Returns:
        PhonemeEvent with JALI parameters and stress level
    """
    # Extract stress level from Arpabet marker
    stress_level = 0
    if phoneme:
        last = phoneme[-1]
        if last == '1':
            stress_level = 2  # primary
        elif last == '2':
            stress_level = 1  # secondary

    clean = phoneme.rstrip('012')
    jali = ARPABET_JALI_MAP.get(clean, JALIViseme(0.3, 0.0, 0.5))

    stressed = lexically_stressed or (stress_level > 0)

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


class AcousticPhonemeDetector:
    """Acoustic phoneme detection using Praat formant analysis.

    Classifies speech regions by acoustic features:
    - Vowels (>80ms): F1/F2 formant space  -> AA, AE, UH, EH, UW, IY, AH
    - Consonants (<80ms): Spectral characteristics  -> T, D, S, N, L, K
    - Silence: SIL
    """

    def __init__(self, audio_path: str):
        if not PARSELMOUTH_AVAILABLE:
            raise ImportError("Install parselmouth: pip install praat-parselmouth")

        self.audio_path = audio_path
        self.sound = parselmouth.Sound(audio_path)
        self.duration = self.sound.get_total_duration()

    def detect_phonemes(self) -> List[PhonemeEvent]:
        """Detect phonemes from audio using acoustic features."""
        intensity = self.sound.to_intensity()
        textgrid = call(
            intensity, "To TextGrid (silences)",
            -25, 0.1, 0.05, "silent", "sounding"
            )

        events: List[PhonemeEvent] = []
        num_intervals = call(textgrid, "Get number of intervals", 1)

        for i in range(1, num_intervals + 1):
            label = call(textgrid, "Get label of interval", 1, i)
            start = call(textgrid, "Get start time of interval", 1, i)
            end = call(textgrid, "Get end time of interval", 1, i)

            if label == "silent":
                # Preserve silence as pause event
                if (end - start) > 0.05:
                    events.append(create_phoneme_event('SIL', start, end))
                continue

            if (end - start) > 0.08:
                phoneme = self._classify_vowel(start, end)
            else:
                phoneme = self._classify_consonant(start, end)

            events.append(create_phoneme_event(phoneme, start, end))

        return events

    def _classify_vowel(self, start: float, end: float) -> str:
        """Classify vowel from F1/F2 formant space."""
        t = (start + end) * 0.5
        try:
            formant = self.sound.to_formant_burg()
            f1 = call(formant, "Get value at time", 1, t, 'Hertz', 'Linear')
            f2 = call(formant, "Get value at time", 2, t, 'Hertz', 'Linear')

            if f1 > 700:  # Low vowels
                return 'AA' if f2 < 1200 else 'AE'
            elif f1 > 500:  # Mid vowels
                return 'UH' if f2 < 1400 else 'EH'
            else:  # High vowels
                return 'UW' if f2 < 1800 else 'IY'
        except Exception:
            pass
        return 'AH'

    def _classify_consonant(self, start: float, end: float) -> str:
        """Classify consonant from spectral characteristics.

        - Sibilants (S, SH): High-frequency energy relative to overall intensity
        - Bilabials/Stops (M, P): Deep intensity valley (near-silence)
        - Default (T): Moderate burst — tongue-only, neutral lip shape
        """
        import math
        t_mid = (start + end) * 0.5

        try:
            # High-frequency energy for frication detection
            hf_sound = call(self.sound, "Filter (pass Hann band)", 4000, 20000, 100)
            hf_intensity = hf_sound.to_intensity(minimum_pitch=50, time_step=0.001)
            hf_val = call(hf_intensity, "Get value at time", t_mid, "Cubic")

            overall = self.sound.to_intensity()
            overall_val = call(overall, "Get value at time", t_mid, "Cubic")

            if math.isnan(hf_val):
                hf_val = 0.0
            if math.isnan(overall_val):
                overall_val = 0.0

            # Sibilant: high friction relative to overall volume
            if hf_val > (overall_val - 15):
                return 'S'

            # Bilabial/stop: deep acoustic valley
            if overall_val < 40:
                return 'M'

        except Exception:
            pass

        # Default: neutral tongue-only consonant
        return 'T'


class TranscriptAligner:
    """Align transcript text to audio using Praat speech detection and g2p_en.

    Uses g2p_en for accurate dictionary-backed phoneme conversion,
    proportional timing with vowels weighted 3× heavier than consonants,
    then snaps vowels to acoustic intensity peaks.
    """

    def __init__(self, audio_path: str, transcript: str):
        if not PARSELMOUTH_AVAILABLE:
            raise ImportError("parselmouth is required")
        if not G2P_AVAILABLE:
            raise ImportError("g2p_en is required for accurate transcript alignment")

        self.audio_path = audio_path
        self.transcript = transcript
        self.g2p = g2p_en.G2p()
        self.vowels = {
            'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY',
            'IH', 'IY', 'OW', 'OY', 'UH', 'UW', 'AX', 'IX',
        }

    def align_phonemes(self) -> List[PhonemeEvent]:
        sound = parselmouth.Sound(self.audio_path)
        self.duration = sound.get_total_duration()

        # Praat speech-interval detection
        intensity = sound.to_intensity()
        textgrid = call(
            intensity, "To TextGrid (silences)",
            -25, 0.1, 0.05, "silent", "sounding",
        )

        intervals: List[Tuple[float, float]] = []       # sounding
        silent_intervals: List[Tuple[float, float]] = [] # silent
        num_intervals = call(textgrid, "Get number of intervals", 1)
        for i in range(1, num_intervals + 1):
            label = call(textgrid, "Get label of interval", 1, i)
            start = call(textgrid, "Get start time of interval", 1, i)
            end = call(textgrid, "Get end time of interval", 1, i)
            if label == "sounding":
                intervals.append((start, end))
            elif (end - start) > 0.05:
                silent_intervals.append((start, end))

        if not intervals:
            intervals = [(0.0, self.duration)]

        # G2P conversion — returns (phoneme, word_index) tuples
        phoneme_words = self._g2p_convert(self.transcript)
        if not phoneme_words:
            return []

        # Proportionally weight vowels higher for realistic pacing
        # g2p_en outputs stress markers (e.g. 'UW1'), strip for weight check
        weights = [3.0 if p.rstrip('012') in self.vowels else 1.0
                   for p, _wi in phoneme_words]
        total_weight = sum(weights)
        total_speech_time = sum(end - start for start, end in intervals)

        events: List[PhonemeEvent] = []
        cumulative_weight = 0.0

        for (p, wi), w in zip(phoneme_words, weights):
            start_speech = (cumulative_weight / total_weight) * total_speech_time
            end_speech = ((cumulative_weight + w) / total_weight) * total_speech_time

            abs_start = self._map_time(start_speech, intervals)
            abs_end = self._map_time(end_speech, intervals)

            if abs_end > abs_start:
                stressed = p[-1] in '12' if p else False
                ev = create_phoneme_event(p, abs_start, abs_end, stressed)
                ev.word_index = wi
                events.append(ev)

            cumulative_weight += w

        # For each phrase, find N intensity peaks (N = vowels in phrase),
        # snap each vowel to its peak, then redistribute consonants in the gaps.
        self._anchor_per_phrase(events, intensity, intervals)

        # Inject SIL events for silent intervals between speech
        for s_start, s_end in silent_intervals:
            sil = create_phoneme_event('SIL', s_start, s_end)
            sil.word_index = -1
            events.append(sil)

        # Sort by start time so SIL events interleave correctly
        events.sort(key=lambda e: e.start)

        return events

    @staticmethod
    def _map_time(
        speech_time: float,
        intervals: List[Tuple[float, float]],
    ) -> float:
        """Convert continuous speech-time to absolute audio time, skipping silences."""
        accumulated = 0.0
        for start, end in intervals:
            interval_dur = end - start
            if accumulated + interval_dur >= speech_time - 1e-5:
                return start + (speech_time - accumulated)
            accumulated += interval_dur
        return intervals[-1][1]

    def _is_vowel(self, phoneme: str) -> bool:
        return phoneme.rstrip('012') in self.vowels

    def _find_n_peaks(self, intensity, t_start: float, t_end: float, n: int) -> List[float]:
        """Find n intensity peaks in [t_start, t_end], sorted by time.

        Uses parselmouth's intensity contour as a numpy array, finds local
        maxima, picks the strongest n by value, and returns their times in
        chronological order.  Falls back to evenly-spaced positions if
        peak detection fails or returns fewer peaks than requested.
        """
        if n <= 0:
            return []

        try:
            times = np.asarray(intensity.xs(), dtype=np.float64)
            values = np.asarray(intensity.values, dtype=np.float64).ravel()
        except Exception:
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]

        mask = (times >= t_start) & (times <= t_end)
        sub_t = times[mask]
        sub_v = values[mask]

        if len(sub_v) < 3:
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]

        # Light smoothing to suppress noise
        if len(sub_v) >= 5:
            kernel = np.ones(5, dtype=np.float64) / 5.0
            smoothed = np.convolve(sub_v, kernel, mode='same')
        else:
            smoothed = sub_v

        # Local maxima
        peaks: List[Tuple[float, float]] = []
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] >= smoothed[i - 1] and smoothed[i] > smoothed[i + 1]:
                peaks.append((float(sub_t[i]), float(smoothed[i])))

        if not peaks:
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]

        if len(peaks) <= n:
            # Fewer peaks than vowels: pad with midpoints of largest gaps
            result = sorted(p[0] for p in peaks)
            while len(result) < n:
                extended = [t_start] + result + [t_end]
                gaps = [extended[i + 1] - extended[i] for i in range(len(extended) - 1)]
                max_idx = gaps.index(max(gaps))
                new_t = (extended[max_idx] + extended[max_idx + 1]) / 2
                result.append(new_t)
                result.sort()
            return result

        # More peaks than vowels: take strongest N by intensity, then sort by time
        peaks.sort(key=lambda p: -p[1])
        return sorted(p[0] for p in peaks[:n])

    def _anchor_per_phrase(
            self,
            events: List[PhonemeEvent],
            intensity,
            phrases: List[Tuple[float, float]],
            ) -> None:
        """Snap vowels to intensity peaks within each phrase.

        Algorithm:
          1. For each phrase, count vowels
          2. Find that many intensity peaks in the phrase
          3. Snap each vowel to its corresponding peak
          4. Redistribute consonants in the gaps between anchored vowels

        """
        for phrase_start, phrase_end in phrases:
            phrase_events = [e for e in events
                             if e.start >= phrase_start - 0.02
                             and e.end <= phrase_end + 0.02]
            if not phrase_events:
                continue

            vowels = [e for e in phrase_events if self._is_vowel(e.phoneme)]
            n_vowels = len(vowels)
            if n_vowels == 0:
                continue

            peaks = self._find_n_peaks(intensity, phrase_start, phrase_end, n_vowels)
            if len(peaks) != n_vowels:
                continue  # safety: skip phrase if peak count mismatch

            # Anchor each vowel: position so peak lands at 40% through the vowel
            for vowel, peak_time in zip(vowels, peaks):
                dur = max(vowel.end - vowel.start, 0.04)
                new_start = peak_time - 0.4 * dur
                new_end = new_start + dur
                new_start = max(new_start, phrase_start)
                new_end = min(new_end, phrase_end)
                if new_end > new_start + 0.02:
                    vowel.start = new_start
                    vowel.end = new_end

            # Redistribute consonants between anchored vowels
            self._fill_consonants(phrase_events, phrase_start, phrase_end)

    def _fill_consonants(
            self,
            phrase_events: List[PhonemeEvent],
            phrase_start: float,
            phrase_end: float,
            ) -> None:
        """After vowels are anchored, distribute consonants evenly in the gaps."""
        n = len(phrase_events)
        if n == 0:
            return

        vowel_pos = [i for i, e in enumerate(phrase_events) if self._is_vowel(e.phoneme)]
        if not vowel_pos:
            return

        # Leading consonants (before first vowel)
        first_v = vowel_pos[0]
        if first_v > 0:
            leading = phrase_events[:first_v]
            gap_end = phrase_events[first_v].start
            gap_start = phrase_start
            gap = gap_end - gap_start
            if gap > 0.001:
                per = gap / len(leading)
                for j, c in enumerate(leading):
                    c.start = gap_start + j * per
                    c.end = gap_start + (j + 1) * per
            else:
                # Stack tightly before vowel
                tick = 0.02
                for j, c in enumerate(leading):
                    c.start = gap_end - tick * (len(leading) - j)
                    c.end = gap_end - tick * (len(leading) - j - 1)

        # Between vowels
        for k in range(len(vowel_pos) - 1):
            v1_idx = vowel_pos[k]
            v2_idx = vowel_pos[k + 1]
            between = phrase_events[v1_idx + 1: v2_idx]
            if not between:
                continue
            gap_start = phrase_events[v1_idx].end
            gap_end = phrase_events[v2_idx].start
            gap = gap_end - gap_start
            if gap > 0.001:
                per = gap / len(between)
                for j, c in enumerate(between):
                    c.start = gap_start + j * per
                    c.end = gap_start + (j + 1) * per
            else:
                # Vowels too close: collapse consonants at midpoint
                mid = (phrase_events[v1_idx].end + phrase_events[v2_idx].start) / 2
                tick = 0.01
                offset = tick * len(between) / 2
                for j, c in enumerate(between):
                    c.start = mid - offset + j * tick
                    c.end = c.start + tick

        # Trailing consonants (after last vowel)
        last_v = vowel_pos[-1]
        if last_v < n - 1:
            trailing = phrase_events[last_v + 1:]
            gap_start = phrase_events[last_v].end
            gap_end = phrase_end
            gap = gap_end - gap_start
            if gap > 0.001:
                per = gap / len(trailing)
                for j, c in enumerate(trailing):
                    c.start = gap_start + j * per
                    c.end = gap_start + (j + 1) * per

    def _g2p_convert(self, text: str) -> List[Tuple[str, int]]:
        """Convert transcript to Arpabet phonemes via g2p_en.

        Returns list of (phoneme, word_index) tuples so Rule 8
        can track word boundaries.
        """
        raw_phonemes = self.g2p(text)

        punctuation = {'.', ',', '?', '!', ':', ';', '-', '"', "'"}
        result: List[Tuple[str, int]] = []
        word_idx = 0

        for p in raw_phonemes:
            if p == ' ':
                word_idx += 1
                continue
            if p in punctuation or not p.strip():
                continue
            result.append((p, word_idx))

        return result