from __future__ import annotations

import time
from typing import Optional
import numpy as np
import bpy
import bpy.app.handlers
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, IntProperty
from bpy.types import Operator

from . import rig_binding


# Constants

WEIGHT_THRESHOLD = 0.001

# Envelope track indices (fixed positions in every CP77 facial rig)
_T_UPPER_FACE       = 1
_T_LOWER_FACE       = 2
_T_LIPSYNC_ENV      = 4
_T_LIPSYNC_LEFT     = 5
_T_LIPSYNC_RIGHT    = 6
_T_JALI_JAW         = 7
_T_JALI_LIPS        = 8
_T_MUZZLE_LIPS      = 9
_T_MUZZLE_EYES      = 10
_T_MUZZLE_BROWS     = 11
_T_MUZZLE_EYE_DIR   = 12

# other_muzzles lookup: indexed by env_type (0-5)
#   0=MUZZLE_LIPS, 1=MUZZLE_JAW → 1.0 (handled by stage 4)
#   2=MUZZLE_EYES, 3=MUZZLE_BROWS, 4=MUZZLE_EYE_DIRECTIONS, 5=MUZZLE_NONE
_MUZZLE_EYES      = 2
_MUZZLE_BROWS     = 3
_MUZZLE_EYE_DIR   = 4

# Influence type constants
_INFL_LINEAR      = 0
_INFL_EXPONENTIAL = 1
_INFL_ORGANIC     = 2

# Lipsync side constants
_SIDE_MID   = 0
_SIDE_LEFT  = 1
_SIDE_RIGHT = 2

_PART_NONE    = 0   # passthrough (1.0)
_PART_UPPER   = 1
_PART_LOWER   = 2

# Handler re-registration guard
_solving = False


# Quaternion helpers

def _quat_mul_batch(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Batch quaternion multiply: a[N,4] * b[N,4] → result[N,4]  (xyzw convention).
    """
    ax, ay, az, aw = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    bx, by, bz, bw = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    return np.stack([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], axis=1)


def _quat_nlerp_batch(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """
    Normalized lerp between a[N,4] and b[N,4] at scalar blend t.
    Now Including shortest-path alignment and zero-collapse fallback.
    """

    dot_products = np.sum(a * b, axis=1, keepdims=True)
    b_corrected = np.where(dot_products < 0, -b, b)

    interp = a + t * (b_corrected - a)
    norms = np.linalg.norm(interp, axis=1, keepdims=True)
    _norms = np.where(norms < 1e-8, 1.0, norms)
    result = interp / _norms

    result = np.where(norms < 1e-8, a, result)

    return result

# Per-part helpers

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _clamp02(x: float) -> float:
    return max(0.0, min(2.0, x))


def _limit_weight(slider: float, mn: float, mid: float, mx: float) -> float:
    """Map JALI slider (0–2) to a maximum allowed pose weight (0–1)."""
    if slider <= 1.0:
        v = mn + slider * (mid - mn)
        lo, hi = (mn, mid) if mn < mid else (mid, mn)
    else:
        v = mid + (slider - 1.0) * (mx - mid)
        lo, hi = (mid, mx) if mid < mx else (mx, mid)
    return max(lo, min(hi, v))


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


# Stage implementations (operates on numpy arrays in-place)

def _stage_3_envelope_weights(
    part,
    in_tracks:  np.ndarray,   # [T] float32  original input
    lod:        int,
    lod_weight: float,
    muzzle_eyes: float,
    muzzle_brows: float,
    muzzle_eye_dir: float,
    out_tracks: np.ndarray,   # [T] float32  modified in-place
) -> None:
    """
    Stage 3: Copy main pose weights from in_tracks, apply LOD gate and muzzle.
    Jaw/lips poses (env_types 0,1) pass through at 1.0 muzzle — handled by stage 4.
    """
    # other_muzzles per entry: indexed by env_type
    other_muzzles = np.ones(6, dtype=np.float32)
    other_muzzles[_MUZZLE_EYES]    = 1.0 - muzzle_eyes
    other_muzzles[_MUZZLE_BROWS]   = 1.0 - muzzle_brows
    other_muzzles[_MUZZLE_EYE_DIR] = 1.0 - muzzle_eye_dir

    env_tracks = part.env_tracks   # [M] int16
    env_lods   = part.env_lods     # [M] uint8
    env_types  = part.env_types    # [M] uint8

    # Base weights from input tracks, clamped [0,1]
    weights = np.clip(in_tracks[env_tracks].astype(np.float32), 0.0, 1.0)

    # LOD gating
    above = env_lods > lod    # active this LOD — apply muzzle, full contribution
    at    = env_lods == lod   # boundary — fade with lod_weight
    below = env_lods < lod    # lower-detail — zero out

    muzzle_per_entry = other_muzzles[env_types]

    weights = np.where(above, weights * muzzle_per_entry, weights)
    weights = np.where(at,    weights * muzzle_per_entry * (1.0 - lod_weight), weights)
    weights = np.where(below, 0.0, weights)
    weights[weights <= WEIGHT_THRESHOLD] = 0.0

    # Scatter back — env_tracks are unique per part (one mapping per main pose track)
    out_tracks[env_tracks] = weights


def _stage_4_global_limits(
    part,
    jali_jaw:    float,
    jali_lips:   float,
    muzzle_lips: float,
    lipsync_env: float,
    out_tracks:  np.ndarray,
) -> None:
    """
    Stage 4: Apply JALI jaw/lips slider limits to pose weights.
    Only runs if lipsync_env > 0.
    """
    if lipsync_env == 0.0:
        return

    envelopes = [jali_jaw, jali_lips]  # indexed by limit_envelope (0=jaw, 1=lips)

    for i in range(part.limit_num):
        t_idx  = int(part.limit_tracks[i])
        env_id = int(part.limit_envelope[i])
        slider = envelopes[env_id] if env_id < 2 else 1.0
        max_w  = _limit_weight(
            slider,
            float(part.limit_min[i]),
            float(part.limit_mid[i]),
            float(part.limit_max[i]),
        )
        current = out_tracks[t_idx]
        if current > max_w:
            out_tracks[t_idx] = _lerp(current, max_w, muzzle_lips)


def _stage_5_9_influences(part, out_tracks: np.ndarray) -> None:
    """
    Stages 5 & 9: Suppress poses that are opposed by other active poses.
    """
    for i in range(part.infl_num):
        t_idx = int(part.infl_tracks[i])
        w = float(out_tracks[t_idx])
        if w <= 0.0:
            continue

        s = int(part.infl_row_ptr[i])
        e = int(part.infl_row_ptr[i + 1])
        inf_sum = float(np.sum(out_tracks[part.infl_indices[s:e]]))

        itype = int(part.infl_types[i])
        if inf_sum >= 1.0:
            w = 0.0
        elif itype == _INFL_LINEAR:
            w = min(w, 1.0 - inf_sum)
        elif itype == _INFL_EXPONENTIAL:
            w *= 1.0 - inf_sum * inf_sum
        elif itype == _INFL_ORGANIC:
            opp = 1.0 - inf_sum
            w *= opp * opp

        out_tracks[t_idx] = w


def _stage_6_upper_lower(
    part,
    upper_face:  float,
    lower_face:  float,
    out_tracks:  np.ndarray,
) -> None:
    """Stage 6: Multiply each pose by its upper/lower face envelope.
    Part 0 = passthrough (1.0), Part 1 = upper, Part 2 = lower.
    """
    fw = np.array([1.0, upper_face, lower_face], dtype=np.float32)
    mults = fw[part.ulf_parts]   # [M] per-entry multiplier
    cur   = out_tracks[part.ulf_tracks].astype(np.float32)
    out_tracks[part.ulf_tracks] = np.clip(cur * mults, 0.0, 1.0)


def _stage_7_lipsync_overrides(
    setup,
    lipsync_env: float,
    in_tracks:   np.ndarray,
    out_tracks:  np.ndarray,
    seg,                          # TrackSegments
) -> None:
    """
    Stage 7: Override tracks suppress main pose weights based on lipsync activity.
    formula: main_weight *= lerp(1.0, override_v, lipsync_env)
    At lipsync_env=0 → scale=1.0 (no suppression), at lipsync_env=1 → scale=override_v.
    """
    if lipsync_env == 0.0:
        return

    ovr_map    = setup.lipsync_override_idx_map   # [86] main pose track indices
    ovr_start  = seg.lipsync_ovr_start            # = 154

    for j, main_track in enumerate(ovr_map):
        ovr_track   = ovr_start + j
        override_v  = float(in_tracks[ovr_track])
        scale       = _lerp(1.0, override_v, lipsync_env)
        out_tracks[int(main_track)] *= scale


def _stage_8_lipsync_poses(
        part,
        in_tracks: np.ndarray,
        out_tracks: np.ndarray,
        seg,
        ) -> None:
    """
    Stage 8: Add lipsync animation pose weights directly on top of main pose weights.
    lipsync_track_idx = lout_start + (main_track - num_envelope_tracks)
    """
    num_env = seg.envelope_end  # 13
    lout_start = seg.lipsync_out_start  # e.g., 240

    lps_tracks = part.lps_tracks  # main pose track indices

    # Map the main pose track index to its matching lipsync output track
    lps_out_indices = (lps_tracks.astype(np.int32) - num_env) + lout_start

    lipsync_weights = in_tracks[lps_out_indices].astype(np.float32)
    cur = out_tracks[lps_tracks].astype(np.float32)
    out_tracks[lps_tracks] = np.clip(cur + lipsync_weights, 0.0, 1.0)


def _stage_10_inbetween_weights(
    part,
    out_tracks: np.ndarray,
) -> np.ndarray:
    """
    Stage 10: Distribute each main pose's scalar weight across its inbetween poses.
    Returns ib_weights: float32 array of length num_ib_poses.
    """
    num_main   = part.num_main_poses
    num_ib     = part.num_ib_poses
    ib_weights = np.zeros(num_ib, dtype=np.float32)

    main_tracks    = part.main_tracks       # [num_main] int16
    ib_row_ptr     = part.ib_row_ptr        # [num_main+1] int32
    ib_thresholds  = part.ib_thresholds     # [num_ib] float32
    sm_row_ptr     = part.sm_row_ptr        # [num_main+1] int32
    ib_scope_mults = part.ib_scope_mults    # [num_scope_mults] float32

    for m in range(num_main):
        w = float(out_tracks[int(main_tracks[m])])
        ib_s = int(ib_row_ptr[m])
        ib_e = int(ib_row_ptr[m + 1])
        n    = ib_e - ib_s

        if w < WEIGHT_THRESHOLD:
            continue   # output slice stays zero

        if n == 1:
            ib_weights[ib_s] = w
            continue

        thresholds = ib_thresholds[ib_s : ib_e]  # length n
        sm_s       = int(sm_row_ptr[m])           # start of scope mults for this pose

        if w <= thresholds[0]:
            # Below first inbetween threshold — scale against it
            ib_weights[ib_s] = w * float(ib_scope_mults[sm_s])

        elif w >= thresholds[n - 1]:
            # At or beyond last threshold — full weight on last inbetween
            ib_weights[ib_e - 1] = 1.0

        else:
            # Binary search for bracketing inbetween
            # np.searchsorted gives end: thresholds[end-1] <= w < thresholds[end]
            end   = int(np.searchsorted(thresholds, w, side='right'))
            start = end - 1
            # scope_mults[sm_s + end - 1] is the reciprocal of the gap width
            end_w = (w - thresholds[start]) * float(ib_scope_mults[sm_s + end - 1])
            ib_weights[ib_s + start] = 1.0 - end_w
            ib_weights[ib_s + end]   = end_w

    return ib_weights


def _stage_12_13_correctives(
    part,
    out_tracks:  np.ndarray,
    ib_weights:  np.ndarray,
    lod:         int,
) -> np.ndarray:
    """
    Stages 12 + 13: Compute corrective pose weights.
    Returns corr_weights: float32 array of length num_correctives.

    Stage 12 (GCE): multiply by main pose track weights.
    Stage 13 (ICE): multiply by inbetween pose weights.
    Entries with flag > lod zero the corrective.
    """
    n_corr = part.num_correctives
    if n_corr == 0:
        return np.zeros(0, dtype=np.float32)

    corr_weights = np.ones(n_corr, dtype=np.float32)

    #  Stage 12: GCE
    gcorr_row_ptr = part.gcorr_row_ptr
    gcorr_tracks  = part.gcorr_tracks
    gcorr_flags   = part.gcorr_flags

    for c in range(n_corr):
        s = int(gcorr_row_ptr[c])
        e = int(gcorr_row_ptr[c + 1])
        for k in range(s, e):
            flag = int(gcorr_flags[k])
            if flag > lod:
                corr_weights[c] = 0.0
                break
            parent_w = float(out_tracks[int(gcorr_tracks[k])])
            corr_weights[c] *= max(0.0, min(1.0, parent_w))

    #  Stage 13: ICE
    icorr_row_ptr = part.icorr_row_ptr
    icorr_tracks  = part.icorr_tracks
    icorr_flags   = part.icorr_flags

    for c in range(n_corr):
        if corr_weights[c] <= 0.0:
            continue
        s = int(icorr_row_ptr[c])
        e = int(icorr_row_ptr[c + 1])
        for k in range(s, e):
            flag = int(icorr_flags[k])
            if flag > lod:
                corr_weights[c] = 0.0
                break
            ib_ref = int(icorr_tracks[k])
            parent_w = float(ib_weights[ib_ref]) if ib_ref < len(ib_weights) else 0.0
            corr_weights[c] *= max(0.0, min(1.0, parent_w))

    return corr_weights


def _stage_14_corrective_influences(
    part,
    corr_weights: np.ndarray,
) -> None:
    """
    Stage 14: Suppress corrective poses that are opposed by other active correctives.
    Modifies corr_weights in-place.

    Result by flags value:
      0 (neither):  simple clamp  → min(w, 1-s)
      1 (speed):    exponential   → w *= 1 - s²
      2 (linear):   linear corr   → w *= (1-s)
      3 (both):     organic       → w *= (1-s)²
    """
    _FLAG_BY_SPEED          = 1
    _FLAG_LINEAR_CORRECTION = 2

    row_ptr      = part.corr_infl_row_ptr
    influencers  = part.corr_infl_influencers
    pose_indices = part.corr_infl_pose_idx
    types        = part.corr_infl_types

    for i in range(part.num_corr_infl):
        c = int(pose_indices[i])
        current = float(corr_weights[c])
        if current <= WEIGHT_THRESHOLD:
            continue

        s = int(row_ptr[i])
        e = int(row_ptr[i + 1])
        inf_sum = float(np.sum(corr_weights[influencers[s:e]]))

        flags = int(types[i])
        by_speed          = bool(flags & _FLAG_BY_SPEED)
        linear_correction = bool(flags & _FLAG_LINEAR_CORRECTION)

        if linear_correction:
            opp = 1.0 - inf_sum
            current *= opp
            if by_speed:
                current *= opp          # total: current *= (1-s)²
        else:
            if inf_sum >= 1.0:
                current = 0.0
            elif not by_speed:
                current = min(current, 1.0 - inf_sum)   # simple clamp
            else:  # by_speed only
                current *= 1.0 - inf_sum * inf_sum       # exponential

        corr_weights[c] = max(0.0, current)


def _stage_15_16_blend_transforms(
    pose_arrays,
    weights:      np.ndarray,    # [num_poses] float32
    bone_quats:   np.ndarray,    # [num_bones, 4] float32 xyzw — modified in-place
    bone_trans:   np.ndarray,    # [num_bones, 3] float32     — modified in-place
) -> None:
    """
    Stages 15 & 16: Additively blend weighted bone transforms.

    For each active pose, affected bones receive:
      translation += delta_trans * weight
      rotation     = nlerp(current, current * delta_rot, weight)

    Bones are processed per-pose but the per-bone math within a pose
    is fully vectorized via _quat_mul_batch.
    """
    row_ptr    = pose_arrays.row_ptr     # [num_poses+1] int32
    pose_bones = pose_arrays.pose_bones  # [total] int16
    pose_quats = pose_arrays.pose_quats  # [total, 4] float32 xyzw
    pose_trans = pose_arrays.pose_trans  # [total, 3] float32

    for ib in range(pose_arrays.num_poses):
        w = float(weights[ib])
        if w <= WEIGHT_THRESHOLD:
            continue

        s = int(row_ptr[ib])
        e = int(row_ptr[ib + 1])
        if s == e:
            continue

        bones  = pose_bones[s:e].astype(np.int32)   # [K]
        dq     = pose_quats[s:e]                     # [K, 4] xyzw
        dt     = pose_trans[s:e]                     # [K, 3]

        cur_q  = bone_quats[bones]   # [K, 4]

        # Translation: always linear
        bone_trans[bones] += dt * w

        # Rotation: quat multiply then nlerp
        full_q = _quat_mul_batch(cur_q, dq)  # [K, 4]
        if w >= 1.0 - 1e-5:
            bone_quats[bones] = full_q
        else:
            bone_quats[bones] = _quat_nlerp_batch(cur_q, full_q, w)


def _stage_17_wrinkles(
    part,
    out_tracks: np.ndarray,
    wrinkle_start: int,
) -> None:
    """
    Stage 17: Compute wrinkle track values.
    wrinkle[i] = 1 - (1 - out_tracks[source_track[i]])^2
    """
    if part.wrinkle_count == 0:
        return

    src = part.wrinkle_source_tracks.astype(np.int32)
    u   = 1.0 - out_tracks[src]
    out_tracks[wrinkle_start : wrinkle_start + part.wrinkle_count] = np.clip(
        1.0 - u * u, 0.0, 1.0
    )


# Per-part solve

def _solve_part(
    part,
    setup,
    seg,
    in_tracks:  np.ndarray,
    out_tracks: np.ndarray,
    bone_quats: np.ndarray,
    bone_trans: np.ndarray,
    lod:        int,
    lod_weight: float,
) -> None:
    """Run all 17 stages for one facial part (tongue / eyes / face)."""

    #  Extract envelope scalars
    upper_face    = _clamp02(float(out_tracks[_T_UPPER_FACE]))
    lower_face    = _clamp02(float(out_tracks[_T_LOWER_FACE]))
    lipsync_env   = _clamp01(float(out_tracks[_T_LIPSYNC_ENV]))
    jali_jaw      = _clamp02(float(out_tracks[_T_JALI_JAW]))
    jali_lips     = _clamp02(float(out_tracks[_T_JALI_LIPS]))
    muzzle_lips   = _clamp01(float(out_tracks[_T_MUZZLE_LIPS]))
    muzzle_eyes   = _clamp01(float(out_tracks[_T_MUZZLE_EYES]))
    muzzle_brows  = _clamp01(float(out_tracks[_T_MUZZLE_BROWS]))
    muzzle_eye_dir= _clamp01(float(out_tracks[_T_MUZZLE_EYE_DIR]))

    #  Stage 3
    _stage_3_envelope_weights(
        part, in_tracks, lod, lod_weight,
        muzzle_eyes, muzzle_brows, muzzle_eye_dir, out_tracks
    )

    #  Stage 4
    _stage_4_global_limits(part, jali_jaw, jali_lips, muzzle_lips, lipsync_env, out_tracks)

    #  Stage 5
    _stage_5_9_influences(part, out_tracks)

    #  Stage 6
    _stage_6_upper_lower(part, upper_face, lower_face, out_tracks)

    #  Stage 7
    _stage_7_lipsync_overrides(setup, lipsync_env, in_tracks, out_tracks, seg)

    #  Stage 8
    _stage_8_lipsync_poses(part, in_tracks, out_tracks, seg)

    #  Stage 9 (second pass of influences)
    _stage_5_9_influences(part, out_tracks)

    #  Stage 10
    ib_weights = _stage_10_inbetween_weights(part, out_tracks)

    #  Stages 11–14
    corr_weights = _stage_12_13_correctives(part, out_tracks, ib_weights, lod)
    if part.num_corr_infl > 0:
        _stage_14_corrective_influences(part, corr_weights)

    #  Stage 15
    _stage_15_16_blend_transforms(part.main_poses, ib_weights, bone_quats, bone_trans)

    #  Stage 16
    if part.num_correctives > 0:
        _stage_15_16_blend_transforms(part.corrective_poses, corr_weights, bone_quats, bone_trans)

    #  Stage 17
    _stage_17_wrinkles(part, out_tracks, part.wrinkle_start_track)


# Public numpy solver

def facial_solve_numpy(
    setup,
    rig,
    seg,
    in_tracks:  np.ndarray,
    lod:        int   = 0,
    lod_weight: float = 0.0,
):
    """
    Full facial solve.  Pure numpy.
    """
    num_bones  = rig.num_bones
    num_tracks = rig.num_tracks

    # Output bone buffers start at rest (identity rotation, zero translation)
    bone_quats = np.zeros((num_bones, 4), dtype=np.float32)
    bone_quats[:, 3] = 1.0   # w = 1 (identity quaternion xyzw)
    bone_trans = np.zeros((num_bones, 3), dtype=np.float32)

    # out_tracks starts as a copy of in_tracks — modified in-place by each stage
    out_tracks = in_tracks.copy()

    # Execute parts in order: tongue (0), eyes (1), face (2)
    for part in (setup.tongue, setup.eyes, setup.face):
        _solve_part(
            part, setup, seg,
            in_tracks, out_tracks,
            bone_quats, bone_trans,
            lod, lod_weight,
        )

    return bone_quats, bone_trans, out_tracks


def write_bones(
    arm_obj:    bpy.types.Object,
    cache:      rig_binding.BindingCache,
    bone_quats: np.ndarray,
    bone_trans: np.ndarray,
) -> int:
    """
    Write solver output transforms back to Blender pose bones.
    Only writes used_bone_indices — all other bones are untouched.
    Returns the number of bones successfully written.
    """
    pb          = arm_obj.pose.bones
    bone_names  = cache.rig.bone_names
    used_idx    = cache.setup.used_bone_indices

    written = 0
    for i, bone_idx in enumerate(used_idx):
        name = str(bone_names[int(bone_idx)])
        if name not in pb:
            continue
        pbone = pb[name]
        pbone.rotation_mode = "QUATERNION"
        # xyzw → Blender (w, x, y, z)
        q = bone_quats[int(bone_idx)]
        pbone.rotation_quaternion = (float(q[3]), float(q[2]), float(q[0]), float(q[1]))
        t = bone_trans[int(bone_idx)]
        pbone.location = (float(-t[2]), float(t[0]), float(t[1]))
        written += 1

    return written



# frame_change_post handler

@persistent
def solve_frame(scene, depsgraph=None):
    """
    frame_change_post handler.  Runs the full facial solve for every bound
    armature in the scene.

    Timing is stored in bpy.app.driver_namespace["cp77_facial_last_ms"]
    for display in the UI panel.
    """
    global _solving
    if _solving:
        return   # prevent recursion
    _solving = True

    try:
        ns     = rig_binding._get_ns()
        timing = {}

        for arm_name, cache in list(ns.items()):
            # Skip non-cache entries (ns may contain other objects)
            if not isinstance(cache, rig_binding.BindingCache):
                continue

            arm_obj = scene.objects.get(arm_name)
            if arm_obj is None or arm_obj.type != "ARMATURE":
                continue
            if not rig_binding.is_bound(arm_obj):
                continue

            t0 = time.perf_counter()

            # Read track values from custom properties
            in_tracks = rig_binding.read_tracks(arm_obj, cache)

            # Solve
            bone_quats, bone_trans, out_tracks = facial_solve_numpy(
                cache.setup,
                cache.rig,
                cache.track_segments,
                in_tracks,
                lod        = _get_lod(scene),
                lod_weight = 0.0,
            )

            # Write transforms to pose bones
            write_bones(arm_obj, cache, bone_quats, bone_trans)

            # Write output tracks (wrinkles, lipsync outputs) back to custom props
            rig_binding.write_output_tracks(arm_obj, cache, out_tracks)

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            timing[arm_name] = elapsed_ms

        # Store timing for UI readout
        bpy.app.driver_namespace["cp77_facial_last_ms"] = timing

    except Exception as e:
        import traceback
        print(f"[CP77 Facial] Solver error: {e}")
        traceback.print_exc()
    finally:
        _solving = False


def _get_lod(scene) -> int:
    """Read the current LOD level from scene properties, defaulting to 0."""
    props = getattr(scene, "cp77_facial", None)
    if props is not None:
        return max(0, min(2, int(getattr(props, "lod_level", 0))))
    return 0


# Handler management

def is_solver_active() -> bool:
    return solve_frame in bpy.app.handlers.frame_change_post


def enable_solver(context) -> None:
    """Register the frame_change_post handler (idempotent)."""
    if not is_solver_active():
        bpy.app.handlers.frame_change_post.append(solve_frame)

    props = getattr(context.scene, "cp77_facial", None)
    if props is not None:
        props.solver_active = True


def disable_solver(context) -> None:
    """Unregister the frame_change_post handler (idempotent)."""
    handlers = bpy.app.handlers.frame_change_post
    while solve_frame in handlers:
        handlers.remove(solve_frame)

    props = getattr(context.scene, "cp77_facial", None)
    if props is not None:
        props.solver_active = False


def restore_handler_on_load() -> None:
    """
    Called by the load_post handler in __init__.py after a file reload.
    Re-registers solve_frame if the scene's solver_active flag is True.
    """
    for scene in bpy.data.scenes:
        props = getattr(scene, "cp77_facial", None)
        if props is not None and getattr(props, "solver_active", False):
            if not is_solver_active():
                bpy.app.handlers.frame_change_post.append(solve_frame)
            break


# Operators

class FACIAL_OT_ToggleSolver(Operator):
    """Enable or disable the real-time facial facial solver"""
    bl_idname  = "cp77_facial.toggle_solver"
    bl_label   = "Toggle Solver"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        # Require at least one bound armature in the scene
        for obj in context.scene.objects:
            if obj.type == "ARMATURE" and rig_binding.is_bound(obj):
                return True
        return False

    def execute(self, context):
        if is_solver_active():
            disable_solver(context)
            self.report({"INFO"}, "CP77 Facial Solver: disabled")
        else:
            enable_solver(context)
            self.report({"INFO"}, "CP77 Facial Solver: enabled")
        return {"FINISHED"}


class FACIAL_OT_SolveNow(Operator):
    """Run a single facial solve on the current frame (one-shot, no handler needed)"""
    bl_idname  = "cp77_facial.solve_now"
    bl_label   = "Solve Now"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        for obj in context.scene.objects:
            if obj.type == "ARMATURE" and rig_binding.is_bound(obj):
                return True
        return False

    def execute(self, context):
        solve_frame(context.scene)

        timing = bpy.app.driver_namespace.get("cp77_facial_last_ms", {})
        if timing:
            msgs = [f"'{n}': {ms:.1f} ms" for n, ms in timing.items()]
            self.report({"INFO"}, "Solved — " + ", ".join(msgs))
        else:
            self.report({"INFO"}, "Solve complete (no timing data)")
        return {"FINISHED"}


# Registration

_CLASSES = (
    FACIAL_OT_ToggleSolver,
    FACIAL_OT_SolveNow,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    disable_solver_global()
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


def disable_solver_global() -> None:
    """Remove handler regardless of scene property state (called on addon unregister)."""
    handlers = bpy.app.handlers.frame_change_post
    while solve_frame in handlers:
        handlers.remove(solve_frame)