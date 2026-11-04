from __future__ import annotations

from collections import defaultdict

from ...model.jali.events import PhonemeEvent
from ...model.jali.phonemes import (
    BILABIALS,
    LABIODENTALS,
    LIP_HEAVY,
    OBSTRUENTS_NASALS,
    PAUSES,
    SIBILANTS,
    TONGUE_ONLY,
    VOWELS,
    _get_viseme,
)


class CoarticulationEngine:
    def apply_rules(self, events: list[PhonemeEvent]) -> list[PhonemeEvent]:
        if not events:
            return events
        for event in events:
            if event.original_start < 0:
                event.original_start = event.start
            if event.original_end < 0:
                event.original_end = event.end
        for event in events:
            self._classify_phoneme(event)
        self._set_context(events)
        self._infer_word_prominence(events)
        self._substitute_pauses(events)
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
        p = event.phoneme
        event.is_vowel = p in VOWELS
        event.is_bilabial = p in BILABIALS
        event.is_labiodental = p in LABIODENTALS
        event.is_sibilant = p in SIBILANTS
        event.is_tongue_only = p in TONGUE_ONLY
        event.is_lip_heavy = p in LIP_HEAVY
        event.is_obstruent_nasal = p in OBSTRUENTS_NASALS

    @staticmethod
    def _set_context(events: list[PhonemeEvent]):
        n = len(events)
        last_pause_end = float("-inf")
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
        next_pause_start = float("inf")
        for i in range(n - 1, -1, -1):
            event = events[i]
            event.next_pause_start = next_pause_start
            if event.phoneme in PAUSES:
                next_pause_start = event.start

    @staticmethod
    def _substitute_pauses(events: list[PhonemeEvent]):
        n = len(events)
        speech = [i for i, event in enumerate(events) if event.phoneme not in PAUSES]
        first = speech[0] if speech else n
        last = speech[-1] if speech else -1
        for i, event in enumerate(events):
            if event.phoneme not in PAUSES:
                continue
            is_interior = first < i < last
            if is_interior:
                if i > 0 and events[i - 1].phoneme not in PAUSES:
                    event.jaw = events[i - 1].jaw
                elif i < n - 1 and events[i + 1].phoneme not in PAUSES:
                    event.jaw = events[i + 1].jaw
                event.lip = 0.0
                event.jaw = max(event.jaw * 0.7, 0.15)
                event.dominance = 0.05
            else:
                event.jaw = 0.0
                event.lip = 0.0
                event.dominance = 0.05

    @staticmethod
    def _merge_duplicates(events: list[PhonemeEvent]):
        merged = []
        for event in events:
            if merged and _get_viseme(merged[-1].phoneme) == _get_viseme(event.phoneme):
                merged[-1].end = event.end
                merged[-1].original_end = event.original_end
            else:
                merged.append(event)
        events[:] = merged

    @staticmethod
    def _open_lip_neighbours(events: list[PhonemeEvent], i: int):
        """The events before and after events[i] that are neither pauses nor bilabial or labiodental"""
        for j in (i - 1, i + 1):
            if 0 <= j < len(events):
                other = events[j]
                if other.phoneme not in PAUSES and (
                    not (other.is_bilabial or other.is_labiodental)
                ):
                    yield j < i, other

    @staticmethod
    def _extend_lip_heavy(events: list[PhonemeEvent]):
        for i, event in enumerate(events):
            if not event.is_lip_heavy:
                continue
            for before, other in CoarticulationEngine._open_lip_neighbours(events, i):
                if before:
                    event.start = other.start
                else:
                    event.end = other.end

    @staticmethod
    def _override_lip_shapes(events: list[PhonemeEvent]):
        for i, event in enumerate(events):
            if not event.is_lip_heavy:
                continue
            for _before, other in CoarticulationEngine._open_lip_neighbours(events, i):
                other.lip = event.lip

    @staticmethod
    def _apply_tongue_only(events: list[PhonemeEvent]):
        n = len(events)
        for i, event in enumerate(events):
            if not event.is_tongue_only:
                continue
            wi = event.word_index
            lip_source = None
            is_last = (
                i == n - 1
                or events[i + 1].word_index != wi
                or events[i + 1].phoneme in PAUSES
            )
            if not is_last:
                for j in range(i + 1, n):
                    ej = events[j]
                    if ej.word_index != wi or ej.phoneme in PAUSES:
                        break
                    if not ej.is_tongue_only:
                        lip_source = ej.lip
                        break
            if lip_source is None:
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
    def _apply_obstruent_rules(events: list[PhonemeEvent]):
        n = len(events)
        for i, event in enumerate(events):
            if not event.is_obstruent_nasal or event.is_sibilant:
                continue
            has_similar = False
            if i > 0 and events[i - 1].is_obstruent_nasal:
                has_similar = True
            if i < n - 1 and events[i + 1].is_obstruent_nasal:
                has_similar = True
            if event.duration < 0.033 and (not has_similar):
                event.jaw = 0.0
            elif event.duration >= 0.033:
                event.jaw = min(event.jaw, 0.3)

    @staticmethod
    def _apply_anticipation(events: list[PhonemeEvent]):
        n = len(events)
        if n < 2:
            return
        for i in range(n):
            event = events[i]
            if event.is_tongue_only or event.phoneme in PAUSES:
                continue
            wi = event.word_index
            is_last_in_word = (
                i == n - 1
                or events[i + 1].word_index != wi
                or events[i + 1].phoneme in PAUSES
            )
            if is_last_in_word:
                for j in range(i - 1, -1, -1):
                    if events[j].word_index != wi or events[j].phoneme in PAUSES:
                        break
                    if not events[j].is_tongue_only:
                        if events[j].is_lip_heavy:
                            event.lip = events[j].lip
                        break
            else:
                for j in range(i + 1, n):
                    if events[j].word_index != wi or events[j].phoneme in PAUSES:
                        break
                    if not events[j].is_tongue_only and events[j].is_lip_heavy:
                        event.lip = events[j].lip * 0.6
                        break

    @staticmethod
    def _enforce_constraints(events: list[PhonemeEvent]):
        NASALS = frozenset({"M", "N", "NG"})
        for event in events:
            p = event.phoneme.rstrip("012")
            if event.is_bilabial:
                event.jaw = 0.0
                event.lip = 0.0
                event.dominance = max(event.dominance, 1.0)
            elif event.is_labiodental:
                event.jaw = min(event.jaw, 0.1)
                event.dominance = max(event.dominance, 0.95)
            elif event.is_sibilant:
                event.jaw = min(event.jaw, 0.15)
            if p not in NASALS and p not in PAUSES:
                if (
                    not event.is_bilabial
                    and event.jaw < 0.01
                    and (abs(event.lip) < 0.01)
                ):
                    event.dominance = min(event.dominance, 0.1)

    @staticmethod
    def _infer_word_prominence(events: list[PhonemeEvent]):
        if not events:
            return
        word_groups: dict[int, list[PhonemeEvent]] = defaultdict(list)
        for ev in events:
            if ev.word_index >= 0:
                word_groups[ev.word_index].append(ev)
        for group in word_groups.values():
            max_stress = 0
            for ev in group:
                if ev.is_vowel and ev.stress_level > max_stress:
                    max_stress = ev.stress_level
            if max_stress < 2:
                for ev in group:
                    ev.word_prominent = False

    @staticmethod
    def _apply_stress_amplitude(events: list[PhonemeEvent]):
        for event in events:
            if not event.is_vowel:
                continue
            stress_known = event.word_index >= 0
            effective_stress = event.stress_level if stress_known else 1
            if effective_stress == 2:
                event.jaw = min(event.jaw * 1.1, 1.0)
            elif effective_stress == 1:
                pass
            else:
                event.jaw *= 0.6
                event.lip *= 0.7
            if not event.word_prominent:
                event.jaw *= 0.7
