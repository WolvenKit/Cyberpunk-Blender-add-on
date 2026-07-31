from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .capability import call, dependency_status, g2p_en, parselmouth
from .events import create_phoneme_event
from .model import PhonemeEvent

class TranscriptAligner:

    def __init__(self, audio_path: str, transcript: str):
        if not dependency_status().parselmouth:
            raise ImportError('parselmouth is required')
        if not dependency_status().g2p:
            raise ImportError('g2p_en is required for accurate transcript alignment')
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
        intensity = sound.to_intensity()
        textgrid = call(intensity, 'To TextGrid (silences)', -25, 0.1, 0.05, 'silent', 'sounding')
        intervals: List[Tuple[float, float]] = []
        silent_intervals: List[Tuple[float, float]] = []
        num_intervals = call(textgrid, 'Get number of intervals', 1)
        for i in range(1, num_intervals + 1):
            label = call(textgrid, 'Get label of interval', 1, i)
            start = call(textgrid, 'Get start time of interval', 1, i)
            end = call(textgrid, 'Get end time of interval', 1, i)
            if label == 'sounding':
                intervals.append((start, end))
            elif end - start > 0.05:
                silent_intervals.append((start, end))
        if not intervals:
            intervals = [(0.0, self.duration)]
        phoneme_words = self._g2p_convert(self.transcript)
        if not phoneme_words:
            return []
        weights = [3.0 if p.rstrip('012') in self.vowels else 1.0 for p, _wi in phoneme_words]
        total_weight = sum(weights)
        total_speech_time = sum((end - start for start, end in intervals))
        events: List[PhonemeEvent] = []
        cumulative_weight = 0.0
        for (p, wi), w in zip(phoneme_words, weights):
            start_speech = cumulative_weight / total_weight * total_speech_time
            end_speech = (cumulative_weight + w) / total_weight * total_speech_time
            abs_start = self._map_time(start_speech, intervals)
            abs_end = self._map_time(end_speech, intervals)
            if abs_end > abs_start:
                stressed = p[-1] in '12' if p else False
                ev = create_phoneme_event(p, abs_start, abs_end, stressed)
                ev.word_index = wi
                events.append(ev)
            cumulative_weight += w
        self._anchor_per_phrase(events, intensity, intervals)
        for s_start, s_end in silent_intervals:
            sil = create_phoneme_event('SIL', s_start, s_end)
            sil.word_index = -1
            events.append(sil)
        events.sort(key=lambda e: e.start)
        return events

    @staticmethod
    def _map_time(speech_time: float, intervals: List[Tuple[float, float]]) -> float:
        accumulated = 0.0
        for start, end in intervals:
            interval_dur = end - start
            if accumulated + interval_dur >= speech_time - 1e-05:
                return start + (speech_time - accumulated)
            accumulated += interval_dur
        return intervals[-1][1]

    def _is_vowel(self, phoneme: str) -> bool:
        return phoneme.rstrip('012') in self.vowels

    def _find_n_peaks(self, intensity, t_start: float, t_end: float, n: int) -> List[float]:
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
        if len(sub_v) >= 5:
            kernel = np.ones(5, dtype=np.float64) / 5.0
            smoothed = np.convolve(sub_v, kernel, mode='same')
        else:
            smoothed = sub_v
        peaks: List[Tuple[float, float]] = []
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] >= smoothed[i - 1] and smoothed[i] > smoothed[i + 1]:
                peaks.append((float(sub_t[i]), float(smoothed[i])))
        if not peaks:
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]
        if len(peaks) <= n:
            result = sorted((p[0] for p in peaks))
            while len(result) < n:
                extended = [t_start] + result + [t_end]
                gaps = [extended[i + 1] - extended[i] for i in range(len(extended) - 1)]
                max_idx = gaps.index(max(gaps))
                new_t = (extended[max_idx] + extended[max_idx + 1]) / 2
                result.append(new_t)
                result.sort()
            return result
        peaks.sort(key=lambda p: -p[1])
        return sorted((p[0] for p in peaks[:n]))

    def _anchor_per_phrase(self, events: List[PhonemeEvent], intensity, phrases: List[Tuple[float, float]]) -> None:
        for phrase_start, phrase_end in phrases:
            phrase_events = [e for e in events if e.start >= phrase_start - 0.02 and e.end <= phrase_end + 0.02]
            if not phrase_events:
                continue
            vowels = [e for e in phrase_events if self._is_vowel(e.phoneme)]
            n_vowels = len(vowels)
            if n_vowels == 0:
                continue
            peaks = self._find_n_peaks(intensity, phrase_start, phrase_end, n_vowels)
            if len(peaks) != n_vowels:
                continue
            for vowel, peak_time in zip(vowels, peaks):
                dur = max(vowel.end - vowel.start, 0.04)
                new_start = peak_time - 0.4 * dur
                new_end = new_start + dur
                new_start = max(new_start, phrase_start)
                new_end = min(new_end, phrase_end)
                if new_end > new_start + 0.02:
                    vowel.start = new_start
                    vowel.end = new_end
            self._fill_consonants(phrase_events, phrase_start, phrase_end)

    def _fill_consonants(self, phrase_events: List[PhonemeEvent], phrase_start: float, phrase_end: float) -> None:
        n = len(phrase_events)
        if n == 0:
            return
        vowel_pos = [i for i, e in enumerate(phrase_events) if self._is_vowel(e.phoneme)]
        if not vowel_pos:
            return
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
                tick = 0.02
                for j, c in enumerate(leading):
                    c.start = gap_end - tick * (len(leading) - j)
                    c.end = gap_end - tick * (len(leading) - j - 1)
        for k in range(len(vowel_pos) - 1):
            v1_idx = vowel_pos[k]
            v2_idx = vowel_pos[k + 1]
            between = phrase_events[v1_idx + 1:v2_idx]
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
                mid = (phrase_events[v1_idx].end + phrase_events[v2_idx].start) / 2
                tick = 0.01
                offset = tick * len(between) / 2
                for j, c in enumerate(between):
                    c.start = mid - offset + j * tick
                    c.end = c.start + tick
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
