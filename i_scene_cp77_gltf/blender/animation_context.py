from __future__ import annotations

import bpy

from ..core.log import get_logger, log_once
from .identity import rna_identity, rna_is_live
from .keyframes import (
    action_slot_identity,
    assign_action_with_slot,
    capture_fcurves,
    restore_fcurves,
)
from .transactions import restore_id_properties, snapshot_id_properties, track_mutation

_LOG = get_logger(__name__)


def track_animation_import_state(armature):
    """Restore an existing rig's authoring state when an animation transaction fails"""
    if armature is None:
        return
    object_properties = snapshot_id_properties(armature)
    data_properties = snapshot_id_properties(armature.data)
    animation_data = armature.animation_data
    previous_action = animation_data.action if animation_data else None
    previous_slot = getattr(animation_data, "action_slot", None)
    rotation_modes = {bone.name: bone.rotation_mode for bone in armature.pose.bones}

    def restore():
        restore_id_properties(armature, object_properties)
        restore_id_properties(armature.data, data_properties)
        if animation_data is None:
            armature.animation_data_clear()
        else:
            current = armature.animation_data_create()
            current.action = previous_action
            if previous_slot is not None:
                current.action_slot = previous_slot
        for name, mode in rotation_modes.items():
            bone = armature.pose.bones.get(name)
            if bone is not None:
                bone.rotation_mode = mode

    track_mutation(
        ("animation-import-state", rna_identity(armature)),
        restore,
        label=f"Animation import state for {armature.name}",
    )


def scene_frame_rate(scene, fallback: float) -> float:
    render = getattr(scene, "render", None)
    try:
        fps = float(render.fps) / float(render.fps_base)
    except (AttributeError, TypeError, ValueError, ZeroDivisionError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("scene_frame_rate", type(error).__name__),
            "scene frame rate: fell back after %s",
            error,
            exc_info=True,
        )
        return fallback
    return fps if fps > 0.0 else fallback


def local_actions():
    return tuple(action for action in bpy.data.actions if action.library is None)


def active_armature(context):
    obj = getattr(context, "active_object", None)
    return obj if obj is not None and getattr(obj, "type", None) == "ARMATURE" else None


def active_action(context, armature=None):
    obj = armature or active_armature(context)
    animation_data = getattr(obj, "animation_data", None) if obj is not None else None
    return getattr(animation_data, "action", None)


def track_id_properties(owner, *, label="ID properties"):
    """Restore every ID property of owner when the active transaction rolls back"""
    if owner is None:
        return
    snapshot = snapshot_id_properties(owner)

    def restore():
        if rna_is_live(owner):
            restore_id_properties(owner, snapshot)

    track_mutation(("id-properties", rna_identity(owner)), restore, label=label)


def track_animation_data(obj, *, label="animation data"):
    """Restore the object's Action, slot and Action blending when the active transaction rolls back"""
    if obj is None:
        return
    animation_data = obj.animation_data
    if animation_data is None:
        state = None
    else:
        identifier, handle = action_slot_identity(animation_data)
        state = (
            animation_data.action,
            identifier,
            handle,
            animation_data.use_nla,
            animation_data.action_blend_type,
            animation_data.action_influence,
        )

    def restore():
        if not rna_is_live(obj):
            return
        if state is None:
            if obj.animation_data is not None:
                obj.animation_data_clear()
            return
        action, identifier, handle, use_nla, blend_type, influence = state
        data = obj.animation_data or obj.animation_data_create()
        if action is None or not rna_is_live(action):
            data.action = None
        else:
            assign_action_with_slot(
                obj, action, slot_identifier=identifier, slot_handle=handle
            )
        data.use_nla = use_nla
        data.action_blend_type = blend_type
        data.action_influence = influence

    track_mutation(("animation-data", rna_identity(obj)), restore, label=label)


def track_pose(armature, *, label="pose"):
    """Restore rotation modes and basis transforms of every pose bone when the transaction rolls back"""
    if armature is None or armature.pose is None:
        return
    state = tuple(
        (bone.name, bone.rotation_mode, bone.matrix_basis.copy())
        for bone in armature.pose.bones
    )

    def restore():
        if not rna_is_live(armature):
            return
        bones = armature.pose.bones
        for name, mode, matrix in state:
            bone = bones.get(name)
            if bone is not None:
                bone.rotation_mode = mode
                bone.matrix_basis = matrix
        armature.update_tag(refresh={"DATA"})

    track_mutation(("pose", rna_identity(armature)), restore, label=label)


def track_scene_frames(scene, *, label="scene frames"):
    """Restore the scene frame range and current frame when the active transaction rolls back"""
    if scene is None:
        return
    state = (
        int(scene.frame_start),
        int(scene.frame_end),
        int(scene.frame_current),
        float(scene.frame_subframe),
    )

    def restore():
        if not rna_is_live(scene):
            return
        start, end, frame, subframe = state
        scene.frame_start = start
        scene.frame_end = end
        scene.frame_set(frame, subframe=subframe)

    track_mutation(("scene-frames", rna_identity(scene)), restore, label=label)


def track_action_curves(action, id_data, paths=None, *, label="action curves"):
    """Restore the action's curves for paths when the active transaction rolls back"""
    paths = None if paths is None else frozenset(paths)

    def predicate(curve):
        return paths is None or curve.data_path in paths

    snapshots = capture_fcurves(action, id_data, predicate)

    def restore():
        if rna_is_live(action):
            restore_fcurves(action, id_data, predicate, snapshots)

    track_mutation(("action-curves", rna_identity(action), paths), restore, label=label)


def track_fake_user(id_block, *, label="fake user"):
    """Restore an ID's fake-user flag when the active transaction rolls back"""
    if id_block is None:
        return
    state = bool(id_block.use_fake_user)

    def restore():
        if rna_is_live(id_block):
            id_block.use_fake_user = state

    track_mutation(("fake-user", rna_identity(id_block)), restore, label=label)
