from __future__ import annotations

from time import perf_counter

from ...domain.animgraph.branch_frames import scope_signature
from ...model.animgraph.frames import BranchFrame
from .base import GraphNodeHandler


class FacialSharedMetaPoseHandler(GraphNodeHandler):
    kinds = ("FACIAL_SHARED_META_POSE",)

    def execute(self, context, step):
        if step.input_frame.model_space:
            raise ValueError("FacialSharedMetaPose requires a local-space input pose")
        binding = context._facial_binding
        shared = context._shared_meta_binding
        if binding is None or shared is None:
            raise ValueError(
                "FacialSharedMetaPose requires bound facial and parent-pose contexts"
            )
        names = frozenset(binding.bone_names[:32]) - {""}
        narrow = BranchFrame(
            {
                name: value
                for name, value in step.input_frame.pose.items()
                if name in names
            },
            dict(step.input_frame.tracks),
            {
                name: parent
                for name, parent in step.input_frame.parent_map.items()
                if name in names and parent in names
            },
            {
                name: value
                for name, value in step.input_frame.reference_pose.items()
                if name in names
            },
            step.input_frame.reference_tracks,
            step.input_frame.transform_scopes,
            step.input_frame.track_scopes,
            ik_targets=step.input_frame.ik_targets,
        )
        step.child = (
            context._execute_program(
                step.program_node.children[0],
                step.raw_dt,
                step.time_dilation,
                step.skip_physics,
                step.operation_callback,
                {},
                narrow,
                step.additive_branch,
            )
            if step.program_node.children
            else narrow
        )
        if step.child.model_space or scope_signature(step.child) != scope_signature(
            narrow
        ):
            raise ValueError(
                "FacialSharedMetaPose input must restore its local pose-stack scope"
            )
        pose = dict(step.input_frame.reference_pose)
        pose.update(
            {name: value for name, value in step.child.pose.items() if name in names}
        )
        parent_frame = context._meta_parent_frame_current or step.input_frame
        parent_pose = (
            context._facial_shared_parent_pose(parent_frame)
            if context._facial_binding is not None and context._owner_scope_bound
            else parent_frame.pose
        )
        excluded = frozenset(
            bone
            for name in ("Neck", "Neck1", "Head")
            if (bone := context.host.resolve_bone(name)) is not None
        )
        for name in shared.transform_names:
            if name in pose and name in parent_pose and name not in excluded:
                pose[name] = parent_pose[name]
        tracks = dict(step.child.tracks)
        for name in shared.track_names:
            if name in tracks and name in parent_frame.tracks:
                tracks[name] = parent_frame.tracks[name]
        result = BranchFrame(
            pose,
            tracks,
            step.input_frame.parent_map,
            step.input_frame.reference_pose,
            step.input_frame.reference_tracks,
            step.input_frame.transform_scopes,
            step.input_frame.track_scopes,
            ik_targets=step.input_frame.ik_targets,
        )
        context._trace_facial_frame("facial_shared_meta_output", result)
        step.frame_cache[step.cache_key] = result
        return result


class SharedMetaPoseHandler(GraphNodeHandler):
    kinds = ("SHARED_META_POSE", "SHARED_META_POSE_ADDITIVE")
    after_child = True

    def execute(self, context, step):
        shared_started = perf_counter()
        result = context._execute_shared_meta_frame(
            step.program_node,
            step.child,
            step.input_frame,
            additive=step.program_node.kind == "SHARED_META_POSE_ADDITIVE",
        )
        context._perf_shared_meta += perf_counter() - shared_started
        step.frame_cache[step.cache_key] = result
        return result
