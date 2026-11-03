from __future__ import annotations

from dataclasses import dataclass

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import multiply_unit_scalar_xyzw
from .solver import solve_runtime


@dataclass(frozen=True)
class FacialGraphBinding:
    runtime: object
    bone_names: tuple[str, ...]
    reference_pose: tuple[QsTransform, ...]
    track_names: tuple[str, ...]
    track_defaults: tuple[float, ...]
    used_bone_indices: tuple[int, ...]


def evaluate_facial_graph(binding, pose, tracks, *, lod=0, lod_weight=0.0):
    """Evaluate the bound facial solver without writing a Blender pose"""
    runtime = binding.runtime
    for index, name in enumerate(binding.track_names):
        runtime.input_tracks[index] = tracks.get(name, binding.track_defaults[index])
    rotations, translations, solved_tracks = solve_runtime(
        runtime,
        input_tracks=runtime.input_tracks,
        lod=lod,
        lod_weight=lod_weight,
    )
    result_pose = dict(pose)
    used = frozenset(binding.used_bone_indices)
    last_used = max(used, default=-1)
    for index, name in enumerate(binding.bone_names):
        if not name or name not in pose:
            continue
        reference = binding.reference_pose[index]
        if index in used:
            result_pose[name] = QsTransform.from_components(
                tuple(
                    reference.translation[axis] + float(translations[index, axis])
                    for axis in range(3)
                ),
                multiply_unit_scalar_xyzw(reference.rotation_xyzw, rotations[index]),
                reference.scale,
            )
        elif index > last_used:
            result_pose[name] = reference
    result_tracks = dict(tracks)
    for index, name in enumerate(binding.track_names):
        result_tracks[name] = float(solved_tracks[index])
    return result_pose, result_tracks
