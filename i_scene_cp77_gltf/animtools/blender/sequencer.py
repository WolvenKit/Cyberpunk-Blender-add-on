from __future__ import annotations

from ...blender.transactions import track_mutation
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)


def replace_sound_strip(scene, name: str, audio_path: str) -> str | None:
    """Put one sound strip named name at the scene start, or return a warning when it cannot be added"""
    try:
        if not scene.sequence_editor:
            scene.sequence_editor_create()
        strips = scene.sequence_editor.strips
        previous = [
            strip for strip in strips if getattr(strip, "name", "").startswith(name)
        ]
        strip = strips.new_sound(
            name, audio_path, channel=1, frame_start=scene.frame_start
        )
        track_mutation(
            ("sound-strip", scene.name, strip.name),
            lambda strips=strips, strip=strip: strips.remove(strip),
            label=f"sound strip {name}",
        )
        for existing in previous:
            strips.remove(existing)
        strip.name = name
    except (
        AttributeError,
        OSError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("replace_sound_strip", type(exc).__name__),
            "replace sound strip: fell back after %s",
            exc,
            exc_info=True,
        )
        return f"Lipsync was generated, but the audio strip could not be added: {exc}"
    return None
