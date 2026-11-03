import os
from pathlib import Path

import bpy

from ...animation.domain.facial.validation import validate_setup
from ...animation.model.facial.setup import TrackSegments
from ...animation.services.facial.repository import FacialRepository
from ...animation.services.rig.parser import RigParseMode
from ...assetio.documents import DocumentSession, FileIdentity
from ...assetio.paths import local_path_key
from ...assetio.references import resource_references
from ...core.log import debug_exception, get_logger
from ..armature_bones import resolve_pose_bone
from ..rig_metadata import source_rig_paths

_LOG = get_logger(__name__)

_RESOURCE_CACHE_LIMIT = 8
_RESOURCES = {}


def resolve_resource(armature, setup_path, repository):
    setup = repository.setups.load(setup_path, required=True)
    paths = source_rig_paths(armature)
    if not paths:
        raise ValueError("The selected rig has no imported .rig.json source metadata")
    matches = []
    for path in paths:
        rig = repository.rigs.load(bpy.path.abspath(path), mode=RigParseMode.FACIAL)
        if rig is None:
            continue
        try:
            segments = TrackSegments.from_setup(setup, rig.num_tracks)
            validate_setup(setup, rig, segments)
        except ValueError:
            continue
        if all(
            resolve_pose_bone(armature, rig.bone_names[int(index)]) is not None
            for index in setup.used_bone_indices
        ):
            matches.append((path, rig))
    if len(matches) != 1:
        raise ValueError(
            f"Facial setup matches {len(matches)} source rigs; expected one unambiguous imported facial rig"
        )
    path, rig = matches[0]
    return repository.load(setup_path, path, required=True)


def _file_key(path):
    try:
        return FileIdentity.from_path(path).key
    except OSError:
        debug_exception(
            _LOG,
            "Could not read the size and time of %s; its cache key carries neither",
            path,
        )
        return local_path_key(path), None, None


def load_resource(armature, setup_path):
    """Resolve the facial resource for armature"""
    setup_path = bpy.path.abspath(setup_path)
    pose = getattr(armature, "pose", None)
    key = (
        _file_key(setup_path),
        tuple(_file_key(bpy.path.abspath(path)) for path in source_rig_paths(armature)),
        tuple(pose.bones.keys()) if pose is not None else (),
    )
    resource = _RESOURCES.get(key)
    if resource is None:
        with DocumentSession() as documents:
            resource = resolve_resource(
                armature, setup_path, FacialRepository(documents)
            )
        if len(_RESOURCES) >= _RESOURCE_CACHE_LIMIT:
            _RESOURCES.pop(next(iter(_RESOURCES)))
        _RESOURCES[key] = resource
    return resource


def clear_resource_cache():
    _RESOURCES.clear()


def discover_setup_paths(armature, resources, payloads) -> dict[str, str]:
    """Facial setup exports for an imported rig"""
    paths = {}
    for payload in payloads:
        for reference in resource_references(payload, ".facialsetup"):
            path = resources.resolve_export(reference, ".facialsetup.json")
            if path:
                paths[local_path_key(path)] = path
    if not paths:
        for rig_path in source_rig_paths(armature):
            sibling = str(rig_path)[:-9] + ".facialsetup.json"
            if Path(sibling).is_file():
                paths[local_path_key(sibling)] = sibling
    if not paths:
        folders = {
            local_path_key(os.path.dirname(path)) for path in source_rig_paths(armature)
        }
        for path in resources.files(".facialsetup.json"):
            if local_path_key(os.path.dirname(path)) in folders:
                paths[local_path_key(path)] = path
    return paths
