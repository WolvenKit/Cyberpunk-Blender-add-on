from __future__ import annotations

from dataclasses import replace

from ...domain.animgraph.look_at import LookAtControllerState, advance_controller
from ...domain.animgraph.look_at_node import evaluate_look_at_node
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.frames import TrackSnapshot
from ...model.animgraph.handles import normalized_source_handle
from .base import GraphNodeHandler, PoseOpHandler, execute_first_child


class LookAtControllerHandler(GraphNodeHandler):
    kinds = ("LOOK_AT_CONTROLLER",)

    def execute(self, context, step):
        step.handle = normalized_source_handle(step.program_node.handle)
        state = context._look_at_states.setdefault(step.handle, LookAtControllerState())
        data = context._look_at_data.get(step.handle, dict(step.program_node.data))
        context._sync_look_at_request(step.handle, state, data)
        result = execute_first_child(context, step)
        result, values = self._advance_look_at_frame(
            context,
            state,
            data,
            result,
            float(step.raw_dt),
            float(step.raw_dt) * float(step.time_dilation),
        )
        context._internal_graph_inputs.update(values)
        step.frame_cache[step.cache_key] = result
        return result

    def _advance_look_at_frame(self, context, state, data, frame, raw_dt, graph_dt):
        tracks = {
            name: float(snapshot.value) for name, snapshot in frame.tracks.items()
        }
        values = advance_controller(
            state,
            data,
            raw_dt,
            graph_dt,
            pose=frame.pose,
            parent_map=frame.parent_map,
            tracks=tracks,
            model_space=frame.model_space,
            eyes_enabled=float(
                context.feature_values().get(("lookAt", "eyesEnabled"), 1.0)
            ),
        )
        written = {
            name: value
            for name, value in tracks.items()
            if value != frame.tracks[name].value
        }
        if written:
            frame = replace(frame, tracks=dict(frame.tracks))
            for name, value in written.items():
                frame.tracks[name] = TrackSnapshot(frame.tracks[name].existed, value)
        return frame, values


class LookAtHandler(PoseOpHandler):
    node_types = ("animAnimNode_LookAt",)
    bone_fields = ("transform",)
    uses_tracks = False

    def evaluate(self, context, op):
        # The target is the origin and the weight 1 while their nodes are not linked.
        target = (
            context.values.linked("vector", op.handle, "targetNode", (0.0, 0.0, 0.0))
            if op.data.get("hasTargetNode")
            else (0.0, 0.0, 0.0)
        )
        weight = (
            context.values.linked("float", op.handle, "weightNode", 1.0)
            if op.data.get("hasWeightNode")
            else 1.0
        )
        written = evaluate_look_at_node(
            op.pose,
            op.child.parent_map,
            op.data,
            target,
            weight,
            model_space=op.child.model_space,
        )
        return PoseOpEvaluation(written, ())
