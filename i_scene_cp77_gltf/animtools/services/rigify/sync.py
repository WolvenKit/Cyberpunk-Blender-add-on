from __future__ import annotations

from typing import Optional

import bpy
from bpy.app.handlers import persistent
from ....blender.context import safe_mode_switch
from ....blender.selection import select_objects
from ....animation.rigify.mapping import (
    CP77_TO_METARIG,
    DIRECTION_FORWARD,
    FORWARD_CONSTRAINT_NAMES,
    FORWARD_NEUTRAL_PROP_PREFIX,
    FORWARD_REST_ONLY_BONES,
    LIMITED_LOCATION_OFFSETS,
    MAX_LIMITED_LOCATION_OFFSET,
    NEUTRALIZED_RIGIFY_CONTROLS,
    resolve_forward_target,
)
from .pairing import get_constraint_direction
from .runtime import (
    RigSyncRuntime,
    clear_runtimes,
    compile_runtime,
    remove_runtime,
    runtimes,
    set_runtime,
)

_HANDLER_ACTIVE = False
_HANDLER_NAMES = {"_rigify_sync_handler", "_cp77_basis_sync_handler", "_cp77_sync_handler"}

def _safe_matrix_inverse(matrix):
    return matrix.inverted_safe() if hasattr(matrix, "inverted_safe") else matrix.inverted()

def _copy_matrix3(target, source) -> None:
    for row in range(3):
        for column in range(3):
            target[row][column] = source[row][column]

def _rotation_only_3x3(matrix):
    return matrix.to_quaternion().to_matrix()

def _matrix_to_flat(matrix) -> list[float]:
    return [float(matrix[row][column]) for row in range(4) for column in range(4)]

def _forward_neutral_prop(source_name: str) -> str:
    return FORWARD_NEUTRAL_PROP_PREFIX + source_name

def neutralize_rigify_controls(rig) -> int:
    if rig is None or rig.type != "ARMATURE":
        return 0
    count = 0
    for name in NEUTRALIZED_RIGIFY_CONTROLS:
        pose_bone = rig.pose.bones.get(name)
        if pose_bone is None:
            continue
        pose_bone.matrix_basis.identity()
        pose_bone.lock_location = (True, True, True)
        pose_bone.lock_rotation = (True, True, True)
        pose_bone.lock_rotation_w = True
        pose_bone.lock_scale = (True, True, True)
        pose_bone.hide = True
        count += 1
    return count

def _neutralized_controls(rig) -> tuple[object, ...]:
    return tuple(
        pose_bone
        for name in NEUTRALIZED_RIGIFY_CONTROLS
        if (pose_bone := rig.pose.bones.get(name)) is not None
    )

def clear_forward_constraints(source) -> int:
    if source is None or source.type != "ARMATURE":
        return 0
    removed = 0
    for pose_bone in source.pose.bones:
        for name in FORWARD_CONSTRAINT_NAMES:
            constraint = pose_bone.constraints.get(name)
            if constraint is not None:
                pose_bone.constraints.remove(constraint)
                removed += 1
    return removed

def _has_forward_neutral_pose(source, rig) -> bool:
    rig_names = set(rig.pose.bones.keys())
    for source_name, metarig_name in CP77_TO_METARIG.items():
        if source_name in FORWARD_REST_ONLY_BONES:
            continue
        if source.pose.bones.get(source_name) is None:
            continue
        target_name = resolve_forward_target(source_name, metarig_name, rig_names)
        if target_name is None:
            continue
        if source.data.get(_forward_neutral_prop(source_name)) is None:
            return False
    return True

def _capture_forward_neutral_pose(source, rig, depsgraph=None) -> int:
    if source is None or rig is None or source.type != "ARMATURE" or rig.type != "ARMATURE":
        return 0
    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            depsgraph = None
    try:
        rig_eval = rig.evaluated_get(depsgraph) if depsgraph is not None else rig
    except Exception:
        rig_eval = rig
    rig_pose = rig_eval.pose.bones
    rig_names = set(rig_pose.keys())
    captured = 0
    for source_name, metarig_name in CP77_TO_METARIG.items():
        if source_name in FORWARD_REST_ONLY_BONES:
            continue
        if source.pose.bones.get(source_name) is None:
            continue
        target_name = resolve_forward_target(source_name, metarig_name, rig_names)
        if target_name is None:
            continue
        target_pose_bone = rig_pose.get(target_name)
        if target_pose_bone is None:
            continue
        source.data[_forward_neutral_prop(source_name)] = _matrix_to_flat(target_pose_bone.matrix.copy())
        captured += 1
    return captured

def _solve_basis(runtime: RigSyncRuntime, entry, rig_eval, target_pose_bone):
    source = runtime.source
    source_pose_bone = entry.source_pose_bone
    source_rest = source_pose_bone.bone.matrix_local.copy()
    target_pose_world = rig_eval.matrix_world @ target_pose_bone.matrix.copy()
    target_neutral_local = entry.target_neutral if entry.target_neutral is not None else entry.target_rest
    target_neutral_world = rig_eval.matrix_world @ target_neutral_local.copy()
    source_rest_world = source.matrix_world @ source_rest
    target_delta_world = target_pose_world @ _safe_matrix_inverse(target_neutral_world)
    desired_pose_world = target_delta_world @ source_rest_world
    desired_pose_local = _safe_matrix_inverse(source.matrix_world) @ desired_pose_world
    if source_pose_bone.parent is not None:
        parent_pose = source_pose_bone.parent.matrix.copy()
        parent_rest = source_pose_bone.parent.bone.matrix_local.copy()
        bind = parent_pose @ _safe_matrix_inverse(parent_rest) @ source_rest
    else:
        bind = source_rest
    basis = _safe_matrix_inverse(bind) @ desired_pose_local
    result = entry.basis
    result.identity()
    _copy_matrix3(result, _rotation_only_3x3(basis))
    if entry.copy_location or entry.limited_location:
        location = basis.translation.copy()
        if entry.limited_location:
            limit = LIMITED_LOCATION_OFFSETS.get(entry.source_name, MAX_LIMITED_LOCATION_OFFSET)
            if location.length > limit:
                location = location.normalized() * limit
        result.translation = location
    return result

def _refresh_pose_matrices(source) -> None:
    try:
        source.update_tag(refresh={"OBJECT", "DATA"})
        bpy.context.view_layer.update()
    except Exception:
        pass

def sync_runtime(runtime: RigSyncRuntime, depsgraph=None) -> int:
    if not runtime.valid():
        return 0
    for pose_bone in runtime.neutralized_controls:
        pose_bone.matrix_basis.identity()
    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            depsgraph = None
    try:
        rig_eval = runtime.rig.evaluated_get(depsgraph) if depsgraph is not None else runtime.rig
    except Exception:
        rig_eval = runtime.rig
    rig_pose = rig_eval.pose.bones
    synced = 0
    for start, end in runtime.depth_ranges:
        for entry in runtime.entries[start:end]:
            if entry.rest_only:
                entry.source_pose_bone.matrix_basis.identity()
                synced += 1
                continue
            target_pose_bone = rig_pose.get(entry.target_name)
            if target_pose_bone is None:
                continue
            entry.source_pose_bone.matrix_basis = _solve_basis(runtime, entry, rig_eval, target_pose_bone)
            synced += 1
        _refresh_pose_matrices(runtime.source)
    return synced

def register_runtime(source, rig) -> RigSyncRuntime:
    neutralize_rigify_controls(rig)
    runtime = compile_runtime(source, rig, _neutralized_controls(rig))
    set_runtime(runtime)
    _ensure_sync_handler()
    return runtime

def enable_forward_sync(source, rig, recapture_neutral: bool = False) -> int:
    clear_forward_constraints(source)
    neutralize_rigify_controls(rig)
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        depsgraph = None
    if recapture_neutral or not _has_forward_neutral_pose(source, rig):
        _capture_forward_neutral_pose(source, rig, depsgraph)
    source.data["cp77_forward_sync_enabled"] = True
    runtime = register_runtime(source, rig)
    select_objects(source)
    safe_mode_switch("POSE")
    return sync_runtime(runtime, depsgraph)

def disable_forward_sync(source) -> None:
    if source is not None:
        source.data["cp77_forward_sync_enabled"] = False
        remove_runtime(source)
    _remove_sync_handler_if_idle()

def _original_id(value):
    original = getattr(value, "original", None)
    if original is not None:
        return original
    original = getattr(value, "id_orig", None)
    return original if original is not None else value

def _updated_ids(depsgraph) -> tuple[object, ...]:
    try:
        return tuple(_original_id(update.id) for update in depsgraph.updates)
    except Exception:
        return ()

def _rebuild_runtime(runtime: RigSyncRuntime) -> Optional[RigSyncRuntime]:
    if not runtime.valid():
        remove_runtime(runtime.source)
        return None
    neutralize_rigify_controls(runtime.rig)
    return set_runtime(compile_runtime(runtime.source, runtime.rig, _neutralized_controls(runtime.rig)))

def _rigify_sync_handler(*args) -> None:
    global _HANDLER_ACTIVE
    if _HANDLER_ACTIVE:
        return
    depsgraph = next((value for value in reversed(args) if hasattr(value, "id_eval_get")), None)
    updates = _updated_ids(depsgraph) if depsgraph is not None else ()
    _HANDLER_ACTIVE = True
    try:
        for runtime in runtimes():
            if not runtime.valid():
                remove_runtime(runtime.source)
                continue
            if not runtime.source.data.get("cp77_forward_sync_enabled", False):
                remove_runtime(runtime.source)
                continue
            if get_constraint_direction(runtime.source) != DIRECTION_FORWARD:
                remove_runtime(runtime.source)
                continue
            if runtime.manual_sync:
                continue
            if runtime.topology_changed(updates):
                runtime = _rebuild_runtime(runtime)
                if runtime is None:
                    continue
            if runtime.matches_updates(updates):
                sync_runtime(runtime, depsgraph)
    finally:
        _HANDLER_ACTIVE = False
        _remove_sync_handler_if_idle()

def _ensure_sync_handler() -> None:
    handlers = bpy.app.handlers.depsgraph_update_post
    while _rigify_sync_handler in handlers:
        handlers.remove(_rigify_sync_handler)
    if runtimes():
        handlers.append(_rigify_sync_handler)

def _remove_sync_handler_if_idle() -> None:
    if runtimes():
        return
    handlers = bpy.app.handlers.depsgraph_update_post
    while _rigify_sync_handler in handlers:
        handlers.remove(_rigify_sync_handler)

def reset_runtimes() -> None:
    clear_runtimes()
    _remove_sync_handler_if_idle()

@persistent
def _reset_runtimes_before_load(_unused) -> None:
    reset_runtimes()

def register() -> None:
    load_handlers = bpy.app.handlers.load_pre
    if _reset_runtimes_before_load not in load_handlers:
        load_handlers.append(_reset_runtimes_before_load)
    reset_runtimes()

def unregister() -> None:
    reset_runtimes()
    load_handlers = bpy.app.handlers.load_pre
    if _reset_runtimes_before_load in load_handlers:
        load_handlers.remove(_reset_runtimes_before_load)
