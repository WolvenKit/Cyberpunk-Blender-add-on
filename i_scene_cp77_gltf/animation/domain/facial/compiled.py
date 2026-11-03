from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .validation import validate_setup


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
    # Transforms applied per pose at LOD 0, 1 and 2.
    lod_widths: tuple[np.ndarray, np.ndarray, np.ndarray]
    # quats * sign(q.w): nlerp toward c*q picks this hemisphere for unit c.
    signed_quats: np.ndarray
    # Poses whose rotations stay clear of q.w ~ 0, where the hemisphere shortcut holds.
    sign_safe: np.ndarray
    # First index of this pose set in CompiledFacialRuntime.pose_table.
    pose_offset: int = 0


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
    # Corrective parents flattened per corrective: global parents, then inbetween parents.
    corr_parent_index: np.ndarray
    corr_parent_is_ib: np.ndarray
    corr_parent_flags: np.ndarray
    corr_parent_owner: np.ndarray
    corr_parent_starts: np.ndarray
    corr_has_parents: np.ndarray
    corr_flagged_by_lod: dict


@dataclass
class PoseTable:
    """Every pose transform of the setup, sorted once by bone and application order"""

    num_poses: int
    bones: np.ndarray  # per sorted row
    quats: np.ndarray
    signed_quats: np.ndarray
    trans: np.ndarray
    pose: np.ndarray  # global pose id of each sorted row
    local: np.ndarray  # index of the row within its pose (for LOD truncation)
    lod_widths: tuple[np.ndarray, np.ndarray, np.ndarray]  # per global pose
    sign_safe: np.ndarray  # per global pose
    weights: np.ndarray  # per-frame scratch: blend weight of every global pose


def _compile_pose_table(pose_sets) -> PoseTable:
    offset = 0
    pose_ids, locals_ = [], []
    for poses in pose_sets:
        poses.pose_offset = offset
        widths = np.diff(poses.row_ptr)
        pose_ids.append(np.repeat(np.arange(poses.num_poses) + offset, widths))
        locals_.append(
            np.arange(int(poses.row_ptr[-1])) - np.repeat(poses.row_ptr[:-1], widths)
        )
        offset += poses.num_poses

    def cat(name):
        return np.concatenate([getattr(p, name) for p in pose_sets])

    bones = cat("bones")
    order = np.lexsort(
        (np.arange(len(bones)), bones)
    )  # by bone, then application order
    return PoseTable(
        num_poses=offset,
        bones=bones[order],
        quats=cat("quats")[order],
        signed_quats=cat("signed_quats")[order],
        trans=cat("trans")[order],
        pose=np.ascontiguousarray(np.concatenate(pose_ids), dtype=np.intp)[order],
        local=np.ascontiguousarray(np.concatenate(locals_), dtype=np.intp)[order],
        lod_widths=tuple(
            np.concatenate([p.lod_widths[i] for p in pose_sets]) for i in range(3)
        ),
        sign_safe=cat("sign_safe"),
        weights=np.zeros(offset, dtype=np.float32),
    )


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
    # Bones that received a partial-weight blend this frame; normalized once at the end.
    partial_bones: np.ndarray
    pose_table: PoseTable

    def reset(self) -> None:
        np.copyto(self.output_tracks, self.input_tracks)
        self.bone_quats.fill(0.0)
        self.bone_quats[:, 3] = 1.0
        self.bone_trans.fill(0.0)
        self.partial_bones.fill(False)


def _lod_widths(source, widths) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    result = [widths]
    for name in ("lod1_counts", "lod2_counts"):
        counts = getattr(source, name, None)
        result.append(
            widths
            if counts is None
            else np.ascontiguousarray(np.minimum(counts, widths), dtype=np.intp)
        )
    return tuple(result)


def _compile_pose_arrays(source) -> CompiledPoseArrays:
    row_ptr = np.ascontiguousarray(source.row_ptr, dtype=np.intp)
    bones = np.ascontiguousarray(source.pose_bones, dtype=np.intp)
    quats = np.ascontiguousarray(source.pose_quats, dtype=np.float32)
    trans = np.ascontiguousarray(source.pose_trans, dtype=np.float32)
    widths = np.diff(row_ptr)
    max_width = int(widths.max(initial=0))
    size = max(1, max_width)
    sign = np.where(quats[:, 3] < 0.0, -1.0, 1.0).astype(np.float32)
    row_pose = np.repeat(np.arange(int(source.num_poses)), widths)
    sign_safe = np.ones(int(source.num_poses), dtype=bool)
    sign_safe[np.unique(row_pose[np.abs(quats[:, 3]) < 1e-3])] = False
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
        lod_widths=_lod_widths(source, widths),
        signed_quats=quats * sign[:, None],
        sign_safe=sign_safe,
    )


def _compile_corrective_parents(source) -> dict:
    index, is_ib, flags, starts = [], [], [], []
    for corrective in range(int(source.num_correctives)):
        starts.append(len(index))
        for row_ptr, tracks, part_flags, inbetween in (
            (source.gcorr_row_ptr, source.gcorr_tracks, source.gcorr_flags, False),
            (source.icorr_row_ptr, source.icorr_tracks, source.icorr_flags, True),
        ):
            start, end = int(row_ptr[corrective]), int(row_ptr[corrective + 1])
            index.extend(int(value) for value in tracks[start:end])
            flags.extend(int(value) for value in part_flags[start:end])
            is_ib.extend([inbetween] * (end - start))
    starts = np.asarray(starts, dtype=np.intp)
    counts = np.diff(np.append(starts, len(index)))
    return dict(
        corr_parent_index=np.asarray(index, dtype=np.intp),
        corr_parent_is_ib=np.asarray(is_ib, dtype=bool),
        corr_parent_flags=np.asarray(flags, dtype=np.intp),
        corr_parent_owner=np.repeat(np.arange(len(starts)), counts),
        corr_parent_starts=starts,
        corr_has_parents=counts > 0,
        corr_flagged_by_lod={},
    )


def _compile_part(source, segments) -> CompiledFacialPart:
    env_tracks = np.ascontiguousarray(source.env_tracks, dtype=np.intp)
    env_lods = np.ascontiguousarray(source.env_lods, dtype=np.uint8)
    lps_tracks = np.ascontiguousarray(source.lps_tracks, dtype=np.intp)
    lps_out_indices = (
        lps_tracks - int(segments.envelope_end) + int(segments.lipsync_out_start)
    )
    lod_count = max(3, int(env_lods.max(initial=0)) + 1)
    env_equal = tuple(np.flatnonzero(env_lods == lod) for lod in range(lod_count))
    env_below = tuple(np.flatnonzero(env_lods < lod) for lod in range(lod_count))
    return CompiledFacialPart(
        part_name=str(source.part_name),
        env_num=int(source.env_num),
        env_tracks=env_tracks,
        env_lods=env_lods,
        env_types=np.ascontiguousarray(source.env_types, dtype=np.intp),
        env_weights=np.empty(len(env_tracks), dtype=np.float32),
        env_factors=np.empty(len(env_tracks), dtype=np.float32),
        env_threshold_mask=np.empty(len(env_tracks), dtype=bool),
        muzzle_values=np.ones(6, dtype=np.float32),
        env_equal=env_equal,
        env_below=env_below,
        limit_num=int(source.limit_num),
        limit_tracks=np.ascontiguousarray(source.limit_tracks, dtype=np.intp),
        limit_envelope=np.ascontiguousarray(source.limit_envelope, dtype=np.intp),
        limit_min=np.ascontiguousarray(source.limit_min, dtype=np.float32),
        limit_mid=np.ascontiguousarray(source.limit_mid, dtype=np.float32),
        limit_max=np.ascontiguousarray(source.limit_max, dtype=np.float32),
        infl_num=int(source.infl_num),
        infl_tracks=np.ascontiguousarray(source.infl_tracks, dtype=np.intp),
        infl_types=np.ascontiguousarray(source.infl_types, dtype=np.uint8),
        infl_row_ptr=np.ascontiguousarray(source.infl_row_ptr, dtype=np.intp),
        infl_indices=np.ascontiguousarray(source.infl_indices, dtype=np.intp),
        ulf_tracks=np.ascontiguousarray(source.ulf_tracks, dtype=np.intp),
        ulf_parts=np.ascontiguousarray(source.ulf_parts, dtype=np.intp),
        ulf_values=np.empty(3, dtype=np.float32),
        ulf_mults=np.empty(int(source.ulf_num), dtype=np.float32),
        ulf_current=np.empty(int(source.ulf_num), dtype=np.float32),
        lps_tracks=lps_tracks,
        lps_out_indices=np.ascontiguousarray(lps_out_indices, dtype=np.intp),
        lps_weights=np.empty(int(source.lps_num), dtype=np.float32),
        lps_current=np.empty(int(source.lps_num), dtype=np.float32),
        num_main_poses=int(source.num_main_poses),
        num_ib_poses=int(source.num_ib_poses),
        main_tracks=np.ascontiguousarray(source.main_tracks, dtype=np.intp),
        ib_row_ptr=np.ascontiguousarray(source.ib_row_ptr, dtype=np.intp),
        ib_thresholds=np.ascontiguousarray(source.ib_thresholds, dtype=np.float32),
        sm_row_ptr=np.ascontiguousarray(source.sm_row_ptr, dtype=np.intp),
        ib_scope_mults=np.ascontiguousarray(source.ib_scope_mults, dtype=np.float32),
        ib_weights=np.zeros(int(source.num_ib_poses), dtype=np.float32),
        num_correctives=int(source.num_correctives),
        gcorr_row_ptr=np.ascontiguousarray(source.gcorr_row_ptr, dtype=np.intp),
        gcorr_tracks=np.ascontiguousarray(source.gcorr_tracks, dtype=np.intp),
        gcorr_flags=np.ascontiguousarray(source.gcorr_flags, dtype=np.uint8),
        icorr_row_ptr=np.ascontiguousarray(source.icorr_row_ptr, dtype=np.intp),
        icorr_tracks=np.ascontiguousarray(source.icorr_tracks, dtype=np.intp),
        icorr_flags=np.ascontiguousarray(source.icorr_flags, dtype=np.uint8),
        num_corr_infl=int(source.num_corr_infl),
        corr_infl_pose_idx=np.ascontiguousarray(
            source.corr_infl_pose_idx, dtype=np.intp
        ),
        corr_infl_types=np.ascontiguousarray(source.corr_infl_types, dtype=np.uint8),
        corr_infl_row_ptr=np.ascontiguousarray(source.corr_infl_row_ptr, dtype=np.intp),
        corr_infl_influencers=np.ascontiguousarray(
            source.corr_infl_influencers, dtype=np.intp
        ),
        corr_weights=np.empty(int(source.num_correctives), dtype=np.float32),
        main_poses=_compile_pose_arrays(source.main_poses),
        corrective_poses=_compile_pose_arrays(source.corrective_poses),
        wrinkle_count=int(source.wrinkle_count),
        wrinkle_start_track=int(source.wrinkle_start_track),
        wrinkle_source_tracks=np.ascontiguousarray(
            source.wrinkle_source_tracks, dtype=np.intp
        ),
        wrinkle_buffer=np.empty(int(source.wrinkle_count), dtype=np.float32),
        **_compile_corrective_parents(source),
    )


def compile_runtime(setup, rig, segments) -> CompiledFacialRuntime:
    validate_setup(setup, rig, segments)
    num_bones = int(rig.num_bones)
    num_tracks = int(rig.num_tracks)
    parts = tuple(
        _compile_part(part, segments) for part in (setup.tongue, setup.eyes, setup.face)
    )
    output_indices = np.concatenate(
        (
            np.arange(
                segments.lipsync_out_start, segments.lipsync_out_end, dtype=np.intp
            ),
            np.arange(segments.wrinkle_start, segments.wrinkle_end, dtype=np.intp),
        )
    )
    runtime = CompiledFacialRuntime(
        setup=setup,
        segments=segments,
        num_bones=num_bones,
        num_tracks=num_tracks,
        parts=parts,
        lipsync_override_map=np.ascontiguousarray(
            setup.lipsync_override_idx_map, dtype=np.intp
        ),
        input_tracks=np.zeros(num_tracks, dtype=np.float32),
        output_tracks=np.empty(num_tracks, dtype=np.float32),
        bone_quats=np.empty((num_bones, 4), dtype=np.float32),
        bone_trans=np.empty((num_bones, 3), dtype=np.float32),
        output_indices=output_indices,
        partial_bones=np.zeros(num_bones, dtype=bool),
        pose_table=_compile_pose_table(
            [
                poses
                for part in parts
                for poses in (part.main_poses, part.corrective_poses)
            ]
        ),
    )
    runtime.reset()
    return runtime
