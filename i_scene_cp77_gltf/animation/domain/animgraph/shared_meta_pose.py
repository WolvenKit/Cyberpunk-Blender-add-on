from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from ....assetio.paths import local_path_key, normalize_depot_path
from ....bartmoss.qs_transform import QsTransform
from ....bartmoss.quaternion import slerp_xyzw
from ....bartmoss.scalar import lerp
from ...model.animgraph.evaluation import PoseOpEvaluation
from ..clip.additive import normalize_additive_type, normalize_track_mode
from ..rig.naming import merged_bone_name
from .topology import PreviewBoundary, has_link


@dataclass(frozen=True, slots=True)
class MetaRigPartScope:
    owner_index: int
    owner_path: str
    owner_name: str
    transform_names: tuple[str, ...]
    track_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SharedMetaPoseBinding:
    owner_index: int
    owner_path: str
    owner_name: str
    transform_names: tuple[str, ...]
    track_names: tuple[str, ...]
    owned_transform_names: tuple[str, ...]
    owned_track_names: tuple[str, ...]

    def with_resolved_names(
        self, transform_names: Sequence[str], track_names: Sequence[str]
    ) -> SharedMetaPoseBinding:
        return replace(
            self,
            transform_names=tuple(transform_names),
            track_names=tuple(track_names),
        )


def resource_stem(path: str, suffix: str) -> str:
    value = normalize_depot_path(str(path or ""))
    base = value.rsplit("/", 1)[-1]
    if not base.casefold().endswith(suffix.casefold()):
        return ""
    return base[: -len(suffix)]


def animgraph_stem(path: str) -> str:
    return resource_stem(path, ".animgraph.json") or resource_stem(path, ".animgraph")


def resolve_owner_index(
    animgraph_path: str,
    rig_paths: Sequence[str],
    part_bindings: Sequence[Mapping[str, Any]] = (),
) -> int:
    graph_stem = animgraph_stem(animgraph_path)
    if not graph_stem:
        raise ValueError(
            "MetaRig part ownership requires the imported AnimGraph source path"
        )

    path_index = {
        local_path_key(str(path or "")): index for index, path in enumerate(rig_paths)
    }
    association_matches = []
    for binding in part_bindings or ():
        if not isinstance(binding, Mapping):
            continue
        if (
            animgraph_stem(str(binding.get("graph", "") or "")).casefold()
            != graph_stem.casefold()
        ):
            continue
        index = path_index.get(local_path_key(str(binding.get("path", "") or "")))
        if index is None:
            index = path_index.get(
                local_path_key(str(binding.get("source_path", "") or ""))
            )
        if index is not None and index not in association_matches:
            association_matches.append(index)
    if len(association_matches) == 1:
        return association_matches[0]
    if len(association_matches) > 1:
        raise ValueError(
            f"AnimGraph {graph_stem!r} is assigned to multiple active MetaRig source parts"
        )

    matches = [
        index
        for index, path in enumerate(rig_paths)
        if resource_stem(path, ".rig.json").casefold() == graph_stem.casefold()
    ]
    if not matches:
        raise ValueError(
            f"SharedMetaPose could not match AnimGraph {graph_stem!r} to the active MetaRig source parts "
            "by component graph association or rig name"
        )
    if len(matches) != 1:
        raise ValueError(
            f"AnimGraph {graph_stem!r} matches multiple active MetaRig source parts"
        )
    return matches[0]


def build_part_scope(
    animgraph_path: str,
    rig_paths: Sequence[str],
    rig_datas: Sequence[Any],
    part_bindings: Sequence[Mapping[str, Any]] = (),
) -> MetaRigPartScope:
    paths = tuple(str(path or "") for path in rig_paths)
    datas = tuple(rig_datas)
    if not paths or len(paths) != len(datas):
        raise ValueError(
            "MetaRig part scope requires one loaded rig definition per active source part"
        )

    owner_index = resolve_owner_index(animgraph_path, paths, part_bindings)
    child = datas[owner_index]
    owned_bones = []
    seen_bones = set()
    for source_index, raw_name in enumerate(getattr(child, "bone_names", ()) or ()):
        if owner_index > 0 and source_index == 0:
            continue
        name = merged_bone_name(raw_name)
        if name and name not in seen_bones:
            seen_bones.add(name)
            owned_bones.append(name)

    owned_tracks = []
    seen_tracks = set()
    for raw_name in getattr(child, "track_names", ()) or ():
        name = str(raw_name or "")
        if name and name not in seen_tracks:
            seen_tracks.add(name)
            owned_tracks.append(name)

    return MetaRigPartScope(
        owner_index=owner_index,
        owner_path=paths[owner_index],
        owner_name=str(
            getattr(child, "rig_name", "")
            or resource_stem(paths[owner_index], ".rig.json")
        ),
        transform_names=tuple(owned_bones),
        track_names=tuple(owned_tracks),
    )


def build_binding(
    animgraph_path: str,
    rig_paths: Sequence[str],
    rig_datas: Sequence[Any],
    part_bindings: Sequence[Mapping[str, Any]] = (),
) -> SharedMetaPoseBinding:
    paths = tuple(str(path or "") for path in rig_paths)
    datas = tuple(rig_datas)
    if not paths or len(paths) != len(datas):
        raise ValueError(
            "SharedMetaPose requires one loaded rig definition per active MetaRig source part"
        )

    scope = build_part_scope(animgraph_path, paths, datas, part_bindings)
    owner_index = scope.owner_index
    child = datas[owner_index]
    parent_bones: set[str] = set()
    parent_tracks: set[str] = set()
    for rig_data in datas[:owner_index]:
        parent_bones.update(
            merged_bone_name(name) for name in getattr(rig_data, "bone_names", ()) or ()
        )
        parent_tracks.update(
            str(name) for name in getattr(rig_data, "track_names", ()) or ()
        )

    child_bones = tuple(getattr(child, "bone_names", ()) or ())
    transform_names = tuple(
        name
        for source_index, raw_name in enumerate(child_bones)
        if source_index != 0
        and (name := merged_bone_name(raw_name))
        and name in parent_bones
    )
    track_names = tuple(
        name
        for raw_name in (getattr(child, "track_names", ()) or ())
        if (name := str(raw_name or "")) and name in parent_tracks
    )
    return SharedMetaPoseBinding(
        owner_index=owner_index,
        owner_path=scope.owner_path,
        owner_name=scope.owner_name,
        transform_names=transform_names,
        track_names=track_names,
        owned_transform_names=scope.transform_names,
        owned_track_names=scope.track_names,
    )


def evaluate_shared_meta_pose(
    local_pose: MutableMapping[str, QsTransform],
    local_tracks: MutableMapping[str, float],
    parent_pose: Mapping[str, QsTransform],
    parent_tracks: Mapping[str, float],
    transform_names: Sequence[str],
    track_names: Sequence[str],
    weight: float,
) -> PoseOpEvaluation:
    weight = float(weight)
    if weight == 0.0:
        return PoseOpEvaluation((), (), False, "zero weight")

    written_bones: list[str] = []
    for name in transform_names:
        if name not in local_pose or name not in parent_pose:
            continue
        source = parent_pose[name]
        if weight == 1.0:
            local_pose[name] = source
        else:
            current = local_pose[name]
            local_pose[name] = QsTransform.from_components(
                lerp(current.translation, source.translation, weight),
                slerp_xyzw(current.rotation_xyzw, source.rotation_xyzw, weight),
                lerp(current.scale, source.scale, weight),
            )
        written_bones.append(name)

    written_tracks: list[str] = []
    for name in track_names:
        if name not in parent_tracks:
            continue
        source = float(parent_tracks[name])
        current = float(local_tracks.get(name, 0.0))
        local_tracks[name] = (
            source if weight == 1.0 else float(lerp(current, source, weight))
        )
        written_tracks.append(name)
    return PoseOpEvaluation(tuple(written_bones), tuple(written_tracks))


def shared_meta_pose_data(node):
    return {"hasWeightNode": has_link(node, "weightLink")}


def shared_meta_pose_additive_data(node):
    try:
        blend_tracks = normalize_track_mode(node.get("blendTracks", "AGBT_Add"))
        additive_type = normalize_additive_type(node.get("additiveType", "AGAT_Local"))
    except ValueError as error:
        raise PreviewBoundary(str(error)) from error
    if blend_tracks == "AGBT_BasePose":
        raise PreviewBoundary(
            "SharedMetaPoseAdditive does not support AGBT_BasePose track blending"
        )
    return {
        "hasWeightNode": has_link(node, "weightLink"),
        "additiveType": additive_type,
        "blendTracks": blend_tracks,
        "convertParentPoseToAdditive": bool(
            node.get("convertParentPoseToAdditive", True)
        ),
    }
