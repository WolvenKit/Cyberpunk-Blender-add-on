from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...animation.domain.clip.additive import layer_additive_bone
from ...animation.domain.clip.timing import mixer_entry_sample_frame
from ...animation.model.animgraph.frames import TrackSnapshot
from ...animation.model.clip.metadata import FPS
from ...assetio.values import coerce_float
from ...bartmoss.qs_transform import QsTransform
from ...blender.animation_context import scene_frame_rate
from ...blender.identity import rna_is_live
from ...blender.keyframes import assign_action_with_slot
from ...blender.pose import restore_tracks
from ...blender.transactions import track_mutation
from ...core.log import TRACE, get_logger, log_on_change, log_once
from ..blender.action_sampling import ActionSamplingPlan, component_value, sample_bone
from ..model.additive import ADDITIVE_PREVIEW_SETTINGS, AdditiveSlotPlayback
from . import facial

_LOG = get_logger(__name__)
_IDENTITY = QsTransform.identity()
_DATA_REFRESH = {"DATA"}


@dataclass(frozen=True, slots=True)
class AdditiveEntry:
    plan: ActionSamplingPlan
    slot_index: int
    storage_mode: str
    mask_name: str
    mask_weights: dict[str, float] | None
    reference_basis: dict[str, QsTransform]
    frame_start: float
    frame_end: float


@dataclass(frozen=True, slots=True)
class PreviewConfiguration:
    entries: tuple[AdditiveEntry, ...]
    base_action: Any | None
    standalone: bool
    base_plan: ActionSamplingPlan | None
    base_frame_start: float
    base_frame_end: float
    reference_tracks: dict[str, float]
    reference_basis: dict[str, QsTransform]
    base_bones: frozenset[str]
    track_names: frozenset[str]
    frame_start: int
    frame_end: int

    @property
    def timeline_origin(self) -> float:
        return (
            float(self.base_frame_start)
            if self.base_plan is not None
            else float(self.entries[0].frame_start)
        )


@dataclass(slots=True)
class PreviewSession:
    scene: Any
    armature: Any
    configuration: PreviewConfiguration
    original_action: Any | None
    original_action_slot_identifier: str
    original_action_slot_handle: int
    original_frame_start: int
    original_frame_end: int
    original_frame: int
    original_subframe: float
    original_pose: dict[str, Any]
    original_rotation_modes: dict[str, str]
    original_tracks: dict[str, TrackSnapshot]


_session: PreviewSession | None = None
_applying = False


def _scene_frame(scene) -> float:
    return float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))


def _entry_frame(
    session: PreviewSession,
    entry: AdditiveEntry,
    playback: AdditiveSlotPlayback,
    master_frame: float,
    master_fps: float,
) -> float:
    configuration = session.configuration
    if configuration.standalone:
        return master_frame
    looped = bool(playback.loop or getattr(entry.plan.action, "use_cyclic", False))
    return mixer_entry_sample_frame(
        master_frame,
        master_origin=configuration.timeline_origin,
        frame_start=entry.frame_start,
        frame_end=entry.frame_end,
        time_offset_seconds=playback.time_offset,
        time_scale=playback.time_scale,
        fps=FPS,
        master_fps=master_fps,
        looped=looped,
    )


def _base_pose_for_frame(
    configuration: PreviewConfiguration, master_frame: float, master_fps: float
):
    if configuration.base_plan is None:
        return {
            name: configuration.reference_basis.get(name, _IDENTITY)
            for name in configuration.base_bones
        }, master_frame
    result = {name: _IDENTITY for name in configuration.base_bones}
    frame = mixer_entry_sample_frame(
        master_frame,
        master_origin=configuration.timeline_origin,
        frame_start=configuration.base_frame_start,
        frame_end=configuration.base_frame_end,
        time_offset_seconds=0.0,
        time_scale=1.0,
        fps=FPS,
        master_fps=master_fps,
        looped=bool(getattr(configuration.base_plan.action, "use_cyclic", False)),
    )
    for binding in configuration.base_plan.bones:
        result[binding.name] = sample_bone(binding, frame)
    return result, frame


def _apply(session: PreviewSession) -> None:
    configuration = session.configuration
    scene = session.scene
    master_frame = _scene_frame(scene)
    master_fps = scene_frame_rate(scene, FPS)
    armature = session.armature
    pose_bones = armature.pose.bones
    settings = getattr(scene, ADDITIVE_PREVIEW_SETTINGS, None)
    playbacks = tuple(
        AdditiveSlotPlayback.from_settings(settings, entry.slot_index)
        for entry in configuration.entries
    )
    weights = tuple(
        1.0 if configuration.standalone else playback.weight for playback in playbacks
    )
    entry_frames = tuple(
        _entry_frame(session, entry, playback, master_frame, master_fps)
        for entry, playback in zip(configuration.entries, playbacks)
    )

    working_pose, base_frame = _base_pose_for_frame(
        configuration, master_frame, master_fps
    )
    for entry, weight, entry_frame in zip(configuration.entries, weights, entry_frames):
        if weight == 0.0:
            continue
        for binding in entry.plan.bones:
            layer_additive_bone(
                working_pose,
                binding.name,
                sample_bone(binding, entry_frame),
                weight=weight,
                storage_mode=entry.storage_mode,
                reference_basis=entry.reference_basis,
                mask_weights=entry.mask_weights,
                replace_with_reference_applied=configuration.standalone,
            )

    for name in configuration.base_bones:
        pose_bone = pose_bones.get(name)
        if pose_bone is not None:
            value = working_pose.get(name, _IDENTITY)
            pose_bone.location = value.translation
            x, y, z, w = value.rotation_xyzw
            pose_bone.rotation_quaternion = (w, x, y, z)
            pose_bone.scale = value.scale

    for name in configuration.track_names:
        reference = float(configuration.reference_tracks.get(name, 0.0))
        component = (
            configuration.base_plan.tracks.get(name)
            if configuration.base_plan is not None
            else None
        )
        value = component_value(component, reference, base_frame)
        for entry, weight, entry_frame in zip(
            configuration.entries, weights, entry_frames
        ):
            if weight == 0.0:
                continue
            component = entry.plan.tracks.get(name)
            if component is None:
                continue
            value += component_value(component, 0.0, entry_frame) * weight
        current = coerce_float(
            armature.get(name, value), value + 1.0, unwrap=False, finite=False
        )
        if current != value or name not in armature:
            armature[name] = value

    armature.update_tag(refresh=_DATA_REFRESH)


def _refresh(session: PreviewSession) -> None:
    _apply(session)
    facial.solve_frame(session.scene, additive_armature=session.armature)


def evaluate_frame(scene) -> None:
    """Re-layer the active preview for the scene's new frame"""
    global _applying
    session = _session
    if session is None or session.scene != scene or _applying:
        return
    _applying = True
    try:
        _apply(session)
        # A success ends the run of failures, so the next failure logs again.
        log_on_change(_LOG, TRACE, "preview", "Additive mixer preview applied")
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        log_on_change(
            _LOG,
            "ERROR",
            "preview",
            "Additive mixer preview failed: %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
    except Exception as exc:
        _LOG.exception("Additive mixer preview failed: %s", exc)
    finally:
        _applying = False


def refresh(scene=None) -> None:
    """Re-layer the active preview after a playback setting changed"""
    session = _session
    if session is None or (scene is not None and scene != session.scene):
        return
    try:
        _refresh(session)
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        log_on_change(
            _LOG,
            "ERROR",
            "preview",
            "Additive mixer preview refresh failed: %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )


def _restore(session: PreviewSession) -> None:
    scene = session.scene
    armature = session.armature
    if not rna_is_live(scene) or not rna_is_live(armature):
        return

    scene.frame_start = session.original_frame_start
    scene.frame_end = session.original_frame_end

    if armature.animation_data is None:
        armature.animation_data_create()
    original_action = (
        session.original_action if rna_is_live(session.original_action) else None
    )
    if original_action is None:
        armature.animation_data.action = None
    else:
        assign_action_with_slot(
            armature,
            original_action,
            slot_identifier=session.original_action_slot_identifier,
            slot_handle=session.original_action_slot_handle,
        )

    try:
        scene.frame_set(session.original_frame, subframe=session.original_subframe)
    except TypeError:
        scene.frame_set(session.original_frame)

    for name, matrix in session.original_pose.items():
        pose_bone = armature.pose.bones.get(name)
        if pose_bone is None:
            continue
        pose_bone.rotation_mode = session.original_rotation_modes.get(
            name, pose_bone.rotation_mode
        )
        pose_bone.matrix_basis = matrix.copy()
    try:
        restore_tracks(armature, session.original_tracks)
    except (KeyError, ReferenceError, RuntimeError) as error:
        _LOG.warning(
            "Additive preview could not restore tracks on %s: %s",
            armature.name,
            error,
            exc_info=True,
        )
    armature.update_tag(refresh=_DATA_REFRESH)


def begin(session: PreviewSession) -> None:
    """Make session the active preview"""
    global _session
    clear(restore=True)
    _session = session


def apply_active() -> None:
    """Layer the active preview for the current frame, raising on failure"""
    if _session is not None:
        _refresh(_session)


def reconfigure(
    configuration: PreviewConfiguration, original_tracks: dict[str, TrackSnapshot]
) -> None:
    """Swap the active preview's configuration in place and re-layer the current frame"""
    session = _session
    armature = session.armature
    previous = session.configuration
    for name in previous.base_bones - configuration.base_bones:
        pose_bone = armature.pose.bones.get(name)
        if pose_bone is not None:
            pose_bone.matrix_basis.identity()
    for name in previous.track_names - configuration.track_names:
        armature[name] = float(previous.reference_tracks.get(name, 0.0))
    for name, snapshot in original_tracks.items():
        session.original_tracks.setdefault(name, snapshot)
    session.configuration = configuration
    for name in configuration.base_bones:
        pose_bone = armature.pose.bones.get(name)
        if pose_bone is not None:
            pose_bone.rotation_mode = "QUATERNION"
    session.scene.frame_start = configuration.frame_start
    session.scene.frame_end = configuration.frame_end
    _refresh(session)


def track_activation() -> None:
    """On rollback, drop a preview begun inside the active transaction"""
    previous = _session

    def restore():
        global _session
        if _session is not previous:
            _session = None

    track_mutation(
        ("additive-preview-activation",), restore, label="additive preview activation"
    )


def track_configuration(session: PreviewSession) -> None:
    """On rollback, put back the configuration the active preview had before reconfiguration"""
    configuration = session.configuration
    original_tracks = dict(session.original_tracks)

    def restore():
        session.configuration = configuration
        session.original_tracks = original_tracks

    track_mutation(
        ("additive-preview-configuration", id(session)),
        restore,
        label="additive preview configuration",
    )


def clear(*, restore: bool) -> None:
    global _session
    session = _session
    _session = None
    if restore and session is not None:
        _restore(session)


def active_session() -> PreviewSession | None:
    return _session


def active_armature():
    return _session.armature if _session is not None else None


def is_active(armature=None) -> bool:
    session = _session
    if session is None:
        return False
    return armature is None or session.armature == armature


def active_action_name(armature=None) -> str:
    if not is_active(armature):
        return ""
    try:
        return str(_session.configuration.entries[0].plan.action.name)
    except (AttributeError, IndexError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("active_action_name", type(error).__name__),
            "active action name: fell back after %s",
            error,
            exc_info=True,
        )
        return ""


def uses_action(armature, action, *, slot_index: int | None = None) -> bool:
    if not is_active(armature):
        return False
    configuration = _session.configuration
    if slot_index is None:
        return (
            configuration.base_plan is not None
            and configuration.base_plan.action == action
        )
    return any(
        entry.slot_index == slot_index and entry.plan.action == action
        for entry in configuration.entries
    )


def references_action(action_name: str) -> bool:
    session = _session
    if session is None:
        return False
    configuration = session.configuration
    if any(
        rna_is_live(entry.plan.action) and entry.plan.action.name == action_name
        for entry in configuration.entries
    ):
        return True
    base = configuration.base_plan
    return (
        base is not None
        and rna_is_live(base.action)
        and base.action.name == action_name
    )
