from __future__ import annotations

from copy import copy
from functools import lru_cache

import numpy as np

from ...model.facial.constants import (
    ANIM_OVERRIDE_SUFFIX,
    LIPSYNC_POSE_SUFFIX,
    Envelope,
)
from ...model.jali.phonemes import PAUSES, VOWELS, _get_viseme
from ...model.jali.viseme_targets import (
    VISEME_DOMINANCE,
    VISEME_TARGETS,
    VISEME_TIMING,
    VISEME_TRACKS,
)
from .mappings import build_jali_track_mappings, get_phoneme_track_overrides

JALI_DIAL_MIDPOINT = 1.0
OVERRIDE_UNSUPPRESSED = 1.0


@lru_cache(maxsize=16)
def _compile_track_layout(track_names: tuple[str, ...]):
    track_map = {name: index for index, name in enumerate(track_names)}
    override_indices = tuple(
        index
        for index, name in enumerate(track_names)
        if name.endswith(ANIM_OVERRIDE_SUFFIX)
    )
    mapping_indices = []
    for mapping in build_jali_track_mappings():
        base_name = mapping["track_name"]
        index = track_map.get(f"{base_name}{LIPSYNC_POSE_SUFFIX}")
        if index is None:
            index = track_map.get(base_name)
        mapping_indices.append(index)
    override_pairs = _build_override_pairs(track_names, track_map, override_indices)
    return track_map, override_indices, tuple(mapping_indices), override_pairs


def _build_override_pairs(track_names, track_map, override_indices):
    overrides = []
    outputs = []
    for index in override_indices:
        base_name = track_names[index][: -len(ANIM_OVERRIDE_SUFFIX)]
        output = track_map.get(f"{base_name}{LIPSYNC_POSE_SUFFIX}")
        if output is None:
            continue
        overrides.append(index)
        outputs.append(output)
    return (
        np.asarray(overrides, dtype=np.intp),
        np.asarray(outputs, dtype=np.intp),
    )


SILENCE = "SIL"
# VISEME_TARGETS row keys: "AA1" stressed vowel, "AY:1" / "AY:2" diphthong halves, "T~R" before a rounded
# sound, "T$" word-final consonant, "SIL^" silence at the start or end of a line.
EDGE_SILENCE = "SIL^"
ROUNDING_CONTEXT = frozenset({"UW", "OW", "OY", "AO", "AW", "W"})
DIPHTHONG_PARTS = (":1", ":2")
_STRESS_DIGIT = {2: "1", 1: "2", 0: "0"}
_VISEME_TABLE = np.asarray(
    [VISEME_TARGETS[p] for p in sorted(VISEME_TARGETS)], dtype=np.float64
)
_VISEME_ROW = {p: i for i, p in enumerate(sorted(VISEME_TARGETS))}
# Calibrated blending dominance per row key (empty: keep the coarticulation engine's values).
_VISEME_DOMINANCE = dict(VISEME_DOMINANCE)
# Calibrated dominance-envelope timing (empty: the original JALI constants).
_VISEME_TIMING = dict(VISEME_TIMING)


def viseme_timing() -> dict:
    return dict(_VISEME_TIMING)


def _base(phoneme) -> str:
    key = str(phoneme).rstrip("012")
    return SILENCE if key in PAUSES else key


def _row_keys(events, index) -> list[str]:
    """Most specific table keys first for events[index]"""
    event = events[index]
    base = _base(event.phoneme)
    part = getattr(event, "viseme_part", "")
    if base == SILENCE:
        return [EDGE_SILENCE, SILENCE] if index in (0, len(events) - 1) else [SILENCE]
    keys = []
    if part:
        keys.append(base + part)
    if base in VOWELS:
        if getattr(event, "stress_marked", False):
            keys.append(
                base + _STRESS_DIGIT.get(int(getattr(event, "stress_level", 0)), "0")
            )
    else:
        following = events[index + 1] if index + 1 < len(events) else None
        if following is not None and _base(following.phoneme) in ROUNDING_CONTEXT:
            keys.append(base + "~R")
        word = getattr(event, "word_index", -1)
        if word >= 0 and (
            following is None
            or _base(following.phoneme) == SILENCE
            or getattr(following, "word_index", -1) != word
        ):
            keys.append(base + "$")
    keys.append(base)
    return keys


def _event_key(events, index) -> str:
    for key in _row_keys(events, index):
        if key in _VISEME_ROW:
            return key
    return _fallback_key(events[index].phoneme)


def _fallback_key(phoneme) -> str:
    key = _base(phoneme)
    if key not in _VISEME_ROW:
        viseme = _get_viseme(key)
        key = next(
            (
                p
                for p in sorted(_VISEME_ROW)
                if p != SILENCE and _get_viseme(p) == viseme
            ),
            SILENCE,
        )
    return key


def _calibrated_dominance(events, keys) -> list:
    """Events whose blending dominance comes from the table (when it has a value for the key)"""
    if not _VISEME_DOMINANCE:
        return events
    out = []
    for event, key in zip(events, keys):
        value = _VISEME_DOMINANCE.get(key)
        if value is None:
            out.append(event)
            continue
        event = copy(event)
        event.dominance = float(value)
        out.append(event)
    return out


def _split_diphthongs(events) -> list:
    """Diphthongs with onset/offset rows become two half-length events"""
    out = []
    for event in events:
        base = _base(event.phoneme)
        if (
            base + DIPHTHONG_PARTS[0] not in _VISEME_ROW
            or base + DIPHTHONG_PARTS[1] not in _VISEME_ROW
        ):
            out.append(event)
            continue
        middle = 0.5 * (event.start + event.end)
        first, second = copy(event), copy(event)
        first.end, second.start = middle, middle
        first.original_start, first.original_end = event.apex, middle
        second.original_start, second.original_end = middle, max(event.end, middle)
        first.viseme_part, second.viseme_part = DIPHTHONG_PARTS
        out += [first, second]
    return out


def viseme_row(phoneme: str) -> np.ndarray:
    """Calibrated targets for a phoneme"""
    return _VISEME_TABLE[_VISEME_ROW[_fallback_key(phoneme)]]


@lru_cache(maxsize=16)
def _viseme_columns(track_names: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    track_map = {name: index for index, name in enumerate(track_names)}
    pairs = [
        (track_map[name], column)
        for column, name in enumerate(VISEME_TRACKS)
        if name in track_map
    ]
    rig_columns = np.asarray([rig for rig, _ in pairs], dtype=np.intp)
    table_columns = np.asarray([column for _, column in pairs], dtype=np.intp)
    return rig_columns, table_columns


def _apply_override_coupling(tracks: np.ndarray, override_pairs) -> None:
    override_indices, output_indices = override_pairs
    if not len(override_indices):
        return
    coupled = np.clip(1.0 - tracks[:, output_indices], 0.0, 1.0)
    tracks[:, override_indices] = np.minimum(tracks[:, override_indices], coupled)


class JALIToCp77Bridge:
    def __init__(self):
        self.mappings = build_jali_track_mappings()
        self.phoneme_overrides = get_phoneme_track_overrides()

    def recouple_overrides(
        self, tracks: np.ndarray, track_names: list[str]
    ) -> np.ndarray:
        _apply_override_coupling(tracks, _compile_track_layout(tuple(track_names))[3])
        return tracks

    def jali_to_tracks(
        self,
        ja_curve: np.ndarray,
        li_curve: np.ndarray,
        track_names: list[str],
        reference_tracks=None,
    ) -> np.ndarray:
        num_frames = len(ja_curve)
        num_tracks = len(track_names)
        names = tuple(track_names)
        track_map, override_indices, mapping_indices, override_pairs = (
            _compile_track_layout(names)
        )
        tracks = self._seed_tracks(
            num_frames, num_tracks, override_indices, reference_tracks
        )
        if Envelope.JALI_JAW < num_tracks:
            tracks[:, Envelope.JALI_JAW] = np.clip(
                JALI_DIAL_MIDPOINT + ja_curve, 0.0, 2.0
            )
        if Envelope.JALI_LIPS < num_tracks:
            tracks[:, Envelope.JALI_LIPS] = np.clip(
                JALI_DIAL_MIDPOINT + li_curve, 0.0, 2.0
            )
        if Envelope.LIPSYNC < num_tracks:
            tracks[:, Envelope.LIPSYNC] = 1.0
        if Envelope.MUZZLE_LIPS < num_tracks:
            tracks[:, Envelope.MUZZLE_LIPS] = 1.0
        ja_clipped = np.clip(ja_curve, 0.0, 1.0)
        li_clipped = np.clip(li_curve, -1.0, 1.0)
        ja_values = ja_clipped.astype(np.float64)
        li_values = li_clipped.astype(np.float64)
        for mapping, track_idx in zip(self.mappings, mapping_indices):
            if track_idx is None:
                continue
            weights = np.broadcast_to(
                mapping["weight_func"](ja_values, li_values), (num_frames,)
            ).astype(np.float32)
            np.clip(weights, 0.0, 1.5, out=weights)
            np.maximum(tracks[:, track_idx], weights, out=tracks[:, track_idx])
        _apply_override_coupling(tracks, override_pairs)
        return tracks

    @staticmethod
    def _seed_tracks(
        num_frames, num_tracks, override_indices, reference_tracks
    ) -> np.ndarray:
        reference = np.asarray(
            reference_tracks if reference_tracks is not None else (),
            dtype=np.float32,
        ).ravel()
        if reference.size:
            row = np.zeros(num_tracks, dtype=np.float32)
            width = min(reference.size, num_tracks)
            row[:width] = reference[:width]
            return np.tile(row, (num_frames, 1))
        tracks = np.zeros((num_frames, num_tracks), dtype=np.float32)
        if override_indices:
            tracks[:, override_indices] = OVERRIDE_UNSUPPRESSED
        return tracks

    def viseme_tracks(
        self,
        events: list,
        duration: float,
        blender,
        track_names: list[str],
        reference_tracks=None,
    ) -> np.ndarray:
        """Tracks from the calibrated per-phoneme targets, blended by event dominance"""
        names = tuple(track_names)
        _track_map, override_indices, _mapping_indices, _override_pairs = (
            _compile_track_layout(names)
        )
        columns, table_columns = _viseme_columns(names)
        num_frames = int(duration * blender.fps) + 1
        tracks = self._seed_tracks(
            num_frames, len(names), override_indices, reference_tracks
        )
        if Envelope.LIPSYNC < len(names):
            tracks[:, Envelope.LIPSYNC] = 1.0
        if Envelope.MUZZLE_LIPS < len(names):
            tracks[:, Envelope.MUZZLE_LIPS] = 1.0
        if not len(columns):
            return tracks
        events = _split_diphthongs(events)
        keys = [_event_key(events, i) for i in range(len(events))]
        rows = np.vstack(
            [_VISEME_TABLE[_VISEME_ROW[key]][table_columns] for key in keys]
        )
        events = _calibrated_dominance(events, keys)
        fallback = viseme_row(SILENCE)[table_columns]
        tracks[:, columns] = blender.blend_event_values(
            events, rows, duration, fallback
        )[:num_frames]
        return tracks
