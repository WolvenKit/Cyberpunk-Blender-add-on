from __future__ import annotations

import os
import struct

import numpy as np

from ..redSpace.contracts import MOCAP_SPACE_ICLONE
from .files import read_bytes
from .mocap import MocapClip, MocapFormatError, MocapSkeleton, MocapTrack

# The motion message opens with its header, whose first field is the authoring application's name.
_HEADER_MARKER = b"\x0a\x06iClone"
_BONE_SCHEMA = b"RLG5MotionBone"


def read_rlmotion(path: str) -> MocapClip:
    """An iClone .rlMotion file as a clip in iClone's units (cm) and axes"""
    label = os.path.basename(path)
    data = read_bytes(path)
    message = _motion_message(data, label)
    try:
        skeleton, clip_tracks = _skeleton_and_tracks(_message(message), label)
    except (IndexError, KeyError, UnicodeDecodeError, struct.error) as error:
        raise MocapFormatError(f"{label}: damaged iClone motion data") from error
    duration = max(
        (float(track.times[-1]) for track in clip_tracks if track is not None),
        default=0.0,
    )
    return MocapClip(
        name=os.path.splitext(label)[0],
        space=MOCAP_SPACE_ICLONE,
        skeleton=skeleton,
        tracks=clip_tracks,
        duration=duration,
    )


def _skeleton_and_tracks(fields, label):
    header = _message(fields[1][0])
    if header.get(4, [b""])[0] != _BONE_SCHEMA:
        raise MocapFormatError(f"{label}: not an iClone body motion")
    bones = [_message(bone) for bone in _message(fields[2][0]).get(1, [])]
    tracks = (
        [_message(track).get(1, []) for track in _message(fields[3][0]).get(1, [])]
        if 3 in fields
        else []
    )
    if not bones or len(tracks) != len(bones):
        raise MocapFormatError(
            f"{label}: {len(bones)} bones but {len(tracks)} motion tracks"
        )
    rest_rotations = np.array([_vector(bone, 5, 4) for bone in bones], dtype=np.float64)
    rest_translations = np.array(
        [_vector(bone, 6, 3) for bone in bones], dtype=np.float64
    )
    skeleton = MocapSkeleton(
        names=tuple(bone[1][0].decode("utf-8") for bone in bones),
        parents=tuple(_signed(bone.get(7, [-1])[0]) for bone in bones),
        rest_translations=rest_translations,
        rest_rotations=rest_rotations,
        end_offsets=(None,) * len(bones),
        hik_slots=tuple(_signed(bone.get(8, [-1])[0]) for bone in bones),
    )
    tracks = tuple(
        _track(keys, rest_rotations[index], rest_translations[index])
        for index, keys in enumerate(tracks)
    )
    return skeleton, tracks


def _motion_message(data, label):
    start = data.find(_HEADER_MARKER) - 2
    if start < 8:
        raise MocapFormatError(f"{label}: no iClone motion data")
    (length,) = struct.unpack_from("<I", data, start - 8)
    if start + length > len(data) or data[start] != 0x0A:
        raise MocapFormatError(f"{label}: damaged iClone motion data")
    return data[start : start + length]


def _track(keys, rest_rotation, rest_translation):
    if not keys:
        return None
    times = np.empty(len(keys), dtype=np.float64)
    rotations = np.empty((len(keys), 4), dtype=np.float64)
    translations = np.empty((len(keys), 3), dtype=np.float64)
    for index, key in enumerate(keys):
        fields = _message(key)
        times[index] = fields.get(1, [0])[0] / 1000.0
        rotations[index] = _vector(fields, 5, 4) if 5 in fields else rest_rotation
        translations[index] = _vector(fields, 6, 3) if 6 in fields else rest_translation
    return MocapTrack(times=times, rotations=rotations, translations=translations)


def _vector(fields, number, width):
    components = _message(fields[number][0])
    return tuple(components.get(component + 1, [0.0])[0] for component in range(width))


def _signed(value):
    return value - (1 << 64) if value >= 1 << 63 else value


def _varint(data, index):
    result = shift = 0
    while True:
        byte = data[index]
        index += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, index
        shift += 7


def _message(data):
    """Protobuf fields by number"""
    fields = {}
    index = 0
    end = len(data)
    while index < end:
        key, index = _varint(data, index)
        wire = key & 7
        if wire == 0:
            value, index = _varint(data, index)
        elif wire == 2:
            length, index = _varint(data, index)
            value = data[index : index + length]
            index += length
        elif wire == 5:
            (value,) = struct.unpack_from("<f", data, index)
            index += 4
        elif wire == 1:
            (value,) = struct.unpack_from("<d", data, index)
            index += 8
        else:
            raise struct.error(f"unsupported protobuf wire type {wire}")
        fields.setdefault(key >> 3, []).append(value)
    if index != end:
        raise struct.error("truncated protobuf message")
    return fields
