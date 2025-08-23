from __future__ import annotations
from typing import Dict, List, Any
import numpy as np
import bpy

def _clamp(x: float, lo: float, hi: float) -> float:
    return float(min(max(x, lo), hi))

def _lerp(t: float, a: float, b: float) -> float:
    return (1.0 - t) * a + (t * b)

def _normalize_track_name(x: Any) -> str:
    if isinstance(x, dict):
        return str(x.get("$value") or x.get("value") or "")
    return str(x)

def build_track_name_map(rig) -> Dict[str, int]:
    names = [
        _normalize_track_name(n)
        for n in list(getattr(rig, "track_names", []) or [])
    ]
    return {n: i for i, n in enumerate(names) if n}

def _ti(name_to_index: Dict[str, int], name: str) -> int:
    return int(name_to_index.get(name, -1))

def apply_global_slider_overrides_inplace(tracks: np.ndarray, rig) -> None:
    """UI can override this to modify `tracks` before solving (noop by default)."""
    return None

def apply_lipsync_overrides_inplace(setup, rig, tracks: np.ndarray) -> None:
    return None

def apply_lipsync_poses_inplace(setup, rig, tracks: np.ndarray) -> None:
    return None

def _iter_track_names(rig) -> List[str]:
    raw = list(getattr(rig, 'track_names', []) or [])
    out: List[str] = []
    for x in raw:
        out.append(_normalize_track_name(x))
    return out

def _get_prop_default(obj, name: str) -> float:
    try:
        ui = obj.id_properties_ui(name)
        if hasattr(ui, 'as_dict'):
            d = ui.as_dict()
            dv = d.get('default') if isinstance(d, dict) else None
            if dv is not None:
                return float(dv)
    except Exception:
        pass
    try:
        rna_ui = obj.get('_RNA_UI')
        if isinstance(rna_ui, dict) and name in rna_ui:
            dv = rna_ui[name].get('default')
            if dv is not None:
                return float(dv)
    except Exception:
        pass
    return 0.0

def _get_selected_armature():
    if bpy is None:
        return None
    ctx = bpy.context
    obj = getattr(ctx, 'active_object', None)
    if obj is not None and getattr(obj, 'type', '') == 'ARMATURE':
        return obj
    for o in list(getattr(ctx, 'selected_objects', []) or []):
        if getattr(o, 'type', '') == 'ARMATURE':
            return o
    return None

def build_tracks_from_armature(obj, rig) -> np.ndarray:
    """Return a float array using `RigData.track_names` and the selected Armature's custom props.
    If a property is missing, fall back to its UI default, else 0.0.
    """
    names = _iter_track_names(rig)
    out = np.zeros((len(names),), dtype=np.float32)

    if bpy is None:
        return out
    if obj is None or getattr(obj, 'type', '') != 'ARMATURE':
        obj = _get_selected_armature()
    if obj is None:
        return out

    for i, n in enumerate(names):
        if not n:
            continue
        try:
            if n in obj.keys():
                out[i] = float(obj.get(n, 0.0))
            else:
                out[i] = _get_prop_default(obj, n)
        except Exception:
            out[i] = 0.0
    return out

def solve_tracks_face(setup, rig_info, tracks_in: np.ndarray) -> dict:
    """Apply CP77-style facial track processing to a copy of `tracks_in` (Face).
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
        apply_global_slider_overrides_inplace(tracks, rig_info)  # type: ignore
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
# Simplified solver for sub-parts (eyes/tongue) – parity with face subset

def solve_tracks_part(meta, Pc: int, tracks_in: np.ndarray, name_to_index: Dict[str, int]) -> dict:
    tracks = np.array(tracks_in, dtype=np.float64, copy=True)
    M = tracks.shape[0]
    # 1) Envelopes
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
