from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

import numpy as np

from ....assetio.values import cname_or_empty
from ....bartmoss.qs_transform import QsTransform, blend_qs, relative_to
from ....bartmoss.scalar import lerp
from ...model.animgraph.evaluation import PoseOpEvaluation
from ...model.animgraph.indices import index_name
from ..clip.additive import normalize_additive_type, normalize_track_mode
from .pose_space import frame_model_transform
from .switch import sync_method_type
from .topology import PreviewBoundary, has_link, linked_node, resolve


def evaluate_blend_override(
    base_pose: MutableMapping[str, QsTransform],
    override_pose: Mapping[str, QsTransform],
    base_tracks: MutableMapping[str, float],
    override_tracks: Mapping[str, float],
    data: Mapping[str, Any],
    control_value: float,
    *,
    parent_map: Mapping[str, str] | None = None,
) -> PoseOpEvaluation:
    control = min(1.0, max(0.0, float(control_value)))
    if control <= 0.01:
        return PoseOpEvaluation((), (), False, "below activation threshold")

    bones = data.get("bones", ()) or ()
    if data.get("blendMethod") == "BoneBranch":
        overrides = {
            str(item.get("bone", "")): float(item.get("weight", 1.0)) for item in bones
        }
        expanded = []
        parents = parent_map or {}
        for name in base_pose:
            current = name
            seen = set()
            while current and current not in overrides:
                if current in seen:
                    raise ValueError(
                        f"Cycle in BlendOverride bone hierarchy at {current!r}"
                    )
                seen.add(current)
                current = str(parents.get(current, "") or "")
            if current in overrides:
                expanded.append({"bone": name, "weight": overrides[current]})
        bones = expanded
    written_bones: list[str] = []
    for item in bones:
        name = str(
            item.get("bone", item.get("transform", item.get("transformIndex", "")))
            or ""
        )
        if not name or name not in base_pose or name not in override_pose:
            continue
        weight = float(item.get("weight", 1.0)) * control
        if weight == 0.0 or (weight < 0.0 and data.get("blendMethod") != "BoneBranch"):
            continue
        base_pose[name] = blend_qs(base_pose[name], override_pose[name], weight)
        written_bones.append(name)

    written_tracks: list[str] = []
    if bool(data.get("blendAllTracks", False)):
        for name in tuple(base_tracks):
            if name not in override_tracks:
                continue
            base_tracks[name] = float(
                lerp(base_tracks[name], override_tracks[name], control)
            )
            written_tracks.append(name)
    else:
        mode = str(data.get("blendTrackMode", "AGBT_Interpolate") or "AGBT_Interpolate")
        for item in data.get("tracks", ()) or ():
            name = str(item.get("track", item.get("trackIndex", "")) or "")
            if not name or name not in base_tracks or name not in override_tracks:
                continue
            weight = float(item.get("weight", 1.0)) * control
            if mode in {"AGBT_Interpolate", "Interpolate"}:
                base_tracks[name] = float(
                    lerp(base_tracks[name], override_tracks[name], weight)
                )
            elif mode in {"AGBT_Add", "Add"}:
                base_tracks[name] += override_tracks[name] * weight
            elif mode in {"AGBT_BasePose", "BasePose"}:
                continue
            else:
                return PoseOpEvaluation(
                    tuple(written_bones),
                    tuple(written_tracks),
                    False,
                    f"unsupported BlendOverride track mode: {mode}",
                )
            written_tracks.append(name)
    return PoseOpEvaluation(tuple(written_bones), tuple(written_tracks))


MASK_WEIGHT_THRESHOLD = 0.0001


def apply_mask_blend(
    base_pose: MutableMapping[str, QsTransform],
    blend_pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    weights: Mapping[str, float],
    rotation_ms: Sequence[str] | set[str],
    alpha: float,
    *,
    model_space: bool = False,
) -> tuple[str, ...]:
    """Blend a rig-part mask of blend_pose into base_pose in place and return the bones written"""
    rotation_ms = set(rotation_ms or ())
    written: list[str] = []
    alpha = float(alpha)

    def model(pose, name):
        return frame_model_transform(name, pose, parent_map, model_space)

    for name in tuple(base_pose):
        weight = weights.get(name)
        if weight is None or name not in blend_pose:
            continue
        w = alpha * float(weight)
        if name in rotation_ms and not model_space:
            parent = str(parent_map.get(name, "") or "")
            if not parent or parent not in base_pose or w < MASK_WEIGHT_THRESHOLD:
                continue
            parent_a, parent_b = model(base_pose, parent), model(blend_pose, parent)
            bone_a, bone_b = model(base_pose, name), model(blend_pose, name)
            offset = np.asarray(bone_b.translation) - np.asarray(parent_b.translation)
            moved = QsTransform.from_components(
                np.asarray(parent_a.translation) + offset,
                bone_b.rotation_xyzw,
                bone_a.scale,
            )
            target = relative_to(parent_a, moved)
            base_pose[name] = (
                target
                if w > 1.0 - MASK_WEIGHT_THRESHOLD
                else blend_qs(base_pose[name], target, w)
            )
        elif w > 1.0 - MASK_WEIGHT_THRESHOLD:
            base_pose[name] = blend_pose[name]
        elif w < MASK_WEIGHT_THRESHOLD:
            continue
        else:
            base_pose[name] = blend_qs(base_pose[name], blend_pose[name], w)
        written.append(name)
    return tuple(written)


BLEND_OVERRIDE_ACTIVATION_THRESHOLD = 0.01


def blend_activation_transition(previous_active: bool, control: float):
    """(active, activated, deactivated) of a blend whose override branch runs above the activation threshold"""
    active = max(0.0, min(1.0, float(control))) > BLEND_OVERRIDE_ACTIVATION_THRESHOLD
    return active, active and not previous_active, previous_active and not active


def blend_mask_dynamic_data(node):
    if node.get("syncMethod") is not None:
        raise PreviewBoundary(
            "BlendByMaskDynamic synchronization is not implemented by Graph preview"
        )
    return {
        "masks": tuple(cname_or_empty(name) for name in node.get("masks") or ()),
        "hasWeight": has_link(node, "weight"),
        "hasMask": has_link(node, "mask"),
    }


def blend_multiple_data(node, index):
    """A BlendMultiple's data and the input links that line up with its sorted input values"""
    sync_method = sync_method_type(node, index, "BlendMultiple")
    inputs = list(node.get("inputNodes") or ())
    values = [
        float(v)
        for v in node.get("sortedInputValues") or sorted(node.get("inputValues") or ())
    ]
    if len(inputs) < len(values):
        raise PreviewBoundary("BlendMultiple has fewer inputs than input values")
    # The motion provider only drives root motion.
    return {
        "sortedInputValues": tuple(values),
        "minWeight": float(node.get("minWeight", 0.0) or 0.0),
        "maxWeight": float(
            node.get("maxWeight", 1.0) if node.get("maxWeight") is not None else 1.0
        ),
        "radialBlending": bool(node.get("radialBlending", False)),
        "hasWeightNode": has_link(node, "weightNode"),
        "timeWarping": bool(node.get("timeWarpingEnabled", False)),
        "syncMethod": sync_method,
    }, inputs[: len(values)]


def blend_two_data(node, index):
    """A Blend2's data and its two input references, None for an input that is not linked"""
    first, second = (
        linked_node(node, "firstInputNode"),
        linked_node(node, "secondInputNode"),
    )
    return (
        {
            "minInputValue": float(node.get("minInputValue", 0.0)),
            "maxInputValue": float(node.get("maxInputValue", 1.0)),
            "syncMethod": sync_method_type(node, index, "Blend2"),
            "timeWarping": bool(node.get("timeWarpingEnabled", False)),
        },
        first,
        second,
    )


def blend_two_weight(value: float, minimum: float, maximum: float) -> float:
    """A Blend2's weight for its input value, 0 at the minimum and 1 at the maximum"""
    return (
        min(1.0, max(0.0, (value - minimum) / (maximum - minimum)))
        if maximum > minimum
        else 0.0
    )


def blend_two_inputs(weight: float) -> frozenset[int]:
    """The inputs a Blend2 plays at weight"""
    return frozenset(
        index for index, enabled in ((0, weight < 1.0), (1, weight > 0.0)) if enabled
    )


def blend_additive_data(node):
    unsupported = []
    if node.get("postProcess") is not None:
        unsupported.append("postProcess")
    if node.get("syncMethod") is not None:
        unsupported.append("syncMethod")
    if bool(node.get("timeWarpingEnabled", False)):
        unsupported.append("timeWarpingEnabled")
    previous_track = index_name(
        node.get("weightPreviousFrameFloatTrack"),
        "animNamedTrackIndex",
        allow_text=True,
    )
    try:
        additive_type = normalize_additive_type(node.get("additiveType", "AGAT_Local"))
        blend_tracks = normalize_track_mode(node.get("blendTracks", "AGBT_Add"))
    except ValueError as error:
        raise PreviewBoundary(str(error)) from error
    if unsupported:
        raise PreviewBoundary(
            "BlendAdditive preview does not yet support " + ", ".join(unsupported)
        )
    return {
        "hasWeightNode": has_link(node, "weightNode"),
        "biasValue": float(node.get("biasValue", 0.0) or 0.0),
        "scaleValue": float(
            node.get("scaleValue", 1.0) if node.get("scaleValue") is not None else 1.0
        ),
        "additiveType": additive_type,
        "blendTracks": blend_tracks,
        "maskName": cname_or_empty(node.get("maskName")),
        "previousFrameWeightTrack": str(previous_track or ""),
        "previousFrameWeightDefault": float(
            node.get("weightPreviousFrameFloatTrackDefaultValue", 0.0) or 0.0
        ),
    }


def blend_override_data(node, index):
    unsupported = []
    method = (
        resolve(node["blendMethod"], index)
        if node.get("blendMethod") is not None
        else None
    )
    if node.get("blendMethod") is not None and method is None:
        unsupported.append("unresolved blendMethod")
    if method is not None and method.get("$type") not in {
        "animPoseBlendMethod_BoneBranch",
        "animPoseBlendMethod_Mask",
    }:
        unsupported.append("blendMethod " + str(method.get("$type", "<unknown>")))
    if node.get("postProcess") is not None:
        unsupported.append("postProcess")
    if node.get("syncMethod") is not None:
        unsupported.append("syncMethod")
    if bool(node.get("timeWarpingEnabled", False)):
        unsupported.append("timeWarpingEnabled")
    if bool(node.get("getDeltaMotionFromOverride", False)):
        unsupported.append("getDeltaMotionFromOverride")
    if unsupported:
        raise PreviewBoundary(
            "BlendOverride preview does not yet support " + ", ".join(unsupported)
        )
    method_type = (
        str(method.get("$type", "") or "") if isinstance(method, Mapping) else ""
    )
    # BoneBranch carries its own bone list; the Mask method blends a rig part and keeps the node's legacy bones.
    bone_source = method if method_type == "animPoseBlendMethod_BoneBranch" else node
    bones = [
        {
            "bone": index_name(
                item.get("transformIndex"), "animTransformIndex", allow_text=False
            ),
            "weight": float(item.get("weight", 1.0) or 0.0),
        }
        for item in bone_source.get("bones") or ()
        if isinstance(item, Mapping)
    ]
    tracks = [
        {
            "track": index_name(
                item.get("track"), "animNamedTrackIndex", allow_text=False
            ),
            "weight": float(item.get("weight", 1.0) or 0.0),
        }
        for item in node.get("tracks") or ()
        if isinstance(item, Mapping)
    ]
    return {
        "bones": tuple(bones),
        "blendMethod": {
            "animPoseBlendMethod_BoneBranch": "BoneBranch",
            "animPoseBlendMethod_Mask": "Mask",
        }.get(method_type, ""),
        "maskName": cname_or_empty(method.get("maskName"))
        if method_type == "animPoseBlendMethod_Mask"
        else "",
        "blendAllTracks": bool(node.get("blendAllTracks", False)),
        "blendTrackMode": str(
            node.get("blendTrackMode", "AGBT_Interpolate") or "AGBT_Interpolate"
        ),
        "tracks": tuple(tracks),
    }
