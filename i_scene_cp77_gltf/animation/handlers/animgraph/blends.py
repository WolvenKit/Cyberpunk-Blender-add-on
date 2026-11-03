from __future__ import annotations

import math
from time import perf_counter

from ....core.log import get_logger
from ...domain.animgraph.blends import (
    apply_mask_blend,
    blend_activation_transition,
    blend_two_inputs,
    blend_two_weight,
    evaluate_blend_override,
)
from ...domain.animgraph.branch_frames import (
    identity_frame,
    interpolate_frames,
    scope_signature,
)
from ...domain.animgraph.switch import SyncEntry, blend_multiple_selection, sync_source
from ...domain.clip.additive import (
    additive_activation_transition,
    evaluate_blend_additive,
    final_additive_weight,
)
from ...model.animgraph.frames import BranchFrame, TrackSnapshot
from ...model.animgraph.handles import normalized_source_handle
from .base import GraphNodeHandler, execute_child

_LOG = get_logger(__name__)


def warp_time(context, step, inputs) -> None:
    """Time warping"""
    entries: list[SyncEntry] = []
    for index, weight in inputs:
        context._gather_sync_entries(step.program_node.children[index], weight, entries)
    mean_duration = sum(entry.weight * entry.duration for entry in entries)
    warpers = context._time_warp_progress
    progress = float(warpers.get(step.handle, 0.0))
    if mean_duration != 0.0:
        progress = math.fmod(
            progress
            + max(0.0, float(step.raw_dt) * float(step.time_dilation)) / mean_duration,
            1.0,
        )
    warpers[step.handle] = progress
    for index, _weight in inputs:
        context._sync_branch(step.program_node.children[index], progress)


class BlendMaskDynamicHandler(GraphNodeHandler):
    kinds = ("BLEND_MASK_DYNAMIC",)

    def execute(self, context, step):
        step.handle = normalized_source_handle(step.program_node.handle)
        data = step.program_node.data
        weight = (
            min(
                1.0,
                max(0.0, context.values.linked("float", step.handle, "weight", 0.0)),
            )
            if data["hasWeight"]
            else 0.0
        )
        context._blend_weights[step.handle] = (1.0 - weight, weight)
        mask_index = (
            context.values.link(
                "int", context._source_index.get(step.handle, {}), None, "mask", set()
            )
            if data["hasMask"]
            else -1
        )
        masks = data["masks"]
        active = weight > 0.01 and 0 <= mask_index < len(masks)
        states = context._mask_blend_active
        if active and not states.get(step.handle, False):
            context._reset_branch_activation(step.program_node.children[1])
        states[step.handle] = active
        base = execute_child(context, step, 0)
        if not active:
            step.frame_cache[step.cache_key] = base
            return base
        blend = execute_child(context, step, 1)
        part = context._rig_part_mask(masks[mask_index])
        if part is None:
            step.frame_cache[step.cache_key] = base
            return base
        pose = dict(base.pose)
        apply_mask_blend(
            pose,
            blend.pose,
            base.parent_map,
            part[0],
            part[1],
            weight,
            model_space=base.model_space,
        )
        result = BranchFrame(
            pose,
            base.tracks,
            base.parent_map,
            base.reference_pose,
            base.reference_tracks,
            base.transform_scopes,
            base.track_scopes,
            base.model_space,
            ik_targets=base.ik_targets,
        )
        step.frame_cache[step.cache_key] = result
        return result


class BlendMultipleHandler(GraphNodeHandler):
    kinds = ("BLEND_MULTIPLE",)

    def execute(self, context, step):
        step.handle = normalized_source_handle(step.program_node.handle)
        data = step.program_node.data
        weight = (
            context.values.linked("float", step.handle, "weightNode", data["minWeight"])
            if data["hasWeightNode"]
            else data["minWeight"]
        )
        first, second, alpha = blend_multiple_selection(
            data["sortedInputValues"],
            weight,
            data["minWeight"],
            data["maxWeight"],
            data["radialBlending"],
        )
        active = frozenset(
            index
            for index, enabled in ((first, alpha < 1.0), (second, alpha > 0.0))
            if index >= 0 and enabled
        )
        selections = context._blend_multiple_selection
        states = context._blend_multiple_active
        previous_active = states.get(step.handle, frozenset())
        activated = active - previous_active
        sync_method = data.get("syncMethod")
        source = None
        if sync_method and activated and previous_active:
            # Progress is gathered from the previous selection before inputs change, then each
            # new input is synced to it.
            entries: list[SyncEntry] = []
            context._gather_sync_entries(step.program_node, 1.0, entries)
            source = sync_source(entries, sync_method)
        selections[step.handle] = (first, second, alpha)
        weights = [0.0] * len(step.program_node.children)
        for index, share in ((first, 1.0 - alpha), (second, alpha)):
            if 0 <= index < len(weights):
                weights[index] += share
        context._blend_weights[step.handle] = tuple(weights)
        for index in sorted(activated):
            context._reset_branch_activation(step.program_node.children[index])
        if source is not None:
            for index in sorted(activated):
                context._sync_branch(step.program_node.children[index], source)
        elif (
            sync_method and not previous_active and first in active and second in active
        ):
            # On activation the second input is synced to the freshly activated first one.
            entries = []
            context._gather_sync_entries(
                step.program_node.children[first], 1.0, entries
            )
            context._sync_branch(
                step.program_node.children[second], sync_source(entries, sync_method)
            )
        states[step.handle] = active
        if data.get("timeWarping") and first in active and second in active:
            warp_time(context, step, ((first, 1.0 - alpha), (second, alpha)))
        frames = {
            index: execute_child(context, step, index) for index in sorted(active)
        }
        if not frames:
            result = (
                identity_frame(step.input_frame)
                if step.additive_branch
                else context._reference_frame(step.input_frame)
            )
        elif first in frames and second in frames:
            result = interpolate_frames(frames[first], frames[second], alpha)
        else:
            result = next(iter(frames.values()))
        step.frame_cache[step.cache_key] = result
        return result


class BlendTwoHandler(GraphNodeHandler):
    kinds = ("BLEND_TWO",)

    def execute(self, context, step):
        step.handle = normalized_source_handle(step.program_node.handle)
        data = step.program_node.data
        minimum, maximum = float(data["minInputValue"]), float(data["maxInputValue"])
        weight = blend_two_weight(
            context.values.linked("float", step.handle, "weightNode", minimum),
            minimum,
            maximum,
        )
        context._blend_weights[step.handle] = (1.0 - weight, weight)
        active = blend_two_inputs(weight)
        previous = context._blend_two_active.get(step.handle, frozenset())
        activated = active - previous
        sync_method = data.get("syncMethod")
        source = None
        if sync_method and activated and previous:
            # Progress is gathered from the inputs as they played before this frame's weight.
            entries: list[SyncEntry] = []
            context._gather_sync_entries(step.program_node, 1.0, entries)
            source = sync_source(entries, sync_method)
        for index in sorted(activated):
            context._reset_branch_activation(step.program_node.children[index])
        if source is not None:
            for index in sorted(activated):
                context._sync_branch(step.program_node.children[index], source)
        elif sync_method and not previous and len(active) == 2:
            # Both inputs start together: the second is synced to the first.
            entries = []
            context._gather_sync_entries(step.program_node.children[0], 1.0, entries)
            context._sync_branch(
                step.program_node.children[1], sync_source(entries, sync_method)
            )
        context._blend_two_active[step.handle] = active
        context._blend_two_weight[step.handle] = weight
        if data.get("timeWarping") and len(active) == 2:
            warp_time(context, step, ((0, 1.0 - weight), (1, weight)))
        frames = {
            index: execute_child(context, step, index) for index in sorted(active)
        }
        result = (
            frames[0]
            if weight <= 0.0
            else frames[1]
            if weight >= 1.0
            else interpolate_frames(frames[0], frames[1], weight)
        )
        step.frame_cache[step.cache_key] = result
        return result


class BlendOverrideHandler(GraphNodeHandler):
    kinds = ("BLEND_OVERRIDE",)

    def execute(self, context, step):
        base = execute_child(context, step, 0)
        step.handle = normalized_source_handle(step.program_node.handle)
        blend_started = perf_counter()
        control = self._blend_control(context, step.handle)
        context._blend_weights[step.handle] = (1.0 - control, control)
        was_active = bool(context._blend_active.get(step.handle, False))
        active, activated, deactivated = blend_activation_transition(
            was_active, control
        )
        if activated:
            context._reset_branch_activation(step.program_node.children[1])
            _LOG.debug(
                "BlendOverride %s override branch activated at weight %.6f",
                step.handle,
                control,
            )
        elif deactivated:
            _LOG.debug(
                "BlendOverride %s override branch deactivated at weight %.6f",
                step.handle,
                control,
            )
        context._blend_active[step.handle] = active
        if not active:
            context._perf_blend += perf_counter() - blend_started
            step.frame_cache[step.cache_key] = base
            return base
        context._perf_blend += perf_counter() - blend_started
        override = execute_child(context, step, 1)
        blend_started = perf_counter()
        if scope_signature(base) != scope_signature(override):
            raise ValueError(
                f"BlendOverride {step.handle!r} branches produce incompatible pose-stack scopes"
            )
        if base.model_space != override.model_space:
            raise ValueError(
                f"BlendOverride {step.handle!r} branches produce incompatible pose spaces"
            )
        base_pose = dict(base.pose)
        base_tracks = {name: snap.value for name, snap in base.tracks.items()}
        override_tracks = {name: snap.value for name, snap in override.tracks.items()}
        blend_settings = context._blend_data[step.handle]
        if blend_settings.get("blendMethod") == "Mask":
            # The blend method runs first with the control value, then the node's own bone list and tracks.
            part = context._rig_part_mask(blend_settings.get("maskName", ""))
            if part is not None:
                apply_mask_blend(
                    base_pose,
                    override.pose,
                    base.parent_map,
                    part[0],
                    part[1],
                    control,
                    model_space=base.model_space,
                )
        evaluation = evaluate_blend_override(
            base_pose,
            override.pose,
            base_tracks,
            override_tracks,
            context._blend_data[step.handle],
            control,
            parent_map=base.parent_map,
        )
        tracks = dict(base.tracks)
        for name in evaluation.tracks_written:
            before = base.tracks.get(name, TrackSnapshot(False, 0.0))
            other = override.tracks.get(name, TrackSnapshot(False, 0.0))
            tracks[name] = TrackSnapshot(
                before.existed or other.existed, float(base_tracks[name])
            )
        result = BranchFrame(
            base_pose,
            tracks,
            base.parent_map,
            base.reference_pose,
            base.reference_tracks,
            base.transform_scopes,
            base.track_scopes,
            base.model_space,
            ik_targets=base.ik_targets,
        )
        context._perf_blend += perf_counter() - blend_started
        step.frame_cache[step.cache_key] = result
        return result

    def _blend_control(self, context, handle: str) -> float:
        return max(
            0.0, min(1.0, context.values.linked("float", handle, "weightNode", 0.0))
        )


class BlendAdditiveHandler(GraphNodeHandler):
    kinds = ("BLEND_ADDITIVE",)

    def execute(self, context, step):
        base = execute_child(context, step, 0)
        step.handle = normalized_source_handle(step.program_node.handle)
        data = context._additive_data[step.handle]
        blend_started = perf_counter()
        control = context._additive_control(step.handle, data)
        previous_track = str(data.get("previousFrameWeightTrack", "") or "")
        if previous_track:
            snapshot = base.tracks.get(previous_track)
            if snapshot is not None and snapshot.existed:
                context._additive_previous_track_values[step.handle] = float(
                    snapshot.value
                )
        weight = final_additive_weight(
            control, data.get("biasValue", 0.0), data.get("scaleValue", 1.0)
        )
        context._blend_weights[step.handle] = (1.0, weight)
        was_active = bool(context._additive_active.get(step.handle, False))
        active, activated, deactivated = additive_activation_transition(
            was_active, weight
        )
        if activated:
            context._reset_branch_activation(step.program_node.children[1])
            _LOG.debug(
                "BlendAdditive %s additive branch activated at weight %.6f",
                step.handle,
                weight,
            )
        elif deactivated:
            _LOG.debug(
                "BlendAdditive %s additive branch deactivated at weight %.6f",
                step.handle,
                weight,
            )
        context._additive_active[step.handle] = active
        if not active:
            context._perf_blend += perf_counter() - blend_started
            step.frame_cache[step.cache_key] = base
            return base
        context._perf_blend += perf_counter() - blend_started
        additive = execute_child(context, step, 1, additive_branch=True)
        blend_started = perf_counter()
        if scope_signature(base) != scope_signature(additive):
            raise ValueError(
                f"BlendAdditive {step.handle!r} branches produce incompatible pose-stack scopes"
            )
        if base.model_space != additive.model_space:
            raise ValueError(
                f"BlendAdditive {step.handle!r} branches produce incompatible pose spaces"
            )
        base_pose = dict(base.pose)
        base_tracks = {name: snap.value for name, snap in base.tracks.items()}
        additive_tracks = {name: snap.value for name, snap in additive.tracks.items()}
        evaluation = evaluate_blend_additive(
            base_pose,
            additive.pose,
            base_tracks,
            additive_tracks,
            weight=weight,
            additive_type=data.get("additiveType", "AGAT_Local"),
            blend_tracks=data.get("blendTracks", "AGBT_Add"),
            mask_weights=context._additive_masks.get(step.handle),
        )
        tracks = dict(base.tracks)
        for name in evaluation.tracks_written:
            before = base.tracks.get(name, TrackSnapshot(False, 0.0))
            other = additive.tracks.get(name, TrackSnapshot(False, 0.0))
            tracks[name] = TrackSnapshot(
                before.existed or other.existed, float(base_tracks[name])
            )
        result = BranchFrame(
            base_pose,
            tracks,
            base.parent_map,
            base.reference_pose,
            base.reference_tracks,
            base.transform_scopes,
            base.track_scopes,
            base.model_space,
            ik_targets=base.ik_targets,
        )
        context._perf_blend += perf_counter() - blend_started
        step.frame_cache[step.cache_key] = result
        return result
