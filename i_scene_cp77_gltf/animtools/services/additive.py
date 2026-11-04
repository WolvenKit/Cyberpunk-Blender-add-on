from __future__ import annotations

import bpy

from ...animation.domain.clip.additive import (
    ADDITIVE_STORAGE_REFERENCE_APPLIED,
    normalize_additive_storage,
)
from ...animation.domain.rig.matching import match_action_source_rig
from ...animation.model.clip.metadata import indexed_strings
from ...animation.services.rig.repository import load_rigs
from ...blender.action_metadata import (
    action_is_additive,
    action_playback_frame_bounds,
    action_playback_frame_domain,
    action_skin_extras,
    armature_track_names,
)
from ...blender.animation_context import (
    active_armature,
    track_animation_data,
    track_id_properties,
    track_pose,
    track_scene_frames,
)
from ...blender.identity import rna_is_live
from ...blender.keyframes import action_slot_identity, assign_action_with_slot
from ...blender.operator_results import OperationResult
from ...blender.pose import capture_tracks, reset_pose_bones
from ...blender.rig_metadata import load_rig_part_masks, source_rig_paths
from ...blender.tracks import reference_track_values
from ...blender.transactions import transactional
from ...core.log import get_logger
from ..blender import playback
from ..blender.action_sampling import compile_action_plan
from ..blender.additive_reference import reference_basis_from_rigs
from ..model.additive import (
    ADDITIVE_PREVIEW_SETTINGS,
    ActionListSlot,
    AdditivePreviewOptions,
    AdditiveSlotPlayback,
)
from ..runtime import additive_preview

_LOG = get_logger(__name__)
_PREVIEW_ERRORS = (
    AttributeError,
    KeyError,
    ReferenceError,
    RuntimeError,
    TypeError,
    ValueError,
)


def preview_settings(context):
    scene = getattr(context, "scene", None)
    return (
        getattr(scene, ADDITIVE_PREVIEW_SETTINGS, None) if scene is not None else None
    )


def _base_label(base_action) -> str:
    if not rna_is_live(base_action):
        return "reference pose"
    return f"'{base_action.name}'"


class _SourceRigs:
    """Source rigs of one armature, parsed at most once per configuration build"""

    __slots__ = ("_rigs", "armature")

    def __init__(self, armature):
        self.armature = armature
        self._rigs = None

    def all(self):
        if self._rigs is None:
            paths = source_rig_paths(self.armature)
            if not paths:
                raise ValueError(
                    "Armature has no source rig metadata for additive reference conversion."
                )
            self._rigs = load_rigs(paths)
        return self._rigs

    def for_action(self, action):
        skin = action_skin_extras(action, self.armature)
        return match_action_source_rig(
            self.all(),
            indexed_strings(skin.get("boneNames")),
            str(skin.get("rigPath", "") or ""),
            action.name,
        )


def _mask_weights(armature, mask_name: str):
    if not mask_name:
        return None, None
    masks = load_rig_part_masks(armature)
    if mask_name not in masks:
        return (
            None,
            f"Rig part mask '{mask_name}' is not available on this MetaRig. Reimport the rig with this build if necessary.",
        )
    return dict(masks[mask_name]), None


def _build_entry(
    armature,
    action,
    *,
    slot_index: int,
    mask_name: str,
    storage_mode: str,
    rigs,
    standalone=False,
):
    if not action_is_additive(action):
        return None, f"Action '{action.name}' is not an additive animation."
    plan = compile_action_plan(action, armature)
    if not plan.bones and not plan.tracks:
        return None, f"Action '{action.name}' has no previewable bone or track curves."

    mask_weights, mask_error = _mask_weights(armature, mask_name)
    if mask_error:
        return None, mask_error
    storage_mode = normalize_additive_storage(storage_mode)
    reference_basis = {}
    if (
        storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED
        and plan.bone_names
        and not (standalone and mask_weights is None)
    ):
        try:
            reference_basis = reference_basis_from_rigs(
                armature, (rigs.for_action(action),), plan.bone_names
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            return (
                None,
                f"Could not resolve reference pose for keyed additive bones in Action '{action.name}': {exc}",
            )
    frame_start, frame_end = action_playback_frame_domain(action)
    return additive_preview.AdditiveEntry(
        plan=plan,
        slot_index=slot_index,
        storage_mode=storage_mode,
        mask_name=mask_name,
        mask_weights=mask_weights,
        reference_basis=reference_basis,
        frame_start=frame_start,
        frame_end=frame_end,
    ), None


def _action_at_selector(settings, slot: ActionListSlot):
    if settings is None:
        return None
    index = int(getattr(settings, slot.selector, -1))
    if 0 <= index < len(bpy.data.actions):
        return bpy.data.actions[index]
    return None


def _secondary_entry(
    settings, options: AdditivePreviewOptions, armature, storage_mode: str, rigs
):
    if not options.secondary_enabled:
        return None, None
    action = _action_at_selector(settings, ActionListSlot.SECONDARY)
    if action is None or not action_is_additive(action):
        if options.secondary_action == "NONE":
            return None, "Choose an additive Action for slot 2."
        action = bpy.data.actions.get(options.secondary_action)
        if action is None:
            return (
                None,
                f"Additive slot 2 Action '{options.secondary_action}' was not found.",
            )
    else:
        settings.secondary_action = action.name
    return _build_entry(
        armature,
        action,
        slot_index=1,
        mask_name=options.secondary_mask,
        storage_mode=storage_mode,
        rigs=rigs,
    )


def selected_primary_action(settings, armature):
    action = _action_at_selector(settings, ActionListSlot.PRIMARY)
    if action is not None and action_is_additive(action):
        return action
    session = additive_preview.active_session()
    if (
        session is not None
        and session.armature == armature
        and session.configuration.entries
    ):
        current = session.configuration.entries[0].plan.action
        if rna_is_live(current):
            return current
    return None


def selected_base_action(settings, armature, primary_action):
    action = _action_at_selector(settings, ActionListSlot.NORMAL)
    if (
        action is not None
        and action != primary_action
        and not action_is_additive(action)
    ):
        return action
    active = armature.animation_data.action if armature.animation_data else None
    if (
        active is not None
        and active != primary_action
        and not action_is_additive(active)
    ):
        return active
    return None


def _build_configuration(
    context,
    armature,
    action,
    *,
    force_reference_base=False,
    include_secondary=True,
    standalone=False,
):
    settings = preview_settings(context)
    options = AdditivePreviewOptions.from_settings(settings)
    storage_mode = normalize_additive_storage(options.storage_mode)
    rigs = _SourceRigs(armature)
    base_action = (
        None
        if force_reference_base
        else selected_base_action(settings, armature, action)
    )
    primary, error = _build_entry(
        armature,
        action,
        slot_index=0,
        mask_name=options.primary_mask,
        storage_mode=storage_mode,
        rigs=rigs,
        standalone=standalone,
    )
    if error:
        return None, error

    entries = [primary]
    secondary = None
    if include_secondary:
        secondary, error = _secondary_entry(
            settings, options, armature, storage_mode, rigs
        )
    if error:
        return None, error
    if secondary is not None:
        if secondary.plan.action == action:
            return (
                None,
                "Additive slot 2 must use a different Action from the primary additive Action.",
            )
        if base_action is not None and secondary.plan.action == base_action:
            return (
                None,
                "The normal base Action cannot also be used as additive slot 2.",
            )
        entries.append(secondary)

    base_plan = (
        compile_action_plan(base_action, armature) if base_action is not None else None
    )
    if base_action is not None:
        base_frame_start, base_frame_end = action_playback_frame_domain(base_action)
    else:
        base_frame_start = base_frame_end = 0.0

    additive_bones = set()
    track_names = set(armature_track_names(armature))
    track_names.update(indexed_strings(armature.data.get("trackNames")))
    for entry in entries:
        additive_bones.update(entry.plan.bone_names)
        track_names.update(entry.plan.tracks)
    if base_plan is not None:
        track_names.update(base_plan.tracks)
    track_names = frozenset(track_names)
    reference_tracks = reference_track_values(armature, track_names)

    base_bones = set(additive_bones)
    if base_plan is not None:
        base_bones.update(base_plan.bone_names)
    direct_standalone = (
        standalone
        and primary.storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED
        and primary.mask_weights is None
    )
    if base_action is None and base_bones and not direct_standalone:
        if standalone:
            try:
                reference_basis = reference_basis_from_rigs(
                    armature, (rigs.for_action(action),), base_bones
                )
            except (KeyError, RuntimeError, TypeError, ValueError) as exc:
                return (
                    None,
                    f"Could not resolve standalone additive reference pose for '{action.name}': {exc}",
                )
        else:
            reference_basis = reference_basis_from_rigs(
                armature, rigs.all(), base_bones
            )
    else:
        reference_basis = {}

    frame_start, frame_end = action_playback_frame_bounds(
        base_action if base_action is not None else action
    )
    return additive_preview.PreviewConfiguration(
        entries=tuple(entries),
        base_action=base_action,
        standalone=bool(standalone),
        base_plan=base_plan,
        base_frame_start=base_frame_start,
        base_frame_end=base_frame_end,
        reference_tracks=reference_tracks,
        reference_basis=reference_basis,
        base_bones=frozenset(base_bones),
        track_names=track_names,
        frame_start=frame_start,
        frame_end=frame_end,
    ), None


def _track_preview_state(armature, scene) -> None:
    track_animation_data(armature, label="additive preview Action")
    track_pose(armature, label="additive preview pose")
    track_id_properties(armature, label="additive preview tracks")
    track_scene_frames(scene, label="additive preview frame range")


@transactional("Additive preview reconfiguration")
def reconfigure(context, *, primary_action_name: str | None = None) -> OperationResult:
    session = additive_preview.active_session()
    if session is None:
        return OperationResult(True, "Additive mixer preview is not active")
    if getattr(context, "scene", None) != session.scene:
        return OperationResult(
            False, "Additive mixer belongs to a different scene.", "WARNING"
        )
    armature = active_armature(context)
    if armature is None or armature != session.armature:
        return OperationResult(
            False, "Active armature does not own the additive mixer.", "WARNING"
        )

    standalone = session.configuration.standalone
    if primary_action_name:
        action = bpy.data.actions.get(primary_action_name)
    elif standalone:
        action = session.configuration.entries[0].plan.action
    else:
        action = selected_primary_action(preview_settings(context), armature)
    if action is None or not action_is_additive(action):
        return OperationResult(
            False, "Select an additive Action for the primary additive slot.", "WARNING"
        )

    configuration, error = _build_configuration(
        context,
        armature,
        action,
        force_reference_base=standalone,
        include_secondary=not standalone,
        standalone=standalone,
    )
    if error:
        return OperationResult(False, error, "ERROR")
    _track_preview_state(armature, session.scene)
    additive_preview.track_configuration(session)
    try:
        missing = [
            name
            for name in configuration.track_names
            if name not in session.original_tracks
        ]
        additive_preview.reconfigure(configuration, capture_tracks(armature, missing))
    except _PREVIEW_ERRORS as exc:
        return OperationResult(
            False, f"Could not reconfigure additive preview: {exc}", "ERROR"
        )

    base_label = _base_label(configuration.base_action)
    _LOG.info(
        "Additive mixer preview reconfigured live: base=%s primary=%s",
        base_label,
        action.name,
    )
    return OperationResult(
        True, f"Additive mixer updated to '{action.name}' over {base_label}"
    )


@transactional("Additive preview")
def start(
    context,
    action_name: str,
    *,
    play: bool = True,
    force_reference_base: bool = False,
    include_secondary: bool = True,
    stop_playback: bool = True,
    standalone: bool = False,
) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "ERROR")
    action = bpy.data.actions.get(action_name)
    if action is None:
        return OperationResult(False, f"Action '{action_name}' not found.", "ERROR")
    if not action_is_additive(action):
        return OperationResult(
            False, f"Action '{action.name}' is not additive.", "ERROR"
        )

    session = additive_preview.active_session()
    if session is not None and session.armature == armature:
        if session.configuration.standalone == bool(standalone):
            result = reconfigure(context, primary_action_name=action.name)
            if result.ok and play:
                return playback.start(context, label=f"additive '{action.name}'")
            return result
        additive_preview.clear(restore=True)

    configuration, error = _build_configuration(
        context,
        armature,
        action,
        force_reference_base=force_reference_base,
        include_secondary=include_secondary,
        standalone=standalone,
    )
    if error:
        return OperationResult(False, error, "ERROR")

    if stop_playback:
        stopped = playback.stop(context)
        if not stopped.ok:
            return stopped
    additive_preview.clear(restore=True)

    scene = context.scene
    _track_preview_state(armature, scene)
    additive_preview.track_activation()
    slot_identifier, slot_handle = action_slot_identity(armature.animation_data)
    session = additive_preview.PreviewSession(
        scene=scene,
        armature=armature,
        configuration=configuration,
        original_action=armature.animation_data.action
        if armature.animation_data
        else None,
        original_action_slot_identifier=slot_identifier,
        original_action_slot_handle=slot_handle,
        original_frame_start=int(scene.frame_start),
        original_frame_end=int(scene.frame_end),
        original_frame=int(scene.frame_current),
        original_subframe=float(getattr(scene, "frame_subframe", 0.0)),
        original_pose={
            bone.name: bone.matrix_basis.copy() for bone in armature.pose.bones
        },
        original_rotation_modes={
            bone.name: str(bone.rotation_mode) for bone in armature.pose.bones
        },
        original_tracks=capture_tracks(armature, configuration.track_names),
    )

    if armature.animation_data is None:
        armature.animation_data_create()
    armature.animation_data.action = None
    for name in configuration.base_bones:
        pose_bone = armature.pose.bones.get(name)
        if pose_bone is not None:
            pose_bone.rotation_mode = "QUATERNION"
    reset_pose_bones(armature)
    for name, value in configuration.reference_tracks.items():
        armature[name] = float(value)

    additive_preview.begin(session)
    frame_start, frame_end = configuration.frame_start, configuration.frame_end
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    try:
        if not frame_start <= scene.frame_current <= frame_end:
            scene.frame_set(frame_start)
        additive_preview.apply_active()
    except _PREVIEW_ERRORS as exc:
        additive_preview.clear(restore=True)
        return OperationResult(
            False, f"Could not initialize additive preview: {exc}", "ERROR"
        )

    if play:
        started = playback.start(context, label=f"additive mixer '{action.name}'")
        if not started.ok:
            additive_preview.clear(restore=True)
            return started

    settings = preview_settings(context)
    base_label = _base_label(configuration.base_action)
    entry_labels = []
    timing_labels = []
    for entry in configuration.entries:
        label = f"{entry.plan.action.name} [{entry.storage_mode}]"
        if entry.mask_name:
            label += f" mask={entry.mask_name}"
        entry_labels.append(label)
        timing = AdditiveSlotPlayback.from_settings(settings, entry.slot_index)
        timing_labels.append(
            (entry.slot_index + 1, timing.time_scale, timing.time_offset, timing.loop)
        )
    _LOG.info(
        "Additive mixer preview started: base=%s entries=%s timing=%s",
        base_label,
        tuple(entry_labels),
        tuple(timing_labels),
    )
    return OperationResult(
        True,
        f"Previewing {len(configuration.entries)} additive slot(s) over {base_label}",
    )


def stop(
    context, *, restore: bool = True, stop_playback: bool = True
) -> OperationResult:
    if stop_playback:
        stopped = playback.stop(context)
        if not stopped.ok:
            return stopped
    session = additive_preview.active_session()
    if session is None:
        return OperationResult(True, "Additive mixer preview is not active")
    action_name = session.configuration.entries[0].plan.action.name
    additive_preview.clear(restore=restore)
    _LOG.info("Additive mixer preview stopped: primary=%s", action_name)
    return OperationResult(True, f"Stopped additive mixer preview '{action_name}'")


def mask_changed(context, *, secondary: bool) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature.", "WARNING")
    if additive_preview.is_active(armature):
        return reconfigure(context)
    if secondary:
        return OperationResult(True, "Mask updated")

    settings = preview_settings(context)
    action = selected_primary_action(settings, armature)
    active = armature.animation_data.action if armature.animation_data else None
    if (
        action is None
        or active != action
        or not AdditivePreviewOptions.from_settings(settings).primary_mask
    ):
        return OperationResult(True, "Mask updated")
    return start(
        context,
        action.name,
        play=False,
        force_reference_base=True,
        include_secondary=False,
        stop_playback=False,
        standalone=True,
    )


def storage_changed(context) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Select an armature.", "WARNING")
    if additive_preview.is_active(armature):
        return reconfigure(context)
    settings = preview_settings(context)
    selected = selected_primary_action(settings, armature)
    active = armature.animation_data.action if armature.animation_data else None
    if selected is None or active != selected:
        return OperationResult(True, "Storage updated")
    options = AdditivePreviewOptions.from_settings(settings)
    storage_mode = normalize_additive_storage(options.storage_mode)
    if storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED and not options.primary_mask:
        return OperationResult(True, "Storage updated")
    return start(
        context,
        selected.name,
        play=False,
        force_reference_base=True,
        include_secondary=False,
        stop_playback=False,
        standalone=True,
    )


def set_enabled(context, enabled: bool) -> OperationResult:
    armature = active_armature(context)
    if armature is None:
        return OperationResult(False, "Active object must be an armature.", "WARNING")
    settings = preview_settings(context)
    if not enabled:
        if additive_preview.is_active(armature):
            base_action = selected_base_action(settings, armature, None)
            result = stop(context, restore=True, stop_playback=False)
            if result.ok and base_action is not None:
                if armature.animation_data is None:
                    armature.animation_data_create()
                assign_action_with_slot(armature, base_action)
            return result
        return OperationResult(True, "Additive mixer disabled")

    action = selected_primary_action(settings, armature)
    if action is None:
        return OperationResult(
            False, "Select an additive Action before enabling the mixer.", "WARNING"
        )
    return start(context, action.name, play=False)


def refresh(context) -> None:
    additive_preview.refresh(getattr(context, "scene", None))
