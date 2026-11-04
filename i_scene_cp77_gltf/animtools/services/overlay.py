from __future__ import annotations

from ...blender.animation_context import active_armature
from ...blender.operator_results import OperationResult
from ..runtime import overlay


def start(context) -> OperationResult:
    if overlay.is_running():
        return OperationResult(False, "Already running", "INFO")
    armature = active_armature(context)
    overlay.start(armature)
    return OperationResult(True, f"Drawing lines for: {armature.name}")


def stop() -> OperationResult:
    overlay.stop()
    return OperationResult(True, "Bone Lines stopped")
