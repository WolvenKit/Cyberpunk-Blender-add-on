from __future__ import annotations

from .base import GraphNodeHandler


class WorkspotHubHandler(GraphNodeHandler):
    kinds = ("WORKSPOT_HUB",)

    def execute(self, context, step):
        result = context._execute_workspot_hub(
            step.program_node, step.raw_dt, step.input_frame, step.additive_branch
        )
        step.frame_cache[step.cache_key] = result
        return result
