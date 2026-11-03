from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import bpy
import numpy as np

from ...animation.domain.facial.compiled import CompiledFacialRuntime, compile_runtime
from ...animation.domain.facial.validation import validate_setup
from ...animation.model.clip.binding import ActionBinding, track_property_path
from ...animation.model.facial.setup import TrackSegments
from ...animation.services.facial.repository import FacialRepository
from ...assetio.documents import DocumentSession, file_identity
from ...core.log import get_logger, log_once
from ..action_metadata import action_is_additive, resolve_action_binding
from ..animation_context import track_id_properties
from ..armature_bones import is_read_rig_armature, resolve_pose_bone
from ..keyframes import get_action_fcurves
from ..pose import pose_bone_collection_indices
from ..tracks import ensure_rig_track_properties
from ..transactions import track_mutation
from .resources import discover_setup_paths, load_resource, resolve_resource

_LOG = get_logger(__name__)

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
    data_pointer: int = 0
    bone_count: int = 0
    assembly_revision: str = ""
    action_binding: ActionBinding | None = None
    action_pointer: int = 0
    action_signature: tuple = ()
    source_revision: tuple = ()
    compiled_runtime: CompiledFacialRuntime | None = None
    graph_preview_runtime: object | None = None
    preview_snapshot: dict = field(default_factory=dict)
    active_pose: tuple[str, int] | None = None
    # Index of each used pose bone in armature.pose.bones, for bulk pose writes.
    used_pose_collection_indices: np.ndarray | None = None
    # Tracks keyed by the active action when it is additive (values are deltas over the
    # rig reference); None when the action is not additive.
    additive_track_mask: np.ndarray | None = None
    # The curve paths of the additive action the mask was built from: the same action can gain or lose curves.
    additive_keyed_paths: frozenset | None = None

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
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_pointer", type(error).__name__),
            "pointer: fell back after %s",
            error,
            exc_info=True,
        )
        return 0


def _file_signature(path: str) -> tuple:
    identity = file_identity(path)
    return (path, identity.mtime_ns, identity.size)


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
            and _pointer(obj.data) == session.data_pointer
            and len(obj.data.bones) == session.bone_count
            and str(obj.get("cp77_metarig_definition_hash", ""))
            == session.assembly_revision
        )
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_session_is_live", type(error).__name__),
            "session is live: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def refresh_action_binding(session: FacialSession, force: bool = False) -> bool:
    animation_data = getattr(session.armature, "animation_data", None)
    action = getattr(animation_data, "action", None)
    action_pointer = _pointer(action)
    if not force and action_pointer == session.action_pointer:
        _refresh_additive_track_mask(session, action)
        return False
    binding = resolve_action_binding(action, session.armature)
    signature = _action_signature(action, binding)
    changed = signature != session.action_signature or binding != session.action_binding
    session.action_binding = binding
    session.action_pointer = signature[0]
    session.action_signature = signature
    session.additive_keyed_paths = None
    _refresh_additive_track_mask(session, action)
    return changed


def _additive_keyed_paths(session: FacialSession, action) -> frozenset | None:
    if action is None or not action_is_additive(action):
        return None
    fcurves = get_action_fcurves(action, session.armature)
    if fcurves is None:
        return None
    return frozenset(curve.data_path for curve in fcurves)


def _refresh_additive_track_mask(session: FacialSession, action) -> None:
    """Rebuild the additive mask when the tracks the action keys are not the ones it was built from"""
    keyed = _additive_keyed_paths(session, action)
    if (
        keyed is not None
        and keyed == session.additive_keyed_paths
        and session.additive_track_mask is not None
    ):
        return
    session.additive_keyed_paths = keyed
    session.additive_track_mask = (
        None
        if keyed is None
        else np.fromiter(
            (track_property_path(name) in keyed for name in session.track_names),
            dtype=bool,
            count=len(session.track_names),
        )
    )


def refresh_session(session: FacialSession, check_sources: bool = False) -> bool:
    changed = refresh_action_binding(session, force=check_sources)
    if not check_sources:
        return changed
    source_revision = (
        _file_signature(session.setup_path),
        _file_signature(session.rig_path),
        _topology_signature(session.armature),
    )
    if source_revision != session.source_revision or not _session_is_live(session):
        # Reparse changed resources; changing the signature alone leaves stale indices.
        resource = load_resource(session.armature, session.setup_path)
        rebound, _ = bind_session(
            session.armature,
            resource.setup_path,
            resource.rig_path,
            rig=resource.rig,
            setup=resource.setup,
        )
        session.__dict__.update(rebound.__dict__)
        _registry()[session.armature_pointer] = session
        changed = True
    return changed


def peek_session(armature) -> FacialSession | None:
    """The live session bound to armature, without refreshing it"""
    obj = _resolve_armature(armature)
    pointer = _pointer(obj)
    if not pointer:
        return None
    session = _registry().get(pointer)
    if not isinstance(session, FacialSession) or not _session_is_live(session):
        return None
    return session


def get_session(armature) -> FacialSession | None:
    obj = _resolve_armature(armature)
    pointer = _pointer(obj)
    if not pointer:
        return None
    session = _registry().get(pointer)
    if not isinstance(session, FacialSession):
        _registry().pop(pointer, None)
        return None
    if not _session_is_live(session):
        return None
    refresh_action_binding(session)
    return session


def iter_sessions():
    registry = _registry()
    for pointer, session in list(registry.items()):
        if not isinstance(session, FacialSession) or not _session_is_live(session):
            registry.pop(pointer, None)
            obj = _resolve_armature(getattr(session, "armature", None))
            session = restore_session(obj) if obj is not None else None
            if session is None:
                continue
        refresh_action_binding(session)
        yield session


def is_bound(obj) -> bool:
    try:
        return bool(obj and obj.get(PROP_BOUND, False))
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("is_bound", type(error).__name__),
            "is bound: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def build_used_bone_names(setup, rig) -> tuple[str, ...]:
    return tuple(str(rig.bone_names[index]) for index in setup.used_bone_indices)


def validate_bones(obj, bone_names) -> list[str]:
    return [name for name in bone_names if resolve_pose_bone(obj, name) is None]


def _persist_session(session: FacialSession) -> None:
    obj = session.armature
    obj[PROP_BOUND] = True
    obj[PROP_SETUP_PATH] = session.setup_path
    obj[PROP_RIG_PATH] = session.rig_path


def stored_paths(obj) -> tuple[str | None, str | None]:
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
    validate_setup(setup, rig, segments)
    used_bone_names = build_used_bone_names(setup, rig)
    missing = validate_bones(obj, used_bone_names)
    if missing:
        raise ValueError("Facial rig bones are missing: " + ", ".join(missing[:8]))
    used_bone_indices = np.ascontiguousarray(setup.used_bone_indices, dtype=np.intp)
    pose_bones = tuple(resolve_pose_bone(obj, str(name)) for name in rig.bone_names)
    track_defaults = np.zeros(rig.num_tracks, dtype=np.float32)
    reference_tracks = np.asarray(
        getattr(rig, "reference_tracks", ()) or (), dtype=np.float32
    )
    track_defaults[: min(len(reference_tracks), rig.num_tracks)] = reference_tracks[
        : rig.num_tracks
    ]
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
        used_pose_bone_map=dict(
            zip(
                used_bone_names,
                (pose_bones[int(index)] for index in used_bone_indices),
            )
        ),
        bind_time=time.time(),
        used_pose_collection_indices=pose_bone_collection_indices(
            obj, tuple(pose_bones[int(index)] for index in used_bone_indices)
        ),
        armature_pointer=_pointer(obj),
        data_pointer=_pointer(obj.data),
        bone_count=len(obj.data.bones),
        assembly_revision=str(obj.get("cp77_metarig_definition_hash", "")),
        source_revision=(
            _file_signature(setup_path),
            _file_signature(rig_path),
            _topology_signature(obj),
        ),
    )
    refresh_action_binding(session, force=True)
    track_id_properties(obj, label="facial session properties")
    _track_registry_entry(session.armature_pointer)
    ensure_rig_track_properties(obj, rig, segments)
    _persist_session(session)
    _registry()[session.armature_pointer] = session
    return session, validate_bones(obj, used_bone_names)


def _track_registry_entry(pointer: int) -> None:
    previous = _registry().get(pointer)

    def restore():
        if previous is None:
            _registry().pop(pointer, None)
        else:
            _registry()[pointer] = previous

    track_mutation(("facial-session", pointer), restore, label="facial session binding")


def restore_session(obj) -> FacialSession | None:
    if not is_bound(obj):
        return None
    setup_path, rig_path = stored_paths(obj)
    if not setup_path or not os.path.isfile(setup_path):
        return None
    try:
        resource = load_resource(obj, setup_path)
        return bind_session(
            obj,
            resource.setup_path,
            resource.rig_path,
            rig=resource.rig,
            setup=resource.setup,
        )[0]
    except Exception as error:
        _LOG.error(
            "Session restore failed for '%s': %s", obj.name, error, exc_info=True
        )
        return None


def preload(armature, resources, payloads) -> str:
    """Bind a component reference or a sibling export, or return why none binds"""
    paths = discover_setup_paths(armature, resources, payloads)
    if not paths:
        return "No facial setup export was found for the imported rig"
    repository = FacialRepository(
        resources.documents,
        asset_index=resources.asset_index,
        rig_repository=resources.rigs,
    )
    matches = []
    for path in paths.values():
        try:
            matches.append(resolve_resource(armature, path, repository))
        except (OSError, RuntimeError, ValueError) as error:
            if len(paths) == 1:
                return str(error)
    if len(matches) != 1:
        return f"Facial setup discovery found {len(matches)} compatible exports; select the desired setup in Animation Tools"
    resource = matches[0]
    bind_session(
        armature,
        resource.setup_path,
        resource.rig_path,
        rig=resource.rig,
        setup=resource.setup,
    )
    return ""


def ensure_session(
    obj, setup_path: str = "", rig_path: str = ""
) -> FacialSession | None:
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
    if not _session_is_live(session):
        refresh_session(session, check_sources=True)
    runtime = session.compiled_runtime
    if runtime is None:
        runtime = compile_runtime(session.setup, session.rig, session.track_segments)
        session.compiled_runtime = runtime
    return runtime


def read_tracks_into(
    session: FacialSession, values: np.ndarray, *, additive_composed: bool = False
) -> np.ndarray:
    armature = session.armature
    defaults = session.track_defaults
    # One bound method mapped over the names: ~4x faster than a per-name attribute lookup.
    values[:] = list(map(armature.get, session.track_names, defaults.tolist()))
    mask = session.additive_track_mask
    if mask is not None and not additive_composed:
        # Additive clips (e.g. game lipsync, AdditiveFromRefPose) key deltas over the rig
        # reference tracks; Sermo sees reference + delta. The additive preview already
        # writes composed values, so it is left alone.
        values[mask] += defaults[mask]
        values[~mask] = defaults[~mask]
    return values


def write_output_tracks(session: FacialSession, values, indices) -> int:
    limit = min(len(session.track_names), len(values))
    picked = [int(index) for index in indices if int(index) < limit]
    if not picked:
        return 0
    armature = session.armature
    names = [session.track_names[index] for index in picked]
    current = list(map(armature.get, names, [None] * len(names)))
    written = 0
    for name, value, old in zip(names, np.asarray(values)[picked].tolist(), current):
        if old is not None and float(old) == value:
            continue
        armature[name] = value
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
    return (
        session.track_names[track_index]
        if track_index < len(session.track_names)
        else ""
    )


def restore_bound_sessions() -> None:
    """Rebuild sessions for every bound armature, e.g. after undo replaced the datablocks"""
    clear_registry()
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and is_bound(obj):
            restore_session(obj)


def clear_registry() -> None:
    _registry().clear()
