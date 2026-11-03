from __future__ import annotations

import math
from collections.abc import Mapping

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import multiply_unit_scalar_xyzw, xyzw_from_euler_xyz
from ...model.animgraph.indices import index_name

PREDICTIVE_LOOK_AT_TRACKS = (
    "predictiveLookAtDirectionX",
    "predictiveLookAtDirectionY",
    "predictiveLookAtDirectionZ",
)


def apply_predictive_look_at_rotation(
    trajectory: QsTransform,
    tracks: Mapping[str, float],
) -> QsTransform:
    if not all(name in tracks for name in PREDICTIVE_LOOK_AT_TRACKS):
        return trajectory

    pitch = float(tracks[PREDICTIVE_LOOK_AT_TRACKS[0]])
    roll = float(tracks[PREDICTIVE_LOOK_AT_TRACKS[1]])
    yaw = float(tracks[PREDICTIVE_LOOK_AT_TRACKS[2]])
    additional = xyzw_from_euler_xyz(
        math.radians(roll),
        math.radians(yaw),
        math.radians(pitch),
    )
    rotation = multiply_unit_scalar_xyzw(additional, trajectory.rotation_xyzw)
    return QsTransform.from_components(
        trajectory.translation, rotation, trajectory.scale
    )


def trajectory_from_meta_pose_data(node):
    return {
        "metaPoseTrajectoryLs": index_name(
            node.get("metaPoseTrajectoryLs"), "animTransformIndex", allow_text=True
        )
    }
