from __future__ import annotations

import time

import bpy
from bpy.app.handlers import persistent

from ....animation.blender_pose import apply_bound_red_local_deltas
from ....animation.facial.solver import solve_runtime
from . import session as facial_session

_solving = False


def _get_lod(scene) -> int:
    props = getattr(scene, "cp77_facial", None)
    if props is None:
        return 0
    return max(0, min(2, int(getattr(props, "lod_level", 0))))


def _apply_result(session, runtime, bone_quats, bone_trans, output_tracks):
    written_bones = apply_bound_red_local_deltas(
        session.armature,
        session.used_pose_bones,
        session.used_bone_indices,
        bone_quats,
        bone_trans,
    )
    written_tracks = facial_session.write_output_tracks(
        session,
        output_tracks,
        runtime.output_indices,
    )
    return written_bones, written_tracks


def solve_tracks(session, input_tracks, lod: int = 0, lod_weight: float = 0.0):
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


def solve_session(session, lod: int = 0, lod_weight: float = 0.0):
    runtime = facial_session.get_compiled_runtime(session)
    facial_session.read_tracks_into(session, runtime.input_tracks)
    return solve_tracks(session, runtime.input_tracks, lod=lod, lod_weight=lod_weight)


@persistent
def solve_frame(scene, depsgraph=None):
    global _solving
    if _solving:
        return
    _solving = True
    try:
        timing = {}
        lod = _get_lod(scene)
        for session in facial_session.iter_sessions():
            if not facial_session.is_bound(session.armature):
                continue
            start = time.perf_counter()
            solve_session(session, lod=lod)
            timing[session.armature.name] = (time.perf_counter() - start) * 1000.0
        bpy.app.driver_namespace["cp77_facial_last_ms"] = timing
    except Exception as error:
        import traceback
        print(f"[CP77 Facial] Solver error: {error}")
        traceback.print_exc()
    finally:
        _solving = False


def is_solver_active() -> bool:
    return solve_frame in bpy.app.handlers.frame_change_post


def enable_solver(context) -> None:
    if not is_solver_active():
        bpy.app.handlers.frame_change_post.append(solve_frame)
    props = getattr(context.scene, "cp77_facial", None)
    if props is not None:
        props.solver_active = True


def disable_solver(context) -> None:
    handlers = bpy.app.handlers.frame_change_post
    while solve_frame in handlers:
        handlers.remove(solve_frame)
    props = getattr(context.scene, "cp77_facial", None)
    if props is not None:
        props.solver_active = False


@persistent
def reset_solver_after_load(_=None) -> None:
    disable_solver_global()
    scene = getattr(bpy.context, "scene", None)
    props = getattr(scene, "cp77_facial", None) if scene is not None else None
    if props is not None:
        props.solver_active = False


def register_handlers() -> None:
    handlers = bpy.app.handlers.load_post
    if reset_solver_after_load not in handlers:
        handlers.append(reset_solver_after_load)
    disable_solver_global()


def unregister_handlers() -> None:
    handlers = bpy.app.handlers.load_post
    while reset_solver_after_load in handlers:
        handlers.remove(reset_solver_after_load)
    disable_solver_global()


def disable_solver_global() -> None:
    handlers = bpy.app.handlers.frame_change_post
    while solve_frame in handlers:
        handlers.remove(solve_frame)
