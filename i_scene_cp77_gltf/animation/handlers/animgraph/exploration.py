from __future__ import annotations

from .base import GraphNodeHandler


class NpcExplorationHandler(GraphNodeHandler):
    kinds = ("NPC_EXPLORATION",)

    def execute(self, context, step):
        result = context._execute_npc_exploration(
            step.program_node, step.raw_dt, step.input_frame, step.additive_branch
        )
        step.frame_cache[step.cache_key] = result
        return result
