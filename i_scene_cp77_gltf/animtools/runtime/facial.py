from __future__ import annotations

import time
from contextlib import contextmanager

from ...blender.facial import session as facial_session
from ...blender.facial.graph import graph_preview_owns_session
from ...blender.facial.resources import clear_resource_cache
from ...blender.facial.solver import solve_session
from ...core.log import TRACE, get_logger, log_on_change

_LOG = get_logger(__name__)

_solving = False
_last_timing: dict[str, float] = {}


def _get_lod(scene) -> int:
    props = getattr(scene, "cp77_facial", None)
    if props is None:
        return 0
    return max(0, min(2, int(getattr(props, "lod_level", 0))))


@contextmanager
def frame_solver_suspended():
    """Skip the frame-change solve while a caller solves each frame itself (e.g. baking)"""
    global _solving
    previous = _solving
    _solving = True
    try:
        yield
    finally:
        _solving = previous


def solve_frame(scene, *, additive_armature=None) -> None:
    """Solve every bound facial rig for the scene's current frame while the Face toggle is on"""
    global _solving
    if _solving:
        return
    facial_props = getattr(scene, "cp77_facial", None)
    if facial_props is None or not bool(getattr(facial_props, "solver_active", False)):
        return
    _solving = True
    try:
        timing = {}
        lod = _get_lod(scene)
        for session in facial_session.iter_sessions():
            if graph_preview_owns_session(session) or not facial_session.is_bound(
                session.armature
            ):
                continue
            start = time.perf_counter()
            try:
                solve_session(
                    session,
                    lod=lod,
                    additive_composed=session.armature == additive_armature,
                )
                # A success ends the run of failures, so the next failure logs again.
                log_on_change(
                    _LOG,
                    TRACE,
                    session.armature.name,
                    "Facial solve succeeded for %s",
                    session.armature.name,
                )
                timing[session.armature.name] = (time.perf_counter() - start) * 1000.0
            except (
                KeyError,
                IndexError,
                RuntimeError,
                ReferenceError,
                TypeError,
                ValueError,
            ) as error:
                log_on_change(
                    _LOG,
                    "ERROR",
                    session.armature.name,
                    "Facial solve failed for %s: %s: %s",
                    session.armature.name,
                    type(error).__name__,
                    error,
                    exc_info=True,
                )
        _last_timing.clear()
        _last_timing.update(timing)
    except Exception as error:
        _LOG.exception("Facial solver failed: %s", error)
    finally:
        _solving = False


def last_solve_timing() -> dict[str, float]:
    return dict(_last_timing)


def reset_after_load(scene) -> None:
    _last_timing.clear()
    props = getattr(scene, "cp77_facial", None) if scene is not None else None
    if props is not None:
        props.solver_active = False


def clear_sessions() -> None:
    facial_session.clear_registry()


def restore_sessions() -> None:
    facial_session.restore_bound_sessions()


def clear_resources() -> None:
    clear_resource_cache()
