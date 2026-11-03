from __future__ import annotations

import numpy as np

from ....bartmoss.qs_transform import QsTransform
from ...domain.animgraph import inertialization
from ...model.animgraph.frames import BranchFrame, TrackSnapshot
from ...model.animgraph.handles import normalized_source_handle
from .base import GraphNodeHandler


class InertializationHandler(GraphNodeHandler):
    kinds = ("INERTIALIZATION",)
    after_child = True

    def execute(self, context, step):
        result = self._execute_inertialization(
            context,
            step.program_node,
            step.child,
            max(0.0, float(step.raw_dt) * float(step.time_dilation)),
        )
        step.frame_cache[step.cache_key] = result
        return result

    def _execute_inertialization(
        self, context, program_node, child: BranchFrame, dt: float
    ) -> BranchFrame:
        handle = normalized_source_handle(program_node.handle)
        data = program_node.data
        state = context._inertialization_states.get(handle)
        if state is None:
            state = context._inertialization_states[handle] = (
                inertialization.InertializationState()
            )
        frame, duration = context._inertialization_request
        inertialization.update(state, dt, frame == context._perf_frames, duration)
        names = list(child.pose)
        bone_cap = int(data.get("transformsCountUpperBound", 0) or 0)
        names = names[:bone_cap] if bone_cap > 0 else names
        track_names = list(child.tracks)
        track_cap = int(data.get("tracksCountUpperBound", 0) or 0)
        track_names = track_names[:track_cap] if track_cap > 0 else track_names
        translations = np.asarray(
            [child.pose[name].translation for name in names], dtype=np.float64
        ).reshape(-1, 3)
        rotations = np.asarray(
            [child.pose[name].rotation_xyzw for name in names], dtype=np.float64
        ).reshape(-1, 4)
        tracks = np.asarray(
            [child.tracks[name].value for name in track_names], dtype=np.float64
        )
        # The trajectory bone is taken out before and put back after.
        trajectory = names.index("Trajectory") if "Trajectory" in names else -1
        if trajectory >= 0:
            saved = translations[trajectory].copy(), rotations[trajectory].copy()
            translations[trajectory] = 0.0
            rotations[trajectory] = (0.0, 0.0, 0.0, 1.0)
        translations, rotations, tracks = inertialization.sample(
            state,
            translations,
            rotations,
            tracks,
            data,
            names,
        )
        if trajectory >= 0:
            translations[trajectory], rotations[trajectory] = saved
        pose = dict(child.pose)
        for row, name in enumerate(names):
            current = pose[name]
            pose[name] = QsTransform(
                tuple(translations[row].tolist()),
                tuple(rotations[row].tolist()),
                current.scale,
            )
        track_values = dict(child.tracks)
        for row, name in enumerate(track_names):
            track_values[name] = TrackSnapshot(
                track_values[name].existed, float(tracks[row])
            )
        return BranchFrame(
            pose,
            track_values,
            child.parent_map,
            child.reference_pose,
            child.reference_tracks,
            child.transform_scopes,
            child.track_scopes,
            child.model_space,
            ik_targets=child.ik_targets,
        )
