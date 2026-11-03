from __future__ import annotations

from .base import GraphNodeHandler


class SkAnimHandler(GraphNodeHandler):
    kinds = ("SK_ANIM",)

    def execute(self, context, step):
        if step.program_node.children:
            result = context._execute_one_shot(
                step.program_node,
                step.raw_dt,
                step.time_dilation,
                step.skip_physics,
                step.operation_callback,
                step.frame_cache,
                step.input_frame,
                step.additive_branch,
            )
            step.frame_cache[step.cache_key] = result
            return result
        result = context._sample_source_action(
            step.program_node,
            step.input_frame,
            additive_branch=bool(step.additive_branch),
            raw_dt=step.raw_dt,
        )
        step.frame_cache[step.cache_key] = result
        return result
