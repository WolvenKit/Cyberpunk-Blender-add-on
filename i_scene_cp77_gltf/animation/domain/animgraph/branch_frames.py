from __future__ import annotations

from ....bartmoss.qs_transform import blend_qs
from ...model.animgraph.frames import BranchFrame, TrackSnapshot
from ..clip.additive import reference_or_identity_pose
from .ik import interpolate_ik_targets


def track_snapshots_equal(
    left: TrackSnapshot | None, right: TrackSnapshot, epsilon: float = 1e-6
) -> bool:
    return (
        left is not None
        and left.existed == right.existed
        and abs(left.value - right.value) <= epsilon
    )


def scope_signature(frame: BranchFrame):
    """The frame's transform and track stack scopes, comparable between branches"""
    return (
        tuple(
            (scope.tag, scope.names, scope.materialized)
            for scope in frame.transform_scopes
        ),
        tuple(
            (scope.tag, scope.names, scope.materialized) for scope in frame.track_scopes
        ),
    )


def identity_frame(input_frame: BranchFrame) -> BranchFrame:
    """input_frame's layout with identity transforms and zero tracks"""
    pose = {name: type(value).identity() for name, value in input_frame.pose.items()}
    tracks = {
        name: TrackSnapshot(snapshot.existed, 0.0)
        for name, snapshot in input_frame.tracks.items()
    }
    return BranchFrame(
        pose,
        tracks,
        input_frame.parent_map,
        input_frame.reference_pose,
        input_frame.reference_tracks,
        input_frame.transform_scopes,
        input_frame.track_scopes,
    )


def interpolate_frames(
    first: BranchFrame, second: BranchFrame, weight: float
) -> BranchFrame:
    """Blend two branch frames of one layout"""
    if scope_signature(first) != scope_signature(second):
        raise ValueError("Pose blend branches produce incompatible pose-stack scopes")
    if first.model_space != second.model_space:
        raise ValueError("Pose blend branches produce incompatible pose spaces")
    if (
        first.pose.keys() != second.pose.keys()
        or first.tracks.keys() != second.tracks.keys()
    ):
        raise ValueError(
            "Pose blend branches produce incompatible transform or track layouts"
        )
    if first.parent_map != second.parent_map:
        raise ValueError("Pose blend branches produce incompatible hierarchies")
    pose = {
        name: blend_qs(value, second.pose[name], weight)
        for name, value in first.pose.items()
    }
    tracks = {
        name: TrackSnapshot(
            value.existed or second.tracks[name].existed,
            value.value + (second.tracks[name].value - value.value) * weight,
        )
        for name, value in first.tracks.items()
    }
    return BranchFrame(
        pose,
        tracks,
        first.parent_map,
        first.reference_pose,
        first.reference_tracks,
        first.transform_scopes,
        first.track_scopes,
        first.model_space,
        interpolate_ik_targets(first.ik_targets, second.ik_targets, weight),
    )


def missing_clip_frame(input_frame: BranchFrame, additive_branch: bool) -> BranchFrame:
    """What a clip player outputs without its clip"""
    pose = reference_or_identity_pose(
        input_frame.reference_pose, additive=additive_branch
    )
    tracks = {
        name: TrackSnapshot(
            snapshot.existed,
            0.0
            if additive_branch
            else float(input_frame.reference_tracks.get(name, 0.0)),
        )
        for name, snapshot in input_frame.tracks.items()
    }
    return BranchFrame(
        pose,
        tracks,
        input_frame.parent_map,
        input_frame.reference_pose,
        input_frame.reference_tracks,
        input_frame.transform_scopes,
        input_frame.track_scopes,
        input_frame.model_space,
        ik_targets=input_frame.ik_targets,
    )
