from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import model_transform


def _clamp_axis(value: float, data: Mapping[str, Any]) -> float:
    result = float(value)
    if bool(data.get("useMin", False)) and result < float(data.get("min", -1.0)):
        result = float(data.get("min", -1.0))
    if bool(data.get("useMax", False)) and result > float(data.get("max", 1.0)):
        result = float(data.get("max", 1.0))
    return result


def _clamp_translation(
    value: QsTransform, axes: Sequence[Mapping[str, Any]]
) -> QsTransform:
    translation = list(value.translation)
    for axis in range(3):
        translation[axis] = _clamp_axis(translation[axis], axes[axis])
    return QsTransform.from_components(translation, value.rotation_xyzw, value.scale)


def evaluate_translation_limit(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> PoseOpEvaluation:
    target = str(data.get("constrainedTransform", "") or "")
    if target not in local_pose:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"constrained transform is absent from the pose: {target or '<empty>'}",
        )
    actual_parent = str(parent_map.get(target, "") or "")
    selected_parent = str(data.get("parentTransform", "") or "")
    if not selected_parent or selected_parent not in local_pose:
        if not actual_parent or actual_parent not in local_pose:
            return PoseOpEvaluation(
                (), applied=False, reason="constrained transform has no valid parent"
            )
        selected_parent = actual_parent

    axes = (
        data.get("limitOnXAxis", {}) or {},
        data.get("limitOnYAxis", {}) or {},
        data.get("limitOnZAxis", {}) or {},
    )
    if model_space:
        parent_ms = local_pose[selected_parent]
        constrained_ls = _clamp_translation(
            relative_to(parent_ms, local_pose[target]), axes
        )
        local_pose[target] = compose(parent_ms, constrained_ls)
        return PoseOpEvaluation((target,))
    if selected_parent == actual_parent:
        local_pose[target] = _clamp_translation(local_pose[target], axes)
        return PoseOpEvaluation((target,))

    try:
        selected_parent_ms = model_transform(
            selected_parent, local_pose, parent_map, {}
        )
        target_ms = model_transform(target, local_pose, parent_map, {})
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transform ancestor is absent from the pose: {name or '<empty>'}",
        )
    selected_local = _clamp_translation(
        relative_to(selected_parent_ms, target_ms), axes
    )
    result_ms = compose(selected_parent_ms, selected_local)
    if actual_parent:
        try:
            actual_parent_ms = model_transform(
                actual_parent, local_pose, parent_map, {}
            )
        except KeyError as exc:
            name = str(exc.args[0] if exc.args else "")
            return PoseOpEvaluation(
                (),
                applied=False,
                reason=f"transform ancestor is absent from the pose: {name or '<empty>'}",
            )
        local_pose[target] = relative_to(actual_parent_ms, result_ms)
    else:
        local_pose[target] = result_ms
    return PoseOpEvaluation((target,))


def _axis_limit_data(value):
    value = value if isinstance(value, Mapping) else {}
    return {
        "useMin": bool(value.get("useMin", False)),
        "useMax": bool(value.get("useMax", False)),
        "min": float(value.get("min", -1.0)),
        "max": float(value.get("max", 1.0)),
    }


def translation_limit_data(node_type, node):
    return {
        "constrainedTransform": index_name(
            node.get("constrainedTransform"), "animTransformIndex", allow_text=True
        ),
        "parentTransform": index_name(
            node.get("parentTransform"), "animTransformIndex", allow_text=True
        ),
        "limitOnXAxis": _axis_limit_data(node.get("limitOnXAxis")),
        "limitOnYAxis": _axis_limit_data(node.get("limitOnYAxis")),
        "limitOnZAxis": _axis_limit_data(node.get("limitOnZAxis")),
    }
