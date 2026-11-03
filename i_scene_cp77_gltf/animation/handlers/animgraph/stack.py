from __future__ import annotations

from time import perf_counter

from .base import GraphNodeHandler


class StackHandler(GraphNodeHandler):
    kind_prefixes = ("STACK_",)
    after_child = True

    def execute(self, context, step):
        node_started = perf_counter()
        result = context._execute_stack_node(step.program_node, step.child)
        context._perf_stack += perf_counter() - node_started
        step.frame_cache[step.cache_key] = result
        return result
