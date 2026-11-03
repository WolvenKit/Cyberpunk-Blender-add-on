from __future__ import annotations

import bpy

from ...animation.domain.clip.bake import frame_sequence
from ...animation.model.clip.bones import ANIMATION_BONE_SET
from ...blender.animation_context import (
    active_armature,
    track_animation_data,
    track_id_properties,
    track_pose,
    track_scene_frames,
)
from ...blender.bake import sample_pose_bones, write_pose_bone_samples
from ...blender.context import preserved_context, safe_mode_switch
from ...blender.keyframes import assign_action_with_slot
from ...blender.operator_results import OperationResult
from ...blender.selection import select_objects
from ...blender.transactions import (
    new_tracked_datablock,
    track_object_state,
    transactional,
)
from ...core.log import get_logger
from ..blender.rigify import control_bake, forward, pairing
from ..blender.rigify.generated import GeneratedRigBuilder
from ..blender.rigify.metarig import MetarigBuilder, hide_metarig
from ..blender.rigify.state import RigifyBuildSession
from ..model.requests import (
    BAKE_RANGE_ACTION,
    BAKE_RANGE_SCENE,
    RigifyBakeDefaults,
    RigifyBakeRequest,
)

_LOG = get_logger(__name__)
_BLENDER_ERRORS = (
    AttributeError,
    KeyError,
    ReferenceError,
    RuntimeError,
    TypeError,
    ValueError,
)


def linked_pair(context):
    """(source, Rigify rig) for the active armature, or (None, None)"""
    return pairing.find_pair(active_armature(context))


def _active_action(obj):
    animation_data = getattr(obj, "animation_data", None) if obj is not None else None
    return animation_data.action if animation_data is not None else None


def _track_sync_state(source, rig) -> None:
    track_id_properties(source.data, label="Rigify source properties")
    track_pose(source, label="Rigify source pose")
    forward.track_forward_constraints(source)
    forward.track_legacy_reverse_constraints(rig)
    forward.track_follow_bones(rig)


def _bind_follow(source, rig) -> int:
    """Make the source follow the rig, building the rig's follow bones when needed"""
    plan = forward.follow_plan(source, rig)
    if not forward.follow_bones_current(rig, plan):
        forward.build_follow_bones(rig, plan)
    return forward.bind_follow_constraints(source, rig, plan)


def _enable_forward_sync(source, rig, *, recapture_neutral: bool = False) -> int:
    forward.clear_legacy_reverse_constraints(rig)
    if recapture_neutral or not forward.has_forward_neutral_pose(source, rig):
        forward.capture_forward_neutral_pose(source, rig)
    return _bind_follow(source, rig)


def _convert(context, source):
    session = RigifyBuildSession.create(source, context)
    session.log("Converting '%s'", source.name)
    with preserved_context():
        existing_meta = pairing.find_metarig(source)
        existing_rig = pairing.linked_rig_object(source)
        if existing_meta is not None:
            session.meta = existing_meta
            session.log("Reusing metarig '%s'", session.meta.name)
        else:
            builder = MetarigBuilder(session)
            builder.create()
            builder.prepare()

        GeneratedRigBuilder(session).generate(existing_rig=existing_rig)
        meta, rig = session.meta, session.rig

        _track_sync_state(source, rig)
        track_id_properties(meta.data, label="Rigify metarig properties")
        track_id_properties(rig.data, label="Rigify rig properties")
        pairing.link_metadata(source, meta, rig)

        session.log("Binding the source to follow the Rigify rig")
        session.stats["source_sync_bones"] = _enable_forward_sync(
            source, rig, recapture_neutral=True
        )
        safe_mode_switch("OBJECT")

        track_object_state(meta, label="Rigify metarig visibility")
        hide_metarig(meta)
    return rig


@transactional("Rigify generation")
def cp77_to_rigify(context) -> bpy.types.Object | None:
    """Build or refresh the Rigify rig of the active armature"""
    source = active_armature(context)
    if source is None or source.type != "ARMATURE":
        _LOG.warning("Rigify build requires a selected armature")
        return None
    _LOG.info("Converting armature to Rigify: source=%s", source.name)
    try:
        rig = _convert(context, source)
    except Exception:
        _LOG.exception("Rigify conversion failed: source=%s", source.name)
        raise
    _LOG.info("Rigify conversion complete: source=%s rig=%s", source.name, rig.name)
    return rig


def generate(context) -> OperationResult:
    try:
        rig = cp77_to_rigify(context)
    except (KeyError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
        return OperationResult.cancelled(f"Rigify generation failed: {exc}", error=exc)
    if rig is None:
        return OperationResult.cancelled("Select a Cyberpunk armature")
    return OperationResult.finished(
        f"Generated Rigify rig '{rig.name}'",
        rig_name=rig.name,
    )


def sync_enabled(source) -> bool:
    return source is not None and forward.forward_sync_enabled(source)


@transactional("Rigify live sync")
def set_live_sync(
    context,
    *,
    enabled: bool,
    source_name: str = "",
    rigify_name: str = "",
) -> OperationResult:
    """Make the Cyberpunk rig follow the Rigify rig, or release it to play its own action"""
    source = bpy.data.objects.get(source_name) if source_name else None
    rig = bpy.data.objects.get(rigify_name) if rigify_name else None
    if source is None or rig is None:
        source, rig = linked_pair(context)
    if source is None or rig is None:
        return OperationResult.cancelled("Source/Rigify pair not found")
    _track_sync_state(source, rig)
    try:
        with preserved_context():
            if enabled:
                synced = _enable_forward_sync(source, rig)
                return OperationResult(
                    True, f"Cyberpunk rig follows Rigify ({synced} bones)", "INFO"
                )
            forward.clear_forward_constraints(source)
            return OperationResult(True, "Cyberpunk rig plays its own action", "INFO")
    except _BLENDER_ERRORS as exc:
        _LOG.error(
            "Rigify live sync switch failed: source=%s error=%s",
            source.name,
            exc,
            exc_info=True,
        )
        return OperationResult(False, f"Live sync switch failed: {exc}", "ERROR")


@transactional("Activate linked rig")
def activate_linked_rig(context, target_name: str) -> OperationResult:
    target = bpy.data.objects.get(target_name)
    if target is None:
        return OperationResult.cancelled(f"Object '{target_name}' not found")
    track_object_state(target, label="Activated rig visibility")
    safe_mode_switch("OBJECT")
    selected = select_objects(target, reveal=True, context=context)
    if not selected:
        return OperationResult.cancelled(f"Object '{target_name}' is unavailable")
    return OperationResult.finished(
        f"Activated '{target.name}'", target_name=target.name
    )


def bake_defaults(context) -> RigifyBakeDefaults | None:
    source, rig = linked_pair(context)
    action = _active_action(rig)
    if action is None:
        return None
    start, end = map(int, action.frame_range)
    return RigifyBakeDefaults(
        f"{action.name}_baked",
        start,
        end,
        sync_enabled(source),
    )


def _frame_range(context, action, frame_range_source, frame_start, frame_end):
    if frame_range_source == BAKE_RANGE_SCENE:
        return context.scene.frame_start, context.scene.frame_end
    if frame_range_source == BAKE_RANGE_ACTION and action is not None:
        return tuple(map(int, action.frame_range))
    return frame_start, frame_end


def bake_active(
    context,
    *,
    action_name: str,
    overwrite: bool,
    frame_range_source: str,
    frame_start: int,
    frame_end: int,
    step: int,
) -> OperationResult:
    source, rig = linked_pair(context)
    start, end = _frame_range(
        context, _active_action(rig), frame_range_source, frame_start, frame_end
    )
    request = RigifyBakeRequest(
        action_name=action_name,
        overwrite=bool(overwrite),
        frame_start=int(start),
        frame_end=int(end),
        step=max(1, int(step)),
    )
    return bake_to_source(context, source, rig, request)


def _enter_pose_mode(context, obj) -> None:
    try:
        safe_mode_switch("OBJECT")
    except RuntimeError as exc:
        _LOG.debug("Rigify bake continues from %s mode: %s", context.mode, exc)
    if obj.hide_get():
        obj.hide_set(False)
    select_objects(obj, context=context)
    safe_mode_switch("POSE")


def _validate_request(request: RigifyBakeRequest, fallback_name: str):
    if request.frame_end < request.frame_start:
        return None, OperationResult(
            False,
            f"Invalid frame range: {request.frame_start} → {request.frame_end}",
            "ERROR",
        )
    action_name = request.action_name.strip() or fallback_name
    existing = bpy.data.actions.get(action_name)
    if existing is not None and not request.overwrite:
        return None, OperationResult(
            False,
            f"Action '{action_name}' already exists — enable Overwrite to replace",
            "ERROR",
        )
    return (action_name, existing), None


@transactional("Rigify bake")
def bake_to_source(context, source, rig, request: RigifyBakeRequest) -> OperationResult:
    """Bake the Rigify rig's action onto the source's animation bones"""
    if source is None or rig is None:
        return OperationResult(False, "No Rigify pair found for active object", "ERROR")
    rig_action = _active_action(rig)
    if rig_action is None:
        return OperationResult(False, "Rigify rig has no action to bake", "ERROR")
    validated, error = _validate_request(request, f"{rig_action.name}_baked")
    if error is not None:
        return error
    action_name, existing = validated
    present_bones = [
        pose_bone.name
        for pose_bone in source.pose.bones
        if pose_bone.name in ANIMATION_BONE_SET
    ]
    if not present_bones:
        return OperationResult(
            False, "No animation bones present on source rig", "ERROR"
        )

    track_animation_data(source, label="Rigify bake source action")
    track_object_state(source, label="Rigify bake source visibility")
    track_pose(source, label="Rigify bake source pose")
    track_scene_frames(context.scene, label="Rigify bake frame")
    forward.track_forward_constraints(source)
    forward.track_follow_bones(rig)

    target_action = new_tracked_datablock("actions", action_name)
    target_action.use_fake_user = True
    frames = frame_sequence(request.frame_start, request.frame_end, request.step)
    try:
        with preserved_context():
            following = sync_enabled(source)
            if not following:
                _bind_follow(source, rig)
            _enter_pose_mode(context, source)
            assign_action_with_slot(source, target_action)
            # Each frame's followed pose goes into the basis, which the sampler reads.
            samples = sample_pose_bones(
                context.scene,
                source,
                present_bones,
                frames,
                before_sample=lambda _frame: forward.apply_follow_pose(source),
            )
            write_pose_bone_samples(
                target_action,
                source,
                frames,
                samples,
                interpolation="BEZIER",
            )
            if not following:
                forward.clear_forward_constraints(source)
    except (KeyError, RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        _LOG.error(
            "Rigify bake failed: source=%s rig=%s error=%s",
            source.name,
            rig.name,
            exc,
            exc_info=True,
        )
        return OperationResult(False, f"Bake failed: {exc}", "ERROR")

    if existing is not None:
        bpy.data.actions.remove(existing)
        target_action.name = action_name
    return OperationResult(
        True,
        f"Baked '{target_action.name}' ({request.frame_start}→{request.frame_end}, "
        f"step {request.step}, {len(present_bones)} bones). Turn live sync off to play it on the Cyberpunk rig.",
        details={"action": target_action, "bone_count": len(present_bones)},
    )


def source_bake_defaults(context) -> RigifyBakeDefaults | None:
    source, rig = linked_pair(context)
    action = _active_action(source)
    if action is None or rig is None:
        return None
    start, end = map(int, action.frame_range)
    return RigifyBakeDefaults(f"{action.name}_rigify", start, end, sync_enabled(source))


def bake_source_active(
    context,
    *,
    action_name: str,
    overwrite: bool,
    frame_range_source: str,
    frame_start: int,
    frame_end: int,
    step: int,
) -> OperationResult:
    source, rig = linked_pair(context)
    start, end = _frame_range(
        context, _active_action(source), frame_range_source, frame_start, frame_end
    )
    request = RigifyBakeRequest(
        action_name=action_name,
        overwrite=bool(overwrite),
        frame_start=int(start),
        frame_end=int(end),
        step=max(1, int(step)),
    )
    return bake_to_rigify(context, source, rig, request)


@transactional("Rigify control bake")
def bake_to_rigify(context, source, rig, request: RigifyBakeRequest) -> OperationResult:
    """Bake the source's action onto the Rigify controls"""
    if source is None or rig is None:
        return OperationResult(False, "No Rigify pair found for active object", "ERROR")
    source_action = _active_action(source)
    if source_action is None:
        return OperationResult(False, "Cyberpunk rig has no action to bake", "ERROR")
    validated, error = _validate_request(request, f"{source_action.name}_rigify")
    if error is not None:
        return error
    action_name, existing = validated

    track_animation_data(rig, label="Rigify control bake action")
    track_animation_data(source, label="Rigify control bake source action")
    track_object_state(rig, label="Rigify control bake visibility")
    track_pose(rig, label="Rigify control bake pose")
    track_pose(source, label="Rigify control bake source pose")
    track_id_properties(source.data, label="Rigify control bake source properties")
    track_scene_frames(context.scene, label="Rigify control bake frame")
    forward.track_forward_constraints(source)
    forward.track_follow_bones(rig)

    target_action = new_tracked_datablock("actions", action_name)
    target_action.use_fake_user = True
    frames = frame_sequence(request.frame_start, request.frame_end, request.step)
    try:
        with preserved_context():
            # The source plays its own action while the controls are solved from it.
            forward.clear_forward_constraints(source)
            if _active_action(rig) is not None:
                rig.animation_data.action = None
            _enter_pose_mode(context, rig)
            solver = control_bake.ControlSolver.compile(source, rig)
            samples = sample_pose_bones(
                context.scene,
                rig,
                solver.control_names,
                frames,
                before_sample=lambda _frame: solver.solve(),
            )
            assign_action_with_slot(rig, target_action)
            write_pose_bone_samples(
                target_action,
                rig,
                frames,
                samples,
                interpolation="BEZIER",
                include_scale=False,
            )
            solver.key_switches(target_action, frames[0])
            residual = solver.residual_degrees()
            # The Rigify action now carries the clip; live sync shows it on the source, so the source's own action
            # is released (kept by a fake user) rather than evaluated underneath the synced pose.
            source_action.use_fake_user = True
            source.animation_data.action = None
            _enable_forward_sync(source, rig)
    except (KeyError, RuntimeError, ReferenceError, TypeError, ValueError) as exc:
        _LOG.error(
            "Rigify control bake failed: source=%s rig=%s error=%s",
            source.name,
            rig.name,
            exc,
            exc_info=True,
        )
        return OperationResult(False, f"Bake failed: {exc}", "ERROR")

    if existing is not None:
        bpy.data.actions.remove(existing)
        target_action.name = action_name
    return OperationResult(
        True,
        f"Baked '{source_action.name}' onto {len(solver.control_names)} Rigify controls as '{target_action.name}' "
        f"({request.frame_start}→{request.frame_end}, step {request.step}); "
        f"largest last-frame difference {residual:.3f}°. '{source_action.name}' was released from the Cyberpunk rig.",
        details={
            "action": target_action,
            "controls": len(solver.control_names),
            "residual_degrees": residual,
        },
    )
