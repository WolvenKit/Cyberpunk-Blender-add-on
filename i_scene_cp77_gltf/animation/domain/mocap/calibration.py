from __future__ import annotations

import dataclasses
import math

import numpy as np

from ....assetio.mocap import MocapClip, MocapTrack
from ....bartmoss.quaternion import angle_between_xyzw

# A calibration pose at frame 0 turns some joint further than this on the way to frame 1, and more than twice as far
# as any joint turns from frame 1 to frame 2.
_CALIBRATION_STEP = math.radians(45.0)
_CALIBRATION_RATIO = 2.0


def _shared_times(clip):
    tracks = [track for track in clip.tracks if track is not None]
    if not tracks or len(tracks[0].times) < 3:
        return None
    times = tracks[0].times
    if any(not np.array_equal(track.times, times) for track in tracks[1:]):
        return None
    return times


def has_calibration_frame(clip: MocapClip) -> bool:
    """True when frame 0 holds a calibration pose the motion jumps away from at frame 1"""
    if _shared_times(clip) is None:
        return False
    joints = [
        track.rotations[:3]
        for track, parent in zip(clip.tracks, clip.skeleton.parents)
        if track is not None and parent >= 0
    ]
    if not joints:
        return False
    rotations = np.stack(joints)
    first = float(np.max(angle_between_xyzw(rotations[:, 0], rotations[:, 1])))
    second = float(np.max(angle_between_xyzw(rotations[:, 1], rotations[:, 2])))
    return first > _CALIBRATION_STEP and first > _CALIBRATION_RATIO * second


def without_first_frame(clip: MocapClip) -> MocapClip:
    """The clip from its second frame on, re-timed to start at zero"""
    times = _shared_times(clip)
    if times is None:
        raise ValueError(
            f"{clip.name}: only clips sampled on one frame grid can drop their first frame"
        )
    tracks = tuple(
        None
        if track is None
        else MocapTrack(
            times=track.times[1:] - track.times[1],
            rotations=track.rotations[1:],
            translations=None if track.translations is None else track.translations[1:],
        )
        for track in clip.tracks
    )
    return dataclasses.replace(
        clip, tracks=tracks, duration=clip.duration - float(times[1] - times[0])
    )


def without_calibration_frame(clip: MocapClip) -> tuple[MocapClip, bool]:
    """The clip without a calibration first frame, and whether it had one"""
    if not has_calibration_frame(clip):
        return clip, False
    return without_first_frame(clip), True
