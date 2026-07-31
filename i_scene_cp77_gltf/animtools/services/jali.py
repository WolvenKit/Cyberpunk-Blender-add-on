from __future__ import annotations

import importlib

import bpy
import numpy as np

from ...animation.jali.acoustic import AcousticPhonemeDetector
from ...animation.jali.alignment import TranscriptAligner
from ...animation.jali.bridge import JALIToCp77Bridge
from ...animation.jali.capability import dependency_status
from ...animation.jali.phonemes import ARPABET_JALI_MAP
from ...animation.jali.pipeline import JALIAnimationPipeline
from ...animation.tracks import write_track_matrix
from ...assetio.resolver import resolve_existing_path
from ...blender.animation_context import active_armature
from ...install_dependency import install_dependency
from ..model import JALIGenerationRequest, OperationResult
from .facial import runtime as facial_runtime
from .facial import session as facial_session


def preview_pose(context, *, pose_type: str, custom_jaw: float, custom_lip: float, intensity: float) -> OperationResult:
    session = facial_session.ensure_context_session(context)
    armature = active_armature(context)
    if session is None or armature is None:
        return OperationResult(False, "Load rig + facialsetup first.", "ERROR")
    jaw, lip = _jali_parameters(pose_type, custom_jaw, custom_lip)
    jaw *= intensity
    lip *= intensity
    track_names = tuple(str(name) for name in session.track_names)
    bridge = JALIToCp77Bridge()
    tracks = bridge.jali_to_tracks(
        np.asarray([jaw], dtype=np.float32),
        np.asarray([lip], dtype=np.float32),
        track_names,
    )[0]
    for index in range(154, min(240, session.rig.num_tracks)):
        tracks[index] = 1.0
    for index, name in enumerate(track_names):
        if name:
            armature[name] = float(tracks[index])
    try:
        facial_runtime.solve_tracks(session, tracks, lod=0)
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult(False, f"Solver error: {exc}", "ERROR")
    context.view_layer.update()
    return OperationResult(True, f"Applied {pose_type} pose (JA={jaw:.2f}, LI={lip:.2f})")


def generate_lipsync(context, request: JALIGenerationRequest) -> OperationResult:
    status = dependency_status()
    if not status.parselmouth:
        return OperationResult(False, "Install parselmouth: pip install praat-parselmouth", "ERROR")
    audio_path = resolve_existing_path(bpy.path.abspath(request.audio_path), warn=False)
    if not audio_path:
        return OperationResult(False, f"Audio file not found: {request.audio_path}", "ERROR")
    session = facial_session.ensure_context_session(context)
    armature = active_armature(context)
    if session is None or armature is None:
        return OperationResult(False, "Load facial rig + setup first", "ERROR")

    warnings = []
    try:
        if request.use_transcript and request.transcript.strip() and status.g2p:
            events = TranscriptAligner(audio_path, request.transcript).align_phonemes()
        else:
            if request.use_transcript and request.transcript.strip() and not status.g2p:
                warnings.append("g2p_en is unavailable; acoustic detection was used")
            events = AcousticPhonemeDetector(audio_path).detect_phonemes()
        if not events:
            return OperationResult(False, "No phonemes detected", "WARNING", tuple(warnings))
        pipeline = JALIAnimationPipeline(
            rig=session.rig,
            setup=session.setup,
            fps=context.scene.render.fps,
        )
        tracks = pipeline.generate_animation(events, audio_path=audio_path)
        if request.jaw_multiplier != 1.0 or request.lip_multiplier != 1.0:
            for index, name in enumerate(session.track_names):
                lowered = str(name).lower()
                if "jaw" in lowered:
                    tracks[:, index] *= request.jaw_multiplier
                elif "lips" in lowered or "mouth" in lowered:
                    tracks[:, index] *= request.lip_multiplier
        keyed = write_track_matrix(
            armature,
            session.track_names,
            tracks,
            action_name="JALI_Lipsync",
            start_frame=context.scene.frame_start,
        )
        duration = events[-1].end + 0.5
        context.scene.frame_end = int(duration * context.scene.render.fps) + 10
        audio_warning = _add_audio_strip(context.scene, audio_path)
        if audio_warning:
            warnings.append(audio_warning)
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult(False, f"JALI generation failed: {exc}", "ERROR", tuple(warnings))
    message = (
        f"Lipsync complete — {keyed} tracks keyed, {duration:.2f}s, "
        f"{len(events)} phonemes. Enable the solver or bake to see results."
    )
    return OperationResult(
        True,
        message,
        warnings=tuple(warnings),
        details={"tracks": keyed, "duration": duration, "phonemes": len(events)},
    )


def install_dependencies() -> OperationResult:
    if getattr(bpy.app, "online_access", True) is False:
        return OperationResult(
            False,
            "Blender online access is disabled. Enable it before installing.",
            "ERROR",
        )
    packages = (
        ("praat-parselmouth", "parselmouth"),
        ("nltk", "nltk"),
        ("g2p_en", "g2p_en"),
    )
    installed = []
    present = []
    failed = []
    for pip_name, import_name in packages:
        try:
            importlib.import_module(import_name)
            present.append(pip_name)
            continue
        except ImportError:
            pass
        if install_dependency(pip_name, import_name):
            installed.append(pip_name)
        else:
            failed.append(pip_name)
    dependency_status.cache_clear()
    if failed:
        return OperationResult(False, "Failed to install: " + ", ".join(failed), "ERROR")
    if installed:
        return OperationResult(
            True,
            "JALI dependencies installed successfully. Restart Blender.",
            details={"installed": tuple(installed)},
        )
    return OperationResult(True, "All dependencies are already installed.", details={"present": tuple(present)})


def _jali_parameters(pose_type: str, custom_jaw: float, custom_lip: float) -> tuple[float, float]:
    if pose_type == "CUSTOM":
        return custom_jaw, custom_lip
    if ARPABET_JALI_MAP and pose_type in ARPABET_JALI_MAP:
        value = ARPABET_JALI_MAP[pose_type]
        return value.jaw, value.lip
    return {
        "NEUTRAL": (0.0, 0.0),
        "SMILE": (0.0, 1.0),
        "POUT": (0.0, -1.0),
        "JAW_OPEN": (1.0, 0.0),
    }.get(pose_type, (0.3, 0.0))


def _add_audio_strip(scene, audio_path: str) -> str | None:
    try:
        if not scene.sequence_editor:
            scene.sequence_editor_create()
        editor = scene.sequence_editor
        strips = next(
            (
                collection
                for name in ("strips", "sequences", "strips_all")
                if (collection := getattr(editor, name, None)) is not None
                and hasattr(collection, "new_sound")
            ),
            None,
        )
        if strips is None:
            for name in dir(editor):
                if name.startswith("_"):
                    continue
                try:
                    collection = getattr(editor, name)
                except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                    continue
                if hasattr(collection, "new_sound"):
                    strips = collection
                    break
        if strips is None:
            return "Audio animation was created, but Blender exposed no writable sequencer strip collection"
        if hasattr(strips, "__iter__"):
            for strip in list(strips):
                if getattr(strip, "name", "").startswith("JALI_Audio"):
                    strips.remove(strip)
        strips.new_sound(
            "JALI_Audio",
            audio_path,
            channel=1,
            frame_start=scene.frame_start,
        )
    except (AttributeError, OSError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
        return f"Lipsync was generated, but the audio strip could not be added: {exc}"
    return None
