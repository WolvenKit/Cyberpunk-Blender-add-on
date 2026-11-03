from __future__ import annotations

import numpy as np

from ....bartmoss.quaternion import multiply_xyzw_into, nlerp_xyzw_into
from ....bartmoss.scalar import clamp_scalar, limit_weight
from ...model.facial.constants import (
    WEIGHT_THRESHOLD,
    Envelope,
    Influence,
)
from .compiled import CompiledFacialPart, CompiledFacialRuntime, CompiledPoseArrays

# Upper/lower face envelopes are sliders: Sermo clamps them to 0..2, not 0..1.
FACE_ENVELOPE_MAX = 2.0


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
    # Sermo thresholds the clamped input before applying muzzles and LOD scaling.
    np.less_equal(weights, WEIGHT_THRESHOLD, out=part.env_threshold_mask)
    np.putmask(weights, part.env_threshold_mask, 0.0)
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
    output_tracks[part.env_tracks] = weights


def _stage_limits(
    part: CompiledFacialPart,
    jali_jaw: float,
    jali_lips: float,
    muzzle_lips: float,
    lipsync_env: float,
    output_tracks: np.ndarray,
) -> None:
    if lipsync_env == 0.0 or not part.limit_num:
        return
    envelope = part.limit_envelope
    slider = np.where(envelope == 0, jali_jaw, np.where(envelope == 1, jali_lips, 1.0))
    limit = limit_weight(
        slider,
        part.limit_min.astype(np.float64),
        part.limit_mid.astype(np.float64),
        part.limit_max.astype(np.float64),
    )
    tracks = part.limit_tracks
    current = output_tracks[tracks].astype(np.float64)
    over = current > limit
    if over.any():
        output_tracks[tracks[over]] = (current + muzzle_lips * (limit - current))[over]


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
        elif influence_type == Influence.LINEAR:
            weight = min(weight, 1.0 - influence)
        elif influence_type == Influence.EXPONENTIAL:
            weight *= 1.0 - influence * influence
        elif influence_type == Influence.ORGANIC:
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
    # Sermo applies the global override map once per part, like this does.
    if lipsync_env == 0.0:
        return
    targets = runtime.lipsync_override_map
    start = int(runtime.segments.lipsync_ovr_start)
    overrides = runtime.input_tracks[start : start + len(targets)].astype(np.float64)
    factors = (1.0 + lipsync_env * (overrides - 1.0)).astype(np.float32)
    runtime.output_tracks[targets] *= factors


def _stage_lipsync_poses(
    part: CompiledFacialPart, runtime: CompiledFacialRuntime
) -> None:
    if not len(part.lps_tracks):
        return
    np.take(runtime.input_tracks, part.lps_out_indices, out=part.lps_weights)
    np.take(runtime.output_tracks, part.lps_tracks, out=part.lps_current)
    np.add(part.lps_current, part.lps_weights, out=part.lps_current)
    np.clip(part.lps_current, 0.0, 1.0, out=part.lps_current)
    runtime.output_tracks[part.lps_tracks] = part.lps_current


def _ib_layout(part: CompiledFacialPart):
    layout = part.__dict__.get("_ib_layout")
    if layout is None:
        starts = np.asarray(part.ib_row_ptr[:-1], dtype=np.intp)
        ends = np.asarray(part.ib_row_ptr[1:], dtype=np.intp)
        counts = ends - starts
        owner = np.repeat(np.arange(part.num_main_poses), counts)
        layout = (
            starts,
            ends,
            counts,
            owner,
            np.asarray(part.sm_row_ptr[:-1], dtype=np.intp),
        )
        part.__dict__["_ib_layout"] = layout
    return layout


def _stage_inbetweens(
    part: CompiledFacialPart, output_tracks: np.ndarray
) -> np.ndarray:
    """Inbetween weights, vectorized"""
    weights = part.ib_weights
    weights.fill(0.0)
    if not part.num_main_poses:
        return weights
    starts, ends, counts, owner, scope_starts = _ib_layout(part)
    thresholds = part.ib_thresholds
    scopes = part.ib_scope_mults
    w32 = output_tracks[part.main_tracks]
    w = w32.astype(np.float64)
    active = w >= WEIGHT_THRESHOLD
    single = active & (counts == 1)
    weights[starts[single]] = w[single]
    multi = active & (counts > 1)
    if not multi.any():
        return weights
    first = thresholds[starts].astype(np.float64)
    last = thresholds[np.maximum(ends - 1, starts)].astype(np.float64)
    below = multi & (w <= first)
    weights[starts[below]] = w[below] * scopes[scope_starts[below]].astype(np.float64)
    above = multi & ~below & (w >= last)
    weights[(ends - 1)[above]] = 1.0
    between = np.flatnonzero(multi & ~below & ~above)
    if len(between):
        # Number of thresholds <= weight within each pose (searchsorted, side="right").
        reached = thresholds.astype(np.float64) <= w[owner]
        upper = np.bincount(owner[reached], minlength=part.num_main_poses)[between]
        lower = upper - 1
        upper_weight = (w32[between] - thresholds[starts[between] + lower]) * scopes[
            scope_starts[between] + upper - 1
        ]
        weights[starts[between] + lower] = np.float32(1.0) - upper_weight
        weights[starts[between] + upper] = upper_weight
    return weights


def _corrective_lod_mask(part: CompiledFacialPart, lod: int) -> np.ndarray:
    flagged = part.corr_flagged_by_lod.get(lod)
    if flagged is None:
        flagged = np.zeros(part.num_correctives, dtype=bool)
        flagged[part.corr_parent_owner[part.corr_parent_flags > lod]] = True
        part.corr_flagged_by_lod[lod] = flagged
    return flagged


def _stage_correctives(
    part: CompiledFacialPart,
    output_tracks: np.ndarray,
    ib_weights: np.ndarray,
    lod: int,
) -> np.ndarray:
    weights = part.corr_weights
    weights.fill(1.0)
    if not part.num_correctives:
        return weights
    index = part.corr_parent_index
    if len(index):
        from_ib = part.corr_parent_is_ib
        parents = np.empty(len(index), dtype=np.float32)
        parents[~from_ib] = output_tracks[index[~from_ib]]
        ib_index = index[from_ib]
        ib_values = np.zeros(len(ib_index), dtype=np.float32)
        in_range = ib_index < len(ib_weights)
        ib_values[in_range] = ib_weights[ib_index[in_range]]
        parents[from_ib] = ib_values
        # Sermo: a parent <= 0 zeroes the corrective, a parent > 1 counts as 1.
        parents = np.where(parents > 1.0, np.float32(1.0), parents)
        parents = np.where(parents <= 0.0, np.float32(0.0), parents)
        has_parents = part.corr_has_parents
        # reduceat multiplies each corrective's parents left to right.
        weights[has_parents] = np.multiply.reduceat(
            parents, part.corr_parent_starts[has_parents]
        )
    weights[_corrective_lod_mask(part, int(lod))] = 0.0
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
        # Sermo keeps negative results; the blend threshold ignores them.
        weights[corrective] = current


def _lod_widths(poses: CompiledPoseArrays, lod: int) -> np.ndarray:
    return poses.lod_widths[lod] if lod in (1, 2) else poses.lod_widths[0]


def _blend_poses_sequential(
    poses: CompiledPoseArrays,
    weights: np.ndarray,
    runtime: CompiledFacialRuntime,
    lod: int,
) -> None:
    widths = _lod_widths(poses, lod)
    for pose in range(poses.num_poses):
        weight = float(weights[pose])
        if weight <= WEIGHT_THRESHOLD:
            continue
        start = int(poses.row_ptr[pose])
        count = int(widths[pose])
        if count <= 0:
            continue
        end = start + count
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
        multiply_xyzw_into(current_quats, quats, full_quats)
        if weight == 1.0:
            runtime.bone_quats[bones] = full_quats
        else:
            blend = poses.blend_quats[:count]
            nlerp_xyzw_into(
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


def _queue_blend(
    batch: list, poses: CompiledPoseArrays, weights: np.ndarray, lod: int
) -> None:
    """Queue one pose set's blend for the frame"""
    # Compare in float64 like Python's float(weight) > threshold.
    active = np.flatnonzero(
        weights[: poses.num_poses].astype(np.float64) > WEIGHT_THRESHOLD
    )
    if len(active):
        batch.append((poses, weights.copy(), lod, active))


def _apply_blends(runtime: CompiledFacialRuntime, batch: list, lod: int) -> None:
    if not batch:
        return
    table = runtime.pose_table
    pose_weights = table.weights
    pose_weights.fill(0.0)
    for poses, weights, _lod, active in batch:
        pose_weights[poses.pose_offset + active] = weights[active]
    active_ids = np.concatenate(
        [poses.pose_offset + active for poses, _w, _lod, active in batch]
    )
    if not table.sign_safe[active_ids].all():
        # A near-180-degree pose rotation: use the exact per-pose nlerp sequence.
        for poses, weights, set_lod, _active in batch:
            _blend_poses_sequential(poses, weights, runtime, set_lod)
        return
    # Active rows (pose active and the row within this LOD's transform count), already
    # grouped by bone in application order because the table is pre-sorted.
    widths = table.lod_widths[lod] if lod in (1, 2) else table.lod_widths[0]
    is_active = np.zeros(table.num_poses, dtype=bool)
    is_active[active_ids] = True
    rows = np.flatnonzero(is_active[table.pose] & (table.local < widths[table.pose]))
    if not len(rows):
        return
    row_weights = pose_weights[table.pose[rows]]
    bones = table.bones[rows]
    run_start = np.flatnonzero(np.concatenate(([True], bones[1:] != bones[:-1])))
    # Translations: sequential per-bone sums in application order, exactly like the per-pose
    # loop (np.add.at is strictly sequential; reduceat is not bit-identical).
    np.add.at(runtime.bone_trans, bones, table.trans[rows] * row_weights[:, None])
    # Rotation factor per row: q for a full blend, (1-w)*1 + w*sign(q.w)*q otherwise.
    # nlerp(c, c*q, w) == normalize(c * that factor), so normalization is deferred
    # to _finish_rotations (normalize(a*b) == normalize(a)*normalize(b)).
    product = table.quats[rows]
    partial = row_weights != 1.0
    if partial.any():
        w = row_weights[partial][:, None]
        product[partial] = table.signed_quats[rows[partial]] * w + _IDENTITY_QUAT * (
            1.0 - w
        )
        runtime.partial_bones[bones[partial]] = True
    # Each bone's rotation is identity * F1 * F2 * ... in application order: multiply
    # neighbouring pairs within each bone's run, level by level (pairs never overlap because
    # the left element sits at an even position in its run; positions halve each level).
    seg = bones
    position = np.arange(len(seg)) - np.repeat(
        run_start, np.diff(np.append(run_start, len(seg)))
    )
    while len(seg) > 1:
        same_next = seg[1:] == seg[:-1]
        left = np.flatnonzero(same_next & ((position[:-1] & 1) == 0))
        if not len(left):
            break
        combined = np.empty((len(left), 4), dtype=np.float32)
        multiply_xyzw_into(product[left], product[left + 1], combined)
        product[left] = combined
        survivors = np.ones(len(seg), dtype=bool)
        survivors[left + 1] = False
        seg, product, position = (
            seg[survivors],
            product[survivors],
            position[survivors] >> 1,
        )
    runtime.bone_quats[seg] = product


_IDENTITY_QUAT = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)


def _finish_rotations(runtime: CompiledFacialRuntime) -> None:
    mask = runtime.partial_bones
    if not mask.any():
        return
    quats = runtime.bone_quats[mask]
    norm = np.sqrt(np.einsum("ij,ij->i", quats, quats))
    valid = norm >= 1e-8
    quats[valid] /= norm[valid, None]
    runtime.bone_quats[mask] = quats


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
    output_tracks[start : start + count] = part.wrinkle_buffer


def _solve_part(
    runtime: CompiledFacialRuntime,
    part: CompiledFacialPart,
    lod: int,
    lod_weight: float,
    batch: list,
) -> None:
    output = runtime.output_tracks
    upper_face = clamp_scalar(
        float(output[Envelope.UPPER_FACE]), 0.0, FACE_ENVELOPE_MAX
    )
    lower_face = clamp_scalar(
        float(output[Envelope.LOWER_FACE]), 0.0, FACE_ENVELOPE_MAX
    )
    lipsync_env = clamp_scalar(float(output[Envelope.LIPSYNC]), 0.0, 1.0)
    jali_jaw = clamp_scalar(float(output[Envelope.JALI_JAW]), 0.0, 2.0)
    jali_lips = clamp_scalar(float(output[Envelope.JALI_LIPS]), 0.0, 2.0)
    muzzle_lips = clamp_scalar(float(output[Envelope.MUZZLE_LIPS]), 0.0, 1.0)
    muzzle_eyes = clamp_scalar(float(output[Envelope.MUZZLE_EYES]), 0.0, 1.0)
    muzzle_brows = clamp_scalar(float(output[Envelope.MUZZLE_BROWS]), 0.0, 1.0)
    muzzle_eye_dir = clamp_scalar(float(output[Envelope.MUZZLE_EYE_DIR]), 0.0, 1.0)
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
    _queue_blend(batch, part.main_poses, ib_weights, lod)
    if part.num_correctives:
        _queue_blend(batch, part.corrective_poses, corr_weights, lod)
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
    batch: list = []
    for part in runtime.parts:
        _solve_part(runtime, part, int(lod), float(lod_weight), batch)
    _apply_blends(runtime, batch, int(lod))
    _finish_rotations(runtime)
    return runtime.bone_quats, runtime.bone_trans, runtime.output_tracks
