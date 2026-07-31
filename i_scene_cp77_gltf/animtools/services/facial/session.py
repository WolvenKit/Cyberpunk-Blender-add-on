from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

import bpy
import numpy as np
from bpy.app.handlers import persistent

from ....animation.binding import ActionBinding, resolve_action_binding
from ....animation.facial.model import TrackSegments
from ....animation.facial.runtime import CompiledFacialRuntime, compile_runtime
from ....animation.rig_binding import is_read_rig_armature, resolve_pose_bone
from ....animation.tracks import ensure_rig_track_properties
from ....animation.facial.repository import FacialRepository
from ....assetio.documents import DocumentSession

DRIVER_NS_KEY = "cp77_facial_sessions"
PROP_BOUND = "_cp77_bound"
PROP_SETUP_PATH = "_cp77_setup_path"
PROP_RIG_PATH = "_cp77_rig_path"


@dataclass
class FacialSession:
    armature: object
    setup: object
    rig: object
    track_segments: TrackSegments
    setup_path: str
    rig_path: str
    used_bone_names: tuple[str, ...]
    track_names: tuple[str, ...]
    track_defaults: np.ndarray
    pose_bones: tuple
    used_bone_indices: np.ndarray
    used_pose_bones: tuple
    used_pose_bone_map: dict[str, object]
    bind_time: float
    armature_pointer: int
    action_binding: Optional[ActionBinding] = None
    action_pointer: int = 0
    action_signature: tuple = ()
    source_revision: tuple = ()
    compiled_runtime: Optional[CompiledFacialRuntime] = None
    preview_snapshot: dict = field(default_factory=dict)
    active_pose: Optional[tuple[str, int]] = None

    @property
    def has_preview(self) -> bool:
        return bool(self.preview_snapshot)


def _registry() -> dict:
    namespace = bpy.app.driver_namespace
    registry = namespace.get(DRIVER_NS_KEY)
    if not isinstance(registry, dict):
        registry = {}
        namespace[DRIVER_NS_KEY] = registry
    return registry


def _resolve_armature(value):
    if value is None:
        return None
    if isinstance(value, str):
        return bpy.data.objects.get(value)
    return value


def _pointer(value) -> int:
    try:
        return int(value.as_pointer())
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return 0


def _file_signature(path: str) -> tuple:
    try:
        stat = os.stat(path)
    except OSError:
        return (path, 0, 0)
    return (path, int(stat.st_mtime_ns), int(stat.st_size))


def _topology_signature(obj) -> tuple:
    bones = getattr(getattr(obj, "data", None), "bones", ())
    return tuple((bone.name, bone.parent.name if bone.parent else "") for bone in bones)


def _action_signature(action, binding: ActionBinding) -> tuple:
    return (_pointer(action), binding.tracks.names)


def _session_is_live(session: FacialSession) -> bool:
    obj = session.armature
    try:
        return (
            obj is not None
            and obj.type == "ARMATURE"
            and _pointer(obj) == session.armature_pointer
            and bpy.data.objects.get(obj.name) is obj
        )
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False


def invalidate_session(session: FacialSession) -> None:
    session.compiled_runtime = None


def refresh_action_binding(session: FacialSession, force: bool = False) -> bool:
    animation_data = getattr(session.armature, "animation_data", None)
    action = getattr(animation_data, "action", None)
    action_pointer = _pointer(action)
    if not force and action_pointer == session.action_pointer:
        return False
    binding = resolve_action_binding(action, session.armature)
    signature = _action_signature(action, binding)
    changed = signature != session.action_signature or binding != session.action_binding
    session.action_binding = binding
    session.action_pointer = signature[0]
    session.action_signature = signature
    return changed


def refresh_session(session: FacialSession, check_sources: bool = False) -> bool:
    changed = refresh_action_binding(session, force=check_sources)
    if not check_sources:
        return changed
    source_revision = (
        _file_signature(session.setup_path),
        _file_signature(session.rig_path),
        _topology_signature(session.armature),
    )
    if source_revision != session.source_revision:
        session.source_revision = source_revision
        session.pose_bones = tuple(
            resolve_pose_bone(session.armature, str(name))
            for name in session.rig.bone_names
        )
        session.used_pose_bones = tuple(
            session.pose_bones[int(index)]
            for index in session.used_bone_indices
        )
        session.used_pose_bone_map = dict(zip(
            session.used_bone_names,
            session.used_pose_bones,
        ))
        invalidate_session(session)
        changed = True
    return changed


def get_session(armature) -> Optional[FacialSession]:
    obj = _resolve_armature(armature)
    pointer = _pointer(obj)
    if not pointer:
        return None
    session = _registry().get(pointer)
    if not isinstance(session, FacialSession) or not _session_is_live(session):
        _registry().pop(pointer, None)
        return None
    refresh_action_binding(session)
    return session


def ensure_context_session(context):
    obj = getattr(context, "active_object", None)
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        return None
    session = ensure_session(obj)
    if session is not None:
        return session
    props = getattr(getattr(context, "scene", None), "cp77_facial", None)
    if props is None or not props.rig_json or not props.facial_json:
        return None
    try:
        from ....assetio.resolver import resolve_asset_path
        rig_path = resolve_asset_path(
            bpy.path.abspath(props.rig_json),
            extensions=(".rig.json",),
            warn=False,
        )
        setup_path = resolve_asset_path(
            bpy.path.abspath(props.facial_json),
            extensions=(".facialsetup.json",),
            warn=False,
        )
        if not rig_path or not setup_path:
            return None
        return bind_session(obj, setup_path, rig_path)[0]
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None

def iter_sessions():
    registry = _registry()
    for pointer, session in list(registry.items()):
        if not isinstance(session, FacialSession) or not _session_is_live(session):
            registry.pop(pointer, None)
            continue
        refresh_action_binding(session)
        yield session


def is_bound(obj) -> bool:
    return bool(obj and obj.get(PROP_BOUND, False))


def build_used_bone_names(setup, rig) -> tuple[str, ...]:
    return tuple(str(rig.bone_names[index]) for index in setup.used_bone_indices)


def validate_bones(obj, bone_names) -> list[str]:
    return [name for name in bone_names if resolve_pose_bone(obj, name) is None]


def _persist_session(session: FacialSession) -> None:
    obj = session.armature
    obj[PROP_BOUND] = True
    obj[PROP_SETUP_PATH] = session.setup_path
    obj[PROP_RIG_PATH] = session.rig_path


def stored_paths(obj) -> tuple[Optional[str], Optional[str]]:
    return obj.get(PROP_SETUP_PATH), obj.get(PROP_RIG_PATH)


def bind_session(obj, setup_path: str, rig_path: str, *, rig=None, setup=None):
    if obj is None or getattr(obj, "type", None) != "ARMATURE":
        raise ValueError("A facial session requires an armature")
    setup_path = bpy.path.abspath(setup_path)
    rig_path = bpy.path.abspath(rig_path)
    if rig is None or setup is None:
        with DocumentSession() as documents:
            resource = FacialRepository(documents).load(
                setup_path,
                rig_path,
                required=True,
            )
        if rig is None:
            rig = resource.rig
        if setup is None:
            setup = resource.setup
    segments = TrackSegments.from_setup(setup, rig.num_tracks)
    used_bone_names = build_used_bone_names(setup, rig)
    ensure_rig_track_properties(obj, rig, segments)
    used_bone_indices = np.ascontiguousarray(setup.used_bone_indices, dtype=np.intp)
    pose_bones = tuple(resolve_pose_bone(obj, str(name)) for name in rig.bone_names)
    track_defaults = np.zeros(rig.num_tracks, dtype=np.float32)
    reference_tracks = np.asarray(getattr(rig, "reference_tracks", ()) or (), dtype=np.float32)
    track_defaults[:min(len(reference_tracks), rig.num_tracks)] = reference_tracks[:rig.num_tracks]
    session = FacialSession(
        armature=obj,
        setup=setup,
        rig=rig,
        track_segments=segments,
        setup_path=setup_path,
        rig_path=rig_path,
        used_bone_names=used_bone_names,
        track_names=tuple(str(name) for name in rig.track_names),
        track_defaults=track_defaults,
        pose_bones=pose_bones,
        used_bone_indices=used_bone_indices,
        used_pose_bones=tuple(pose_bones[int(index)] for index in used_bone_indices),
        used_pose_bone_map=dict(zip(
            used_bone_names,
            (pose_bones[int(index)] for index in used_bone_indices),
        )),
        bind_time=time.time(),
        armature_pointer=_pointer(obj),
        source_revision=(
            _file_signature(setup_path),
            _file_signature(rig_path),
            _topology_signature(obj),
        ),
    )
    refresh_action_binding(session, force=True)
    _registry()[session.armature_pointer] = session
    _persist_session(session)
    return session, validate_bones(obj, used_bone_names)


def restore_session(obj) -> Optional[FacialSession]:
    if not is_bound(obj):
        return None
    setup_path, rig_path = stored_paths(obj)
    if not setup_path or not rig_path:
        return None
    if not os.path.isfile(setup_path) or not os.path.isfile(rig_path):
        return None
    try:
        return bind_session(obj, setup_path, rig_path)[0]
    except Exception as error:
        print(f"[CP77 Facial] Session restore failed for '{obj.name}': {error}")
        return None


def ensure_session(obj, setup_path: str = "", rig_path: str = "") -> Optional[FacialSession]:
    session = get_session(obj)
    if session is not None:
        return session
    session = restore_session(obj)
    if session is not None:
        return session
    if setup_path and rig_path:
        return bind_session(obj, setup_path, rig_path)[0]
    return None


def remove_session(obj, keep_properties: bool = False) -> None:
    session = get_session(obj)
    if session is not None and not keep_properties and not is_read_rig_armature(obj):
        for name in session.track_names:
            if name in obj:
                del obj[name]
    for key in (PROP_BOUND, PROP_SETUP_PATH, PROP_RIG_PATH):
        if key in obj:
            del obj[key]
    pointer = _pointer(obj)
    if pointer:
        _registry().pop(pointer, None)


def get_compiled_runtime(session: FacialSession) -> CompiledFacialRuntime:
    runtime = session.compiled_runtime
    if runtime is None:
        runtime = compile_runtime(session.setup, session.rig, session.track_segments)
        session.compiled_runtime = runtime
    return runtime


def read_tracks_into(session: FacialSession, values: np.ndarray) -> np.ndarray:
    np.copyto(values, session.track_defaults)
    for index, name in enumerate(session.track_names):
        values[index] = float(session.armature.get(name, session.track_defaults[index]))
    return values


def write_output_tracks(session: FacialSession, values, indices) -> int:
    written = 0
    limit = min(len(session.track_names), len(values))
    for index in indices:
        index = int(index)
        if index >= limit:
            continue
        name = session.track_names[index]
        value = float(values[index])
        if name in session.armature and float(session.armature[name]) == value:
            continue
        session.armature[name] = value
        written += 1
    return written


def pose_count(session: FacialSession, part_name: str) -> int:
    part = getattr(session.setup, part_name, None)
    return int(part.num_main_poses) if part is not None else 0


def pose_track_name(session: FacialSession, part_name: str, pose_index: int) -> str:
    part = getattr(session.setup, part_name, None)
    if part is None or pose_index < 0 or pose_index >= part.num_main_poses:
        return ""
    track_index = int(part.main_tracks[pose_index])
    return session.track_names[track_index] if track_index < len(session.track_names) else ""


@persistent
def clear_sessions_before_load(_):
    clear_registry()


def register() -> None:
    handlers = bpy.app.handlers.load_pre
    if clear_sessions_before_load not in handlers:
        handlers.append(clear_sessions_before_load)
    clear_registry()


def unregister() -> None:
    handlers = bpy.app.handlers.load_pre
    while clear_sessions_before_load in handlers:
        handlers.remove(clear_sessions_before_load)
    clear_registry()


def clear_registry() -> None:
    _registry().clear()
