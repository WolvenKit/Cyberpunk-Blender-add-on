from __future__ import annotations

import bpy

from ....animation.rigify.mapping import DIRECTION_FORWARD, DIRECTION_REVERSE
from ....blender.animation_context import active_armature
from ....blender.context import safe_mode_switch
from ....blender.selection import select_objects
from ...model import OperationResult
from .build import cp77_to_rigify
from .direction import set_constraint_direction
from .pairing import find_pair, get_constraint_direction


def generate_rigify(context) -> OperationResult:
    try:
        rig = cp77_to_rigify(context)
    except (KeyError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult.cancelled(f"Rigify generation failed: {exc}")
    if rig is None:
        return OperationResult.cancelled("Select a Cyberpunk armature")
    return OperationResult.finished(
        f"Generated Rigify rig '{rig.name}'",
        rig_name=rig.name,
    )


def toggle_constraint_direction(
    context,
    *,
    source_name: str = "",
    rigify_name: str = "",
) -> OperationResult:
    source = bpy.data.objects.get(source_name) if source_name else None
    rig = bpy.data.objects.get(rigify_name) if rigify_name else None
    if source is None or rig is None:
        source, rig = find_pair(active_armature(context))
    if source is None or rig is None:
        return OperationResult.cancelled("Source/Rigify pair not found")
    target = (
        DIRECTION_REVERSE
        if get_constraint_direction(source) == DIRECTION_FORWARD
        else DIRECTION_FORWARD
    )
    ok, message = set_constraint_direction(source, rig, target)
    return OperationResult(ok, message, "INFO" if ok else "ERROR")


def activate_linked_rig(context, target_name: str) -> OperationResult:
    target = bpy.data.objects.get(target_name)
    if target is None:
        return OperationResult.cancelled(f"Object '{target_name}' not found")
    safe_mode_switch("OBJECT")
    selected = select_objects(target, reveal=True, context=context)
    if not selected:
        return OperationResult.cancelled(f"Object '{target_name}' is unavailable")
    return OperationResult.finished(f"Activated '{target.name}'", target_name=target.name)
