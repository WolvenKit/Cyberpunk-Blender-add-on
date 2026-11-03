from __future__ import annotations

import math

from ...domain.animgraph.branch_frames import identity_frame, interpolate_frames
from ...domain.animgraph.switch import (
    SyncEntry,
    selected_input_index,
    switch_state_weights,
    sync_source,
)
from ...model.animgraph.handles import normalized_source_handle
from .base import GraphNodeHandler, execute_child
from .blends import warp_time


class SwitchHandler(GraphNodeHandler):
    kinds = ("SWITCH",)

    def execute(self, context, step):
        step.handle = normalized_source_handle(step.program_node.handle)
        count = min(
            int(
                step.program_node.data.get("numInputs", len(step.program_node.children))
                or 0
            ),
            len(step.program_node.children),
        )
        select_source = step.program_node.data.get("selectSource")
        if select_source:
            raw = 0.0
            if select_source == "int":
                raw = float(
                    int(
                        context.values.linked(
                            "float", step.handle, "selectIntNode", 0.0
                        )
                    )
                )
            elif select_source == "float":
                value = context.values.linked(
                    "float", step.handle, "selectFloatNode", 0.0
                )
                raw = float(
                    math.floor(value + 0.5)
                    if value >= 0.0
                    else -math.floor(-value + 0.5)
                )
            selected = int(raw) if 0 <= int(raw) < count else -1
        else:
            weight = (
                context.values.linked("float", step.handle, "weightNode", 0.0)
                if step.program_node.data.get("hasWeightNode")
                else 0.0
            )
            selected = selected_input_index(weight, count)
        if step.program_node.data.get("pushDataByTag"):
            context._data_flow[step.program_node.data["pushDataByTag"]] = (
                context.values.linked("float", step.handle, "weightNode", 0.0)
                if step.program_node.data.get("hasWeightNode")
                else 0.0
            )
        if selected < 0:
            result = (
                identity_frame(step.input_frame)
                if step.additive_branch
                else context._reference_frame(step.input_frame)
            )
            step.frame_cache[step.cache_key] = result
            return result
        previous = context._switch_selected.get(step.handle)
        duration = float(step.program_node.data.get("blendTime", 0.0))
        if step.program_node.data.get("canRequestInertialization"):
            if previous is not None and previous != selected:
                context._request_inertialization(duration)
            duration = 0.0
        blends = context._switch_blends
        active_inputs = context._switch_active
        prior = (
            (
                previous,
                blends.get(step.handle),
                active_inputs.get(step.handle, frozenset()),
            )
            if step.program_node.data.get("syncMethod")
            else None
        )
        if previous != selected:
            context._switch_selected[step.handle] = selected
            if previous is not None and duration > 0.0:
                blends[step.handle] = previous, duration
            else:
                blends.pop(step.handle, None)
        elif step.handle in blends:
            source, remaining = blends[step.handle]
            remaining = max(
                0.0,
                remaining - max(0.0, float(step.raw_dt) * float(step.time_dilation)),
            )
            if remaining > 1e-8:
                blends[step.handle] = source, remaining
            else:
                blends.pop(step.handle, None)
        source, remaining = blends.get(step.handle, (selected, 0.0))
        alpha = 1.0 - remaining / duration if duration > 0.0 else 1.0
        active = frozenset(
            index
            for index, enabled in ((source, alpha < 1.0), (selected, alpha > 0.0))
            if enabled
        )
        old_active = active_inputs.get(step.handle, frozenset())
        activated = active - old_active
        progress = None
        if activated and prior is not None and prior[2]:
            progress = self._switch_prior_progress(context, step.program_node, *prior)
        for branch in activated:
            context._reset_branch_activation(step.program_node.children[branch])
        if progress is not None:
            for branch in sorted(activated):
                context._sync_branch(step.program_node.children[branch], progress)
        active_inputs[step.handle] = active
        if step.program_node.data.get("timeWarping") and len(active) == 2:
            warp_time(context, step, ((source, 1.0 - alpha), (selected, alpha)))
        frames = {
            branch: execute_child(context, step, branch) for branch in sorted(active)
        }
        if alpha <= 0.0:
            result = frames[source]
        elif alpha >= 1.0:
            result = frames[selected]
        else:
            result = interpolate_frames(frames[source], frames[selected], alpha)
        step.frame_cache[step.cache_key] = result
        return result

    def _switch_prior_progress(self, context, program_node, selected, blend, active):
        """Sync source of a switch's inputs as they stood before this frame's selection"""
        entries: list[SyncEntry] = []
        for index, weight in switch_state_weights(
            float(program_node.data.get("blendTime", 0.0)), selected, blend, active
        ):
            context._gather_sync_entries(program_node.children[index], weight, entries)
        return sync_source(entries, program_node.data.get("syncMethod"))
