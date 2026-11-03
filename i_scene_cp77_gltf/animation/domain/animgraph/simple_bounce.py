from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ....bartmoss.qs_transform import QsTransform, compose, matrix_from_qs, relative_to
from ....bartmoss.quaternion import rotate_vector_unit_scalar_xyzw
from ....redSpace.euler import CHANNEL_INDEX, euler_from_xyzw, xyzw_from_euler
from ...model.animgraph.indices import index_name
from ...model.animgraph.simple_bounce import normalize_data
from .pose_space import frame_model_transform, model_transform


@dataclass(frozen=True)
class DriverEvaluation:
    signed_input: float
    output: float
    positive_side: bool


@dataclass(frozen=True)
class SimpleBounceEvaluation:
    driver: DriverEvaluation
    transforms_written: tuple[str, ...]
    tracks_written: tuple[str, ...]
    applied: bool = True
    reason: str = ""


def _noop_simple_bounce(reason: str) -> SimpleBounceEvaluation:
    return SimpleBounceEvaluation(
        DriverEvaluation(0.0, 0.0, True), (), (), False, reason
    )


def signed_driver_x(start_model: QsTransform, end_model: QsTransform) -> float:
    sx, sy, sz = start_model.scale
    scale_x = float(sx)
    if abs(scale_x) <= 1e-15:
        relative = np.linalg.inv(matrix_from_qs(start_model)) @ matrix_from_qs(
            end_model
        )
        return float(relative[0, 3])
    ex, ey, ez = end_model.translation
    sx_t, sy_t, sz_t = start_model.translation
    qx, qy, qz, qw = start_model.rotation_xyzw
    local_x, _, _ = rotate_vector_unit_scalar_xyzw(
        (-qx, -qy, -qz, qw),
        (ex - sx_t, ey - sy_t, ez - sz_t),
    )
    return float(local_x / scale_x)


def evaluate_driver(
    signed_input: float,
    *,
    multiplier: float,
    negative_multiplier: float,
    smooth_step: float,
    offset: float,
    delay: float,
) -> DriverEvaluation:
    signed = float(signed_input)
    input_value = signed
    active_multiplier = float(multiplier)
    positive = input_value >= 0.0
    if input_value < 0.0:
        input_value = -input_value
        active_multiplier = float(negative_multiplier)

    out_value = 0.0
    delay = float(delay)
    smooth_step = float(smooth_step)
    if input_value > delay:
        input_with_delay = input_value - delay
        if smooth_step != 0.0 and abs(input_with_delay) < smooth_step:
            out_value = (
                input_with_delay * input_with_delay / smooth_step
            ) * active_multiplier
        else:
            out_value = input_with_delay * active_multiplier
    out_value += float(offset)
    return DriverEvaluation(signed, float(out_value), positive)


def modify_local_transform(
    target: QsTransform,
    value: float,
    channel_ops: Sequence[tuple[str, float]],
) -> QsTransform:
    tx, ty, tz = target.translation
    sx, sy, sz = target.scale
    rotation = target.rotation_xyzw
    euler = None
    scalar_value = float(value)
    for channel, multiplier in channel_ops:
        adjusted = multiplier * scalar_value
        if channel == "PosX":
            tx = adjusted
        elif channel == "PosY":
            ty = adjusted
        elif channel == "PosZ":
            tz = adjusted
        elif channel in {"RotX", "RotY", "RotZ"}:
            if euler is None:
                euler = list(euler_from_xyzw(rotation))
            # EulerAngles are degrees; RotX/RotY/RotZ set Pitch/Roll/Yaw.
            euler[CHANNEL_INDEX[channel]] = adjusted
        elif channel == "ScaleX":
            sx = adjusted
        elif channel == "ScaleY":
            sy = adjusted
        elif channel == "ScaleZ":
            sz = adjusted
        else:
            raise ValueError(f"Unsupported SimpleBounce transform channel: {channel}")
    if euler is not None:
        rotation = tuple(float(v) for v in xyzw_from_euler(*euler))
    return QsTransform((tx, ty, tz), rotation, (sx, sy, sz))


def _modify_model_translation_only(
    target_model: QsTransform,
    parent_model: QsTransform,
    value: float,
    channel_ops: Sequence[tuple[str, float]],
) -> QsTransform | None:
    psx, psy, psz = parent_model.scale
    if abs(psx) <= 1e-15 or abs(psy) <= 1e-15 or abs(psz) <= 1e-15:
        return None

    px, py, pz, pw = parent_model.rotation_xyzw
    ttx, tty, ttz = target_model.translation
    ptx, pty, ptz = parent_model.translation
    ltx, lty, ltz = rotate_vector_unit_scalar_xyzw(
        (-px, -py, -pz, pw),
        (ttx - ptx, tty - pty, ttz - ptz),
    )
    ltx /= psx
    lty /= psy
    ltz /= psz
    scalar_value = float(value)
    for channel, multiplier in channel_ops:
        adjusted = multiplier * scalar_value
        if channel == "PosX":
            ltx = adjusted
        elif channel == "PosY":
            lty = adjusted
        elif channel == "PosZ":
            ltz = adjusted
        else:
            return None

    rtx, rty, rtz = rotate_vector_unit_scalar_xyzw(
        parent_model.rotation_xyzw,
        (ltx * psx, lty * psy, ltz * psz),
    )
    return QsTransform(
        (ptx + rtx, pty + rty, ptz + rtz),
        target_model.rotation_xyzw,
        target_model.scale,
    )


def evaluate_simple_bounce(
    local_pose: MutableMapping[str, QsTransform],
    tracks: MutableMapping[str, float],
    parent_map: Mapping[str, str],
    data: Mapping[str, Any],
    *,
    model_space: bool = False,
) -> SimpleBounceEvaluation:
    start_name = str(data.get("startTransform", "") or "")
    end_name = str(data.get("endTransform", "") or "")
    if start_name not in local_pose:
        return _noop_simple_bounce(
            f"start transform is absent from the pose: {start_name or '<empty>'}"
        )
    if end_name not in local_pose:
        return _noop_simple_bounce(
            f"end transform is absent from the pose: {end_name or '<empty>'}"
        )

    for output in data.get("transformOutputs", ()) or ():
        target_name = str(output.get("targetTransform", "") or "")
        parent_name = str(output.get("parentTransform", "") or "")
        if target_name not in local_pose:
            return _noop_simple_bounce(
                f"output transform is absent from the pose: {target_name or '<empty>'}"
            )
    for output in data.get("trackOutputs", ()) or ():
        target_name = str(output.get("targetTrack", "") or "")
        if target_name not in tracks:
            return _noop_simple_bounce(
                f"output track is absent from the pose: {target_name or '<empty>'}"
            )

    cache: dict[str, QsTransform] = {}
    try:
        start_model = frame_model_transform(
            start_name, local_pose, parent_map, model_space, cache
        )
        end_model = frame_model_transform(
            end_name, local_pose, parent_map, model_space, cache
        )
    except KeyError as exc:
        name = str(exc.args[0] if exc.args else "")
        return _noop_simple_bounce(
            f"transform ancestor is absent from the pose: {name or '<empty>'}"
        )
    driver_params = data["_driverParams"]
    driver = evaluate_driver(
        signed_driver_x(start_model, end_model),
        multiplier=driver_params[0],
        negative_multiplier=driver_params[1],
        smooth_step=driver_params[2],
        offset=driver_params[3],
        delay=driver_params[4],
    )

    tracks_written = []
    for output in data.get("trackOutputs", ()) or ():
        target = str(output.get("targetTrack", "") or "")
        tracks[target] = float(output.get("multiplier", 1.0)) * driver.output
        tracks_written.append(target)
    output_driver = str(data.get("outputDriverTrack", "") or "")
    if output_driver:
        tracks[output_driver] = driver.signed_input
        tracks_written.append(output_driver)

    transforms_written = []
    for output in data.get("transformOutputs", ()) or ():
        target_name = str(output.get("targetTransform", "") or "")
        parent_name = str(output.get("parentTransform", "") or "")
        entries = output["_channelOps"]
        rig_parent = str(parent_map.get(target_name, "") or "")
        if parent_name and parent_name not in local_pose:
            # An unresolved parentTransform falls back to the rig parent.
            parent_name = rig_parent if rig_parent in local_pose else ""
        if model_space:
            # Model space always re-parents, onto the rig parent when none is authored.
            space_parent = parent_name or rig_parent
            selected_parent_model = (
                local_pose[space_parent] if space_parent in local_pose else None
            )
            target_model = local_pose[target_name]
            if selected_parent_model is not None and output.get(
                "_translationOnly", False
            ):
                translated = _modify_model_translation_only(
                    target_model, selected_parent_model, driver.output, entries
                )
                if translated is not None:
                    local_pose[target_name] = translated
                    transforms_written.append(target_name)
                    continue
            selected_local = (
                relative_to(selected_parent_model, target_model)
                if selected_parent_model is not None
                else target_model
            )
            selected_local = modify_local_transform(
                selected_local, driver.output, entries
            )
            local_pose[target_name] = (
                compose(selected_parent_model, selected_local)
                if selected_parent_model is not None
                else selected_local
            )
        elif not parent_name:
            local_pose[target_name] = modify_local_transform(
                local_pose[target_name], driver.output, entries
            )
        else:
            current_cache: dict[str, QsTransform] = {}
            target_model = model_transform(
                target_name, local_pose, parent_map, current_cache
            )
            selected_parent_model = model_transform(
                parent_name, local_pose, parent_map, current_cache
            )
            selected_local = relative_to(selected_parent_model, target_model)
            selected_local = modify_local_transform(
                selected_local, driver.output, entries
            )
            modified_model = compose(selected_parent_model, selected_local)
            original_parent = str(parent_map.get(target_name, "") or "")
            local_pose[target_name] = (
                relative_to(
                    model_transform(original_parent, local_pose, parent_map, {}),
                    modified_model,
                )
                if original_parent
                else modified_model
            )
        transforms_written.append(target_name)
    return SimpleBounceEvaluation(
        driver, tuple(transforms_written), tuple(tracks_written), True, ""
    )


def simple_bounce_data(node_type, node):
    normalized = normalize_data(dict(node))
    return {
        "startTransform": index_name(
            normalized.get("startTransform"), "animTransformIndex", allow_text=True
        ),
        "endTransform": index_name(
            normalized.get("endTransform"), "animTransformIndex", allow_text=True
        ),
        "multiplier": float(normalized.get("multiplier", 1.0) or 0.0),
        "negativeMultiplier": float(normalized.get("negativeMultiplier", 1.0) or 0.0),
        "smoothStep": float(normalized.get("smoothStep", 1.0) or 0.0),
        "offset": float(normalized.get("offset", 0.0) or 0.0),
        "delay": float(normalized.get("delay", 0.0) or 0.0),
        "outputDriverTrack": index_name(
            normalized.get("outputDriverTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "transformOutputs": tuple(
            {
                "targetTransform": index_name(
                    raw.get("targetTransform"), "animTransformIndex", allow_text=True
                ),
                "parentTransform": index_name(
                    raw.get("parentTransform"), "animTransformIndex", allow_text=True
                ),
                "channelEntries": tuple(
                    {
                        "transformChannel": str(
                            entry.get("transformChannel", "PosX") or "PosX"
                        ),
                        "multiplier": float(entry.get("multiplier", 1.0) or 0.0),
                    }
                    for entry in raw.get("channelEntries", ()) or ()
                    if isinstance(entry, Mapping)
                ),
            }
            for raw in normalized.get("transformOutputs", ()) or ()
            if isinstance(raw, Mapping)
        ),
        "trackOutputs": tuple(
            {
                "targetTrack": index_name(
                    raw.get("targetTrack"), "animNamedTrackIndex", allow_text=True
                ),
                "multiplier": float(raw.get("multiplier", 1.0) or 0.0),
            }
            for raw in normalized.get("trackOutputs", ()) or ()
            if isinstance(raw, Mapping)
        ),
    }
