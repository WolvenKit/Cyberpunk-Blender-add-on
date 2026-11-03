from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import replace

from ....assetio.values import cname_or_empty
from ....bartmoss.ik import solve_two_bone_ik
from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import (
    IDENTITY_XYZW,
    multiply_scalar_xyzw,
    slerp_scalar_xyzw,
)
from ....bartmoss.vector3 import add3, lerp3
from ...model.animgraph.aim_constraint import vector_components
from ...model.animgraph.constants import AXIS_VECTORS
from ...model.animgraph.frames import IkTarget
from ...model.animgraph.indices import index_name
from .pose_space import frame_model_transform
from .source_channels import vector_channel_data
from .topology import has_link


def _model(pose, parent_map, name: str, model_space: bool, cache: dict) -> QsTransform:
    if not name:
        return QsTransform.identity()
    return frame_model_transform(name, pose, parent_map, model_space, cache)


def add_ik_request(
    targets: Sequence[IkTarget],
    data: Mapping,
    pose: Mapping[str, QsTransform],
    parent_map: Mapping[str, str],
    *,
    model_space: bool = False,
) -> tuple[IkTarget, ...]:
    """Targets after an AddIkRequest"""
    chain = str(data.get("ikChain", "") or "")
    priority = int(data.get("priority", 0) or 0)
    position = next(
        (index for index, target in enumerate(targets) if target.chain == chain), -1
    )
    if position >= 0 and priority > targets[position].priority:
        return tuple(targets)
    bone = str(data.get("targetBone", "") or "")
    if bone not in pose:
        return tuple(targets)
    cache: dict = {}
    target_ms = _model(pose, parent_map, bone, model_space, cache)
    previous = targets[position] if position >= 0 else IkTarget(chain)
    pole_bone = str(data.get("poleTargetBone", "") or "")
    pole_weight, pole = 0.0, previous.pole
    if pole_bone in pose:
        pole_weight = 1.0
        pole = add3(
            _model(pose, parent_map, pole_bone, model_space, cache).translation,
            data.get("polePositionOffset", (0.0, 0.0, 0.0)),
        )
    request = replace(
        previous,
        chain=chain,
        priority=priority,
        transition_in=float(data.get("blendTimeIn", 0.0) or 0.0),
        transition_out=float(data.get("blendTimeOut", 0.0) or 0.0),
        weight_position=float(data.get("weightPosition", 0.0) or 0.0),
        weight_orientation=float(data.get("weightRotation", 0.0) or 0.0),
        pole_weight=pole_weight,
        translation=add3(
            target_ms.translation, data.get("positionOffset", (0.0, 0.0, 0.0))
        ),
        rotation=tuple(
            multiply_scalar_xyzw(
                target_ms.rotation_xyzw, data.get("rotationOffset", IDENTITY_XYZW)
            )
        ),
        pole=tuple(pole),
    )
    result = list(targets)
    if position >= 0:
        result[position] = request
    else:
        result.append(request)
    return tuple(result)


def read_ik_request(
    pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    targets: Sequence[IkTarget],
    chain: str,
    bone: str,
    *,
    model_space: bool = False,
) -> bool:
    """Write the chain's target into bone as a transform relative to the bone's model-space parent"""
    target = next((item for item in targets if item.chain == chain), None)
    if target is None or bone not in pose:
        return False
    parent = str(parent_map.get(bone, "") or "")
    parent_ms = (
        _model(pose, parent_map, parent, model_space, {})
        if parent in pose
        else QsTransform.identity()
    )
    target_ms = QsTransform.from_components(
        target.translation, target.rotation, (1.0, 1.0, 1.0)
    )
    pose[bone] = relative_to(parent_ms, target_ms)
    return True


def _weighted_alpha(alpha: float, first: float, second: float) -> float:
    total = first + second
    if total < 1.1920929e-07:
        return alpha
    alpha_first = 1.0 - (1.0 - alpha) * first
    alpha_second = alpha * second
    return min(
        1.0, max(0.0, alpha_first * (second / total) + alpha_second * (first / total))
    )


def interpolate_ik_targets(
    first: Sequence[IkTarget], second: Sequence[IkTarget], alpha: float
) -> tuple[IkTarget, ...]:
    """The target list of a blend between two full sample outputs"""
    alpha = float(alpha)
    if not first and not second:
        return ()
    by_chain = {target.chain: target for target in second}
    result: list[IkTarget] = []
    for a in first:
        b = by_chain.get(a.chain)
        if b is None:
            result.append(
                replace(
                    a,
                    weight_position=a.weight_position * (1.0 - alpha),
                    weight_orientation=a.weight_orientation * (1.0 - alpha),
                )
            )
            continue
        result.append(
            IkTarget(
                chain=a.chain,
                priority=min(a.priority, b.priority),
                transition_in=a.transition_in
                + (b.transition_in - a.transition_in) * alpha,
                transition_out=a.transition_out
                + (b.transition_out - a.transition_out) * alpha,
                weight_position=a.weight_position * (1.0 - alpha)
                + b.weight_position * alpha,
                weight_orientation=a.weight_orientation * (1.0 - alpha)
                + b.weight_orientation * alpha,
                pole_weight=a.pole_weight * (1.0 - alpha) + b.pole_weight * alpha,
                translation=lerp3(
                    a.translation,
                    b.translation,
                    _weighted_alpha(alpha, a.weight_position, b.weight_position),
                ),
                rotation=tuple(
                    slerp_scalar_xyzw(
                        a.rotation,
                        b.rotation,
                        _weighted_alpha(
                            alpha, a.weight_orientation, b.weight_orientation
                        ),
                    )
                ),
                pole=lerp3(
                    a.pole, b.pole, _weighted_alpha(alpha, a.pole_weight, b.pole_weight)
                ),
            )
        )
    merged = {target.chain for target in result}
    for b in second:
        if b.chain not in merged:
            result.append(
                replace(
                    b,
                    weight_position=b.weight_position * alpha,
                    weight_orientation=b.weight_orientation * alpha,
                )
            )
    return tuple(result)


def solve_ik2(
    first_parent_ms: QsTransform,
    first_ls: QsTransform,
    second_ls: QsTransform,
    end_ls: QsTransform,
    *,
    hinge_axis_ls,
    target_ms,
    pole_ms=None,
    end_rotation_ms=None,
    weight: float = 1.0,
    twist_deg: float = 0.0,
    cos_max_hinge: float = -1.0,
    cos_min_hinge: float = 1.0,
    gains: tuple[float, float, float] = (1.0, 1.0, 1.0),
    end_offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    enforce_position: bool = True,
) -> tuple[QsTransform, QsTransform, QsTransform]:
    """First, second and end bone local transforms that reach target_ms (see solve_two_bone_ik)"""
    chain_ms = []
    parent = first_parent_ms
    for local in (first_ls, second_ls, end_ls):
        parent = compose(parent, local)
        chain_ms.append(parent)
    solved = solve_two_bone_ik(
        *((bone.translation, bone.rotation_xyzw) for bone in chain_ms),
        hinge_axis_local=hinge_axis_ls,
        target=target_ms,
        pole=pole_ms,
        end_rotation=end_rotation_ms,
        weight=weight,
        twist_deg=twist_deg,
        cos_max_hinge=cos_max_hinge,
        cos_min_hinge=cos_min_hinge,
        gains=gains,
        end_offset=end_offset,
        enforce_position=enforce_position,
    )
    first_ms, second_ms, end_ms = (
        QsTransform.from_components(position, rotation, bone.scale)
        for (position, rotation), bone in zip(solved, chain_ms)
    )
    return (
        relative_to(first_parent_ms, first_ms),
        relative_to(first_ms, second_ms),
        relative_to(second_ms, end_ms),
    )


def evaluate_ik2_constraint(
    pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    data: Mapping,
    target_ms,
    pole_ms,
    weight: float,
    twist_deg: float,
    *,
    model_space: bool = False,
) -> tuple[str, ...]:
    """Apply Ik2Constraint in place and return the bones written"""
    first, second, end = (
        str(data.get(key, "") or "") for key in ("firstBone", "secondBone", "endBone")
    )
    parent = str(parent_map.get(first, "") or "")
    if (
        weight <= 0.0
        or target_ms is None
        or not all(name in pose for name in (first, second, end, parent))
    ):
        return ()
    max_angle = float(data.get("maxHingeAngle", 0.0) or 0.0)
    first_ls, second_ls, end_ls = solve_ik2(
        _model(pose, parent_map, parent, model_space, {}),
        pose[first],
        pose[second],
        pose[end],
        hinge_axis_ls=AXIS_VECTORS.get(
            str(data.get("hingeAxis", "Y") or "Y"), AXIS_VECTORS["Y"]
        ),
        target_ms=target_ms,
        pole_ms=pole_ms,
        weight=float(weight),
        twist_deg=float(twist_deg),
        cos_max_hinge=math.cos(math.radians(max_angle)) if max_angle > 0.0 else -1.0,
    )
    pose[first], pose[second], pose[end] = first_ls, second_ls, end_ls
    return (first, second, end)


def add_ik_request_data(node_type, node):
    rotation = (
        node.get("rotationOffset")
        if isinstance(node.get("rotationOffset"), Mapping)
        else {}
    )
    pole = node.get("poleVector") if isinstance(node.get("poleVector"), Mapping) else {}
    return {
        "ikChain": cname_or_empty(node.get("ikChain")),
        "targetBone": index_name(
            node.get("targetBone"), "animTransformIndex", allow_text=True
        ),
        "positionOffset": vector_components(
            node.get("positionOffset"), (0.0, 0.0, 0.0)
        ),
        "rotationOffset": tuple(
            float(
                rotation.get(key, default) if rotation.get(key) is not None else default
            )
            for key, default in (("i", 0.0), ("j", 0.0), ("k", 0.0), ("r", 1.0))
        ),
        "poleTargetBone": index_name(
            pole.get("targetBone"), "animTransformIndex", allow_text=True
        ),
        "polePositionOffset": vector_components(
            pole.get("positionOffset"), (0.0, 0.0, 0.0)
        ),
        "weightPosition": float(node.get("weightPosition", 0.0) or 0.0),
        "weightRotation": float(node.get("weightRotation", 0.0) or 0.0),
        "blendTimeIn": float(node.get("blendTimeIn", 0.0) or 0.0),
        "blendTimeOut": float(node.get("blendTimeOut", 0.0) or 0.0),
        "priority": int(node.get("priority", 0) or 0),
    }


def read_ik_request_data(node_type, node):
    return {
        "ikChain": cname_or_empty(node.get("ikChain")),
        "outTransform": index_name(
            node.get("outTransform"), "animTransformIndex", allow_text=True
        ),
    }


def ik2_constraint_data(node_type, node):
    target = node.get("inputTarget")
    pole = node.get("inputPoleVector")
    return {
        "firstBone": index_name(
            node.get("firstBoneIndex"), "animTransformIndex", allow_text=True
        ),
        "secondBone": index_name(
            node.get("secondBoneIndex"), "animTransformIndex", allow_text=True
        ),
        "endBone": index_name(
            node.get("endBoneIndex"), "animTransformIndex", allow_text=True
        ),
        "hingeAxis": str(node.get("hingeAxis", "Y") or "Y"),
        "inputTarget": vector_channel_data(target)
        if isinstance(target, Mapping)
        else None,
        "inputPoleVector": vector_channel_data(pole)
        if isinstance(pole, Mapping)
        else None,
        "weight": float(
            node.get("weight", 1.0) if node.get("weight") is not None else 1.0
        ),
        "weightFloatTrack": index_name(
            node.get("weightFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "hasWeightNode": has_link(node, "weightNode"),
        "twistValue": float(node.get("twistValue", 0.0) or 0.0),
        "hasTwistNode": has_link(node, "twistNode"),
        "maxHingeAngle": float(node.get("maxHingeAngle", 0.0) or 0.0),
    }


def ik2_data(node_type, node):
    def gain(key):
        return float(node.get(key, 1.0) if node.get(key) is not None else 1.0)

    def angle(key, default):
        return float(node.get(key, default) if node.get(key) is not None else default)

    return {
        "firstBone": index_name(
            node.get("firstBone"), "animTransformIndex", allow_text=True
        ),
        "secondBone": index_name(
            node.get("secondBone"), "animTransformIndex", allow_text=True
        ),
        "endBone": index_name(
            node.get("endBone"), "animTransformIndex", allow_text=True
        ),
        "bone": index_name(node.get("bone"), "animTransformIndex", allow_text=True),
        "hingeAxis": str(node.get("hingeAxis", "Y") or "Y"),
        "minHingeAngle": angle("minHingeAngleDegrees", 0.0),
        "maxHingeAngle": angle("maxHingeAngleDegrees", 180.0),
        "gains": (
            gain("firstBoneIkGain"),
            gain("secondBoneIkGain"),
            gain("endBoneIkGain"),
        ),
        "enforceEndPosition": bool(node.get("enforceEndPosition", True)),
        "enforceEndOrientation": bool(node.get("enforceEndOrientation", False)),
        "endBoneOffset": vector_components(
            node.get("endBoneOffsetPositionLS"), (0.0, 0.0, 0.0)
        ),
        "floatTrack": index_name(
            node.get("floatTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "hasWeightNode": has_link(node, "weightNode"),
        "hasEndTargetPositionNode": has_link(node, "endTargetPositionNode"),
        "hasEndTargetOrientationNode": has_link(node, "endTargetOrientationNode"),
    }


def evaluate_ik2(
    pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    data: Mapping,
    weight: float,
    target_ms=None,
    target_rotation_ms=None,
    *,
    model_space: bool = False,
) -> tuple[str, ...]:
    """Apply Ik2 in place and return the bones written"""
    first, second, end = (
        str(data.get(key, "") or "") for key in ("firstBone", "secondBone", "endBone")
    )
    parent = str(parent_map.get(first, "") or "")
    enforce_position = bool(data.get("enforceEndPosition", True))
    enforce_rotation = bool(data.get("enforceEndOrientation", False))
    if weight == 0.0 or not (enforce_position or enforce_rotation):
        return ()
    if not all(name in pose for name in (first, second, end, parent)):
        return ()
    cache: dict = {}
    bone = str(data.get("bone", "") or "")
    if (target_ms is None or target_rotation_ms is None) and bone in pose:
        bone_ms = _model(pose, parent_map, bone, model_space, cache)
        target_ms = bone_ms.translation if target_ms is None else target_ms
        target_rotation_ms = (
            bone_ms.rotation_xyzw if target_rotation_ms is None else target_rotation_ms
        )
    first_ls, second_ls, end_ls = solve_ik2(
        _model(pose, parent_map, parent, model_space, cache),
        pose[first],
        pose[second],
        pose[end],
        hinge_axis_ls=AXIS_VECTORS.get(
            str(data.get("hingeAxis", "Y") or "Y"), AXIS_VECTORS["Y"]
        ),
        target_ms=target_ms if target_ms is not None else (0.0, 0.0, 0.0),
        end_rotation_ms=(target_rotation_ms or IDENTITY_XYZW)
        if enforce_rotation
        else None,
        weight=float(weight),
        cos_max_hinge=math.cos(math.radians(float(data.get("maxHingeAngle", 180.0)))),
        cos_min_hinge=math.cos(math.radians(float(data.get("minHingeAngle", 0.0)))),
        gains=tuple(data.get("gains", (1.0, 1.0, 1.0))),
        end_offset=tuple(data.get("endBoneOffset", (0.0, 0.0, 0.0))),
        enforce_position=enforce_position,
    )
    pose[first], pose[second], pose[end] = first_ls, second_ls, end_ls
    return (first, second, end)
