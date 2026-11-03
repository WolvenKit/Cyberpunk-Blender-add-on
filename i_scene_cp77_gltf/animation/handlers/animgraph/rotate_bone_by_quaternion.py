from __future__ import annotations

import numpy as np

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import multiply_scalar_xyzw
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler


class RotateBoneByQuaternionHandler(PoseOpHandler):
    node_types = ("animAnimNode_RotateBoneByQuaternion",)
    bone_fields = ("bone",)
    uses_tracks = False

    def evaluate(self, context, op):
        rotation = context._quaternion_rotations.get(op.handle, (0.0, 0.0, 0.0, 1.0))
        if op.data.get("hasQuaternionNode"):
            value = context.values.linked(
                "quaternion", op.handle, "quaternionNode", (0.0, 0.0, 0.0, 1.0)
            )
            if op.data.get("useIncrementalMode"):
                step = float(context._current_raw_dt)
                increment = np.asarray(
                    (
                        value[0] * step,
                        value[1] * step,
                        value[2] * step,
                        1.0 - step + value[3] * step,
                    )
                )
                increment /= max(float(np.linalg.norm(increment)), 1e-12)
                rotation = multiply_scalar_xyzw(rotation, increment)
            else:
                rotation = tuple(float(v) for v in value)
        else:
            rotation = (0.0, 0.0, 0.0, 1.0)
        context._quaternion_rotations[op.handle] = rotation
        bone = op.data["bone"]
        if (
            bone in op.pose
            and max(
                abs(rotation[0]),
                abs(rotation[1]),
                abs(rotation[2]),
                abs(1.0 - abs(rotation[3])),
            )
            > 1e-6
        ):
            current = op.pose[bone]
            op.pose[bone] = QsTransform(
                current.translation,
                multiply_scalar_xyzw(current.rotation_xyzw, rotation),
                current.scale,
            )
            evaluation = PoseOpEvaluation((bone,))
        else:
            evaluation = PoseOpEvaluation(())
        return evaluation
