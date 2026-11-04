from __future__ import annotations

from time import perf_counter

from .base import GraphNodeHandler


class PoseLsToMsHandler(GraphNodeHandler):
    kinds = ("POSE_LS_TO_MS",)
    after_child = True

    def execute(self, context, step):
        started = perf_counter()
        result = context._pose_ls_to_ms(step.child)
        context._perf_pose_space += perf_counter() - started
        step.frame_cache[step.cache_key] = result
        return result


class PoseMsToLsHandler(GraphNodeHandler):
    kinds = ("POSE_MS_TO_LS",)
    after_child = True

    def execute(self, context, step):
        started = perf_counter()
        result = context._pose_ms_to_ls(step.child)
        context._perf_pose_space += perf_counter() - started
        step.frame_cache[step.cache_key] = result
        return result
