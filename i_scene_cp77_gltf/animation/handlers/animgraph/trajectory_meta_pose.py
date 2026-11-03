from __future__ import annotations

from .base import GraphNodeHandler, execute_first_child


class TrajectoryFromMetaPoseHandler(GraphNodeHandler):
    kinds = ("TRAJECTORY_FROM_META_POSE",)

    def execute(self, context, step):
        step.child = execute_first_child(context, step)
        result = context._execute_trajectory_from_meta_pose_frame(
            step.program_node, step.child, step.input_frame
        )
        step.frame_cache[step.cache_key] = result
        return result
