from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

import numpy as np

from ....assetio.transform_values import qs_transform_from_data
from ....bartmoss.qs_transform import QsTransform, compose, interpolate_qs
from ....bartmoss.quaternion import (
    aligned_xyzw,
    multiply_scalar_xyzw,
    normalize_xyzw,
    rotate_vector_unit_scalar_xyzw,
)
from ....redSpace.euler import xyzw_from_euler
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform, write_model_transform
from .source_channels import constraint_weight
from .topology import has_link


def evaluate_parent_constraint(
    local_pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    reference_pose: Mapping[str, QsTransform],
    data: Mapping[str, Any],
    weight: float,
    *,
    offset_translation: Sequence[float] | None = None,
    offset_euler: Sequence[float] | None = None,
    model_space: bool = False,
) -> PoseOpEvaluation:
    """Move a bone onto a ParentConstraint's parent transform in model space"""
    target = str(data.get("transformIndex", "") or "")
    parent = str(data.get("parentTransformIndex", "") or "")
    weight = float(weight)
    if not weight > 0.0:
        return PoseOpEvaluation((), applied=False, reason="nonpositive weight")
    if target not in local_pose or parent not in local_pose:
        return PoseOpEvaluation(
            (),
            applied=False,
            reason="constrained or parent transform is absent from the pose",
        )
    try:
        parent_ms = frame_model_transform(parent, local_pose, parent_map, model_space)
        output_ms = frame_model_transform(target, local_pose, parent_map, model_space)
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transform ancestor is absent from the pose: {name}",
        )
    if bool(data.get("useBoneReferencePoseAsDefaultOffset", False)):
        # The default offset is the bone's reference transform relative to its rig parent.
        if str(parent_map.get(target, "") or "") and target in reference_pose:
            parent_ms = compose(parent_ms, reference_pose[target])
    if weight < 1.0:
        output_ms = interpolate_qs(
            output_ms, parent_ms, weight, data.get("interpolationType", "Slerp")
        )
    else:
        output_ms = parent_ms
    if offset_euler is not None:
        # The vector input carries (pitch, roll, yaw) in its X, Y, Z components.
        offset = xyzw_from_euler(
            float(offset_euler[0]), float(offset_euler[1]), float(offset_euler[2])
        )
        output_ms = QsTransform.from_components(
            output_ms.translation,
            multiply_scalar_xyzw(output_ms.rotation_xyzw, offset),
            output_ms.scale,
        )
    if offset_translation is not None:
        moved = rotate_vector_unit_scalar_xyzw(
            output_ms.rotation_xyzw, tuple(float(v) for v in offset_translation[:3])
        )
        tx, ty, tz = output_ms.translation
        output_ms = QsTransform.from_components(
            (tx + moved[0], ty + moved[1], tz + moved[2]),
            output_ms.rotation_xyzw,
            output_ms.scale,
        )
    write_model_transform(local_pose, parent_map, target, output_ms, model_space)
    return PoseOpEvaluation((target,))


def _parent_info_weight(info: Mapping[str, Any], tracks: Mapping[str, float]) -> float:
    raw = constraint_weight(
        str(info.get("parentWeightMode", "Static") or "Static"),
        float(info.get("parentStaticWeight", 1.0)),
        str(info.get("parentTrackWeight", "") or ""),
        tracks,
    )
    return 1.0 - raw if bool(info.get("useComplementWeight", False)) else raw


def evaluate_multiple_parent_constraint(
    local_pose: MutableMapping[str, QsTransform],
    tracks: Mapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> PoseOpEvaluation:
    """Blend a bone toward a MultipleParentConstraint's weighted mix of parents"""
    target = str(data.get("transformIndex", "") or "")
    infos = tuple(data.get("parentsTransforms", ()) or ())
    weight = constraint_weight(
        str(data.get("weightMode", "Static") or "Static"),
        float(data.get("weight", 1.0)),
        str(data.get("weightFloatTrack", "") or ""),
        tracks,
    )
    if not weight > 0.0 or not infos:
        return PoseOpEvaluation((), applied=False, reason="nonpositive weight")
    if target not in local_pose:
        return PoseOpEvaluation(
            (), applied=False, reason="constrained transform is absent from the pose"
        )
    interpolation = data.get("interpolationType", "Slerp")

    def parent_model(info) -> QsTransform | None:
        name = str(info.get("parentTransform", "") or "")
        if name not in local_pose:
            return None
        try:
            value = frame_model_transform(name, local_pose, parent_map, model_space)
        except KeyError:
            return None
        if bool(info.get("useOffset", False)):
            value = compose(value, qs_transform_from_data(info.get("offset")))
        return value

    # An unresolved parent contributes the identity transform.
    parent_ms = QsTransform.identity()
    if len(infos) == 1:
        a = parent_model(infos[0])
        if a is not None:
            t = _parent_info_weight(infos[0], tracks)
            parent_ms = (
                interpolate_qs(QsTransform.identity(), a, t, interpolation)
                if t < 1.0
                else a
            )
    elif len(infos) == 2:
        a, b = parent_model(infos[0]), parent_model(infos[1])
        if a is not None and b is not None:
            wa, wb = (
                _parent_info_weight(infos[0], tracks),
                _parent_info_weight(infos[1], tracks),
            )
            t = wb / (wa + wb) if wa + wb > 0.0 else 0.0
            parent_ms = interpolate_qs(a, b, t, interpolation) if t < 1.0 else b
    else:
        models = [parent_model(info) for info in infos]
        if all(model is not None for model in models):
            # Weighted accumulation with sign-aligned rotations, then renormalized.
            total = 0.0
            translation = np.zeros(3)
            scale = np.zeros(3)
            rotation = np.zeros(4)
            for info, model in zip(infos, models):
                w = _parent_info_weight(info, tracks)
                total += w
                translation += np.asarray(model.translation, dtype=np.float64) * w
                scale += np.asarray(model.scale, dtype=np.float64) * w
                rotation += aligned_xyzw(rotation, model.rotation_xyzw) * w
            if total > 1e-12:
                parent_ms = QsTransform.from_components(
                    translation / total,
                    normalize_xyzw(rotation),
                    scale / total,
                )
    try:
        current = frame_model_transform(target, local_pose, parent_map, model_space)
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return PoseOpEvaluation(
            (),
            applied=False,
            reason=f"transform ancestor is absent from the pose: {name}",
        )
    output_ms = (
        interpolate_qs(current, parent_ms, weight, interpolation)
        if weight < 1.0
        else parent_ms
    )
    write_model_transform(local_pose, parent_map, target, output_ms, model_space)
    return PoseOpEvaluation((target,))


def parent_constraint_data(node_type, node):
    parent = index_name(
        node.get("parentTransformIndex"), "animTransformIndex", allow_text=True
    )
    legacy = node.get("parentTransform")
    if not bool(node.get("isParentTransformResaved", False)) and isinstance(
        legacy, Mapping
    ):
        # An unresaved node names its parent in the legacy source channel.
        legacy_data = (
            legacy.get("Data") if isinstance(legacy.get("Data"), Mapping) else legacy
        )
        parent = (
            index_name(
                legacy_data.get("transformIndex"), "animTransformIndex", allow_text=True
            )
            or parent
        )
    return {
        "transformIndex": index_name(
            node.get("transformIndex"), "animTransformIndex", allow_text=True
        ),
        "parentTransformIndex": parent,
        "interpolationType": str(node.get("interpolationType", "Slerp") or "Slerp"),
        "weight": float(
            node.get("weight", 1.0) if node.get("weight") is not None else 1.0
        ),
        "weightFloatTrack": index_name(
            node.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "useBoneReferencePoseAsDefaultOffset": bool(
            node.get("useBoneReferencePoseAsDefaultOffset", False)
        ),
        "hasWeightNode": has_link(node, "weightNode"),
        "hasOffsetTranslation": has_link(node, "offsetTranslationLS"),
        "hasOffsetRotation": has_link(node, "offsetEulerRotationLS"),
    }


def multiple_parent_constraint_data(node_type, node):
    resaved = bool(node.get("areSourceChannelsResaved", False))
    current = [
        raw for raw in node.get("parentsTransforms") or () if isinstance(raw, Mapping)
    ]
    if resaved:
        sources = current
    else:
        # An unresaved node holds one legacy source channel per parent.
        legacy_transforms = list(node.get("parentsTransform") or ())
        legacy_weights = list(node.get("parentsWeight") or ())
        sources = []
        for index, wrapper in enumerate(legacy_transforms):
            base = dict(current[index]) if index < len(current) else {}
            channel = (
                wrapper.get("Data")
                if isinstance(wrapper, Mapping)
                and isinstance(wrapper.get("Data"), Mapping)
                else {}
            )
            if channel:
                base["parentTransform"] = channel.get("transformIndex")
            weight_wrapper = (
                legacy_weights[index] if index < len(legacy_weights) else None
            )
            weight_data = (
                weight_wrapper.get("Data")
                if isinstance(weight_wrapper, Mapping)
                and isinstance(weight_wrapper.get("Data"), Mapping)
                else {}
            )
            if weight_data:
                track = index_name(
                    weight_data.get("floatTrack"),
                    "animNamedTrackIndex",
                    allow_text=True,
                )
                base["parentWeightMode"] = "FloatTrack" if track else "Static"
                base["parentTrackWeight"] = weight_data.get("floatTrack")
                base["useComplementWeight"] = weight_data.get(
                    "useComplementValue", False
                )
            sources.append(base)
    infos = tuple(
        {
            "parentTransform": index_name(
                raw.get("parentTransform"), "animTransformIndex", allow_text=True
            ),
            "parentWeightMode": str(raw.get("parentWeightMode", "Static") or "Static"),
            "parentStaticWeight": float(
                raw.get("parentStaticWeight", 1.0)
                if raw.get("parentStaticWeight") is not None
                else 1.0
            ),
            "parentTrackWeight": index_name(
                raw.get("parentTrackWeight"), "animNamedTrackIndex", allow_text=True
            ),
            "useComplementWeight": bool(raw.get("useComplementWeight", False)),
            "useOffset": bool(raw.get("useOffset", False)),
            "offset": raw.get("offset") or {},
        }
        for raw in sources
    )
    weight_track = index_name(
        node.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=True
    )
    if resaved:
        weight_mode = str(node.get("weightMode", "Static") or "Static")
    else:
        weight_mode = "FloatTrack" if weight_track else "Static"
    return {
        "transformIndex": index_name(
            node.get("transformIndex"), "animTransformIndex", allow_text=True
        ),
        "parentsTransforms": infos,
        "interpolationType": str(node.get("interpolationType", "Slerp") or "Slerp"),
        "weightMode": weight_mode,
        "weight": float(
            node.get("weight", 1.0) if node.get("weight") is not None else 1.0
        ),
        "weightFloatTrack": weight_track,
    }
