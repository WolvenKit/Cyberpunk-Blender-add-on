from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from ....bartmoss.qs_transform import (
    QsTransform,
    compose,
    relative_to,
    translation_only,
    without_translation,
)
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, model_transform


def evaluate_set_bone_transform(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    reference_pose_ms: Mapping[str, QsTransform],
    entries: Sequence[Mapping[str, Any]],
    *,
    model_space: bool = False,
) -> PoseOpEvaluation:
    targets = tuple(str(entry.get("transformToChange", "") or "") for entry in entries)
    missing_target = next((name for name in targets if name not in local_pose), "")
    if missing_target or any(not name for name in targets):
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transformToChange is absent from the pose: {missing_target or '<empty>'}",
        )

    written: list[str] = []
    for entry, target in zip(entries, targets):
        method = str(entry.get("setMethod", "WholeTransform") or "WholeTransform")
        source = str(entry.get("sourceBone", "") or "")
        if (
            model_space
            and bool(entry.get("_fastModelSourceOffset", False))
            and source in local_pose
        ):
            offset = entry["_offsetQs"]
            local_pose[target] = compose(local_pose[source], offset)
            if target not in written:
                written.append(target)
            continue
        if method != "NoSnapping" and source in local_pose:
            try:
                snap_ms = (
                    reference_pose_ms[source]
                    if bool(entry.get("snapToReference", False))
                    else (
                        frame_model_transform(
                            source, local_pose, parent_map, model_space
                        )
                    )
                )
            except KeyError:
                snap_ms = None
            if snap_ms is not None:
                parent = str(parent_map.get(target, "") or "")
                snap_local = (
                    snap_ms
                    if model_space
                    else (
                        relative_to(
                            model_transform(parent, local_pose, parent_map, {}), snap_ms
                        )
                        if parent
                        else snap_ms
                    )
                )
                current = local_pose[target]
                if method == "WholeTransform":
                    local_pose[target] = snap_local
                elif method == "TranslationOnly":
                    local_pose[target] = QsTransform.from_components(
                        snap_local.translation, current.rotation_xyzw, current.scale
                    )
                elif method == "RotationOnly":
                    local_pose[target] = QsTransform.from_components(
                        current.translation, snap_local.rotation_xyzw, current.scale
                    )
                else:
                    return PoseOpEvaluation(
                        tuple(written),
                        applied=False,
                        reason=f"unsupported SetBoneTransform setMethod: {method}",
                    )

        offset_space = str(entry.get("offsetSpaceBone", "") or "")
        if offset_space in local_pose:
            try:
                offset_space_ms = (
                    reference_pose_ms[offset_space]
                    if bool(entry.get("offsetToReference", False))
                    else (
                        frame_model_transform(
                            offset_space, local_pose, parent_map, model_space
                        )
                    )
                )
                current_ms = frame_model_transform(
                    target, local_pose, parent_map, model_space
                )
            except KeyError:
                offset_space_ms = current_ms = None
            if offset_space_ms is not None and current_ms is not None:
                current_offset_space = relative_to(offset_space_ms, current_ms)
                offset = entry["_offsetQs"]
                translation_part = compose(
                    translation_only(offset), current_offset_space
                )
                rotation_scale_part = compose(
                    without_translation(offset),
                    without_translation(current_offset_space),
                )
                combined = QsTransform.from_components(
                    translation_part.translation,
                    rotation_scale_part.rotation_xyzw,
                    rotation_scale_part.scale,
                )
                result_ms = compose(offset_space_ms, combined)
                parent = str(parent_map.get(target, "") or "")
                local_pose[target] = (
                    result_ms
                    if model_space
                    else (
                        relative_to(
                            model_transform(parent, local_pose, parent_map, {}),
                            result_ms,
                        )
                        if parent
                        else result_ms
                    )
                )
        if target not in written:
            written.append(target)
    return PoseOpEvaluation(tuple(written))


def set_bone_transform_data(node_type, node):
    entries = []
    for raw in node.get("entries") or ():
        if not isinstance(raw, Mapping):
            continue
        entries.append(
            {
                "transformToChange": index_name(
                    raw.get("transformToChange"), "animTransformIndex", allow_text=True
                ),
                "setMethod": str(
                    raw.get("setMethod", "WholeTransform") or "WholeTransform"
                ),
                "snapToReference": bool(raw.get("snapToReference", False)),
                "sourceBone": index_name(
                    raw.get("sourceBone"), "animTransformIndex", allow_text=True
                ),
                "offsetToReference": bool(raw.get("offsetToReference", False)),
                "offsetSpaceBone": index_name(
                    raw.get("offsetSpaceBone"), "animTransformIndex", allow_text=True
                ),
                "offset": raw.get("offset") or {},
            }
        )
    return {"entries": tuple(entries)}
