from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

from ..core.log import debug_exception, get_logger
from .paths import backslash_depot_key, strip_json_suffix
from .resources import get_rig_dir
from .values import cname_text

_LOG = get_logger(__name__)

BUNDLE_FORMAT = "cp77_metarig_bundle"
BUNDLE_VERSION = 1
_LISTING = {}


@dataclass(frozen=True)
class BundledRigPart:
    """One part"""

    path: str
    document: dict


@dataclass(frozen=True)
class MetaRigBundle:
    name: str
    rig_name: str
    parts: tuple[BundledRigPart, ...]
    properties: dict
    rest_bone_names: tuple[str, ...]
    rest_matrices: np.ndarray


def _json_value(array):
    return json.loads(np.asarray(array, dtype=np.uint8).tobytes().decode("utf-8"))


def _manifest(data, path) -> dict:
    manifest = _json_value(data["manifest"])
    if not isinstance(manifest, dict) or manifest.get("format") != BUNDLE_FORMAT:
        raise ValueError(f"{path} is not a MetaRig bundle")
    if int(manifest.get("version", 0)) > BUNDLE_VERSION:
        raise ValueError(
            f"{path} is a newer MetaRig bundle (version {manifest.get('version')}) than this add-on reads"
        )
    return manifest


def read_metarig_bundle(path) -> MetaRigBundle:
    try:
        with np.load(path, allow_pickle=False) as data:
            manifest = _manifest(data, path)
            parts = tuple(
                BundledRigPart(str(part_path), _json_value(data[f"part_{index:03d}"]))
                for index, part_path in enumerate(manifest["parts"])
            )
            bone_names = tuple(str(name) for name in data["rest_bone_names"])
            matrices = np.array(data["rest_matrices"], dtype=np.float64)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"{path} could not be read as a MetaRig bundle: {error}"
        ) from error
    return MetaRigBundle(
        name=str(manifest.get("name", "")),
        rig_name=str(manifest.get("rig_name", "")),
        parts=parts,
        properties=dict(manifest.get("properties") or {}),
        rest_bone_names=bone_names,
        rest_matrices=matrices,
    )


def read_metarig_bundle_name(path) -> str:
    """The bundle's display name, reading only its manifest"""
    with np.load(path, allow_pickle=False) as data:
        return str(_manifest(data, path).get("name", ""))


def bundled_metarigs() -> tuple[tuple[str, str, str], ...]:
    """(identifier, name, path) for each bundled MetaRig, by name"""
    try:
        entries = sorted(
            (
                entry
                for entry in os.scandir(get_rig_dir())
                if entry.is_file() and entry.name.casefold().endswith(".npz")
            ),
            key=lambda entry: entry.name.casefold(),
        )
        signature = tuple((entry.path, entry.stat().st_mtime_ns) for entry in entries)
    except OSError:
        debug_exception(_LOG, "Could not list the MetaRig bundles; none are offered")
        signature = ()
    cached = _LISTING.get("bundles")
    if cached is None or cached[0] != signature:
        bundles = []
        for path, _stamp in signature:
            identifier = os.path.basename(path)[: -len(".npz")]
            try:
                name = read_metarig_bundle_name(path)
            except (OSError, KeyError, ValueError):
                continue
            bundles.append((identifier, name or identifier, path))
        bundles.sort(key=lambda bundle: bundle[1].casefold())
        cached = (signature, tuple(bundles))
        _LISTING["bundles"] = cached
    return cached[1]


def _part_index():
    """(bundle path, part position) for each shipped part, by its depot path without .json"""
    bundles = bundled_metarigs()
    cached = _LISTING.get("parts")
    if cached is None or cached[0] != bundles:
        index = {}
        for identifier, _name, path in bundles:
            try:
                with np.load(path, allow_pickle=False) as data:
                    parts = _manifest(data, path)["parts"]
            except (OSError, KeyError, ValueError):
                debug_exception(_LOG, "MetaRig bundle %s lists no readable parts", path)
                continue
            for position, part_path in enumerate(parts):
                key = backslash_depot_key(strip_json_suffix(part_path))
                # A rig's own bundle (woman_base for woman_base.rig) wins over the characters that also bundle it.
                if (
                    key.rsplit("\\", 1)[-1] == f"{identifier}.rig".casefold()
                    or key not in index
                ):
                    index[key] = (path, position)
        cached = (bundles, index)
        _LISTING["parts"] = cached
    return cached[1]


def bundled_rig_document(rig_path) -> dict | None:
    """The rig document a shipped MetaRig bundles for the rig at depot path rig_path, or None"""
    entry = _part_index().get(backslash_depot_key(strip_json_suffix(rig_path)))
    if entry is None:
        return None
    path, position = entry
    with np.load(path, allow_pickle=False) as data:
        return _json_value(data[f"part_{position:03d}"])


def bundled_bone_parents(rig_path) -> dict[str, str]:
    """Each bone's parent bone name in the shipped MetaRig that bundles the rig at rig_path"""
    entry = _part_index().get(backslash_depot_key(strip_json_suffix(rig_path)))
    if entry is None:
        return {}
    parents = {}
    for part in read_metarig_bundle(entry[0]).parts:
        root = part.document.get("Data", {}).get("RootChunk", {})
        names = [cname_text(name) for name in root.get("boneNames", ())]
        for name, parent in zip(names, root.get("boneParentIndexes", ())):
            if 0 <= int(parent) < len(names):
                parents.setdefault(name, names[int(parent)])
    return parents
