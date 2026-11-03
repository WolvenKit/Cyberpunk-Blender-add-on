from __future__ import annotations

import os
from dataclasses import dataclass

from ...assetio.files import read_prefix
from ...assetio.index import IndexPolicy, build_asset_index, indexed_files
from ...assetio.paths import (
    local_path_key,
    normalize_local_path,
    split_source_tree_root,
)
from ...assetio.tweakdb import load_layered_tweak_database, tweakxl_load_order
from ...assetio.tweakdb_compiled import read_compiled_tweakdb
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)

REDMOD_TWEAKS = ("tools", "redmod", "tweaks")
VEHICLE_FOLDERS = (
    ("base", "gameplay", "static_data", "database", "vehicles"),
    ("ep1", "gameplay", "static_data", "database", "vehicles"),
)
# Phantom Liberty's database includes the base game's, so it is preferred when installed.
COMPILED_TWEAKDBS = (
    ("r6", "cache", "tweakdb_ep1.bin"),
    ("r6", "cache", "tweakdb.bin"),
)
TWEAK_EXTENSIONS = (".tweak", ".yaml", ".yml")
_PACKAGE_HEADER_BYTES = 256
_vehicle_selections = {}


@dataclass(frozen=True, slots=True)
class VehicleTweakSources:
    base_root: str
    base_files: tuple[str, ...]
    base_key: tuple
    compiled_tweakdb: str
    override_root: str
    override_files: tuple[str, ...]

    @property
    def summary(self):
        parts = [f"{len(self.base_files)} base sources from {self.base_root}"]
        if self.override_files:
            parts.append(
                f"{len(self.override_files)} project overrides from {self.override_root}"
            )
        if not self.compiled_tweakdb:
            parts.append("no compiled TweakDB; inline record names are estimated")
        return "; ".join(parts)


def _folder(value):
    """The normalized folder a user entered, or '' for a blank entry"""
    return normalize_local_path(value) if str(value or "").strip() else ""


def redmod_tweak_root(game_directory):
    """The RedMod tweaks folder of a game installation, or '' when the folder does not exist"""
    root = _folder(game_directory)
    if not root:
        return ""
    folder = os.path.join(root, *REDMOD_TWEAKS)
    return folder if os.path.isdir(folder) else ""


def compiled_tweakdb_path(game_directory):
    root = _folder(game_directory)
    if not root:
        return ""
    for parts in COMPILED_TWEAKDBS:
        path = os.path.join(root, *parts)
        if os.path.isfile(path):
            return path
    return ""


def _declares_vehicle_package(path):
    try:
        header = read_prefix(path, _PACKAGE_HEADER_BYTES).decode(
            "utf-8-sig", errors="replace"
        )
    except OSError:
        debug_exception(
            _LOG, "Could not read %s; it is not taken as a vehicle package", path
        )
        return False
    for line in header.splitlines():
        text = line.strip()
        if text and not text.startswith("//"):
            return text.split() == ["package", "Vehicle"]
    return False


def vehicle_base_files(root):
    """(files, cache key) for the vehicle sources of a tweaks folder"""
    index = build_asset_index(root, TWEAK_EXTENSIONS, policy=IndexPolicy.REUSE)
    key = (index.root.key, index.generation)
    cached = _vehicle_selections.get(key)
    if cached is not None:
        return cached, key
    vehicle_folders = [
        local_path_key(os.path.join(root, *parts)) + "/"
        for parts in VEHICLE_FOLDERS
        if os.path.isdir(os.path.join(root, *parts))
    ]
    if vehicle_folders:
        sources = indexed_files(index, ".tweak")
        files = tuple(
            sorted(
                path
                for path in sources
                if local_path_key(path).startswith(tuple(vehicle_folders))
                or _declares_vehicle_package(path)
            )
        )
    else:
        files = tuple(sorted(indexed_files(index, *TWEAK_EXTENSIONS)))
    _vehicle_selections.clear()
    _vehicle_selections[key] = files
    return files, key


def project_resources_root(source_path):
    """source/resources of the WolvenKit project an exported source/raw file belongs to, or ''"""
    resources, _relative = split_source_tree_root(source_path, "resources")
    if resources:
        return resources if os.path.isdir(resources) else ""
    raw_root, _relative = split_source_tree_root(source_path, "raw")
    if not raw_root:
        return ""
    folder = os.path.join(os.path.dirname(raw_root), "resources")
    return folder if os.path.isdir(folder) else ""


def project_tweak_files(resources_root):
    """The TweakXL sources of a project's source/resources folder, in TweakXL's order"""
    if not resources_root:
        return ()
    index = build_asset_index(
        resources_root, TWEAK_EXTENSIONS, policy=IndexPolicy.REUSE
    )
    return tuple(
        tweakxl_load_order(indexed_files(index, *TWEAK_EXTENSIONS), resources_root)
    )


def vehicle_tweak_sources(game_directory="", base_root="", project_source=""):
    """The sources for vehicle tweak data"""
    explicit = _folder(base_root)
    if explicit:
        if not os.path.isdir(explicit):
            raise ValueError(f"Tweak Data Root does not exist: {explicit}")
        root = explicit
    else:
        game = _folder(game_directory)
        if not game:
            raise ValueError("Set the Game Directory in the add-on preferences")
        root = redmod_tweak_root(game)
        if not root:
            raise ValueError(
                f"No RedMod tweaks folder at {os.path.join(game, *REDMOD_TWEAKS)}; install REDmod or set a Tweak Data Root"
            )
    base_files, base_key = vehicle_base_files(root)
    if not base_files:
        raise ValueError(f"No .tweak, .yaml, or .yml files were found below {root}")
    override_root = project_resources_root(project_source) if project_source else ""
    return VehicleTweakSources(
        root,
        base_files,
        base_key,
        compiled_tweakdb_path(game_directory),
        override_root,
        project_tweak_files(override_root),
    )


def load_vehicle_tweak_database(sources):
    compiled = (
        read_compiled_tweakdb(sources.compiled_tweakdb)
        if sources.compiled_tweakdb
        else None
    )
    return load_layered_tweak_database(
        sources.base_files, sources.override_files, compiled, base_key=sources.base_key
    )
