from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np

from ..facial.constants import (
    ANIM_OVERRIDE_SUFFIX,
    ENV_FACE_ENVELOPE as IDX_FACE_ENVELOPE,
    ENV_JALI_JAW as IDX_JALI_JAW,
    ENV_JALI_LIPS as IDX_JALI_LIPS,
    ENV_LIPSYNC as IDX_LIPSYNC_ENVELOPE,
    ENV_LOWER_FACE as IDX_LOWER_FACE,
    ENV_MUZZLE_BROWS as IDX_MUZZLE_BROWS,
    ENV_MUZZLE_EYES as IDX_MUZZLE_EYES,
    ENV_MUZZLE_LIPS as IDX_MUZZLE_LIPS,
    ENV_UPPER_FACE as IDX_UPPER_FACE,
    LIPSYNC_POSE_SUFFIX,
)
from .mappings import build_jali_track_mappings, get_phoneme_track_overrides


@lru_cache(maxsize=16)
def _compile_track_layout(track_names: tuple[str, ...]):
    track_map = {name: index for index, name in enumerate(track_names)}
    override_indices = tuple(
        index for index, name in enumerate(track_names)
        if name.endswith(ANIM_OVERRIDE_SUFFIX)
    )
    mapping_indices = []
    for mapping in build_jali_track_mappings():
        base_name = mapping["track_name"]
        index = track_map.get(f"{base_name}{LIPSYNC_POSE_SUFFIX}")
        if index is None:
            index = track_map.get(base_name)
        mapping_indices.append(index)
    return track_map, override_indices, tuple(mapping_indices)


class JALIToCp77Bridge:
    def __init__(self):
        self.mappings = build_jali_track_mappings()
        self.phoneme_overrides = get_phoneme_track_overrides()

    def _get_lipsync_track_name(self, base_name: str) -> str:
        return f'{base_name}{LIPSYNC_POSE_SUFFIX}'

    def _get_anim_override_track_name(self, base_name: str) -> str:
        return f'{base_name}{ANIM_OVERRIDE_SUFFIX}'

    def jali_to_tracks(self, ja_curve: np.ndarray, li_curve: np.ndarray, track_names: List[str]) -> np.ndarray:
        num_frames = len(ja_curve)
        num_tracks = len(track_names)
        names = tuple(track_names)
        track_map, override_indices, mapping_indices = _compile_track_layout(names)
        tracks = np.zeros((num_frames, num_tracks), dtype=np.float32)
        if override_indices:
            tracks[:, override_indices] = 1.0
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
        if IDX_MUZZLE_LIPS < num_tracks:
            tracks[:, IDX_MUZZLE_LIPS] = 1.0
        if IDX_MUZZLE_EYES < num_tracks:
            tracks[:, IDX_MUZZLE_EYES] = 1.0
        if IDX_MUZZLE_BROWS < num_tracks:
            tracks[:, IDX_MUZZLE_BROWS] = 0.41
        if IDX_UPPER_FACE < num_tracks:
            tracks[:, IDX_UPPER_FACE] = 0.25
        ja_clipped = np.clip(ja_curve, 0.0, 1.0)
        li_clipped = np.clip(li_curve, -1.0, 1.0)
        for mapping, track_idx in zip(self.mappings, mapping_indices):
            if track_idx is None:
                continue
            weight_func = mapping["weight_func"]
            weights = np.fromiter(
                (
                    float(weight_func(float(ja), float(li)))
                    for ja, li in zip(ja_clipped, li_clipped)
                ),
                dtype=np.float32,
                count=num_frames,
            )
            np.clip(weights, 0.0, 1.5, out=weights)
            np.maximum(tracks[:, track_idx], weights, out=tracks[:, track_idx])
        return tracks

    def add_phoneme_overrides(
        self,
        tracks: np.ndarray,
        phoneme_events: List,
        track_names: List[str],
        fps: float,
    ) -> np.ndarray:
        track_map = _compile_track_layout(tuple(track_names))[0]
        num_frames = tracks.shape[0]
        fade_seconds = 0.06
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
            fi = min(fade_frames, (n - 1) // 2)
            envelope = np.ones(n, dtype=np.float32)
            if fi > 0:
                ramp = np.sin(0.5 * np.pi * np.arange(fi, dtype=np.float32) / fi) ** 2
                envelope[:fi] = ramp
                envelope[-fi:] = ramp[::-1]
            for base_name, target_weight in overrides.items():
                if target_weight == 0.0:
                    override_name = self._get_anim_override_track_name(base_name)
                    idx = track_map.get(override_name)
                    if idx is None:
                        continue
                    suppression_curve = 1.0 - envelope
                    tracks[start_frame:end_frame, idx] = np.minimum(
                        tracks[start_frame:end_frame, idx],
                        suppression_curve,
                    )
                else:
                    lipsync_name = self._get_lipsync_track_name(base_name)
                    idx = track_map.get(lipsync_name)
                    if idx is None:
                        idx = track_map.get(base_name)
                        if idx is None:
                            continue
                    target_curve = envelope * target_weight
                    tracks[start_frame:end_frame, idx] = np.maximum(
                        tracks[start_frame:end_frame, idx],
                        target_curve,
                    )
        return tracks
