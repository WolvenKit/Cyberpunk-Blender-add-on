from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    message: str = ""
    level: str = "INFO"
    warnings: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def blender_status(self) -> set[str]:
        return {"FINISHED"} if self.ok else {"CANCELLED"}

    @classmethod
    def finished(cls, message: str = "", level: str = "INFO", **details):
        return cls(True, message, level, details=details)

    @classmethod
    def cancelled(cls, message: str = "", level: str = "ERROR", **details):
        return cls(False, message, level, details=details)


@dataclass(frozen=True)
class RootMotionRequest:
    root_bone: str
    hip_bone: str
    step: int = 1
    include_vertical: bool = True
    include_rotation: bool = True


@dataclass(frozen=True)
class FacialBakeRequest:
    frame_start: int
    frame_end: int
    keyframe_step: int = 1


@dataclass(frozen=True)
class JALIGenerationRequest:
    audio_path: str
    transcript: str = ""
    use_transcript: bool = False
    jaw_multiplier: float = 1.0
    lip_multiplier: float = 1.0


@dataclass(frozen=True)
class RigifyBakeRequest:
    action_name: str
    overwrite: bool
    frame_start: int
    frame_end: int
    step: int = 1
