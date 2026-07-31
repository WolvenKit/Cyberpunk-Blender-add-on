from __future__ import annotations

import numpy as np

from ...bartmoss.scalar import clamp_scalar, lerp, limit_weight_scalar
from .constants import (
    ENV_JALI_JAW,
    ENV_JALI_LIPS,
    ENV_LIPSYNC,
    ENV_LOWER_FACE,
    ENV_MUZZLE_BROWS,
    ENV_MUZZLE_EYE_DIR,
    ENV_MUZZLE_EYES,
    ENV_MUZZLE_LIPS,
    ENV_UPPER_FACE,
    INFLUENCE_EXPONENTIAL,
    INFLUENCE_LINEAR,
    INFLUENCE_ORGANIC,
    WEIGHT_THRESHOLD,
)
from .runtime import CompiledFacialPart, CompiledFacialRuntime, CompiledPoseArrays

_MUZZLE_EYES = 2
_MUZZLE_BROWS = 3
_MUZZLE_EYE_DIR = 4


def _stage_envelopes(
    part: CompiledFacialPart,
    input_tracks: np.ndarray,
    output_tracks: np.ndarray,
    lod: int,
    lod_weight: float,
    muzzle_eyes: float,
    muzzle_brows: float,
    muzzle_eye_dir: float,
) -> None:
    weights = part.env_weights
    factors = part.env_factors
    np.take(input_tracks, part.env_tracks, out=weights)
    np.clip(weights, 0.0, 1.0, out=weights)
    muzzle = part.muzzle_values
    muzzle[2] = 1.0 - muzzle_eyes
    muzzle[3] = 1.0 - muzzle_brows
    muzzle[4] = 1.0 - muzzle_eye_dir
    np.take(muzzle, part.env_types, out=factors)
    lod_index = max(int(lod), 0)
    if lod_index < len(part.env_equal):
        equal = part.env_equal[lod_index]
        below = part.env_below[lod_index]
    else:
        equal = ()
        below = range(len(part.env_tracks))
    if len(equal):
        factors[equal] *= 1.0 - lod_weight
    if len(below):
        factors[below] = 0.0
    np.multiply(weights, factors, out=weights)
    np.less_equal(weights, WEIGHT_THRESHOLD, out=part.env_threshold_mask)
    np.putmask(weights, part.env_threshold_mask, 0.0)
    output_tracks[part.env_tracks] = weights


def _stage_limits(
    part: CompiledFacialPart,
    jali_jaw: float,
    jali_lips: float,
    muzzle_lips: float,
    lipsync_env: float,
    output_tracks: np.ndarray,
) -> None:
    if lipsync_env == 0.0:
        return
    for i in range(part.limit_num):
        track = int(part.limit_tracks[i])
        envelope = int(part.limit_envelope[i])
        slider = jali_jaw if envelope == 0 else jali_lips if envelope == 1 else 1.0
        maximum = limit_weight_scalar(
            slider,
            float(part.limit_min[i]),
            float(part.limit_mid[i]),
            float(part.limit_max[i]),
        )
        current = float(output_tracks[track])
        if current > maximum:
            output_tracks[track] = lerp(current, maximum, muzzle_lips)


def _stage_influences(part: CompiledFacialPart, output_tracks: np.ndarray) -> None:
    for i in range(part.infl_num):
        track = int(part.infl_tracks[i])
        weight = float(output_tracks[track])
        if weight <= 0.0:
            continue
        start = int(part.infl_row_ptr[i])
        end = int(part.infl_row_ptr[i + 1])
        influence = float(np.sum(output_tracks[part.infl_indices[start:end]]))
        influence_type = int(part.infl_types[i])
        if influence >= 1.0:
            weight = 0.0
        elif influence_type == INFLUENCE_LINEAR:
            weight = min(weight, 1.0 - influence)
        elif influence_type == INFLUENCE_EXPONENTIAL:
            weight *= 1.0 - influence * influence
        elif influence_type == INFLUENCE_ORGANIC:
            opposite = 1.0 - influence
            weight *= opposite * opposite
        output_tracks[track] = weight


def _stage_upper_lower(
    part: CompiledFacialPart,
    upper_face: float,
    lower_face: float,
    output_tracks: np.ndarray,
) -> None:
    if not len(part.ulf_tracks):
        return
    part.ulf_values[:] = (1.0, upper_face, lower_face)
    np.take(part.ulf_values, part.ulf_parts, out=part.ulf_mults)
    np.take(output_tracks, part.ulf_tracks, out=part.ulf_current)
    np.multiply(part.ulf_current, part.ulf_mults, out=part.ulf_current)
    np.clip(part.ulf_current, 0.0, 1.0, out=part.ulf_current)
    output_tracks[part.ulf_tracks] = part.ulf_current


def _stage_lipsync_overrides(
    runtime: CompiledFacialRuntime,
    lipsync_env: float,
) -> None:
    if lipsync_env == 0.0:
        return
    start = int(runtime.segments.lipsync_ovr_start)
    for offset, main_track in enumerate(runtime.lipsync_override_map):
        override = float(runtime.input_tracks[start + offset])
        runtime.output_tracks[int(main_track)] *= lerp(1.0, override, lipsync_env)


def _stage_lipsync_poses(part: CompiledFacialPart, runtime: CompiledFacialRuntime) -> None:
    if not len(part.lps_tracks):
        return
    np.take(runtime.input_tracks, part.lps_out_indices, out=part.lps_weights)
    np.take(runtime.output_tracks, part.lps_tracks, out=part.lps_current)
    np.add(part.lps_current, part.lps_weights, out=part.lps_current)
    np.clip(part.lps_current, 0.0, 1.0, out=part.lps_current)
    runtime.output_tracks[part.lps_tracks] = part.lps_current


def _stage_inbetweens(part: CompiledFacialPart, output_tracks: np.ndarray) -> np.ndarray:
    weights = part.ib_weights
    weights.fill(0.0)
    for pose in range(part.num_main_poses):
        weight = float(output_tracks[int(part.main_tracks[pose])])
        start = int(part.ib_row_ptr[pose])
        end = int(part.ib_row_ptr[pose + 1])
        count = end - start
        if weight < WEIGHT_THRESHOLD:
            continue
        if count == 1:
            weights[start] = weight
            continue
        thresholds = part.ib_thresholds[start:end]
        scope_start = int(part.sm_row_ptr[pose])
        if weight <= thresholds[0]:
            weights[start] = weight * float(part.ib_scope_mults[scope_start])
        elif weight >= thresholds[count - 1]:
            weights[end - 1] = 1.0
        else:
            upper = int(np.searchsorted(thresholds, weight, side="right"))
            lower = upper - 1
            upper_weight = (
                weight - thresholds[lower]
            ) * float(part.ib_scope_mults[scope_start + upper - 1])
            weights[start + lower] = 1.0 - upper_weight
            weights[start + upper] = upper_weight
    return weights


def _stage_correctives(
    part: CompiledFacialPart,
    output_tracks: np.ndarray,
    ib_weights: np.ndarray,
    lod: int,
) -> np.ndarray:
    weights = part.corr_weights
    weights.fill(1.0)
    for corrective in range(part.num_correctives):
        start = int(part.gcorr_row_ptr[corrective])
        end = int(part.gcorr_row_ptr[corrective + 1])
        for index in range(start, end):
            if int(part.gcorr_flags[index]) > lod:
                weights[corrective] = 0.0
                break
            parent = float(output_tracks[int(part.gcorr_tracks[index])])
            weights[corrective] *= max(0.0, min(1.0, parent))
    for corrective in range(part.num_correctives):
        if weights[corrective] <= 0.0:
            continue
        start = int(part.icorr_row_ptr[corrective])
        end = int(part.icorr_row_ptr[corrective + 1])
        for index in range(start, end):
            if int(part.icorr_flags[index]) > lod:
                weights[corrective] = 0.0
                break
            reference = int(part.icorr_tracks[index])
            parent = float(ib_weights[reference]) if reference < len(ib_weights) else 0.0
            weights[corrective] *= max(0.0, min(1.0, parent))
    return weights


def _stage_corrective_influences(
    part: CompiledFacialPart,
    weights: np.ndarray,
) -> None:
    for index in range(part.num_corr_infl):
        corrective = int(part.corr_infl_pose_idx[index])
        current = float(weights[corrective])
        if current <= WEIGHT_THRESHOLD:
            continue
        start = int(part.corr_infl_row_ptr[index])
        end = int(part.corr_infl_row_ptr[index + 1])
        influence = float(np.sum(weights[part.corr_infl_influencers[start:end]]))
        flags = int(part.corr_infl_types[index])
        by_speed = bool(flags & 1)
        linear = bool(flags & 2)
        if linear:
            opposite = 1.0 - influence
            current *= opposite
            if by_speed:
                current *= opposite
        elif influence >= 1.0:
            current = 0.0
        elif not by_speed:
            current = min(current, 1.0 - influence)
        else:
            current *= 1.0 - influence * influence
        weights[corrective] = max(0.0, current)


def _multiply_xyzw(left: np.ndarray, right: np.ndarray, out: np.ndarray) -> None:
    lx = left[:, 0]
    ly = left[:, 1]
    lz = left[:, 2]
    lw = left[:, 3]
    rx = right[:, 0]
    ry = right[:, 1]
    rz = right[:, 2]
    rw = right[:, 3]
    out[:, 0] = lw * rx + lx * rw + ly * rz - lz * ry
    out[:, 1] = lw * ry - lx * rz + ly * rw + lz * rx
    out[:, 2] = lw * rz + lx * ry - ly * rx + lz * rw
    out[:, 3] = lw * rw - lx * rx - ly * ry - lz * rz


def _nlerp(
    current: np.ndarray,
    target: np.ndarray,
    weight: float,
    output: np.ndarray,
    dot: np.ndarray,
    norm: np.ndarray,
    sign: np.ndarray,
    valid: np.ndarray,
    negative: np.ndarray,
    safe_norm: np.ndarray,
) -> None:
    np.einsum("ij,ij->i", current, target, out=dot)
    sign.fill(1.0)
    np.less(dot, 0.0, out=negative)
    np.putmask(sign, negative, -1.0)
    np.multiply(target, sign[:, None], out=output)
    np.subtract(output, current, out=output)
    output *= weight
    output += current
    np.einsum("ij,ij->i", output, output, out=norm)
    np.sqrt(norm, out=norm)
    np.greater_equal(norm, 1e-8, out=valid)
    np.copyto(safe_norm, norm)
    for index in range(len(valid)):
        if not valid[index]:
            safe_norm[index] = 1.0
    output /= safe_norm[:, None]
    for index in range(len(valid)):
        if not valid[index]:
            output[index] = current[index]


def _blend_poses(
    poses: CompiledPoseArrays,
    weights: np.ndarray,
    runtime: CompiledFacialRuntime,
) -> None:
    for pose in range(poses.num_poses):
        weight = float(weights[pose])
        if weight <= WEIGHT_THRESHOLD:
            continue
        start = int(poses.row_ptr[pose])
        end = int(poses.row_ptr[pose + 1])
        count = end - start
        if count <= 0:
            continue
        bones = poses.bones[start:end]
        quats = poses.quats[start:end]
        trans = poses.trans[start:end]
        current_quats = poses.current_quats[:count]
        current_trans = poses.current_trans[:count]
        np.take(runtime.bone_quats, bones, axis=0, out=current_quats)
        np.take(runtime.bone_trans, bones, axis=0, out=current_trans)
        np.multiply(trans, weight, out=poses.delta_trans[:count])
        np.add(current_trans, poses.delta_trans[:count], out=current_trans)
        runtime.bone_trans[bones] = current_trans
        full_quats = poses.full_quats[:count]
        _multiply_xyzw(current_quats, quats, full_quats)
        if weight >= 1.0 - 1e-5:
            runtime.bone_quats[bones] = full_quats
        else:
            blend = poses.blend_quats[:count]
            _nlerp(
                current_quats,
                full_quats,
                weight,
                blend,
                poses.dot[:count],
                poses.norm[:count],
                poses.sign[:count],
                poses.valid[:count],
                poses.negative[:count],
                poses.safe_norm[:count],
            )
            runtime.bone_quats[bones] = blend


def _stage_wrinkles(part: CompiledFacialPart, output_tracks: np.ndarray) -> None:
    count = len(part.wrinkle_source_tracks)
    if not count:
        return
    np.take(output_tracks, part.wrinkle_source_tracks, out=part.wrinkle_buffer)
    np.subtract(1.0, part.wrinkle_buffer, out=part.wrinkle_buffer)
    np.square(part.wrinkle_buffer, out=part.wrinkle_buffer)
    np.subtract(1.0, part.wrinkle_buffer, out=part.wrinkle_buffer)
    np.clip(part.wrinkle_buffer, 0.0, 1.0, out=part.wrinkle_buffer)
    start = part.wrinkle_start_track
    output_tracks[start:start + count] = part.wrinkle_buffer


def _solve_part(
    runtime: CompiledFacialRuntime,
    part: CompiledFacialPart,
    lod: int,
    lod_weight: float,
) -> None:
    output = runtime.output_tracks
    upper_face = clamp_scalar(float(output[ENV_UPPER_FACE]), 0.0, 1.0)
    lower_face = clamp_scalar(float(output[ENV_LOWER_FACE]), 0.0, 1.0)
    lipsync_env = clamp_scalar(float(output[ENV_LIPSYNC]), 0.0, 1.0)
    jali_jaw = clamp_scalar(float(output[ENV_JALI_JAW]), 0.0, 2.0)
    jali_lips = clamp_scalar(float(output[ENV_JALI_LIPS]), 0.0, 2.0)
    muzzle_lips = clamp_scalar(float(output[ENV_MUZZLE_LIPS]), 0.0, 1.0)
    muzzle_eyes = clamp_scalar(float(output[ENV_MUZZLE_EYES]), 0.0, 1.0)
    muzzle_brows = clamp_scalar(float(output[ENV_MUZZLE_BROWS]), 0.0, 1.0)
    muzzle_eye_dir = clamp_scalar(float(output[ENV_MUZZLE_EYE_DIR]), 0.0, 1.0)
    _stage_envelopes(
        part,
        runtime.input_tracks,
        output,
        lod,
        lod_weight,
        muzzle_eyes,
        muzzle_brows,
        muzzle_eye_dir,
    )
    _stage_limits(part, jali_jaw, jali_lips, muzzle_lips, lipsync_env, output)
    _stage_influences(part, output)
    _stage_upper_lower(part, upper_face, lower_face, output)
    _stage_lipsync_overrides(runtime, lipsync_env)
    _stage_lipsync_poses(part, runtime)
    _stage_influences(part, output)
    ib_weights = _stage_inbetweens(part, output)
    corr_weights = _stage_correctives(part, output, ib_weights, lod)
    if part.num_corr_infl:
        _stage_corrective_influences(part, corr_weights)
    _blend_poses(part.main_poses, ib_weights, runtime)
    if part.num_correctives:
        _blend_poses(part.corrective_poses, corr_weights, runtime)
    _stage_wrinkles(part, output)


def solve_runtime(
    runtime: CompiledFacialRuntime,
    input_tracks=None,
    lod: int = 0,
    lod_weight: float = 0.0,
):
    if input_tracks is not None and input_tracks is not runtime.input_tracks:
        np.copyto(runtime.input_tracks, np.asarray(input_tracks, dtype=np.float32))
    runtime.reset()
    for part in runtime.parts:
        _solve_part(runtime, part, int(lod), float(lod_weight))
    return runtime.bone_quats, runtime.bone_trans, runtime.output_tracks
