from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from ....assetio.documents import DocumentSession, file_identity
from ....assetio.paths import (
    is_local_absolute,
    split_source_raw_root,
    split_source_tree_root,
    strip_json_suffix,
)
from ....assetio.transform_values import parse_wkit_trs
from ....bartmoss.trs import compose_matrices_wxyz
from ....redSpace.contracts import SOURCE_REST_SPACE_CONTRACT
from .repository import RigRepository, stored_rig_document


@dataclass(frozen=True, slots=True)
class AnimationRigExportSource:
    source_path: str
    rig_path: str
    bone_names: tuple[str, ...]
    parent_indices: tuple[int, ...]
    track_names: tuple[str, ...]
    source_rest: dict

    @property
    def skin_extras(self) -> dict:
        return {
            "rigPath": self.rig_path,
            "boneNames": list(self.bone_names),
            "boneParentIndexes": list(self.parent_indices),
            "trackNames": list(self.track_names),
        }


def _archive_rig_path(source_path: str, source_document: dict | None) -> str:
    header = (
        source_document.get("Header", {}) if isinstance(source_document, dict) else {}
    )
    value = str(header.get("ArchiveFileName", "") or "")
    if value and not is_local_absolute(value):
        return strip_json_suffix(value)
    if value:
        _archive_root, depot_path = split_source_tree_root(value, "archive")
        if depot_path:
            return strip_json_suffix(depot_path.replace("/", "\\"))
    if source_path and not is_local_absolute(source_path):
        # A bundled rig's part path is already relative to the depot.
        return strip_json_suffix(str(source_path).replace("/", "\\"))
    _root, relative = split_source_raw_root(source_path)
    return strip_json_suffix(str(relative or value or source_path).replace("/", "\\"))


def load_animation_rig_export_source(source_path: str) -> AnimationRigExportSource:
    source_path = str(source_path or "")
    if not source_path:
        raise ValueError(
            "A source rig must be selected for merged MetaRig animation export."
        )
    if stored_rig_document(source_path) is not None:
        # A bundled rig's part: the rig carries its document; there is no file.
        return _animation_rig_export_source(source_path)
    identity = file_identity(source_path)
    return _load_animation_rig_export_source_cached(
        identity.path.value, identity.mtime_ns, identity.size
    )


@lru_cache(maxsize=32)
def _load_animation_rig_export_source_cached(
    source_path: str, _mtime_ns: int, _size: int
) -> AnimationRigExportSource:
    return _animation_rig_export_source(source_path)


def _animation_rig_export_source(source_path: str) -> AnimationRigExportSource:
    with DocumentSession() as documents:
        rig_data = RigRepository(documents).load(source_path, required=True)

    bone_names = tuple(str(name) for name in rig_data.bone_names)
    parent_indices = tuple(int(value) for value in rig_data.parent_indices)
    if not bone_names or len(parent_indices) != len(bone_names):
        raise ValueError(
            f"Selected source rig has an invalid bone table: {source_path}"
        )
    if len(set(bone_names)) != len(bone_names):
        raise ValueError(
            f"Selected source rig contains duplicate bone names: {source_path}"
        )
    for index, parent_index in enumerate(parent_indices):
        if parent_index == -1:
            continue
        if parent_index < 0 or parent_index >= index:
            raise ValueError(
                f"Selected source rig has invalid parent index {parent_index} "
                f"for bone {bone_names[index]!r}: {source_path}"
            )

    transforms = list(rig_data.apose_ls or ())
    if len(transforms) != len(bone_names):
        transforms = list(rig_data.bone_transforms or ())
    if len(transforms) != len(bone_names):
        raise ValueError(
            f"Selected source rig has no complete local animation reference pose: {source_path}"
        )
    rotations, translations, scales = parse_wkit_trs(
        transforms,
        len(bone_names),
        quaternion_order="wxyz",
    )
    rest_relative = compose_matrices_wxyz(translations, rotations, scales)
    if not np.all(np.isfinite(rest_relative)):
        raise ValueError(
            f"Selected source rig contains a non-finite rest pose: {source_path}"
        )
    determinants = np.linalg.det(rest_relative[:, :3, :3])
    if np.any(np.abs(determinants) <= 1e-10):
        raise ValueError(
            f"Selected source rig contains a singular rest pose: {source_path}"
        )

    track_names = tuple(str(name) for name in rig_data.track_names)
    if len(set(track_names)) != len(track_names):
        raise ValueError(
            f"Selected source rig contains duplicate track names: {source_path}"
        )

    source_rest = {
        "version": 1,
        "space": SOURCE_REST_SPACE_CONTRACT,
        "boneNames": list(bone_names),
        "matrices": rest_relative.reshape(len(bone_names), 16).tolist(),
    }
    return AnimationRigExportSource(
        source_path=source_path,
        rig_path=_archive_rig_path(source_path, rig_data.source_document),
        bone_names=bone_names,
        parent_indices=parent_indices,
        track_names=track_names,
        source_rest=source_rest,
    )
