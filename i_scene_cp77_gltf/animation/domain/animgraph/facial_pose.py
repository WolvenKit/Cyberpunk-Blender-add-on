from __future__ import annotations

import math

from ....bartmoss.qs_transform import QsTransform, relative_to
from ....bartmoss.scalar import clamp_scalar
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import model_transform
from .topology import has_link


def evaluate_eyes_tracks(pose, tracks, data):
    bone = str(data.get("eyeTransform", ""))
    if bone not in pose:
        return PoseOpEvaluation((), (), False, "eye transform is absent from the pose")
    x, y, z, w = pose[bone].rotation_xyzw
    unit = x * x + y * y + z * z + w * w
    if unit <= 1e-15:
        raise ValueError("EyesTracksLookAt requires a nonzero eye rotation")
    norm = math.sqrt(unit)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    abcd = w * x + y * z
    if abcd > 0.499:
        yaw, pitch = 2 * math.atan2(y, w), math.pi / 2
    elif abcd < -0.499:
        yaw, pitch = -2 * math.atan2(y, w), -math.pi / 2
    else:
        yaw = math.atan2(2 * (w * z - x * y), 1 - 2 * (z * z + x * x))
        pitch = math.asin(clamp_scalar(2 * abcd, -1, 1))
    horizontal = clamp_scalar(pitch / math.radians(40), -1, 1)
    vertical = clamp_scalar(yaw / math.radians(21), 0, 1) + clamp_scalar(
        yaw / math.radians(30), -1, 0
    )
    written = []
    for positive, negative, value in (
        ("leftTrack", "rightTrack", horizontal),
        ("upTrack", "downTrack", vertical),
    ):
        pos, neg = str(data.get(positive, "")), str(data.get(negative, ""))
        if pos not in tracks or neg not in tracks:
            continue
        value += tracks[pos] - tracks[neg]
        tracks[pos], tracks[neg] = clamp_scalar(value, 0, 1), clamp_scalar(-value, 0, 1)
        written.extend((pos, neg))
    return PoseOpEvaluation((), tuple(written))


def remap_track_range(value, minimum, maximum, old_minimum, old_maximum):
    if old_maximum == old_minimum:
        raise ValueError("SetTrackRange cannot remap an empty input range")
    result = minimum + (value - old_minimum) / (old_maximum - old_minimum) * (
        maximum - minimum
    )
    return clamp_scalar(result, minimum, maximum)


def evaluate_set_bone_position(pose, parent_map, bone, position, *, model_space=False):
    if bone not in pose:
        return PoseOpEvaluation((), (), False, "target is absent from the pose")
    parent = parent_map.get(bone)
    if parent and not model_space:
        parent_transform = model_transform(parent, pose, parent_map)
        position = relative_to(
            parent_transform,
            QsTransform.from_components(position, (0, 0, 0, 1), (1, 1, 1)),
        ).translation
    current = pose[bone]
    pose[bone] = QsTransform.from_components(
        position, current.rotation_xyzw, current.scale
    )
    return PoseOpEvaluation((bone,))


def sermo_data(node_type, node):
    return {"facialSolver": True}


def eyes_tracks_look_at_data(node_type, node):
    return {
        "eyeTransform": index_name(
            node.get("eyeTransform"), "animTransformIndex", allow_text=True
        ),
        **{
            key: index_name(node.get(key), "animNamedTrackIndex", allow_text=True)
            for key in ("leftTrack", "rightTrack", "upTrack", "downTrack")
        },
    }


def set_track_range_data(node_type, node):
    return {
        "track": index_name(node.get("track"), "animNamedTrackIndex", allow_text=True),
        **{
            key: float(node.get(key, default))
            for key, default in (("min", 0), ("max", 1), ("oldMin", 0), ("oldMax", 1))
        },
    }


def set_bone_position_data(node_type, node):
    return {
        "bone": index_name(node.get("bone"), "animTransformIndex", allow_text=True),
        "hasPosition": has_link(node, "positionMs"),
    }
