from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _indices(values) -> np.ndarray:
    return np.ascontiguousarray(values, dtype=np.intp)


def _float32(values) -> np.ndarray:
    return np.ascontiguousarray(values, dtype=np.float32)


def _uint8(values) -> np.ndarray:
    return np.ascontiguousarray(values, dtype=np.uint8)


@dataclass
class CompiledPoseArrays:
    num_poses: int
    row_ptr: np.ndarray
    bones: np.ndarray
    quats: np.ndarray
    trans: np.ndarray
    max_width: int
    current_quats: np.ndarray
    full_quats: np.ndarray
    blend_quats: np.ndarray
    current_trans: np.ndarray
    delta_trans: np.ndarray
    dot: np.ndarray
    norm: np.ndarray
    sign: np.ndarray
    valid: np.ndarray
    negative: np.ndarray
    safe_norm: np.ndarray


@dataclass
class CompiledFacialPart:
    part_name: str
    env_num: int
    env_tracks: np.ndarray
    env_lods: np.ndarray
    env_types: np.ndarray
    env_weights: np.ndarray
    env_factors: np.ndarray
    env_threshold_mask: np.ndarray
    muzzle_values: np.ndarray
    env_equal: tuple[np.ndarray, ...]
    env_below: tuple[np.ndarray, ...]
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
    ulf_tracks: np.ndarray
    ulf_parts: np.ndarray
    ulf_values: np.ndarray
    ulf_mults: np.ndarray
    ulf_current: np.ndarray
    lps_tracks: np.ndarray
    lps_out_indices: np.ndarray
    lps_weights: np.ndarray
    lps_current: np.ndarray
    num_main_poses: int
    num_ib_poses: int
    main_tracks: np.ndarray
    ib_row_ptr: np.ndarray
    ib_thresholds: np.ndarray
    sm_row_ptr: np.ndarray
    ib_scope_mults: np.ndarray
    ib_weights: np.ndarray
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
    corr_weights: np.ndarray
    main_poses: CompiledPoseArrays
    corrective_poses: CompiledPoseArrays
    wrinkle_count: int
    wrinkle_start_track: int
    wrinkle_source_tracks: np.ndarray
    wrinkle_buffer: np.ndarray


@dataclass
class CompiledFacialRuntime:
    setup: object
    segments: object
    num_bones: int
    num_tracks: int
    parts: tuple[CompiledFacialPart, ...]
    lipsync_override_map: np.ndarray
    input_tracks: np.ndarray
    output_tracks: np.ndarray
    bone_quats: np.ndarray
    bone_trans: np.ndarray
    output_indices: np.ndarray

    def reset(self) -> None:
        np.copyto(self.output_tracks, self.input_tracks)
        self.bone_quats.fill(0.0)
        self.bone_quats[:, 3] = 1.0
        self.bone_trans.fill(0.0)


def _compile_pose_arrays(source) -> CompiledPoseArrays:
    row_ptr = _indices(source.row_ptr)
    bones = _indices(source.pose_bones)
    quats = _float32(source.pose_quats)
    trans = _float32(source.pose_trans)
    widths = np.diff(row_ptr)
    max_width = int(widths.max(initial=0))
    size = max(1, max_width)
    return CompiledPoseArrays(
        num_poses=int(source.num_poses),
        row_ptr=row_ptr,
        bones=bones,
        quats=quats,
        trans=trans,
        max_width=max_width,
        current_quats=np.empty((size, 4), dtype=np.float32),
        full_quats=np.empty((size, 4), dtype=np.float32),
        blend_quats=np.empty((size, 4), dtype=np.float32),
        current_trans=np.empty((size, 3), dtype=np.float32),
        delta_trans=np.empty((size, 3), dtype=np.float32),
        dot=np.empty(size, dtype=np.float32),
        norm=np.empty(size, dtype=np.float32),
        sign=np.empty(size, dtype=np.float32),
        valid=np.empty(size, dtype=bool),
        negative=np.empty(size, dtype=bool),
        safe_norm=np.empty(size, dtype=np.float32),
    )


def _compile_part(source, segments) -> CompiledFacialPart:
    env_tracks = _indices(source.env_tracks)
    env_lods = _uint8(source.env_lods)
    lps_tracks = _indices(source.lps_tracks)
    lps_out_indices = lps_tracks - int(segments.envelope_end) + int(segments.lipsync_out_start)
    lod_count = max(3, int(env_lods.max(initial=0)) + 1)
    env_equal = tuple(np.flatnonzero(env_lods == lod) for lod in range(lod_count))
    env_below = tuple(np.flatnonzero(env_lods < lod) for lod in range(lod_count))
    return CompiledFacialPart(
        part_name=str(source.part_name),
        env_num=int(source.env_num),
        env_tracks=env_tracks,
        env_lods=env_lods,
        env_types=_indices(source.env_types),
        env_weights=np.empty(len(env_tracks), dtype=np.float32),
        env_factors=np.empty(len(env_tracks), dtype=np.float32),
        env_threshold_mask=np.empty(len(env_tracks), dtype=bool),
        muzzle_values=np.ones(6, dtype=np.float32),
        env_equal=env_equal,
        env_below=env_below,
        limit_num=int(source.limit_num),
        limit_tracks=_indices(source.limit_tracks),
        limit_envelope=_indices(source.limit_envelope),
        limit_min=_float32(source.limit_min),
        limit_mid=_float32(source.limit_mid),
        limit_max=_float32(source.limit_max),
        infl_num=int(source.infl_num),
        infl_tracks=_indices(source.infl_tracks),
        infl_types=_uint8(source.infl_types),
        infl_row_ptr=_indices(source.infl_row_ptr),
        infl_indices=_indices(source.infl_indices),
        ulf_tracks=_indices(source.ulf_tracks),
        ulf_parts=_indices(source.ulf_parts),
        ulf_values=np.empty(3, dtype=np.float32),
        ulf_mults=np.empty(int(source.ulf_num), dtype=np.float32),
        ulf_current=np.empty(int(source.ulf_num), dtype=np.float32),
        lps_tracks=lps_tracks,
        lps_out_indices=_indices(lps_out_indices),
        lps_weights=np.empty(int(source.lps_num), dtype=np.float32),
        lps_current=np.empty(int(source.lps_num), dtype=np.float32),
        num_main_poses=int(source.num_main_poses),
        num_ib_poses=int(source.num_ib_poses),
        main_tracks=_indices(source.main_tracks),
        ib_row_ptr=_indices(source.ib_row_ptr),
        ib_thresholds=_float32(source.ib_thresholds),
        sm_row_ptr=_indices(source.sm_row_ptr),
        ib_scope_mults=_float32(source.ib_scope_mults),
        ib_weights=np.zeros(int(source.num_ib_poses), dtype=np.float32),
        num_correctives=int(source.num_correctives),
        gcorr_row_ptr=_indices(source.gcorr_row_ptr),
        gcorr_tracks=_indices(source.gcorr_tracks),
        gcorr_flags=_uint8(source.gcorr_flags),
        icorr_row_ptr=_indices(source.icorr_row_ptr),
        icorr_tracks=_indices(source.icorr_tracks),
        icorr_flags=_uint8(source.icorr_flags),
        num_corr_infl=int(source.num_corr_infl),
        corr_infl_pose_idx=_indices(source.corr_infl_pose_idx),
        corr_infl_types=_uint8(source.corr_infl_types),
        corr_infl_row_ptr=_indices(source.corr_infl_row_ptr),
        corr_infl_influencers=_indices(source.corr_infl_influencers),
        corr_weights=np.empty(int(source.num_correctives), dtype=np.float32),
        main_poses=_compile_pose_arrays(source.main_poses),
        corrective_poses=_compile_pose_arrays(source.corrective_poses),
        wrinkle_count=int(source.wrinkle_count),
        wrinkle_start_track=int(source.wrinkle_start_track),
        wrinkle_source_tracks=_indices(source.wrinkle_source_tracks),
        wrinkle_buffer=np.empty(int(source.wrinkle_count), dtype=np.float32),
    )


def compile_runtime(setup, rig, segments) -> CompiledFacialRuntime:
    num_bones = int(rig.num_bones)
    num_tracks = int(rig.num_tracks)
    parts = tuple(
        _compile_part(part, segments)
        for part in (setup.tongue, setup.eyes, setup.face)
    )
    output_indices = np.concatenate((
        np.arange(segments.lipsync_out_start, segments.lipsync_out_end, dtype=np.intp),
        np.arange(segments.wrinkle_start, segments.wrinkle_end, dtype=np.intp),
    ))
    runtime = CompiledFacialRuntime(
        setup=setup,
        segments=segments,
        num_bones=num_bones,
        num_tracks=num_tracks,
        parts=parts,
        lipsync_override_map=_indices(setup.lipsync_override_idx_map),
        input_tracks=np.empty(num_tracks, dtype=np.float32),
        output_tracks=np.empty(num_tracks, dtype=np.float32),
        bone_quats=np.empty((num_bones, 4), dtype=np.float32),
        bone_trans=np.empty((num_bones, 3), dtype=np.float32),
        output_indices=output_indices,
    )
    runtime.reset()
    return runtime
