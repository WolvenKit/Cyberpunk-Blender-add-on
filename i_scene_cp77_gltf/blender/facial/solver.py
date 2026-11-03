from __future__ import annotations

from ...animation.domain.facial.solver import solve_runtime
from ..pose import apply_bound_red_local_deltas
from . import session as facial_session


def _apply_result(session, runtime, bone_quats, bone_trans, output_tracks):
    written_bones = apply_bound_red_local_deltas(
        session.armature,
        session.used_pose_bones,
        session.used_bone_indices,
        bone_quats,
        bone_trans,
        session.used_pose_collection_indices,
    )
    written_tracks = facial_session.write_output_tracks(
        session,
        output_tracks,
        runtime.output_indices,
    )
    return written_bones, written_tracks


def solve_tracks(
    session, input_tracks, lod: int = 0, lod_weight: float = 0.0, runtime=None
):
    if runtime is None:
        runtime = facial_session.get_compiled_runtime(session)
    bone_quats, bone_trans, output_tracks = solve_runtime(
        runtime,
        input_tracks=input_tracks,
        lod=lod,
        lod_weight=lod_weight,
    )
    written_bones, written_tracks = _apply_result(
        session,
        runtime,
        bone_quats,
        bone_trans,
        output_tracks,
    )
    return bone_quats, bone_trans, output_tracks, written_bones, written_tracks


def solve_session(
    session, lod: int = 0, lod_weight: float = 0.0, *, additive_composed: bool = False
):
    """Solve the facial rig from the armature's current track values"""
    runtime = facial_session.get_compiled_runtime(session)
    facial_session.read_tracks_into(
        session, runtime.input_tracks, additive_composed=additive_composed
    )
    return solve_tracks(
        session, runtime.input_tracks, lod=lod, lod_weight=lod_weight, runtime=runtime
    )
