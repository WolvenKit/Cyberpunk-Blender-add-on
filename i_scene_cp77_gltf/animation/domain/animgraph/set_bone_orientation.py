from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence

from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import normalize_xyzw
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, write_model_transform
from .topology import has_link


def evaluate_set_bone_orientation(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    bone: str,
    orientation_ms: Sequence[float] | None,
    *,
    model_space: bool = False,
) -> PoseOpEvaluation:
    """Replace a bone's model-space rotation, keeping its position"""
    if orientation_ms is None or bone not in local_pose:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"bone is absent from the pose: {bone or '<empty>'}",
        )
    try:
        bone_ms = frame_model_transform(bone, local_pose, parent_map, model_space)
    except KeyError as exc:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transform ancestor is absent from the pose: {exc.args[0] if exc.args else ''}",
        )
    rotated = QsTransform.from_components(
        bone_ms.translation, normalize_xyzw(orientation_ms), bone_ms.scale
    )
    write_model_transform(local_pose, parent_map, bone, rotated, model_space)
    return PoseOpEvaluation((bone,))


def set_bone_orientation_data(node_type, node):
    return {
        "bone": index_name(node.get("bone"), "animTransformIndex", allow_text=True),
        "hasOrientation": has_link(node, "orientationMs"),
    }
