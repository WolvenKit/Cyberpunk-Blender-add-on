from __future__ import annotations

from ....bartmoss.qs_transform import QsTransform
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name


def evaluate_suspension_limit(pose, reference_pose, tracks, data) -> PoseOpEvaluation:
    name = str(data.get("constrainedTransform", "") or "")
    radius_name = str(data.get("radiusTrack", "") or "")
    deviation_name = str(data.get("deviationTrack", "") or "")
    if name not in pose or name not in reference_pose:
        return PoseOpEvaluation(
            (), (), False, "constrained transform is absent from the pose"
        )
    if radius_name not in tracks or deviation_name not in tracks:
        return PoseOpEvaluation((), (), False, "target track is absent")
    axis = str(data.get("axis", "X") or "X").split("::")[-1]
    component = {
        "X": 0,
        "NegativeX": 0,
        "Y": 1,
        "NegativeY": 1,
        "Z": 2,
        "NegativeZ": 2,
    }.get(axis)
    if component is None:
        raise ValueError(f"Unsupported SuspensionLimit axis {axis!r}")
    radius = abs(float(tracks[radius_name]))
    reference = float(reference_pose[name].translation[component])
    value = reference + float(tracks[deviation_name])
    if component == 2:
        lower, upper = (-5.0, 2.0) if reference < 0.0 else (-2.0, 5.0)
        lower, upper = reference + lower * radius, reference + upper * radius
    else:
        sign = 1.0 if reference >= 0.0 else -1.0
        lower, upper = reference + sign * radius, reference - sign * radius
    transform = pose[name]
    translation = list(transform.translation)
    translation[component] = min(max(value, lower), upper)
    pose[name] = QsTransform.from_components(
        translation, transform.rotation_xyzw, transform.scale
    )
    return PoseOpEvaluation((name,))


def suspension_limit_data(node_type, node):
    return {
        "constrainedTransform": index_name(
            node.get("constrainedTransform"), "animTransformIndex", allow_text=True
        ),
        "radiusTrack": index_name(
            node.get("radiusTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "deviationTrack": index_name(
            node.get("deviationTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "axis": str(node.get("axis", "X") or "X"),
    }
