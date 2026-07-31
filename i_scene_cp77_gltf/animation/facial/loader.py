from __future__ import annotations

from dataclasses import dataclass

import numpy as np


NUM_ENVELOPE_TRACKS = 13
NUM_ENVELOPE_WEIGHTS = 6
WEIGHT_THRESHOLD = 0.001
FACIAL_VERSION = 8

INFL_LINEAR = 0
INFL_EXPONENTIAL = 1
INFL_ORGANIC = 2

SIDE_MID = 0
SIDE_LEFT = 1
SIDE_RIGHT = 2

PART_LOWER = 0
PART_UPPER = 1
PART_LIPSYNC = 2

CORR_INFL_BY_SPEED = 0
CORR_INFL_LINEAR_CORRECTION = 1
CORR_INFL_BOTH = 2
CORR_INFL_SIMPLE = 3


@dataclass
class PoseArrays:
    num_poses: int
    row_ptr: np.ndarray
    pose_bones: np.ndarray
    pose_quats: np.ndarray
    pose_trans: np.ndarray


@dataclass
class facialPartData:
    part_name: str

    env_num: int
    env_tracks: np.ndarray
    env_lods: np.ndarray
    env_types: np.ndarray

    limit_num: int
    limit_tracks: np.ndarray
    limit_envelope: np.ndarray
    limit_min: np.ndarray
    limit_mid: np.ndarray
    limit_max: np.ndarray

    infl_num: int
    infl_tracks: np.ndarray
    infl_types: np.ndarray
    infl_row_ptr: np.ndarray
    infl_indices: np.ndarray

    ulf_num: int
    ulf_tracks: np.ndarray
    ulf_parts: np.ndarray

    lps_num: int
    lps_tracks: np.ndarray
    lps_sides: np.ndarray

    num_main_poses: int
    num_ib_poses: int
    main_tracks: np.ndarray
    ib_row_ptr: np.ndarray
    ib_thresholds: np.ndarray
    sm_row_ptr: np.ndarray
    ib_scope_mults: np.ndarray

    num_correctives: int
    gcorr_row_ptr: np.ndarray
    gcorr_tracks: np.ndarray
    gcorr_flags: np.ndarray

    icorr_row_ptr: np.ndarray
    icorr_tracks: np.ndarray
    icorr_flags: np.ndarray

    num_corr_infl: int
    corr_infl_pose_idx: np.ndarray
    corr_infl_types: np.ndarray
    corr_infl_row_ptr: np.ndarray
    corr_infl_influencers: np.ndarray

    main_poses: PoseArrays
    corrective_poses: PoseArrays

    wrinkle_count: int
    wrinkle_source_tracks: np.ndarray
    wrinkle_start_track: int


@dataclass
class FacialSetupData:
    version: int
    face: facialPartData
    eyes: facialPartData
    tongue: facialPartData

    used_bone_indices: np.ndarray
    lipsync_override_idx_map: np.ndarray
    joint_regions: np.ndarray

    num_envelope_tracks: int
    num_lipsync_overrides: int
    num_main_poses: int
    num_wrinkle_tracks: int


def _build_csr(num_rows: int, row_col_pairs) -> tuple[np.ndarray, np.ndarray]:
    row_ptr = np.zeros(num_rows + 1, dtype=np.int32)
    values = []
    for row, val in row_col_pairs:
        row_ptr[row + 1] += 1
        values.append(val)
    np.cumsum(row_ptr, out=row_ptr)
    return row_ptr, values


def _build_csr_multi(num_rows: int, entries, row_key, val_keys):
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


def _parse_pose_arrays(wk_part: dict) -> PoseArrays:
    poses_raw = wk_part["Poses"]
    transforms_raw = wk_part["Transforms"]
    num_poses = len(poses_raw)

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
        n = p["NumTransforms"]
        t_off = p["TransformIdx"]
        for k in range(n):
            t = transforms_raw[t_off + k]
            pose_bones[start + k] = t["Bone"]
            r = t["Rotation"]
            pose_quats[start + k] = (r["i"], r["j"], r["k"], r["r"])
            v = t["Translation"]
            pose_trans[start + k] = (v["X"], v["Y"], v["Z"])

    return PoseArrays(
            num_poses=num_poses,
            row_ptr=row_ptr,
            pose_bones=pose_bones,
            pose_quats=pose_quats,
            pose_trans=pose_trans,
            )


def _parse_facial_part(
        part_name: str,
        baked: dict,
        main_wk: dict,
        corr_wk: dict,
        tracks_mapping: dict,
        part_info: dict,
        ) -> facialPartData:

    ept = baked["EnvelopesPerTrackMapping"]
    env_num = len(ept)
    env_tracks = np.array([e["Track"] for e in ept], dtype=np.int16)
    env_lods = np.array([e["LevelOfDetail"] for e in ept], dtype=np.uint8)
    env_types = np.array([e["Envelope"] for e in ept], dtype=np.uint8)

    gl = baked["GlobalLimits"]
    limit_num = len(gl)
    limit_tracks = np.array([e["Track"] for e in gl], dtype=np.int16)
    limit_envelope = np.array([e["Envelope"] for e in gl], dtype=np.uint8)
    limit_min = np.array([e["Min"] for e in gl], dtype=np.float32)
    limit_mid = np.array([e["Mid"] for e in gl], dtype=np.float32)
    limit_max = np.array([e["Max"] for e in gl], dtype=np.float32)

    ip = baked["InfluencedPoses"]
    ii = baked["InfluenceIndices"]
    infl_num = len(ip)
    infl_tracks = np.array([e["Track"] for e in ip], dtype=np.int16)
    infl_types = np.array([e["Type"] for e in ip], dtype=np.uint8)

    infl_row_ptr = np.zeros(infl_num + 1, dtype=np.int32)
    for i, e in enumerate(ip):
        infl_row_ptr[i + 1] = infl_row_ptr[i] + e["NumInfluences"]
    infl_indices = np.array(ii, dtype=np.int16)

    ulf = baked["UpperLowerFace"]
    ulf_num = len(ulf)
    ulf_tracks = np.array([e["Track"] for e in ulf], dtype=np.int16)
    ulf_parts = np.array([e["Part"] for e in ulf], dtype=np.uint8)

    lps = baked["LipsyncPosesSides"]
    lps_num = len(lps)
    lps_tracks = np.array([e["Track"] for e in lps], dtype=np.int16)
    lps_sides = np.array([e["Side"] for e in lps], dtype=np.uint8)

    amp = baked["AllMainPoses"]
    ampi = baked["AllMainPosesInbetweens"]
    amsm = baked["AllMainPosesInbetweenScopeMultipliers"]

    num_main_poses = len(amp)
    main_tracks = np.array([e["Track"] for e in amp], dtype=np.int16)
    num_inbetweens = np.array([e["NumInbetweens"] for e in amp], dtype=np.int32)

    ib_row_ptr = np.zeros(num_main_poses + 1, dtype=np.int32)
    np.cumsum(num_inbetweens, out=ib_row_ptr[1:])
    num_ib_poses = int(ib_row_ptr[-1])
    ib_thresholds = np.array(ampi, dtype=np.float32)

    num_gaps = num_inbetweens - 1
    sm_row_ptr = np.zeros(num_main_poses + 1, dtype=np.int32)
    np.cumsum(num_gaps, out=sm_row_ptr[1:])
    ib_scope_mults = np.array(amsm, dtype=np.float32)

    gc = baked["GlobalCorrectiveEntries"]
    num_correctives = len(corr_wk["Poses"])

    gcorr_row_ptr, (gcorr_tracks_list, gcorr_flags_list) = _build_csr_multi(
            num_correctives, gc, "Index", ["Track", "Unknown"]
            )
    gcorr_tracks = np.array(gcorr_tracks_list, dtype=np.int16)
    gcorr_flags = np.array(gcorr_flags_list, dtype=np.uint8)

    ic = baked["InbetweenCorrectiveEntries"]
    icorr_row_ptr, (icorr_tracks_list, icorr_flags_list) = _build_csr_multi(
            num_correctives, ic, "Index", ["Track", "Unknown"]
            )
    icorr_tracks = np.array(icorr_tracks_list, dtype=np.int16)
    icorr_flags = np.array(icorr_flags_list, dtype=np.uint8)

    ci = baked["CorrectiveInfluencedPoses"]
    cii = baked["CorrectiveInfluenceIndices"]
    num_corr_infl = len(ci)
    corr_infl_pose_idx = np.array([e["Index"] for e in ci], dtype=np.int32)
    corr_infl_types = np.array([e["Type"] for e in ci], dtype=np.uint8)

    corr_infl_row_ptr = np.zeros(num_corr_infl + 1, dtype=np.int32)
    for i, e in enumerate(ci):
        corr_infl_row_ptr[i + 1] = corr_infl_row_ptr[i] + e["NumInfluences"]
    corr_infl_influencers = np.array(cii, dtype=np.int32)

    main_poses = _parse_pose_arrays(main_wk)
    corrective_poses = _parse_pose_arrays(corr_wk)

    wrk = baked["Wrinkles"]
    wrinkle_count = len(wrk)
    wrinkle_source_tracks = np.array(wrk, dtype=np.int16)
    wrinkle_start_track = int(part_info["wrinkleStartingIndex"])

    return facialPartData(
            part_name=part_name,

            env_num=env_num,
            env_tracks=env_tracks,
            env_lods=env_lods,
            env_types=env_types,

            limit_num=limit_num,
            limit_tracks=limit_tracks,
            limit_envelope=limit_envelope,
            limit_min=limit_min,
            limit_mid=limit_mid,
            limit_max=limit_max,

            infl_num=infl_num,
            infl_tracks=infl_tracks,
            infl_types=infl_types,
            infl_row_ptr=infl_row_ptr,
            infl_indices=infl_indices,

            ulf_num=ulf_num,
            ulf_tracks=ulf_tracks,
            ulf_parts=ulf_parts,

            lps_num=lps_num,
            lps_tracks=lps_tracks,
            lps_sides=lps_sides,

            num_main_poses=num_main_poses,
            num_ib_poses=num_ib_poses,
            main_tracks=main_tracks,
            ib_row_ptr=ib_row_ptr,
            ib_thresholds=ib_thresholds,
            sm_row_ptr=sm_row_ptr,
            ib_scope_mults=ib_scope_mults,

            num_correctives=num_correctives,
            gcorr_row_ptr=gcorr_row_ptr,
            gcorr_tracks=gcorr_tracks,
            gcorr_flags=gcorr_flags,

            icorr_row_ptr=icorr_row_ptr,
            icorr_tracks=icorr_tracks,
            icorr_flags=icorr_flags,

            num_corr_infl=num_corr_infl,
            corr_infl_pose_idx=corr_infl_pose_idx,
            corr_infl_types=corr_infl_types,
            corr_infl_row_ptr=corr_infl_row_ptr,
            corr_infl_influencers=corr_infl_influencers,

            main_poses=main_poses,
            corrective_poses=corrective_poses,

            wrinkle_count=wrinkle_count,
            wrinkle_source_tracks=wrinkle_source_tracks,
            wrinkle_start_track=wrinkle_start_track,
            )


def parse_facial_setup(payload):
    rc = payload["Data"]["RootChunk"]

    version = rc["version"]
    if version != FACIAL_VERSION:
        import warnings
        warnings.warn(f"Expected facialsetup version {FACIAL_VERSION}, got {version}")

    used_bones = np.array(rc["usedTransformIndices"], dtype=np.int16)

    baked = rc["bakedData"]["Data"]
    joint_regions = np.array(baked["JointRegions"], dtype=np.uint8)
    lipsync_map = np.array(baked["LipsyncOverridesIndexMapping"], dtype=np.int16)

    tracks_mapping = rc["info"]["tracksMapping"]

    main_data = rc["mainPosesData"]["Data"]
    corr_data = rc["correctivePosesData"]["Data"]

    face = _parse_facial_part(
            "face",
            baked["Face"],
            main_data["Face"],
            corr_data["Face"],
            tracks_mapping,
            rc["info"]["face"],
            )
    eyes = _parse_facial_part(
            "eyes",
            baked["Eyes"],
            main_data["Eyes"],
            corr_data["Eyes"],
            tracks_mapping,
            rc["info"]["eyes"],
            )
    tongue = _parse_facial_part(
            "tongue",
            baked["Tongue"],
            main_data["Tongue"],
            corr_data["Tongue"],
            tracks_mapping,
            rc["info"]["tongue"],
            )

    return FacialSetupData(
            version=version,
            face=face,
            eyes=eyes,
            tongue=tongue,
            used_bone_indices=used_bones,
            lipsync_override_idx_map=lipsync_map,
            joint_regions=joint_regions,
            num_envelope_tracks=tracks_mapping["numEnvelopes"],
            num_lipsync_overrides=tracks_mapping["numLipsyncOverrides"],
            num_main_poses=tracks_mapping["numMainPoses"],
            num_wrinkle_tracks=tracks_mapping["numWrinkles"],
            )


def _print_summary(setup: FacialSetupData, rig) -> None:
    print(f" FacialSetupData (v{setup.version}) ")
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
        print(f"    Influence poses:   {part.infl_num}  ({len(part.infl_indices)} total influencers)")
        print(f"    Main poses: {part.num_main_poses}")
        print(f"    Main pose inbetweens:    {part.num_ib_poses}  ({mp.row_ptr[-1]} total transforms)")
        print(f"    Scope multipliers:  {len(part.ib_scope_mults)}")
        print(f"    Correctives:        {part.num_correctives}  ({cp.row_ptr[-1]} total transforms)")
        print(f"    Global Corrective entries:        {len(part.gcorr_tracks)}")
        print(f"    Inbetween Corrective entries:        {len(part.icorr_tracks)}")
        print(f"    Corr. influences:   {part.num_corr_infl}")
        print(f"    Wrinkles:           {part.wrinkle_count}")
        print()

    print(f"=== RigData ===")
    print(f"  Bones:   {rig.num_bones}")
    print(f"  Tracks:  {rig.num_tracks}")
    print(f"  LOD starts: {rig.lod_start_indices.tolist()}")
    print(f"  Track[0:6]: {rig.track_names[:6].tolist()}")
