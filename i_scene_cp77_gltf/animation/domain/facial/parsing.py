from __future__ import annotations

import numpy as np

from ....bartmoss.arrays import build_csr_columns
from ....core.log import get_logger
from ...model.facial.setup import FacialPartData, FacialSetupData, PoseArrays

_LOG = get_logger(__name__)


WEIGHT_THRESHOLD = 0.001
FACIAL_VERSION = 8


def _parse_pose_arrays(wk_part: dict) -> PoseArrays:
    poses_raw = wk_part["Poses"]
    transforms_raw = wk_part["Transforms"]
    num_poses = len(poses_raw)

    row_ptr = np.empty(num_poses + 1, dtype=np.int32)
    row_ptr[0] = 0
    for i, p in enumerate(poses_raw):
        row_ptr[i + 1] = row_ptr[i] + p["NumTransforms"]
    total = int(row_ptr[-1])

    pose_bones = np.empty(total, dtype=np.intp)
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
        lod1_counts=_lod_counts(
            poses_raw, ("Flag2", "NumTransformsForLod1", "numTransformsForLod1")
        ),
        lod2_counts=_lod_counts(
            poses_raw, ("Flag3", "NumTransformsForLod2", "numTransformsForLod2")
        ),
    )


def _lod_counts(poses_raw, keys) -> np.ndarray | None:
    # A pose's per-LOD transform counts are its last three 16-bit fields, which WolvenKit
    # exports as Flag1 (padding), Flag2 (LOD 1) and Flag3 (LOD 2).
    for key in keys:
        if poses_raw and all(key in p for p in poses_raw):
            counts = np.array([int(p[key]) for p in poses_raw], dtype=np.intp)
            totals = np.array(
                [int(p["NumTransforms"]) for p in poses_raw], dtype=np.intp
            )
            return np.minimum(np.maximum(counts, 0), totals)
    return None


def _parse_facial_part(
    part_name: str,
    baked: dict,
    main_wk: dict,
    corr_wk: dict,
    part_info: dict,
) -> FacialPartData:

    ept = baked["EnvelopesPerTrackMapping"]
    env_num = len(ept)
    env_tracks = np.array([e["Track"] for e in ept], dtype=np.intp)
    env_lods = np.array([e["LevelOfDetail"] for e in ept], dtype=np.uint8)
    env_types = np.array([e["Envelope"] for e in ept], dtype=np.uint8)

    gl = baked["GlobalLimits"]
    limit_num = len(gl)
    limit_tracks = np.array([e["Track"] for e in gl], dtype=np.intp)
    limit_envelope = np.array([e["Envelope"] for e in gl], dtype=np.uint8)
    limit_min = np.array([e["Min"] for e in gl], dtype=np.float32)
    limit_mid = np.array([e["Mid"] for e in gl], dtype=np.float32)
    limit_max = np.array([e["Max"] for e in gl], dtype=np.float32)

    ip = baked["InfluencedPoses"]
    ii = baked["InfluenceIndices"]
    infl_num = len(ip)
    infl_tracks = np.array([e["Track"] for e in ip], dtype=np.intp)
    infl_types = np.array([e["Type"] for e in ip], dtype=np.uint8)

    infl_row_ptr = np.zeros(infl_num + 1, dtype=np.int32)
    for i, e in enumerate(ip):
        infl_row_ptr[i + 1] = infl_row_ptr[i] + e["NumInfluences"]
    infl_indices = np.array(ii, dtype=np.intp)

    ulf = baked["UpperLowerFace"]
    ulf_num = len(ulf)
    ulf_tracks = np.array([e["Track"] for e in ulf], dtype=np.intp)
    ulf_parts = np.array([e["Part"] for e in ulf], dtype=np.uint8)

    lps = baked["LipsyncPosesSides"]
    lps_num = len(lps)
    lps_tracks = np.array([e["Track"] for e in lps], dtype=np.intp)
    lps_sides = np.array([e["Side"] for e in lps], dtype=np.uint8)

    amp = baked["AllMainPoses"]
    ampi = baked["AllMainPosesInbetweens"]
    amsm = baked["AllMainPosesInbetweenScopeMultipliers"]

    num_main_poses = len(amp)
    main_tracks = np.array([e["Track"] for e in amp], dtype=np.intp)
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

    gcorr_row_ptr, (gcorr_tracks_list, gcorr_flags_list) = build_csr_columns(
        num_correctives, gc, "Index", ["Track", "Unknown"]
    )
    gcorr_tracks = np.array(gcorr_tracks_list, dtype=np.intp)
    gcorr_flags = np.array(gcorr_flags_list, dtype=np.uint8)

    ic = baked["InbetweenCorrectiveEntries"]
    icorr_row_ptr, (icorr_tracks_list, icorr_flags_list) = build_csr_columns(
        num_correctives, ic, "Index", ["Track", "Unknown"]
    )
    icorr_tracks = np.array(icorr_tracks_list, dtype=np.intp)
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
    wrinkle_source_tracks = np.array(wrk, dtype=np.intp)
    wrinkle_start_track = int(part_info["wrinkleStartingIndex"])

    return FacialPartData(
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
        _LOG.warning(
            "Facial setup version mismatch: expected=%d actual=%s",
            FACIAL_VERSION,
            version,
        )

    used_bones = np.array(rc["usedTransformIndices"], dtype=np.intp)

    baked = rc["bakedData"]["Data"]
    joint_regions = np.array(baked["JointRegions"], dtype=np.uint8)
    lipsync_map = np.array(baked["LipsyncOverridesIndexMapping"], dtype=np.intp)

    tracks_mapping = rc["info"]["tracksMapping"]

    main_data = rc["mainPosesData"]["Data"]
    corr_data = rc["correctivePosesData"]["Data"]

    face = _parse_facial_part(
        "face",
        baked["Face"],
        main_data["Face"],
        corr_data["Face"],
        rc["info"]["face"],
    )
    eyes = _parse_facial_part(
        "eyes",
        baked["Eyes"],
        main_data["Eyes"],
        corr_data["Eyes"],
        rc["info"]["eyes"],
    )
    tongue = _parse_facial_part(
        "tongue",
        baked["Tongue"],
        main_data["Tongue"],
        corr_data["Tongue"],
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
