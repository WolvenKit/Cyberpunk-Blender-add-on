"""
facial_setup_loader.py
======================
Parse WolvenKit-exported CP77 .facialsetup and animRig JSON files into
numpy arrays ready for the vectorized Sermo compute pipeline.

Usage
-----
    from facial_setup_loader import load_facial_setup, load_rig

    rig   = load_rig("skeleton_rig.json")
    setup = load_facial_setup("facialsetup.json", rig)

    # setup.face / setup.eyes / setup.tongue  -> SermoPartData
    # rig.bone_names, rig.track_names, rig.ref_quats, rig.ref_trans ...
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


# Constants (mirror sermo.h)

NUM_ENVELOPE_TRACKS    = 13
NUM_ENVELOPE_WEIGHTS   = 6   # face, upper, lower, lipsync, JALI_jaw, JALI_lips
WEIGHT_THRESHOLD       = 0.001
FACIAL_VERSION         = 8

# Envelope type indices (bakedData Envelope field)
ENV_FACE        = 0
ENV_LIPSYNC     = 1
ENV_JALI_JAW    = 2  # unused label — maps to JALI jaw slider
ENV_UPPER_FACE  = 3
ENV_LOWER_FACE  = 4  # actually "lowerFace" envelope
ENV_MUZZLE      = 5  # muzzle multiplier group

# Influence type (InfluencedPoses.Type)
INFL_LINEAR      = 0
INFL_EXPONENTIAL = 1
INFL_ORGANIC     = 2

# Lipsync pose side (LipsyncPosesSides.Side)
SIDE_MID   = 0
SIDE_LEFT  = 1
SIDE_RIGHT = 2

# Upper/lower face part (UpperLowerFace.Part)
PART_UPPER  = 0
PART_LOWER  = 1
PART_LIPSYNC = 2   # lip/jaw region — gets lipsync zone envelope

# Corrective influence type flags
CORR_INFL_BY_SPEED        = 0
CORR_INFL_LINEAR          = 1
CORR_INFL_LINEAR_CORRECTION = 2
CORR_INFL_ORGANIC         = 3


# Rig data

@dataclass
class RigData:
    """Parsed animRig — bone names, hierarchy, reference pose, tracks."""

    # Bone table
    bone_names:   np.ndarray   # [num_bones]  object (str)
    bone_parents: np.ndarray   # [num_bones]  int16  (-1 = root)
    num_bones:    int

    # Reference pose — bone-space (boneTransforms / LS rest pose)
    ref_quats:    np.ndarray   # [num_bones, 4] float32  xyzw
    ref_trans:    np.ndarray   # [num_bones, 3] float32  xyz
    ref_scales:   np.ndarray   # [num_bones, 3] float32  xyz

    # Track table (facial float tracks come from here)
    track_names:  np.ndarray   # [num_tracks]  object (str)
    num_tracks:   int

    # LOD bone split points (facial LOD thresholds)
    lod_start_indices: np.ndarray  # [num_lod_groups] int32

    # Convenience: name → index maps
    _bone_index_map:  Dict[str, int] = field(default_factory=dict, repr=False)
    _track_index_map: Dict[str, int] = field(default_factory=dict, repr=False)

    def bone_index(self, name: str) -> int:
        return self._bone_index_map[name]

    def track_index(self, name: str) -> int:
        return self._track_index_map[name]


# Per-part pose data

@dataclass
class PoseArrays:
    """
    CSR-compressed pose transform arrays for one part (face/eyes/tongue).

    Pose i uses transforms in the range [row_ptr[i], row_ptr[i+1]).
    pose_bones[k]  → bone index in the rig
    pose_quats[k]  → quaternion delta (xyzw, float32)
    pose_trans[k]  → translation delta (xyz,  float32)

    num_poses == number of inbetween-expanded poses (e.g. 133 for face main)
    """
    num_poses:   int
    row_ptr:     np.ndarray   # [num_poses + 1]  int32
    pose_bones:  np.ndarray   # [total_transforms] int16
    pose_quats:  np.ndarray   # [total_transforms, 4] float32 xyzw
    pose_trans:  np.ndarray   # [total_transforms, 3] float32


# Per-part sermo lookup tables

@dataclass
class SermoPartData:
    """
    All sermo pipeline lookup tables for one part (face / eyes / tongue),
    stored as numpy arrays for vectorized evaluation.

    Array sizes correspond to the actual rig — Songbird face part has ~121
    main poses, 133 inbetween poses, 255 correctives, etc.
    """

    part_name: str   # 'face' | 'eyes' | 'tongue'

    #  Stage 3: Envelope → track weight gates 
    # Each entry maps a track to the envelope that gates it.
    # env_lods: tracks with lod > current LOD are skipped.
    env_num:    int
    env_tracks: np.ndarray   # [env_num] int16
    env_lods:   np.ndarray   # [env_num] uint8   LOD threshold (skip if lod > this)
    env_types:  np.ndarray   # [env_num] uint8   ENV_* constant

    #  Stage 4: Global limits (JALI jaw / lips sliders) 
    limit_num:      int
    limit_tracks:   np.ndarray   # [limit_num] int16
    limit_envelope: np.ndarray   # [limit_num] uint8   which envelope controls
    limit_min:      np.ndarray   # [limit_num] float32
    limit_mid:      np.ndarray   # [limit_num] float32
    limit_max:      np.ndarray   # [limit_num] float32

    #  Stage 5/9: Influence suppression (CSR) 
    # For track infl_tracks[i], sum influencer weights from
    # infl_indices[infl_row_ptr[i] : infl_row_ptr[i+1]].
    infl_num:      int
    infl_tracks:   np.ndarray   # [infl_num] int16
    infl_types:    np.ndarray   # [infl_num] uint8   INFL_* constant
    infl_row_ptr:  np.ndarray   # [infl_num + 1] int32
    infl_indices:  np.ndarray   # [total_infl_indices] int16

    #  Stage 6: Upper/lower face envelopes 
    ulf_num:    int
    ulf_tracks: np.ndarray   # [ulf_num] int16
    ulf_parts:  np.ndarray   # [ulf_num] uint8   PART_* constant

    #  Stage 7/8: Lipsync pose sides 
    lps_num:    int
    lps_tracks: np.ndarray   # [lps_num] int16
    lps_sides:  np.ndarray   # [lps_num] uint8   SIDE_* constant

    #  Stage 10: Main pose inbetween expansion 
    # num_main_poses: logical pose count (121 face main)
    # num_ib_poses:   inbetween-expanded count (133 face, flat)
    # num_scope_mults: gaps across all multi-inbetween poses (12 face)
    # For main pose m:
    #   inbetween pose indices: [ib_row_ptr[m], ib_row_ptr[m+1])
    #   thresholds:             ib_thresholds[ib_row_ptr[m]:ib_row_ptr[m+1]]
    #   scope multipliers:      ib_scope_mults[sm_row_ptr[m]:sm_row_ptr[m+1]]
    #                           len = num_inbetweens[m] - 1
    num_main_poses:   int
    num_ib_poses:     int
    main_tracks:      np.ndarray   # [num_main_poses] int16
    ib_row_ptr:       np.ndarray   # [num_main_poses + 1] int32
    ib_thresholds:    np.ndarray   # [num_ib_poses] float32
    sm_row_ptr:       np.ndarray   # [num_main_poses + 1] int32  into ib_scope_mults
    ib_scope_mults:   np.ndarray   # [num_scope_mults] float32

    #  Stage 12: Global corrective entries (CSR) 
    # corrective pose c is active when ALL tracks in
    # gcorr_tracks[gcorr_row_ptr[c] : gcorr_row_ptr[c+1]] have non-zero weight.
    num_correctives:   int
    gcorr_row_ptr:     np.ndarray   # [num_correctives + 1] int32
    gcorr_tracks:      np.ndarray   # [total_gcorr] int16
    gcorr_flags:       np.ndarray   # [total_gcorr] uint8   Unknown field from JSON

    #  Stage 13: Inbetween corrective entries (CSR) 
    # Indexed by inbetween-expanded pose index (0..num_ib_poses-1).
    icorr_row_ptr:  np.ndarray   # [num_ib_poses + 1] int32
    icorr_tracks:   np.ndarray   # [total_icorr] int16
    icorr_flags:    np.ndarray   # [total_icorr] uint8   Unknown field

    #  Stage 14: Corrective influence suppression (CSR) 
    # corr_infl_indices[i] = which corrective pose to suppress
    num_corr_infl:         int
    corr_infl_pose_idx:    np.ndarray   # [num_corr_infl] int32   corrective to suppress
    corr_infl_types:       np.ndarray   # [num_corr_infl] uint8   CORR_INFL_* flag
    corr_infl_row_ptr:     np.ndarray   # [num_corr_infl + 1] int32
    corr_infl_influencers: np.ndarray   # [total_corr_infl_idx] int32  influencer corrective indices

    #  Stage 15/16: Pose transforms (CSR, inbetween-expanded) 
    main_poses:       PoseArrays   # num_poses  num_ib_poses
    corrective_poses: PoseArrays   # num_poses  num_correctives

    #  Stage 17: Wrinkle mapping 
    # wrinkle_track_offset[i]: the main pose TRACK driving wrinkle i.
    # The output wrinkle track index = wrinkle_start_track + i.
    wrinkle_count:        int
    wrinkle_source_tracks: np.ndarray   # [wrinkle_count] int16  main pose track ids
    wrinkle_start_track:   int          # first wrinkle track index in rig


# Top-level facial setup

@dataclass
class FacialSetupData:
    """Complete parsed facial setup, ready for sermo_compute."""

    version:       int
    face:          SermoPartData
    eyes:          SermoPartData
    tongue:        SermoPartData

    # Global data
    used_bone_indices:          np.ndarray   # [N] int16  subset of rig bones used
    lipsync_override_idx_map:   np.ndarray   # [86] int16 lipsync → main pose track
    joint_regions:              np.ndarray   # [num_used_bones] uint8

    # Track layout constants (from tracksMapping)
    num_envelope_tracks:   int   # always 13
    num_lipsync_overrides: int
    num_main_poses:        int   # face main pose count
    num_wrinkle_tracks:    int


# Internal helpers

def _cname(obj) -> str:
    """Extract string from WolvenKit CName object or plain str."""
    if isinstance(obj, dict):
        return obj.get("$value", "")
    return str(obj)


def _quat_wk_to_xyzw(rot: dict) -> np.ndarray:
    """Convert WolvenKit Quaternion {i,j,k,r} → numpy [x,y,z,w] float32."""
    return np.array([rot["i"], rot["j"], rot["k"], rot["r"]], dtype=np.float32)


def _vec3_wk(v: dict, keys=("X", "Y", "Z")) -> np.ndarray:
    return np.array([v[keys[0]], v[keys[1]], v[keys[2]]], dtype=np.float32)


def _vec4_wk(v: dict) -> np.ndarray:
    return np.array([v["X"], v["Y"], v["Z"]], dtype=np.float32)


def _build_csr(num_rows: int, row_col_pairs) -> tuple[np.ndarray, np.ndarray]:
    """
    Build CSR row_ptr and flat data arrays from (row, value) pairs.
    Pairs must be sorted by row.
    Returns (row_ptr [num_rows+1], values [total]).
    """
    row_ptr = np.zeros(num_rows + 1, dtype=np.int32)
    values  = []
    for row, val in row_col_pairs:
        row_ptr[row + 1] += 1
        values.append(val)
    np.cumsum(row_ptr, out=row_ptr)
    return row_ptr, values


def _build_csr_multi(num_rows: int, entries, row_key, val_keys):
    """
    Build CSR from a list of dicts.
    row_key: dict key for the row index
    val_keys: list of dict keys to extract as value tuple
    Returns (row_ptr, list_of_value_arrays) — one value array per val_key.
    """
    per_row: list[list] = [[] for _ in range(num_rows)]
    for e in entries:
        r = e[row_key]
        per_row[r].append(tuple(e[k] for k in val_keys))

    row_ptr = np.zeros(num_rows + 1, dtype=np.int32)
    for r, lst in enumerate(per_row):
        row_ptr[r + 1] = row_ptr[r] + len(lst)

    total = row_ptr[-1]
    val_arrays = [np.empty(total, dtype=np.int32) for _ in val_keys]
    for r, lst in enumerate(per_row):
        start = row_ptr[r]
        for i_entry, tup in enumerate(lst):
            for i_key, v in enumerate(tup):
                val_arrays[i_key][start + i_entry] = v

    return row_ptr, val_arrays


# Pose-transform extraction

def _parse_pose_arrays(wk_part: dict) -> PoseArrays:
    """
    Convert mainPosesData or correctivePosesData for one part (Face/Tongue/Eyes)
    into a CSR PoseArrays.  Each pose uses LOD0 transforms (NumTransforms).
    """
    poses_raw      = wk_part["Poses"]
    transforms_raw = wk_part["Transforms"]
    num_poses      = len(poses_raw)

    row_ptr = np.empty(num_poses + 1, dtype=np.int32)
    row_ptr[0] = 0
    for i, p in enumerate(poses_raw):
        row_ptr[i + 1] = row_ptr[i] + p["NumTransforms"]
    total = int(row_ptr[-1])

    pose_bones = np.empty(total, dtype=np.int16)
    pose_quats = np.empty((total, 4), dtype=np.float32)
    pose_trans = np.empty((total, 3), dtype=np.float32)

    for i, p in enumerate(poses_raw):
        start = int(row_ptr[i])
        n     = p["NumTransforms"]
        t_off = p["TransformIdx"]
        for k in range(n):
            t = transforms_raw[t_off + k]
            pose_bones[start + k] = t["Bone"]
            r = t["Rotation"]
            pose_quats[start + k] = (r["i"], r["j"], r["k"], r["r"])   # xyzw
            v = t["Translation"]
            pose_trans[start + k] = (v["X"], v["Y"], v["Z"])

    return PoseArrays(
        num_poses   = num_poses,
        row_ptr     = row_ptr,
        pose_bones  = pose_bones,
        pose_quats  = pose_quats,
        pose_trans  = pose_trans,
    )


# Sermo part parser

def _parse_sermo_part(
    part_name: str,
    baked: dict,           # bakedData.Data.{Face|Eyes|Tongue}
    main_wk: dict,         # mainPosesData.Data.{Face|Eyes|Tongue}
    corr_wk: dict,         # correctivePosesData.Data.{Face|Eyes|Tongue}
    tracks_mapping: dict,  # bakedData global tracksMapping
) -> SermoPartData:

    #  Envelopes per track (Stage 3) 
    ept = baked["EnvelopesPerTrackMapping"]
    env_num    = len(ept)
    env_tracks = np.array([e["Track"]        for e in ept], dtype=np.int16)
    env_lods   = np.array([e["LevelOfDetail"] for e in ept], dtype=np.uint8)
    env_types  = np.array([e["Envelope"]     for e in ept], dtype=np.uint8)

    #  Global limits (Stage 4) 
    gl = baked["GlobalLimits"]
    limit_num      = len(gl)
    limit_tracks   = np.array([e["Track"]    for e in gl], dtype=np.int16)
    limit_envelope = np.array([e["Envelope"] for e in gl], dtype=np.uint8)
    limit_min      = np.array([e["Min"]      for e in gl], dtype=np.float32)
    limit_mid      = np.array([e["Mid"]      for e in gl], dtype=np.float32)
    limit_max      = np.array([e["Max"]      for e in gl], dtype=np.float32)

    #  Influence suppression (Stage 5/9) — CSR 
    ip = baked["InfluencedPoses"]
    ii = baked["InfluenceIndices"]
    infl_num    = len(ip)
    infl_tracks = np.array([e["Track"] for e in ip], dtype=np.int16)
    infl_types  = np.array([e["Type"]  for e in ip], dtype=np.uint8)

    # Build CSR row_ptr from NumInfluences
    infl_row_ptr = np.zeros(infl_num + 1, dtype=np.int32)
    for i, e in enumerate(ip):
        infl_row_ptr[i + 1] = infl_row_ptr[i] + e["NumInfluences"]
    infl_indices = np.array(ii, dtype=np.int16)

    #  Upper/lower face envelopes (Stage 6) 
    ulf = baked["UpperLowerFace"]
    ulf_num    = len(ulf)
    ulf_tracks = np.array([e["Track"] for e in ulf], dtype=np.int16)
    ulf_parts  = np.array([e["Part"]  for e in ulf], dtype=np.uint8)

    #  Lipsync pose sides (Stage 7/8) 
    lps = baked["LipsyncPosesSides"]
    lps_num    = len(lps)
    lps_tracks = np.array([e["Track"] for e in lps], dtype=np.int16)
    lps_sides  = np.array([e["Side"]  for e in lps], dtype=np.uint8)

    #  Main pose inbetween expansion (Stage 10) 
    amp   = baked["AllMainPoses"]           # 121 logical main poses
    ampi  = baked["AllMainPosesInbetweens"] # 133 flat inbetween thresholds
    amsm  = baked["AllMainPosesInbetweenScopeMultipliers"]  # 12 scope mults

    num_main_poses = len(amp)
    main_tracks    = np.array([e["Track"] for e in amp], dtype=np.int16)
    num_inbetweens = np.array([e["NumInbetweens"] for e in amp], dtype=np.int32)

    # Build ib_row_ptr (CSR into thresholds)
    ib_row_ptr = np.zeros(num_main_poses + 1, dtype=np.int32)
    np.cumsum(num_inbetweens, out=ib_row_ptr[1:])
    num_ib_poses   = int(ib_row_ptr[-1])
    ib_thresholds  = np.array(ampi, dtype=np.float32)

    # Build sm_row_ptr (CSR into scope multipliers — one per intra-pose gap)
    num_gaps      = num_inbetweens - 1           # gaps per main pose
    sm_row_ptr    = np.zeros(num_main_poses + 1, dtype=np.int32)
    np.cumsum(num_gaps, out=sm_row_ptr[1:])
    ib_scope_mults = np.array(amsm, dtype=np.float32)

    #  Global corrective entries (Stage 12) — CSR 
    gc = baked["GlobalCorrectiveEntries"]
    num_correctives = len(corr_wk["Poses"])

    gcorr_row_ptr, (gcorr_tracks_list, gcorr_flags_list) = _build_csr_multi(
        num_correctives, gc, "Index", ["Track", "Unknown"]
    )
    gcorr_tracks = np.array(gcorr_tracks_list, dtype=np.int16)
    gcorr_flags  = np.array(gcorr_flags_list,  dtype=np.uint8)

    #  Inbetween corrective entries (Stage 13) — CSR 
    # Also indexed by corrective pose index (same as GCE).
    # ICE.Track = flat inbetween-expanded pose index providing the weight.
    ic = baked["InbetweenCorrectiveEntries"]
    icorr_row_ptr, (icorr_tracks_list, icorr_flags_list) = _build_csr_multi(
        num_correctives, ic, "Index", ["Track", "Unknown"]
    )
    icorr_tracks = np.array(icorr_tracks_list, dtype=np.int16)
    icorr_flags  = np.array(icorr_flags_list,  dtype=np.uint8)

    #  Corrective influence suppression (Stage 14) — CSR 
    ci  = baked["CorrectiveInfluencedPoses"]
    cii = baked["CorrectiveInfluenceIndices"]
    num_corr_infl       = len(ci)
    corr_infl_pose_idx  = np.array([e["Index"] for e in ci], dtype=np.int32)
    corr_infl_types     = np.array([e["Type"]  for e in ci], dtype=np.uint8)

    corr_infl_row_ptr = np.zeros(num_corr_infl + 1, dtype=np.int32)
    for i, e in enumerate(ci):
        corr_infl_row_ptr[i + 1] = corr_infl_row_ptr[i] + e["NumInfluences"]
    corr_infl_influencers = np.array(cii, dtype=np.int32)

    #  Pose transform arrays (Stages 15/16) 
    main_poses       = _parse_pose_arrays(main_wk)
    corrective_poses = _parse_pose_arrays(corr_wk)

    #  Wrinkle mapping (Stage 17) 
    wrk               = baked["Wrinkles"]
    wrinkle_count         = len(wrk)
    wrinkle_source_tracks = np.array(wrk, dtype=np.int16)
    num_env  = tracks_mapping["numEnvelopes"]        # 13
    num_main = tracks_mapping["numMainPoses"]        # 141
    num_lips = tracks_mapping["numLipsyncOverrides"] # 86
    wrinkle_start_track = num_env + num_main + num_lips  # 240

    return SermoPartData(
        part_name = part_name,

        env_num    = env_num,
        env_tracks = env_tracks,
        env_lods   = env_lods,
        env_types  = env_types,

        limit_num      = limit_num,
        limit_tracks   = limit_tracks,
        limit_envelope = limit_envelope,
        limit_min      = limit_min,
        limit_mid      = limit_mid,
        limit_max      = limit_max,

        infl_num     = infl_num,
        infl_tracks  = infl_tracks,
        infl_types   = infl_types,
        infl_row_ptr = infl_row_ptr,
        infl_indices = infl_indices,

        ulf_num    = ulf_num,
        ulf_tracks = ulf_tracks,
        ulf_parts  = ulf_parts,

        lps_num    = lps_num,
        lps_tracks = lps_tracks,
        lps_sides  = lps_sides,

        num_main_poses  = num_main_poses,
        num_ib_poses    = num_ib_poses,
        main_tracks     = main_tracks,
        ib_row_ptr      = ib_row_ptr,
        ib_thresholds   = ib_thresholds,
        sm_row_ptr      = sm_row_ptr,
        ib_scope_mults  = ib_scope_mults,

        num_correctives = num_correctives,
        gcorr_row_ptr   = gcorr_row_ptr,
        gcorr_tracks    = gcorr_tracks,
        gcorr_flags     = gcorr_flags,

        icorr_row_ptr = icorr_row_ptr,
        icorr_tracks  = icorr_tracks,
        icorr_flags   = icorr_flags,

        num_corr_infl         = num_corr_infl,
        corr_infl_pose_idx    = corr_infl_pose_idx,
        corr_infl_types       = corr_infl_types,
        corr_infl_row_ptr     = corr_infl_row_ptr,
        corr_infl_influencers = corr_infl_influencers,

        main_poses       = main_poses,
        corrective_poses = corrective_poses,

        wrinkle_count         = wrinkle_count,
        wrinkle_source_tracks = wrinkle_source_tracks,
        wrinkle_start_track   = wrinkle_start_track,
    )


# Public loaders

def load_rig(path: str | Path) -> RigData:
    """
    Parse a WolvenKit-exported animRig JSON into RigData.

    Parameters
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    rc = raw["Data"]["RootChunk"]

    # Bone names & parents
    bone_names_raw = rc["boneNames"]
    num_bones      = len(bone_names_raw)
    bone_names     = np.array([_cname(b) for b in bone_names_raw], dtype=object)
    bone_parents   = np.array(rc["boneParentIndexes"], dtype=np.int16)

    # Reference pose from boneTransforms (bone-space QsTransform)
    bt = rc["boneTransforms"]
    ref_quats  = np.empty((num_bones, 4), dtype=np.float32)
    ref_trans  = np.empty((num_bones, 3), dtype=np.float32)
    ref_scales = np.empty((num_bones, 3), dtype=np.float32)
    for i, xform in enumerate(bt):
        r = xform["Rotation"]
        ref_quats[i]  = (r["i"], r["j"], r["k"], r["r"])
        t = xform["Translation"]
        ref_trans[i]  = (t["X"], t["Y"], t["Z"])
        s = xform["Scale"]
        ref_scales[i] = (s["X"], s["Y"], s["Z"])

    # Track names
    track_names_raw = rc["trackNames"]
    num_tracks  = len(track_names_raw)
    track_names = np.array([_cname(t) for t in track_names_raw], dtype=object)

    # LOD split indices
    lod_starts = np.array(rc.get("levelOfDetailStartIndices", []), dtype=np.int32)

    # Build lookup maps
    bone_index_map  = {n: i for i, n in enumerate(bone_names)}
    track_index_map = {n: i for i, n in enumerate(track_names)}

    return RigData(
        bone_names          = bone_names,
        bone_parents        = bone_parents,
        num_bones           = num_bones,
        ref_quats           = ref_quats,
        ref_trans           = ref_trans,
        ref_scales          = ref_scales,
        track_names         = track_names,
        num_tracks          = num_tracks,
        lod_start_indices   = lod_starts,
        _bone_index_map     = bone_index_map,
        _track_index_map    = track_index_map,
    )


def load_facial_setup(path: str | Path, rig: Optional[RigData] = None) -> FacialSetupData:
    """
    Parse a WolvenKit-exported .facialsetup JSON into FacialSetupData.

    Parameters
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    rc = raw["Data"]["RootChunk"]

    version = rc["version"]
    if version != FACIAL_VERSION:
        import warnings
        warnings.warn(f"Expected facialsetup version {FACIAL_VERSION}, got {version}")

    # Global arrays
    used_bones = np.array(rc["usedTransformIndices"], dtype=np.int16)

    baked         = rc["bakedData"]["Data"]
    joint_regions = np.array(baked["JointRegions"], dtype=np.uint8)
    lipsync_map   = np.array(baked["LipsyncOverridesIndexMapping"], dtype=np.int16)

    tracks_mapping = rc["info"]["tracksMapping"]

    main_data = rc["mainPosesData"]["Data"]
    corr_data = rc["correctivePosesData"]["Data"]

    # Parse each part: Face, Eyes, Tongue
    # Note: WolvenKit uses title-case keys — "Face", "Eyes", "Tongue"
    face = _parse_sermo_part(
        "face",
        baked["Face"],
        main_data["Face"],
        corr_data["Face"],
        tracks_mapping,
    )
    eyes = _parse_sermo_part(
        "eyes",
        baked["Eyes"],
        main_data["Eyes"],
        corr_data["Eyes"],
        tracks_mapping,
    )
    tongue = _parse_sermo_part(
        "tongue",
        baked["Tongue"],
        main_data["Tongue"],
        corr_data["Tongue"],
        tracks_mapping,
    )

    return FacialSetupData(
        version        = version,
        face           = face,
        eyes           = eyes,
        tongue         = tongue,
        used_bone_indices        = used_bones,
        lipsync_override_idx_map = lipsync_map,
        joint_regions            = joint_regions,
        num_envelope_tracks      = tracks_mapping["numEnvelopes"],
        num_lipsync_overrides    = tracks_mapping["numLipsyncOverrides"],
        num_main_poses           = tracks_mapping["numMainPoses"],
        num_wrinkle_tracks       = tracks_mapping["numWrinkles"],
    )


# Smoke test / summary

def _print_summary(setup: FacialSetupData, rig: RigData) -> None:
    print(f"=== FacialSetupData (v{setup.version}) ===")
    print(f"  Used bones:          {len(setup.used_bone_indices)}")
    print(f"  Lipsync overrides:   {len(setup.lipsync_override_idx_map)}")
    print(f"  Joint regions:       {len(setup.joint_regions)}")
    print(f"  Envelope tracks:     {setup.num_envelope_tracks}")
    print(f"  Main pose tracks:    {setup.num_main_poses}")
    print(f"  Wrinkle tracks:      {setup.num_wrinkle_tracks}")
    print()

    for part in (setup.face, setup.eyes, setup.tongue):
        mp = part.main_poses
        cp = part.corrective_poses
        print(f"  [{part.part_name}]")
        print(f"    Envelope mappings:  {part.env_num}")
        print(f"    Global limits:      {part.limit_num}")
        print(f"    Influence groups:   {part.infl_num}  ({len(part.infl_indices)} total influencers)")
        print(f"    Main poses (logic): {part.num_main_poses}")
        print(f"    Main poses (ib):    {part.num_ib_poses}  ({mp.row_ptr[-1]} total transforms)")
        print(f"    Scope multipliers:  {len(part.ib_scope_mults)}")
        print(f"    Correctives:        {part.num_correctives}  ({cp.row_ptr[-1]} total transforms)")
        print(f"    GCE entries:        {len(part.gcorr_tracks)}")
        print(f"    ICE entries:        {len(part.icorr_tracks)}")
        print(f"    Corr. influences:   {part.num_corr_infl}")
        print(f"    Wrinkles:           {part.wrinkle_count}")
        print()

    print(f"=== RigData ===")
    print(f"  Bones:   {rig.num_bones}")
    print(f"  Tracks:  {rig.num_tracks}")
    print(f"  LOD starts: {rig.lod_start_indices.tolist()}")
    print(f"  Track[0:6]: {rig.track_names[:6].tolist()}")


if __name__ == "__main__":
    import sys
    facial_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/mnt/user-data/uploads/h0_001_wa_a__songbird_rigsetup_facialsetup__1___1_.json"
    rig_path = sys.argv[2] if len(sys.argv) > 2 else \
        "/mnt/user-data/uploads/h0_001_wa_a__songbird_skeleton_rig.json"

    rig   = load_rig(rig_path)
    setup = load_facial_setup(facial_path, rig)
    _print_summary(setup, rig)

    # Spot-check: first face main pose drives track 13, inbetween threshold 1.0
    f = setup.face
    print("--- Spot checks ---")
    print(f"face.main_tracks[0]   = {f.main_tracks[0]}  (expect 13)")
    print(f"face.ib_thresholds[0] = {f.ib_thresholds[0]:.4f}  (expect 1.0)")
    print(f"face.main_poses.row_ptr[:5] = {f.main_poses.row_ptr[:5]}")
    print(f"face.main_poses.pose_bones[:6] = {f.main_poses.pose_bones[:6]}")
    print(f"face.main_poses.pose_quats[0]  = {f.main_poses.pose_quats[0]}  (xyzw)")
    print()
    # Inbetween expansion spot-check: pose 14 (track 27) has 2 inbetweens
    print(f"main_pose[14] track={f.main_tracks[14]}")
    start, end = int(f.ib_row_ptr[14]), int(f.ib_row_ptr[15])
    print(f"  ib range [{start}:{end}]  thresholds={f.ib_thresholds[start:end].tolist()}")
    sm_s, sm_e = int(f.sm_row_ptr[14]), int(f.sm_row_ptr[15])
    print(f"  scope_mults={f.ib_scope_mults[sm_s:sm_e].tolist()}")
    print()
    # Corrective spot-check: corrective 0 requires tracks 25 and 27
    print(f"gcorr tracks for corr[0]: {f.gcorr_tracks[f.gcorr_row_ptr[0]:f.gcorr_row_ptr[1]].tolist()}")
    print(f"gcorr tracks for corr[2]: {f.gcorr_tracks[f.gcorr_row_ptr[2]:f.gcorr_row_ptr[3]].tolist()}")
