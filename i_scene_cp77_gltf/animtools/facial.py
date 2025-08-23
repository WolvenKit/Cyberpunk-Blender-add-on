from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np
from .tracksolvers import (
    build_tracks_from_armature,
    solve_tracks_face,  # keep public name
)
@dataclass
class _RigMinimal:
    num_bones: int
    parent_indices: np.ndarray
    bone_names: list
    track_names: list
    ls_q: np.ndarray
    ls_t: np.ndarray
    ls_s: np.ndarray

def load_wkit_rig_skeleton(path: str | Path):
    p = Path(path)
    data = json.loads(p.read_text())
    root = data["Data"]["RootChunk"]

    bone_names = [e.get("$value", "") for e in root.get("boneNames", [])]
    parent_indices = np.asarray(root.get("boneParentIndexes", []), dtype=np.int16)
    track_names = [e.get("$value", "") for e in root.get("trackNames", [])]

    trs = root.get("boneTransforms", [])
    N = len(bone_names)
    q = np.zeros((N, 4), dtype=np.float32); q[:, 3] = 1.0
    t = np.zeros((N, 3), dtype=np.float32)
    s = np.ones((N, 3), dtype=np.float32)
    for i, tr in enumerate(trs[:N]):
        r = tr.get("Rotation", {})
        q[i] = [float(r.get("i", 0.0)), float(r.get("j", 0.0)), float(r.get("k", 0.0)), float(r.get("r", 1.0))]
        tt = tr.get("Translation", {})
        t[i] = [float(tt.get("X", 0.0)), float(tt.get("Y", 0.0)), float(tt.get("Z", 0.0))]
        sc = tr.get("Scale", {})
        s[i] = [float(sc.get("X", 1.0)), float(sc.get("Y", 1.0)), float(sc.get("Z", 1.0))]
    return _RigMinimal(len(bone_names), parent_indices, bone_names, track_names, q, t, s)

def _np_int(arr, dtype=np.int16):
    return np.asarray(arr, dtype=dtype)

def load_wkit_facialsetup(path: str | Path, rig_info) -> "FacialSetupAll":
    p = Path(path)
    data = json.loads(p.read_text())
    root = data["Data"]["RootChunk"]

    baked = root["bakedData"]["Data"]["Face"]
    main_face = root["mainPosesData"]["Data"]["Face"]
    corr_face = root["correctivePosesData"]["Data"]["Face"]

    class FaceMeta:
        pass

    face_meta = FaceMeta()
    env = baked.get("EnvelopesPerTrackMapping", [])
    setattr(face_meta, "envelopes_track", _np_int([e.get("Track", 0) for e in env]))
    setattr(face_meta, "envelopes_type", _np_int([e.get("Envelope", 0) for e in env], np.int8))

    gl = baked.get("GlobalLimits", [])
    setattr(face_meta, "global_limits_track", _np_int([e.get("Track", 0) for e in gl]))
    setattr(face_meta, "global_limits_min", np.asarray([e.get("Min", 0.0) for e in gl], dtype=np.float32))
    setattr(face_meta, "global_limits_mid", np.asarray([e.get("Mid", 0.0) for e in gl], dtype=np.float32))
    setattr(face_meta, "global_limits_max", np.asarray([e.get("Max", 0.0) for e in gl], dtype=np.float32))
    setattr(face_meta, "global_limits_type", _np_int([e.get("Type", 0) for e in gl], np.int8))

    infl = baked.get("InfluencedPoses", [])
    setattr(face_meta, "influenced_poses_track", _np_int([e.get("Track", 0) for e in infl]))
    setattr(face_meta, "influenced_poses_num", _np_int([e.get("NumInfluences", 0) for e in infl], np.int8))
    setattr(face_meta, "influenced_poses_type", _np_int([e.get("Type", 0) for e in infl], np.int8))
    setattr(face_meta, "influence_indices", _np_int(baked.get("InfluenceIndices", [])))

    ul = baked.get("UpperLowerFace", [])
    setattr(face_meta, "upper_lower_track", _np_int([e.get("Track", 0) for e in ul]))
    setattr(face_meta, "upper_lower_part", _np_int([e.get("Part", 0) for e in ul], np.int8))

    mp = baked.get("AllMainPoses", [])
    setattr(face_meta, "mainposes_track", _np_int([e.get("Track", 0) for e in mp]))
    setattr(face_meta, "mainposes_num_inbtw", _np_int([e.get("NumInbetweens", 0) for e in mp]))
    setattr(face_meta, "mainposes_inbtw", _np_int(baked.get("AllMainPosesInbetweens", [])))
    setattr(face_meta, "inbtw_scope_multipliers", np.asarray(baked.get("AllMainPosesInbetweenScopeMultipliers", []), dtype=np.float32))

    setattr(face_meta, "global_corrective_entries", baked.get("GlobalCorrectiveEntries", []))
    setattr(face_meta, "inbetween_corrective_entries", baked.get("InbetweenCorrectiveEntries", []))
    setattr(face_meta, "corrective_influenced_poses", baked.get("CorrectiveInfluencedPoses", []))
    setattr(face_meta, "corrective_influence_indices", _np_int(baked.get("CorrectiveInfluenceIndices", [])))

    def _q_identity(n: int):
        q = np.zeros((n, 4), dtype=np.float32); q[:, 3] = 1.0; return q

    def _s_identity(n: int):
        return np.ones((n, 3), dtype=np.float32)

    def _build_bank(num_bones: int, poses_desc: list, transforms: list):
        P = len(poses_desc)
        q = np.tile(_q_identity(num_bones), (P, 1, 1))
        t = np.zeros((P, num_bones, 3), dtype=np.float32)
        s = np.tile(_s_identity(num_bones), (P, 1, 1))
        for p_idx, pose in enumerate(poses_desc):
            start = int(pose.get("TransformIdx", 0)); count = int(pose.get("NumTransforms", 0))
            for rec in transforms[start:start+count]:
                b = int(rec.get("Bone", -1))
                if b < 0 or b >= num_bones:
                    continue
                rot = rec.get("Rotation", {}); trn = rec.get("Translation", {})
                q[p_idx, b, :] = [float(rot.get("i", 0.0)), float(rot.get("j", 0.0)), float(rot.get("k", 0.0)), float(rot.get("r", 1.0))]
                t[p_idx, b, :] = [float(trn.get("X", 0.0)), float(trn.get("Y", 0.0)), float(trn.get("Z", 0.0))]
        return type("Bank", (), {"q": q, "t": t, "s": s})()

    fb_main = _build_bank(rig_info.num_bones, main_face["Poses"], main_face["Transforms"])  # type: ignore[attr-defined]
    fb_corr = _build_bank(rig_info.num_bones, corr_face["Poses"], corr_face["Transforms"])  # type: ignore[attr-defined]

    return type("FacialSetupAll", (), {"face_meta": face_meta, "face_main_bank": fb_main, "face_corrective_bank": fb_corr})()

