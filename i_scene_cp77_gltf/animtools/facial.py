from __future__ import annotations
import os 

"""
Design
- Operates on numpy arrays:
  - Rotations: q[N,4] as (x,y,z,w)
  - Translations: t[N,3]
  - Scales: s[N,3]
  - Tracks: tracks[M] float array 
"""

import json
from typing import Optional, Tuple, Sequence, List
import numpy as np
try:
    from pathlib import Path
except Exception:
    Path = None  

from dataclasses import dataclass

# Fallbacks if facial helpers aren’t in this module yet (hot‑reload safe)
try:
    TransformMaskEntry  
except NameError:
    @dataclass
    class TransformMaskEntry:
        index: int
        weight: float = 1.0

try:
    Pose  
except NameError:
    Pose = Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]  

try:
    build_track_name_map  
except NameError:
    def build_track_name_map(rig_info):  
        names = getattr(rig_info, "track_names", [])
        return {n: i for i, n in enumerate(names)}


from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Sequence, Tuple, List, Dict
import numpy as np

# ---------------------------
# Quaternion helpers (x,y,z,w)
# ---------------------------

def quat_normalize(q: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return q / n


def quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ax, ay, az, aw = np.moveaxis(a, -1, 0)
    bx, by, bz, bw = np.moveaxis(b, -1, 0)
    x = aw * bx + ax * bw + ay * bz - az * by
    y = aw * by - ax * bz + ay * bw + az * bx
    z = aw * bz + ax * by - ay * bx + az * bw
    w = aw * bw - ax * bx - ay * by - az * bz
    return np.stack([x, y, z, w], axis=-1)


def slerp(q0: np.ndarray, q1: np.ndarray, t: np.ndarray) -> np.ndarray:
    dot = np.sum(q0 * q1, axis=-1, keepdims=True)
    sign = np.where(dot < 0, -1.0, 1.0)
    q1 = q1 * sign
    dot = np.clip(np.abs(dot), 0.0, 1.0)
    eps = 1e-6
    use_lerp = dot > 1 - eps
    theta = np.arccos(dot)
    sin_theta = np.sin(theta)
    w0 = np.where(use_lerp, 1 - t, np.sin((1 - t) * theta) / np.where(sin_theta == 0, 1, sin_theta))
    w1 = np.where(use_lerp, t, np.sin(t * theta) / np.where(sin_theta == 0, 1, sin_theta))
    out = quat_normalize(q0 * w0 + q1 * w1)
    return out

# ---------------------------
# Data structures
# ---------------------------

@dataclass
class TransformMaskEntry:
    index: int
    weight: float = 1.0

TracksMode = Literal["interpolate", "add", "from_base"]

@dataclass
class FaceBank:
    # Dense pose banks ready for additive blending (sparse encoded as identity)
    # Shapes: [P, N, 4/3/3]
    q: np.ndarray
    t: np.ndarray
    s: np.ndarray

@dataclass
class FacialSetupFaceMeta:
    # Baked tables used at runtime to compute track weights / envelopes
    envelopes_track: np.ndarray         # [K] int16 track indices
    envelopes_lod: np.ndarray           # [K] int8 lod
    envelopes_type: np.ndarray          # [K] int8 (muzzle envelope type)

    global_limits_track: np.ndarray     # [G] int16
    global_limits_min: np.ndarray       # [G] float32
    global_limits_mid: np.ndarray       # [G] float32
    global_limits_max: np.ndarray       # [G] float32
    global_limits_type: np.ndarray      # [G] int8

    influenced_poses_track: np.ndarray  # [I] int16 (main pose track)
    influenced_poses_num: np.ndarray    # [I] int8  (how many indices slice)
    influenced_poses_type: np.ndarray   # [I] int8  (influence mode)
    influence_indices: np.ndarray       # [S] int16 (flat table of indices)

    upper_lower_track: np.ndarray       # [U] int16
    upper_lower_part: np.ndarray        # [U] int8 (upper/lower enum)

    lipsync_sides_track: np.ndarray     # [L] int16
    lipsync_sides_side: np.ndarray      # [L] int8 (left/right/center)

    # Main pose in-between topology
    mainposes_track: np.ndarray         # [P] int16
    mainposes_num_inbtw: np.ndarray     # [P] int16
    mainposes_inbtw: np.ndarray         # [sum(P.num_inbtw)] int16 (per main pose contiguous slices)
    inbtw_scope_multipliers: np.ndarray # [M] float32 (aux table)

    # Correctives (raw; detailed combination rules are handled elsewhere)
    global_corrective_entries: list
    inbetween_corrective_entries: list
    corrective_influenced_poses: list
    corrective_influence_indices: np.ndarray

    # Misc
    wrinkles: list

@dataclass
class TracksMapping:
    num_envelopes: int
    num_main_poses: int
    num_lipsync_overrides: int
    num_wrinkles: int

@dataclass
class FacialSetupAll:
    lipsync_override_index_mapping: np.ndarray  # [numOverrides] int16
    joint_regions: np.ndarray                   # [N] int8 per-joint region
    used_transform_indices: np.ndarray          # [T] int16 global list

    tracks_mapping: TracksMapping

    face_meta: FacialSetupFaceMeta
    face_main_bank: FaceBank
    face_corrective_bank: FaceBank

    # Optional banks + meta for eyes/tongue
    eyes_meta: Optional[FacialSetupFaceMeta] = None
    eyes_main_bank: Optional[FaceBank] = None
    eyes_corrective_bank: Optional[FaceBank] = None
    tongue_meta: Optional[FacialSetupFaceMeta] = None
    tongue_main_bank: Optional[FaceBank] = None
    tongue_corrective_bank: Optional[FaceBank] = None

    # Optional human-readable names (if you load them)
    face_corrective_names: Optional[List[str]] = None
    eyes_corrective_names: Optional[List[str]] = None
    tongue_corrective_names: Optional[List[str]] = None

@dataclass
class RigSkeletonInfo:
    num_bones: int
    parent_indices: np.ndarray       # [N] int16
    bone_names: list                 # [N] str
    track_names: list                # [M] str
    ls_q: np.ndarray                 # [N,4] local-space reference quats (x,y,z,w)
    ls_t: np.ndarray                 # [N,3] local-space reference translations
    ls_s: np.ndarray                 # [N,3] local-space reference scales

# ---------------------------
# Low-level blend helpers
# ---------------------------

def additive_local_pose_only(
    base_q: np.ndarray,
    base_t: np.ndarray,
    base_s: np.ndarray,
    add_q: np.ndarray,
    add_t: np.ndarray,
    add_s: np.ndarray,
    weight: float,
    mask: Optional[Sequence[TransformMaskEntry]] = None,
    use_scale: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Additive LS blend with optional transform mask.
    Engine-style: add_t scaled by weight; add_q slerp from identity by weight; scale optional.
    """
    w = float(np.clip(weight, 0.0, 10.0))  # allow >1, handled by identity slerp chunking elsewhere if needed
    ident = np.zeros_like(add_q)
    ident[..., 3] = 1.0

    out_q = base_q.copy(); out_t = base_t.copy(); out_s = base_s.copy()

    if mask is None:
        ww = np.full((base_q.shape[0], 1), w)
        dq = slerp(ident, add_q, ww)
        out_q = quat_mul(base_q, dq)
        out_t = base_t + add_t * ww
        if use_scale:
            out_s = base_s * (1.0 + (add_s - 1.0) * ww)
        return quat_normalize(out_q), out_t, out_s

    # masked/sparse path
    for e in mask:
        idx = int(e.index)
        wi = float(np.clip(e.weight * w, 0.0, 10.0))
        if wi <= 1e-8:
            continue
        dq = slerp(ident[idx:idx+1], add_q[idx:idx+1], np.array([[min(wi,1.0)]]))
        out_q[idx] = quat_mul(base_q[idx:idx+1], dq)[0]
        out_t[idx] = base_t[idx] + add_t[idx] * min(wi, 1.0)
        if use_scale:
            out_s[idx] = base_s[idx] * (1.0 + (add_s[idx] - 1.0) * min(wi, 1.0))

    return quat_normalize(out_q), out_t, out_s


def additive_local_pose_only_lipsync(
    base_q: np.ndarray,
    base_t: np.ndarray,
    base_s: np.ndarray,
    add_q: np.ndarray,
    add_t: np.ndarray,
    add_s: np.ndarray,
    weight: float,
    mask: Optional[Sequence[TransformMaskEntry]] = None,
    use_scale: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Like additive_local_pose_only but supports weights > 1 by repeated application."""
    whole = int(max(0, np.floor(weight)))
    frac = float(np.clip(weight - whole, 0.0, 1.0))
    q, t, s = base_q.copy(), base_t.copy(), base_s.copy()
    for _ in range(whole):
        q, t, s = additive_local_pose_only(q, t, s, add_q, add_t, add_s, 1.0, mask, use_scale)
    if frac > 0:
        q, t, s = additive_local_pose_only(q, t, s, add_q, add_t, add_s, frac, mask, use_scale)
    return q, t, s

# ---------------------------
# Tracks blending
# ---------------------------

def interpolate_tracks(out_tracks: np.ndarray, base_tracks: np.ndarray, add_tracks: np.ndarray, weight: float) -> None:
    n = min(len(out_tracks), len(base_tracks), len(add_tracks))
    out_tracks[:n] = base_tracks[:n] * (1.0 - weight) + add_tracks[:n] * weight


def add_tracks(out_tracks: np.ndarray, base_tracks: np.ndarray, add_tracks_arr: np.ndarray, weight: float) -> None:
    n = min(len(out_tracks), len(base_tracks), len(add_tracks_arr))
    out_tracks[:n] = base_tracks[:n] + add_tracks_arr[:n] * weight


def copy_tracks(out_tracks: np.ndarray, base_tracks: np.ndarray) -> None:
    n = min(len(out_tracks), len(base_tracks))
    out_tracks[:n] = base_tracks[:n]


def blend_tracks(
    out_tracks: np.ndarray,
    base_tracks: np.ndarray,
    add_tracks_arr: np.ndarray,
    mode: TracksMode,
    weight: float,
) -> None:
    if mode == "interpolate":
        interpolate_tracks(out_tracks, base_tracks, add_tracks_arr, weight)
    elif mode == "add":
        add_tracks(out_tracks, base_tracks, add_tracks_arr, weight)
    else:
        copy_tracks(out_tracks, base_tracks)

# ---------------------------
# Utilities / math helpers
# ---------------------------

def _ti(name_to_index: dict, name: str, default: int = -1) -> int:
    return int(name_to_index.get(name, default))

def _clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))

def _lerp(a: float, b: float, t: float) -> float:
    return float(a * (1.0 - t) + b * t)

def build_track_name_map(rig_info: RigSkeletonInfo) -> dict:
    return {n: i for i, n in enumerate(rig_info.track_names)}

# ---------------------------
# Lipsync helpers (offset mapping via TracksMapping)
# ---------------------------

def _lipsync_offsets(setup: FacialSetupAll) -> Tuple[int, int, int, int]:
    """Return (num_env, overrides_start, lipsync_start, total_main) indices."""
    tm = setup.tracks_mapping
    num_env = int(tm.num_envelopes)
    main_start = num_env
    overrides_start = num_env + int(tm.num_main_poses)
    lipsync_start = overrides_start + int(tm.num_lipsync_overrides)
    return num_env, overrides_start, lipsync_start, int(tm.num_main_poses)


def apply_lipsync_overrides_inplace(setup: FacialSetupAll, rig_info: RigSkeletonInfo, tracks: np.ndarray) -> None:
    """Multiply specific main-pose tracks by an override value blended by LipSyncEnvelope.
    multiplier = Lerp(lipSyncEnvelope, 1.0, overrideValue)
    """
    face = setup.face_meta
    name_to_index = build_track_name_map(rig_info)
    idx_env = _ti(name_to_index, "lipSyncEnvelope")
    M = tracks.shape[0]
    lipsyncEnvelope = _clamp(tracks[idx_env] if idx_env >= 0 else 0.0, 0.0, 1.0)
    num_env, overrides_start, _lipsync_start, _ = _lipsync_offsets(setup)

    # IndexMapping holds the destination main-pose track indices to be scaled
    mapping = setup.lipsync_override_index_mapping
    for i in range(len(mapping)):
        trk = int(mapping[i])
        src = overrides_start + i  # override value track
        if 0 <= trk < M and 0 <= src < M:
            ov = float(tracks[src])
            mult = _lerp(lipsyncEnvelope, 1.0, ov)  # env=0->1, env=1->ov
            tracks[trk] *= mult


def apply_lipsync_poses_inplace(setup: FacialSetupAll, rig_info: RigSkeletonInfo, tracks: np.ndarray) -> None:
    """Add lipsync extra tracks into their paired main tracks and clamp [0,1].
    Uses TracksMapping offsets; optional 'side' is currently not modifying weights further.
    """
    face = setup.face_meta
    M = tracks.shape[0]
    num_env, _overrides_start, lipsync_start, _num_main = _lipsync_offsets(setup)
    for k in range(len(face.lipsync_sides_track)):
        trk = int(face.lipsync_sides_track[k])  # a main-pose track index
        if not (0 <= trk < M):
            continue
        # Compute index of paired lipsync source track
        src = lipsync_start + (trk - num_env)
        if 0 <= src < M:
            tracks[trk] = _clamp(tracks[trk] + tracks[src], 0.0, 1.0)

# ---------------------------
# Track solver (Face) — full order parity
# ---------------------------

def solve_tracks_face(setup: FacialSetupAll, rig_info: RigSkeletonInfo, tracks_in: np.ndarray) -> dict:
    """Apply facial track processing to a copy of `tracks_in` (Face).
    Order (engine parity):
      muzzles → global limits (if lipSyncEnvelope>0) → influences → upper/lower →
      lipsync overrides → lipsync poses → influences → in-betweens → correctives.
    Returns: {"tracks": M, "inbetween_weights": SumInbtw, "corrective_weights": Pc}
    """
    face = setup.face_meta
    name_to_index = build_track_name_map(rig_info)

    tracks = np.array(tracks_in, dtype=np.float64, copy=True)
    M = tracks.shape[0]

    # Inject UI slider overrides if running inside Blender UI
    try:
        apply_global_slider_overrides_inplace(tracks, rig_info)  
    except Exception:
        pass

    # 1) Muzzles
    muzzleLimits = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    idx_mEyes  = _ti(name_to_index, "muzzleEyes")
    idx_mBrows = _ti(name_to_index, "muzzleBrows")
    idx_mDirs  = _ti(name_to_index, "muzzleEyeDirections")

    muzzles = [
        1.0 - _clamp(0.0, 0.0, muzzleLimits[0]),
        1.0 - _clamp(0.0, 0.0, muzzleLimits[1]),
        1.0 - _clamp(tracks[idx_mEyes]  if idx_mEyes  >= 0 else 0.0, 0.0, muzzleLimits[2]),
        1.0 - _clamp(tracks[idx_mBrows] if idx_mBrows >= 0 else 0.0, 0.0, muzzleLimits[3]),
        1.0 - _clamp(tracks[idx_mDirs]  if idx_mDirs  >= 0 else 0.0, 0.0, muzzleLimits[4]),
        1.0 - _clamp(0.0, 0.0, muzzleLimits[5]),
    ]

    for k in range(len(face.envelopes_track)):
        trk = int(face.envelopes_track[k])
        if 0 <= trk < M:
            env = int(face.envelopes_type[k])
            w = _clamp(tracks[trk], 0.0, 1.0)
            tracks[trk] = w * (muzzles[env] if 0 <= env < len(muzzles) else 1.0)

    # 2) Global limits (gated by lipSyncEnvelope)
    idx_jaw  = _ti(name_to_index, "jaliJaw")
    idx_lips = _ti(name_to_index, "jaliLips")
    idx_muzzleLips = _ti(name_to_index, "muzzleLips")
    idx_lipsync_env = _ti(name_to_index, "lipSyncEnvelope")

    jawMult  = _clamp(tracks[idx_jaw]  if idx_jaw  >= 0 else 0.0, 0.0, 2.0)
    lipsMult = _clamp(tracks[idx_lips] if idx_lips >= 0 else 0.0, 0.0, 2.0)
    muzzleLips = _clamp(tracks[idx_muzzleLips] if idx_muzzleLips >= 0 else 0.0, 0.0, 1.0)
    lipsyncEnvelope = _clamp(tracks[idx_lipsync_env] if idx_lipsync_env >= 0 else 0.0, 0.0, 1.0)

    envelopes = [jawMult, lipsMult, 1.0, 1.0, 1.0, 1.0]

    if lipsyncEnvelope != 0.0:
        for i in range(len(face.global_limits_track)):
            trk = int(face.global_limits_track[i])
            if not (0 <= trk < M):
                continue
            env_type = int(face.global_limits_type[i])
            Min = float(face.global_limits_min[i])
            Mid = float(face.global_limits_mid[i])
            Max = float(face.global_limits_max[i])
            slider = envelopes[env_type] if 0 <= env_type < len(envelopes) else 1.0
            if slider == 1.0:
                limit = Mid
            elif slider < 1.0:
                limit = Min + slider * (Mid - Min)
                lo, hi = (Min, Mid) if Min <= Mid else (Mid, Min)
                limit = _clamp(limit, lo, hi)
            else:
                limit = Mid + (slider - 1.0) * (Max - Mid)
                lo, hi = (Mid, Max) if Mid <= Max else (Max, Mid)
                limit = _clamp(limit, lo, hi)
            cur = float(tracks[trk])
            if cur > limit:
                tracks[trk] = _lerp(muzzleLips, cur, limit)

    # 3) Influenced poses (pass 1)
    idx = 0
    for i in range(len(face.influenced_poses_track)):
        trk = int(face.influenced_poses_track[i])
        num = int(face.influenced_poses_num[i])
        typ = int(face.influenced_poses_type[i])
        if not (0 <= trk < M):
            idx += num; continue
        w = tracks[trk]
        if w <= 1e-3:
            idx += num; continue
        inf_w = 0.0
        for j in range(num):
            k = int(face.influence_indices[idx + j])
            if 0 <= k < M:
                inf_w += tracks[k]
        idx += num
        if inf_w >= 1.0:
            w = 0.0
        elif typ == 0:
            m = 1.0 - inf_w
            if m < w:
                w = m
        elif typ == 1:
            w *= 1.0 - (inf_w * inf_w)
        elif typ == 2:
            m = 1.0 - inf_w
            w *= m * m
        tracks[trk] = w

    # 4) Upper/Lower envelopes
    idx_upper = _ti(name_to_index, "upperFace")
    idx_lower = _ti(name_to_index, "lowerFace")
    faceEnv = [1.0,
               _clamp(tracks[idx_upper] if idx_upper >= 0 else 0.0, 0.0, 2.0),
               _clamp(tracks[idx_lower] if idx_lower >= 0 else 0.0, 0.0, 2.0)]
    limits = [(0.0,1.0), (0.0,2.0), (0.0,2.0)]
    for i in range(len(face.upper_lower_track)):
        trk = int(face.upper_lower_track[i])
        part = int(face.upper_lower_part[i])
        if 0 <= trk < M:
            lo, hi = limits[part]
            tracks[trk] = _clamp(tracks[trk] * faceEnv[part], lo, hi)

    # 5) Lipsync overrides (multiply selected main tracks)
    apply_lipsync_overrides_inplace(setup, rig_info, tracks)

    # 6) Lipsync poses (add lipsync tracks into paired main tracks)
    apply_lipsync_poses_inplace(setup, rig_info, tracks)

    # 7) Influenced poses (pass 2)
    idx = 0
    for i in range(len(face.influenced_poses_track)):
        trk = int(face.influenced_poses_track[i])
        num = int(face.influenced_poses_num[i])
        typ = int(face.influenced_poses_type[i])
        if not (0 <= trk < M):
            idx += num; continue
        w = tracks[trk]
        if w <= 1e-3:
            idx += num; continue
        inf_w = 0.0
        for j in range(num):
            k = int(face.influence_indices[idx + j])
            if 0 <= k < M:
                inf_w += tracks[k]
        idx += num
        if inf_w >= 1.0:
            w = 0.0
        elif typ == 0:
            m = 1.0 - inf_w
            if m < w:
                w = m
        elif typ == 1:
            w *= 1.0 - (inf_w * inf_w)
        elif typ == 2:
            m = 1.0 - inf_w
            w *= m * m
        tracks[trk] = w

    # 8) In-between weights
    total_inbtw = int(np.sum(face.mainposes_num_inbtw.astype(np.int64)))
    inbetween_weights = np.zeros((total_inbtw,), dtype=np.float64)
    oi = 0; wi = 0; si = 0
    for p in range(len(face.mainposes_track)):
        trk = int(face.mainposes_track[p])
        num = int(face.mainposes_num_inbtw[p])
        w = tracks[trk] if (0 <= trk < M) else 0.0
        if num <= 0:
            continue
        inbetween_weights[oi:oi+num] = 0.0
        end = num - 1
        startW = float(face.mainposes_inbtw[wi]) if num > 0 else 0.0
        endW   = float(face.mainposes_inbtw[wi + end]) if num > 0 else 1.0
        if w < 1e-3:
            pass
        elif num == 1:
            inbetween_weights[oi] = w
        elif w <= startW:
            inbetween_weights[oi] = w * float(face.inbtw_scope_multipliers[si])
        elif w >= endW:
            inbetween_weights[oi + end] = 1.0
        else:
            realEnd = 1
            while realEnd < num and float(face.mainposes_inbtw[wi + realEnd]) <= w:
                realEnd += 1
            start = realEnd - 1
            realEndingWeight = (w - float(face.mainposes_inbtw[wi + start])) * float(face.inbtw_scope_multipliers[si + (realEnd-1)])
            realStartWeight = 1.0 - realEndingWeight
            inbetween_weights[oi + start] = realStartWeight
            if oi + realEnd < oi + num:
                inbetween_weights[oi + realEnd] = realEndingWeight
        oi += num; wi += num; si += max(0, num - 1)

    # 9) Correctives weights
    Pc = setup.face_corrective_bank.q.shape[0]
    correctives = np.ones((Pc,), dtype=np.float64)
    for gc in face.global_corrective_entries:
        ci = int(gc.get("Index", -1)); trk_raw = int(gc.get("Track", 0)); unk = int(gc.get("Unknown", 0))
        trk = ((trk_raw << 4) | unk) >> 4
        if 0 <= ci < Pc and 0 <= trk < M:
            w = tracks[trk]; correctives[ci] = 0.0 if w <= 0.0 else min(1.0, correctives[ci] * w)
    for gc in face.inbetween_corrective_entries:
        ci = int(gc.get("Index", -1)); trk_raw = int(gc.get("Track", 0)); unk = int(gc.get("Unknown", 0))
        trk = ((trk_raw << 4) | unk) >> 4
        if 0 <= ci < Pc and 0 <= trk < M:
            w = tracks[trk]; correctives[ci] = 0.0 if w <= 0.0 else min(1.0, correctives[ci] * w)
    idx = 0
    for entry in face.corrective_influenced_poses:
        trk = int(entry.get("Index", -1)); num = int(entry.get("NumInfluences", 0)); typ = int(entry.get("Type", 0))
        if not (0 <= trk < Pc):
            idx += num; continue
        w = correctives[trk]
        if w <= 1e-3:
            idx += num; continue
        inf_w = 0.0
        for j in range(num):
            k = int(setup.face_meta.corrective_influence_indices[idx + j])
            if 0 <= k < Pc:
                inf_w += correctives[k]
        idx += num
        influenceBySpeed = (typ & 1) != 0
        linearCorrection = (typ & 2) != 0
        if linearCorrection:
            c = 1.0 - inf_w
            w = w * c
            if influenceBySpeed:
                w *= c
        else:
            if inf_w >= 1.0:
                w = 0.0
            elif not influenceBySpeed:
                c = 1.0 - inf_w
                if c < w:
                    w = c
            else:
                w *= 1.0 - (inf_w * inf_w)
        correctives[trk] = max(0.0, min(1.0, w))

    return {
        "tracks": tracks.astype(np.float32, copy=False),
        "inbetween_weights": inbetween_weights.astype(np.float32, copy=False),
        "corrective_weights": correctives.astype(np.float32, copy=False),
    }

# ---------------------------
# Track solver (Eyes/Tongue) — simplified (no lipsync/global limits)
# ---------------------------

def _solve_tracks_part(meta: FacialSetupFaceMeta, Pc: int, tracks_in: np.ndarray, name_to_index: dict) -> dict:
    tracks = np.array(tracks_in, dtype=np.float64, copy=True)
    M = tracks.shape[0]
    # 1) Envelopes (muzzles table may still be referenced; keep neutral 1.0 when missing)
    muzzles = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    for k in range(len(meta.envelopes_track)):
        trk = int(meta.envelopes_track[k])
        if 0 <= trk < M:
            env = int(meta.envelopes_type[k])
            w = _clamp(tracks[trk], 0.0, 1.0)
            scale = muzzles[env] if 0 <= env < len(muzzles) else 1.0
            tracks[trk] = w * scale
    # 2) Influenced poses
    idx = 0
    for i in range(len(meta.influenced_poses_track)):
        trk = int(meta.influenced_poses_track[i]); num = int(meta.influenced_poses_num[i]); typ = int(meta.influenced_poses_type[i])
        if not (0 <= trk < M):
            idx += num; continue
        w = tracks[trk]
        if w <= 1e-3:
            idx += num; continue
        inf_w = 0.0
        for j in range(num):
            k = int(meta.influence_indices[idx + j])
            if 0 <= k < M:
                inf_w += tracks[k]
        idx += num
        if inf_w >= 1.0:
            w = 0.0
        elif typ == 0:
            m = 1.0 - inf_w
            if m < w:
                w = m
        elif typ == 1:
            w *= 1.0 - (inf_w * inf_w)
        elif typ == 2:
            m = 1.0 - inf_w
            w *= m * m
        tracks[trk] = w
    # 3) In-betweens
    total_inbtw = int(np.sum(meta.mainposes_num_inbtw.astype(np.int64)))
    inbetween_weights = np.zeros((total_inbtw,), dtype=np.float64)
    oi = 0; wi = 0; si = 0
    for p in range(len(meta.mainposes_track)):
        trk = int(meta.mainposes_track[p]); num = int(meta.mainposes_num_inbtw[p])
        w = tracks[trk] if (0 <= trk < M) else 0.0
        if num <= 0:
            continue
        inbetween_weights[oi:oi+num] = 0.0
        end = num - 1
        startW = float(meta.mainposes_inbtw[wi]) if num > 0 else 0.0
        endW   = float(meta.mainposes_inbtw[wi + end]) if num > 0 else 1.0
        if w < 1e-3:
            pass
        elif num == 1:
            inbetween_weights[oi] = w
        elif w <= startW:
            inbetween_weights[oi] = w * float(meta.inbtw_scope_multipliers[si])
        elif w >= endW:
            inbetween_weights[oi + end] = 1.0
        else:
            realEnd = 1
            while realEnd < num and float(meta.mainposes_inbtw[wi + realEnd]) <= w:
                realEnd += 1
            start = realEnd - 1
            realEndingWeight = (w - float(meta.mainposes_inbtw[wi + start])) * float(meta.inbtw_scope_multipliers[si + (realEnd-1)])
            realStartWeight = 1.0 - realEndingWeight
            inbetween_weights[oi + start] = realStartWeight
            if oi + realEnd < oi + num:
                inbetween_weights[oi + realEnd] = realEndingWeight
        oi += num; wi += num; si += max(0, num - 1)
    # 4) Correctives
    correctives = np.ones((Pc,), dtype=np.float64)
    for gc in meta.global_corrective_entries:
        ci = int(gc.get("Index", -1)); trk_raw = int(gc.get("Track", 0)); unk = int(gc.get("Unknown", 0))
        trk = ((trk_raw << 4) | unk) >> 4
        if 0 <= ci < Pc and 0 <= trk < M:
            w = tracks[trk]; correctives[ci] = 0.0 if w <= 0.0 else min(1.0, correctives[ci] * w)
    for gc in meta.inbetween_corrective_entries:
        ci = int(gc.get("Index", -1)); trk_raw = int(gc.get("Track", 0)); unk = int(gc.get("Unknown", 0))
        trk = ((trk_raw << 4) | unk) >> 4
        if 0 <= ci < Pc and 0 <= trk < M:
            w = tracks[trk]; correctives[ci] = 0.0 if w <= 0.0 else min(1.0, correctives[ci] * w)
    idx = 0
    for entry in meta.corrective_influenced_poses:
        trk = int(entry.get("Index", -1)); num = int(entry.get("NumInfluences", 0)); typ = int(entry.get("Type", 0))
        if not (0 <= trk < Pc):
            idx += num; continue
        w = correctives[trk]
        if w <= 1e-3:
            idx += num; continue
        inf_w = 0.0
        for j in range(num):
            k = int(meta.corrective_influence_indices[idx + j])
            if 0 <= k < Pc:
                inf_w += correctives[k]
        idx += num
        influenceBySpeed = (typ & 1) != 0
        linearCorrection = (typ & 2) != 0
        if linearCorrection:
            c = 1.0 - inf_w
            w = w * c
            if influenceBySpeed:
                w *= c
        else:
            if inf_w >= 1.0:
                w = 0.0
            elif not influenceBySpeed:
                c = 1.0 - inf_w
                if c < w:
                    w = c
            else:
                w *= 1.0 - (inf_w * inf_w)
        correctives[trk] = max(0.0, min(1.0, w))

    return {
        "tracks": tracks.astype(np.float32, copy=False),
        "inbetween_weights": inbetween_weights.astype(np.float32, copy=False),
        "corrective_weights": correctives.astype(np.float32, copy=False),
    }


def solve_tracks_eyes(setup: FacialSetupAll, rig_info: RigSkeletonInfo, tracks_in: np.ndarray) -> dict:
    if setup.eyes_meta is None:
        return {"tracks": np.asarray(tracks_in, dtype=np.float32), "inbetween_weights": np.zeros((0,), dtype=np.float32), "corrective_weights": np.zeros((0,), dtype=np.float32)}
    Pc = 0 if setup.eyes_corrective_bank is None else setup.eyes_corrective_bank.q.shape[0]
    return _solve_tracks_part(setup.eyes_meta, Pc, tracks_in, build_track_name_map(rig_info))


def solve_tracks_tongue(setup: FacialSetupAll, rig_info: RigSkeletonInfo, tracks_in: np.ndarray) -> dict:
    if setup.tongue_meta is None:
        return {"tracks": np.asarray(tracks_in, dtype=np.float32), "inbetween_weights": np.zeros((0,), dtype=np.float32), "corrective_weights": np.zeros((0,), dtype=np.float32)}
    Pc = 0 if setup.tongue_corrective_bank is None else setup.tongue_corrective_bank.q.shape[0]
    return _solve_tracks_part(setup.tongue_meta, Pc, tracks_in, build_track_name_map(rig_info))

# ---------------------------
# High-level helpers for applying multiple poses sparsely
# ---------------------------

Pose = Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]


def build_identity_masks_for_bank(bank: FaceBank, eps_rot: float = 1e-8, eps_t: float = 1e-8, eps_s: float = 1e-8) -> Dict[int, Sequence[TransformMaskEntry]]:
    masks: Dict[int, Sequence[TransformMaskEntry]] = {}
    P, N = bank.q.shape[0], bank.q.shape[1]
    for p in range(P):
        q = bank.q[p]; t = bank.t[p]; s = bank.s[p]
        rot_nonid = (np.linalg.norm(q[..., :3], axis=-1) > eps_rot) | (np.abs(q[..., 3] - 1.0) > eps_rot)
        trn_nonid = (np.linalg.norm(t, axis=-1) > eps_t)
        scl_nonid = (np.linalg.norm(s - 1.0, axis=-1) > eps_s)
        any_nonid = rot_nonid | trn_nonid | scl_nonid
        idxs = np.nonzero(any_nonid)[0]
        masks[p] = [TransformMaskEntry(int(i), 1.0) for i in idxs]
    return masks


def apply_pose_bank_additive_local(
    base_pose: Pose,
    pose_bank: Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]],  # (P,N,4), (P,N,3), (P,N,3), (P,M)|None
    weights: np.ndarray,  # [P]
    masks: Optional[dict[int, Sequence[TransformMaskEntry]]] = None,
    tracks_accumulate_additive: bool = True,
    lipsync_lipsync_mode: bool = False,
    use_scale: bool = True,
) -> Pose:
    """Apply multiple additive local poses from an additive bank to a base pose.
    - Each pose p is applied with weights[p] and optional bone mask from masks[p].
    - If tracks are present and tracks_accumulate_additive=True, they accumulate additively.
    - Set use_scale=False for Face/Eyes; True for Tongue/rare scale banks.
    """
    bq, bt, bs, btr = base_pose
    Pq, Pt, Ps, Ptr = pose_bank
    q, t, s = bq.copy(), bt.copy(), bs.copy()

    # tracks
    out_tracks: Optional[np.ndarray] = None
    if btr is not None:
        out_tracks = btr.copy()

    for p in range(len(weights)):
        w = float(weights[p])
        if abs(w) <= 1e-8:
            continue
        mask = None if masks is None else masks.get(p, None)
        if lipsync_lipsync_mode:
            q, t, s = additive_local_pose_only_lipsync(q, t, s, Pq[p], Pt[p], Ps[p], w, mask, use_scale)
        else:
            q, t, s = additive_local_pose_only(q, t, s, Pq[p], Pt[p], Ps[p], w, mask, use_scale)
        if out_tracks is not None and Ptr is not None and tracks_accumulate_additive:
            n = min(len(out_tracks), Ptr.shape[1])
            out_tracks[:n] += Ptr[p, :n] * w

    return quat_normalize(q), t, s, out_tracks


def blend_additive_local(
    base_pose: Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]],
    add_pose: Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]],
    weight: float,
    mask: Optional[Sequence[TransformMaskEntry]] = None,
    tracks_mode: TracksMode = "interpolate",
    lipsync_lipsync_mode: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """Blend base + additive in local space and blend track arrays according to `tracks_mode`.
    `pose` tuple layout: (q, t, s, tracks_or_None)
    """
    bq, bt, bs, btr = base_pose
    aq, at, as_, atr = add_pose

    if lipsync_lipsync_mode:
        q, t, s = additive_local_pose_only_lipsync(bq, bt, bs, aq, at, as_, weight, mask)
    else:
        q, t, s = additive_local_pose_only(bq, bt, bs, aq, at, as_, weight, mask)

    out_tracks = None
    if btr is not None and atr is not None:
        out_tracks = np.empty_like(btr)
        blend_tracks(out_tracks, btr, atr, tracks_mode, float(np.clip(weight, 0.0, 1.0)))
    elif btr is not None:
        out_tracks = btr.copy()

    return q, t, s, out_tracks

# ---------------------------
# WolvenKit facialsetup + rig JSON loaders (numpy)
# ---------------------------

import json
from pathlib import Path


def _q_identity(n: int) -> np.ndarray:
    q = np.zeros((n, 4), dtype=np.float32)
    q[:, 3] = 1.0
    return q


def _s_identity(n: int) -> np.ndarray:
    return np.ones((n, 3), dtype=np.float32)


def load_wkit_rig_skeleton(path: str | Path) -> RigSkeletonInfo:
    p = Path(path)
    data = json.loads(Path(p).read_text())
    root = data["Data"]["RootChunk"]

    # bone names
    bone_names = [e.get("$value", "") for e in root.get("boneNames", [])]
    parent_indices = np.asarray(root.get("boneParentIndexes", []), dtype=np.int16)
    track_names = [e.get("$value", "") for e in root.get("trackNames", [])]

    # reference LS transforms (bind/neutral)
    trs = root.get("boneTransforms", [])
    N = len(bone_names)
    q = np.zeros((N, 4), dtype=np.float32)
    t = np.zeros((N, 3), dtype=np.float32)
    s = np.ones((N, 3), dtype=np.float32)
    for i in range(min(N, len(trs))):
        tr = trs[i]
        r = tr.get("Rotation", {})
        q[i, 0] = float(r.get("i", 0.0))
        q[i, 1] = float(r.get("j", 0.0))
        q[i, 2] = float(r.get("k", 0.0))
        q[i, 3] = float(r.get("r", 1.0))
        tt = tr.get("Translation", {})
        t[i, 0] = float(tt.get("X", 0.0))
        t[i, 1] = float(tt.get("Y", 0.0))
        t[i, 2] = float(tt.get("Z", 0.0))
        sc = tr.get("Scale", {})
        s[i, 0] = float(sc.get("X", 1.0))
        s[i, 1] = float(sc.get("Y", 1.0))
        s[i, 2] = float(sc.get("Z", 1.0))
    q = quat_normalize(q)

    return RigSkeletonInfo(
        num_bones=len(bone_names),
        parent_indices=parent_indices,
        bone_names=bone_names,
        track_names=track_names,
        ls_q=q,
        ls_t=t,
        ls_s=s,
    )


def _build_dense_pose_bank(num_bones: int, poses_desc: list, transforms: list, scales: list | None) -> FaceBank:
    """Convert facialsetup pose blocks into dense [P,N] arrays suitable for additive blending.
    - Each entry in `poses_desc` is a dict with TransformIdx, NumTransforms, IsScale, etc.
    - `transforms` is a flat list; each item has Rotation{i,j,k,r}, Translation{X,Y,Z}, Bone (index).
    - If scales list is empty, we produce identity scale.
    """
    P = len(poses_desc)
    q = np.tile(_q_identity(num_bones), (P, 1, 1))
    t = np.zeros((P, num_bones, 3), dtype=np.float32)
    s = np.tile(_s_identity(num_bones), (P, 1, 1))

    have_scales = bool(scales)

    for p_idx, pose in enumerate(poses_desc):
        start = int(pose.get("TransformIdx", 0))
        count = int(pose.get("NumTransforms", 0))
        for rec in transforms[start:start+count]:
            b = int(rec.get("Bone", -1))
            if b < 0 or b >= num_bones:
                continue
            rot = rec.get("Rotation", {})
            trn = rec.get("Translation", {})
            q[p_idx, b, 0] = float(rot.get("i", 0.0))
            q[p_idx, b, 1] = float(rot.get("j", 0.0))
            q[p_idx, b, 2] = float(rot.get("k", 0.0))
            q[p_idx, b, 3] = float(rot.get("r", 1.0))
            t[p_idx, b, 0] = float(trn.get("X", 0.0))
            t[p_idx, b, 1] = float(trn.get("Y", 0.0))
            t[p_idx, b, 2] = float(trn.get("Z", 0.0))
        if have_scales:
            # Scales are rare in face; implement when encountered
            pass

    q = quat_normalize(q)
    return FaceBank(q=q, t=t, s=s)


def _np_int(arr, dtype=np.int16):
    return np.asarray(arr, dtype=dtype)


def load_wkit_facialsetup(path: str | Path, rig_info: RigSkeletonInfo) -> FacialSetupAll:
    p = Path(path)
    data = json.loads(Path(p).read_text())
    root = data["Data"]["RootChunk"]

    baked = root["bakedData"]["Data"]
    face_meta_src = baked["Face"]

    # --- Face meta tables ---
    env_map = face_meta_src.get("EnvelopesPerTrackMapping", [])
    envelopes_track = _np_int([e.get("Track", 0) for e in env_map])
    envelopes_lod = np.asarray([e.get("LevelOfDetail", 0) for e in env_map], dtype=np.int8)
    envelopes_type = np.asarray([e.get("Envelope", 0) for e in env_map], dtype=np.int8)

    gl_src = face_meta_src.get("GlobalLimits", [])
    global_limits_track = _np_int([e.get("Track", 0) for e in gl_src])
    global_limits_min = np.asarray([e.get("Min", 0.0) for e in gl_src], dtype=np.float32)
    global_limits_mid = np.asarray([e.get("Mid", 0.0) for e in gl_src], dtype=np.float32)
    global_limits_max = np.asarray([e.get("Max", 0.0) for e in gl_src], dtype=np.float32)
    global_limits_type = np.asarray([e.get("Type", 0) for e in gl_src], dtype=np.int8)

    infl_src = face_meta_src.get("InfluencedPoses", [])
    influenced_poses_track = _np_int([e.get("Track", 0) for e in infl_src])
    influenced_poses_num = np.asarray([e.get("NumInfluences", 0) for e in infl_src], dtype=np.int8)
    influenced_poses_type = np.asarray([e.get("Type", 0) for e in infl_src], dtype=np.int8)
    influence_indices = _np_int(face_meta_src.get("InfluenceIndices", []))

    ul_src = face_meta_src.get("UpperLowerFace", [])
    upper_lower_track = _np_int([e.get("Track", 0) for e in ul_src])
    upper_lower_part = np.asarray([e.get("Part", 0) for e in ul_src], dtype=np.int8)

    lips_src = face_meta_src.get("LipsyncPosesSides", [])
    lipsync_sides_track = _np_int([e.get("Track", 0) for e in lips_src])
    lipsync_sides_side = np.asarray([e.get("Side", 0) for e in lips_src], dtype=np.int8)

    mp_src = face_meta_src.get("AllMainPoses", [])
    mainposes_track = _np_int([e.get("Track", 0) for e in mp_src])
    mainposes_num_inbtw = _np_int([e.get("NumInbetweens", 0) for e in mp_src])
    mainposes_inbtw = _np_int(face_meta_src.get("AllMainPosesInbetweens", []))
    inbtw_scope_multipliers = np.asarray(face_meta_src.get("AllMainPosesInbetweenScopeMultipliers", []), dtype=np.float32)

    global_corrective_entries = face_meta_src.get("GlobalCorrectiveEntries", [])
    inbetween_corrective_entries = face_meta_src.get("InbetweenCorrectiveEntries", [])
    corrective_influenced_poses = face_meta_src.get("CorrectiveInfluencedPoses", [])
    corrective_influence_indices = _np_int(face_meta_src.get("CorrectiveInfluenceIndices", []))

    wrinkles = face_meta_src.get("Wrinkles", [])

    face_meta = FacialSetupFaceMeta(
        envelopes_track=envelopes_track,
        envelopes_lod=envelopes_lod,
        envelopes_type=envelopes_type,
        global_limits_track=global_limits_track,
        global_limits_min=global_limits_min,
        global_limits_mid=global_limits_mid,
        global_limits_max=global_limits_max,
        global_limits_type=global_limits_type,
        influenced_poses_track=influenced_poses_track,
        influenced_poses_num=influenced_poses_num,
        influenced_poses_type=influenced_poses_type,
        influence_indices=influence_indices,
        upper_lower_track=upper_lower_track,
        upper_lower_part=upper_lower_part,
        lipsync_sides_track=lipsync_sides_track,
        lipsync_sides_side=lipsync_sides_side,
        mainposes_track=mainposes_track,
        mainposes_num_inbtw=mainposes_num_inbtw,
        mainposes_inbtw=mainposes_inbtw,
        inbtw_scope_multipliers=inbtw_scope_multipliers,
        global_corrective_entries=global_corrective_entries,
        inbetween_corrective_entries=inbetween_corrective_entries,
        corrective_influenced_poses=corrective_influenced_poses,
        corrective_influence_indices=corrective_influence_indices,
        wrinkles=wrinkles,
    )

    # --- Optional Eyes/Tongue meta ---
    def _safe_meta(meta_src_dict: dict) -> FacialSetupFaceMeta:
        env_map = meta_src_dict.get("EnvelopesPerTrackMapping", [])
        envelopes_track = _np_int([e.get("Track", 0) for e in env_map])
        envelopes_lod = np.asarray([e.get("LevelOfDetail", 0) for e in env_map], dtype=np.int8)
        envelopes_type = np.asarray([e.get("Envelope", 0) for e in env_map], dtype=np.int8)
        gl_src = meta_src_dict.get("GlobalLimits", [])
        global_limits_track = _np_int([e.get("Track", 0) for e in gl_src])
        global_limits_min = np.asarray([e.get("Min", 0.0) for e in gl_src], dtype=np.float32)
        global_limits_mid = np.asarray([e.get("Mid", 0.0) for e in gl_src], dtype=np.float32)
        global_limits_max = np.asarray([e.get("Max", 0.0) for e in gl_src], dtype=np.float32)
        global_limits_type = np.asarray([e.get("Type", 0) for e in gl_src], dtype=np.int8)
        infl_src = meta_src_dict.get("InfluencedPoses", [])
        influenced_poses_track = _np_int([e.get("Track", 0) for e in infl_src])
        influenced_poses_num = np.asarray([e.get("NumInfluences", 0) for e in infl_src], dtype=np.int8)
        influenced_poses_type = np.asarray([e.get("Type", 0) for e in infl_src], dtype=np.int8)
        influence_indices = _np_int(meta_src_dict.get("InfluenceIndices", []))
        ul_src = meta_src_dict.get("UpperLowerFace", [])
        upper_lower_track = _np_int([e.get("Track", 0) for e in ul_src])
        upper_lower_part = np.asarray([e.get("Part", 0) for e in ul_src], dtype=np.int8)
        lips_src = meta_src_dict.get("LipsyncPosesSides", [])
        lipsync_sides_track = _np_int([e.get("Track", 0) for e in lips_src])
        lipsync_sides_side = np.asarray([e.get("Side", 0) for e in lips_src], dtype=np.int8)
        mp_src = meta_src_dict.get("AllMainPoses", [])
        mainposes_track = _np_int([e.get("Track", 0) for e in mp_src])
        mainposes_num_inbtw = _np_int([e.get("NumInbetweens", 0) for e in mp_src])
        mainposes_inbtw = _np_int(meta_src_dict.get("AllMainPosesInbetweens", []))
        inbtw_scope_multipliers = np.asarray(meta_src_dict.get("AllMainPosesInbetweenScopeMultipliers", []), dtype=np.float32)
        global_corrective_entries = meta_src_dict.get("GlobalCorrectiveEntries", [])
        inbetween_corrective_entries = meta_src_dict.get("InbetweenCorrectiveEntries", [])
        corrective_influenced_poses = meta_src_dict.get("CorrectiveInfluencedPoses", [])
        corrective_influence_indices = _np_int(meta_src_dict.get("CorrectiveInfluenceIndices", []))
        wrinkles = meta_src_dict.get("Wrinkles", [])
        return FacialSetupFaceMeta(
            envelopes_track,envelopes_lod,envelopes_type,
            global_limits_track,global_limits_min,global_limits_mid,global_limits_max,global_limits_type,
            influenced_poses_track,influenced_poses_num,influenced_poses_type,influence_indices,
            upper_lower_track,upper_lower_part,
            lipsync_sides_track,lipsync_sides_side,
            mainposes_track,mainposes_num_inbtw,mainposes_inbtw,inbtw_scope_multipliers,
            global_corrective_entries,inbetween_corrective_entries,corrective_influenced_poses,corrective_influence_indices,
            wrinkles)

    eyes_meta = None
    tongue_meta = None
    if "Eyes" in baked:
        try:
            eyes_meta = _safe_meta(baked["Eyes"])  
        except Exception:
            eyes_meta = None
    if "Tongue" in baked:
        try:
            tongue_meta = _safe_meta(baked["Tongue"])  
        except Exception:
            tongue_meta = None

    # --- TracksMapping (counts & offsets for lipsync) ---
    info = root.get("info", {})
    tm = info.get("tracksMapping", {})
    tracks_mapping = TracksMapping(
        num_envelopes=int(tm.get("numEnvelopes", 13)),
        num_main_poses=int(tm.get("numMainPoses", 0)),
        num_lipsync_overrides=int(tm.get("numLipsyncOverrides", 0)),
        num_wrinkles=int(tm.get("numWrinkles", 0)),
    )

    # --- General baked arrays ---
    lipsync_override_index_mapping = _np_int(baked.get("LipsyncOverridesIndexMapping", []))
    joint_regions = np.asarray(baked.get("JointRegions", []), dtype=np.int8)
    used_transform_indices = _np_int(root.get("usedTransformIndices", []))

    # --- Pose banks (face/eyes/tongue main & corrective) ---
    main_face = root["mainPosesData"]["Data"].get("Face", {})
    corr_face = root["correctivePosesData"]["Data"].get("Face", {})
    face_main_bank = _build_dense_pose_bank(rig_info.num_bones, main_face.get("Poses", []), main_face.get("Transforms", []), main_face.get("Scales", []))
    face_corrective_bank = _build_dense_pose_bank(rig_info.num_bones, corr_face.get("Poses", []), corr_face.get("Transforms", []), corr_face.get("Scales", []))

    eyes_main_bank = eyes_corrective_bank = None
    tongue_main_bank = tongue_corrective_bank = None
    if "Eyes" in root["mainPosesData"]["Data"]:
        m = root["mainPosesData"]["Data"]["Eyes"]
        eyes_main_bank = _build_dense_pose_bank(rig_info.num_bones, m.get("Poses", []), m.get("Transforms", []), m.get("Scales", []))
    if "Eyes" in root["correctivePosesData"]["Data"]:
        c = root["correctivePosesData"]["Data"]["Eyes"]
        eyes_corrective_bank = _build_dense_pose_bank(rig_info.num_bones, c.get("Poses", []), c.get("Transforms", []), c.get("Scales", []))
    if "Tongue" in root["mainPosesData"]["Data"]:
        m = root["mainPosesData"]["Data"]["Tongue"]
        tongue_main_bank = _build_dense_pose_bank(rig_info.num_bones, m.get("Poses", []), m.get("Transforms", []), m.get("Scales", []))
    if "Tongue" in root["correctivePosesData"]["Data"]:
        c = root["correctivePosesData"]["Data"]["Tongue"]
        tongue_corrective_bank = _build_dense_pose_bank(rig_info.num_bones, c.get("Poses", []), c.get("Transforms", []), c.get("Scales", []))
    return FacialSetupAll(
        lipsync_override_index_mapping=lipsync_override_index_mapping,
        joint_regions=joint_regions,
        used_transform_indices=used_transform_indices,
        tracks_mapping=tracks_mapping,
        face_meta=face_meta,
        face_main_bank=face_main_bank,
        face_corrective_bank=face_corrective_bank,
        eyes_meta=eyes_meta,
        eyes_main_bank=eyes_main_bank,
        eyes_corrective_bank=eyes_corrective_bank,
        tongue_meta=tongue_meta,
        tongue_main_bank=tongue_main_bank,
        tongue_corrective_bank=tongue_corrective_bank,
    )

# ---------------------------
# LS->MS and local deltas
# ---------------------------

def ls_to_ms(parents: np.ndarray, q_ls: np.ndarray, t_ls: np.ndarray, s_ls: np.ndarray):
    n = len(parents)
    q_ms = np.zeros_like(q_ls)
    t_ms = np.zeros_like(t_ls)
    s_ms = np.zeros_like(s_ls)
    for i in range(n):
        p = int(parents[i])
        if p < 0:
            q_ms[i] = q_ls[i]
            t_ms[i] = t_ls[i]
            s_ms[i] = s_ls[i]
        else:
            ax, ay, az, aw = q_ms[p]
            bx, by, bz, bw = q_ls[i]
            q_ms[i] = np.array([
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz,
            ], dtype=q_ls.dtype)
            s_ms[i] = s_ms[p] * s_ls[i]
            x, y, z, w = q_ms[p]
            vx, vy, vz = (s_ms[p] * t_ls[i])
            tx = 2 * (y * vz - z * vy)
            ty = 2 * (z * vx - x * vz)
            tz = 2 * (x * vy - y * vx)
            vpx = vx + w * tx + (y * tz - z * ty)
            vpy = vy + w * ty + (z * tx - x * tz)
            vpz = vz + w * tz + (x * ty - y * tx)
            t_ms[i] = t_ms[p] + np.array([vpx, vpy, vpz], dtype=t_ls.dtype)
    return quat_normalize(q_ms), t_ms, s_ms


def local_deltas(ref_q: np.ndarray, ref_t: np.ndarray, ref_s: np.ndarray,
                 q: np.ndarray, t: np.ndarray, s: np.ndarray):
    """Compute deltas such that: q = ref_q * dq, t = ref_t + dt, s = ref_s * ds."""
    rx, ry, rz, rw = np.moveaxis(ref_q, -1, 0)
    inv_ref = np.stack([-rx, -ry, -rz, rw], axis=-1)
    ax, ay, az, aw = np.moveaxis(inv_ref, -1, 0)
    bx, by, bz, bw = np.moveaxis(q, -1, 0)
    dq = np.stack([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], axis=-1)
    dq = quat_normalize(dq)
    dt = t - ref_t
    ds = s / np.where(ref_s == 0.0, 1.0, ref_s)
    return dq, dt, ds

# --- Blender stuff  -----------------------------------
try:
    import bpy
    import numpy as np
    from bpy.props import (
        StringProperty, BoolProperty, FloatProperty, IntProperty,
        EnumProperty, CollectionProperty, PointerProperty
    )
    from mathutils import Vector, Quaternion, Matrix
except Exception:
    # Allows importing this module outside Blender
    bpy = None


# ------------------------------------------------------------------------------
# Shared runtime state (loaded rig/setup, caches)
# ------------------------------------------------------------------------------
_STATE = {
    "rig": None,                 # RigSkeletonInfo
    "setup": None,               # FacialSetupAll
    "names_face_corr": [],       # list[str]
    "names_eyes_corr": [],
    "names_tongue_corr": [],
    "_face_main_masks": None,    # cached sparse masks for main bank
    "_eyes_main_masks": None,
    "_tongue_main_masks": None,
    "_face_corr_masks": None,
    "_eyes_corr_masks": None,
    "_tongue_corr_masks": None,
}


# ------------------------------------------------------------------------------
# Conversions & application helpers
# ------------------------------------------------------------------------------
def _np_vec3_to_bpy(v):
    return Vector((float(v[0]), float(v[1]), float(v[2])))

def _np_quat_to_bpy(q):
    # scalar-last (x,y,z,w)
    return Quaternion((float(q[3]), float(q[0]), float(q[1]), float(q[2])))

def _locrotscale_to_matrix(t, q, s):
    m = _np_quat_to_bpy(q).to_matrix().to_4x4()
    m.translation = _np_vec3_to_bpy(t)
    sm = Matrix.Diagonal((_np_vec3_to_bpy(s).x, _np_vec3_to_bpy(s).y, _np_vec3_to_bpy(s).z, 1.0))
    return m @ sm

def _apply_channels_to_active_armature(obj, q_ls, t_ls, s_ls):
    if obj is None or obj.type != 'ARMATURE':
        return
    pbones = obj.pose.bones
    n = min(len(pbones), len(q_ls))
    for i in range(n):
        pb = pbones[i]
        pb.location = _np_vec3_to_bpy(t_ls[i])
        # Use Quaternion mode for safety
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = _np_quat_to_bpy(q_ls[i])
        if s_ls is not None:
            pb.scale = _np_vec3_to_bpy(s_ls[i])

def _apply_ms_to_active_armature(obj, q_ms, t_ms, s_ms, input_is_world=False):
    if obj is None or obj.type != 'ARMATURE':
        return
    inv_world = obj.matrix_world.inverted() if input_is_world else Matrix.Identity(4)
    pbones = obj.pose.bones
    n = min(len(pbones), len(q_ms))
    for i in range(n):
        M = _locrotscale_to_matrix(t_ms[i], q_ms[i], s_ms[i])
        pbones[i].matrix = inv_world @ M

def _apply_channels_or_ms(obj, q, t, s, apply_mode, ms_is_world=False):
    if apply_mode == 'MATRIX':
        _apply_ms_to_active_armature(obj, q, t, s, input_is_world=ms_is_world)
    else:
        _apply_channels_to_active_armature(obj, q, t, s)

def _track_names_from_state_or_armature(context):
    names = []
    rig = _STATE.get("rig")
    if rig and getattr(rig, "track_names", None):
        names = list(rig.track_names)
    # Fallback: read from active armature custom prop
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        rd = obj.get("_rd_track_names")
        if isinstance(rd, (list, tuple)) and len(rd) > 0:
            names = list(rd)
    return names

def _build_track_name_map(track_names):
    return {name: idx for idx, name in enumerate(track_names)}

def _make_identity_pose(n_bones, with_scale=True):
    q = np.zeros((n_bones, 4), dtype=np.float32)
    q[:, 3] = 1.0
    t = np.zeros((n_bones, 3), dtype=np.float32)
    s = np.ones((n_bones, 3), dtype=np.float32) if with_scale else None
    return q, t, s
def _make_corrective_enum(bank, names):
    count = len(getattr(bank, "q", [])) if bank else 0
    if not names or len(names) != count:
        names = [f"corr_{i}" for i in range(count)]
    # identifier must be a string and we want it numeric for easy int(...)
    return [(str(i), names[i], "", i) for i in range(count)]

def _coerce_enum_to_index(val, bank, names):
    """
    Accepts either a numeric-string identifier ('0','1',...) or a name.
    Returns a valid index in [0..len(bank.q)-1], or 0 if not resolvable.
    """
    # numeric-string path
    try:
        idx = int(val)
        if 0 <= idx < len(getattr(bank, "q", [])):
            return idx
    except Exception:
        pass
    # name path
    if isinstance(val, str) and names:
        try:
            return names.index(val)
        except ValueError:
            pass
    return 0


def _build_tracks_from_armature(context):
    obj = context.active_object
    names = _track_names_from_state_or_armature(context)
    tracks = np.zeros((len(names),), dtype=np.float32)
    if not obj or obj.type != 'ARMATURE':
        return tracks, names
    # Read from custom props by name
    for i, nm in enumerate(names):
        v = obj.get(nm)
        try:
            tracks[i] = float(v) if v is not None else 0.0
        except Exception:
            tracks[i] = 0.0
    # Add wrinkle deltas from UI
    ws = obj.CP77_wrinkles if hasattr(obj, "CP77_wrinkles") else None
    if ws:
        name_to_idx = _build_track_name_map(names)
        for item in ws.items:
            idx = name_to_idx.get(item.track, None)
            if idx is not None:
                tracks[idx] += float(item.weight)
    return tracks, names


# ------------------------------------------------------------------------------
# Dynamic enums (correctives and tracks)
# ------------------------------------------------------------------------------
def _enum_face_correctives(self, context):
    setup = _STATE.get("setup")
    return _make_corrective_enum(getattr(setup, "face_corrective_bank", None),
                                 _STATE.get("names_face_corr", []))

def _enum_eyes_correctives(self, context):
    setup = _STATE.get("setup")
    return _make_corrective_enum(getattr(setup, "eyes_corrective_bank", None),
                                 _STATE.get("names_eyes_corr", []))

def _enum_tongue_correctives(self, context):
    setup = _STATE.get("setup")
    return _make_corrective_enum(getattr(setup, "tongue_corrective_bank", None),
                                 _STATE.get("names_tongue_corr", []))




def _enum_tracks(self, context):
    names = _track_names_from_state_or_armature(context)
    if not names:
        names = ["track_0"]
    return [(n, n, "", i) for i, n in enumerate(names)]


# ------------------------------------------------------------------------------
# Property groups
# ------------------------------------------------------------------------------
class CP77_FacialPreviewProps(bpy.types.PropertyGroup):
    rig_json: StringProperty(
        name="Rig (.rig.json)", subtype='FILE_PATH', default=""
    )
    facial_json: StringProperty(
        name="Facial Setup (.face.json)", subtype='FILE_PATH', default=""
    )

    # Global envelopes / gates
    jaw: FloatProperty(name="Jaw", default=1.0, min=0.0, max=2.0)
    lips: FloatProperty(name="Lips", default=1.0, min=0.0, max=2.0)
    upper: FloatProperty(name="Upper", default=1.0, min=0.0, max=2.0)
    lower: FloatProperty(name="Lower", default=1.0, min=0.0, max=2.0)
    muzzle: FloatProperty(name="Muzzle", default=1.0, min=0.0, max=2.0)
    lipsync_env: FloatProperty(name="Lipsync Env", default=1.0, min=0.0, max=2.0)

    lipsync: BoolProperty(name="lipsync Lipsync Mode", default=False)

    # Apply mode
    apply_mode: EnumProperty(
        name="Apply",
        items=[('CHANNELS', "Channels (LS)", ""), ('MATRIX', "Matrix (MS)", "")],
        default='CHANNELS'
    )
    ms_is_world: BoolProperty(name="MS is World Space", default=False)

    # Main poses + weights
    face_main_pose: IntProperty(name="Face Main Pose", default=0, min=0)
    face_main_weight: FloatProperty(name="Face Weight", default=1.0, min=0.0, max=3.0)

    eyes_main_pose: IntProperty(name="Eyes Main Pose", default=0, min=0)
    eyes_main_weight: FloatProperty(name="Eyes Weight", default=1.0, min=0.0, max=3.0)

    tongue_main_pose: IntProperty(name="Tongue Main Pose", default=0, min=0)
    tongue_main_weight: FloatProperty(name="Tongue Weight", default=1.0, min=0.0, max=3.0)

    # Corrective selectors
    
    face_corr: EnumProperty(name="Face Corrective", items=_enum_face_correctives)
    face_corr_weight: FloatProperty(name="Weight", default=1.0, min=0.0, max=3.0)

    eyes_corr: EnumProperty(name="Eyes Corrective", items=_enum_eyes_correctives)
    eyes_corr_weight: FloatProperty(name="Weight", default=1.0, min=0.0, max=3.0)

    tongue_corr: EnumProperty(name="Tongue Corrective", items=_enum_tongue_correctives)
    tongue_corr_weight: FloatProperty(name="Weight", default=1.0, min=0.0, max=3.0)


class CP77_WrinkleItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="")
    track: EnumProperty(name="Track", items=_enum_tracks)
    weight: FloatProperty(name="Weight", default=0.0, soft_min=-2.0, soft_max=2.0)


class CP77_WrinklesState(bpy.types.PropertyGroup):
    items: CollectionProperty(type=CP77_WrinkleItem)
    active_index: IntProperty(name="Active", default=0)


# ------------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------------
def _safe_list(x):
    """Return list(x) if x is a list/tuple, else an empty list. Avoids list(None)."""
    return list(x) if isinstance(x, (list, tuple)) else []

def _bank_has_data(bank):
    """True if FaceBank-like object has q/t with length > 0."""
    return bool(getattr(bank, "q", None)) and len(bank.q) > 0
# -----------------------------------------------------------------------------


class CP77_OT_LoadFacial(bpy.types.Operator):
    bl_idname = "cp77.load_facial"
    bl_label = "Load Rig & Facial"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Allow clicking any time; operator itself validates inputs
        return True

    def execute(self, context):
        props = context.scene.CP77_facial

        # 1) Resolve and validate file paths early
        rig_path = bpy.path.abspath(props.rig_json) if props.rig_json else ""
        face_path = bpy.path.abspath(props.facial_json) if props.facial_json else ""
        if not rig_path or not os.path.exists(rig_path):
            self.report({'ERROR'}, f"Rig path missing or not found: {rig_path!r}")
            return {'CANCELLED'}
        if not face_path or not os.path.exists(face_path):
            self.report({'ERROR'}, f"Facial path missing or not found: {face_path!r}")
            return {'CANCELLED'}

        # 2) Load JSONs with hard guards (catch loaders that return None)
        try:
            rig = load_wkit_rig_skeleton(rig_path)
            if rig is None:
                raise ValueError("load_wkit_rig_skeleton returned None")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load rig: {e}")
            return {'CANCELLED'}

        try:
            setup = load_wkit_facialsetup(face_path, rig)
            if setup is None:
                raise ValueError("load_wkit_facialsetup returned None")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load facial setup: {e}")
            return {'CANCELLED'}

        # 3) Commit to state
        _STATE["rig"] = rig
        _STATE["setup"] = setup

        # Pull corrective names from the source JSON (face/tongue only)
        try:
            import json
            with open(face_path, 'r', encoding='utf-8') as f:
                _raw = json.load(f)
            rc = _raw.get("Data", {}).get("RootChunk", {})
            def _cnames(arr):
                if isinstance(arr, list):
                    out = []
                    for it in arr:
                        if isinstance(it, dict):
                            v = it.get("$value")
                            if isinstance(v, str):
                                out.append(v)
                    return out
                return []
            _STATE["names_face_corr"]   = _cnames(rc.get("faceCorrectiveNames", []))
            _STATE["names_eyes_corr"]   = _cnames(rc.get("eyesCorrectiveNames", []))
            _STATE["names_tongue_corr"] = _cnames(rc.get("tongueCorrectiveNames", []))

        except Exception as e:
            self.report({'WARNING'}, f"Corrective names not found: {e}")

        # 5) Build mask caches only if banks actually exist
        try:
            if getattr(setup, "face_main_bank", None):
                _STATE["_face_main_masks"] = build_identity_masks_for_bank(setup.face_main_bank)
            if getattr(setup, "eyes_main_bank", None):
                _STATE["_eyes_main_masks"] = build_identity_masks_for_bank(setup.eyes_main_bank)
            if getattr(setup, "tongue_main_bank", None):
                _STATE["_tongue_main_masks"] = build_identity_masks_for_bank(setup.tongue_main_bank)

            if getattr(setup, "face_corrective_bank", None):
                _STATE["_face_corr_masks"] = build_identity_masks_for_bank(setup.face_corrective_bank)
            if getattr(setup, "eyes_corrective_bank", None):
                _STATE["_eyes_corr_masks"] = build_identity_masks_for_bank(setup.eyes_corrective_bank)
            if getattr(setup, "tongue_corrective_bank", None):
                _STATE["_tongue_corr_masks"] = build_identity_masks_for_bank(setup.tongue_corrective_bank)
        except Exception as e:
            self.report({'WARNING'}, f"Mask caching skipped: {e}")



        # 6) Populate wrinkles list from track names, but only if armature + property exist
        obj = context.active_object if getattr(context, "active_object", None) else None
        if obj and obj.type == 'ARMATURE' and hasattr(obj, "CP77_wrinkles"):
            try:
                tn    = getattr(rig, "track_names", None)
                names = _safe_list(tn)
                obj["_rd_track_names"] = names
                # Remember source rig file for utilities
                obj.data["source_rig_file"] = rig_path

                ws = obj.CP77_wrinkles
                # Make sure the collection exists before clearing/adding
                if hasattr(ws, "items"):
                    ws.items.clear()
                    for nm in names:
                        it = ws.items.add()
                        it.name   = nm
                        it.track  = nm
                        it.weight = 0.0
            except Exception as e:
                # Do not fail load if UI population hiccups
                self.report({'WARNING'}, f"Wrinkles list population skipped: {e}")

        self.report({'INFO'}, f"Loaded rig & facial. Bones={len(getattr(rig,'bone_names',[]))}, Tracks={len(_safe_list(getattr(rig,'track_names',None)))}")
        return {'FINISHED'}


class _ApplyBase:
    @classmethod
    def _poll_ready(cls, context):
        obj = context.active_object
        return obj and obj.type == 'ARMATURE' and _STATE.get("rig") and _STATE.get("setup")

    def _apply_pose(self, context, bank, pose_index, weight, cached_masks, use_scale=True):
        obj = context.active_object
        rig = _STATE["rig"]
        props = context.scene.CP77_facial
        n_bones = len(getattr(rig, "bone_names", []))
        q_base, t_base, s_base = _make_identity_pose(n_bones, with_scale=True)
        p = int(np.clip(pose_index, 0, len(bank.q) - 1))
        mask = cached_masks[p] if (cached_masks is not None and p < len(cached_masks)) else None

        if props.lipsync:
            q_out, t_out, s_out = additive_local_pose_only_lipsync(
                q_base, t_base, s_base,
                bank.q[p], bank.t[p], bank.s[p],
                float(weight), mask, use_scale=use_scale
            )
        else:
            q_out, t_out, s_out = additive_local_pose_only(
                q_base, t_base, s_base,
                bank.q[p], bank.t[p], bank.s[p],
                float(weight), mask, use_scale=use_scale
            )
        _apply_channels_or_ms(obj, q_out, t_out, s_out, props.apply_mode, props.ms_is_world)


class CP77_OT_ApplyMainPose(_ApplyBase, bpy.types.Operator):
    bl_idname = "cp77.apply_face_pose"
    bl_label = "Apply Face Main Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return cls._poll_ready(context)

    def execute(self, context):
        setup = _STATE["setup"]
        props = context.scene.CP77_facial
        self._apply_pose(context, setup.face_main_bank, props.face_main_pose,
                         props.face_main_weight, _STATE.get("_face_main_masks"), use_scale=True)
        return {'FINISHED'}


class CP77_OT_ApplyFaceCorrective(bpy.types.Operator):
    bl_idname = "cp77.apply_face_corrective"
    bl_label = "Apply Face Corrective"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _ApplyBase._poll_ready(context)

    def execute(self, context):
        setup = _STATE["setup"]
        props = context.scene.CP77_facial
        obj   = context.active_object
        rig   = _STATE["rig"]
        n     = len(rig.bone_names)
        q,t,s = _make_identity_pose(n, True)

        bank  = getattr(setup, "face_corrective_bank", None)
        if not bank or not getattr(bank, "q", None):
            self.report({'WARNING'}, "No face correctives available.")
            return {'CANCELLED'}

        names = _STATE.get("names_face_corr", [])
        idx   = _coerce_enum_to_index(props.face_corr, bank, names)

        masks = _STATE.get("_face_corr_masks") or []
        mask  = masks[idx] if idx < len(masks) else None

        q,t,s = additive_local_pose_only(
            q,t,s, bank.q[idx], bank.t[idx], bank.s[idx],
            float(props.face_corr_weight), mask, use_scale=True
        )
        _apply_channels_or_ms(obj, q,t,s, props.apply_mode, props.ms_is_world)
        return {'FINISHED'}



class CP77_OT_ApplyEyesPose(_ApplyBase, bpy.types.Operator):
    bl_idname = "cp77.apply_eyes_pose"
    bl_label = "Apply Eyes Main Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return cls._poll_ready(context)

    def execute(self, context):
        setup = _STATE["setup"]
        props = context.scene.CP77_facial
        self._apply_pose(context, setup.eyes_main_bank, props.eyes_main_pose,
                         props.eyes_main_weight, _STATE.get("_eyes_main_masks"), use_scale=True)
        return {'FINISHED'}


class CP77_OT_ApplyEyesCorrective(bpy.types.Operator):
    bl_idname = "cp77.apply_eyes_corrective"
    bl_label = "Apply Eyes Corrective"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _ApplyBase._poll_ready(context)

    def execute(self, context):
        setup = _STATE["setup"]
        props = context.scene.CP77_facial
        obj   = context.active_object
        rig   = _STATE["rig"]
        n     = len(rig.bone_names)
        q,t,s = _make_identity_pose(n, True)

        bank  = getattr(setup, "eyes_corrective_bank", None)
        if not bank or not getattr(bank, "q", None):
            self.report({'WARNING'}, "No eyes correctives available.")
            return {'CANCELLED'}

        names = _STATE.get("names_eyes_corr", [])
        idx   = _coerce_enum_to_index(props.eyes_corr, bank, names)

        masks = _STATE.get("_eyes_corr_masks") or []
        mask  = masks[idx] if idx < len(masks) else None

        q,t,s = additive_local_pose_only(
            q,t,s, bank.q[idx], bank.t[idx], bank.s[idx],
            float(props.eyes_corr_weight), mask, use_scale=True
        )
        _apply_channels_or_ms(obj, q,t,s, props.apply_mode, props.ms_is_world)
        return {'FINISHED'}


class CP77_OT_ApplyTonguePose(_ApplyBase, bpy.types.Operator):
    bl_idname = "cp77.apply_tongue_pose"
    bl_label = "Apply Tongue Main Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return cls._poll_ready(context)

    def execute(self, context):
        setup = _STATE["setup"]
        props = context.scene.CP77_facial
        self._apply_pose(context, setup.tongue_main_bank, props.tongue_main_pose,
                         props.tongue_main_weight, _STATE.get("_tongue_main_masks"), use_scale=True)
        return {'FINISHED'}


class CP77_OT_ApplyTongueCorrective(bpy.types.Operator):
    bl_idname = "cp77.apply_tongue_corrective"
    bl_label = "Apply Tongue Corrective"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _ApplyBase._poll_ready(context)

    def execute(self, context):
        setup = _STATE["setup"]
        props = context.scene.CP77_facial
        obj   = context.active_object
        rig   = _STATE["rig"]
        n     = len(rig.bone_names)
        q,t,s = _make_identity_pose(n, True)

        bank  = getattr(setup, "tongue_corrective_bank", None)
        if not bank or not getattr(bank, "q", None):
            self.report({'WARNING'}, "No tongue correctives available.")
            return {'CANCELLED'}

        names = _STATE.get("names_tongue_corr", [])
        idx   = _coerce_enum_to_index(props.tongue_corr, bank, names)

        masks = _STATE.get("_tongue_corr_masks") or []
        mask  = masks[idx] if idx < len(masks) else None

        q,t,s = additive_local_pose_only(
            q,t,s, bank.q[idx], bank.t[idx], bank.s[idx],
            float(props.tongue_corr_weight), mask, use_scale=True
        )
        _apply_channels_or_ms(obj, q,t,s, props.apply_mode, props.ms_is_world)
        return {'FINISHED'}



class CP77_OT_ResetNeutral(bpy.types.Operator):
    bl_idname = "cp77.reset_neutral"
    bl_label = "Reset To Neutral"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        bones = obj.pose.bones
        for pb in bones:
            pb.matrix_basis.identity()
            pb.rotation_mode = 'QUATERNION'
        return {'FINISHED'}


class CP77_OT_RebuildTracksFromJSON(bpy.types.Operator):
    bl_idname = "cp77.rebuild_tracks"
    bl_label = "Rebuild Track Names"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        props = context.scene.CP77_facial
        path = props.rig_json or obj.data.get("source_rig_file", "")
        if not path:
            self.report({'ERROR'}, "No rig path found.")
            return {'CANCELLED'}
        try:
            rig = load_wkit_rig_skeleton(path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read rig: {e}")
            return {'CANCELLED'}
        names = list(getattr(rig, "track_names", [])) or []
        obj["_rd_track_names"] = names
        # Refresh tracks list to match

        ws = obj.CP77_wrinkles
        ws.items.clear()
        for nm in names:
            it = ws.items.add()
            it.name = nm
            it.track = nm
            it.weight = 0.0
        self.report({'INFO'}, f"Tracks rebuilt: {len(names)}")
        return {'FINISHED'}


class CP77_OT_ArmaturePropsToUI(bpy.types.Operator):
    bl_idname = "cp77.arm_props_to_ui"
    bl_label = "Armature → UI Sliders"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        props = context.scene.CP77_facial
        for k in ("jaw","lips","upper","lower","muzzle","lipsync_env"):
            v = obj.get(k)
            if v is not None:
                setattr(props, k, float(v))
        self.report({'INFO'}, "Copied armature sliders to UI.")
        return {'FINISHED'}


class CP77_OT_UIToArmatureProps(bpy.types.Operator):
    bl_idname = "cp77.ui_to_arm_props"
    bl_label = "UI Sliders → Armature"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        props = context.scene.CP77_facial
        for k in ("jaw","lips","upper","lower","muzzle","lipsync_env"):
            obj[k] = float(getattr(props, k))
        self.report({'INFO'}, "Copied UI sliders to armature.")
        return {'FINISHED'}


class CP77_OT_WrinklesFromArm(bpy.types.Operator):
    bl_idname = "cp77.wrinkles_from_arm"
    bl_label = "Load Wrinkles From Armature"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        ws = obj.CP77_wrinkles
        names = _track_names_from_state_or_armature(context)
        for it in ws.items:
            if it.track in names:
                v = obj.get(it.track)
                it.weight = float(v) if v is not None else 0.0
        self.report({'INFO'}, "Wrinkles pulled from armature.")
        return {'FINISHED'}


class CP77_OT_WrinklesToArm(bpy.types.Operator):
    bl_idname = "cp77.wrinkles_to_arm"
    bl_label = "Apply Wrinkles To Armature"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        ws = obj.CP77_wrinkles
        for it in ws.items:
            obj[it.track] = float(it.weight)
        self.report({'INFO'}, "Wrinkles applied to armature custom properties.")
        return {'FINISHED'}


class CP77_OT_WrinklesPreview(bpy.types.Operator):
    bl_idname = "cp77.pose_preview"
    bl_label = "Apply Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _ApplyBase._poll_ready(context)

    def execute(self, context):
        obj = context.active_object
        props = context.scene.CP77_facial
        rig = _STATE["rig"]
        setup = _STATE["setup"]
        n_bones = len(rig.bone_names)

        q, t, s = _make_identity_pose(n_bones, True)

        # Apply main poses first (respect lipsync mode)
        def _apply_main(bank, pose_idx, w, masks):
            nonlocal q, t, s
            p = int(np.clip(pose_idx, 0, len(bank.q) - 1))
            mask = masks[p] if (masks is not None and p < len(masks)) else None
            if props.lipsync:
                q, t, s = additive_local_pose_only_lipsync(q, t, s, bank.q[p], bank.t[p], bank.s[p], float(w), mask, use_scale=True)
            else:
                q, t, s = additive_local_pose_only(q, t, s, bank.q[p], bank.t[p], bank.s[p], float(w), mask, use_scale=True)

        if getattr(setup, "face_main_bank", None):
            _apply_main(setup.face_main_bank, props.face_main_pose, props.face_main_weight, _STATE.get("_face_main_masks"))
        if getattr(setup, "eyes_main_bank", None):
            _apply_main(setup.eyes_main_bank, props.eyes_main_pose, props.eyes_main_weight, _STATE.get("_eyes_main_masks"))
        if getattr(setup, "tongue_main_bank", None):
            _apply_main(setup.tongue_main_bank, props.tongue_main_pose, props.tongue_main_weight, _STATE.get("_tongue_main_masks"))

        # Build tracks + solve face; apply face corrective weights
        tracks, track_names = _build_tracks_from_armature(context)
        solved = solve_tracks_face(setup, rig, tracks)
        face_cw = np.asarray(solved.get("corrective_weights", []), dtype=np.float32)
        if getattr(setup, "face_corr_bank", None) and face_cw.size:
            q, t, s = apply_pose_bank_additive_local(
                (q, t, s),
                setup.face_corr_bank,
                face_cw,
                masks=_STATE.get("_face_corr_masks"),
                tracks_accumulate_additive=False,
                lipsync_lipsync_mode=False,
                use_scale=True
            )

        _apply_channels_or_ms(obj, q, t, s, props.apply_mode, props.ms_is_world)
        self.report({'INFO'}, "Wrinkle preview solved/applied.")
        return {'FINISHED'}


class CP77_OT_ApplyAllFacial(bpy.types.Operator):
    bl_idname = "cp77.apply_all"
    bl_label = "Apply All (Solve)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _ApplyBase._poll_ready(context)

    def execute(self, context):
        obj = context.active_object
        props = context.scene.CP77_facial
        rig = _STATE["rig"]
        setup = _STATE["setup"]
        n_bones = len(rig.bone_names)

        q, t, s = _make_identity_pose(n_bones, True)

        # Apply main poses (face/eyes/tongue)
        def _apply_main(bank, pose_idx, w, masks, use_scale=True):
            nonlocal q, t, s
            p = int(np.clip(pose_idx, 0, len(bank.q) - 1))
            mask = masks[p] if (masks is not None and p < len(masks)) else None
            if props.lipsync:
                q, t, s = additive_local_pose_only_lipsync(q, t, s, bank.q[p], bank.t[p], bank.s[p], float(w), mask, use_scale=use_scale)
            else:
                q, t, s = additive_local_pose_only(q, t, s, bank.q[p], bank.t[p], bank.s[p], float(w), mask, use_scale=use_scale)

        if getattr(setup, "face_main_bank", None):
            _apply_main(setup.face_main_bank, props.face_main_pose, props.face_main_weight, _STATE.get("_face_main_masks"), True)
        if getattr(setup, "eyes_main_bank", None):
            _apply_main(setup.eyes_main_bank, props.eyes_main_pose, props.eyes_main_weight, _STATE.get("_eyes_main_masks"), True)
        if getattr(setup, "tongue_main_bank", None):
            _apply_main(setup.tongue_main_bank, props.tongue_main_pose, props.tongue_main_weight, _STATE.get("_tongue_main_masks"), True)

        # Face from solver
        if getattr(setup, "face_corrective_bank", None) and face_cw.size:
            q, t, s = apply_pose_bank_additive_local(
                (q, t, s),
                setup.face_corrective_bank,
                face_cw,
                masks=_STATE.get("_face_corr_masks"),
                tracks_accumulate_additive=False,
                lipsync_lipsync_mode=False,
                use_scale=True
            )

        # Eyes (if any in data; Songbird has 0)
        if getattr(setup, "eyes_corrective_bank", None) and eyes_cw.size:
            q, t, s = apply_pose_bank_additive_local(
                (q, t, s),
                setup.eyes_corrective_bank,
                eyes_cw,
                masks=_STATE.get("_eyes_corr_masks"),
                tracks_accumulate_additive=False,
                lipsync_lipsync_mode=False,
                use_scale=True
            )

        # Tongue (Songbird has 4)
        if getattr(setup, "tongue_corrective_bank", None) and tongue_cw.size:
            q, t, s = apply_pose_bank_additive_local(
                (q, t, s),
                setup.tongue_corrective_bank,
                tongue_cw,
                masks=_STATE.get("_tongue_corr_masks"),
                tracks_accumulate_additive=False,
                lipsync_lipsync_mode=False,
                use_scale=True
            )


        # Solve tracks from armature (globals + wrinkles already captured)
        tracks, track_names = _build_tracks_from_armature(context)
        solved_face = solve_tracks_face(setup, rig, tracks)
        face_cw = np.asarray(solved_face.get("corrective_weights", []), dtype=np.float32)

        # Apply face corrective weights from solver
        if getattr(setup, "face_corr_bank", None) and face_cw.size:
            q, t, s = apply_pose_bank_additive_local(
                (q, t, s),
                setup.face_corr_bank,
                face_cw,
                masks=_STATE.get("_face_corr_masks"),
                tracks_accumulate_additive=False,
                lipsync_lipsync_mode=False,
                use_scale=True
            )

        try:
            solved_eyes = solve_tracks_eyes(setup, rig, tracks)
            eyes_cw = np.asarray(solved_eyes.get("corrective_weights", []), dtype=np.float32)
            if getattr(setup, "eyes_corr_bank", None) and eyes_cw.size:
                q, t, s = apply_pose_bank_additive_local(
                    (q, t, s),
                    setup.eyes_corr_bank,
                    eyes_cw,
                    masks=_STATE.get("_eyes_corr_masks"),
                    tracks_accumulate_additive=False,
                    lipsync_lipsync_mode=False,
                    use_scale=True
                )
        except Exception:
            pass

        try:
            solved_tongue = solve_tracks_tongue(setup, rig, tracks)
            tongue_cw = np.asarray(solved_tongue.get("corrective_weights", []), dtype=np.float32)
            if getattr(setup, "tongue_corr_bank", None) and tongue_cw.size:
                q, t, s = apply_pose_bank_additive_local(
                    (q, t, s),
                    setup.tongue_corr_bank,
                    tongue_cw,
                    masks=_STATE.get("_tongue_corr_masks"),
                    tracks_accumulate_additive=False,
                    lipsync_lipsync_mode=False,
                    use_scale=True
                )
        except Exception:
            pass

        _apply_channels_or_ms(obj, q, t, s, props.apply_mode, props.ms_is_world)
        self.report({'INFO'}, "Applied all (poses + solver correctives).")
        return {'FINISHED'}


# ------------------------------------------------------------------------------
# UI
# ------------------------------------------------------------------------------
class CP77_UL_Wrinkles(bpy.types.UIList):
    bl_idname = "CP77_UL_Wrinkles"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        wr = item
        row = layout.row(align=True)
        row.prop(wr, "name", text="", emboss=False)
        row.prop(wr, "track", text="")
        row.prop(wr, "weight", text="")

class CP77_PT_FacialPreview(bpy.types.Panel):
    bl_idname = "CP77_PT_FacialPreview"
    bl_label = "Facial Setup"
    bl_category = "CP77 Modding"
    bl_parent_id = "CP77_PT_animspanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.CP77_facial

        col = layout.column(align=True)
        col.prop(props, "rig_json")
        col.prop(props, "facial_json")
        col.operator("cp77.load_facial", icon='FILE_REFRESH')

        col.separator()
        grid = col.grid_flow(columns=2, even_columns=True, align=True)
        box = grid.box()
        box.label(text="Eyes")
        box.prop(props, "eyes_main_pose", text="Main Pose")
        box.prop(props, "eyes_main_weight", text="Weight")
        row = box.row(align=True)
        row.operator("cp77.apply_eyes_pose", text="Apply Pose", icon='PLAY')
        row = box.row(align=True)
        row.prop(props, "eyes_corr", text="Corrective")
        row.prop(props, "eyes_corr_weight", text="W")
        box.operator("cp77.apply_eyes_corrective", text="Apply Corrective", icon='MOD_ARMATURE')

        box = grid.box()
        box.label(text="Tongue")
        box.prop(props, "tongue_main_pose", text="Main Pose")
        box.prop(props, "tongue_main_weight", text="Weight")
        row = box.row(align=True)
        row.operator("cp77.apply_tongue_pose", text="Apply Pose", icon='PLAY')
        row = box.row(align=True)
        row.prop(props, "tongue_corr", text="Corrective")
        row.prop(props, "tongue_corr_weight", text="W")
        box.operator("cp77.apply_tongue_corrective", text="Apply Corrective", icon='MOD_ARMATURE')
        box = col.box()
        box.label(text="Face")
        box.prop(props, "face_main_pose", text="Main Pose")
        box.prop(props, "face_main_weight", text="Weight")
        row = box.row(align=True)
        row.operator("cp77.apply_face_pose", text="Apply Pose", icon='PLAY')
        row = box.row(align=True)
        row.prop(props, "face_corr", text="Corrective")
        row.prop(props, "face_corr_weight", text="W")
        box.operator("cp77.apply_face_corrective", text="Apply Corrective", icon='MOD_ARMATURE')
        col.separator()
        col.prop(props, "apply_mode", text="Apply Mode")
        if props.apply_mode == 'MATRIX':
            col.prop(props, "ms_is_world", text="Treat MS as World Space")
        col.prop(props, "lipsync", text=" Lipsync Mode")


        col.separator()
        box = col.box()
        box.label(text="Wrinkles")

        obj = context.active_object
        if obj and obj.type == 'ARMATURE' and hasattr(obj, "CP77_wrinkles"):
            row = box.row()
            # dataptr = obj.CP77_wrinkles (PropertyGroup)
            # propname = "items" (the CollectionProperty inside)
            # active_dataptr = obj.CP77_wrinkles
            # active_propname = "active_index"
            row.template_list(
                "CP77_UL_Wrinkles", "",
                obj.CP77_wrinkles, "items",
                obj.CP77_wrinkles, "active_index",
                rows=6
            )
            row = box.row(align=True)
            row.operator("cp77.wrinkles_from_arm", icon='IMPORT')
            row.operator("cp77.wrinkles_to_arm", icon='EXPORT')
            
        else:
            box.label(text="Select an Armature to edit wrinkles.", icon='INFO')

        col.separator()
        box = col.box()
        box.label(text="Track Utilities")
        row = box.row(align=True)
        row.operator("cp77.rebuild_tracks", icon='SORTALPHA')
        row.operator("cp77.reset_neutral", icon='LOOP_BACK')


# ------------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------------
_CLASSES = (
    CP77_FacialPreviewProps,
    CP77_WrinkleItem,
    CP77_WrinklesState,
    CP77_OT_LoadFacial,
    CP77_OT_ApplyMainPose,
    CP77_OT_ApplyFaceCorrective,
    CP77_OT_ApplyEyesPose,
    CP77_OT_ApplyEyesCorrective,
    CP77_OT_ApplyTonguePose,
    CP77_OT_ApplyTongueCorrective,
    CP77_OT_ResetNeutral,
    CP77_OT_RebuildTracksFromJSON,
    CP77_OT_ArmaturePropsToUI,
    CP77_OT_UIToArmatureProps,
    CP77_OT_WrinklesFromArm,
    CP77_OT_WrinklesToArm,
    CP77_OT_WrinklesPreview,
    CP77_UL_Wrinkles,
    CP77_PT_FacialPreview,
)

def register():
    if bpy is None:
        return
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.CP77_facial = PointerProperty(type=CP77_FacialPreviewProps)
    bpy.types.Object.CP77_wrinkles = PointerProperty(type=CP77_WrinklesState)

def unregister():
    if bpy is None:
        return
    del bpy.types.Object.CP77_wrinkles
    del bpy.types.Scene.CP77_facial
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
# --- end Blender Integration --------------------------------------------------


