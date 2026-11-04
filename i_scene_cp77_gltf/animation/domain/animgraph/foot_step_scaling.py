from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping

from ....bartmoss.qs_transform import QsTransform, compose, relative_to
from ....bartmoss.quaternion import axis_angle_scalar_xyzw, multiply_scalar_xyzw
from ....bartmoss.scalar import lerp, linear_step_scalar, smoothstep_scalar
from ....bartmoss.vector3 import add3, length3, lerp3, midpoint3, scale3, sub3
from ...model.animgraph.indices import index_name
from .ik import solve_ik2
from .pose_space import frame_model_transform
from .topology import has_link

MIN_REASONABLE_SCALE = 0.6
MAX_REASONABLE_SCALE = 1.4
FLOAT_EPSILON = 1.1920929e-07


def _exponential(param: float, scale: float) -> float:
    return param - param / (scale * scale)


def _relative(value: QsTransform, root) -> QsTransform:
    return QsTransform.from_components(
        sub3(value.translation, root), value.rotation_xyzw, (1.0, 1.0, 1.0)
    )


def _absolute(value: QsTransform, root) -> QsTransform:
    return QsTransform.from_components(
        add3(value.translation, root),
        value.rotation_xyzw,
        (1.0, 1.0, 1.0),
    )


def _leg_chain(end: str, parent_map: Mapping[str, str]) -> tuple[str, str, str, str]:
    second = str(parent_map.get(end, "") or "")
    first = str(parent_map.get(second, "") or "") if second else ""
    first_parent = str(parent_map.get(first, "") or "") if first else ""
    return first_parent, first, second, end


def evaluate_foot_step_scaling(
    pose: MutableMapping[str, QsTransform],
    parent_map: Mapping[str, str],
    reference_ms: Mapping[str, QsTransform],
    data: Mapping,
    speed: float,
    weight: float,
    *,
    model_space: bool = False,
) -> tuple[str, ...]:
    """Apply FootStepScaling in place and return the bones written"""
    if weight <= 0.0 or abs(1.0 - speed) <= FLOAT_EPSILON or not speed < math.inf:
        return ()
    hip, left, right = (
        str(data.get(key, "") or "")
        for key in ("hipsIndex", "leftFootIKIndex", "rightFootIKIndex")
    )
    if not all(name in pose and name in reference_ms for name in (hip, left, right)):
        return ()
    params = data.get("params", {}) or {}
    scale_factor = float(speed)

    # Body parameters from the reference pose.
    ref_root = midpoint3(
        reference_ms[left].translation, reference_ms[right].translation
    )
    leg_length = length3(sub3(reference_ms[hip].translation, ref_root))
    scale = linear_step_scalar(MIN_REASONABLE_SCALE, MAX_REASONABLE_SCALE, scale_factor)
    influence = scale * 2.0 - 1.0
    shaped = 1.0 - smoothstep_scalar(0.0, 1.0, scale)
    curve_leg_length = lerp(
        leg_length,
        leg_length - float(params.get("LegLengthAdjustment", 0.0) or 0.0),
        shaped,
    )
    max_stretch = leg_length - float(params.get("LegMaxStretchOffset", 0.0) or 0.0)
    max_stretch = lerp(
        max_stretch,
        max_stretch + float(params.get("LegMaxStretchAdjustment", 0.0) or 0.0),
        shaped,
    )
    pull = smoothstep_scalar(0.0, 0.33, scale) * (
        smoothstep_scalar(0.66, 1.0, scale) * 0.5 + 0.5
    )
    pull_factor = lerp(
        float(params.get("LegsPullFactorMin", 0.0) or 0.0),
        float(params.get("LegsPullFactorMax", 0.0) or 0.0),
        pull,
    )

    cache: dict = {}

    def model(name: str) -> QsTransform:
        if not name:
            return QsTransform.identity()
        return frame_model_transform(name, pose, parent_map, model_space, cache)

    hip_ms, left_ms, right_ms = model(hip), model(left), model(right)
    root = midpoint3(left_ms.translation, right_ms.translation)
    initial_hip = _relative(hip_ms, root)
    initial_left = _relative(left_ms, root).translation
    initial_right = _relative(right_ms, root).translation

    # Step 1: scale the feet along Y and Z about their midpoint.
    left_pos = (
        initial_left[0],
        initial_left[1] * scale_factor,
        initial_left[2] * scale_factor,
    )
    right_pos = (
        initial_right[0],
        initial_right[1] * scale_factor,
        initial_right[2] * scale_factor,
    )
    hip_pos = initial_hip.translation
    # Step 2: lower the hips along their direction from the root when a scaled leg over-stretches.
    if scale_factor > 1.0:
        lowering = (
            max(
                max(length3(sub3(hip_pos, left_pos)) - max_stretch, 0.0),
                max(length3(sub3(hip_pos, right_pos)) - max_stretch, 0.0),
            )
            * influence
            * influence
            * 0.5
        )
        length = length3(hip_pos)
        if length > 0.0:
            hip_pos = sub3(hip_pos, scale3(hip_pos, lowering / length))
    # Step 3: retarget hip height to the stride, and lean and shift it forward when speeding up.
    hip_pos = (
        hip_pos[0],
        hip_pos[1],
        lerp(
            hip_pos[2],
            hip_pos[2] * scale_factor + curve_leg_length * (1.0 - scale_factor),
            influence * influence,
        ),
    )
    hip_rotation = initial_hip.rotation_xyzw
    if scale_factor > 1.0:
        hip_pos = (
            hip_pos[0],
            hip_pos[1]
            + _exponential(float(params.get("HipsShift", 0.0) or 0.0), scale_factor),
            hip_pos[2],
        )
        tilt = -math.radians(
            _exponential(float(params.get("HipsTilt", 0.0) or 0.0), scale_factor)
        )
        # The lean is about the model's lateral (X) axis.
        hip_rotation = multiply_scalar_xyzw(
            axis_angle_scalar_xyzw((1.0, 0.0, 0.0), tilt), hip_rotation
        )
    # Step 4: pull over-stretched feet back towards the animated pose.
    feet = []
    for original, scaled in ((initial_left, left_pos), (initial_right, right_pos)):
        stretch = length3(sub3(hip_pos, scaled))
        if stretch > max_stretch and pull_factor != 0.0:
            delta = abs(stretch - max_stretch) / pull_factor
            if delta > 1.0:
                scaled = lerp3(scaled, original, smoothstep_scalar(1.0, 1.25, delta))
        feet.append(scaled)

    new_hip_ms = _absolute(
        QsTransform.from_components(hip_pos, hip_rotation, (1.0, 1.0, 1.0)), root
    )
    written = [hip]
    solutions = []
    # The legs' first-bone parent follows the hips' move, by the offset of the left leg for both legs;
    # on rigs where both legs hang from the hips the two offsets are equal.
    offset = relative_to(hip_ms, model(_leg_chain(left, parent_map)[0]))
    for foot, target in ((left, feet[0]), (right, feet[1])):
        _first_parent, first, second, end = _leg_chain(foot, parent_map)
        if not all(name in pose for name in (first, second, end)):
            continue
        solutions.append(
            (
                (first, second, end),
                solve_ik2(
                    compose(new_hip_ms, offset),
                    pose[first],
                    pose[second],
                    pose[end],
                    hinge_axis_ls=(0.0, 0.0, 1.0),
                    target_ms=add3(target, root),
                ),
            )
        )
    # The hips take their model-space result directly.
    pose[hip] = new_hip_ms
    for names, transforms in solutions:
        for name, value in zip(names, transforms):
            pose[name] = value
        written.extend(names)
    return tuple(written)


def foot_step_scaling_data(node_type, node):
    params = node.get("Params") if isinstance(node.get("Params"), Mapping) else {}
    return {
        "hipsIndex": index_name(
            node.get("hipsIndex"), "animTransformIndex", allow_text=True
        ),
        "leftFootIKIndex": index_name(
            node.get("leftFootIKIndex"), "animTransformIndex", allow_text=True
        ),
        "rightFootIKIndex": index_name(
            node.get("rightFootIKIndex"), "animTransformIndex", allow_text=True
        ),
        "params": {
            key: float(value)
            for key, value in params.items()
            if key != "$type" and isinstance(value, (int, float))
        },
        "hasInputSpeed": has_link(node, "inputSpeed"),
        "hasWeight": has_link(node, "weight"),
    }
