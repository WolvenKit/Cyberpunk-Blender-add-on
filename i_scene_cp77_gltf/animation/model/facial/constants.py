from __future__ import annotations

from enum import IntEnum

WEIGHT_THRESHOLD = 0.001


class Envelope(IntEnum):
    """Envelope track indices"""

    UPPER_FACE = 1
    LOWER_FACE = 2
    LIPSYNC = 4
    JALI_JAW = 7
    JALI_LIPS = 8
    MUZZLE_LIPS = 9
    MUZZLE_EYES = 10
    MUZZLE_BROWS = 11
    MUZZLE_EYE_DIR = 12


class Influence(IntEnum):
    """Corrective influence types"""

    LINEAR = 0
    EXPONENTIAL = 1
    ORGANIC = 2


LIPSYNC_POSE_SUFFIX = "LipsyncPoseOutput"
ANIM_OVERRIDE_SUFFIX = "AnimOverrideWeight"

# Envelope tracks that lipsync generation drives besides lipsync pose outputs and overrides.
LIPSYNC_ENVELOPE_TRACKS = frozenset(
    {"lipSyncEnvelope", "jaliJaw", "jaliLips", "muzzleLips"}
)
