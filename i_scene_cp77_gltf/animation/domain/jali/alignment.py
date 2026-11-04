from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from ....assetio.arrays import read_npz_arrays
from ....core.log import debug_exception, get_logger
from ...model.jali.events import PhonemeEvent
from .capability import call, dependency_status, g2p_en, parselmouth
from .events import create_phoneme_event

_LOG = get_logger(__name__)

# Forced alignment: a small frame classifier (log-mel context window -> phoneme posteriors)
# trained on phoneme segments aligned to the game's own lipsync clips, decoded with a
# duration-explicit Viterbi over the g2p phoneme sequence with optional pauses between words.
ALIGNER_MODEL_PATH = Path(__file__).with_name("aligner_model.npz")

HOP = 0.01
WIN = 0.025
N_MEL = 26
N_CEP = 13

# Similar phoneme to score with when the model has no class for one.
BACKOFF = {
    "ZH": "SH",
    "SH": "CH",
    "CH": "JH",
    "JH": "CH",
    "OY": "OW",
    "OW": "AO",
    "AW": "AA",
    "UH": "AH",
    "TH": "DH",
    "DH": "TH",
    "NG": "N",
    "G": "K",
    "Y": "IY",
    "AY": "AA",
    "EY": "EH",
    "ER": "R",
    "AX": "AH",
    "IX": "IH",
}


def _mel(f):
    return 2595.0 * np.log10(1.0 + f / 700.0)


def _imel(m):
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _deltas(f: np.ndarray, w: int = 2) -> np.ndarray:
    pad = np.pad(f, ((w, w), (0, 0)), mode="edge")
    num = sum(
        k * (pad[w + k : len(f) + w + k] - pad[w - k : len(f) + w - k])
        for k in range(1, w + 1)
    )
    return num / (2 * sum(k * k for k in range(1, w + 1)))


def acoustic_features(samples: np.ndarray, sr: float, kind: str = "mfcc") -> np.ndarray:
    """Per-utterance normalised cepstra and relative energy, with deltas, one row per HOP"""
    x = np.asarray(samples, np.float64)
    if x.ndim > 1:
        x = x.mean(axis=0)
    hop = int(round(HOP * sr))
    win = int(round(WIN * sr))
    n = max(int(np.ceil(len(x) / hop)), 1)
    x = np.append(x[:1], x[1:] - 0.97 * x[:-1])
    x = np.concatenate([np.zeros((win - hop) // 2), x, np.zeros(win)])
    nfft = 1 << int(np.ceil(np.log2(win)))
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    edges = _imel(np.linspace(_mel(60.0), _mel(min(8000.0, sr / 2)), N_MEL + 2))
    lo, mid, hi = edges[:-2, None], edges[1:-1, None], edges[2:, None]
    bank = np.clip(
        np.minimum((freqs - lo) / (mid - lo), (hi - freqs) / (hi - mid)), 0.0, None
    )
    window = np.hamming(win)[None, :]
    mel_power = np.empty((n, N_MEL))
    total_power = np.empty(n)
    for first in range(0, n, 512):
        # In blocks, so long lines do not hold the whole spectrogram in memory.
        frames = np.arange(first, min(first + 512, n))
        idx = np.minimum(np.arange(win)[None, :] + hop * frames[:, None], len(x) - 1)
        power = np.abs(np.fft.rfft(x[idx] * window, nfft, axis=1)) ** 2
        mel_power[frames] = power @ bank.T
        total_power[frames] = power.sum(axis=1)
    logmel = np.log(mel_power + 1e-10)
    if kind == "logmel":
        spec = logmel
    else:
        dct = np.cos(
            np.pi
            / N_MEL
            * (np.arange(N_MEL)[None, :] + 0.5)
            * np.arange(N_CEP)[:, None]
        )
        spec = logmel @ dct.T
    energy = np.log(total_power + 1e-10)
    rel = (energy - np.percentile(energy, 95))[:, None] / 5.0
    base = np.hstack([(spec - spec.mean(0)) / (spec.std(0) + 1e-6), rel])
    return np.hstack([base, _deltas(base), _deltas(_deltas(base))])


def stack_context(feats: np.ndarray, ctx: int, stride: int) -> np.ndarray:
    T = len(feats)
    r = ctx * stride
    pad = np.pad(feats, ((r, r), (0, 0)), mode="edge")
    return np.hstack(
        [pad[r + o * stride : r + o * stride + T] for o in range(-ctx, ctx + 1)]
    )


def state_key(phone: str, k: int, n_sub: int) -> str:
    return phone if (phone == "SIL" or n_sub == 1) else f"{phone}#{k}"


@lru_cache(maxsize=4)
def load_aligner_model(path: str = "") -> dict | None:
    """The acoustic model, or None if it is missing or unreadable"""
    raw = read_npz_arrays(Path(path) if path else ALIGNER_MODEL_PATH)
    if raw is None:
        return None
    layers = []
    while f"W{len(layers)}" in raw:
        i = len(layers)
        layers.append(
            (raw[f"W{i}"].astype(np.float32), raw[f"b{i}"].astype(np.float32))
        )
    dur_phones = [str(p) for p in raw["dur_phones"]]
    return {
        "kind": str(raw["kind"]),
        "ctx": int(raw["ctx"]),
        "stride": int(raw["stride"]),
        "n_sub": int(raw["n_sub"]),
        "mu": raw["mu"].astype(np.float32),
        "sd": raw["sd"].astype(np.float32),
        "layers": layers,
        "classes": [str(c) for c in raw["classes"]],
        "log_prior": raw["log_prior"].astype(np.float64),
        "dur": {
            p: (float(m), float(s))
            for p, m, s in zip(dur_phones, raw["dur_mean"], raw["dur_std"])
        },
        "dur_default": (float(raw["dur_default"][0]), float(raw["dur_default"][1])),
        "params": {
            str(k): float(v) for k, v in zip(raw["param_names"], raw["param_values"])
        },
    }


def frame_log_likelihoods(model: dict, feats: np.ndarray) -> np.ndarray:
    """Scaled log-likelihoods (log posterior - log prior), frames x classes"""
    h = (
        stack_context(feats, model["ctx"], model["stride"]).astype(np.float32)
        - model["mu"]
    ) / model["sd"]
    layers = model["layers"]
    for i, (w, b) in enumerate(layers):
        h = h @ w + b
        if i < len(layers) - 1:
            h = np.maximum(h, 0.0)
    z = h.astype(np.float64)
    z -= z.max(axis=1, keepdims=True)
    z -= np.log(np.exp(z).sum(axis=1, keepdims=True))
    return z - model["params"].get("prior_pow", 1.0) * model["log_prior"][None, :]


def _resolve_class(key: str, index: dict[str, int]) -> int | None:
    seen = set()
    while key not in index and key not in seen:
        seen.add(key)
        base, _, sub = key.partition("#")
        nxt = BACKOFF.get(base)
        if nxt is None:
            return None
        key = nxt + ("#" + sub if sub else "")
    return index.get(key)


def viterbi_align(
    model: dict, loglik: np.ndarray, words: list[list[str]]
) -> list[tuple[int, int, int]]:
    """Align words to frames, with an optional pause before, between and after them"""
    params = model["params"]
    frame_weight = params.get("frame_weight", 0.3)
    dur_weight = params.get("dur_weight", 1.0)
    sil_penalty = params.get("sil_penalty", 0.0)
    max_dur_cap = int(params.get("max_dur", 100))
    n_sub = model["n_sub"]
    index = {c: i for i, c in enumerate(model["classes"])}
    fallback = loglik.mean(axis=1)
    T = len(loglik)

    states: list[tuple[str, bool, int]] = [("SIL", True, -1)]
    flat = 0
    for word in words:
        for p in word:
            states.append((p.rstrip("012"), False, flat))
            flat += 1
        states.append(("SIL", True, -1))
    # Shortest phoneme in frames (the game's lipsync has none under one 30 fps frame); relaxed when
    # the audio is too short to give every phoneme that long.
    min_dur = max(1, min(int(params.get("min_dur", 1)), T // max(flat, 1)))
    cums: dict[str, np.ndarray] = {}

    def cum(key: str) -> np.ndarray:
        if key not in cums:
            ci = _resolve_class(key, index)
            column = loglik[:, ci] if ci is not None else fallback
            cums[key] = np.concatenate([[0.0], np.cumsum(column * frame_weight)])
        return cums[key]

    S = len(states)
    neg = -1e18
    best = np.full((S, T + 1), neg)
    back_d = np.zeros((S, T + 1), np.int32)
    back_s = np.zeros((S, T + 1), np.int32)
    frames = np.arange(T + 1)
    for s, (p, _optional, _flat) in enumerate(states):
        if s == 0:
            entry = np.full(T + 1, neg)
            entry[0] = 0.0
            entry_from = np.full(T + 1, -1, np.int32)
        else:
            entry = best[s - 1].copy()
            entry_from = np.full(T + 1, s - 1, np.int32)
            if s >= 2 and states[s - 1][1]:
                better = best[s - 2] > entry
                entry[better] = best[s - 2][better]
                entry_from[better] = s - 2
            if s == 1 and entry[0] < 0.0:
                entry[0] = 0.0
                entry_from[0] = -1
        if p == "SIL":
            # No duration model: best start is a running max of entry - cumulative score.
            c = cum("SIL")
            g = entry - c
            run = np.maximum.accumulate(g)
            arg = np.maximum.accumulate(np.where(g >= run, frames, 0))
            best[s, 1:] = c[1:] + run[:-1] - sil_penalty
            starts = arg[:-1]
            back_d[s, 1:] = frames[1:] - starts
            back_s[s, 1:] = entry_from[starts]
            best[s, 1:][run[:-1] <= neg / 2] = neg
            continue
        dm, ds = model["dur"].get(p, model["dur_default"])
        dmax = int(min(T, max_dur_cap, max(15, np.exp(dm + 3.0 * ds))))
        subs = [cum(state_key(p, k, n_sub)) for k in range(n_sub)]
        dmax = max(dmax, min_dur)
        if n_sub == 1:
            # Vectorised over durations: score[b, j] = entry[b - d] - c[b - d] + c[b] + duration term, d = durs[j].
            c = subs[0]
            durs = np.arange(min_dur, dmax + 1)
            dur_lp = dur_weight * (
                -0.5 * ((np.log(durs) - dm) / ds) ** 2 - np.log(ds * durs)
            )
            padded = np.concatenate([np.full(dmax, neg), entry - c])
            score = (
                np.lib.stride_tricks.sliding_window_view(padded, dmax + 1)[
                    :, dmax - durs
                ]
                + dur_lp
            )
            pick = score.argmax(axis=1)
            value = score[frames, pick] + c
            valid = value > neg / 2
            chosen = durs[pick]
            best[s] = np.where(valid, value, neg)
            back_d[s] = np.where(valid, chosen, 0)
            back_s[s] = np.where(valid, entry_from[np.maximum(frames - chosen, 0)], 0)
            continue
        for d in range(min_dur, dmax + 1):
            n = T + 1 - d
            dur_lp = -0.5 * ((np.log(d) - dm) / ds) ** 2 - np.log(ds * d)
            cand = entry[:n] + dur_weight * dur_lp
            cuts = [int(round(d * k / n_sub)) for k in range(n_sub + 1)]
            for k, c in enumerate(subs):
                cand = cand + (
                    c[cuts[k + 1] : cuts[k + 1] + n] - c[cuts[k] : cuts[k] + n]
                )
            target = best[s, d:]
            upd = cand > target
            if upd.any():
                target[upd] = cand[upd]
                back_d[s, d:][upd] = d
                back_s[s, d:][upd] = entry_from[:n][upd]
    s = S - 1
    if best[S - 2, T] > best[S - 1, T]:
        s = S - 2
    if best[s, T] <= neg / 2:
        raise ValueError("no alignment path")
    t = T
    out: list[tuple[int, int, int]] = []
    while s >= 0 and t > 0:
        d = int(back_d[s, t])
        if d <= 0:
            raise ValueError("broken alignment path")
        out.append((states[s][2], t - d, t))
        s = int(back_s[s, t])
        t -= d
    out.reverse()
    return out


class TranscriptAligner:
    def __init__(self, audio_path: str, transcript: str, method: str = "auto"):
        """method is 'auto', 'forced' or 'legacy'"""
        if not dependency_status().parselmouth:
            raise ImportError("parselmouth is required")
        if not dependency_status().g2p:
            raise ImportError("g2p_en is required for accurate transcript alignment")
        self.audio_path = audio_path
        self.transcript = transcript
        self.method = method
        self.method_used = ""
        self.g2p = g2p_en.G2p()
        self.vowels = {
            "AA",
            "AE",
            "AH",
            "AO",
            "AW",
            "AY",
            "EH",
            "ER",
            "EY",
            "IH",
            "IY",
            "OW",
            "OY",
            "UH",
            "UW",
            "AX",
            "IX",
        }

    def align_phonemes(self) -> list[PhonemeEvent]:
        sound = parselmouth.Sound(self.audio_path)
        self.duration = sound.get_total_duration()
        if self.method != "legacy":
            model = load_aligner_model()
            if model is not None:
                try:
                    events = self._align_forced(sound, model)
                    self.method_used = "forced"
                    return events
                except Exception as error:
                    # 'auto' must never be worse than the legacy aligner: fall back on any failure.
                    if self.method == "forced":
                        raise
                    _LOG.warning(
                        "Forced alignment failed (%s); using legacy timing", error
                    )
            elif self.method == "forced":
                raise FileNotFoundError(
                    f"aligner model not found: {ALIGNER_MODEL_PATH}"
                )
            else:
                _LOG.warning(
                    "Aligner model missing (%s); using legacy timing",
                    ALIGNER_MODEL_PATH,
                )
        self.method_used = "legacy"
        return self._align_legacy(sound)

    def _align_forced(self, sound, model: dict) -> list[PhonemeEvent]:
        # g2p passes non-words such as '...' through unchanged; pauses are optional states already.
        phoneme_words = [
            (p, wi) for p, wi in self._g2p_convert(self.transcript) if p[:1].isalpha()
        ]
        if not phoneme_words:
            return []
        words: list[list[str]] = []
        word_ids: list[int] = []
        for p, wi in phoneme_words:
            if not word_ids or word_ids[-1] != wi:
                words.append([])
                word_ids.append(wi)
            words[-1].append(p)
        samples = np.asarray(sound.values, np.float64)
        feats = acoustic_features(
            samples, float(sound.sampling_frequency), model["kind"]
        )
        if len(feats) < 2 * len(phoneme_words):
            raise ValueError("audio too short for the transcript")
        path = viterbi_align(model, frame_log_likelihoods(model, feats), words)
        params = model["params"]
        offset = params.get("offset", 0.0)
        min_sil = params.get("min_sil", 0.05)
        events: list[PhonemeEvent] = []
        for flat, a, b in path:
            start = min(max(a * HOP + offset, 0.0), self.duration)
            end = min(max(b * HOP + offset, 0.0), self.duration)
            if flat < 0:
                if end - start >= min_sil:
                    sil = create_phoneme_event("SIL", start, end)
                    sil.word_index = -1
                    events.append(sil)
                continue
            p, wi = phoneme_words[flat]
            ev = create_phoneme_event(p, start, max(end, start + 1e-3), p[-1] in "12")
            ev.word_index = wi
            events.append(ev)
        events.sort(key=lambda e: e.start)
        return events

    def _align_legacy(self, sound) -> list[PhonemeEvent]:
        intensity = sound.to_intensity()
        textgrid = call(
            intensity, "To TextGrid (silences)", -25, 0.1, 0.05, "silent", "sounding"
        )
        intervals: list[tuple[float, float]] = []
        silent_intervals: list[tuple[float, float]] = []
        num_intervals = call(textgrid, "Get number of intervals", 1)
        for i in range(1, num_intervals + 1):
            label = call(textgrid, "Get label of interval", 1, i)
            start = call(textgrid, "Get start time of interval", 1, i)
            end = call(textgrid, "Get end time of interval", 1, i)
            if label == "sounding":
                intervals.append((start, end))
            elif end - start > 0.05:
                silent_intervals.append((start, end))
        if not intervals:
            intervals = [(0.0, self.duration)]
        phoneme_words = self._g2p_convert(self.transcript)
        if not phoneme_words:
            return []
        weights = [
            3.0 if p.rstrip("012") in self.vowels else 1.0 for p, _wi in phoneme_words
        ]
        total_weight = sum(weights)
        total_speech_time = sum((end - start for start, end in intervals))
        events: list[PhonemeEvent] = []
        cumulative_weight = 0.0
        for (p, wi), w in zip(phoneme_words, weights):
            start_speech = cumulative_weight / total_weight * total_speech_time
            end_speech = (cumulative_weight + w) / total_weight * total_speech_time
            abs_start = self._map_time(start_speech, intervals)
            abs_end = self._map_time(end_speech, intervals)
            if abs_end > abs_start:
                stressed = p[-1] in "12" if p else False
                ev = create_phoneme_event(p, abs_start, abs_end, stressed)
                ev.word_index = wi
                events.append(ev)
            cumulative_weight += w
        self._anchor_per_phrase(events, intensity, intervals)
        for s_start, s_end in silent_intervals:
            sil = create_phoneme_event("SIL", s_start, s_end)
            sil.word_index = -1
            events.append(sil)
        events.sort(key=lambda e: e.start)
        return events

    @staticmethod
    def _map_time(speech_time: float, intervals: list[tuple[float, float]]) -> float:
        accumulated = 0.0
        for start, end in intervals:
            interval_dur = end - start
            if accumulated + interval_dur >= speech_time - 1e-05:
                return start + (speech_time - accumulated)
            accumulated += interval_dur
        return intervals[-1][1]

    def _is_vowel(self, phoneme: str) -> bool:
        return phoneme.rstrip("012") in self.vowels

    def _find_n_peaks(
        self, intensity, t_start: float, t_end: float, n: int
    ) -> list[float]:
        if n <= 0:
            return []
        try:
            times = np.asarray(intensity.xs(), dtype=np.float64)
            values = np.asarray(intensity.values, dtype=np.float64).ravel()
        except Exception:
            debug_exception(_LOG, "Praat intensity contour details")
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]
        mask = (times >= t_start) & (times <= t_end)
        sub_t = times[mask]
        sub_v = values[mask]
        if len(sub_v) < 3:
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]
        if len(sub_v) >= 5:
            kernel = np.ones(5, dtype=np.float64) / 5.0
            smoothed = np.convolve(sub_v, kernel, mode="same")
        else:
            smoothed = sub_v
        peaks: list[tuple[float, float]] = []
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] >= smoothed[i - 1] and smoothed[i] > smoothed[i + 1]:
                peaks.append((float(sub_t[i]), float(smoothed[i])))
        if not peaks:
            return [t_start + (i + 0.5) * (t_end - t_start) / n for i in range(n)]
        if len(peaks) <= n:
            result = sorted(p[0] for p in peaks)
            while len(result) < n:
                extended = [t_start] + result + [t_end]
                gaps = [extended[i + 1] - extended[i] for i in range(len(extended) - 1)]
                max_idx = gaps.index(max(gaps))
                new_t = (extended[max_idx] + extended[max_idx + 1]) / 2
                result.append(new_t)
                result.sort()
            return result
        peaks.sort(key=lambda p: -p[1])
        return sorted(p[0] for p in peaks[:n])

    def _anchor_per_phrase(
        self, events: list[PhonemeEvent], intensity, phrases: list[tuple[float, float]]
    ) -> None:
        for phrase_start, phrase_end in phrases:
            phrase_events = [
                e
                for e in events
                if e.start >= phrase_start - 0.02 and e.end <= phrase_end + 0.02
            ]
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

    def _fill_consonants(
        self, phrase_events: list[PhonemeEvent], phrase_start: float, phrase_end: float
    ) -> None:
        n = len(phrase_events)
        if n == 0:
            return
        vowel_pos = [
            i for i, e in enumerate(phrase_events) if self._is_vowel(e.phoneme)
        ]
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
            between = phrase_events[v1_idx + 1 : v2_idx]
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
            trailing = phrase_events[last_v + 1 :]
            gap_start = phrase_events[last_v].end
            gap_end = phrase_end
            gap = gap_end - gap_start
            if gap > 0.001:
                per = gap / len(trailing)
                for j, c in enumerate(trailing):
                    c.start = gap_start + j * per
                    c.end = gap_start + (j + 1) * per

    def _g2p_convert(self, text: str) -> list[tuple[str, int]]:
        raw_phonemes = self.g2p(text)
        punctuation = {".", ",", "?", "!", ":", ";", "-", '"', "'"}
        result: list[tuple[str, int]] = []
        word_idx = 0
        for p in raw_phonemes:
            if p == " ":
                word_idx += 1
                continue
            if p in punctuation or not p.strip():
                continue
            result.append((p, word_idx))
        return result
