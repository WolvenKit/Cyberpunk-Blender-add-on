from __future__ import annotations

import numpy as np

from ...model.facial.constants import (
    ANIM_OVERRIDE_SUFFIX,
    LIPSYNC_ENVELOPE_TRACKS,
    LIPSYNC_POSE_SUFFIX,
)
from ...model.jali.phonemes import ARPABET_JALI_MAP
from ...model.jali.viseme_targets import VISEME_TARGETS, VISEME_TRACKS
from .curves import DominanceBlender
from .events import create_phoneme_event

_PREVIEW_FPS = 30.0
# A one-second preview event sampled at its midpoint frame.
_PREVIEW_SAMPLE = 15

_NAMED_POSES = {
    "NEUTRAL": (0.0, 0.0),
    "SMILE": (0.0, 1.0),
    "POUT": (0.0, -1.0),
    "JAW_OPEN": (1.0, 0.0),
}


def generated_track_columns(track_names, used_viseme_targets: bool) -> list[int]:
    """Indices of the tracks lipsync generation owns"""
    owned = []
    viseme_tracks = set(VISEME_TRACKS) if used_viseme_targets else set()
    for index, name in enumerate(str(n) for n in track_names):
        if (
            name.endswith(LIPSYNC_POSE_SUFFIX)
            or name.endswith(ANIM_OVERRIDE_SUFFIX)
            or name in LIPSYNC_ENVELOPE_TRACKS
            or name in viseme_tracks
        ):
            owned.append(index)
    return owned


def scale_pose_tracks(
    segments, track_names, tracks, jaw_multiplier: float, lip_multiplier: float
) -> None:
    """Scale jaw and lip pose tracks in place by the user multipliers"""
    pose_ranges = (
        range(segments.main_start, min(segments.main_end, tracks.shape[1])),
        range(
            segments.lipsync_out_start, min(segments.lipsync_out_end, tracks.shape[1])
        ),
    )
    for pose_range in pose_ranges:
        for index in pose_range:
            name = str(track_names[index])
            name = name.removesuffix(LIPSYNC_POSE_SUFFIX)
            lowered = name.lower()
            if "jaw" in lowered:
                tracks[:, index] *= jaw_multiplier
            elif "lips" in lowered or "mouth" in lowered:
                tracks[:, index] *= lip_multiplier


def jali_parameters(
    pose_type: str, custom_jaw: float, custom_lip: float
) -> tuple[float, float]:
    if pose_type == "CUSTOM":
        return custom_jaw, custom_lip
    if ARPABET_JALI_MAP and pose_type in ARPABET_JALI_MAP:
        value = ARPABET_JALI_MAP[pose_type]
        return value.jaw, value.lip
    return _NAMED_POSES.get(pose_type, (0.3, 0.0))


def preview_pose_tracks(
    bridge,
    segments,
    track_names,
    reference_tracks,
    num_tracks: int,
    *,
    pose_type: str,
    jaw: float,
    lip: float,
    intensity: float,
) -> np.ndarray:
    """Track values for a single preview pose"""
    if pose_type in VISEME_TARGETS:
        reference = np.asarray(reference_tracks, dtype=np.float32)
        target = bridge.viseme_tracks(
            [create_phoneme_event(pose_type, 0.0, 1.0)],
            1.0,
            DominanceBlender(fps=_PREVIEW_FPS),
            track_names,
            reference_tracks=reference,
        )[_PREVIEW_SAMPLE]
        return reference + (target - reference) * float(intensity)
    tracks = bridge.jali_to_tracks(
        np.asarray([jaw], dtype=np.float32),
        np.asarray([lip], dtype=np.float32),
        track_names,
        reference_tracks=reference_tracks,
    )[0]
    for index in range(
        segments.lipsync_ovr_start, min(segments.lipsync_ovr_end, num_tracks)
    ):
        tracks[index] = 1.0
    return tracks
