from __future__ import annotations

import bpy

from ...animation.domain.jali.acoustic import AcousticPhonemeDetector
from ...animation.domain.jali.alignment import TranscriptAligner
from ...animation.domain.jali.bridge import JALIToCp77Bridge
from ...animation.domain.jali.capability import dependency_status
from ...animation.domain.jali.lipsync_tracks import (
    generated_track_columns,
    jali_parameters,
    preview_pose_tracks,
    scale_pose_tracks,
)
from ...animation.model.clip.binding import track_property_path
from ...animation.services.jali.pipeline import JALIAnimationPipeline
from ...assetio.resolver import resolve_existing_path
from ...blender.action_metadata import action_is_additive
from ...blender.animation_context import (
    active_armature,
    track_action_curves,
    track_animation_data,
    track_fake_user,
    track_id_properties,
    track_pose,
    track_scene_frames,
)
from ...blender.facial.solver import solve_tracks
from ...blender.operator_results import OperationResult
from ...blender.tracks import write_track_matrix
from ...blender.transactions import transactional
from ...core.log import get_logger
from ..blender.sequencer import replace_sound_strip
from ..model.requests import JALI_TARGET_OVERWRITE, JALIGenerationRequest
from .facial import context_session

_LOG = get_logger(__name__)

_AUDIO_STRIP = "JALI_Audio"


@transactional("JALI pose preview")
def preview_pose(
    context, *, pose_type: str, custom_jaw: float, custom_lip: float, intensity: float
) -> OperationResult:
    session = context_session(context)
    armature = active_armature(context)
    if session is None or armature is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    jaw, lip = jali_parameters(pose_type, custom_jaw, custom_lip)
    jaw *= intensity
    lip *= intensity
    track_names = tuple(str(name) for name in session.track_names)
    tracks = preview_pose_tracks(
        JALIToCp77Bridge(),
        session.track_segments,
        track_names,
        session.track_defaults,
        session.rig.num_tracks,
        pose_type=pose_type,
        jaw=jaw,
        lip=lip,
        intensity=intensity,
    )
    track_id_properties(armature, label="JALI preview tracks")
    track_pose(armature, label="JALI preview pose")
    for index, name in enumerate(track_names):
        if name:
            armature[name] = float(tracks[index])
    try:
        solve_tracks(session, tracks, lod=0)
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        _LOG.error(
            "JALI pose preview solve failed: armature=%s pose=%s error=%s",
            armature.name,
            pose_type,
            exc,
            exc_info=True,
        )
        return OperationResult(False, f"Solver error: {exc}", "ERROR")
    context.view_layer.update()
    return OperationResult(
        True, f"Applied {pose_type} pose (JA={jaw:.2f}, LI={lip:.2f})"
    )


def _target_action_is_additive(armature) -> bool:
    action = getattr(getattr(armature, "animation_data", None), "action", None)
    return action is not None and action_is_additive(action)


@transactional("JALI lipsync")
def generate_lipsync(context, request: JALIGenerationRequest) -> OperationResult:
    status = dependency_status()
    if not status.parselmouth:
        return OperationResult(
            False,
            f"parselmouth didn't load: {status.parselmouth_error}",
            "ERROR",
            error=status.parselmouth_error,
        )
    audio_path = resolve_existing_path(bpy.path.abspath(request.audio_path), warn=False)
    if not audio_path:
        return OperationResult(
            False, f"Audio file not found: {request.audio_path}", "ERROR"
        )
    session = context_session(context)
    armature = active_armature(context)
    if session is None or armature is None:
        return OperationResult(False, "Load facial rig + setup first", "ERROR")

    scene = context.scene
    warnings = []
    try:
        if request.use_transcript and request.transcript.strip() and status.g2p:
            aligner = TranscriptAligner(audio_path, request.transcript)
            events = aligner.align_phonemes()
            if aligner.method_used == "legacy":
                warnings.append(
                    "Forced alignment was unavailable; approximate transcript timing was used"
                )
        else:
            if request.use_transcript and request.transcript.strip() and not status.g2p:
                warnings.append("g2p_en is unavailable; acoustic detection was used")
            detector = AcousticPhonemeDetector(audio_path)
            events = detector.detect_phonemes()
            warnings.extend(detector.warnings())
        if not events:
            return OperationResult(
                False, "No phonemes detected", "WARNING", tuple(warnings)
            )
        pipeline = JALIAnimationPipeline(
            rig=session.rig,
            setup=session.setup,
            fps=scene.render.fps,
        )
        tracks = pipeline.generate_animation(events, audio_path=audio_path)
        warnings.extend(pipeline.warnings)
        if request.jaw_multiplier != 1.0 or request.lip_multiplier != 1.0:
            scale_pose_tracks(
                session.track_segments,
                session.track_names,
                tracks,
                request.jaw_multiplier,
                request.lip_multiplier,
            )
            if not pipeline.used_viseme_targets:
                # Calibrated targets carry measured override values; only the JA/LI
                # mapping derives overrides from the pose outputs.
                pipeline.bridge.recouple_overrides(tracks, session.track_names)
        existing = getattr(getattr(armature, "animation_data", None), "action", None)
        overwrite = request.target == JALI_TARGET_OVERWRITE and existing is not None
        if overwrite and _target_action_is_additive(armature):
            # Additive actions key deltas over the rig reference (AdditiveFromRefPose).
            tracks = tracks - session.track_defaults[None, : tracks.shape[1]]
        columns = (
            generated_track_columns(session.track_names, pipeline.used_viseme_targets)
            if overwrite
            else None
        )
        track_animation_data(armature, label="JALI lipsync Action")
        track_id_properties(armature, label="JALI lipsync track properties")
        track_scene_frames(scene, label="JALI lipsync frame range")
        if overwrite:
            track_id_properties(existing, label="JALI lipsync Action metadata")
            track_action_curves(
                existing,
                armature,
                (track_property_path(session.track_names[index]) for index in columns),
                label="JALI lipsync tracks",
            )
        elif existing is not None:
            track_fake_user(existing, label="JALI kept Action")
        keyed = write_track_matrix(
            armature,
            session.track_names,
            tracks,
            action_name="JALI_Lipsync",
            start_frame=scene.frame_start,
            # Overwrite: only the tracks lipsync generates, only inside the generated range.
            columns=columns,
            new_action=not overwrite,
            keep_keys_outside_range=overwrite,
        )
        duration = events[-1].end + 0.5
        needed_end = scene.frame_start + int(duration * scene.render.fps) + 10
        scene.frame_end = max(scene.frame_end, needed_end)
        audio_warning = replace_sound_strip(scene, _AUDIO_STRIP, audio_path)
        if audio_warning:
            warnings.append(audio_warning)
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        _LOG.error(
            "JALI generation failed: armature=%s audio=%s error=%s",
            armature.name,
            audio_path,
            exc,
            exc_info=True,
        )
        return OperationResult(
            False, f"JALI generation failed: {exc}", "ERROR", tuple(warnings)
        )
    action = armature.animation_data.action
    if overwrite:
        where = f"lipsync tracks of '{action.name}' overwritten (other keys kept)"
    else:
        kept = (
            f"; '{existing.name}' kept with a fake user" if existing is not None else ""
        )
        where = f"new action '{action.name}'{kept}"
    message = (
        f"Lipsync complete — {keyed} tracks keyed into {where}, {duration:.2f}s, "
        f"{len(events)} phonemes. Enable the solver or bake to see results."
    )
    return OperationResult(
        True,
        message,
        warnings=tuple(warnings),
        details={"tracks": keyed, "duration": duration, "phonemes": len(events)},
    )
