from __future__ import annotations
import numpy as np
from typing import Dict, List, Any, Optional
from .constants import (
    WEIGHT_THRESHOLD,
    NUM_ENVELOPE_TRACKS,
    ENV_LIPSYNC_ENVELOPE, ENV_UPPER_FACE, ENV_LOWER_FACE,
    ENV_JALI_JAW, ENV_JALI_LIPS,
    ENV_MUZZLE_LIPS, ENV_MUZZLE_EYES, ENV_MUZZLE_BROWS, ENV_MUZZLE_EYE_DIRS,
    LIPSYNC_OVERRIDE_OFFSET, LIPSYNC_POSE_OFFSET,
    INFLUENCE_LINEAR, INFLUENCE_EXPONENTIAL, INFLUENCE_ORGANIC,
    CORRECTIVE_INFLUENCE_BY_SPEED, CORRECTIVE_INFLUENCE_LINEAR_CORRECTION,
)
from .math_utils import clamp, lerp, limit_weight, wrinkle_weight
import bpy 

def normalize_track_name(x: Any) -> str:
    """Extract string from track name 
    
    Args:
        x: Track name (string or dict with $value key)
    
    Returns:
        Normalized string name
    """
    if isinstance(x, dict):
        return str(x.get("$value") or x.get("value") or "")
    return str(x)

def build_track_name_map(rig) -> Dict[str, int]:
    """Build name→index mapping from rig track names
    
    Args:
        rig: Rig info object with track_names attribute
    
    Returns:
        Dictionary mapping track names to indices
    """
    names = [normalize_track_name(n) for n in getattr(rig, "track_names", []) or []]
    return {n: i for i, n in enumerate(names) if n}

def safe_track_index(name_map: Dict[str, int], name: str) -> int:
    """Safe track index lookup
    
    Args:
        name_map: Name to index mapping
        name: Track name to look up
    
    Returns:
        Track index, or -1 if not found
    """
    return int(name_map.get(name, -1))

def apply_envelope_weights(
    meta,
    muzzles: np.ndarray,
    tracks: np.ndarray,
    lod: int = 0,
    lod_weight: float = 0.0
) -> None:
    """Apply muzzle envelope scaling to tracks

    Args:
        meta: Face metadata with envelopes_track, envelopes_type, envelopes_lod
        muzzles: Muzzle values array [jaw, lips, eyes, brows, eyeDirs, none]
        tracks: Track array (modified in-place)
        lod: Current level of detail
        lod_weight: Blend weight for current LOD
    """
    M = tracks.shape[0]
    
    env_tracks = meta.envelopes_track
    env_types = meta.envelopes_type
    env_lods = getattr(meta, 'envelopes_lod', np.zeros_like(env_tracks))
    
    for k in range(len(env_tracks)):
        trk_idx = int(env_tracks[k])
        if not (0 <= trk_idx < M):
            continue
        
        env_type = int(env_types[k])
        lod_level = int(env_lods[k])
        
        weight = clamp(tracks[trk_idx], 0.0, 1.0)
        
        if weight <= WEIGHT_THRESHOLD:
            tracks[trk_idx] = 0.0
            continue
        
        muzzle_val = float(muzzles[env_type]) if 0 <= env_type < len(muzzles) else 1.0
        
        # LOD filtering
        if lod_level > lod:
            weight *= muzzle_val
        elif lod_level == lod:
            weight *= muzzle_val * (1.0 - lod_weight)
        else:
            weight = 0.0
        
        tracks[trk_idx] = weight

def apply_global_limits(
    meta,
    envelopes: np.ndarray,
    muzzle_lips: float,
    tracks: np.ndarray
) -> None:
    """Constrain track weights using min/mid/max limit values
    
    Args:
        meta: Face metadata with global_limits_* arrays
        envelopes: [jawMult, lipsMult, 1, 1, 1, 1]
        muzzle_lips: Muzzle lips value for lerp
        tracks: Track array (modified in-place)
    """
    M = tracks.shape[0]
    
    for i in range(len(meta.global_limits_track)):
        trk_idx = int(meta.global_limits_track[i])
        if not (0 <= trk_idx < M):
            continue
        
        env_type = int(meta.global_limits_type[i])
        min_val = float(meta.global_limits_min[i])
        mid_val = float(meta.global_limits_mid[i])
        max_val = float(meta.global_limits_max[i])
        
        slider = float(envelopes[env_type]) if 0 <= env_type < len(envelopes) else 1.0
        limit = limit_weight(slider, min_val, mid_val, max_val)
        
        current = float(tracks[trk_idx])
        if current > limit:
            tracks[trk_idx] = lerp(muzzle_lips, current, limit)

def apply_influences(meta, tracks: np.ndarray) -> None:
    """Apply influence system to reduce conflicting poses
    
    Three influence types: LINEAR, EXPONENTIAL, ORGANIC
    
    Args:
        meta: Face metadata with influenced_poses_* arrays
        tracks: Track array (modified in-place)
    """
    M = tracks.shape[0]
    idx = 0
    
    for i in range(len(meta.influenced_poses_track)):
        trk_idx = int(meta.influenced_poses_track[i])
        num_influences = int(meta.influenced_poses_num[i])
        influence_type = int(meta.influenced_poses_type[i])
        
        if not (0 <= trk_idx < M):
            idx += num_influences
            continue
        
        weight = float(tracks[trk_idx])
        if weight <= WEIGHT_THRESHOLD:
            idx += num_influences
            continue
        
        # Accumulate influencer weights
        influence_sum = 0.0
        for j in range(num_influences):
            inf_trk = int(meta.influence_indices[idx + j])
            if 0 <= inf_trk < M:
                influence_sum += float(tracks[inf_trk])
        idx += num_influences
        
        if influence_sum >= 1.0:
            weight = 0.0
        elif influence_type == INFLUENCE_LINEAR:
            max_allowed = 1.0 - influence_sum
            if max_allowed < weight:
                weight = max_allowed
        elif influence_type == INFLUENCE_EXPONENTIAL:
            weight *= 1.0 - (influence_sum * influence_sum)
        elif influence_type == INFLUENCE_ORGANIC:
            opposite = 1.0 - influence_sum
            weight *= opposite * opposite
        
        tracks[trk_idx] = weight

def apply_upper_lower_face_envelopes(
    meta,
    face_part_weights: np.ndarray,
    tracks: np.ndarray
) -> None:
    """Apply upper/lower face envelope scaling
       
    Args:
        meta: Face metadata with upper_lower_* arrays
        face_part_weights: [none=1.0, upper, lower]
        tracks: Track array (modified in-place)
    """
    M = tracks.shape[0]
    
    for i in range(len(meta.upper_lower_track)):
        trk_idx = int(meta.upper_lower_track[i])
        part = int(meta.upper_lower_part[i])
        
        if not (0 <= trk_idx < M):
            continue
        
        envelope = float(face_part_weights[part]) if 0 <= part < len(face_part_weights) else 1.0
        
        tracks[trk_idx] = clamp(tracks[trk_idx] * envelope, 0.0, 1.0)

def apply_lipsync_overrides(
    meta,
    lipsync_envelope: float,
    in_tracks: np.ndarray,
    tracks: np.ndarray
) -> None:
    """Apply lipsync override (multiplicative)
    
    Formula: mainPose *= lerp(lipsyncEnv, 1.0, overrideValue)
    
    Args:
        meta: Face metadata with lipsync_overrides_mapping
        lipsync_envelope: Lipsync envelope value (0-1)
        in_tracks: Input track array (read-only)
        tracks: Output track array (modified in-place)
    """
    if lipsync_envelope == 0.0:
        return
    
    M = tracks.shape[0]
    mapping = meta.lipsync_overrides_mapping
    
    for i in range(len(mapping)):
        main_track_idx = int(mapping[i])
        override_track_idx = LIPSYNC_OVERRIDE_OFFSET + i
        
        if 0 <= main_track_idx < M and 0 <= override_track_idx < M:
            override_value = float(in_tracks[override_track_idx])
            multiplier = lerp(lipsync_envelope, 1.0, override_value)
            tracks[main_track_idx] *= multiplier

def apply_lipsync_poses(
    meta,
    in_tracks: np.ndarray,
    tracks: np.ndarray
) -> None:
    """Apply lipsync poses (additive)
    
    Formula: mainPose = clamp(mainPose + lipsyncPose, 0, 1)
    
    Args:
        meta: Face metadata with lipsync_pose_sides
        in_tracks: Input track array
        tracks: Output track array (modified in-place)
    """
    M = tracks.shape[0]
    
    for entry in meta.lipsync_pose_sides:
        main_track_idx = int(entry.get("Track", -1))
        if main_track_idx < 0:
            continue
        
        lipsync_track_idx = LIPSYNC_POSE_OFFSET + (main_track_idx - NUM_ENVELOPE_TRACKS)
        
        if 0 <= main_track_idx < M and 0 <= lipsync_track_idx < M:
            main_weight = float(tracks[main_track_idx])
            lipsync_weight = float(in_tracks[lipsync_track_idx])
            tracks[main_track_idx] = clamp(main_weight + lipsync_weight, 0.0, 1.0)

def calculate_inbetween_weights(meta, tracks: np.ndarray) -> np.ndarray:
    """Calculate in-between weights from main pose weights
       
    Args:
        meta: Face metadata with mainposes_* arrays
        tracks: Current track weights
    
    Returns:
        Array of in-between weights
    """
    M = tracks.shape[0]
    total_inbtw = int(np.sum(meta.mainposes_num_inbtw.astype(np.int64)))
    inbetween_weights = np.zeros(total_inbtw, dtype=np.float64)
    
    out_idx = 0
    weight_idx = 0
    scope_idx = 0
    
    for p in range(len(meta.mainposes_track)):
        trk_idx = int(meta.mainposes_track[p])
        num_inbtw = int(meta.mainposes_num_inbtw[p])
        
        weight = float(tracks[trk_idx]) if (0 <= trk_idx < M) else 0.0
        
        if num_inbtw <= 0:
            continue
        
        inbetween_weights[out_idx:out_idx + num_inbtw] = 0.0
        
        end_idx = num_inbtw - 1
        first_weight = float(meta.mainposes_inbtw[weight_idx]) if num_inbtw > 0 else 0.0
        last_weight = float(meta.mainposes_inbtw[weight_idx + end_idx]) if num_inbtw > 0 else 1.0
        
        if weight < WEIGHT_THRESHOLD:
            pass  # All zeros
        elif num_inbtw == 1:
            inbetween_weights[out_idx] = weight
        elif weight <= first_weight:
            scope = float(meta.inbtw_scope_multipliers[scope_idx])
            inbetween_weights[out_idx] = weight * scope
        elif weight >= last_weight:
            inbetween_weights[out_idx + end_idx] = 1.0
        else:
            # interpolate between two in-betweens
            real_end = 1
            while real_end < num_inbtw and float(meta.mainposes_inbtw[weight_idx + real_end]) <= weight:
                real_end += 1
            
            start = real_end - 1
            scope = float(meta.inbtw_scope_multipliers[scope_idx + (real_end - 1)])
            threshold_start = float(meta.mainposes_inbtw[weight_idx + start])
            
            ending_weight = (weight - threshold_start) * scope
            starting_weight = 1.0 - ending_weight
            
            inbetween_weights[out_idx + start] = starting_weight
            if out_idx + real_end < out_idx + num_inbtw:
                inbetween_weights[out_idx + real_end] = ending_weight
        
        out_idx += num_inbtw
        weight_idx += num_inbtw
        scope_idx += max(0, num_inbtw - 1)
    
    return inbetween_weights

def calculate_corrective_weights(
    meta,
    tracks: np.ndarray,
    inbetween_weights: np.ndarray,
    num_correctives: int,
    lod: int = 0
) -> np.ndarray:
    """Calculate corrective pose weights
    
    Args:
        meta: Face metadata with corrective_* arrays
        tracks: Current track weights
        inbetween_weights: Calculated in-between weights
        num_correctives: Total corrective poses
        lod: Current level of detail
    
    Returns:
        Array of corrective weights
    """
    M = tracks.shape[0]
    correctives = np.ones(num_correctives, dtype=np.float64)
    
    for gc in meta.global_corrective_entries:
        ci = int(gc.get("Index", -1))
        trk_raw = int(gc.get("Track", 0))
        unk = int(gc.get("Unknown", 0))
        
        trk = ((trk_raw << 4) | unk) >> 4
        corr_lod = unk & 0x000F
        
        if not (0 <= ci < num_correctives):
            continue
        
        if corr_lod > lod:
            correctives[ci] = 0.0
            continue
        
        if 0 <= trk < M:
            w = float(tracks[trk])
            if w <= 0.0:
                correctives[ci] = 0.0
            else:
                correctives[ci] *= min(1.0, w)
    
    for gc in meta.inbetween_corrective_entries:
        ci = int(gc.get("Index", -1))
        trk_raw = int(gc.get("Track", 0))
        unk = int(gc.get("Unknown", 0))
        
        trk = ((trk_raw << 4) | unk) >> 4
        corr_lod = unk & 0x000F
        
        if not (0 <= ci < num_correctives):
            continue
        
        if corr_lod > lod:
            correctives[ci] = 0.0
            continue
        
        if 0 <= trk < len(inbetween_weights):
            w = float(inbetween_weights[trk])
            if w <= 0.0:
                correctives[ci] = 0.0
            else:
                correctives[ci] *= min(1.0, w)
    
    idx = 0
    for entry in meta.corrective_influenced_poses:
        corr_idx = int(entry.get("Index", -1))
        num_influences = int(entry.get("NumInfluences", 0))
        flags = int(entry.get("Type", 0))
        
        if not (0 <= corr_idx < num_correctives):
            idx += num_influences
            continue
        
        current_weight = correctives[corr_idx]
        if current_weight <= WEIGHT_THRESHOLD:
            idx += num_influences
            continue
        
        influence_sum = 0.0
        for j in range(num_influences):
            inf_idx = int(meta.corrective_influence_indices[idx + j])
            if 0 <= inf_idx < num_correctives:
                influence_sum += correctives[inf_idx]
        idx += num_influences
        
        influence_by_speed = (flags & CORRECTIVE_INFLUENCE_BY_SPEED) != 0
        linear_correction = (flags & CORRECTIVE_INFLUENCE_LINEAR_CORRECTION) != 0
        
        if linear_correction:
            opposite = 1.0 - influence_sum
            current_weight *= opposite
            if influence_by_speed:
                current_weight *= opposite
        else:
            if influence_sum >= 1.0:
                current_weight = 0.0
            elif not influence_by_speed:
                max_allowed = 1.0 - influence_sum
                if max_allowed < current_weight:
                    current_weight = max_allowed
            elif influence_by_speed:
                current_weight *= 1.0 - (influence_sum * influence_sum)
        
        correctives[corr_idx] = max(0.0, min(1.0, current_weight))
    
    return correctives

def calculate_wrinkle_weights(
    meta,
    tracks: np.ndarray,
    wrinkle_start_idx: int
) -> None:
    """Calculate wrinkle output tracks

    Args:
        meta: Face metadata with wrinkle_mapping
        tracks: Track array (modified in-place)
        wrinkle_start_idx: Starting index for wrinkle tracks
    """
    M = tracks.shape[0]
    wrinkle_mapping = meta.wrinkle_mapping
    
    for i in range(len(wrinkle_mapping)):
        main_idx = int(wrinkle_mapping[i])
        wrinkle_idx = wrinkle_start_idx + i
        
        if 0 <= main_idx < M and wrinkle_idx < M:
            tracks[wrinkle_idx] = wrinkle_weight(tracks[main_idx])

def solve_tracks_face(
    setup,
    rig_info,
    tracks_in: np.ndarray
) -> dict:
    """Main facial track solver

    Args:
        setup: FacialSetup with face_meta and pose banks
        rig_info: Rig skeleton info
        tracks_in: Input track array (not modified)
    
    Returns:
        Dict with:
            - tracks: Solved track weights (M,)
            - inbetween_weights: In-between pose weights (P,)
            - corrective_weights: Corrective pose weights (C,)
    """
    face = setup.face_meta
    name_map = build_track_name_map(rig_info)
    
    tracks = np.array(tracks_in, dtype=np.float64, copy=True)
    M = tracks.shape[0]
    
    # Read envelope track values
    def get_track(name: str, lo: float, hi: float, default: float = 0.0) -> float:
        idx = safe_track_index(name_map, name)
        val = float(tracks[idx]) if idx >= 0 else default
        return float(clamp(val, lo, hi))
    
    lipsync_envelope = get_track("lipSyncEnvelope", 0.0, 1.0)
    upper_face = get_track("upperFace", 0.0, 2.0)
    lower_face = get_track("lowerFace", 0.0, 2.0)
    jaw_mult = get_track("jaliJaw", 0.0, 2.0)
    lips_mult = get_track("jaliLips", 0.0, 2.0)
    muzzle_lips = get_track("muzzleLips", 0.0, 1.0)
    muzzle_eyes = get_track("muzzleEyes", 0.0, 1.0)
    muzzle_brows = get_track("muzzleBrows", 0.0, 1.0)
    muzzle_dirs = get_track("muzzleEyeDirections", 0.0, 1.0)
    
    # Build arrays
    muzzles = np.array([1.0, 1.0, 1.0 - muzzle_eyes, 1.0 - muzzle_brows, 1.0 - muzzle_dirs, 1.0])
    envelopes = np.array([jaw_mult, lips_mult, 1.0, 1.0, 1.0, 1.0])
    face_part_weights = np.array([1.0, upper_face, lower_face])
    
    in_tracks = tracks.copy()
    
    apply_envelope_weights(face, muzzles, tracks, lod=0, lod_weight=0.0)
    
    if lipsync_envelope > 0.0:
        apply_global_limits(face, envelopes, muzzle_lips, tracks)
    
    apply_influences(face, tracks)
    
    apply_upper_lower_face_envelopes(face, face_part_weights, tracks)
    
    if hasattr(face, 'lipsync_overrides_mapping'):
        apply_lipsync_overrides(face, lipsync_envelope, in_tracks, tracks)
    
    if hasattr(face, 'lipsync_pose_sides'):
        apply_lipsync_poses(face, in_tracks, tracks)
    
    apply_influences(face, tracks)
    
    inbetween_weights = calculate_inbetween_weights(face, tracks)
    
    num_correctives = setup.face_corrective_bank.q.shape[0]
    corrective_weights = calculate_corrective_weights(
        face, tracks, inbetween_weights, num_correctives, lod=0
    )
    
    if hasattr(face, 'wrinkle_mapping') and hasattr(face, 'wrinkle_starting_index'):
        wrinkle_start = int(face.wrinkle_starting_index)
        calculate_wrinkle_weights(face, tracks, wrinkle_start)
    
    return {
        "tracks": tracks.astype(np.float32, copy=False),
        "inbetween_weights": inbetween_weights.astype(np.float32, copy=False),
        "corrective_weights": corrective_weights.astype(np.float32, copy=False),
    }

def build_tracks_from_armature(obj, rig) -> np.ndarray:
    """Build track array from Blender armature custom properties
    
    Args:
        obj: Blender armature object (or None to auto-detect)
        rig: Rig info with track_names
    
    Returns:
        NumPy array of track values
    """
    names = [normalize_track_name(n) for n in list(getattr(rig, "track_names", []) or [])]
    out = np.zeros((len(names),), dtype=np.float32)

    # Auto-detect armature if not provided
    if obj is None or getattr(obj, 'type', '') != 'ARMATURE':
        ctx = bpy.context
        obj = getattr(ctx, 'active_object', None)
        if obj is None or getattr(obj, 'type', '') != 'ARMATURE':
            return out
    
    # Read custom properties
    for i, name in enumerate(names):
        if not name:
            continue
        try:
            if name in obj.keys():
                out[i] = float(obj.get(name, 0.0))
            else:
                # Try to get UI default
                try:
                    ui = obj.id_properties_ui(name)
                    if hasattr(ui, 'as_dict'):
                        d = ui.as_dict()
                        dv = d.get('default') if isinstance(d, dict) else None
                        if dv is not None:
                            out[i] = float(dv)
                except Exception:
                    pass
        except Exception:
            out[i] = 0.0
    
    return out