import numpy as np

from ....bartmoss.arrays import validate_csr, validate_indices


def validate_setup(setup, rig, segments):
    tracks, bones = int(rig.num_tracks), int(rig.num_bones)
    if segments.envelope_end < 13 or min(tracks, bones) < 1:
        raise ValueError(
            "Facial rigs require bones and the complete envelope track block"
        )
    validate_indices(setup.used_bone_indices, bones, "used bones")
    validate_indices(setup.lipsync_override_idx_map, tracks, "override map")
    if len(setup.lipsync_override_idx_map) != setup.num_lipsync_overrides:
        raise ValueError("Lipsync override count does not match its mapping")
    for part in (setup.tongue, setup.eyes, setup.face):
        label = part.part_name
        for count, fields in (
            (part.env_num, ("env_tracks", "env_lods", "env_types")),
            (
                part.limit_num,
                (
                    "limit_tracks",
                    "limit_envelope",
                    "limit_min",
                    "limit_mid",
                    "limit_max",
                ),
            ),
            (part.infl_num, ("infl_tracks", "infl_types")),
            (part.ulf_num, ("ulf_tracks", "ulf_parts")),
            (part.lps_num, ("lps_tracks", "lps_sides")),
            (part.num_main_poses, ("main_tracks",)),
            (part.num_corr_infl, ("corr_infl_pose_idx", "corr_infl_types")),
            (part.wrinkle_count, ("wrinkle_source_tracks",)),
            (len(part.gcorr_tracks), ("gcorr_flags",)),
            (len(part.icorr_tracks), ("icorr_flags",)),
        ):
            for field in fields:
                values = np.asarray(getattr(part, field))
                if (
                    values.ndim != 1
                    or len(values) != count
                    or not np.isfinite(values).all()
                ):
                    raise ValueError(
                        label + "." + field + " has an invalid parallel array"
                    )
        for field in (
            "env_tracks",
            "limit_tracks",
            "infl_tracks",
            "infl_indices",
            "ulf_tracks",
            "lps_tracks",
            "main_tracks",
            "gcorr_tracks",
            "wrinkle_source_tracks",
        ):
            validate_indices(getattr(part, field), tracks, label + "." + field)
        validate_indices(part.env_types, 6, label + ".env_types")
        validate_indices(part.ulf_parts, 3, label + ".ulf_parts")
        validate_indices(
            part.corr_infl_pose_idx, part.num_correctives, label + ".correctives"
        )
        validate_indices(
            part.corr_infl_influencers, part.num_correctives, label + ".influencers"
        )
        for prefix, rows, values in (
            ("infl", part.infl_num, part.infl_indices),
            ("gcorr", part.num_correctives, part.gcorr_tracks),
            ("icorr", part.num_correctives, part.icorr_tracks),
            ("corr_infl", part.num_corr_infl, part.corr_infl_influencers),
            ("ib", part.num_main_poses, part.ib_thresholds),
            ("sm", part.num_main_poses, part.ib_scope_mults),
        ):
            validate_csr(
                getattr(part, prefix + "_row_ptr"),
                rows,
                len(values),
                label + "." + prefix,
            )
        if len(part.ib_thresholds) != part.num_ib_poses:
            raise ValueError(label + " inbetween pose count mismatch")
        if (
            not np.isfinite(part.ib_thresholds).all()
            or not np.isfinite(part.ib_scope_mults).all()
            or np.any(np.asarray(part.icorr_tracks) < 0)
        ):
            raise ValueError(label + " has invalid inbetween values")
        for start, end in zip(part.ib_row_ptr[:-1], part.ib_row_ptr[1:]):
            if np.any(np.diff(part.ib_thresholds[int(start) : int(end)]) < 0):
                raise ValueError(label + " inbetween thresholds must be ordered")
        for poses, count in (
            (part.main_poses, part.num_ib_poses),
            (part.corrective_poses, part.num_correctives),
        ):
            if poses.num_poses != count:
                raise ValueError(label + " pose count mismatch")
            validate_csr(poses.row_ptr, count, len(poses.pose_bones), label + ".poses")
            validate_indices(poses.pose_bones, bones, label + ".pose_bones")
            if (
                poses.pose_quats.shape != (len(poses.pose_bones), 4)
                or poses.pose_trans.shape != (len(poses.pose_bones), 3)
                or not np.isfinite(poses.pose_quats).all()
                or not np.isfinite(poses.pose_trans).all()
            ):
                raise ValueError(label + " has invalid pose transforms")
            widths = np.diff(np.asarray(poses.row_ptr))
            for lod_counts in (
                getattr(poses, "lod1_counts", None),
                getattr(poses, "lod2_counts", None),
            ):
                if lod_counts is not None and (
                    len(lod_counts) != count
                    or np.any(lod_counts < 0)
                    or np.any(lod_counts > widths)
                ):
                    raise ValueError(label + " has invalid per-LOD transform counts")
        output_indices = (
            np.asarray(part.lps_tracks)
            - segments.main_start
            + segments.lipsync_out_start
        )
        validate_indices(output_indices, tracks, label + ".lipsync outputs")
        if part.wrinkle_count and not (
            0 <= part.wrinkle_start_track
            and part.wrinkle_start_track + part.wrinkle_count <= tracks
        ):
            raise ValueError(label + " wrinkle output range is outside the rig tracks")
