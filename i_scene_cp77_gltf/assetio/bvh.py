from __future__ import annotations

import os

import numpy as np

from ..bartmoss.quaternion import xyzw_from_axis_sequence
from ..redSpace.contracts import MOCAP_SPACE_BVH
from .files import read_bytes
from .mocap import MocapClip, MocapFormatError, MocapSkeleton, MocapTrack

_CHANNEL_KINDS = frozenset(
    f"{axis}{kind}" for axis in "XYZ" for kind in ("POSITION", "ROTATION")
)


def read_bvh(path: str) -> MocapClip:
    """A BVH motion capture file as a clip in the file's own units and axes"""
    lines = read_bytes(path).decode("latin-1").splitlines()
    label = os.path.basename(path)
    names, parents, offsets, end_offsets, channels, motion_line = _read_hierarchy(
        lines, label
    )
    frame_time, rows = _read_motion(
        lines, motion_line, sum(len(kinds) for kinds in channels), label
    )
    times = np.arange(len(rows), dtype=np.float64) * frame_time
    tracks = []
    column = 0
    for index, kinds in enumerate(channels):
        columns = range(column, column + len(kinds))
        column += len(kinds)
        rotation = [
            (kind[0], at)
            for kind, at in zip(kinds, columns)
            if kind.endswith("ROTATION")
        ]
        position = {
            kind[0]: at for kind, at in zip(kinds, columns) if kind.endswith("POSITION")
        }
        translations = None
        if parents[index] < 0 and position:
            translations = np.tile(offsets[index], (len(rows), 1))
            for axis, at in position.items():
                translations[:, "XYZ".index(axis)] = rows[:, at]
        if not rotation and translations is None:
            tracks.append(None)
            continue
        if rotation:
            angles = rows[:, [at for _axis, at in rotation]]
            rotations = xyzw_from_axis_sequence(
                angles, "".join(axis for axis, _at in rotation)
            )
        else:
            rotations = np.tile((0.0, 0.0, 0.0, 1.0), (len(rows), 1))
        tracks.append(
            MocapTrack(times=times, rotations=rotations, translations=translations)
        )
    skeleton = MocapSkeleton(
        names=tuple(names),
        parents=tuple(parents),
        rest_translations=np.asarray(offsets, dtype=np.float64),
        rest_rotations=np.tile((0.0, 0.0, 0.0, 1.0), (len(names), 1)),
        end_offsets=tuple(end_offsets),
    )
    return MocapClip(
        name=os.path.splitext(label)[0],
        space=MOCAP_SPACE_BVH,
        skeleton=skeleton,
        tracks=tuple(tracks),
        duration=float(times[-1]),
    )


def _floats(parts, count, label, line_number):
    try:
        values = tuple(float(value) for value in parts)
    except ValueError as error:
        raise MocapFormatError(
            f"{label}: unreadable number on line {line_number}"
        ) from error
    if len(values) != count:
        raise MocapFormatError(
            f"{label}: expected {count} values on line {line_number}, found {len(values)}"
        )
    return values


def _read_hierarchy(lines, label):
    names, parents, offsets, end_offsets, channels = [], [], [], [], []
    stack = []
    pending = None
    for line_number, line in enumerate(lines, start=1):
        parts = line.split()
        if not parts:
            continue
        key = parts[0].upper()
        if key == "HIERARCHY":
            continue
        if key == "MOTION":
            if stack or not names:
                raise MocapFormatError(
                    f"{label}: the hierarchy is incomplete before MOTION on line {line_number}"
                )
            return names, parents, offsets, end_offsets, channels, line_number
        if key in ("ROOT", "JOINT"):
            if key == "ROOT" and names:
                raise MocapFormatError(
                    f"{label}: a second ROOT on line {line_number}; one skeleton per file is supported"
                )
            if key == "JOINT" and not stack:
                raise MocapFormatError(
                    f"{label}: JOINT outside a ROOT on line {line_number}"
                )
            name = line.strip()[len(parts[0]) :].strip().rstrip("{").strip()
            if not name:
                raise MocapFormatError(
                    f"{label}: a joint without a name on line {line_number}"
                )
            parents.append(stack[-1][1] if stack else -1)
            names.append(name)
            offsets.append((0.0, 0.0, 0.0))
            end_offsets.append(None)
            channels.append(())
            pending = ("joint", len(names) - 1)
        elif key == "END":
            if not stack:
                raise MocapFormatError(
                    f"{label}: End Site outside a joint on line {line_number}"
                )
            pending = ("end", stack[-1][1])
        elif key == "OFFSET":
            if not stack:
                raise MocapFormatError(
                    f"{label}: OFFSET outside a joint on line {line_number}"
                )
            kind, index = stack[-1]
            value = _floats(parts[1:], 3, label, line_number)
            if kind == "end":
                end_offsets[index] = value
            else:
                offsets[index] = value
        elif key == "CHANNELS":
            if (
                not stack
                or stack[-1][0] != "joint"
                or len(parts) < 2
                or not parts[1].isdigit()
            ):
                raise MocapFormatError(
                    f"{label}: misplaced CHANNELS on line {line_number}"
                )
            kinds = tuple(kind.upper() for kind in parts[2:])
            if len(kinds) != int(parts[1]) or not set(kinds) <= _CHANNEL_KINDS:
                raise MocapFormatError(
                    f"{label}: unsupported CHANNELS on line {line_number}"
                )
            channels[stack[-1][1]] = kinds
        elif key not in ("{", "}"):
            raise MocapFormatError(
                f"{label}: unexpected {parts[0]!r} on line {line_number}"
            )
        if parts[-1] == "{":
            if pending is None:
                raise MocapFormatError(
                    f"{label}: unexpected '{{' on line {line_number}"
                )
            stack.append(pending)
            pending = None
        elif parts[-1] == "}":
            if not stack:
                raise MocapFormatError(f"{label}: unmatched '}}' on line {line_number}")
            stack.pop()
    raise MocapFormatError(f"{label}: no MOTION section")


def _header_value(lines, line_number, name, label):
    for offset, line in enumerate(lines[line_number:], start=line_number + 1):
        if not line.strip():
            continue
        key, _sep, value = line.partition(":")
        if " ".join(key.split()).casefold() != name.casefold():
            raise MocapFormatError(f"{label}: expected '{name}:' on line {offset}")
        return value.strip(), offset
    raise MocapFormatError(f"{label}: the MOTION section has no '{name}:' line")


def _read_motion(lines, motion_line, channel_count, label):
    text, frames_line = _header_value(lines, motion_line, "Frames", label)
    try:
        frame_count = int(text)
    except ValueError as error:
        raise MocapFormatError(
            f"{label}: unreadable frame count on line {frames_line}"
        ) from error
    text, time_line = _header_value(lines, frames_line, "Frame Time", label)
    try:
        frame_time = float(text)
    except ValueError as error:
        raise MocapFormatError(
            f"{label}: unreadable frame time on line {time_line}"
        ) from error
    if frame_count < 1 or frame_time <= 0.0:
        raise MocapFormatError(f"{label}: the file holds no frames")
    rows = [
        _floats(line.split(), channel_count, label, line_number)
        for line_number, line in enumerate(lines[time_line:], start=time_line + 1)
        if line.strip()
    ]
    if len(rows) != frame_count:
        raise MocapFormatError(
            f"{label}: the header promises {frame_count} frames but the file holds {len(rows)}"
        )
    return frame_time, np.asarray(rows, dtype=np.float64).reshape(
        frame_count, channel_count
    )
