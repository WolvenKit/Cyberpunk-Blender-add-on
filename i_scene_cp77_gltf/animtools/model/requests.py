from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RootMotionRequest:
    root_bone: str
    source_bone: str
    step: int = 1
    translation_axes: tuple[bool, bool, bool] = (True, True, True)
    rotation_mode: str = "YAW"
    export_type: str = "AUTO"
    preserve_pose: bool = False


@dataclass(frozen=True, slots=True)
class RootMotionEditOptions:
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    direction: float = 0.0
    turn_scale: float = 1.0
    displacement: tuple[float, float, float] = (0.0, 1.0, 0.0)
    turn: float = 0.0
    smooth_radius: float = 3.0

    def as_kwargs(self) -> dict:
        return {
            "scale": self.scale,
            "direction": self.direction,
            "turn_scale": self.turn_scale,
            "displacement": self.displacement,
            "turn": self.turn,
            "smooth_radius": self.smooth_radius,
        }


@dataclass(frozen=True, slots=True)
class FacialBakeRequest:
    frame_start: int
    frame_end: int
    keyframe_step: int = 1


JALI_TARGET_NEW = "NEW"
JALI_TARGET_OVERWRITE = "OVERWRITE"


@dataclass(frozen=True, slots=True)
class JALIGenerationRequest:
    audio_path: str
    transcript: str = ""
    use_transcript: bool = False
    jaw_multiplier: float = 1.0
    lip_multiplier: float = 1.0
    target: str = JALI_TARGET_NEW


@dataclass(frozen=True, slots=True)
class RigifyBakeRequest:
    action_name: str
    overwrite: bool
    frame_start: int
    frame_end: int
    step: int = 1


BAKE_RANGE_SCENE = "SCENE"
BAKE_RANGE_ACTION = "ACTION"
BAKE_RANGE_MANUAL = "MANUAL"


@dataclass(frozen=True, slots=True)
class RigifyBakeDefaults:
    action_name: str
    frame_start: int
    frame_end: int
    forward: bool
