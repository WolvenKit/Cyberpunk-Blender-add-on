from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TrackSegments:
    num_tracks: int
    envelope_start: int
    envelope_end: int
    main_start: int
    main_end: int
    lipsync_ovr_start: int
    lipsync_ovr_end: int
    lipsync_out_start: int
    lipsync_out_end: int
    wrinkle_start: int
    wrinkle_end: int

    @classmethod
    def from_setup(cls, setup, num_tracks: int) -> TrackSegments:
        envelope_end = int(setup.num_envelope_tracks)
        main_start = envelope_end
        main_end = main_start + int(setup.num_main_poses)
        lipsync_ovr_start = main_end
        lipsync_ovr_end = lipsync_ovr_start + int(setup.num_lipsync_overrides)
        lipsync_out_start = lipsync_ovr_end
        lipsync_out_end = lipsync_out_start + int(setup.num_main_poses)
        wrinkle_start = lipsync_out_end
        wrinkle_end = wrinkle_start + int(setup.num_wrinkle_tracks)
        if wrinkle_end > num_tracks:
            raise ValueError(
                f"Facial setup requires {wrinkle_end} tracks, but the rig provides {num_tracks}"
            )
        return cls(
            num_tracks=num_tracks,
            envelope_start=0,
            envelope_end=envelope_end,
            main_start=main_start,
            main_end=main_end,
            lipsync_ovr_start=lipsync_ovr_start,
            lipsync_ovr_end=lipsync_ovr_end,
            lipsync_out_start=lipsync_out_start,
            lipsync_out_end=lipsync_out_end,
            wrinkle_start=wrinkle_start,
            wrinkle_end=wrinkle_end,
        )

    def is_input(self, track_index: int) -> bool:
        return (
            self.envelope_start <= track_index < self.envelope_end
            or self.main_start <= track_index < self.main_end
            or self.lipsync_ovr_start <= track_index < self.lipsync_ovr_end
        )

    def is_output(self, track_index: int) -> bool:
        return (
            self.lipsync_out_start <= track_index < self.lipsync_out_end
            or self.wrinkle_start <= track_index < self.wrinkle_end
        )


@dataclass
class PoseArrays:
    num_poses: int
    row_ptr: np.ndarray
    pose_bones: np.ndarray
    pose_quats: np.ndarray
    pose_trans: np.ndarray
    # Per-pose transform counts used at LOD 1 and LOD 2 (Sermo applies only the
    # first N transforms of each pose there). None means "all transforms".
    lod1_counts: np.ndarray | None = None
    lod2_counts: np.ndarray | None = None


@dataclass
class FacialPartData:
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
    face: FacialPartData
    eyes: FacialPartData
    tongue: FacialPartData

    used_bone_indices: np.ndarray
    lipsync_override_idx_map: np.ndarray
    joint_regions: np.ndarray

    num_envelope_tracks: int
    num_lipsync_overrides: int
    num_main_poses: int
    num_wrinkle_tracks: int
