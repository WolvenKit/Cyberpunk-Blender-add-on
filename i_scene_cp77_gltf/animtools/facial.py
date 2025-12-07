from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, List
import numpy as np
from ..main.datashards import RigSkeleton

from .bartmoss_math import (
    to_int_array,
    to_float_array,
    quat_identity,
    scale_identity,
)

class FacialSetup:
    """Complete facial animation setup data
    
    Contains:
        - face_meta: Metadata for envelope mappings, limits, influences, etc.
        - face_main_bank: Main pose transforms (quaternions, translations, scales)
        - face_corrective_bank: Corrective pose transforms
    """
    pass


def load_wkit_rig_skeleton(path: str | Path) -> RigSkeleton:
    """Load skeleton rig from WolvenKit JSON export
    
    Args:
        path: Path to rig JSON file
    
    Returns:
        RigSkeleton with bone hierarchy and reference pose
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON structure is invalid
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Rig file not found: {path}")
    
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in rig file: {e}")
    
    # Navigate to root chunk
    try:
        root = data["Data"]["RootChunk"]
    except KeyError:
        raise ValueError("Missing Data.RootChunk in rig JSON")
    
    # Extract bone names
    bone_names = []
    for e in root.get("boneNames", []):
        if isinstance(e, dict):
            bone_names.append(e.get("$value", ""))
        else:
            bone_names.append(str(e))
    
    # Extract parent indices
    parent_indices = to_int_array(
        root.get("boneParentIndexes", []),
        dtype=np.int16
    )
    
    # Extract track names
    track_names = []
    for e in root.get("trackNames", []):
        if isinstance(e, dict):
            track_names.append(e.get("$value", ""))
        else:
            track_names.append(str(e))
    
    # Validate bone count
    N = len(bone_names)
    if N == 0:
        raise ValueError("No bones found in rig")
    
    if len(parent_indices) != N:
        raise ValueError(f"Parent indices count ({len(parent_indices)}) doesn't match bone count ({N})")
    
    # Extract reference track defaults
    reference_tracks_raw = root.get("referenceTracks", [])
    M = len(track_names)
    
    if len(reference_tracks_raw) != M:
        print(f"Warning: referenceTracks count ({len(reference_tracks_raw)}) doesn't match track names ({M})")
        # Pad with zeros if needed
        reference_tracks_raw = list(reference_tracks_raw) + [0.0] * (M - len(reference_tracks_raw))
    
    reference_tracks = to_float_array(reference_tracks_raw[:M], dtype=np.float32)
    
    # Extract reference pose transforms
    trs = root.get("boneTransforms", [])
    
    # Initialize arrays (identity transforms using bartmoss_math functions)
    q = quat_identity(N)
    t = np.zeros((N, 3), dtype=np.float32)
    s = scale_identity(N)
    
    # Parse transforms
    for i, tr in enumerate(trs[:N]):
        if not isinstance(tr, dict):
            continue
        
        # Rotation (quaternion)
        r = tr.get("Rotation", {})
        if isinstance(r, dict):
            q[i] = [
                float(r.get("i", 0.0)),
                float(r.get("j", 0.0)),
                float(r.get("k", 0.0)),
                float(r.get("r", 1.0))
            ]
        
        # Translation
        tt = tr.get("Translation", {})
        if isinstance(tt, dict):
            t[i] = [
                float(tt.get("X", 0.0)),
                float(tt.get("Y", 0.0)),
                float(tt.get("Z", 0.0))
            ]
        
        # Scale
        sc = tr.get("Scale", {})
        if isinstance(sc, dict):
            s[i] = [
                float(sc.get("X", 1.0)),
                float(sc.get("Y", 1.0)),
                float(sc.get("Z", 1.0))
            ]
    
    return RigSkeleton(
        num_bones=N,
        parent_indices=parent_indices,
        bone_names=bone_names,
        track_names=track_names,
        reference_tracks=reference_tracks,
        ls_q=q,
        ls_t=t,
        ls_s=s
    )


def load_wkit_facialsetup(path: str | Path, rig_info: RigSkeleton) -> FacialSetup:
    """Load facial setup from WolvenKit JSON export
    
    Args:
        path: Path to facial setup JSON file
        rig_info: Previously loaded rig skeleton
    
    Returns:
        FacialSetup object with metadata and pose banks
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON structure is invalid
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Facial setup file not found: {path}")
    
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in facial setup: {e}")
    
    # Navigate to root
    try:
        root = data["Data"]["RootChunk"]
        baked = root["bakedData"]["Data"]["Face"]
        main_face = root["mainPosesData"]["Data"]["Face"]
        corr_face = root["correctivePosesData"]["Data"]["Face"]
    except KeyError as e:
        raise ValueError(f"Missing required key in facial setup: {e}")
    
    # === Build Face Metadata ===
    class FaceMeta:
        """Container for baked facial animation metadata"""
        pass
    
    face_meta = FaceMeta()
    
    # Envelope mappings
    env = baked.get("EnvelopesPerTrackMapping", [])
    setattr(face_meta, "envelopes_track", to_int_array([e.get("Track", 0) for e in env]))
    setattr(face_meta, "envelopes_type", to_int_array([e.get("Envelope", 0) for e in env], np.int8))
    setattr(face_meta, "envelopes_lod", to_int_array([e.get("LevelOfDetail", 0) for e in env], np.int8))
    
    # Global limits
    gl = baked.get("GlobalLimits", [])
    setattr(face_meta, "global_limits_track", to_int_array([e.get("Track", 0) for e in gl]))
    setattr(face_meta, "global_limits_min", to_float_array([e.get("Min", 0.0) for e in gl]))
    setattr(face_meta, "global_limits_mid", to_float_array([e.get("Mid", 0.0) for e in gl]))
    setattr(face_meta, "global_limits_max", to_float_array([e.get("Max", 0.0) for e in gl]))
    setattr(face_meta, "global_limits_type", to_int_array([e.get("Envelope", 0) for e in gl], np.int8))
    
    # Influenced poses
    infl = baked.get("InfluencedPoses", [])
    setattr(face_meta, "influenced_poses_track", to_int_array([e.get("Track", 0) for e in infl]))
    setattr(face_meta, "influenced_poses_num", to_int_array([e.get("NumInfluences", 0) for e in infl], np.int8))
    setattr(face_meta, "influenced_poses_type", to_int_array([e.get("Type", 0) for e in infl], np.int8))
    setattr(face_meta, "influence_indices", to_int_array(baked.get("InfluenceIndices", [])))
    
    # Upper/lower face
    ul = baked.get("UpperLowerFace", [])
    setattr(face_meta, "upper_lower_track", to_int_array([e.get("Track", 0) for e in ul]))
    setattr(face_meta, "upper_lower_part", to_int_array([e.get("Part", 0) for e in ul], np.int8))
    
    # Main poses
    mp = baked.get("AllMainPoses", [])
    setattr(face_meta, "mainposes_track", to_int_array([e.get("Track", 0) for e in mp]))
    setattr(face_meta, "mainposes_num_inbtw", to_int_array([e.get("NumInbetweens", 0) for e in mp]))
    setattr(face_meta, "mainposes_inbtw", to_float_array(baked.get("AllMainPosesInbetweens", [])))
    setattr(face_meta, "inbtw_scope_multipliers", to_float_array(baked.get("AllMainPosesInbetweenScopeMultipliers", [])))
    
    # Corrective entries
    setattr(face_meta, "global_corrective_entries", baked.get("GlobalCorrectiveEntries", []))
    setattr(face_meta, "inbetween_corrective_entries", baked.get("InbetweenCorrectiveEntries", []))
    setattr(face_meta, "corrective_influenced_poses", baked.get("CorrectiveInfluencedPoses", []))
    setattr(face_meta, "corrective_influence_indices", to_int_array(baked.get("CorrectiveInfluenceIndices", [])))
    
    # Lipsync overrides (AnimOverrideWeight tracks) - Offset 140
    ls_ovr_mapping = root["bakedData"]["Data"].get("LipsyncOverridesIndexMapping", [])
    setattr(face_meta, "lipsync_overrides_mapping", to_int_array(ls_ovr_mapping))
    
    # Lipsync poses (LipsyncPoseOutput tracks) - Offset 240
    ls_pose_sides = baked.get("LipsyncPosesSides", [])
    setattr(face_meta, "lipsync_pose_sides", ls_pose_sides)
    
    # Wrinkle data - Offset 381+
    wrinkle_map = baked.get("Wrinkles", [])
    setattr(face_meta, "wrinkle_mapping", to_int_array(wrinkle_map))
    wrinkle_start = root["info"]["face"].get("wrinkleStartingIndex", 381)
    setattr(face_meta, "wrinkle_starting_index", int(wrinkle_start))
    
    # === Build Pose Banks ===
    
    def _build_bank(num_bones: int, poses_desc: list, transforms: list):
        """Build pose bank from JSON data
        
        Creates arrays of additive transforms for all poses.
        Sparse: only stores non-identity transforms per pose.
        
        Args:
            num_bones: Total bone count
            poses_desc: List of pose descriptors with TransformIdx, NumTransforms
            transforms: Flat list of all transform records
        
        Returns:
            Object with .q, .t, .s attributes (P, N, *) arrays
        """
        P = len(poses_desc)
        
        # Initialize with identity transforms using bartmoss_math
        q = np.tile(quat_identity(num_bones), (P, 1, 1))  # (P, N, 4)
        t = np.zeros((P, num_bones, 3), dtype=np.float32)  # (P, N, 3)
        s = np.tile(scale_identity(num_bones), (P, 1, 1))  # (P, N, 3)
        
        # Fill in sparse transforms
        for p_idx, pose in enumerate(poses_desc):
            start = int(pose.get("TransformIdx", 0))
            count = int(pose.get("NumTransforms", 0))
            
            for rec in transforms[start:start+count]:
                b = int(rec.get("Bone", -1))
                if b < 0 or b >= num_bones:
                    continue
                
                # Rotation (quaternion)
                rot = rec.get("Rotation", {})
                if isinstance(rot, dict):
                    q[p_idx, b, :] = [
                        float(rot.get("i", 0.0)),
                        float(rot.get("j", 0.0)),
                        float(rot.get("k", 0.0)),
                        float(rot.get("r", 1.0))
                    ]
                
                # Translation
                trn = rec.get("Translation", {})
                if isinstance(trn, dict):
                    t[p_idx, b, :] = [
                        float(trn.get("X", 0.0)),
                        float(trn.get("Y", 0.0)),
                        float(trn.get("Z", 0.0))
                    ]
                
                # Scale (not used but stored)
                scl = rec.get("Scale", {})
                if isinstance(scl, dict):
                    s[p_idx, b, :] = [
                        float(scl.get("X", 1.0)),
                        float(scl.get("Y", 1.0)),
                        float(scl.get("Z", 1.0))
                    ]
        
        # Return as simple object
        class Bank:
            pass
        bank = Bank()
        bank.q = q
        bank.t = t
        bank.s = s
        return bank
    
    # Build main pose bank
    fb_main = _build_bank(
        rig_info.num_bones,
        main_face["Poses"],
        main_face["Transforms"]
    )
    
    # Build corrective pose bank
    fb_corr = _build_bank(
        rig_info.num_bones,
        corr_face["Poses"],
        corr_face["Transforms"]
    )
    
    # === Validation ===
    expected_main = len(mp)
    actual_main = fb_main.q.shape[0]
    if expected_main != actual_main:
        print(f"Warning: Expected {expected_main} main poses, got {actual_main}")
    
    expected_corr = len(face_meta.global_corrective_entries) + len(face_meta.inbetween_corrective_entries)
    actual_corr = fb_corr.q.shape[0]
    if expected_corr > actual_corr:
        print(f"Warning: Corrective entries reference up to index {expected_corr}, but only {actual_corr} poses loaded")
    
    # === Build Final Setup Object ===
    
    setup = FacialSetup()
    setup.face_meta = face_meta
    setup.face_main_bank = fb_main
    setup.face_corrective_bank = fb_corr
    
    return setup
