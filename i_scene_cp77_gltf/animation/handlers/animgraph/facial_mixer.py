from __future__ import annotations

from ...domain.animgraph.facial_mixer import FacialMixerState
from ...model.animgraph.handles import normalized_source_handle
from .base import GraphNodeHandler, execute_first_child


class FacialMixerHandler(GraphNodeHandler):
    kinds = ("FACIAL_MIXER",)

    def execute(self, context, step):
        result = execute_first_child(context, step)
        step.handle = normalized_source_handle(step.program_node.handle)
        state = context._facial_mixer_states.setdefault(step.handle, FacialMixerState())
        result = context._advance_facial_mixer_frame(
            state,
            context._facial_mixer_data.get(step.handle, dict(step.program_node.data)),
            result,
            float(step.raw_dt) * float(step.time_dilation),
        )
        step.frame_cache[step.cache_key] = result
        return result
